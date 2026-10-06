"""Configure logging and own its handler lifecycle and dispatch."""

from __future__ import annotations

import contextlib
import logging
import logging.handlers
import os
import queue
import sys
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO, cast

import structlog
from structlog.typing import EventDict

from labs_logging.config import LoggingConfig
from labs_logging.dirs import RunDir, resolve_log_dir
from labs_logging.envelope import (
    EnvelopeBuilder,
    foreign_pre_chain,
    producer_processors,
    renderer_for,
)
from labs_logging.errors import AlreadyConfiguredError, SetupError
from labs_logging.lock import FileLock
from labs_logging.rotation import JsonFileHandler

__all__ = ["Runtime", "cleanup_runs", "configure"]

_log = logging.getLogger(__name__)

_ACTIVE: Runtime | None = None
_ACTIVE_LOCK = threading.Lock()

_STOP = object()
_JOIN_TIMEOUT = 10.0
_STOP_TIMEOUT = 5.0
_POLL_INTERVAL = 0.2


def _diagnostic(message: str) -> None:
    """Write straight to stderr, outside the logging pipeline."""
    # A closed stderr leaves nowhere to report, so the error is dropped.
    with contextlib.suppress(OSError, ValueError):
        print(f"labs-logging: {message}", file=sys.stderr)


class _CaptureFilter(logging.Filter):
    """Capture task context, runtime identity, and timestamp in the producing thread.

    Logger-level filters do not run for records propagated from child loggers, so
    this filter sits on the dispatch handler, which every record reaches.
    """

    def __init__(self, application: str, run_id: str, process_id: str) -> None:
        super().__init__()
        self._runtime = (application, run_id, process_id)

    def filter(self, record: logging.LogRecord) -> bool:
        # Idempotent: the first filter to see a record wins.
        if not hasattr(record, "labs_ts"):
            record.labs_ts = datetime.now(UTC).isoformat()
            record.labs_runtime = self._runtime
            record.labs_context = dict(structlog.contextvars.get_contextvars())
        return True


def _strip_meta(_logger: object, _method: str, event_dict: EventDict) -> EventDict:
    """Drop ProcessorFormatter's meta keys if present.

    Structlog events still carry `_record` and `_from_structlog` here. Foreign
    records lost them in `build`, so `remove_processors_meta` would raise KeyError.
    """
    event_dict.pop("_record", None)
    event_dict.pop("_from_structlog", None)
    return event_dict


class _FanOutHandler(logging.Handler):
    """Deliver one record to each destination; one failing handler cannot block the rest."""

    def __init__(
        self,
        handlers: list[logging.Handler],
        on_error: Any,
    ) -> None:
        super().__init__(logging.NOTSET)
        self._handlers = handlers
        self._on_error = on_error

    def emit(self, record: logging.LogRecord) -> None:
        for handler in self._handlers:
            if record.levelno < handler.level:
                continue
            try:
                handler.handle(record)
            except Exception as exc:
                self._on_error(handler, exc)


class _DroppingQueueHandler(logging.handlers.QueueHandler):
    """Enqueue without blocking; count and report drops when the queue is full."""

    _REPORT_EVERY = 5.0

    def __init__(self, q: queue.Queue[Any]) -> None:
        super().__init__(q)
        self.drops = 0
        self._closed = False
        self._lock = threading.Lock()
        self._last_report = float("-inf")
        self._reported_drops = 0

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        # structlog leaves the event dict in record.msg. The base class stringifies
        # it here, which would break ProcessorFormatter downstream. Return the
        # record untouched; the listener's handlers own formatting.
        return record

    def enqueue(self, record: logging.LogRecord) -> None:
        with self._lock:
            if self._closed:
                return
            message = None
            try:
                self.queue.put_nowait(record)
            except queue.Full:
                self.drops += 1
                message = self._due_report()
        # Print outside the lock so a slow stderr cannot stall other producers.
        if message:
            _diagnostic(message)

    def stop_accepting(self) -> None:
        with self._lock:
            self._closed = True

    def _due_report(self) -> str | None:
        """Return a drop message if the report interval has passed. Caller holds the lock."""
        now = time.monotonic()
        if now - self._last_report < self._REPORT_EVERY:
            return None
        self._last_report = now
        self._reported_drops = self.drops
        return f"dropped {self.drops} events (queue full)"

    def report_final(self) -> None:
        """Report drops that the periodic report never covered."""
        with self._lock:
            unreported = self.drops > self._reported_drops
            self._reported_drops = self.drops
            total = self.drops
        if unreported:
            _diagnostic(f"dropped {total} events in total (queue full)")


class _Listener(threading.Thread):
    """Drain the queue into one sink until told to stop."""

    def __init__(
        self,
        q: queue.Queue[Any],
        sink: logging.Handler,
        on_error: Callable[[BaseException], None],
    ) -> None:
        super().__init__(name="labs-logging-listener", daemon=True)
        self._queue = q
        self._sink = sink
        self._on_error = on_error
        self._abandoned = threading.Event()

    def run(self) -> None:
        while True:
            try:
                item = self._queue.get(timeout=_POLL_INTERVAL)
            except queue.Empty:
                # No stop sentinel was queued; exit once the backlog is drained.
                if self._abandoned.is_set():
                    return
                continue
            if item is _STOP:
                return
            try:
                self._sink.handle(item)
            except Exception as exc:
                self._on_error(exc)

    def stop(self) -> None:
        """Ask the listener to finish queued events, then wait for it, within bounds."""
        try:
            self._queue.put(_STOP, timeout=_STOP_TIMEOUT)
        except queue.Full:
            self._abandoned.set()
            self._on_error(TimeoutError("listener queue stayed full; stop signal not queued"))
        self.join(timeout=_JOIN_TIMEOUT)
        if self.is_alive():
            self._abandoned.set()
            self._on_error(TimeoutError("listener did not stop in time; continuing shutdown"))


def _console_handler(config: LoggingConfig, builder: EnvelopeBuilder) -> logging.Handler:
    stream = cast("TextIO", config.console_stream) if config.console_stream else sys.stderr
    colors = config.console_colors
    if colors is None:
        colors = stream.isatty() if hasattr(stream, "isatty") else False
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[_strip_meta, renderer_for(config.console_json, colors)],
        foreign_pre_chain=foreign_pre_chain(builder),
    )
    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)
    handler.setLevel(logging.NOTSET)
    return handler


def _file_handler(config: LoggingConfig, run: RunDir, builder: EnvelopeBuilder) -> logging.Handler:
    handler = JsonFileHandler(run.main_path, max_bytes=config.max_bytes, backups=config.backups)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                _strip_meta,
                structlog.processors.JSONRenderer(sort_keys=True, ensure_ascii=False),
            ],
            foreign_pre_chain=foreign_pre_chain(builder),
        )
    )
    handler.setLevel(logging.NOTSET)
    return handler


def _is_run_dir(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink() and (path / "lock").is_file()


def cleanup_runs(root: Path, retain: int, active_name: str) -> None:
    """Keep the newest `retain` runs plus any older active runs; remove the rest.

    The caller holds the application's coordination lock.
    """
    runs = sorted((p for p in root.iterdir() if _is_run_dir(p)), key=lambda p: p.name)
    for run_path in runs[: max(0, len(runs) - retain)]:
        if run_path.name == active_name:
            continue
        lock = FileLock(run_path / "lock")
        if not lock.try_acquire():
            lock.release()
            continue
        try:
            for child in run_path.iterdir():
                if child.name != "lock" and (child.is_file() or child.is_symlink()):
                    child.unlink()
        finally:
            lock.release()
        # Unrelated subdirectories keep the run in place instead of being deleted.
        (run_path / "lock").unlink(missing_ok=True)
        try:
            run_path.rmdir()
        except OSError:
            _log.debug("left run directory %s in place", run_path)


class Runtime:
    """Owns the configured logging state for the lifetime of one application run."""

    def __init__(self, config: LoggingConfig, run: RunDir, log_dir: Path) -> None:
        self._config = config
        self._run = run
        self._log_dir = log_dir
        self._root = logging.getLogger()
        self._run_lock = FileLock(run.lock_path)
        self._restored_levels: dict[str, int] = {}
        self._restored_root_level = self._root.level
        self._owned: list[logging.Handler] = []
        self._extra: list[logging.Handler] = []
        self._dispatch: logging.Handler | None = None
        self._queue_handler: _DroppingQueueHandler | None = None
        self._listener: _Listener | None = None
        self._done = False
        self._state_lock = threading.Lock()
        self._healthy = True
        self._errors: list[str] = []
        self._reported: set[int] = set()

    @property
    def drops(self) -> int:
        """Events dropped because the background queue was full."""
        return self._queue_handler.drops if self._queue_handler else 0

    @property
    def healthy(self) -> bool:
        """False once any destination has raised an error."""
        return self._healthy

    @property
    def errors(self) -> tuple[str, ...]:
        """Descriptions of destination errors, oldest first."""
        with self._state_lock:
            return tuple(self._errors)

    def _note_error(self, handler: logging.Handler, exc: BaseException) -> None:
        with self._state_lock:
            self._healthy = False
            self._errors.append(f"{type(handler).__name__}: {exc!r}")
            first = id(handler) not in self._reported
            self._reported.add(id(handler))
        if first:
            _diagnostic(f"{type(handler).__name__} failed: {exc!r}")

    def _note_listener_error(self, exc: BaseException) -> None:
        self._note_error(logging.Handler(), exc)

    def _install(self) -> None:
        config = self._config
        self._run_lock.acquire()
        builder = EnvelopeBuilder(
            application=config.app, run_id=self._run.name, process_id=str(os.getpid())
        )
        structlog.configure(
            processors=producer_processors(builder),
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=False,
        )

        for name in (config.family, *config.level_overrides):
            self._restored_levels.setdefault(name, logging.getLogger(name).level)
        logging.getLogger(config.family).setLevel(config.level)
        for name, level in config.level_overrides.items():
            logging.getLogger(name).setLevel(level)
        self._root.setLevel(config.level)

        if config.console:
            self._owned.append(_console_handler(config, builder))
        if config.file:
            self._owned.append(_file_handler(config, self._run, builder))
        self._extra = [h for h in config.extra_handlers if isinstance(h, logging.Handler)]

        fan_out = _FanOutHandler([*self._owned, *self._extra], self._note_error)
        capture = _CaptureFilter(config.app, self._run.name, str(os.getpid()))
        if config.synchronous:
            self._dispatch = fan_out
            fan_out.addFilter(capture)
        else:
            q: queue.Queue[Any] = queue.Queue(maxsize=config.queue_size)
            self._queue_handler = _DroppingQueueHandler(q)
            self._queue_handler.addFilter(capture)
            self._dispatch = self._queue_handler
            self._listener = _Listener(q, fan_out, self._note_listener_error)
            self._listener.start()
        self._root.addHandler(self._dispatch)

    def _release(self) -> None:
        """Stop dispatch and release everything this runtime holds. Safe on partial setup."""
        if self._dispatch is not None:
            self._root.removeHandler(self._dispatch)
        if self._queue_handler is not None:
            self._queue_handler.stop_accepting()
        if self._listener is not None and self._listener.is_alive():
            self._listener.stop()
        if self._queue_handler is not None:
            self._queue_handler.report_final()
        for handler in self._owned:
            self._safely(handler.flush)
            self._safely(handler.close)
        for handler in self._extra:
            self._safely(handler.flush)
        for name, level in self._restored_levels.items():
            logging.getLogger(name).setLevel(level)
        self._root.setLevel(self._restored_root_level)

    def _safely(self, action: Any) -> None:
        try:
            action()
        except Exception as exc:
            self._note_error(logging.Handler(), exc)

    def shutdown(self) -> None:
        """Drain queued events, flush, clean up old runs, and release ownership."""
        global _ACTIVE  # noqa: PLW0603 - the process-wide active runtime
        with self._state_lock:
            if self._done:
                return
            self._done = True
        try:
            self._release()
            try:
                with FileLock(self._log_dir / ".coord"):
                    cleanup_runs(self._log_dir, self._config.retain_runs, self._run.name)
            except OSError as exc:
                self._note_error(logging.Handler(), exc)
        finally:
            self._run_lock.release()
            with _ACTIVE_LOCK:
                if _ACTIVE is self:
                    _ACTIVE = None

    def close(self) -> None:
        """Alias for `shutdown`."""
        self.shutdown()

    def __enter__(self) -> Runtime:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.shutdown()


def _remove_run(run: RunDir) -> None:
    for child in run.path.iterdir():
        child.unlink(missing_ok=True)
    run.path.rmdir()


def configure(config: LoggingConfig) -> Runtime:
    """Configure process-wide logging and return the owning runtime.

    Raises:
        AlreadyConfiguredError: A runtime is already active in this process.
        SetupError: Destinations, locks, or handlers could not be set up. Nothing
            stays installed.
    """
    global _ACTIVE  # noqa: PLW0603 - the process-wide active runtime
    with _ACTIVE_LOCK:
        if _ACTIVE is not None:
            raise AlreadyConfiguredError("a logging runtime is already active")
        if logging.getLogger().handlers:
            raise SetupError(
                "the root logger already has handlers; resolve competing logging "
                "configuration first"
            )
        bad = [h for h in config.extra_handlers if not isinstance(h, logging.Handler)]
        if bad:
            raise SetupError(f"extra_handlers must be logging.Handler instances, got {bad!r}")

        log_dir = resolve_log_dir(config)
        run: RunDir | None = None
        runtime: Runtime | None = None
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            with FileLock(log_dir / ".coord"):
                run = RunDir.create(log_dir, datetime.now(UTC))
                runtime = Runtime(config, run, log_dir)
                runtime._install()
                cleanup_runs(log_dir, config.retain_runs, run.name)
        except Exception as exc:
            if runtime is not None:
                runtime._release()
                runtime._run_lock.release()
            if run is not None:
                try:
                    _remove_run(run)
                except OSError:
                    _log.debug("could not remove run directory %s", run.path)
            raise SetupError(f"could not configure logging: {exc}") from exc
        _ACTIVE = runtime
        return runtime
