"""Reads a Claude Code `mcpServers` file into stdio server settings."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from weather_agents.mcp_client.errors import ConfigError

__all__ = ["SUPPORTED_TYPES", "StdioServerConfig", "load_config"]

# Level 2 adds "http". Anything outside this set fails loudly instead of being skipped.
SUPPORTED_TYPES = frozenset({"stdio"})


class StdioServerConfig(BaseModel):
    """One `mcpServers` entry that starts a server as a child process."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["stdio"] = "stdio"
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] | None = None


def load_config(path: Path) -> dict[str, StdioServerConfig]:
    """Read the `mcpServers` object of a config file.

    Args:
        path: A JSON file in Claude Code's `mcpServers` format.

    Returns:
        The servers by name, in the file's order.

    Raises:
        ConfigError: The file cannot be read or parsed, has no `mcpServers` object, or has an
            entry with an unsupported type, an unknown key, or a missing field. The whole load
            fails, because this is a mistake in the file and not a server that is down.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigError(f"cannot read {path}: {error.strerror or error}") from error
    except UnicodeDecodeError as error:
        raise ConfigError(f"{path} is not valid UTF-8: {error}") from error
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as error:
        raise ConfigError(f"{path} is not valid JSON: {error}") from error
    entries = raw.get("mcpServers") if isinstance(raw, dict) else None
    if not isinstance(entries, dict):
        raise ConfigError(f"{path} has no 'mcpServers' object")
    return {name: _parse_entry(name, entry) for name, entry in entries.items()}


def _parse_entry(name: str, entry: object) -> StdioServerConfig:
    if not isinstance(entry, dict):
        raise ConfigError(f"server '{name}': entry must be an object")
    kind = entry.get("type", "stdio")
    # The isinstance check also keeps an unhashable JSON value from raising TypeError below.
    if not isinstance(kind, str) or kind not in SUPPORTED_TYPES:
        supported = ", ".join(sorted(SUPPORTED_TYPES))
        message = f"server '{name}': type {kind!r} is not supported, supported: {supported}"
        raise ConfigError(message)
    try:
        return StdioServerConfig.model_validate(entry)
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        raise ConfigError(f"server '{name}': {where}: {first['msg']}") from error
