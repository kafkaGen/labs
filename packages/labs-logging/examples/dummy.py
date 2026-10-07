"""Runnable demo: parent/child loggers, a stdlib record, context, an exception.

Run from the repository root:
  uv run --package labs-logging python packages/labs-logging/examples/dummy.py --sync
Omit `--sync` for background dispatch. Pass `--log-dir PATH` to choose where files go
(default: the platform user log directory for `dummy`), and `--no-console` or
`--no-file` to turn a destination off.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from labs_logging import LoggingConfig, bind_context, bound_context, configure, get_logger


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sync", action="store_true", help="write in the calling thread")
    parser.add_argument("--log-dir", type=Path, default=None)
    parser.add_argument("--no-console", action="store_true")
    parser.add_argument("--no-file", action="store_true")
    args = parser.parse_args()

    config = LoggingConfig(
        app="dummy",
        family="dummy_app",
        synchronous=args.sync,
        log_dir=args.log_dir,
        console=not args.no_console,
        file=not args.no_file,
    )
    with configure(config):
        parent = get_logger("dummy_app")
        child = get_logger("dummy_app.tools")
        bind_context(session="demo-session")
        parent.info("running the demo")
        child.info("tool called", tool="add", result=3)
        with bound_context(request_id="req-42"):
            child.info("scoped call")
        logging.getLogger("third.party").warning("a stdlib message")
        try:
            raise ValueError("something broke")
        except ValueError:
            parent.exception("failed")


if __name__ == "__main__":
    main()
