"""Snapshot event values into JSON-safe data in the producing thread."""

from __future__ import annotations

import math
from typing import Any

__all__ = ["normalize"]

_CYCLE = "<cycle>"


def normalize(value: object) -> Any:
    """Return a JSON-safe copy of `value`.

    JSON-native values pass through. Containers are copied recursively, so later
    mutation by the caller cannot change the result. A container that contains
    itself becomes `"<cycle>"` at the repeat. Other values become a string labelled
    with their type, or just the type name when conversion fails.
    """
    try:
        return _walk(value, set())
    except RecursionError:
        return type(value).__name__


def _walk(value: object, path: set[int]) -> Any:
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, dict | list | tuple | set | frozenset):
        if id(value) in path:
            return _CYCLE
        path.add(id(value))
        try:
            if isinstance(value, dict):
                return {_key(k): _walk(v, path) for k, v in list(value.items())}
            return [_walk(item, path) for item in list(value)]
        finally:
            path.discard(id(value))
    return _labelled(value)


def _key(key: object) -> str:
    return key if isinstance(key, str) else str(_walk(key, set()))


def _labelled(value: object) -> str:
    name = type(value).__name__
    try:
        return f"{name}: {value!r}"
    except Exception:
        return name
