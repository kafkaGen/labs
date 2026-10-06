import logging
import sys

import structlog

from labs_logging.envelope import (
    EnvelopeBuilder,
    foreign_pre_chain,
    producer_processors,
    renderer_for,
)


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
    assert isinstance(console, structlog.dev.ConsoleRenderer)
    assert isinstance(json_renderer, structlog.processors.JSONRenderer)


def _run_foreign(builder, record, event="msg"):
    event_dict = {"_record": record, "event": event}
    for key in ("exc_info", "stack_info"):
        value = getattr(record, key, None)
        if value:
            event_dict[key] = value
    for processor in foreign_pre_chain(builder):
        event_dict = processor(None, None, event_dict)
    return event_dict


def _exc_info():
    try:
        raise ValueError("bad")
    except ValueError:
        return sys.exc_info()


def test_exception_matches_on_structlog_and_stdlib_paths():
    builder = _builder()
    exc_info = _exc_info()
    structlog_out = {"event": "e", "level": "error", "logger": "l", "exc_info": exc_info}
    for processor in producer_processors(builder)[:-1]:
        structlog_out = processor(logging.getLogger("l"), "error", structlog_out)
    record = logging.LogRecord("lib", logging.ERROR, "", 0, "e", (), exc_info)
    record.stack_info = "stack"
    foreign_out = _run_foreign(builder, record, "e")
    assert "ValueError: bad" in structlog_out["exception"]
    assert foreign_out["exception"] == structlog_out["exception"]
    for out in (structlog_out, foreign_out):
        assert not {"exc_info", "stack_info", "exception"} & set(out["context"])


def test_producer_chain_builds_before_wrapping():
    chain = producer_processors(_builder())
    names = [getattr(p, "__name__", None) for p in chain]
    assert names.index("build") == len(chain) - 2
    assert chain[-1] is structlog.stdlib.ProcessorFormatter.wrap_for_formatter


def test_foreign_record_without_labs_attributes_keeps_builder_runtime():
    record = logging.LogRecord("lib", logging.INFO, "", 0, "hi", (), None)
    out = _run_foreign(_builder(), record, "hi")
    assert (out["application"], out["run_id"], out["process_id"]) == ("app", "run1", "42")
    assert out["timestamp"] is None


def test_caller_fields_do_not_overwrite_runtime_fields():
    event = {
        "event": "e",
        "level": "i",
        "logger": "l",
        "timestamp": "t",
        "application": "evil",
        "run_id": "r",
        "process_id": "p",
    }
    out = _builder().build(None, "info", event)
    assert (out["application"], out["run_id"], out["process_id"]) == ("app", "run1", "42")
    assert out["context"] == {"application": "evil", "run_id": "r", "process_id": "p"}


def test_foreign_extra_does_not_overwrite_runtime_fields():
    record = logging.LogRecord("lib", logging.INFO, "", 0, "hi", (), None)
    record.application = "evil"
    out = _run_foreign(_builder(), record, "hi")
    assert out["application"] == "app"
    assert out["context"]["application"] == "evil"
