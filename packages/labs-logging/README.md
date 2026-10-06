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
