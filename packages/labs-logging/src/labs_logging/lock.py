"""Advisory cross-process lock released automatically on process exit."""

from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO

__all__ = ["FileLock"]


class FileLock:
    """Serialize access to a resource across processes via an OS-held lock.

    The OS releases the lock when the holding process exits, even after a crash.
    Windows is untested.

    Args:
        path: Lock file. Its parent directory is created on first use.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._fh: BinaryIO | None = None
        self._locked = False

    def _open(self) -> None:
        if self._fh is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = self.path.open("a+b")

    def acquire(self) -> None:
        """Block until the lock is held.

        Raises:
            OSError: The lock file cannot be opened or locked. On Windows, also
                raised when the wait times out.
        """
        self._open()
        self._lock(blocking=True)
        self._locked = True

    def try_acquire(self) -> bool:
        """Take the lock without waiting.

        Returns:
            True if this object now holds the lock, False if another holder has it.

        Raises:
            OSError: The lock file cannot be opened.
        """
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

            # LK_NBLCK raises OSError at once when the byte is held. LK_LOCK retries
            # for about ten seconds, then raises OSError, so it is not unbounded.
            flag = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
            msvcrt.locking(self._fh.fileno(), flag, 1)
        else:
            import fcntl

            flags = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
            fcntl.flock(self._fh.fileno(), flags)

    def release(self) -> None:
        """Release the lock and close the file. Does nothing when not held."""
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
        """Whether this object holds the lock."""
        return self._locked

    def __enter__(self) -> FileLock:
        self.acquire()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()
