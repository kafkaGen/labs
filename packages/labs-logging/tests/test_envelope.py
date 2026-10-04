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
