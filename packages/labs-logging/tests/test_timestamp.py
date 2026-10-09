import json
import logging
import re

import pytest

from labs_logging import LoggingConfig, configure, get_logger

# UTC ISO 8601 with microseconds and a literal Z.
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z")


@pytest.mark.parametrize("synchronous", [True, False])
def test_both_paths_share_one_timestamp_format(tmp_path, synchronous):
    config = LoggingConfig(
        app="a", family="a", console=False, log_dir=tmp_path, synchronous=synchronous
    )
    with configure(config):
        # Repeat so a zero-microsecond instant (isoformat drops it) is likely to appear.
        for _ in range(50):
            get_logger("a.s").info("structured")
            logging.getLogger("lib").info("foreign")
    (main,) = tmp_path.glob("*/main.jsonl")
    events = [json.loads(line) for line in main.read_text("utf-8").splitlines()]
    assert len(events) == 100
    assert all(TIMESTAMP.fullmatch(e["timestamp"]) for e in events)
