import io
import json
import logging
from datetime import datetime, timedelta

import pytest

from labs_logging import LoggingConfig, configure, get_logger

ENVELOPE_KEYS = {
    "timestamp",
    "level",
    "logger",
    "application",
    "run_id",
    "process_id",
    "event",
    "context",
}


def _main(tmp_path):
    (main,) = tmp_path.glob("*/main.jsonl")
    return main


def _read(tmp_path):
    return [json.loads(line) for line in _main(tmp_path).read_text("utf-8").splitlines()]


def test_file_receives_json_lines(tmp_path):
    config = LoggingConfig(app="a", family="a", console=False, log_dir=tmp_path)
    runtime = configure(config)
    try:
        get_logger("a.child").info("hello", request_id=7)
        logging.getLogger("lib").error("oops")
    finally:
        runtime.shutdown()
    assert "\x1b[" not in _main(tmp_path).read_text("utf-8")
    first, second = _read(tmp_path)
    assert first["event"] == "hello"
    assert first["context"]["request_id"] == 7
    assert first["application"] == "a"
    assert first["logger"] == "a.child"
    assert second["logger"] == "lib"
    assert second["event"] == "oops"
    assert second["application"] == "a"


@pytest.mark.parametrize("synchronous", [True, False])
def test_envelope_fields_for_both_event_kinds(tmp_path, synchronous):
    config = LoggingConfig(
        app="a", family="a", console=False, log_dir=tmp_path, synchronous=synchronous
    )
    runtime = configure(config)
    try:
        get_logger("a.s").info("structured", n=1)
        logging.getLogger("lib").warning("foreign %s", "x", extra={"k": 2})
    finally:
        runtime.shutdown()
    events = _read(tmp_path)
    assert len(events) == 2
    for event in events:
        assert set(event) == ENVELOPE_KEYS
        assert datetime.fromisoformat(event["timestamp"]).utcoffset() == timedelta(0)
        assert event["run_id"] == _main(tmp_path).parent.name
        assert event["process_id"].isdigit()
        assert event["application"] == "a"
    assert events[0]["level"] == "info"
    assert events[0]["context"] == {"n": 1}
    assert events[1]["level"] == "warning"
    assert events[1]["event"] == "foreign x"
    assert events[1]["context"] == {"k": 2}


@pytest.mark.parametrize("kind", ["structlog", "stdlib"])
def test_exception_is_single_field_not_context(tmp_path, kind):
    config = LoggingConfig(app="a", family="a", console=False, log_dir=tmp_path, synchronous=True)
    runtime = configure(config)
    try:
        try:
            raise ValueError("boom")
        except ValueError:
            if kind == "structlog":
                get_logger("a.e").error("failed", exc_info=True)
            else:
                logging.getLogger("lib").exception("failed")
    finally:
        runtime.shutdown()
    text = _main(tmp_path).read_text("utf-8")
    assert len(text.splitlines()) == 1
    (event,) = _read(tmp_path)
    assert "ValueError: boom" in event["exception"]
    assert "exc_info" not in event["context"]
    assert "exception" not in event["context"]


@pytest.mark.parametrize("synchronous", [True, False])
def test_file_failure_marks_unhealthy_and_console_keeps_working(tmp_path, synchronous):
    stream = io.StringIO()
    config = LoggingConfig(
        app="a", family="a", console_stream=stream, log_dir=tmp_path, synchronous=synchronous
    )
    runtime = configure(config)
    try:
        assert runtime.healthy
        # A directory in the file's place makes every write fail.
        (next(tmp_path.glob("*/lock")).parent / "main.jsonl").mkdir()
        get_logger("a.x").info("still-visible")
        logging.getLogger("lib").info("also-visible")
    finally:
        runtime.shutdown()
    assert not runtime.healthy
    assert any("JsonFileHandler" in e for e in runtime.errors)
    assert "still-visible" in stream.getvalue()
    assert "also-visible" in stream.getvalue()
