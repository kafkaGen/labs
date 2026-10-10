"""Caller fields named like envelope keys land under `context`, never on the envelope."""

import json
import logging

import pytest

from labs_logging import LoggingConfig, bound_context, configure, get_logger


def _events(tmp_path):
    (main,) = (tmp_path / "a").glob("*/main.jsonl")
    return [json.loads(line) for line in main.read_text("utf-8").splitlines()]


def _run(tmp_path, emit):
    config = LoggingConfig(app="a", family="a", console=False, log_dir=tmp_path, synchronous=True)
    with configure(config):
        emit()
    return _events(tmp_path)


@pytest.mark.parametrize("key", ["level", "logger", "timestamp", "exception"])
def test_structlog_reserved_kwarg_goes_to_context(tmp_path, key):
    (event,) = _run(tmp_path, lambda: get_logger("a.s").info("msg", **{key: "spoof"}))
    assert event["context"] == {key: "spoof"}
    assert event["event"] == "msg"
    assert event["level"] == "info"
    assert event["logger"] == "a.s"
    assert event["timestamp"] != "spoof"
    assert "exception" not in event


def test_structlog_real_exception_survives_spoofed_field(tmp_path):
    def emit():
        try:
            raise ValueError("real")
        except ValueError:
            get_logger("a.s").exception("failed", exception="spoof")

    (event,) = _run(tmp_path, emit)
    assert "ValueError: real" in event["exception"]
    assert event["context"] == {"exception": "spoof"}


def test_structlog_reserved_contextvar_goes_to_context(tmp_path):
    def emit():
        with bound_context(level="spoof"):
            get_logger("a.s").info("msg")

    (event,) = _run(tmp_path, emit)
    assert event["level"] == "info"
    assert event["context"] == {"level": "spoof"}


@pytest.mark.parametrize("key", ["level", "logger", "timestamp", "exception", "event"])
def test_stdlib_reserved_extra_goes_to_context(tmp_path, key):
    (event,) = _run(tmp_path, lambda: logging.getLogger("lib").warning("msg", extra={key: "spoof"}))
    assert event["context"] == {key: "spoof"}
    assert event["event"] == "msg"
    assert event["level"] == "warning"
    assert event["logger"] == "lib"
    assert event["timestamp"] != "spoof"
    assert "exception" not in event


def test_stdlib_real_exception_survives_spoofed_extra(tmp_path):
    def emit():
        try:
            raise ValueError("real")
        except ValueError:
            logging.getLogger("lib").exception("failed", extra={"exception": "spoof"})

    (event,) = _run(tmp_path, emit)
    assert "ValueError: real" in event["exception"]
    assert event["context"] == {"exception": "spoof"}
