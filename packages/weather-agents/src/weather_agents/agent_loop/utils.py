"""Small helpers the agent loop shares."""

import json

__all__ = ["truncate"]


def truncate(value: object, limit: int) -> str:
    """Render `value` as text and cut it to `limit` characters, saying how much was cut.

    Dicts and lists render as JSON. Everything else uses `str`.
    """
    if isinstance(value, str):
        text = value
    elif isinstance(value, dict | list):
        text = json.dumps(value, ensure_ascii=False, default=str)
    else:
        text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}… [cut {len(text) - limit} chars]"
