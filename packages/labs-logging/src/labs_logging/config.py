"""Typed configuration for the logging package."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = ["LoggingConfig"]

_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


class LoggingConfig(BaseModel):
    """Where and how one application logs.

    Args:
        app: Application identity, a safe directory name.
        family: Logger-name prefix shared by the application's loggers.
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
    backups: int = Field(default=0, ge=0)
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
    def _override_shape(cls, value: Mapping[str, int]) -> Mapping[str, int]:
        for name, level in value.items():
            if not isinstance(name, str) or not name:
                raise ValueError("override keys must be non-empty logger names")
            if not isinstance(level, int):
                raise ValueError("override values must be int levels")
        return value
