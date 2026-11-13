"""Captures `labs-logging` output for tests through the real pipeline, context included."""

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from labs_logging import LoggingConfig, configure


class CapturedLogs:
    """Reads back what a test logged, as the JSON records `labs-logging` writes.

    Records are typed `Any`, not `object`: they are parsed JSON that assertions index freely.
    """

    def __init__(self, log_dir: Path) -> None:
        self._log_dir = log_dir

    def records(self) -> list[dict[str, Any]]:
        lines = []
        for path in sorted(self._log_dir.rglob("main.jsonl")):
            lines += path.read_text().splitlines()
        return [json.loads(line) for line in lines if line]

    def events(self, name: str) -> list[dict[str, Any]]:
        """Records whose event is `name`, with their context fields at the top level."""
        found = []
        for record in self.records():
            if record["event"] != name:
                continue
            context = record.get("context")
            fields = dict(context) if isinstance(context, dict) else {}
            found.append({**fields, "event": record["event"], "level": record["level"]})
        return found


@pytest.fixture
def logs(tmp_path: Path) -> Iterator[CapturedLogs]:
    root = logging.getLogger()
    saved = root.handlers[:]
    root.handlers.clear()  # pytest's handlers would make `configure` refuse to start
    config = LoggingConfig(
        app="weather-agents-test",
        family="weather_agents",
        log_dir=tmp_path / "logs",
        synchronous=True,
        console=False,
        level=logging.DEBUG,
    )
    try:
        with configure(config):
            yield CapturedLogs(tmp_path / "logs")
    finally:
        root.handlers[:] = saved
