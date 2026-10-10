import asyncio
import io
import json
import logging
import threading
import time

import pytest

from labs_logging import LoggingConfig, LoggingError, configure, get_logger


def _run_dirs(tmp_path):
    return [p for p in (tmp_path / "a").iterdir() if p.is_dir() and p.name != ".coord"]


def _main_text(tmp_path):
    return (_run_dirs(tmp_path)[0] / "main.jsonl").read_text()


def _listener_threads():
    return [t for t in threading.enumerate() if t.name == "labs-logging-listener"]


def test_synchronous_mode_has_no_listener_thread(tmp_path):
    config = LoggingConfig(app="a", family="a", console=False, synchronous=True, log_dir=tmp_path)
    runtime = configure(config)
    try:
        assert not _listener_threads()
        get_logger("a").info("sync", k=1)
        assert "sync" in _main_text(tmp_path)
    finally:
        runtime.shutdown()


def test_background_mode_starts_listener(tmp_path):
    config = LoggingConfig(app="a", family="a", console=False, synchronous=False, log_dir=tmp_path)
    runtime = configure(config)
    try:
        assert _listener_threads()
        get_logger("a").info("bg", k=1)
    finally:
        runtime.shutdown()
    assert not _listener_threads()
    assert "bg" in _main_text(tmp_path)


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


def test_setup_failure_raises_and_rolls_back(tmp_path):
    bad = tmp_path / "not-a-dir"
    bad.write_text("file")
    with pytest.raises(LoggingError):
        configure(LoggingConfig(app="a", family="a", log_dir=bad))
    assert logging.getLogger().handlers == []
    assert not _listener_threads()
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
    foreign = logging.StreamHandler(io.StringIO())
    logging.getLogger().addHandler(foreign)
    try:
        with pytest.raises(LoggingError):
            configure(LoggingConfig(app="a", family="a", log_dir=tmp_path))
        assert logging.getLogger().handlers == [foreign]
    finally:
        logging.getLogger().handlers.clear()


def test_async_context_is_task_local(tmp_path):
    from labs_logging import bind_context

    runtime = configure(LoggingConfig(app="a", family="a", console=False, log_dir=tmp_path))

    async def worker(rid):
        bind_context(request_id=rid)
        get_logger("a.w").info("do", step=1)
        await asyncio.sleep(0)

    async def run():
        await asyncio.gather(worker("r1"), worker("r2"))

    try:
        asyncio.run(run())
    finally:
        runtime.shutdown()
    lines = _main_text(tmp_path).splitlines()
    assert {json.loads(line)["context"].get("request_id") for line in lines} == {"r1", "r2"}
