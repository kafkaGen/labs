import logging

import pytest
import structlog


@pytest.fixture(autouse=True)
def _clean_logging_state():
    structlog.contextvars.clear_contextvars()
    yield
    structlog.contextvars.clear_contextvars()
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
