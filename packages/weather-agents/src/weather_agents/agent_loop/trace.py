"""Cuts values to a fixed length before they reach the log."""

import json

from pydantic import BaseModel

__all__ = ["truncate"]


def _to_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, BaseModel):
        return value.model_dump_json(exclude_none=True)
    return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))


def truncate(name: str, value: object, limit: int) -> dict[str, object]:
    """Return log fields for `value` under `name`, cut to `limit` characters.

    The result always has `name`. A cut value also gets `<name>_truncated=True` and
    `<name>_length`, its length before the cut. Non-string values are serialized to compact
    JSON first.

    Example:
        `log.debug("tool.result", **truncate("result", text, 200))`

    Args:
        name: The log field to fill.
        value: A string, a pydantic model, or anything JSON can serialize.
        limit: The longest text kept.
    """
    text = _to_text(value)
    if len(text) <= limit:
        return {name: text}
    return {name: text[:limit], f"{name}_truncated": True, f"{name}_length": len(text)}
