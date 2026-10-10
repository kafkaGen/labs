import datetime
from pathlib import Path

import pytest
from platformdirs import user_log_dir

from labs_logging.config import LoggingConfig
from labs_logging.dirs import RunDir, new_run_name, resolve_log_dir


def test_explicit_log_dir_gets_the_family_appended(tmp_path):
    config = LoggingConfig(app="a", family="fam", log_dir=tmp_path)
    assert resolve_log_dir(config) == tmp_path / "fam"


def test_default_log_dir_ends_with_the_family():
    path = resolve_log_dir(LoggingConfig(app="a", family="fam"))
    assert path == Path(user_log_dir("a")) / "fam"


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


def test_run_dir_create_retries_on_collision(tmp_path, monkeypatch):
    now = datetime.datetime.now(datetime.timezone.utc)
    (tmp_path / "collision").mkdir()
    names = iter(("collision", "fresh"))
    monkeypatch.setattr("labs_logging.dirs.new_run_name", lambda _now: next(names))

    run = RunDir.create(tmp_path, now)

    assert run.path.name == "fresh"
    assert run.path.is_dir()


def test_run_dir_create_raises_after_all_collisions(tmp_path, monkeypatch):
    now = datetime.datetime.now(datetime.timezone.utc)
    (tmp_path / "same").mkdir()
    monkeypatch.setattr("labs_logging.dirs.new_run_name", lambda _now: "same")

    with pytest.raises(FileExistsError):
        RunDir.create(tmp_path, now)
