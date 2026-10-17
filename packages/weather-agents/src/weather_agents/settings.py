"""Agent runtime settings: defaults, then the package `.env`, then the environment."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["PACKAGE_ROOT", "Effort", "LogLevel", "Settings"]

PACKAGE_ROOT = Path(__file__).resolve().parents[2]

# Literals, not Enums, so the values pass to the SDK's typed parameters unchanged.
Effort = Literal["low", "medium", "high", "xhigh", "max"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class Settings(BaseSettings):
    """Everything the API runtime reads.

    Each field is read from `WEATHER_AGENTS_<FIELD>` in the environment or in
    `packages/weather-agents/.env`, except the API key, which is plain `ANTHROPIC_API_KEY`.
    An invalid value fails when the object is built, and the error names the field.
    """

    model_config = SettingsConfigDict(
        env_prefix="WEATHER_AGENTS_",
        env_file=PACKAGE_ROOT / ".env",
        extra="ignore",
    )

    model: str = "claude-haiku-5-5"
    effort: Effort = "low"
    thinking: bool = True
    max_tokens: Annotated[int, Field(gt=0)] = 32_000
    fast_mode: bool = False
    mcp_config: Path = PACKAGE_ROOT / "mcp.stdio.json"
    log_level: LogLevel = "INFO"
    log_truncate: Annotated[int, Field(gt=0)] = 200
    anthropic_api_key: Annotated[
        SecretStr,
        Field(validation_alias=AliasChoices("ANTHROPIC_API_KEY", "anthropic_api_key")),
    ]

    @field_validator("mcp_config")
    @classmethod
    def _resolve_from_package_root(cls, value: Path) -> Path:
        return value if value.is_absolute() else PACKAGE_ROOT / value
