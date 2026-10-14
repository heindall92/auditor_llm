import base64
from io import BytesIO
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from agent_audit.hosted import HostedApp, deployment_origin
from agent_audit.models import ValidationError

ORIGIN = "https://audit.example"
PASSWORD = "random-test-password-0123456789"
TARGET = {"name": "Proveedor", "endpoint": "https://provider.example/v1/chat/completions", "model": "test-model"}


class HostedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict("os.environ", {"PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.app = HostedApp(Path(self.tmp.name), ORIGIN, PASSWORD)

    def request(self, path="/", payload=None, auth=True, host="audit.example", origin=ORIGIN, csrf=None, method=None):
        body = json.dumps(payload).encode() if payload is not None else b""
        environ = {"PATH_INFO": path, "HTTP_HOST": host, "REQUEST_METHOD": method or ("POST" if payload is not None else "GET"), "wsgi.input": BytesIO(body)}
        if auth:
            environ["HTTP_AUTHORIZATION"] = "Basic " + base64.b64encode(("auditor:" + (PASSWORD if auth is True else auth)).encode()).decode()
        if payload is not None:
            environ.update(CONTENT_LENGTH=str(len(body)), CONTENT_TYPE="application/json", HTTP_ORIGIN=origin, HTTP_X_AEGIS_CSRF=csrf or self.app.state.token)
        captured = {}
        def start(status, headers):
            captured.update(status=int(status.split()[0]), headers=dict(headers))
        captured["body"] = b"".join(self.app(environ, start))
        return captured

    def test_health_only_is_public(self):
        self.assertEqual(self.request("/healthz", auth=False)["status"], 200)
        for path in ["/", "/api/bootstrap", "/api/runs", "/api/report", "/app.js", "/icons/sprite.svg"]:
            response = self.request(path, auth=False)
            self.assertEqual(response["status"], 401, path)
            self.assertIn("WWW-Authenticate", response["headers"])
            self.assertNotIn(self.app.state.token.encode(), response["body"])

    def test_authenticated_bootstrap_and_assets(self):
        response = self.request("/api/bootstrap")
        self.assertEqual(response["status"], 200)
        data = json.loads(response["body"])
        self.assertTrue(data["hosted"])
        self.assertEqual(data["default_endpoint"], "")
        self.assertNotIn(PASSWORD.encode(), response["body"])
        self.assertEqual(self.request()["status"], 200)
        self.assertEqual(self.request("/../web.py")["status"], 404)

    def test_host_origin_and_csrf_remain_required(self):
        self.assertEqual(self.request(host="attacker.example")["status"], 403)
        for changes in [{"origin": "https://evil.example"}, {"csrf": "wrong"}]:
            self.assertEqual(self.request("/api/run", {"mode": "scripted", "scenario_ids": ["legitimate"]}, **changes)["status"], 403)

    def test_missing_config_or_changed_endpoint_cannot_receive_key(self):
        payload = {"mode": "llm_text", "scenario_ids": ["T01"], "target": TARGET, "authorized": True}
        self.assertEqual(self.request("/api/run", payload)["status"], 400)
        with patch.dict("os.environ", {"AEGIS_LLM_URL": TARGET["endpoint"], "AEGIS_LLM_MODEL": TARGET["model"], "AEGIS_LLM_API_KEY": "server-only-secret"}):
            payload["target"] = {**TARGET, "endpoint": "https://attacker.example/v1/chat/completions"}
            with patch("agent_audit.web.run_probe") as call:
                self.assertEqual(self.request("/api/run", payload)["status"], 400)
                call.assert_not_called()
            self.assertNotIn(b"server-only-secret", self.request("/api/bootstrap")["body"])

    def test_scripted_audit_end_to_end_without_provider(self):
        response = self.request("/api/run", {"mode": "scripted", "scenario_ids": ["legitimate", "unauthorized_effect", "insufficient_evidence"]})
        self.assertEqual(response["status"], 202)
        deadline = time.monotonic() + 5
        while self.app.state.job["status"] == "running" and time.monotonic() < deadline:
            time.sleep(.02)
        runs = json.loads(self.request("/api/runs")["body"])
        self.assertEqual({r["security_verdict"] for r in runs}, {"pass", "fail", "inconclusive"})
        self.assertEqual(self.request("/api/runs/" + runs[0]["run_id"])["status"], 200)

    def test_wrong_credentials_are_rate_limited(self):
        for _ in range(20):
            self.assertEqual(self.request(auth="incorrect-password")["status"], 401)
        self.assertEqual(self.request(auth="incorrect-password")["status"], 429)
        self.assertEqual(self.request("/healthz", auth=False)["status"], 200)
        self.app.failures = [time.monotonic() - 61]
        self.assertEqual(self.request()["status"], 200)

    def test_invalid_deployment_configuration_fails_closed(self):
        for origin in ["http://audit.example", "https://audit.example/path", "https://user:secret@audit.example", "https://audit.example?x=1", "https://audit.example:bad"]:
            with self.subTest(origin=origin), self.assertRaises(ValidationError):
                deployment_origin(origin)
        with self.assertRaises(ValidationError):
            HostedApp(self.tmp.name, ORIGIN, "short")
        for endpoint in ["http://localhost/v1/chat/completions", "https://127.0.0.1/v1/chat/completions", "https://169.254.169.254/v1/chat/completions"]:
            with patch.dict("os.environ", {"AEGIS_LLM_URL": endpoint, "AEGIS_LLM_MODEL": "model"}), self.assertRaises(ValidationError):
                HostedApp(self.tmp.name, ORIGIN, PASSWORD)

    def test_unsupported_methods_cannot_mutate(self):
        self.assertEqual(self.request("/api/run", method="DELETE")["status"], 405)
        self.assertIsNone(self.app.state.job)
