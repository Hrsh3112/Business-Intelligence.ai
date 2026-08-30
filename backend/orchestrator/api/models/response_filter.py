"""Response redaction filter for server-side persona entitlements (Req 8)."""

from typing import Any, Dict, List, Union

EXEC_REDACTED_FIELDS = {
    "z_score",
    "noise_confidence",
    "slope",
    "acceleration",
    "driver_rank",
}


def redact_for_persona(data: Any, persona: str) -> Any:
    """Recursively redacts analyst-depth fields if persona is executive."""
    if persona != "executive":
        return data

    if isinstance(data, dict):
        cleaned: Dict[str, Any] = {}
        for k, v in data.items():
            if k not in EXEC_REDACTED_FIELDS:
                cleaned[k] = redact_for_persona(v, persona)
        return cleaned
    elif isinstance(data, list):
        return [redact_for_persona(item, persona) for item in data]
    else:
        return data
