"""Local-only HTTP bridge. No remote hosting or browser credentials."""
from copy import deepcopy
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import urlsplit
from uuid import uuid4

from .llm_text import EndpointError, PROBES, run_probe, validate_target
from .models import Scenario, ValidationError, load_scenario, no_duplicates
from .runner import run_scenario

HERE = Path(__file__).resolve().parent


class State:
    def __init__(self, output):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.job = None

    def runs(self):
        result = []
        for path in self.output.glob("*/summary.json"):
            try:
                summary = json.loads(path.read_text(encoding="utf-8"))
                if summary.get("run_id") == path.parent.name:
                    result.append(summary)
            except (OSError, ValueError, AttributeError):
                continue
        return sorted(result, key=lambda r: r.get("started_utc", ""), reverse=True)

    def start(self, payload):
        if not isinstance(payload, dict) or set(payload) - {"mode", "scenario_ids", "target", "repetitions", "max_tokens", "timeout_seconds", "custom_scenario", "authorized"}:
            raise ValidationError("Petición no válida.")
        mode = payload.get("mode")
        if mode not in ("scripted", "llm_text"):
            raise ValidationError("Selecciona laboratorio o LLM.")
        ids = payload.get("scenario_ids", [])
        if not isinstance(ids, list) or not ids or len(ids) > 10 or any(not isinstance(x, str) for x in ids) or len(set(ids)) != len(ids):
            raise ValidationError("Selecciona entre 1 y 10 pruebas diferentes.")
        repetitions = payload.get("repetitions", 1)
        tokens = payload.get("max_tokens", 256)
        timeout = payload.get("timeout_seconds", 15)
        if type(repetitions) is not int or not 1 <= repetitions <= 3:
            raise ValidationError("Usa entre 1 y 3 repeticiones.")
        if type(tokens) is not int or not 32 <= tokens <= 1024 or type(timeout) is not int or not 5 <= timeout <= 30:
            raise ValidationError("Revisa los límites de tokens y tiempo.")
        custom = None
        if payload.get("custom_scenario") is not None:
            custom = Scenario.from_dict(payload["custom_scenario"])
        target = validate_target(payload.get("target")) if mode == "llm_text" else None
        if mode == "llm_text" and payload.get("authorized") is not True:
            raise ValidationError("Confirma que el endpoint está autorizado para las pruebas.")
        available = {p["id"] for p in PROBES} if mode == "llm_text" else {"legitimate", "unauthorized_effect", "insufficient_evidence"} | ({"custom"} if custom else set())
        if any(x not in available for x in ids):
            raise ValidationError("La selección contiene una prueba desconocida.")
        with self.lock:
            if self.job and self.job["status"] == "running":
                raise ValidationError("Ya hay una ejecución activa.")
            self.job = {"job_id": uuid4().hex, "status": "running", "total": len(ids) * repetitions,
                        "completed": 0, "run_ids": [], "cancel_requested": False, "error": None}
            snapshot = deepcopy(self.job)
        threading.Thread(target=self._work, args=(mode, ids, repetitions, target, tokens, timeout, custom), daemon=True).start()
        return snapshot

    def _work(self, mode, ids, repetitions, target, tokens, timeout, custom):
        try:
            for repetition in range(repetitions):
                for sid in ids:
                    with self.lock:
                        if self.job["cancel_requested"]:
                            self.job["status"] = "cancelled"
                            return
                    if mode == "scripted":
                        scenario = custom if sid == "custom" else load_scenario(HERE / "data" / (sid + ".json"))
                        summary, _ = run_scenario(scenario, self.output)
                    else:
                        summary = run_probe(next(p for p in PROBES if p["id"] == sid), target, self.output, tokens, timeout)
                    with self.lock:
                        self.job["completed"] += 1
                        self.job["run_ids"].append(summary["run_id"])
            with self.lock:
                self.job["status"] = "completed"
        except Exception:
            with self.lock:
                self.job.update(status="error", error="No se pudo completar el trabajo. Revisa el directorio de salida y la configuración.")


def report_html(runs):
    rows = "".join("<tr>" + "".join("<td>" + escape(str(r.get(k, "—"))) + "</td>" for k in ("scenario_id", "adapter", "model", "execution_status", "security_verdict", "reason")) + "</tr>" for r in runs)
    return ('<!doctype html><html lang="es"><meta charset="utf-8"><title>auditor_llm · Informe</title>'
            '<meta name="viewport" content="width=device-width"><style>body{font:16px/1.6 system-ui;margin:40px;color:#172326}table{border-collapse:collapse;width:100%}td,th{padding:12px;text-align:left;border-bottom:1px solid #ddd}h1{letter-spacing:-.04em}@media print{body{margin:0}}</style>'
            '<h1>auditor_llm · Evidencia de auditoría</h1><p>Resultados de los escenarios ejecutados. Las pruebas guionizadas son sintéticas. '
            'Las pruebas LLM observan solo texto; pass significa que se cumple el oráculo concreto, no que el agente sea seguro.</p>'
            '<table><thead><tr><th>Prueba</th><th>Adaptador</th><th>Modelo</th><th>Ejecución</th><th>Resultado</th><th>Motivo</th></tr></thead><tbody>' + rows + '</tbody></table></html>')


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def valid_host(self):
            port = self.server.server_port
            return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

        def send(self, status, data, content_type="application/json; charset=utf-8"):
            body = json.dumps(data, ensure_ascii=False).encode() if content_type.startswith("application/json") else data if isinstance(data, bytes) else data.encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.valid_host():
                return self.send(403, {"error": "Host no permitido."})
            path = urlsplit(self.path).path
            if path == "/api/bootstrap":
                with state.lock:
                    job = deepcopy(state.job)
                return self.send(200, {"csrf_token": state.token, "job": job, "probes": PROBES,
                                      "key_configured": bool(os.environ.get("AEGIS_LLM_API_KEY")),
                                      "default_endpoint": os.environ.get("AEGIS_LLM_URL", "http://127.0.0.1:11434/v1/chat/completions"),
                                      "default_model": os.environ.get("AEGIS_LLM_MODEL", ""), "version": "0.0.2"})
            if path == "/api/runs":
                return self.send(200, state.runs())
            if path == "/api/job":
                with state.lock:
                    return self.send(200, deepcopy(state.job))
            if path == "/api/report":
                return self.send(200, report_html(state.runs()), "text/html; charset=utf-8")
            if path.startswith("/api/runs/"):
                rid = path.removeprefix("/api/runs/")
                if not re.fullmatch("[a-f0-9]{32}", rid):
                    return self.send(404, {"error": "Ejecución no encontrada."})
                directory = state.output / rid
                try:
                    summary = json.loads((directory / "summary.json").read_text())
                    events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
                    return self.send(200, {"summary": summary, "events": events})
                except (OSError, ValueError):
                    return self.send(404, {"error": "Ejecución no encontrada."})
            if path.startswith("/api/fixture/"):
                name = path.removeprefix("/api/fixture/")
                if name in {"legitimate", "unauthorized_effect", "insufficient_evidence"}:
                    return self.send(200, load_scenario(HERE / "data" / (name + ".json")).to_dict())
                return self.send(404, {"error": "Escenario no encontrado."})
            relative = "index.html" if path == "/" else path.lstrip("/")
            static = (HERE / "static" / relative).resolve()
            if not static.is_relative_to((HERE / "static").resolve()) or not static.is_file():
                return self.send(404, {"error": "Archivo no encontrado."})
            types = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}
            return self.send(200, static.read_bytes(), types.get(static.suffix, "text/plain; charset=utf-8"))

        def do_POST(self):
            origins = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
            if not self.valid_host() or self.headers.get("Origin") not in origins or not secrets.compare_digest(self.headers.get("X-Aegis-CSRF", ""), state.token):
                return self.send(403, {"error": "Petición local no autorizada."})
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.send(415, {"error": "Se requiere JSON."})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1048576:
                    raise ValidationError("Entrada vacía o demasiado grande.")
                data = json.loads(self.rfile.read(length), object_pairs_hook=no_duplicates)
                if self.path == "/api/run":
                    return self.send(202, state.start(data))
                if self.path == "/api/validate":
                    return self.send(200, {"valid": True, "scenario": Scenario.from_dict(data).to_dict()})
                if self.path == "/api/cancel":
                    with state.lock:
                        if state.job and state.job["status"] == "running":
                            state.job["cancel_requested"] = True
                    return self.send(200, {"message": "La ejecución se detendrá al terminar la petición en curso."})
                return self.send(404, {"error": "Operación no encontrada."})
            except (ValidationError, EndpointError) as exc:
                return self.send(400, {"error": str(exc)})
            except (ValueError, TypeError, RecursionError):
                return self.send(400, {"error": "JSON no válido."})

    return Handler


def serve(port, output):
    if not 1 <= port <= 65535:
        raise ValidationError("El puerto debe estar entre 1 y 65535.")
    state = State(output)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    print(f"auditor_llm · http://127.0.0.1:{port} · Solo acceso local. Ctrl+C para cerrar.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
