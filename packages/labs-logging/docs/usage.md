# labs-logging usage

Short snippets for using `labs-logging` correctly. Reference: `README.md`.

## Rules

- Call `configure` once, in the entrypoint of the process. Nowhere else.
- Name the family after the top-level Python package, and call `get_logger(__name__)` at module level in every other module. The logger then falls under the family with nothing typed twice. Modules do not import `LoggingConfig`.
- One process, one family. Two parts of an application that run as separate processes, such as an MCP server and an agent runner, each use their own family and their own config.
- Pass data as keyword fields, not in the message: `log.info("saved", rows=3)`.
- Never print to stdout in a stdio server. The console goes to stderr.
- Call `configure` after `fork`, in the child. Never inherit a runtime.

## Setup (one place)

```python
# my_app/logging_setup.py
import logging
from labs_logging import LoggingConfig, Runtime, configure


def setup_logging() -> Runtime:
    return configure(LoggingConfig(app="my-app", family="my_app", level=logging.INFO))


# my_app/main.py
def main() -> None:
    with setup_logging():  # shutdown flushes the queue and releases the run lock
        run()
```

## Loggers in other files

```python
# my_app/tools.py
from labs_logging import get_logger

log = get_logger(__name__)  # "my_app.tools", under family "my_app". Safe at import time

log.info("tool called", tool="add", result=3)
log.warning("slow", seconds=4.2)
```

## Exceptions

```python
try:
    risky()
except ValueError:
    log.exception("risky failed", job="j-1")  # traceback goes to the `exception` field
```

## Context shared by every line

```python
from labs_logging import bind_context, bound_context, unbind_context

with bound_context(request_id="r-1"):  # once per request or tool call, at the boundary
    helper()  # its logs carry request_id, no argument passing

bind_context(session="s-1")  # no indentation, scoped to the current task or thread
unbind_context("session")

log2 = log.bind(job="j-1")  # one logger only, not global
```

Context is isolated per asyncio task and per thread. A new thread starts empty.

## Standard library and third-party logs

```python
import logging

logging.getLogger("my_app.legacy").info("captured")  # same destinations and envelope

LoggingConfig(
    app="a",
    family="a",
    level=logging.DEBUG,
    level_overrides={"httpx": logging.WARNING, "urllib3": logging.WARNING},
)
```

The root level equals `level`. Quiet noisy libraries with `level_overrides`.

## Destinations

```python
LoggingConfig(app="a", family="a", console_json=True)  # JSON lines on stderr, for collectors
LoggingConfig(app="a", family="a", file=False)  # console only
LoggingConfig(app="a", family="a", console=False)  # file only
LoggingConfig(app="a", family="a", backups=1, retain_runs=10, max_bytes=5_000_000)
```

Files: `<log_dir>/<family>/<UTC start>-<suffix>/main.jsonl`, one directory per process start.
Collectors tail `<log_dir>/<family>/*/main.jsonl`. Set `backups>=1` when one tails, because `backups=0` discards on rollover.

## Custom destination

```python
class S3Handler(logging.Handler):
    def emit(self, record): ...  # record.msg is the finished JSON envelope dict


LoggingConfig(app="a", family="a", extra_handlers=[S3Handler()])
```

`record.msg` is the envelope dict for structlog events and for standard-library and third-party records alike. Read `record.msg["event"]`, not `record.getMessage()`. The runtime flushes extra handlers on shutdown and never closes them.

## Threads

```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(8) as pool:
    list(pool.map(lambda i: log.info("work", i=i), range(100)))  # safe, no locking by you
```

Default dispatch is a bounded queue and one writer thread. Log calls do not wait on I/O.
A full queue drops the new event. Use `synchronous=True` to write in the calling thread:
nothing is dropped, but threads take turns on the handler lock and each call pays the write.

## Health

```python
with setup_logging() as rt:
    ...
    rt.healthy, rt.drops, rt.error_count, rt.errors  # destination failures and dropped events
```

## Tests

```python
# pyproject.toml: pytest's logging plugin installs root handlers and makes configure fail.
[tool.pytest.ini_options]
addopts = "-p no:logging"
```

```python
with configure(
    LoggingConfig(app="t", family="t", log_dir=tmp_path, synchronous=True, console=False)
):
    ...
```

If you cannot disable the plugin, clear root handlers in a fixture instead:

```python
@pytest.fixture(autouse=True)
def _clean_root_logger():
    root = logging.getLogger()
    saved = root.handlers[:]
    root.handlers.clear()
    yield
    root.handlers[:] = saved
```
