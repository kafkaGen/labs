"""The one settings object every knob of the agent layer lives in."""

from pathlib import Path
from typing import Annotated

from pydantic import Field, FilePath, PositiveInt, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["DEFAULT_MCP_CONFIG", "Settings", "SettingsError", "load_settings"]

# The package root, three levels up from src/weather_agents/settings.py. The package is only
# ever installed editable in this workspace, so the file is always there.
DEFAULT_MCP_CONFIG = Path(__file__).resolve().parents[2] / "mcp.stdio.json"


class SettingsError(Exception):
    """A setting is missing or invalid. The message names each field and never its value."""


class Settings(BaseSettings):
    """Read with `load_settings`, which finds `.env` and turns failures into `SettingsError`.

    Priority, highest first: keyword overrides for one run, the environment, `.env`, defaults.
    Every field but the key reads `WEATHER_AGENTS_<FIELD>`. The key reads `ANTHROPIC_API_KEY`.
    """

    model_config = SettingsConfigDict(
        env_prefix="WEATHER_AGENTS_",
        extra="ignore",
        validate_by_name=True,
        validate_by_alias=True,
    )

    anthropic_api_key: Annotated[SecretStr, Field(validation_alias="ANTHROPIC_API_KEY")]
    model: str = "claude-haiku-5-5"
    max_tokens: PositiveInt = 16_000
    mcp_config: FilePath = DEFAULT_MCP_CONFIG


def load_settings(**overrides: object) -> Settings:
    """Load settings, with `overrides` taking priority for this run.

    Raises:
        SettingsError: A value is missing or does not fit its field.
    """
    try:
        # Overrides are untyped on purpose: pydantic validates each one and names the field.
        return Settings(_env_file=_nearest_dotenv(), **overrides)  # ty: ignore[invalid-argument-type]
    except ValidationError as error:
        # `input` is left out on purpose: it may be the API key.
        problems = "; ".join(
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in error.errors(include_input=False, include_url=False)
        )
        raise SettingsError(f"invalid settings: {problems}") from None


def _nearest_dotenv() -> Path | None:
    # Tests and Makefile targets run from the package directory, and the key lives in the
    # repo root's `.env`, so look up the tree rather than only in the current directory.
    for directory in (Path.cwd(), *Path.cwd().parents):
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None
