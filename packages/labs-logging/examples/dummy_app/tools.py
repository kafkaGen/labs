"""A module that logs without importing any logging config."""

from labs_logging import get_logger

# `__name__` is "dummy_app.tools": the family prefix comes from the package name.
log = get_logger(__name__)


def add(a: int, b: int) -> int:
    result = a + b
    log.info("tool called", tool="add", result=result)
    return result
