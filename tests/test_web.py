import io
import json
import re
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from agent_audit.llm_text import EndpointError, PROBES, completion, run_probe, validate_target
from agent_audit.web import State, make_handler, report_html

TARGET = {"name": "Local test double", "endpoint": "http://127.0.0.1:9999/v1/chat/completions", "model": "test-double"}


class TextProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name)

    def test_target_constraints(self):
        self.assertEqual(validate_target(TARGET), TARGET)
        for endpoint in ["http://example.com/v1/chat/completions", "file:///tmp/token", "https://user:password@example.com/v1/chat/completions", "https://example.com/v1/chat/completions?key=secret", "https://example.com/wrong", "https://example.com:bad/v1/chat/completions"]:
            with self.subTest(endpoint=endpoint), self.assertRaises(EndpointError):
                validate_target({**TARGET, "endpoint": endpoint})

    def test_functional_probe(self):
        with patch("agent_audit.llm_text.completion", return_value=("AEGIS_OK", "stop", {})):
            result = run_probe(PROBES[0], TARGET, self.output)
        self.assertEqual(result["security_verdict"], "pass")
        self.assertEqual(result["coverage"], "text_output_only")
        self.assertTrue(result["synthetic_inputs"])
        self.assertEqual(result["adapter"], "llm_text")

    def test_literal_leak_detected_from_sent_canary(self):
        def echo(target, messages, max_tokens, timeout):
            canary = re.search(r"AEGIS_SYNTHETIC_[a-f0-9]{32}", messages[0]["content"])[0]
            return canary, "length", {"total_tokens": 12}
        with patch("agent_audit.llm_text.completion", side_effect=echo):
            result = run_probe(PROBES[1], TARGET, self.output)
        self.assertEqual(result["security_verdict"], "fail")
        self.assertEqual(result["reason"], "synthetic_canary_disclosed")
        self.assertEqual(result["usage"]["total_tokens"], 12)

    def test_no_literal_leak_scoped_pass(self):
        with patch("agent_audit.llm_text.completion", return_value=("No puedo revelar ese marcador.", "stop", {})):
            result = run_probe(PROBES[1], TARGET, self.output)
        self.assertEqual(result["security_verdict"], "pass")
        self.assertEqual(result["reason"], "literal_canary_not_observed")

    def test_incomplete_response_does_not_pass(self):
        for finish in ["length", None, "content_filter"]:
            with self.subTest(finish=finish), patch("agent_audit.llm_text.completion", return_value=("partial", finish, {})):
                result = run_probe(PROBES[1], TARGET, self.output)
                self.assertEqual(result["security_verdict"], "inconclusive")

    def test_network_and_protocol_errors_inconclusive(self):
        for error in [TimeoutError(), OSError(), KeyError(), ValueError()]:
            with self.subTest(error=type(error).__name__), patch("agent_audit.llm_text.completion", side_effect=error):
                result = run_probe(PROBES[1], TARGET, self.output)
                self.assertIn(result["execution_status"], {"error", "timeout"})
                self.assertEqual(result["security_verdict"], "inconclusive")

    def test_agent_instrumentation_probe_skips_without_network(self):
        with patch("agent_audit.llm_text.completion") as mocked:
            result = run_probe(PROBES[-1], TARGET, self.output)
        mocked.assert_not_called()
        self.assertEqual(result["execution_status"], "skipped")
        self.assertEqual(result["security_verdict"], "inconclusive")

    def test_key_redaction_and_fixed_protocol(self):
        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *args): self.close()
        secret = "test-secret-not-a-real-key"
        fake = Response(json.dumps({"choices": [{"message": {"content": secret}, "finish_reason": "stop"}]}).encode())
        with patch.dict("os.environ", {"AEGIS_LLM_API_KEY": secret}), patch("agent_audit.llm_text.build_opener") as opener:
            opener.return_value.open.return_value = fake
            text, finish, usage = completion(TARGET, [{"role": "user", "content": "test"}], 32, 5)
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_header("Authorization"), "Bearer " + secret)
            self.assertFalse(json.loads(request.data)["stream"])
        self.assertNotIn(secret, text)

    def test_http_transport_against_local_test_double(self):
        received = []
        class FakeProvider(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                received.append(payload)
                raw = json.dumps({"choices": [{"message": {"content": "AEGIS_OK"}, "finish_reason": "stop"}], "usage": {"total_tokens": 10}}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeProvider)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            target = {**TARGET, "endpoint": f"http://127.0.0.1:{server.server_port}/v1/chat/completions"}
            result = run_probe(PROBES[0], target, self.output)
            self.assertEqual(result["security_verdict"], "pass")
            self.assertEqual(received[0]["model"], "test-double")
            self.assertEqual(received[0]["max_tokens"], 256)
            self.assertEqual(result["usage"]["total_tokens"], 10)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


class LocalWebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.state = State(Path(cls.tmp.name))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.state))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.tmp.cleanup()

    def request(self, path, payload=None, headers=None):
        data = None if payload is None else json.dumps(payload).encode()
        default = {} if payload is None else {"Content-Type": "application/json", "Origin": self.base, "X-Aegis-CSRF": self.state.token}
        return urlopen(Request(self.base + path, data=data, headers={**default, **(headers or {})}), timeout=5)

    def test_bootstrap_has_no_key_value(self):
        with patch.dict("os.environ", {"AEGIS_LLM_API_KEY": "test-key-hidden"}), self.request("/api/bootstrap") as r:
            raw = r.read().decode()
            self.assertNotIn("test-key-hidden", raw)
            data = json.loads(raw)
            self.assertTrue(data["key_configured"])
            self.assertEqual(len(data["probes"]), 10)
            self.assertIn("frame-ancestors 'none'", r.headers["Content-Security-Policy"])

    def test_static_assets_and_traversal(self):
        for path in ["/", "/app.js", "/styles.css", "/icons/sprite.svg"]:
            with self.subTest(path=path), self.request(path) as r:
                self.assertEqual(r.status, 200)
                self.assertTrue(r.read())
        with self.assertRaises(HTTPError) as err:
            self.request("/../web.py")
        self.assertEqual(err.exception.code, 404)

    def test_reject_host_and_cross_origin_mutation(self):
        with self.assertRaises(HTTPError) as err:
            self.request("/api/bootstrap", headers={"Host": "attacker.example"})
        self.assertEqual(err.exception.code, 403)
        for headers in [{"Origin": "https://attacker.example"}, {"X-Aegis-CSRF": "wrong"}]:
            with self.assertRaises(HTTPError) as err:
                self.request("/api/run", {}, headers)
            self.assertEqual(err.exception.code, 403)

    def test_validate_and_run_scripted_end_to_end(self):
        with self.request("/api/fixture/legitimate") as r:
            scenario = json.load(r)
        with self.request("/api/validate", scenario) as r:
            self.assertTrue(json.load(r)["valid"])
        with self.request("/api/run", {"mode": "scripted", "scenario_ids": ["legitimate", "unauthorized_effect", "insufficient_evidence"]}) as r:
            self.assertEqual(r.status, 202)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with self.request("/api/job") as r:
                job = json.load(r)
            if job["status"] != "running": break
            time.sleep(.02)
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["completed"], 3)
        with self.request("/api/runs") as r:
            runs = json.load(r)
        selected = [x for x in runs if x["run_id"] in job["run_ids"]]
        self.assertEqual({x["security_verdict"] for x in selected}, {"pass", "fail", "inconclusive"})
        with self.request("/api/runs/" + selected[0]["run_id"]) as r:
            self.assertTrue(json.load(r)["events"])

    def test_bounds_unknown_scenario_and_authorization(self):
        for payload in [
            {"mode": "scripted", "scenario_ids": ["missing"]},
            {"mode": "scripted", "scenario_ids": ["legitimate"], "repetitions": 100},
            {"mode": "scripted", "scenario_ids": ["legitimate"], "timeout_seconds": True},
            {"mode": "llm_text", "scenario_ids": ["T01"], "target": TARGET},
        ]:
            with self.subTest(payload=payload), self.assertRaises(HTTPError) as err:
                self.request("/api/run", payload)
            self.assertEqual(err.exception.code, 400)

    def test_export_html_escapes_untrusted_fields(self):
        html = report_html([{"scenario_id": "<script>alert(1)</script>", "reason": '<img src=x onerror="alert(1)">'}])
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;script&gt;", html)

