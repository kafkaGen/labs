import datetime

import pytest

from labs_logging.config import LoggingConfig
from labs_logging.dirs import RunDir, new_run_name, resolve_log_dir


def test_explicit_log_dir_wins(tmp_path):
    assert resolve_log_dir(LoggingConfig(app="a", family="a", log_dir=tmp_path)) == tmp_path


def test_new_run_name_is_fs_safe_and_sortable():
    now = datetime.datetime(2026, 10, 4, 21, 0, 0, 123456, tzinfo=datetime.timezone.utc)
    name = new_run_name(now)
    assert " " not in name and ":" not in name
    assert name.startswith("2026-10-04T21-00-00.123456Z-")
    assert len(name.rsplit("-", 1)[1]) == 6


def test_run_dir_create_creates_once(tmp_path):
    now = datetime.datetime.now(datetime.timezone.utc)
    run = RunDir.create(tmp_path, now)
    assert run.path.is_dir()
    assert run.main_path.parent == run.path
    assert run.lock_path.name == "lock"
    with pytest.raises(FileExistsError):
        run.path.mkdir()
