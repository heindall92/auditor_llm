"""Bounded subprocess worker. stdout is exclusively the event protocol."""
import json
import sys

from .adapters.scripted import ActionLimitError, execute
from .models import Scenario


def main():
    try:
        payload = json.load(sys.stdin)
        scenario = Scenario.from_dict(payload["scenario"])
        execute(scenario, payload["run_id"],
                lambda event: print(json.dumps(event), flush=True))
        return 0
    except ActionLimitError:
        return 4
    except Exception:
        # Never emit arbitrary exception messages or secret-bearing input.
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

