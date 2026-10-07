"""Child process for the multiprocess tests. Run as a script, never imported.

Usage: child_process.py LOG_DIR SYNC_DIR NAME RETAIN_RUNS

It waits for `SYNC_DIR/go`, configures logging in this process, logs one event,
announces `SYNC_DIR/ready-NAME`, and (when `SYNC_DIR/hold-NAME` exists) keeps the
run open until `SYNC_DIR/release` appears. Files, not sleeps, order the processes.
"""

import sys
import time
from pathlib import Path

from labs_logging import LoggingConfig, configure, get_logger

DEADLINE = 30.0


def wait_for(path: Path) -> None:
    end = time.monotonic() + DEADLINE
    while not path.exists():
        if time.monotonic() > end:
            sys.exit(f"timed out waiting for {path}")
        time.sleep(0.005)


def main() -> None:
    log_dir, sync_dir, name, retain = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
    wait_for(sync_dir / "go")
    config = LoggingConfig(
        app="a", family="a", console=False, log_dir=log_dir, retain_runs=int(retain)
    )
    with configure(config):
        get_logger("a.child").info("hello", child=name)
        (sync_dir / f"ready-{name}").touch()
        if (sync_dir / f"hold-{name}").exists():
            wait_for(sync_dir / "release")


if __name__ == "__main__":
    main()
