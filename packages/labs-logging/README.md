# labs-logging

Structured logging for Python applications in the labs monorepo. It writes colorful
console output to stderr and rotating JSON Lines files, one isolated directory per run.

## Configure

Call `configure` once at startup and shut the runtime down on exit. `get_logger` and
the standard-library `logging` module both feed the same destinations.

```python
import logging

from labs_logging import LoggingConfig, bind_context, bound_context, configure, get_logger

runtime = configure(LoggingConfig(app="my-app", family="my_app"))
with runtime:
    log = get_logger("my_app.worker")
    bind_context(session="abc")
    log.info("started", jobs=3)
    with bound_context(request_id="r-1"):
        log.info("handling")
    logging.getLogger("third.party").warning("also captured")
```

`app` names the log directory and must be one safe path component. `family` is the
logger-name prefix for your application. Importing the package or calling `get_logger`
opens no files and starts no threads. `configure` raises `AlreadyConfiguredError` while
a runtime is active in the process, and `SetupError` when setup fails, for example
because the root logger already has handlers. A failed setup leaves nothing installed.
After `shutdown()` you can configure again.

Main `LoggingConfig` fields:

| Field | Default | Meaning |
|---|---|---|
| `level`, `level_overrides` | `INFO`, `{}` | Family level and per-logger levels. |
| `log_dir` | platform user log dir for `app` | Where run directories go. |
| `console`, `console_json`, `console_colors`, `console_stream` | on, off, auto, stderr | Console destination. Colors default to on only for a terminal. |
| `file` | on | File destination. |
| `synchronous` | `False` | `True` writes in the calling thread. `False` uses one listener thread and a bounded queue. |
| `queue_size` | 10,000 | Background queue capacity. A full queue drops the new event and counts it in `Runtime.drops`. |
| `max_bytes`, `backups` | 10 MiB, 0 | Size per file and rotated backups per run. |
| `retain_runs` | 5 | Newest runs kept per application. |
| `extra_handlers` | `[]` | Your own `logging.Handler` instances. The runtime flushes them on shutdown and never closes them. |

`Runtime.healthy`, `Runtime.errors`, `Runtime.error_count`, and `Runtime.drops` report
destination failures and dropped events. A failing handler marks the runtime unhealthy
and does not stop the other handlers.

## Files

Each launch creates `<log_dir>/<UTC start time>-<suffix>/` with `main.jsonl`, any
`main.jsonl.N` backups, and a `lock` file. Two processes never share a file. With
`backups=0`, reaching `max_bytes` discards the old contents and starts the same file
again. The size limit is approximate: one oversized event is written whole.

Setup and shutdown delete whole runs beyond the newest `retain_runs`, and never delete
a run whose process still holds its lock. A crashed run becomes deletable on the next
setup or shutdown.

Each line is one JSON object. Keys are written in alphabetical order (the renderer uses
`sort_keys`), at the top level and inside `context`. Do not rely on any other order.
The envelope keys are `application`, `context`, `event`, `level`, `logger`,
`process_id`, `run_id`, and `timestamp`, plus `exception` when there is one. Fields you
pass to a logger go under `context`, and a field of the same name as an envelope key
cannot overwrite it. The timestamp is ISO 8601 UTC. Structlog events end in `Z` and
standard-library records in `+00:00`.

`labs_logging.rotation.JsonFileHandler` is the file writer. Used inside a runtime, its
errors are caught and recorded in `Runtime.errors`. Used on its own, `emit` raises on a
write or format failure instead of calling `logging`'s `handleError`.

## Testing

`configure()` raises `SetupError` when the root logger already has handlers. Pytest's
logging plugin attaches some during each test, so tests that call `configure()` must
clear them first. Either disable the plugin:

```toml
[tool.pytest.ini_options]
addopts = "-p no:logging"
```

or clear the root handlers in a fixture:

```python
import logging

import pytest


@pytest.fixture(autouse=True)
def _clean_root_logger():
    root = logging.getLogger()
    saved = root.handlers[:]
    root.handlers.clear()
    yield
    root.handlers[:] = saved
```

Point `log_dir` at `tmp_path` so tests never touch the real log directory.

## Event values

Values passed to the logger are copied into JSON-safe data when you call it, so later
mutation cannot change a queued event. Tuples and sets become lists, and set order is
iteration order. Cycles become `"<cycle>"`. Unsupported types become a string such as
`"Decimal: Decimal('1.5')"`, or just the type name when `repr` fails. Non-finite floats
become strings. Dict keys become strings, and keys that collide after conversion
overwrite each other. The console shows these same normalized strings, not the
original objects, so a `Decimal` appears as `Decimal: Decimal('1.5')` there too.

Standard-library messages are formatted, and tracebacks rendered, in the calling thread.
Tracebacks carry no frame locals.

`Runtime.errors` keeps the first 100 destination errors plus a count of the rest.
`Runtime.error_count` has the total. Copying costs time per call, so avoid passing very
large objects as fields. Logging is not a place for secrets: nothing is redacted.

## Example

`examples/dummy.py` emits parent and child events, a standard-library record, scoped
context, and an exception. From the repository root:

```sh
uv run --package labs-logging python packages/labs-logging/examples/dummy.py --sync
```

Omit `--sync` for background dispatch. `--log-dir PATH`, `--no-console`, and
`--no-file` choose the destinations.
