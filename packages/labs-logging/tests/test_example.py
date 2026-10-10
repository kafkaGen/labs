import json
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).parent.parent / "examples"


@pytest.mark.parametrize("flags", [["--sync"], []])
def test_dummy_app_runs_in_both_dispatch_modes(tmp_path, flags):
    result = subprocess.run(
        [sys.executable, "-m", "dummy_app", "--log-dir", str(tmp_path), *flags],
        capture_output=True,
        text=True,
        check=False,
        cwd=EXAMPLES,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "Warning" not in result.stderr
    (main,) = (tmp_path / "dummy_app").glob("*/main.jsonl")
    events = [json.loads(line) for line in main.read_text().splitlines()]
    assert [e["event"] for e in events] == [
        "running the demo",
        "tool called",
        "scoped call",
        "a stdlib message",
        "failed",
    ]
    assert events[2]["context"]["request_id"] == "req-42"
    assert "ValueError: something broke" in events[4]["exception"]
