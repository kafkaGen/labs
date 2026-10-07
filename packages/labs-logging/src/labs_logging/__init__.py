"""Structured logging shared across Python applications."""

import structlog

from labs_logging.config import LoggingConfig
from labs_logging.context import bind_context, bound_context, unbind_context
from labs_logging.errors import AlreadyConfiguredError, LoggingError, SetupError
from labs_logging.runtime import Runtime, configure

__all__ = [
    "AlreadyConfiguredError",
    "LoggingConfig",
    "LoggingError",
    "Runtime",
    "SetupError",
    "bind_context",
    "bound_context",
    "configure",
    "get_logger",
    "unbind_context",
]


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structured logger for `name`, e.g. `mcp_server.tools`."""
    return structlog.stdlib.get_logger(name)
