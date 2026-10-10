import logging

import pytest
from pydantic import ValidationError

from labs_logging.config import LoggingConfig


def test_defaults():
    cfg = LoggingConfig(app="my-app", family="my_app")
    assert cfg.level == logging.INFO
    assert cfg.level_overrides == {}
    assert cfg.log_dir is None
    assert cfg.console is True
    assert cfg.console_json is False
    assert cfg.file is True
    assert cfg.synchronous is False
    assert cfg.queue_size == 10_000
    assert cfg.max_bytes == 10 * 1024 * 1024
    assert cfg.backups == 3
    assert cfg.retain_runs == 5
    assert cfg.extra_handlers == []


def test_app_name_rejects_paths():
    with pytest.raises(ValidationError):
        LoggingConfig(app="a/b", family="x")
    with pytest.raises(ValidationError):
        LoggingConfig(app="..", family="x")


def test_nonnegative_limits():
    with pytest.raises(ValidationError):
        LoggingConfig(app="a", family="x", queue_size=0)
    with pytest.raises(ValidationError):
        LoggingConfig(app="a", family="x", backups=-1)


def test_extra_handlers_must_be_logging_handlers():
    handler = logging.NullHandler()
    assert LoggingConfig(app="a", family="a", extra_handlers=[handler]).extra_handlers == [handler]
    with pytest.raises(ValidationError):
        LoggingConfig(app="a", family="a", extra_handlers=["not a handler"])
