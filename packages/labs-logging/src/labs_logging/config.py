"""Typed configuration for the logging package."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = ["LoggingConfig"]

_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


class LoggingConfig(BaseModel):
    """Where and how one application logs.

    Args:
        app: Application identity. It names the log directory, so it must be one
            path-safe component: letters, digits, `.`, `_`, `-`, and not `.` or `..`.
        family: Logger-name prefix shared by the application's loggers. It follows
            the same character rule as `app`.
        level: Level for the family logger and the root logger.
        level_overrides: Per-logger levels. Names must be non-empty.
        log_dir: Where run directories go. Defaults to the platform log directory
            for `app`.
        console: Write to the console destination.
        console_colors: Force colors on or off. `None` colors only a terminal.
        console_json: Render console lines as JSON.
        console_stream: Text stream for the console. Defaults to stderr.
        file: Write rotating JSON Lines files.
        synchronous: Write in the calling thread instead of a listener thread.
        queue_size: Background queue capacity. At least 1.
        max_bytes: Approximate size of one log file. At least 1.
        backups: Rotated backups kept per run. 0 discards old contents.
        retain_runs: Newest runs kept per application. 0 or more.
        extra_handlers: Your own `logging.Handler` instances.

    Raises:
        pydantic.ValidationError: A field fails validation, for example an unsafe
            `app`, an empty override name, or a non-positive `queue_size`.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    app: str
    family: str
    level: int = logging.INFO
    level_overrides: dict[str, int] = Field(default_factory=dict)
    log_dir: Path | None = None
    console: bool = True
    console_colors: bool | None = None
    console_json: bool = False
    console_stream: object = Field(default=None, repr=False)
    file: bool = True
    synchronous: bool = False
    queue_size: int = Field(default=10_000, ge=1)
    max_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    backups: int = Field(default=3, ge=0)
    retain_runs: int = Field(default=5, ge=0)
    extra_handlers: list[object] = Field(default_factory=list)

    @field_validator("app", "family")
    @classmethod
    def _single_component(cls, value: str) -> str:
        # "." and ".." name the directory or its parent, so they are not safe
        # single components even though the charset would admit them.
        if value in {".", ".."}:
            raise ValueError("must be a single path-safe component")
        if not _NAME.fullmatch(value):
            raise ValueError("must be a single path-safe component")
        return value

    @field_validator("level_overrides")
    @classmethod
    def _override_shape(cls, value: dict[str, int]) -> dict[str, int]:
        # Pydantic has already checked the key and value types; only emptiness is left.
        if any(not name for name in value):
            raise ValueError("override keys must be non-empty logger names")
        return value
