import logging

import pytest

from labs_logging import LoggingConfig, configure, get_logger
from labs_logging.envelope import EnvelopeBuilder, foreign_pre_chain


class _Collect(logging.Handler):
    def __init__(self):
        super().__init__()
        self.msgs = []

    def emit(self, record):
        self.msgs.append(record.msg)


@pytest.mark.parametrize("synchronous", [True, False])
def test_extra_handler_gets_envelope_for_both_event_kinds(tmp_path, synchronous):
    sink = _Collect()
    runtime = configure(
        LoggingConfig(
            app="a",
            family="a",
            console=False,
            file=False,
            synchronous=synchronous,
            log_dir=tmp_path,
            extra_handlers=[sink],
        )
    )
    try:
        get_logger("a.t").info("from structlog", k=1)
        logging.getLogger("third.party").warning("from stdlib %s", "x", extra={"n": 2})
    finally:
        runtime.shutdown()

    structlog_env, stdlib_env = sink.msgs
    for env, event in ((structlog_env, "from structlog"), (stdlib_env, "from stdlib x")):
        assert isinstance(env, dict)
        assert env["event"] == event
        assert env["application"] == "a"
        assert env["timestamp"].endswith("Z")
    assert structlog_env["context"] == {"k": 1}
    assert stdlib_env["context"] == {"n": 2}
    assert stdlib_env["logger"] == "third.party"
    assert stdlib_env["level"] == "warning"


def test_extra_handler_envelope_carries_foreign_exception(tmp_path):
    sink = _Collect()
    runtime = configure(
        LoggingConfig(
            app="a",
            family="a",
            console=False,
            file=False,
            synchronous=True,
            log_dir=tmp_path,
            extra_handlers=[sink],
        )
    )
    try:
        try:
            raise ValueError("boom")
        except ValueError:
            logging.getLogger("third.party").exception("failed")
    finally:
        runtime.shutdown()
    assert "ValueError: boom" in sink.msgs[0]["exception"]


def test_exception_outside_handler_does_not_lose_event(tmp_path):
    # logging.exception() with no active exception sets exc_info=(None, None, None).
    sink = _Collect()
    runtime = configure(
        LoggingConfig(
            app="a",
            family="a",
            console=False,
            synchronous=True,
            log_dir=tmp_path,
            extra_handlers=[sink],
        )
    )
    try:
        logging.getLogger("third.party").exception("no active exception")
        assert runtime.healthy
    finally:
        runtime.shutdown()
    assert sink.msgs[0]["event"] == "no active exception"
    assert "exception" not in sink.msgs[0]
    assert "no active exception" in (next((tmp_path / "a").glob("*/main.jsonl"))).read_text()


def test_foreign_chain_survives_empty_exc_info_without_the_filter():
    builder = EnvelopeBuilder(application="a", run_id="r", process_id="1")
    record = logging.LogRecord("x", logging.ERROR, __file__, 1, "msg", (), (None, None, None))
    ed = {"event": "msg", "_record": record, "exc_info": record.exc_info}
    for proc in foreign_pre_chain(builder):
        ed = proc(None, "error", ed)
    assert not ed.get("exception")
