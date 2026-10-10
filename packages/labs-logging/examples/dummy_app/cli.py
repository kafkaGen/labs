"""Runnable demo: a family of loggers, a stdlib record, context, an exception.

Run from the repository root:
  cd packages/labs-logging/examples && uv run --package labs-logging python -m dummy_app --sync
Omit `--sync` for background dispatch. Pass `--log-dir PATH` to choose where files go
(default: the platform user log directory for `dummy`), and `--no-console` or
`--no-file` to turn a destination off.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from labs_logging import LoggingConfig, bind_context, bound_context, configure, get_logger

from dummy_app import tools

# The family is the package name, so every `get_logger(__name__)` in the package
# falls under it with nothing typed twice.
FAMILY = __package__ or "dummy_app"

log = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sync", action="store_true", help="write in the calling thread")
    parser.add_argument("--log-dir", type=Path, default=None)
    parser.add_argument("--no-console", action="store_true")
    parser.add_argument("--no-file", action="store_true")
    args = parser.parse_args()

    config = LoggingConfig(
        app="dummy",
        family=FAMILY,
        synchronous=args.sync,
        log_dir=args.log_dir,
        console=not args.no_console,
        file=not args.no_file,
    )
    with configure(config):
        bind_context(session="demo-session")
        log.info("running the demo")
        tools.add(1, 2)
        with bound_context(request_id="req-42"):
            log.info("scoped call")
        logging.getLogger("third.party").warning("a stdlib message")
        try:
            raise ValueError("something broke")
        except ValueError:
            log.exception("failed")
