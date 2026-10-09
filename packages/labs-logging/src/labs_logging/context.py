"""Scoped context helpers, re-exported from structlog's contextvars."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import structlog

__all__ = ["bind_context", "bound_context", "unbind_context"]


def bind_context(**kwargs: object) -> None:
    """Bind key-value pairs to the current task's logging context."""
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """Remove keys from the current task's logging context."""
    structlog.contextvars.unbind_contextvars(*keys)


@contextmanager
def bound_context(**kwargs: object) -> Iterator[None]:
    """Temporarily bind context, restoring prior values on exit."""
    with structlog.contextvars.bound_contextvars(**kwargs):
        yield
