# Shared logging package: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `labs-logging`, a reusable logging package with structured, colorful console output, rotating JSON Lines files isolated per run, named logger families, scoped context, and standard `logging.Handler` extension points.

**Architecture:** Standard `logging` owns the logger hierarchy, handler routing, and third-party record flow; `structlog` adds structured events, context, and rendering. One dispatch path (`QueueHandler` to a listener thread, or direct handlers in synchronous mode) feeds a colored console handler and a custom discard-and-restart JSON file handler. A per-run directory and OS-level lock isolate concurrent processes, and the application level keeps the newest N runs plus any older active ones.

**Tech stack:** Python 3.12, `structlog` 24.x, `platformdirs`, `pydantic` v2, `pytest`, `uv`, `ruff`, `ty`.

**Spec:** [`../specs/2026-10-04-shared-logging-design.md`](../specs/2026-10-04-shared-logging-design.md). **ADR:** [`../../adr/0001-isolate-log-files-by-run.md`](../../adr/0001-isolate-log-files-by-run.md).

## Global constraints

- Work in the worktree `.worktrees/feature/labs-logging`, on branch `feature/labs-logging`. Commit only files under `packages/labs-logging/`, plus the root `uv.lock` when Task 1 adds dependencies.
- Python `>=3.12`. Dependencies: `structlog>=24,<25`, `platformdirs>=4`, `pydantic>=2`. Dev: `pytest>=9`.
- Repo conventions: Pydantic models for structured data, `pathlib.Path`, modern generics (`list[str]`, `X | None`), `-> None` on void functions, `__all__` on public modules, Google-style docstrings, lazy `%`-args for stdlib logs, structured keyword fields for structlog events, no bare `except`.
- Run `pytest` from `packages/labs-logging/`. Run `ruff`/`ty` with `uv run pre-commit run --files <paths>` from the repo root. A pre-commit hook failure means fix and re-commit, never `--no-verify`.
- Console writes to `stderr`, never `stdout`. No application logs write to stdout in this package.
- Console colors default to on only when the destination stream `isatty()`. Interactive output is colorful; file output is JSON Lines without color escapes.
- Default application and destination level is `INFO`, enforced through logger levels (handlers are set to `NOTSET` so per-family/child overrides actually work).
- One owner per file. The five-run limit includes active runs and their backups. No secrets, no exception-frame locals, no MCP-specific logic, no cloud transport, no shared multiprocess file writer.
- The `LogRecord` has no static fields for our captured state; attach them with `setattr` so `ty` passes.
- Prose in docs: sentence-case headings, plain words, no em dashes. Do not edit the spec or the ADR after this plan is committed.

## File structure

Everything lives under `packages/labs-logging/`.

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, dependencies, build backend, pytest config |
| `README.md` | Install and quick-start |
| `src/labs_logging/__init__.py` | Public exports: `configure`, `Runtime`, `LoggingConfig`, `get_logger`, context helpers, errors |
| `src/labs_logging/errors.py` | `LoggingError`, `SetupError`, `AlreadyConfiguredError` |
| `src/labs_logging/config.py` | `LoggingConfig` Pydantic model and validation |
| `src/labs_logging/dirs.py` | Log dir resolution, `RunDir` naming/creation |
| `src/labs_logging/lock.py` | `FileLock` advisory cross-process lock |
| `src/labs_logging/rotation.py` | `JsonFileHandler` discard-and-restart rollover |
| `src/labs_logging/envelope.py` | `EnvelopeBuilder`, producer processors, foreign pre-chain, renderer factory |
| `src/labs_logging/context.py` | `bind_context`, `unbind_context`, `bound_context` |
| `src/labs_logging/runtime.py` | `configure`, `Runtime`, dispatch, queue, listener, retention, shutdown |
| `tests/` | One test module per source module, plus retention, async, and multiprocess tests |
| `examples/dummy.py` | Runnable dummy application exercising both dispatch modes |

## Docs check

Docs this plan could make wrong:

- `packages/labs-logging/README.md`: created in Task 1 with a quick-start that must match the shipped API. Task 12 verifies it.
- No `docs/architecture.md` exists in this package, and the spec already records the system shape, so none is created here. No ADR is edited. Root `uv.lock` changes only when dependencies change.

---

### Task 1: Scaffold the package

**Files:**
- Modify: `packages/labs-logging/pyproject.toml` (replace the design placeholder)
- Create: `packages/labs-logging/README.md`
- Create: `packages/labs-logging/src/labs_logging/__init__.py`
- Create: `packages/labs-logging/src/labs_logging/errors.py`
- Create: `packages/labs-logging/tests/__init__.py`
- Create: `packages/labs-logging/tests/test_errors.py`

**Interfaces:**
- Produces: a uv workspace member `labs-logging` importing as `labs_logging`, with `LoggingError`, `SetupError`, `AlreadyConfiguredError` importable.

- [ ] **Step 1: Commit the plan**

```bash
cd /Users/oboryse/Projects/labs/.worktrees/feature/labs-logging && git add packages/labs-logging/docs/superpowers/plans
git commit -m "docs(labs-logging): add shared logging implementation plan"
```

- [ ] **Step 2: Replace `pyproject.toml`**

```toml
[project]
name = "labs-logging"
version = "0.1.0"
description = "Shared structured logging for Python applications."
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "platformdirs>=4",
    "pydantic>=2",
    "structlog>=24,<25",
]

[dependency-groups]
dev = [
    "pytest>=9",
]

[build-system]
requires = ["uv_build>=0.9,<0.12"]
build-backend = "uv_build"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Create `errors.py`**

```python
"""Errors the logging package raises."""

__all__ = ["AlreadyConfiguredError", "LoggingError", "SetupError"]


class LoggingError(Exception):
    """Base class for errors raised by the logging package."""


class SetupError(LoggingError):
    """Logging could not be configured. Nothing was left partially installed."""


class AlreadyConfiguredError(SetupError):
    """A runtime is already active in this process."""
```

- [ ] **Step 4: Create `__init__.py`**

```python
"""Structured logging shared across Python applications."""

from labs_logging.errors import AlreadyConfiguredError, LoggingError, SetupError

__all__ = ["AlreadyConfiguredError", "LoggingError", "SetupError", "__version__"]

__version__ = "0.1.0"
```

- [ ] **Step 5: Create `README.md`**

```markdown
# labs-logging

Structured logging for Python applications in the labs monorepo. Colorful console
output on stderr and rotating JSON Lines files, one isolated file per run.

## Configure

```python
from labs_logging import LoggingConfig, configure, get_logger

runtime = configure(LoggingConfig(app="my-app", family="my_app"))
log = get_logger("my_app.worker")
with runtime:
    log.info("started")
```
```

- [ ] **Step 6: Write the failing test**

```python
from labs_logging import AlreadyConfiguredError, LoggingError, SetupError


def test_error_hierarchy():
    assert issubclass(SetupError, LoggingError)
    assert issubclass(AlreadyConfiguredError, SetupError)


def test_errors_are_raisable():
    err = SetupError("boom")
    assert str(err) == "boom"
    assert isinstance(err, LoggingError)
```

- [ ] **Step 7: Install and run the test**

Run: `cd packages/labs-logging && uv run pytest tests/test_errors.py -q`
Expected: 2 passed.

- [ ] **Step 8: Commit**

```bash
git add packages/labs-logging uv.lock
git commit -m "chore(labs-logging): scaffold package with errors and metadata"
```

---

### Task 2: Configuration model

**Files:**
- Create: `packages/labs-logging/src/labs_logging/config.py`
- Create: `packages/labs-logging/tests/test_config.py`
- Modify: `packages/labs-logging/src/labs_logging/__init__.py` (export `LoggingConfig`)

**Interfaces:**
- Produces: `LoggingConfig(BaseModel)` with fields `app: str`, `family: str`, `level: int = logging.INFO`, `level_overrides: dict[str, int]`, `log_dir: pathlib.Path | None = None`, `console: bool = True`, `console_colors: bool | None = None`, `console_json: bool = False`, `console_stream: object = None`, `file: bool = True`, `synchronous: bool = False`, `queue_size: int = 10_000`, `max_bytes: int = 10 * 1024 * 1024`, `backups: int = 0`, `retain_runs: int = 5`, `extra_handlers: list[object] = []`.

- [ ] **Step 1: Write the failing test**

```python
import logging

import pytest
from pydantic import ValidationError

from labs_logging.config import LoggingConfig


def test_defaults():
    cfg = LoggingConfig(app="my-app", family="my_app")
    assert cfg.level == logging.INFO
    assert cfg.level_overrides == {}
    assert cfg.log_dir is None
    assert cfg.console is True
    assert cfg.console_json is False
    assert cfg.file is True
    assert cfg.synchronous is False
    assert cfg.queue_size == 10_000
    assert cfg.max_bytes == 10 * 1024 * 1024
    assert cfg.backups == 0
    assert cfg.retain_runs == 5
    assert cfg.extra_handlers == []


def test_app_name_rejects_paths():
    with pytest.raises(ValidationError):
        LoggingConfig(app="a/b", family="x")
    with pytest.raises(ValidationError):
        LoggingConfig(app="..", family="x")


def test_nonnegative_limits():
    with pytest.raises(ValidationError):
        LoggingConfig(app="a", family="x", queue_size=0)
    with pytest.raises(ValidationError):
        LoggingConfig(app="a", family="x", backups=-1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/labs-logging && uv run pytest tests/test_config.py -q`
Expected: FAIL (`ModuleNotFoundError: labs_logging.config`).

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/labs-logging && uv run pytest tests/test_config.py -q`
Expected: 3 passed.

- [ ] **Step 5: Export `LoggingConfig`**

Update `__init__.py`:

```python
from labs_logging.config import LoggingConfig
from labs_logging.errors import AlreadyConfiguredError, LoggingError, SetupError

__all__ = ["AlreadyConfiguredError", "LoggingConfig", "LoggingError", "SetupError", "__version__"]

__version__ = "0.1.0"
```

- [ ] **Step 6: Commit**

```bash
git add packages/labs-logging/src packages/labs-logging/tests/test_config.py
git commit -m "feat(labs-logging): add typed logging configuration"
```

---

### Task 3: Directory resolution and run naming

**Files:**
- Create: `packages/labs-logging/src/labs_logging/dirs.py`
- Create: `packages/labs-logging/tests/test_dirs.py`

**Interfaces:**
- Consumes: `LoggingConfig` (Task 2).
- Produces: `resolve_log_dir(config: LoggingConfig) -> pathlib.Path`; `new_run_name(now: datetime.datetime) -> str`; `class RunDir` with `.name`, `.path`, `.main_path`, `.lock_path`, and classmethod `create(root: pathlib.Path, now: datetime.datetime) -> RunDir`.

- [ ] **Step 1: Write the failing test**

```python
import datetime

import pytest

from labs_logging.config import LoggingConfig
from labs_logging.dirs import RunDir, new_run_name, resolve_log_dir


def test_explicit_log_dir_wins(tmp_path):
    assert resolve_log_dir(LoggingConfig(app="a", family="a", log_dir=tmp_path)) == tmp_path


def test_new_run_name_is_fs_safe_and_sortable():
    now = datetime.datetime(2026, 10, 4, 21, 0, 0, 123456, tzinfo=datetime.timezone.utc)
    name = new_run_name(now)
    assert " " not in name and ":" not in name
    assert name.startswith("2026-10-04T21-00-00.123456Z-")
    assert len(name.rsplit("-", 1)[1]) == 6


def test_run_dir_create_creates_once(tmp_path):
    now = datetime.datetime.now(datetime.timezone.utc)
    run = RunDir.create(tmp_path, now)
    assert run.path.is_dir()
    assert run.main_path.parent == run.path
    assert run.lock_path.name == "lock"
    with pytest.raises(FileExistsError):
        run.path.mkdir()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/labs-logging && uv run pytest tests/test_dirs.py -q`
Expected: FAIL (`ModuleNotFoundError: labs_logging.dirs`).

- [ ] **Step 3: Write minimal implementation**

```python
"""Log directory resolution and per-run directory naming."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from pathlib import Path

from platformdirs import user_log_dir

from labs_logging.config import LoggingConfig

__all__ = ["RunDir", "new_run_name", "resolve_log_dir"]


def resolve_log_dir(config: LoggingConfig) -> Path:
    """Return the application log root, per config or the platform log dir."""
    return config.log_dir if config.log_dir is not None else Path(user_log_dir(config.app))


def new_run_name(now: datetime) -> str:
    """A sortable, filesystem-safe run name with a collision-resistant suffix."""
    stamp = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S.%fZ")
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
    def create(cls, root: Path, now: datetime) -> "RunDir":
        """Create a fresh run directory, retrying a rare name collision."""
        for _ in range(5):
            path = root / new_run_name(now)
            try:
                path.mkdir(parents=True, exist_ok=False)
                return cls(path, path.name)
            except FileExistsError:
                continue
        raise FileExistsError(f"could not create a unique run directory under {root}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/labs-logging && uv run pytest tests/test_dirs.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/labs-logging/src/labs_logging/dirs.py packages/labs-logging/tests/test_dirs.py
git commit -m "feat(labs-logging): resolve log dir and create run directories"
```

---

### Task 4: Cross-process file lock

**Files:**
- Create: `packages/labs-logging/src/labs_logging/lock.py`
- Create: `packages/labs-logging/tests/test_lock.py`

**Interfaces:**
- Produces: `class FileLock(path: pathlib.Path)` with `acquire() -> None`, `try_acquire() -> bool`, `release() -> None`, `locked: bool` property, and context-manager support.

- [ ] **Step 1: Write the failing test**

```python
import subprocess
import sys
import textwrap

from labs_logging.lock import FileLock


def test_acquire_and_release(tmp_path):
    first = FileLock(tmp_path / "lock")
    assert not first.locked
    assert first.try_acquire() is True
    assert first.locked
    other = FileLock(tmp_path / "lock")
    assert other.try_acquire() is False
    first.release()
    assert other.try_acquire() is True
    other.release()


def test_context_manager(tmp_path):
    with FileLock(tmp_path / "lock") as lock:
        assert lock.locked
    assert FileLock(tmp_path / "lock").try_acquire() is True


def test_lock_releases_on_process_exit(tmp_path):
    code = textwrap.dedent(
        f"""
        from labs_logging.lock import FileLock
        lock = FileLock({str(tmp_path / "lock")!r})
        lock.acquire()
        # exit without releasing: the OS must drop the lock
        """
    )
    subprocess.run([sys.executable, "-c", code], check=True, cwd=tmp_path)
    assert FileLock(tmp_path / "lock").try_acquire() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/labs-logging && uv run pytest tests/test_lock.py -q`
Expected: FAIL (`ModuleNotFoundError: labs_logging.lock`). The subprocess test relies on `labs_logging` being importable, which it is via the installed workspace member.

- [ ] **Step 3: Write minimal implementation**

```python
"""Advisory cross-process lock released automatically on process exit."""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["FileLock"]


class FileLock:
    """Serialize access to a resource across processes via an OS-held lock."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh: object | None = None
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
            return False
        self._locked = True
        return True

    def _lock(self, *, blocking: bool) -> None:
        assert self._fh is not None
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

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/labs-logging && uv run pytest tests/test_lock.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/labs-logging/src/labs_logging/lock.py packages/labs-logging/tests/test_lock.py
git commit -m "feat(labs-logging): add cross-process file lock"
```

---

### Task 5: Discard-and-restart JSON file handler

**Files:**
- Create: `packages/labs-logging/src/labs_logging/rotation.py`
- Create: `packages/labs-logging/tests/test_rotation.py`

**Interfaces:**
- Produces: `rotate_files(path: Path, backups: int) -> None`; `class JsonFileHandler(logging.Handler)` constructed as `JsonFileHandler(path, max_bytes, backups)` with `emit(record) -> None` and `close() -> None`.

- [ ] **Step 1: Write the failing test**

```python
import logging

from labs_logging.rotation import JsonFileHandler


def _handler(tmp_path, max_bytes, backups):
    handler = JsonFileHandler(tmp_path / "main.jsonl", max_bytes=max_bytes, backups=backups)
    handler.setFormatter(logging.Formatter("%(message)s"))
    return handler


def _emit(handler, payload):
    handler.emit(logging.LogRecord("x", logging.INFO, "", 0, payload, (), None))


def test_writes_json_lines(tmp_path):
    handler = _handler(tmp_path, 100, 0)
    _emit(handler, "one")
    _emit(handler, "two")
    handler.close()
    assert (tmp_path / "main.jsonl").read_text() == "one\ntwo\n"


def test_discard_and_restart_at_size(tmp_path):
    handler = _handler(tmp_path, 10, 0)
    _emit(handler, "first")  # 6 bytes with newline
    _emit(handler, "second")  # 6 + 7 > 10, rollover discards "first"
    handler.close()
    assert (tmp_path / "main.jsonl").read_text() == "second\n"


def test_oversized_record_kept_intact(tmp_path):
    handler = _handler(tmp_path, 5, 0)
    _emit(handler, "way-too-long")
    handler.close()
    assert (tmp_path / "main.jsonl").read_text() == "way-too-long\n"


def test_backups_rotate(tmp_path):
    handler = _handler(tmp_path, 5, 2)
    for msg in ["aaaa", "bbbb", "cccc"]:
        _emit(handler, msg)
    handler.close()
    assert (tmp_path / "main.jsonl").read_text() == "cccc\n"
    assert (tmp_path / "main.jsonl.1").read_text() == "bbbb\n"
    assert (tmp_path / "main.jsonl.2").read_text() == "aaaa\n"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/labs-logging && uv run pytest tests/test_rotation.py -q`
Expected: FAIL (`ModuleNotFoundError: labs_logging.rotation`).

- [ ] **Step 3: Write minimal implementation**

```python
"""A JSON Lines file handler that rotates by size."""

from __future__ import annotations

import logging
from pathlib import Path

__all__ = ["JsonFileHandler", "rotate_files"]


def rotate_files(path: Path, backups: int) -> None:
    """Shift `path`, `path.1`, ... one slot right, dropping the oldest."""
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
        try:
            message = self.format(record) + "\n"
        except Exception:
            self.handleError(record)
            return
        try:
            if (
                self.path.exists()
                and self.path.stat().st_size + len(message.encode(self.encoding)) > self.max_bytes
            ):
                self._rollover()
            with self.path.open("a", encoding=self.encoding) as stream:
                stream.write(message)
        except Exception:
            self.handleError(record)

    def _rollover(self) -> None:
        if self.backups > 0:
            rotate_files(self.path, self.backups)
        else:
            self.path.unlink(missing_ok=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/labs-logging && uv run pytest tests/test_rotation.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/labs-logging/src/labs_logging/rotation.py packages/labs-logging/tests/test_rotation.py
git commit -m "feat(labs-logging): add size-bounded JSON file handler"
```

---

### Task 6: Structured envelope and rendering pipeline

**Files:**
- Create: `packages/labs-logging/src/labs_logging/envelope.py`
- Create: `packages/labs-logging/tests/test_envelope.py`

**Interfaces:**
- Consumes: `structlog`, `structlog.contextvars`.
- Produces: `class EnvelopeBuilder(application, run_id, process_id)` with `build(logger, method_name, event_dict) -> dict`; `producer_processors(builder) -> list`; `foreign_pre_chain(builder) -> list`; `renderer_for(console_json: bool, colors: bool) -> Callable`.
- Key facts for the engineer: `foreign_pre_chain` has no `TimeStamper`. Producer-side timestamp and context are captured into the `LogRecord` by the runtime's context filter (Task 7) and injected into foreign events by `_inject_captured` here. The envelope field names are exactly `timestamp`, `level`, `logger`, `application`, `run_id`, `process_id`, `event`, `exception`, `context`.

- [ ] **Step 1: Write the failing test**

```python
import logging

from labs_logging.envelope import EnvelopeBuilder, foreign_pre_chain, renderer_for


def _builder():
    return EnvelopeBuilder(application="app", run_id="run1", process_id="42")


def test_envelope_pins_ordered_fields():
    builder = _builder()
    event = {
        "event": "hello",
        "level": "info",
        "logger": "a.b",
        "timestamp": "t",
        "request_id": 7,
        "server": "s",
    }
    out = builder.build(None, None, event)
    assert list(out)[:3] == ["timestamp", "level", "logger"]
    assert out["application"] == "app"
    assert out["run_id"] == "run1"
    assert out["process_id"] == "42"
    assert out["event"] == "hello"
    assert out["context"] == {"request_id": 7, "server": "s"}


def test_explicit_event_wins_over_captured_context():
    builder = _builder()
    event = {
        "event": "e",
        "level": "i",
        "logger": "l",
        "timestamp": "t",
        "_captured_context": {"rid": 1},
        "rid": 2,
    }
    out = builder.build(None, None, event)
    assert "_captured_context" not in out
    assert out["context"] == {"rid": 2}


def test_foreign_records_get_captured_runtime():
    builder = _builder()
    record = logging.LogRecord("lib", logging.WARNING, "", 0, "boom %s", ("x",), None)
    setattr(record, "labs_context", {"rid": 3})
    setattr(record, "labs_runtime", ("app", "run2", "77"))
    setattr(record, "labs_ts", "2026-10-04T21:00:00Z")
    event = {"_record": record, "event": "boom x"}
    for processor in foreign_pre_chain(builder):
        event = processor(None, None, event)
    assert event["application"] == "app"
    assert event["run_id"] == "run2"
    assert event["process_id"] == "77"
    assert event["timestamp"] == "2026-10-04T21:00:00Z"
    assert event["level"] == "warning"
    assert event["logger"] == "lib"
    assert event["context"] == {"rid": 3}


def test_renderer_factory():
    console = renderer_for(console_json=False, colors=False)
    json_renderer = renderer_for(console_json=True, colors=False)
    assert console is not json_renderer
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/labs-logging && uv run pytest tests/test_envelope.py -q`
Expected: FAIL (`ModuleNotFoundError: labs_logging.envelope`).

- [ ] **Step 3: Write minimal implementation**

```python
"""Build the log envelope and wire structlog processors for both event kinds."""

from __future__ import annotations

from collections.abc import Callable

import structlog
from structlog.typing import EventDict

__all__ = ["EnvelopeBuilder", "foreign_pre_chain", "producer_processors", "renderer_for"]

_ENVELOPE_KEYS = (
    "timestamp",
    "level",
    "logger",
    "application",
    "run_id",
    "process_id",
    "event",
    "exception",
)


class EnvelopeBuilder:
    """Partition an event dict into ordered envelope fields and a nested context."""

    def __init__(self, *, application: str, run_id: str, process_id: str) -> None:
        self._meta = {"application": application, "run_id": run_id, "process_id": process_id}

    def build(self, logger: object, method_name: str, event_dict: EventDict) -> EventDict:
        captured = event_dict.pop("_captured_context", {})
        for key, value in self._meta.items():
            event_dict.setdefault(key, value)

        context: dict[str, object] = {}
        for key in list(event_dict):
            if key in _ENVELOPE_KEYS or key.startswith("_"):
                continue
            context[key] = event_dict.pop(key)
        context = {**captured, **context}

        ordered: dict[str, object] = {
            key: event_dict[key] for key in _ENVELOPE_KEYS if key in event_dict
        }
        ordered["context"] = context
        return ordered


def _add_logger_name(_, __, event_dict: EventDict) -> EventDict:
    record = event_dict.get("_record")
    event_dict["logger"] = record.name if record is not None else "root"
    return event_dict


def _inject_captured(_, __, event_dict: EventDict) -> EventDict:
    record = event_dict.get("_record")
    if record is not None:
        event_dict["timestamp"] = getattr(record, "labs_ts", None)
        app, run, pid = getattr(record, "labs_runtime", (None, None, None))
        event_dict["application"] = app
        event_dict["run_id"] = run
        event_dict["process_id"] = pid
        event_dict["_captured_context"] = getattr(record, "labs_context", {})
    return event_dict


def _format_foreign_exception(_, __, event_dict: EventDict) -> EventDict:
    record = event_dict.get("_record")
    if record is not None and record.exc_info:
        event_dict["exception"] = structlog.processors.format_exc_info(
            None, None, {"exc_info": record.exc_info}
        )["exception"]
    return event_dict


def producer_processors(builder: EnvelopeBuilder) -> list[Callable]:
    """Structlog processors that run in the producing thread or task."""
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        structlog.processors.format_exc_info,
        builder.build,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]


def foreign_pre_chain(builder: EnvelopeBuilder) -> list[Callable]:
    """Processors for standard-library records; timestamp and context come from the filter."""
    return [
        structlog.stdlib.ExtraAdder(),
        structlog.stdlib.add_log_level,
        _add_logger_name,
        _format_foreign_exception,
        _inject_captured,
        builder.build,
    ]


def renderer_for(console_json: bool, colors: bool) -> Callable:
    """A ProcessorFormatter renderer: console or JSON."""
    if console_json:
        return structlog.processors.JSONRenderer(sort_keys=True, ensure_ascii=False)
    return structlog.dev.ConsoleRenderer(colors=colors)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/labs-logging && uv run pytest tests/test_envelope.py -q`
Expected: 4 passed.

- [ ] **Step 5: Run ruff and ty**

Run: `uv run pre-commit run --files packages/labs-logging/src/labs_logging/envelope.py packages/labs-logging/tests/test_envelope.py`
Expected: all hooks pass.

- [ ] **Step 6: Commit**

```bash
git add packages/labs-logging/src/labs_logging/envelope.py packages/labs-logging/tests/test_envelope.py
git commit -m "feat(labs-logging): build structured envelope and rendering chain"
```

---

### Task 7: Runtime, synchronous/background dispatch, and console output

**Files:**
- Create: `packages/labs-logging/src/labs_logging/context.py`
- Create: `packages/labs-logging/src/labs_logging/runtime.py`
- Create: `packages/labs-logging/tests/test_runtime_console.py`
- Modify: `packages/labs-logging/src/labs_logging/__init__.py`

**Interfaces:**
- Consumes: `EnvelopeBuilder`, `foreign_pre_chain`, `producer_processors`, `renderer_for` (Task 6); `RunDir` and `resolve_log_dir` (Task 3); `FileLock` (Task 4).
- Produces: `configure(config: LoggingConfig) -> Runtime`; `class Runtime` (`.shutdown()`, `.close()`, `.drops`, `.healthy`, `.errors`, context-manager support); `get_logger(name: str)`; `bind_context(**kwargs) -> None`, `unbind_context(*keys) -> None`, `@contextmanager bound_context(**kwargs)`.
- Level rule the engineer must follow: handlers are created at `logging.NOTSET`; the family logger, per-child overrides, and root logger carry the real levels. Do not set an `INFO` level on the handlers, or overrides to `DEBUG` will be silently filtered.

- [ ] **Step 1: Write `context.py`**

```python
"""Scoped context helpers, re-exported from structlog's contextvars."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import structlog

__all__ = ["bind_context", "bound_context", "unbind_context"]


def bind_context(**kwargs: object) -> None:
    """Bind key-value pairs to the current task's logging context."""
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """Remove keys from the current task's logging context."""
    structlog.contextvars.unbind_contextvars(*keys)


@contextmanager
def bound_context(**kwargs: object) -> Iterator[None]:
    """Temporarily bind context, restoring prior values on exit."""
    with structlog.contextvars.bound_contextvars(**kwargs):
        yield
```

- [ ] **Step 2: Write the failing console test**

```python
import io
import logging

from labs_logging import LoggingConfig, configure, get_logger


def _cfg(tmp_path, stream, **overrides):
    base = dict(app="a", family="a", console_stream=stream, log_dir=tmp_path)
    base.update(overrides)
    return LoggingConfig(**base)


def test_console_default_no_color_for_non_tty(tmp_path):
    stream = io.StringIO()
    runtime = configure(_cfg(tmp_path, stream, file=False))
    try:
        get_logger("a.child").info("hello", request_id=1)
    finally:
        runtime.shutdown()
    out = stream.getvalue()
    assert "hello" in out
    assert "\x1b[" not in out


def test_stdlib_and_structlog_share_console(tmp_path):
    stream = io.StringIO()
    runtime = configure(_cfg(tmp_path, stream, file=False))
    try:
        get_logger("a.s").info("structured", n=1)
        logging.getLogger("other.lib").warning("foreign %s", "thing")
    finally:
        runtime.shutdown()
    out = stream.getvalue()
    assert "structured" in out
    assert "foreign thing" in out


def test_info_filters_debug_by_default(tmp_path):
    stream = io.StringIO()
    runtime = configure(_cfg(tmp_path, stream, file=False))
    try:
        get_logger("a").debug("hidden")
    finally:
        runtime.shutdown()
    assert "hidden" not in stream.getvalue()


def test_level_override_on_child(tmp_path):
    stream = io.StringIO()
    runtime = configure(
        _cfg(tmp_path, stream, file=False, level_overrides={"a.child": logging.DEBUG})
    )
    try:
        get_logger("a.child").debug("visible")
    finally:
        runtime.shutdown()
    assert "visible" in stream.getvalue()


def test_shutdown_restores_logger_state(tmp_path):
    before = logging.getLogger("a.child").getEffectiveLevel()
    stream = io.StringIO()
    runtime = configure(_cfg(tmp_path, stream, file=False))
    runtime.shutdown()
    assert logging.getLogger("a.child").getEffectiveLevel() == before
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd packages/labs-logging && uv run pytest tests/test_runtime_console.py -q`
Expected: FAIL (`ModuleNotFoundError: labs_logging.runtime`).

- [ ] **Step 4: Write `runtime.py`**

```python
"""Configure logging and own its handler lifecycle and dispatch."""

from __future__ import annotations

import logging
import logging.handlers
import os
import queue
import sys
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from labs_logging.config import LoggingConfig
from labs_logging.dirs import RunDir, resolve_log_dir
from labs_logging.envelope import (
    EnvelopeBuilder,
    foreign_pre_chain,
    producer_processors,
    renderer_for,
)
from labs_logging.errors import AlreadyConfiguredError
from labs_logging.lock import FileLock
from labs_logging.rotation import JsonFileHandler

__all__ = ["Runtime", "cleanup_runs", "configure"]

_ACTIVE: "Runtime | None" = None

_STOP = object()


class _ContextFilter(logging.Filter):
    """Capture task context, runtime identity, and timestamp on the producer side."""

    def __init__(self, application: str, run_id: str, process_id: str) -> None:
        super().__init__()
        self._runtime = (application, run_id, process_id)

    def filter(self, record: logging.LogRecord) -> bool:
        setattr(record, "labs_context", structlog.contextvars.merge_contextvars(None, None, {}))
        setattr(record, "labs_runtime", self._runtime)
        setattr(record, "labs_ts", datetime.now(timezone.utc).isoformat())
        return True


class _DroppingQueueHandler(logging.handlers.QueueHandler):
    _REPORT_EVERY = 5.0

    def __init__(self, q: queue.Queue) -> None:
        super().__init__(q)
        self.drops = 0
        self._closed = False
        self._lock = threading.Lock()
        self._last_report = 0.0

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        # structlog leaves the event dict in record.msg. The base QueueHandler
        # stringifies it here, which would break ProcessorFormatter downstream.
        # Return the record untouched; the listener's handlers own formatting.
        return record

    def enqueue(self, record: logging.LogRecord) -> None:
        with self._lock:
            if self._closed:
                return
            try:
                self.queue.put_nowait(record)
            except queue.Full:
                self.drops += 1
                self._report()

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def _report(self) -> None:
        now = time.monotonic()
        if now - self._last_report >= self._REPORT_EVERY:
            print(f"labs-logging: dropped {self.drops} events (queue full)", file=sys.stderr)
            self._last_report = now


class _Listener(threading.Thread):
    def __init__(
        self,
        q: queue.Queue,
        handlers: list[logging.Handler],
        on_error: Callable[[BaseException], None],
    ) -> None:
        super().__init__(name="labs-logging-listener", daemon=True)
        self._queue = q
        self._handlers = handlers
        self._on_error = on_error

    def run(self) -> None:
        while True:
            item = self._queue.get()
            if item is _STOP:
                return
            if isinstance(item, logging.LogRecord):
                for handler in self._handlers:
                    try:
                        if item.levelno >= handler.level:
                            handler.handle(item)
                    except BaseException as exc:  # noqa: BLE001 - a bad handler must not kill dispatch
                        self._on_error(exc)


def _strip_meta(_, __, event_dict):
    """Drop ProcessorFormatter's meta keys if present.

    Structlog events still carry `_record` and `_from_structlog` here. Foreign
    records lost them in `build`, so `remove_processors_meta` would raise KeyError.
    """
    event_dict.pop("_record", None)
    event_dict.pop("_from_structlog", None)
    return event_dict


def _console_handler(config: LoggingConfig, builder: EnvelopeBuilder) -> logging.Handler:
    stream = config.console_stream if config.console_stream is not None else sys.stderr
    colors = config.console_colors
    if colors is None:
        colors = bool(getattr(stream, "isatty", lambda: False)())
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            _strip_meta,
            renderer_for(config.console_json, colors),
        ],
        foreign_pre_chain=foreign_pre_chain(builder),
    )
    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)
    handler.setLevel(logging.NOTSET)
    return handler


def _file_formatter(builder: EnvelopeBuilder) -> structlog.stdlib.ProcessorFormatter:
    return structlog.stdlib.ProcessorFormatter(
        processors=[
            _strip_meta,
            structlog.processors.JSONRenderer(sort_keys=True, ensure_ascii=False),
        ],
        foreign_pre_chain=foreign_pre_chain(builder),
    )


class Runtime:
    """Owns the configured logging state for the lifetime of one application run."""

    def __init__(
        self,
        *,
        config: LoggingConfig,
        run: RunDir,
        run_lock: FileLock,
        root: logging.Logger,
        context_filter: _ContextFilter,
        owned_handlers: list[logging.Handler],
        extra_handlers: list[logging.Handler],
        queue_handler: _DroppingQueueHandler | None,
        listener: _Listener | None,
        restored_levels: dict[str, int],
        restored_root_level: int,
        log_dir: Path,
    ) -> None:
        self._config = config
        self._run = run
        self._run_lock = run_lock
        self._root = root
        self._context_filter = context_filter
        self._owned_handlers = owned_handlers
        self._extra_handlers = extra_handlers
        self._queue_handler = queue_handler
        self._listener = listener
        self._restored_levels = restored_levels
        self._restored_root_level = restored_root_level
        self._log_dir = log_dir
        self._done = False
        self._healthy = True
        self._errors: list[str] = []
        self._errors_lock = threading.Lock()

    @property
    def drops(self) -> int:
        return self._queue_handler.drops if self._queue_handler else 0

    @property
    def healthy(self) -> bool:
        return self._healthy

    @property
    def errors(self) -> tuple[str, ...]:
        with self._errors_lock:
            return tuple(self._errors)

    def _note_error(self, exc: BaseException) -> None:
        with self._errors_lock:
            self._healthy = False
            self._errors.append(repr(exc))

    def shutdown(self) -> None:
        if self._done:
            return
        self._done = True
        if self._queue_handler is not None and self._listener is not None:
            self._queue_handler.close()
            self._root.removeHandler(self._queue_handler)
            self._listener._queue.put(_STOP)  # noqa: SLF001
            self._listener.join(timeout=10)
        for handler in self._owned_handlers:
            try:
                handler.flush()
            except Exception:
                pass
            handler.close()
            try:
                self._root.removeHandler(handler)
            except Exception:
                pass
        for handler in self._extra_handlers:
            try:
                handler.flush()
            except Exception:
                pass
        self._root.removeFilter(self._context_filter)
        self._cleanup()
        for name, level in self._restored_levels.items():
            logging.getLogger(name).setLevel(level)
        self._root.setLevel(self._restored_root_level)
        self._run_lock.release()
        global _ACTIVE
        _ACTIVE = None

    def _cleanup(self) -> None:
        cleanup_runs(self._log_dir, self._config.retain_runs, self._run.name)

    def close(self) -> None:
        self.shutdown()

    def __enter__(self) -> "Runtime":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.shutdown()


def _is_run_dir(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink() and (path / "lock").exists()


def cleanup_runs(root: Path, retain: int, active_name: str) -> None:
    """Keep the newest `retain` runs plus any older active runs; remove the rest."""
    runs = sorted((p for p in root.iterdir() if _is_run_dir(p)), key=lambda p: p.name)
    to_delete = runs[: max(0, len(runs) - retain)]
    for run_path in sorted(to_delete, key=lambda p: p.name, reverse=True):
        if run_path.name == active_name:
            continue
        lock = FileLock(run_path / "lock")
        if lock.try_acquire():
            try:
                for child in sorted(run_path.iterdir(), key=lambda p: p.name):
                    if child.is_file() or child.is_symlink():
                        child.unlink()
                run_path.rmdir()
            finally:
                lock.release()


def configure(config: LoggingConfig) -> Runtime:
    """Configure process-wide logging and return the owning runtime."""
    global _ACTIVE
    if _ACTIVE is not None:
        raise AlreadyConfiguredError("a logging runtime is already active")

    log_dir = resolve_log_dir(config)
    log_dir.mkdir(parents=True, exist_ok=True)

    coord = FileLock(log_dir / ".coord")
    coord.acquire()
    try:
        run = RunDir.create(log_dir, datetime.now(timezone.utc))
        run_lock = FileLock(run.lock_path)
        run_lock.acquire()

        builder = EnvelopeBuilder(
            application=config.app,
            run_id=run.name,
            process_id=str(os.getpid()),
        )
        structlog.configure(
            processors=producer_processors(builder),
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=False,
        )

        root = logging.getLogger()
        if root.handlers:
            raise SetupError(
                "the root logger already has handlers; resolve competing logging configuration first"
            )
        restored_root_level = root.level
        restored_levels: dict[str, int] = {}

        family_logger = logging.getLogger(config.family)
        restored_levels[config.family] = family_logger.level
        family_logger.setLevel(config.level)

        for name, level in config.level_overrides.items():
            logger = logging.getLogger(name)
            restored_levels[name] = logger.level
            logger.setLevel(level)

        root.setLevel(config.level)

        context_filter = _ContextFilter(config.app, run.name, str(os.getpid()))
        root.addFilter(context_filter)

        owned_handlers: list[logging.Handler] = []
        total_handlers: list[logging.Handler] = []

        if config.console:
            total_handlers.append(_console_handler(config, builder))
        if config.file:
            file_handler = JsonFileHandler(
                run.main_path, max_bytes=config.max_bytes, backups=config.backups
            )
            file_handler.setFormatter(_file_formatter(builder))
            file_handler.setLevel(logging.NOTSET)
            total_handlers.append(file_handler)

        owned_handlers.extend(total_handlers)
        extra_handlers = list(config.extra_handlers)
        total_handlers.extend(extra_handlers)

        queue_handler: _DroppingQueueHandler | None = None
        listener: _Listener | None = None

        runtime = Runtime(
            config=config,
            run=run,
            run_lock=run_lock,
            root=root,
            context_filter=context_filter,
            owned_handlers=owned_handlers,
            extra_handlers=extra_handlers,
            queue_handler=queue_handler,
            listener=listener,
            restored_levels=restored_levels,
            restored_root_level=restored_root_level,
            log_dir=log_dir,
        )

        if config.synchronous:
            for handler in total_handlers:
                root.addHandler(handler)
        else:
            q: queue.Queue[Any] = queue.Queue(maxsize=config.queue_size)
            queue_handler = _DroppingQueueHandler(q)
            runtime._queue_handler = queue_handler
            root.addHandler(queue_handler)
            listener = _Listener(q, total_handlers, runtime._note_error)
            runtime._listener = listener
            listener.start()

        _ACTIVE = runtime
        cleanup_runs(log_dir, config.retain_runs, run.name)
        return runtime
    finally:
        coord.release()
```

- [ ] **Step 5: Update `__init__.py`**

```python
"""Structured logging shared across Python applications."""

import structlog

from labs_logging.config import LoggingConfig
from labs_logging.context import bind_context, bound_context, unbind_context
from labs_logging.errors import AlreadyConfiguredError, LoggingError, SetupError
from labs_logging.runtime import Runtime, configure

__all__ = [
    "AlreadyConfiguredError",
    "LoggingConfig",
    "LoggingError",
    "Runtime",
    "SetupError",
    "bind_context",
    "bound_context",
    "configure",
    "get_logger",
    "unbind_context",
    "__version__",
]

__version__ = "0.1.0"


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structured logger for `name`, e.g. `mcp_server.tools`."""
    return structlog.stdlib.get_logger(name)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd packages/labs-logging && uv run pytest tests/test_runtime_console.py -q`
Expected: 5 passed. If `test_stdlib_and_structlog_share_console` shows the foreign message without a level prefix, that is fine: the assertion only checks message text.

- [ ] **Step 7: Run ruff and ty**

Run: `uv run pre-commit run --files packages/labs-logging/src/labs_logging/__init__.py packages/labs-logging/src/labs_logging/context.py packages/labs-logging/src/labs_logging/runtime.py packages/labs-logging/tests/test_runtime_console.py`
Expected: all hooks pass. Fix findings before committing. If `ty` complains about the listener's private `_STOP` sentinel or `runtime._queue_handler` assignment, rewrite `Runtime` to expose a small `_start_background()` method instead and call it in `configure`.

- [ ] **Step 8: Commit**

```bash
git add packages/labs-logging/src packages/labs-logging/tests/test_runtime_console.py
git commit -m "feat(labs-logging): add runtime with dispatch, context, and console"
```

---

### Task 8: JSON file output

**Files:**
- Create: `packages/labs-logging/tests/test_runtime_file.py`

**Interfaces:**
- Consumes: `configure`, `get_logger` (Task 7); `JsonFileHandler` (Task 5).
- Produces: none new. Verifies the file destination end-to-end, including the foreign pre-chain.

- [ ] **Step 1: Write the failing test**

```python
import json
import logging

from labs_logging import LoggingConfig, configure, get_logger


def test_file_receives_json_lines(tmp_path):
    config = LoggingConfig(app="a", family="a", console=False, log_dir=tmp_path)
    runtime = configure(config)
    try:
        get_logger("a.child").info("hello", request_id=7)
        logging.getLogger("lib").error("oops")
    finally:
        runtime.shutdown()
    runs = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert len(runs) == 1
    lines = (runs[0] / "main.jsonl").read_text().splitlines()
    parsed = [json.loads(line) for line in lines]
    assert len(parsed) == 2
    first, second = parsed
    assert first["event"] == "hello"
    assert first["context"]["request_id"] == 7
    assert first["application"] == "a"
    assert first["logger"] == "a.child"
    assert second["logger"] == "lib"
    assert second["event"] == "oops"
    assert second["application"] == "a"
    assert "\x1b[" not in (runs[0] / "main.jsonl").read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/labs-logging && uv run pytest tests/test_runtime_file.py -q`
Expected: the file should already exist, but this test is the first to exercise the foreign-record JSON path. If it passes on the first run, that is acceptable evidence the path works; if it fails, fix the failure before proceeding.

- [ ] **Step 3: Commit**

```bash
git add packages/labs-logging/tests/test_runtime_file.py
git commit -m "test(labs-logging): verify JSON Lines file output"
```

---

### Task 9: Whole-run retention and active-run protection

**Files:**
- Create: `packages/labs-logging/tests/test_retention.py`

**Interfaces:**
- Consumes: `cleanup_runs` (Task 7), `RunDir` (Task 3), `FileLock` (Task 4).
- Produces: none new.

- [ ] **Step 1: Write the failing test**

```python
import datetime

from labs_logging.dirs import RunDir
from labs_logging.lock import FileLock
from labs_logging.runtime import cleanup_runs


def _make_run(root, ts_ms):
    now = datetime.datetime(2026, 10, 4, 12, 0, 0, tzinfo=datetime.timezone.utc).replace(
        microsecond=ts_ms
    )
    run = RunDir.create(root, now)
    run.main_path.write_text("x")
    run.lock_path.write_text("")
    return run


def test_keeps_newest_five(tmp_path):
    runs = [_make_run(tmp_path, i * 1000) for i in range(8)]
    cleanup_runs(tmp_path, retain=5, active_name="none")
    kept = {p.name for p in tmp_path.iterdir()}
    assert kept == {r.name for r in runs[3:]}


def test_active_old_run_survives(tmp_path):
    runs = [_make_run(tmp_path, i * 1000) for i in range(8)]
    oldest = runs[0]
    lock = FileLock(oldest.lock_path)
    lock.acquire()
    try:
        cleanup_runs(tmp_path, retain=5, active_name="none")
    finally:
        lock.release()
    assert oldest.name in {p.name for p in tmp_path.iterdir()}


def test_active_name_always_skipped(tmp_path):
    runs = [_make_run(tmp_path, i * 1000) for i in range(8)]
    current = runs[2]  # inside the deletion window
    cleanup_runs(tmp_path, retain=5, active_name=current.name)
    assert current.name in {p.name for p in tmp_path.iterdir()}
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd packages/labs-logging && uv run pytest tests/test_retention.py -q`
Expected: 3 passed.

- [ ] **Step 3: Commit**

```bash
git add packages/labs-logging/tests/test_retention.py
git commit -m "test(labs-logging): verify whole-run retention and active-run protection"
```

---

### Task 10: Dispatch modes, queue overflow, and strict setup

**Files:**
- Modify: `packages/labs-logging/src/labs_logging/runtime.py` (wrap setup failures in `SetupError` with rollback)
- Create: `packages/labs-logging/tests/test_dispatch.py`

**Interfaces:**
- Consumes: `configure`, `get_logger`, `Runtime` (Task 7).
- Produces: none new, but `configure` now raises `SetupError` rather than the raw `OSError`/`FileExistsError` on failure, and releases locks it acquired on the failure path.

- [ ] **Step 1: Write the failing test**

```python
import asyncio
import io
import logging
import threading
import time

import pytest

from labs_logging import LoggingConfig, LoggingError, configure, get_logger


def _run_dirs(tmp_path):
    return [p for p in tmp_path.iterdir() if p.is_dir() and p.name != ".coord"]


def test_synchronous_mode_has_no_listener_thread(tmp_path):
    config = LoggingConfig(app="a", family="a", console=False, synchronous=True, log_dir=tmp_path)
    runtime = configure(config)
    try:
        assert all(t.name != "labs-logging-listener" for t in threading.enumerate())
        get_logger("a").info("sync", k=1)
        data = (_run_dirs(tmp_path)[0] / "main.jsonl").read_text()
        assert "sync" in data
    finally:
        runtime.shutdown()


def test_background_mode_starts_listener(tmp_path):
    config = LoggingConfig(app="a", family="a", console=False, synchronous=False, log_dir=tmp_path)
    runtime = configure(config)
    try:
        assert any(t.name == "labs-logging-listener" for t in threading.enumerate())
        get_logger("a").info("bg", k=1)
    finally:
        runtime.shutdown()
    assert "bg" in (_run_dirs(tmp_path)[0] / "main.jsonl").read_text()


class _SlowHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        time.sleep(0.2)


def test_queue_overflow_drops_and_counts(tmp_path):
    config = LoggingConfig(
        app="a",
        family="a",
        console=False,
        file=False,
        synchronous=False,
        queue_size=2,
        extra_handlers=[_SlowHandler()],
        log_dir=tmp_path,
    )
    runtime = configure(config)
    try:
        for i in range(10):
            get_logger("a").info("msg %d", i)
    finally:
        runtime.shutdown()
    assert runtime.drops > 0


class _BoomHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        raise RuntimeError("disk full")


def test_handler_failure_marks_unhealthy_and_keeps_console(tmp_path):
    stream = io.StringIO()
    config = LoggingConfig(
        app="a",
        family="a",
        console_stream=stream,
        file=False,
        extra_handlers=[_BoomHandler()],
        log_dir=tmp_path,
    )
    runtime = configure(config)
    try:
        get_logger("a").info("boom")
    finally:
        runtime.shutdown()
    assert not runtime.healthy
    assert runtime.errors
    assert "boom" in stream.getvalue()


def test_async_context_is_task_local(tmp_path):
    config = LoggingConfig(app="a", family="a", console=False, log_dir=tmp_path)
    runtime = configure(config)

    async def run():
        from labs_logging import bind_context

        async def worker(rid):
            bind_context(request_id=rid)
            get_logger("a.w").info("do", step=1)
            await asyncio.sleep(0)

        await asyncio.gather(worker("r1"), worker("r2"))

    try:
        asyncio.run(run())
    finally:
        runtime.shutdown()

    lines = (_run_dirs(tmp_path)[0] / "main.jsonl").read_text().splitlines()
    import json

    rids = {json.loads(line)["context"].get("request_id") for line in lines}
    assert rids == {"r1", "r2"}


def test_setup_failure_raises_and_rolls_back(tmp_path):
    bad = tmp_path / "not-a-dir"
    bad.write_text("file")
    with pytest.raises(LoggingError):
        configure(LoggingConfig(app="a", family="a", log_dir=bad))
    runtime = configure(LoggingConfig(app="a", family="a", console=False, log_dir=tmp_path / "ok"))
    runtime.shutdown()


def test_restart_after_shutdown(tmp_path):
    first = configure(LoggingConfig(app="a", family="a", console=False, log_dir=tmp_path / "runs"))
    first.shutdown()
    second = configure(LoggingConfig(app="a", family="a", console=False, log_dir=tmp_path / "runs"))
    second.shutdown()


def test_second_configure_while_active_raises(tmp_path):
    config = LoggingConfig(app="a", family="a", console=False, log_dir=tmp_path)
    runtime = configure(config)
    try:
        with pytest.raises(LoggingError):
            configure(config)
    finally:
        runtime.shutdown()


def test_existing_root_handler_raises(tmp_path):
    logging.getLogger().addHandler(logging.StreamHandler(io.StringIO()))
    try:
        with pytest.raises(LoggingError):
            configure(LoggingConfig(app="a", family="a", log_dir=tmp_path))
    finally:
        logging.getLogger().handlers.clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/labs-logging && uv run pytest tests/test_dispatch.py -q`
Expected: `test_setup_failure_raises_and_rolls_back` FAILS first, because `configure` currently leaks a raw `FileExistsError` instead of `SetupError`.

- [ ] **Step 3: Wrap `configure` setup failures**

Rename the current `configure` body to `_do_configure(config: LoggingConfig) -> Runtime` and add a thin public wrapper. At the top of `runtime.py` import `SetupError`.

```python
from labs_logging.errors import AlreadyConfiguredError, SetupError


def configure(config: LoggingConfig) -> Runtime:
    """Configure process-wide logging and return the owning runtime."""
    global _ACTIVE
    if _ACTIVE is not None:
        raise AlreadyConfiguredError("a logging runtime is already active")
    try:
        return _do_configure(config)
    except LoggingError:
        raise
    except Exception as exc:
        raise SetupError(f"logging setup failed: {exc}") from exc


def _do_configure(config: LoggingConfig) -> Runtime:
    # The body of the previous configure(), unchanged except:
    # - it no longer checks _ACTIVE (the wrapper did that)
    # - on any Exception after run_lock.acquire(), it releases run_lock and
    #   removes any handlers already added to root before re-raising.
    global _ACTIVE
    log_dir = resolve_log_dir(config)
    log_dir.mkdir(parents=True, exist_ok=True)

    coord = FileLock(log_dir / ".coord")
    coord.acquire()
    try:
        run = RunDir.create(log_dir, datetime.now(timezone.utc))
        run_lock = FileLock(run.lock_path)
        run_lock.acquire()
        try:
            # ... build builder, structlog.configure, set levels, add filter,
            # build handlers, build runtime, addHandler, start listener ...
            _ACTIVE = runtime
            cleanup_runs(log_dir, config.retain_runs, run.name)
            return runtime
        except Exception:
            # Roll back whatever this attempt installed before re-raising.
            for handler in owned_handlers:
                try:
                    root.removeHandler(handler)
                    handler.close()
                except Exception:
                    pass
            run_lock.release()
            raise
    finally:
        coord.release()
```

The inner body (builder, levels, handlers, runtime assembly, dispatch) is the same code from Task 7 Step 4, now nested inside the `try` that releases `run_lock` on failure.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/labs-logging && uv run pytest tests/test_dispatch.py -q`
Expected: 10 passed.

- [ ] **Step 5: Run ruff and ty**

Run: `uv run pre-commit run --files packages/labs-logging/src/labs_logging/runtime.py packages/labs-logging/tests/test_dispatch.py`
Expected: all hooks pass. Fix findings before committing.

- [ ] **Step 6: Commit**

```bash
git add packages/labs-logging/src/labs_logging/runtime.py packages/labs-logging/tests/test_dispatch.py
git commit -m "feat(labs-logging): enforce strict setup and verify dispatch modes"
```

---

### Task 11: Two processes, two files

**Files:**
- Create: `packages/labs-logging/tests/test_multiprocess.py`

**Interfaces:**
- Consumes: `configure` (Task 7).
- Produces: none new. Verifies two simultaneous processes never share a rotating file.

- [ ] **Step 1: Write the failing test**

```python
import subprocess
import sys
import textwrap


def test_two_processes_write_separate_files(tmp_path):
    code = textwrap.dedent(
        """
        import sys
        from pathlib import Path
        from labs_logging import LoggingConfig, configure, get_logger

        log_dir = Path(sys.argv[1])
        runtime = configure(LoggingConfig(app="a", family="a", console=False, log_dir=log_dir))
        with runtime:
            get_logger("a.child").info("hello", pid=True)
        """
    )
    first = subprocess.Popen([sys.executable, "-c", code, str(tmp_path)])
    second = subprocess.Popen([sys.executable, "-c", code, str(tmp_path)])
    first.wait()
    second.wait()
    runs = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert len(runs) == 2
    for run in runs:
        content = (run / "main.jsonl").read_text()
        assert '"hello"' in content
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd packages/labs-logging && uv run pytest tests/test_multiprocess.py -q`
Expected: 1 passed. The two subprocesses import the installed `labs_logging`; if the package is not importable on `PYTHONPATH` yet, run `uv run --package labs-logging pytest` or set the venv site-packages explicitly before committing.

- [ ] **Step 3: Commit**

```bash
git add packages/labs-logging/tests/test_multiprocess.py
git commit -m "test(labs-logging): verify two processes write separate files"
```

---

### Task 12: Dummy app and docs check

**Files:**
- Create: `packages/labs-logging/examples/dummy.py`
- Verify: `packages/labs-logging/README.md` matches the shipped API

**Interfaces:**
- Consumes: the full public surface (`configure`, `LoggingConfig`, `get_logger`, `bind_context`, `bound_context`, `Runtime`).
- Produces: a runnable example demonstrating parent/child loggers, a standard-library record, scoped context, an exception, and both dispatch modes.

- [ ] **Step 1: Write `examples/dummy.py`**

```python
"""Runnable demo: parent/child loggers, a stdlib record, context, an exception.

Run inside the worktree:
  uv run --package labs-logging python packages/labs-logging/examples/dummy.py --sync
Omit the flag for background dispatch.
"""

from __future__ import annotations

import logging
import sys

from labs_logging import LoggingConfig, bind_context, bound_context, configure, get_logger


def main() -> None:
    synchronous = "--sync" in sys.argv
    runtime = configure(LoggingConfig(app="dummy", family="dummy_app", synchronous=synchronous))
    with runtime:
        parent = get_logger("dummy_app")
        child = get_logger("dummy_app.tools")
        bind_context(session="demo-session")
        parent.info("running the demo")
        child.info("tool called", tool="add", result=3)
        with bound_context(request_id="req-42"):
            child.info("scoped call")
        logging.getLogger("third.party").warning("a stdlib message")
        try:
            raise ValueError("something broke")
        except ValueError:
            parent.exception("failed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the example and confirm output**

Run: `cd packages/labs-logging && uv run python examples/dummy.py 2>&1`
Expected: colorful structured lines on stderr; a `main.jsonl` file under the platform user log dir for `dummy` with six JSON records. Check that the stdlib message and the exception both appear once, and that choosing `--sync` makes no observable behavioral difference beyond disabled background dispatch.

- [ ] **Step 3: Verify README matches the API**

Re-read `README.md` and confirm every import and call it shows (`LoggingConfig`, `configure`, `get_logger`) matches `__init__.py`. Fix the README if any name drifted. No other docs exist in this package to check.

- [ ] **Step 4: Full-suite run**

Run: `cd packages/labs-logging && uv run pytest -q`
Expected: all tests pass (Task 1 through Task 11 combined).

- [ ] **Step 5: Run all hooks**

Run: `uv run pre-commit run --all-files`
Expected: every hook passes. Fix any findings and re-commit the affected files.

- [ ] **Step 6: Commit**

```bash
git add packages/labs-logging/examples packages/labs-logging/README.md
git commit -m "docs(labs-logging): add dummy app and align README"
```
```
