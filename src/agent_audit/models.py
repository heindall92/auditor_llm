"""Strict, dependency-free scenario validation. No executable fixture code."""
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import re

MAX_BYTES = 1024 * 1024
TOOLS = {"search_documents", "create_ticket"}


class ValidationError(ValueError):
    pass


def obj(value, required, optional=()):
    if not isinstance(value, dict):
        raise ValidationError("Expected an object")
    if set(value) - set(required) - set(optional) or set(required) - set(value):
        raise ValidationError("Object has missing or unknown fields")
    return value


def string(value, label, limit=120):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValidationError(f"Invalid {label}")
    if any(ord(c) < 32 for c in value):
        raise ValidationError(f"Control characters in {label}")
    return value


def tool(value):
    if not isinstance(value, str) or value not in TOOLS:
        raise ValidationError("Unsupported tool")
    return value


def number(value, label, minimum, maximum):
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValidationError(f"Invalid {label}")
    return value


@dataclass(frozen=True)
class Policy:
    policy_id: str
    version: str
    allowed_resources: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class Expectation:
    tool: str
    resource: str
    count: int


@dataclass(frozen=True)
class Scenario:
    schema_version: str
    scenario_id: str
    version: str
    description: str
    user_id: str
    policy: Policy
    required_effects: tuple[Expectation, ...]
    steps: tuple[dict, ...]
    timeout_seconds: float
    max_actions: int

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        v = obj(value, {"schema_version", "scenario_id", "version", "description", "user_id", "policy", "required_effects", "steps"}, {"timeout_seconds", "max_actions"})
        if v["schema_version"] != "1.0":
            raise ValidationError("Unsupported schema_version")
        sid = string(v["scenario_id"], "scenario_id", 64)
        if not re.fullmatch(r"[A-Za-z0-9_-]+", sid):
            raise ValidationError("scenario_id must be a safe identifier")
        p = obj(v["policy"], {"policy_id", "version", "allowed_resources"})
        allowed = p["allowed_resources"]
        if not isinstance(allowed, dict) or len(allowed) > len(TOOLS):
            raise ValidationError("Invalid allowed_resources")
        grants = {}
        for name, resources in allowed.items():
            tool(name)
            if not isinstance(resources, list) or len(resources) > 50:
                raise ValidationError("Invalid resource list")
            grants[name] = tuple(string(r, "resource") for r in resources)
        policy = Policy(string(p["policy_id"], "policy_id"), string(p["version"], "policy version"), grants)
        raw_expectations = v["required_effects"]
        if not isinstance(raw_expectations, list) or len(raw_expectations) > 50:
            raise ValidationError("Invalid required_effects")
        expectations = []
        seen = set()
        for raw in raw_expectations:
            e = obj(raw, {"tool", "resource", "count"})
            name, resource = tool(e["tool"]), string(e["resource"], "resource")
            if type(e["count"]) is not int or not 1 <= e["count"] <= 100:
                raise ValidationError("Invalid expected count")
            if (name, resource) in seen or resource not in grants.get(name, ()):
                raise ValidationError("Duplicate or unauthorized required effect")
            seen.add((name, resource))
            expectations.append(Expectation(name, resource, e["count"]))
        raw_steps = v["steps"]
        if not isinstance(raw_steps, list) or len(raw_steps) > 200:
            raise ValidationError("steps must be a list of at most 200 entries")
        steps, calls, terminals = [], {}, set()
        for index, raw in enumerate(raw_steps):
            if not isinstance(raw, dict):
                raise ValidationError("Invalid step")
            kind = raw.get("kind")
            if kind in ("attempted", "blocked", "completed"):
                step = obj(raw, {"kind", "call_id", "tool", "resource"})
                cid = string(step["call_id"], "call_id")
                action = (tool(step["tool"]), string(step["resource"], "resource"))
                if kind == "attempted":
                    if cid in calls:
                        raise ValidationError("Duplicate call_id")
                    calls[cid] = action
                elif cid not in calls or calls[cid] != action or cid in terminals:
                    raise ValidationError("Invalid action lifecycle")
                else:
                    terminals.add(cid)
            elif kind == "coverage":
                step = obj(raw, {"kind", "complete"})
                if type(step["complete"]) is not bool or index != len(raw_steps) - 1:
                    raise ValidationError("coverage must be a final boolean marker")
            elif kind == "delay":
                step = obj(raw, {"kind", "seconds"})
                number(step["seconds"], "delay", 0, 10)
            elif kind == "error":
                step = obj(raw, {"kind"})
            else:
                raise ValidationError("Unknown step kind")
            steps.append(dict(step))
        actions = v.get("max_actions", 20)
        if type(actions) is not int or not 1 <= actions <= 100:
            raise ValidationError("Invalid max_actions")
        timeout = number(v.get("timeout_seconds", 5.0), "timeout_seconds", 0.05, 30)
        return cls("1.0", sid, string(v["version"], "version"),
                   string(v["description"], "description", 1000), string(v["user_id"], "user_id"),
                   policy, tuple(expectations), tuple(steps), float(timeout), actions)


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("Duplicate JSON key")
        result[key] = value
    return result


def load_scenario(path: Path):
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValidationError("Scenario exceeds 1 MiB")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValidationError("Invalid UTF-8 JSON scenario") from exc
    return Scenario.from_dict(value)

