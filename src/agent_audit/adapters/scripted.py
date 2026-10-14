from datetime import datetime, timezone
import time

from ..models import Scenario


class ActionLimitError(RuntimeError):
    pass


def execute(scenario: Scenario, run_id: str, emit):
    """Emit fabricated lab telemetry, never real tool calls or model output."""
    action_count = 0
    sequence = 0
    for step in scenario.steps:
        if step["kind"] == "delay":
            time.sleep(step["seconds"])
            continue
        if step["kind"] == "error":
            raise RuntimeError("scripted failure")
        if step["kind"] == "attempted":
            action_count += 1
            if action_count > scenario.max_actions:
                raise ActionLimitError("action limit")
        sequence += 1
        emit({"schema_version": "1.0", "run_id": run_id,
              "scenario_id": scenario.scenario_id, "sequence": sequence,
              "timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "user_id": scenario.user_id, "synthetic": True, **step})

