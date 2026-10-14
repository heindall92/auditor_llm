"""Single-operator WSGI deployment behind a trusted HTTPS hosting edge."""
import base64
import binascii
from email.message import Message
import hashlib
from http import HTTPStatus
import ipaddress
import json
import os
import secrets
import threading
import time
from urllib.parse import urlsplit

from .llm_text import validate_target
from .models import ValidationError
from .web import AuditRoutes, State


class Gateway(AuditRoutes):
    """Use the same routes as the local server without opening an internal socket."""
    def __init__(self, state, environ):
        self.state = state
        self.path = environ.get("PATH_INFO", "/")
        if environ.get("QUERY_STRING"):
            self.path += "?" + environ["QUERY_STRING"]
        self.headers = Message()
        for key, value in environ.items():
            if key.startswith("HTTP_"):
                self.headers[key[5:].replace("_", "-")] = value
        for key in ("CONTENT_TYPE", "CONTENT_LENGTH"):
            if environ.get(key):
                self.headers[key.replace("_", "-")] = environ[key]
        self.rfile = environ["wsgi.input"]

    def valid_host(self):
        return self.headers.get("Host") == urlsplit(self.state.public_origin).netloc

    def send(self, status, data, content_type="application/json; charset=utf-8"):
        body = json.dumps(data, ensure_ascii=False).encode() if content_type.startswith("application/json") else data if isinstance(data, bytes) else data.encode()
        return status, [("Content-Type", content_type), ("Content-Length", str(len(body))),
                        ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                        ("Referrer-Policy", "no-referrer"),
                        ("Strict-Transport-Security", "max-age=31536000"),
                        ("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")], body


def deployment_origin(value):
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValidationError("AUDITOR_PUBLIC_ORIGIN no es válido.") from exc
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment or port not in (None, 443)):
        raise ValidationError("Configura un origen HTTPS sin ruta ni credenciales.")
    return value


def check_endpoint_configuration():
    endpoint = os.environ.get("AEGIS_LLM_URL", "")
    model = os.environ.get("AEGIS_LLM_MODEL", "")
    if not endpoint:
        if model or os.environ.get("AEGIS_LLM_API_KEY"):
            raise ValidationError("Configura AEGIS_LLM_URL y AEGIS_LLM_MODEL antes de añadir una clave.")
        return
    validate_target({"name": "Servidor", "endpoint": endpoint, "model": model})
    parsed = urlsplit(endpoint)
    if parsed.scheme != "https" or parsed.hostname == "localhost":
        raise ValidationError("El endpoint alojado debe usar HTTPS público.")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return
    if not address.is_global:
        raise ValidationError("No se permiten direcciones IP internas como endpoint alojado.")


class HostedApp:
    def __init__(self, output, origin, password):
        self.origin = deployment_origin(origin)
        if len(password) < 24 or len(password) > 256 or not password.isascii() or any(ord(c) < 33 for c in password):
            raise ValidationError("AUDITOR_ADMIN_PASSWORD necesita entre 24 y 256 caracteres ASCII sin espacios.")
        check_endpoint_configuration()
        self.state = State(output, public_origin=self.origin)
        # A fixed-size digest supports constant-time comparison without retaining the password.
        # The generated password must be random; this is not a password database.
        self.credential = hashlib.sha256(("auditor:" + password).encode()).digest()
        self.auth_lock = threading.Lock()
        self.failures = []

    def authenticate(self, header):
        now = time.monotonic()
        with self.auth_lock:
            self.failures = [t for t in self.failures if now - t < 60]
            if len(self.failures) >= 20:
                return 429
        try:
            scheme, encoded = header.split(" ", 1)
            raw = base64.b64decode(encoded, validate=True) if scheme.lower() == "basic" else b""
        except (ValueError, binascii.Error):
            raw = b""
        if secrets.compare_digest(hashlib.sha256(raw).digest(), self.credential):
            return 200
        # Missing credentials trigger the browser prompt without consuming attempts.
        if header:
            with self.auth_lock:
                self.failures.append(now)
        return 401

    def __call__(self, environ, start_response):
        route = Gateway(self.state, environ)
        method = environ.get("REQUEST_METHOD", "GET")
        # No state, hostname, version, paths or configuration are exposed by health checks.
        if route.path == "/healthz" and method in ("GET", "HEAD"):
            result = route.send(200, {"status": "ok"})
        elif not route.valid_host():
            result = route.send(403, {"error": "Host no permitido."})
        else:
            auth_status = self.authenticate(environ.get("HTTP_AUTHORIZATION", ""))
            if auth_status != 200:
                result = route.send(auth_status, {"error": "Acceso protegido." if auth_status == 401 else "Demasiados intentos. Espera un minuto."})
                if auth_status == 401:
                    result[1].append(("WWW-Authenticate", 'Basic realm="auditor_llm", charset="UTF-8"'))
                else:
                    result[1].append(("Retry-After", "60"))
            elif method == "GET":
                result = route.do_GET()
            elif method == "POST":
                result = route.do_POST()
            else:
                result = route.send(405, {"error": "Método no permitido."})
                result[1].append(("Allow", "GET, POST"))
        status, headers, body = result
        start_response(f"{status} {HTTPStatus(status).phrase}", headers)
        return [b"" if method == "HEAD" else body]


def create_app():
    origin = os.environ.get("AUDITOR_PUBLIC_ORIGIN") or os.environ.get("RENDER_EXTERNAL_URL", "")
    return HostedApp(os.environ.get("AUDITOR_OUTPUT_DIR", "/app/output/web"), origin,
                     os.environ.get("AUDITOR_ADMIN_PASSWORD", ""))


def main():
    from waitress import serve
    try:
        app = create_app()
        port = int(os.environ.get("PORT", "10000"))
        if not 1 <= port <= 65535:
            raise ValueError
    except (ValidationError, ValueError) as exc:
        # Configuration errors contain no secret values.
        raise SystemExit(str(exc) or "PORT no válido.") from None
    serve(app, host="0.0.0.0", port=port, threads=4, connection_limit=100,
          channel_timeout=30, max_request_header_size=16384, max_request_body_size=1048576,
          clear_untrusted_proxy_headers=True, expose_tracebacks=False, ident="auditor_llm")


if __name__ == "__main__":
    main()
