import asyncio
import json
import logging
import threading

import pytest

from labs_logging import LoggingConfig, bind_context, configure, get_logger


def _events(tmp_path):
    run = next(p for p in (tmp_path / "a").iterdir() if p.is_dir() and p.name != ".coord")
    return [json.loads(line) for line in (run / "main.jsonl").read_text().splitlines()]


class _BoomHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        raise RuntimeError("disk full")


@pytest.mark.parametrize("synchronous", [True, False])
def test_unsafe_values_are_normalized(tmp_path, synchronous):
    class Odd:
        def __repr__(self):
            return "<odd>"

    class Hostile:
        def __repr__(self):
            raise RuntimeError("no repr")

    cycle: dict = {"name": "loop"}
    cycle["self"] = cycle
    runtime = configure(
        LoggingConfig(app="a", family="a", console=False, synchronous=synchronous, log_dir=tmp_path)
    )
    try:
        get_logger("a").info("e", cycle=cycle, odd=Odd(), hostile=Hostile(), raw=b"by", s={1, 2})
    finally:
        runtime.shutdown()
    assert runtime.healthy, runtime.errors
    ctx = _events(tmp_path)[0]["context"]
    assert ctx["cycle"]["name"] == "loop"
    assert ctx["cycle"]["self"] == "<cycle>"
    assert "odd" in ctx["odd"].lower()
    assert ctx["hostile"] == "Hostile"
    assert isinstance(ctx["raw"], str)
    assert sorted(ctx["s"]) == [1, 2]


def test_mutation_after_call_does_not_change_event(tmp_path):
    runtime = configure(
        LoggingConfig(app="a", family="a", console=False, synchronous=False, log_dir=tmp_path)
    )
    items = [1, 2]
    nested = {"k": [1]}
    try:
        # A slow first event keeps later ones queued while the producer mutates.
        get_logger("a").info("e", items=items, nested=nested)
        items.append(3)
        nested["k"].append(2)
    finally:
        runtime.shutdown()
    ctx = _events(tmp_path)[0]["context"]
    assert ctx["items"] == [1, 2]
    assert ctx["nested"] == {"k": [1]}


def test_mutation_is_snapshotted_before_listener_runs(tmp_path):
    gate = threading.Event()

    class _Gate(logging.Handler):
        def emit(self, record):
            gate.wait(5)

    runtime = configure(
        LoggingConfig(
            app="a",
            family="a",
            console=False,
            synchronous=False,
            extra_handlers=[_Gate()],
            log_dir=tmp_path,
        )
    )
    items = [1]
    try:
        get_logger("a").info("first")
        get_logger("a").info("second", items=items)
        items.append(2)
        gate.set()
    finally:
        runtime.shutdown()
    second = [e for e in _events(tmp_path) if e["event"] == "second"][0]
    assert second["context"]["items"] == [1]


def test_stdlib_extra_values_are_normalized(tmp_path):
    cycle: list = []
    cycle.append(cycle)
    runtime = configure(LoggingConfig(app="a", family="a", console=False, log_dir=tmp_path))
    try:
        logging.getLogger("a.std").info("std", extra={"cyc": cycle})
    finally:
        runtime.shutdown()
    assert runtime.healthy, runtime.errors
    assert _events(tmp_path)[0]["context"]["cyc"] == ["<cycle>"]


def test_async_context_is_task_local(tmp_path):
    runtime = configure(LoggingConfig(app="a", family="a", console=False, log_dir=tmp_path))

    async def worker(rid):
        bind_context(request_id=rid)
        await asyncio.sleep(0)
        get_logger("a.w").info("do", rid=rid)
        logging.getLogger("a.std").info("std %s", rid)

    async def run():
        await asyncio.gather(worker("r1"), worker("r2"))

    try:
        asyncio.run(run())
    finally:
        runtime.shutdown()
    for event in _events(tmp_path):
        expected = event["context"].get("rid")
        if expected is None:
            expected = event["event"].split()[-1]
        assert event["context"]["request_id"] == expected
    assert len(_events(tmp_path)) == 4


def test_thread_context_is_isolated(tmp_path):
    runtime = configure(LoggingConfig(app="a", family="a", console=False, log_dir=tmp_path))

    def work(tag):
        bind_context(who=tag)
        get_logger("a.t").info("t", tag=tag)

    try:
        bind_context(who="main")
        threads = [threading.Thread(target=work, args=(f"t{i}",)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        get_logger("a").info("main-done")
    finally:
        runtime.shutdown()
    for event in _events(tmp_path):
        if "tag" in event["context"]:
            assert event["context"]["who"] == event["context"]["tag"]
    main = [e for e in _events(tmp_path) if e["event"] == "main-done"][0]
    assert main["context"]["who"] == "main"
    assert {e["context"]["who"] for e in _events(tmp_path)} == {"main", "t0", "t1", "t2"}


def test_runtime_errors_are_bounded(tmp_path):
    runtime = configure(
        LoggingConfig(
            app="a",
            family="a",
            console=False,
            file=False,
            extra_handlers=[_BoomHandler()],
            log_dir=tmp_path,
        )
    )
    try:
        for i in range(500):
            get_logger("a").info("e%d", i)
    finally:
        runtime.shutdown()
    assert not runtime.healthy
    assert len(runtime.errors) == 101
    assert "400 more" in runtime.errors[-1]
    assert runtime.error_count == 500


def test_stdlib_exception_args_formatted_in_producer(tmp_path):
    gate = threading.Event()

    class _Gate(logging.Handler):
        def emit(self, record):
            gate.wait(5)

    class Mutable:
        value = "before"

        def __str__(self):
            return self.value

    obj = Mutable()
    runtime = configure(
        LoggingConfig(
            app="a",
            family="a",
            console=False,
            synchronous=False,
            extra_handlers=[_Gate()],
            log_dir=tmp_path,
        )
    )
    try:
        logging.getLogger("a.std").info("first")
        logging.getLogger("a.std").info("value=%s", obj)
        Mutable.value = "after"
        gate.set()
    finally:
        runtime.shutdown()
        Mutable.value = "before"
    event = [e for e in _events(tmp_path) if e["event"].startswith("value=")][0]
    assert event["event"] == "value=before"


def test_stdlib_exception_text_is_captured_in_producer(tmp_path):
    runtime = configure(
        LoggingConfig(app="a", family="a", console=False, synchronous=False, log_dir=tmp_path)
    )
    try:
        try:
            raise ValueError("kaboom")
        except ValueError:
            logging.getLogger("a.std").exception("failed")
    finally:
        runtime.shutdown()
    event = _events(tmp_path)[0]
    assert "ValueError: kaboom" in event["exception"]
    assert "labs_exception" not in event["context"]
