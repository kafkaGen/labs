"""Advisory cross-process lock released automatically on process exit."""

from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO

__all__ = ["FileLock"]


class FileLock:
    """Serialize access to a resource across processes via an OS-held lock."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._fh: BinaryIO | None = None
        self._locked = False

    def _open(self) -> None:
        if self._fh is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = self.path.open("a+b")

    def acquire(self) -> None:
        self._open()
        self._lock(blocking=True)
        self._locked = True

    def try_acquire(self) -> bool:
        self._open()
        try:
            self._lock(blocking=False)
        except OSError:
            # Close now so a lock that was never acquired holds no open file.
            if self._fh is not None:
                self._fh.close()
                self._fh = None
            return False
        self._locked = True
        return True

    def _lock(self, *, blocking: bool) -> None:
        if self._fh is None:
            raise RuntimeError("lock file is not open")
        if os.name == "nt":
            import msvcrt

            # msvcrt.locking blocks until the region is free regardless of a
            # nonblocking flag, so use LK_NBLCK semantics only via try/except.
            flag = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
            msvcrt.locking(self._fh.fileno(), flag, 1)
        else:
            import fcntl

            flags = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
            fcntl.flock(self._fh.fileno(), flags)

    def release(self) -> None:
        if not self._locked or self._fh is None:
            return
        if os.name == "nt":
            import msvcrt

            self._fh.seek(0)
            msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        self._fh.close()
        self._fh = None
        self._locked = False

    @property
    def locked(self) -> bool:
        return self._locked

    def __enter__(self) -> FileLock:
        self.acquire()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()
