# labs-logging

Structured logging for Python applications in the labs monorepo. Colorful console
output on stderr and rotating JSON Lines files, one isolated file per run.

## Configure

```python
from labs_logging import LoggingConfig, configure, get_logger

runtime = configure(LoggingConfig(app="my-app", family="my_app"))
log = get_logger("my_app.worker")
with runtime:
    log.info("started")
```
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

## Event values

Values passed to the logger are copied into JSON-safe data when you call it, so later
mutation cannot change a queued event. Cycles become `"<cycle>"`, and unsupported
types become a string such as `"Decimal: Decimal('1.5')"`. Standard-library
messages are formatted, and tracebacks rendered, in the calling thread too.

`Runtime.errors` keeps the first 100 destination errors plus a count of the rest.
`Runtime.error_count` has the total. Copying costs time per call, so avoid passing
very large objects as fields.
