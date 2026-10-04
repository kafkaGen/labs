"""Errors the logging package raises."""

__all__ = ["AlreadyConfiguredError", "LoggingError", "SetupError"]


class LoggingError(Exception):
    """Base class for errors raised by the logging package."""


class SetupError(LoggingError):
    """Logging could not be configured. Nothing was left partially installed."""


class AlreadyConfiguredError(SetupError):
    """A runtime is already active in this process."""
