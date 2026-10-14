from .models import Policy


def is_allowed(policy: Policy, tool: str, resource: str) -> bool:
    """Policy belongs to the scenario's single synthetic user. Default deny."""
    return resource in policy.allowed_resources.get(tool, ())

