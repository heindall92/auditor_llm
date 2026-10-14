import argparse
import json
from pathlib import Path
import sys

from .models import ValidationError, load_scenario
from .runner import run_scenario


def main(argv=None):
    parser = argparse.ArgumentParser(description="auditor_llm: local scripted evaluation and output-only LLM probes")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="Validate a JSON scenario")
    validate.add_argument("scenario", type=Path)
    run = sub.add_parser("run", help="Execute a scripted synthetic fixture")
    run.add_argument("scenario", type=Path)
    run.add_argument("--output", type=Path, default=Path("output"))
    serve = sub.add_parser("serve", help="Start the local audit web app on loopback only")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--output", type=Path, default=Path("output/web"))
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            from .web import serve as start_server
            return start_server(args.port, args.output)
        scenario = load_scenario(args.scenario)
        if args.command == "validate":
            print(json.dumps({"scenario_id": scenario.scenario_id, "valid": True}))
            return 0
        summary, run_dir = run_scenario(scenario, args.output)
        print(json.dumps({**summary, "output_directory": str(run_dir)}, ensure_ascii=False))
        if summary["execution_status"] != "completed" or summary["security_verdict"] == "inconclusive":
            return 2
        return 1 if summary["security_verdict"] == "fail" else 0
    except (ValidationError, OSError) as exc:
        # File contents and arbitrary exception text are not printed.
        error = str(exc) if isinstance(exc, ValidationError) else "Unable to read or write local files"
        print(json.dumps({"error": error, "security_verdict": "inconclusive"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
