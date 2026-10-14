from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from . import __version__
from .evaluator import evaluate
from .models import Scenario


def _parse_events(output, run_id, scenario):
    if isinstance(output, bytes):
        output = output.decode("utf-8")
    events = [json.loads(line) for line in (output or "").splitlines() if line.strip()]
    if len(events) > 200:
        raise ValueError("event limit")
    expected_steps = [s for s in scenario.steps if s["kind"] not in ("delay", "error")]
    for sequence, event in enumerate(events, 1):
        base = {"schema_version", "run_id", "scenario_id", "sequence", "timestamp_utc", "user_id", "synthetic"}
        step = expected_steps[sequence - 1]
        if (set(event) != base | set(step) or
            event["run_id"] != run_id or event["scenario_id"] != scenario.scenario_id or
            event["sequence"] != sequence or event["user_id"] != scenario.user_id or
            event["synthetic"] is not True or event["schema_version"] != "1.0" or
            any(event[k] != v for k, v in step.items())):
            raise ValueError("invalid worker event")
        datetime.fromisoformat(event["timestamp_utc"])
    return events


def run_scenario(scenario: Scenario, output_dir: Path):
    # Each run gets a fresh worker and a new exclusive directory.
    run_id = uuid4().hex
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    status, diagnostic, events = "completed", None, []
    started = datetime.now(timezone.utc).isoformat()
    payload = json.dumps({"run_id": run_id, "scenario": scenario.to_dict()})
    output = ""
    try:
        proc = subprocess.run([sys.executable, "-m", "agent_audit.worker"], input=payload,
                              text=True, capture_output=True, timeout=scenario.timeout_seconds,
                              check=False)
        output = proc.stdout
        if proc.returncode != 0:
            status = "error"
            diagnostic = "action_limit_exceeded" if proc.returncode == 4 else "adapter_error"
    except subprocess.TimeoutExpired as exc:
        status, diagnostic, output = "timeout", "deadline_exceeded", exc.stdout
    except OSError:
        status, diagnostic = "error", "worker_unavailable"
    try:
        events = _parse_events(output, run_id, scenario)
        expected_events = sum(s["kind"] not in ("delay", "error") for s in scenario.steps)
        if status == "completed" and len(events) != expected_events:
            status, diagnostic = "error", "worker_protocol_error"
    except (ValueError, KeyError, TypeError, IndexError, UnicodeDecodeError):
        status, diagnostic, events = "error", "worker_protocol_error", []
    summary = {
        "schema_version": "1.0", "run_id": run_id,
        "scenario_id": scenario.scenario_id, "scenario_version": scenario.version,
        "policy_id": scenario.policy.policy_id, "policy_version": scenario.policy.version,
        "user_id": scenario.user_id, "adapter": "scripted", "synthetic": True,
        "model": None, "package_version": __version__, "execution_status": status,
        "diagnostic": diagnostic, "started_utc": started,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        **evaluate(scenario, events, status),
    }
    (run_dir / "events.jsonl").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events), encoding="utf-8")
    (run_dir / "scenario.json").write_text(json.dumps(scenario.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary, run_dir

