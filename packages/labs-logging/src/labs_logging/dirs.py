"""Log directory resolution and per-run directory naming."""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime
from pathlib import Path

from platformdirs import user_log_dir

from labs_logging.config import LoggingConfig

__all__ = ["RUN_NAME_PATTERN", "RunDir", "new_run_name", "resolve_log_dir"]

# Matches the names `new_run_name` produces, so cleanup never touches other directories.
RUN_NAME_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\.\d{6}Z-[0-9a-f]{6}")


def resolve_log_dir(config: LoggingConfig) -> Path:
    """Return the application log root, per config or the platform log dir."""
    return config.log_dir if config.log_dir is not None else Path(user_log_dir(config.app))


def new_run_name(now: datetime) -> str:
    """A sortable, filesystem-safe run name with a collision-resistant suffix."""
    stamp = now.astimezone(UTC).strftime("%Y-%m-%dT%H-%M-%S.%fZ")
    return f"{stamp}-{secrets.token_hex(3)}"


class RunDir:
    """One launch's isolated directory, holding its file, backups, and lock."""

    def __init__(self, path: Path, name: str) -> None:
        self.path = path
        self.name = name

    @property
    def main_path(self) -> Path:
        return self.path / "main.jsonl"

    @property
    def lock_path(self) -> Path:
        return self.path / "lock"

    @classmethod
    def create(cls, root: Path, now: datetime) -> RunDir:
        """Create a fresh run directory, retrying a rare name collision."""
        for _ in range(5):
            path = root / new_run_name(now)
            try:
                path.mkdir(parents=True, exist_ok=False)
                return cls(path, path.name)
            except FileExistsError:
                continue
        raise FileExistsError(f"could not create a unique run directory under {root}")
