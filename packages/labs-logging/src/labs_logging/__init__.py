"""Structured logging shared across Python applications."""

from labs_logging.errors import AlreadyConfiguredError, LoggingError, SetupError

__all__ = ["AlreadyConfiguredError", "LoggingError", "SetupError", "__version__"]

__version__ = "0.1.0"
