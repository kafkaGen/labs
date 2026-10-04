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