"""A JSON Lines file handler that rotates by size."""

from __future__ import annotations

import logging
from pathlib import Path

__all__ = ["JsonFileHandler", "rotate_files"]


def rotate_files(path: Path, backups: int) -> None:
    """Shift `path`, `path.1`, ... one slot right, dropping the oldest.

    Args:
        path: The active file.
        backups: Number of numbered backups to keep. 0 shifts nothing.

    Raises:
        OSError: A rename fails.
    """
    for i in range(backups - 1, 0, -1):
        src = path.with_name(f"{path.name}.{i}")
        dst = path.with_name(f"{path.name}.{i + 1}")
        if src.exists():
            src.replace(dst)
    if backups >= 1 and path.exists():
        path.replace(path.with_name(f"{path.name}.1"))


class JsonFileHandler(logging.Handler):
    """Append rendered records; rotate when the next write would exceed a size.

    With `backups == 0`, rollover unlinks the current file and starts again.
    With `backups > 0`, the active file shifts into numbered backups first.

    Args:
        path: The active file.
        max_bytes: Size at which the next write triggers rollover. One oversized
            record is still written whole.
        backups: Rotated backups to keep.
        encoding: File encoding.
    """

    def __init__(
        self, path: Path, *, max_bytes: int, backups: int, encoding: str = "utf-8"
    ) -> None:
        super().__init__()
        self.path = path
        self.max_bytes = max_bytes
        self.backups = backups
        self.encoding = encoding

    def emit(self, record: logging.LogRecord) -> None:
        """Append one rendered record.

        Args:
            record: The record to format and write.

        Raises:
            Exception: Any formatting or file error. It is not routed to
                `handleError`, so the runtime's fan-out can mark itself unhealthy.
        """
        message = self.format(record) + "\n"
        if (
            self.path.exists()
            and self.path.stat().st_size + len(message.encode(self.encoding)) > self.max_bytes
        ):
            self._rollover()
        with self.path.open("a", encoding=self.encoding) as stream:
            stream.write(message)

    def _rollover(self) -> None:
        if self.backups > 0:
            rotate_files(self.path, self.backups)
        else:
            self.path.unlink(missing_ok=True)
