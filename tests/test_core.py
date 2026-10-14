import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from agent_audit.models import MAX_BYTES, Scenario, ValidationError, load_scenario
from agent_audit.runner import run_scenario

ROOT = Path(__file__).resolve().parents[1]


def fixture(name="legitimate"):
    return json.loads((ROOT / "fixtures" / f"{name}.json").read_text())


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)

    def run_data(self, data):
        return run_scenario(Scenario.from_dict(data), self.output)

    def test_three_expected_verdicts_and_exports(self):
        for name, verdict in [("legitimate", "pass"), ("unauthorized_effect", "fail"),
                              ("insufficient_evidence", "inconclusive")]:
            with self.subTest(name=name):
                summary, directory = self.run_data(fixture(name))
                self.assertEqual(summary["execution_status"], "completed")
                self.assertEqual(summary["security_verdict"], verdict)
                self.assertEqual(json.loads((directory / "summary.json").read_text()), summary)
                events = [json.loads(x) for x in (directory / "events.jsonl").read_text().splitlines()]
                self.assertTrue(all(e["run_id"] == summary["run_id"] for e in events))
                self.assertTrue(summary["synthetic"])
                self.assertIsNone(summary["model"])

    def test_fresh_run_ids_and_event_state(self):
        first, a = self.run_data(fixture("unauthorized_effect"))
        second, b = self.run_data(fixture())
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertNotEqual(a, b)
        self.assertEqual(second["observed_violation_sequences"], [])
        self.assertEqual(second["action_counts"]["completed"], 1)

    def test_block_everything_fails_legitimate_task(self):
        data = fixture()
        data["steps"][1]["kind"] = "blocked"
        result, _ = self.run_data(data)
        self.assertEqual(result["security_verdict"], "fail")
        self.assertEqual(result["reason"], "functional_expectation_mismatch")
        self.assertEqual(result["observed_violation_sequences"], [])

    def test_prohibited_attempt_blocked_is_not_a_completed_violation(self):
        data = fixture("unauthorized_effect")
        data["steps"][1]["kind"] = "blocked"
        result, _ = self.run_data(data)
        self.assertEqual(result["security_verdict"], "pass")
        self.assertEqual(result["action_counts"], {"attempted": 1, "blocked": 1, "completed": 0})

    def test_no_coverage_marker_never_passes(self):
        data = fixture()
        data["steps"].pop()
        result, _ = self.run_data(data)
        self.assertEqual(result["security_verdict"], "inconclusive")

    def test_unresolved_call_never_passes_even_with_coverage_claim(self):
        data = fixture()
        data["required_effects"] = []
        del data["steps"][1]
        result, _ = self.run_data(data)
        self.assertEqual(result["security_verdict"], "inconclusive")

    def test_positive_violation_survives_missing_coverage(self):
        data = fixture("unauthorized_effect")
        data["steps"].pop()
        result, _ = self.run_data(data)
        self.assertEqual(result["security_verdict"], "fail")
        self.assertEqual(result["observed_violation_sequences"], [2])

    def test_adapter_error_cannot_pass(self):
        data = fixture()
        data["steps"] = [{"kind": "error"}]
        result, _ = self.run_data(data)
        self.assertEqual(result["execution_status"], "error")
        self.assertEqual(result["security_verdict"], "inconclusive")

    def test_timeout_cannot_pass_and_worker_is_killed(self):
        data = fixture()
        data["timeout_seconds"] = 0.15
        data["steps"] = [{"kind": "delay", "seconds": 2}, {"kind": "coverage", "complete": True}]
        result, _ = self.run_data(data)
        self.assertEqual(result["execution_status"], "timeout")
        self.assertEqual(result["security_verdict"], "inconclusive")

    def test_partial_events_preserved_after_timeout(self):
        data = fixture("unauthorized_effect")
        data["timeout_seconds"] = 0.5
        data["steps"].insert(2, {"kind": "delay", "seconds": 2})
        result, directory = self.run_data(data)
        self.assertEqual(result["execution_status"], "timeout")
        self.assertEqual(result["security_verdict"], "inconclusive")
        self.assertEqual(result["observed_violation_sequences"], [2])
        self.assertEqual(len((directory / "events.jsonl").read_text().splitlines()), 2)

    def test_action_limit_cannot_pass(self):
        data = fixture()
        data["max_actions"] = 1
        data["steps"].insert(2, {"kind": "attempted", "call_id": "second", "tool": "create_ticket", "resource": "support"})
        result, _ = self.run_data(data)
        self.assertEqual(result["diagnostic"], "action_limit_exceeded")
        self.assertEqual(result["execution_status"], "error")
        self.assertEqual(result["security_verdict"], "inconclusive")

    def test_extra_permitted_effect_is_functional_failure(self):
        data = fixture()
        data["steps"][2:2] = [
            {"kind": "attempted", "call_id": "second", "tool": "create_ticket", "resource": "support"},
            {"kind": "completed", "call_id": "second", "tool": "create_ticket", "resource": "support"}]
        result, _ = self.run_data(data)
        self.assertEqual(result["reason"], "functional_expectation_mismatch")

    def test_unknown_fields_rejected(self):
        data = fixture()
        data["shell_command"] = "never execute"
        with self.assertRaises(ValidationError):
            Scenario.from_dict(data)

    def test_invalid_types_and_bounds_rejected(self):
        for key, value in [("timeout_seconds", True), ("timeout_seconds", float("nan")),
                           ("timeout_seconds", 0), ("max_actions", False),
                           ("max_actions", 1000), ("steps", "text"),
                           ("schema_version", "unsupported"), ("scenario_id", "../escape")]:
            with self.subTest(key=key, value=value):
                data = fixture()
                data[key] = value
                with self.assertRaises(ValidationError):
                    Scenario.from_dict(data)

    def test_invalid_call_lifecycles_rejected(self):
        mutations = []
        data = fixture()
        data["steps"][1]["call_id"] = "missing"
        mutations.append(data)
        data = fixture()
        data["steps"].insert(2, copy.deepcopy(data["steps"][1]))
        mutations.append(data)
        data = fixture()
        data["steps"][1]["resource"] = "other"
        mutations.append(data)
        for data in mutations:
            with self.assertRaises(ValidationError):
                Scenario.from_dict(data)

    def test_invalid_policy_and_expectations_rejected(self):
        for mutate in [
            lambda d: d["policy"]["allowed_resources"].update({"shell": []}),
            lambda d: d["required_effects"][0].update({"resource": "private"}),
            lambda d: d["required_effects"][0].update({"count": True}),
            lambda d: d["required_effects"].append(d["required_effects"][0]),
            lambda d: d["steps"][2].update({"complete": "true"}),
        ]:
            data = fixture()
            mutate(data)
            with self.assertRaises(ValidationError):
                Scenario.from_dict(data)

    def test_duplicate_json_and_bad_encoding_rejected(self):
        path = self.output / "bad.json"
        for raw in [b'{"a":1,"a":2}', b'\xff', b'{', b'[' * 1500]:
            path.write_bytes(raw)
            with self.assertRaises(ValidationError):
                load_scenario(path)

    def test_oversized_input_rejected(self):
        path = self.output / "large.json"
        path.write_bytes(b" " * (MAX_BYTES + 1))
        with self.assertRaises(ValidationError):
            load_scenario(path)

    def test_worker_protocol_corruption_is_inconclusive(self):
        proc = subprocess.CompletedProcess([], 0, stdout='{"kind":"coverage"}\n', stderr="")
        with patch("agent_audit.runner.subprocess.run", return_value=proc):
            result, _ = self.run_data(fixture())
        self.assertEqual(result["execution_status"], "error")
        self.assertEqual(result["diagnostic"], "worker_protocol_error")
        self.assertEqual(result["security_verdict"], "inconclusive")

    def test_missing_worker_does_not_pass(self):
        with patch("agent_audit.runner.subprocess.run", side_effect=OSError):
            result, _ = self.run_data(fixture())
        self.assertEqual(result["diagnostic"], "worker_unavailable")
        self.assertEqual(result["security_verdict"], "inconclusive")

    def test_cli_exit_codes(self):
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        for name, code in [("legitimate", 0), ("unauthorized_effect", 1), ("insufficient_evidence", 2)]:
            proc = subprocess.run([sys.executable, "-m", "agent_audit", "run",
                                   str(ROOT / "fixtures" / f"{name}.json"), "--output", str(self.output)],
                                  capture_output=True, text=True, env=env, check=False)
            self.assertEqual(proc.returncode, code, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["adapter"], "scripted")
        proc = subprocess.run([sys.executable, "-m", "agent_audit", "validate", str(self.output / "missing.json")],
                              capture_output=True, text=True, env=env, check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stderr)["security_verdict"], "inconclusive")


if __name__ == "__main__":
    unittest.main()

