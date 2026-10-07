"""Cross-process behavior: separate files, active-run exclusion, concurrent startup."""

import json
import subprocess
import sys
import time
from pathlib import Path

from labs_logging import LoggingConfig, configure

CHILD = Path(__file__).with_name("child_process.py")
DEADLINE = 30.0


def _spawn(log_dir, sync_dir, name, retain, *, hold=False):
    if hold:
        (sync_dir / f"hold-{name}").touch()
    return subprocess.Popen(
        [sys.executable, str(CHILD), str(log_dir), str(sync_dir), name, str(retain)],
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_ready(sync_dir, names):
    end = time.monotonic() + DEADLINE
    while not all((sync_dir / f"ready-{n}").exists() for n in names):
        assert time.monotonic() < end, f"children not ready: {names}"
        time.sleep(0.005)


def _finish(procs):
    for proc in procs:
        _, err = proc.communicate(timeout=DEADLINE)
        assert proc.returncode == 0, err


def _runs(log_dir):
    return sorted(p for p in log_dir.iterdir() if p.is_dir())


def _records(run):
    return [json.loads(line) for line in (run / "main.jsonl").read_text().splitlines()]


def test_two_processes_write_separate_files(tmp_path):
    log_dir, sync = tmp_path / "logs", tmp_path / "sync"
    sync.mkdir()
    procs = [_spawn(log_dir, sync, n, 10, hold=True) for n in ("one", "two")]
    (sync / "go").touch()
    _wait_ready(sync, ("one", "two"))
    # Both runs are open at once, so the files cannot have been shared in turn.
    runs = _runs(log_dir)
    assert len(runs) == 2
    (sync / "release").touch()
    _finish(procs)
    seen = set()
    for run in runs:
        (record,) = _records(run)
        assert record["event"] == "hello"
        assert record["run_id"] == run.name
        seen.add((record["context"]["child"], record["process_id"]))
    assert {child for child, _ in seen} == {"one", "two"}
    assert len({pid for _, pid in seen}) == 2


def test_running_process_survives_another_process_cleanup(tmp_path):
    log_dir, sync = tmp_path / "logs", tmp_path / "sync"
    sync.mkdir()
    holder = _spawn(log_dir, sync, "holder", 1, hold=True)
    (sync / "go").touch()
    _wait_ready(sync, ("holder",))
    (held,) = _runs(log_dir)
    # Newer runs from other processes, each cleaning up with retain_runs=1.
    for i in range(3):
        _finish([_spawn(log_dir, sync, f"other{i}", 1)])
    assert held.exists()
    assert len(_records(held)) == 1
    (sync / "release").touch()
    _finish([holder])
    # Once the holder has exited its run is inactive and the next cleanup removes it.
    configure(
        LoggingConfig(app="a", family="a", console=False, log_dir=log_dir, retain_runs=1)
    ).shutdown()
    assert not held.exists()
    assert len(_runs(log_dir)) == 1


def test_concurrent_startup_gives_each_process_its_own_run(tmp_path):
    log_dir, sync = tmp_path / "logs", tmp_path / "sync"
    sync.mkdir()
    names = [f"p{i}" for i in range(6)]
    procs = [_spawn(log_dir, sync, n, 3, hold=True) for n in names]
    (sync / "go").touch()  # every child is already waiting, so they start together
    _wait_ready(sync, names)
    # All six are active, so retention of three must not delete any of them.
    runs = _runs(log_dir)
    assert len(runs) == 6
    assert len({r.name for r in runs}) == 6
    assert sorted(_records(r)[0]["context"]["child"] for r in runs) == names
    (sync / "release").touch()
    _finish(procs)
    # A later cleanup sees every run inactive and keeps the newest three, itself included.
    configure(
        LoggingConfig(app="a", family="a", console=False, log_dir=log_dir, retain_runs=3)
    ).shutdown()
    kept = _runs(log_dir)
    assert len(kept) == 3
    assert [r.name for r in kept[:2]] == [r.name for r in runs[-2:]]
