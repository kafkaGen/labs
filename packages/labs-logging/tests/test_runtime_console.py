import io
import json
import logging
from typing import Any

import pytest

from labs_logging import (
    AlreadyConfiguredError,
    LoggingConfig,
    SetupError,
    bind_context,
    bound_context,
    configure,
    get_logger,
)


def _cfg(tmp_path, stream=None, **overrides):
    base: dict[str, Any] = dict(app="a", family="a", console_stream=stream, log_dir=tmp_path)
    base.update(overrides)
    return LoggingConfig(**base)


def _events(tmp_path):
    (main,) = tmp_path.glob("*/main.jsonl")
    return [json.loads(line) for line in main.read_text(encoding="utf-8").splitlines()]


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


@pytest.mark.parametrize("synchronous", [True, False])
@pytest.mark.parametrize("console_json", [True, False])
def test_console_renders_both_event_kinds(tmp_path, synchronous, console_json):
    stream = io.StringIO()
    runtime = configure(
        _cfg(tmp_path, stream, file=False, synchronous=synchronous, console_json=console_json)
    )
    try:
        get_logger("a.s").info("structured", n=1)
        logging.getLogger("other.lib").warning("foreign %s", "thing")
    finally:
        runtime.shutdown()
    out = stream.getvalue()
    assert "structured" in out
    assert "foreign thing" in out
    assert runtime.healthy
    if console_json:
        lines = [json.loads(line) for line in out.splitlines()]
        assert [line["timestamp"] is not None for line in lines] == [True, True]


@pytest.mark.parametrize("synchronous", [True, False])
def test_file_renders_both_event_kinds_with_timestamps(tmp_path, synchronous):
    runtime = configure(_cfg(tmp_path, io.StringIO(), synchronous=synchronous))
    try:
        get_logger("a.s").info("structured", n=1)
        logging.getLogger("other.lib").warning("foreign %s", "thing")
    finally:
        runtime.shutdown()
    structured, foreign = _events(tmp_path)
    (run_name,) = [p.name for p in tmp_path.iterdir() if p.is_dir()]
    assert structured["event"] == "structured"
    assert structured["context"] == {"n": 1}
    assert foreign["event"] == "foreign thing"
    assert foreign["logger"] == "other.lib"
    assert foreign["level"] == "warning"
    for event in (structured, foreign):
        assert event["timestamp"]
        assert event["application"] == "a"
        assert event["run_id"] == run_name
        assert "_record" not in event
        assert "_from_structlog" not in event


def test_foreign_record_timestamp_never_null_in_background_mode(tmp_path):
    runtime = configure(_cfg(tmp_path, io.StringIO(), console=False))
    try:
        for i in range(20):
            logging.getLogger("lib").error("e%s", i)
    finally:
        runtime.shutdown()
    events = _events(tmp_path)
    assert len(events) == 20
    assert all(event["timestamp"] for event in events)


def test_context_is_captured_on_producer_side(tmp_path):
    runtime = configure(_cfg(tmp_path, io.StringIO(), console=False))
    try:
        bind_context(req="r1")
        logging.getLogger("lib").info("stdlib")
        with bound_context(req="r2"):
            get_logger("a").info("structured")
        bind_context(req="r3")
    finally:
        runtime.shutdown()
    stdlib, structured = _events(tmp_path)
    assert stdlib["context"] == {"req": "r1"}
    assert structured["context"] == {"req": "r2"}


def test_console_defaults_to_stderr_not_stdout(tmp_path, capsys):
    runtime = configure(_cfg(tmp_path, file=False))
    try:
        get_logger("a").info("to-stderr")
    finally:
        runtime.shutdown()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "to-stderr" in captured.err


def test_console_disabled_writes_nothing(tmp_path):
    stream = io.StringIO()
    runtime = configure(_cfg(tmp_path, stream, console=False))
    try:
        get_logger("a").info("quiet")
    finally:
        runtime.shutdown()
    assert stream.getvalue() == ""


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
        get_logger("a.other").debug("still hidden")
    finally:
        runtime.shutdown()
    assert "visible" in stream.getvalue()
    assert "still hidden" not in stream.getvalue()


def test_override_on_family_name_restores_original_level(tmp_path):
    logging.getLogger("fam").setLevel(logging.ERROR)
    runtime = configure(_cfg(tmp_path, io.StringIO(), family="fam", level_overrides={"fam": 10}))
    runtime.shutdown()
    assert logging.getLogger("fam").level == logging.ERROR
    logging.getLogger("fam").setLevel(logging.NOTSET)


def test_shutdown_restores_logger_state(tmp_path):
    root = logging.getLogger()
    before_root = root.level
    before = logging.getLogger("a.child").getEffectiveLevel()
    runtime = configure(_cfg(tmp_path, io.StringIO(), file=False))
    runtime.shutdown()
    assert logging.getLogger("a.child").getEffectiveLevel() == before
    assert root.level == before_root
    assert root.handlers == []


def test_shutdown_is_idempotent_and_setup_works_again(tmp_path):
    runtime = configure(_cfg(tmp_path, io.StringIO(), file=False))
    runtime.shutdown()
    runtime.shutdown()
    runtime.close()
    again = configure(_cfg(tmp_path, io.StringIO(), file=False))
    again.shutdown()


def test_second_configure_raises_while_active(tmp_path):
    with configure(_cfg(tmp_path, io.StringIO(), file=False)):
        with pytest.raises(AlreadyConfiguredError):
            configure(_cfg(tmp_path, io.StringIO(), file=False))
    configure(_cfg(tmp_path, io.StringIO(), file=False)).shutdown()


def test_existing_root_handler_is_a_setup_error_and_rolls_back(tmp_path):
    foreign = logging.NullHandler()
    logging.getLogger().addHandler(foreign)
    with pytest.raises(SetupError):
        configure(_cfg(tmp_path, io.StringIO()))
    assert logging.getLogger().handlers == [foreign]
    assert [p for p in tmp_path.iterdir() if p.is_dir()] == []
    logging.getLogger().removeHandler(foreign)
    configure(_cfg(tmp_path, io.StringIO(), file=False)).shutdown()


def test_synchronous_has_no_listener_thread_and_background_does(tmp_path):
    import threading

    def names():
        return {t.name for t in threading.enumerate()}

    with configure(_cfg(tmp_path, io.StringIO(), file=False, synchronous=True)):
        assert "labs-logging-listener" not in names()
    with configure(_cfg(tmp_path, io.StringIO(), file=False)):
        assert "labs-logging-listener" in names()
    assert "labs-logging-listener" not in names()


def test_extra_handlers_are_flushed_not_closed(tmp_path):
    class Spy(logging.Handler):
        def __init__(self):
            super().__init__()
            self.messages = []
            self.flushed = 0
            self.closed = False

        def emit(self, record):
            self.messages.append(record.getMessage())

        def flush(self):
            self.flushed += 1

        def close(self):
            self.closed = True
            super().close()

    spy = Spy()
    runtime = configure(
        _cfg(tmp_path, io.StringIO(), console=False, file=False, extra_handlers=[spy])
    )
    logging.getLogger("lib").warning("to spy %s", 1)
    runtime.shutdown()
    assert spy.messages == ["to spy 1"]
    assert spy.flushed >= 1
    assert not spy.closed


def test_failing_handler_marks_unhealthy_without_stopping_others(tmp_path):
    class Boom(logging.Handler):
        def emit(self, record):
            raise RuntimeError("boom")

    stream = io.StringIO()
    runtime = configure(_cfg(tmp_path, stream, file=False, extra_handlers=[Boom()]))
    logging.getLogger("lib").warning("still shown")
    runtime.shutdown()
    assert "still shown" in stream.getvalue()
    assert not runtime.healthy
    assert any("boom" in error for error in runtime.errors)


def test_queue_overflow_counts_drops(tmp_path):
    import threading

    gate = threading.Event()

    class Slow(logging.Handler):
        def emit(self, record):
            gate.wait(5)

    runtime = configure(
        _cfg(
            tmp_path,
            io.StringIO(),
            console=False,
            file=False,
            queue_size=2,
            extra_handlers=[Slow()],
        )
    )
    log = logging.getLogger("lib")
    for _ in range(10):
        log.warning("x")
    drops = runtime.drops
    gate.set()
    runtime.shutdown()
    assert drops >= 1
