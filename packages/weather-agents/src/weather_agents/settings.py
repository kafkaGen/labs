"""Every knob the agent reads, in one settings object.

Values come from defaults in code, then `.env` in the working directory, then the environment,
then overrides passed for one run. A later source wins, field by field. Environment variables
carry the `WEATHER_AGENTS_` prefix, for example `WEATHER_AGENTS_USD_CAP=0.05`. The API key is the
exception: it is read from `ANTHROPIC_API_KEY`, and only from `.env` or the environment.
"""

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Self

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["ForbiddenOverrideError", "LogLevel", "Settings", "UnknownSettingError"]


class LogLevel(StrEnum):
    """Log levels a run can use."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ForbiddenOverrideError(ValueError):
    """A per-run override named a field that may only come from `.env` or the environment."""


class UnknownSettingError(ValueError):
    """A per-run override named a field that does not exist."""


class Settings(BaseSettings):
    """The agent's settings.

    Loading fails with a `pydantic.ValidationError` naming the field when a value is invalid,
    such as a negative USD cap or a zero deadline.
    """

    model_config = SettingsConfigDict(
        env_prefix="WEATHER_AGENTS_",
        env_file=".env",
        env_file_encoding="utf-8",
        # A shared .env holds other tools' keys. Ignore them, and never echo any input in an
        # error, because a bad value may be a secret.
        extra="ignore",
        hide_input_in_errors=True,
    )

    model: str = "claude-haiku-5-5"
    deadline_seconds: Annotated[float, Field(gt=0)] = 120.0
    usd_cap: Annotated[float, Field(gt=0)] = 0.10
    max_tokens: Annotated[int, Field(gt=0)] = 16_000
    mcp_config: Path = Path("mcp.stdio.json")
    log_level: LogLevel = LogLevel.INFO
    log_truncate_chars: Annotated[int, Field(gt=0)] = 200
    # Read without the prefix, so the SDK's usual variable name works.
    anthropic_api_key: Annotated[SecretStr | None, Field(validation_alias="ANTHROPIC_API_KEY")] = (
        None
    )

    def with_overrides(self, **changes: object) -> Self:
        """Return a copy with `changes` applied for one run, validated like any other source.

        Raises:
            ForbiddenOverrideError: `changes` names the API key.
            UnknownSettingError: `changes` names no setting.
            pydantic.ValidationError: A changed value is invalid.
        """
        if {"anthropic_api_key", "ANTHROPIC_API_KEY"} & changes.keys():
            raise ForbiddenOverrideError(
                "anthropic_api_key: the API key comes only from .env or the environment"
            )
        unknown = sorted(changes.keys() - type(self).model_fields.keys())
        if unknown:
            raise UnknownSettingError(f"no such setting: {', '.join(unknown)}")
        values = self.model_dump(by_alias=True) | changes
        return self.model_validate(values)
