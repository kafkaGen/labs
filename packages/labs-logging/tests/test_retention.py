import datetime

from labs_logging import LoggingConfig, configure
from labs_logging import runtime as runtime_mod
from labs_logging.dirs import RunDir
from labs_logging.lock import FileLock
from labs_logging.runtime import cleanup_runs

BASE = datetime.datetime(2026, 10, 4, 12, 0, 0, tzinfo=datetime.UTC)


def _make_run(root, index, backups=0):
    run = RunDir.create(root, BASE.replace(microsecond=index * 1000))
    run.main_path.write_text("x")
    run.lock_path.write_text("")
    for n in range(1, backups + 1):
        (run.path / f"main.jsonl.{n}").write_text("old")
    return run


def _names(root):
    return {p.name for p in root.iterdir()}


def test_keeps_newest_five(tmp_path):
    runs = [_make_run(tmp_path, i) for i in range(8)]
    cleanup_runs(tmp_path, retain=5, active_name="none")
    assert _names(tmp_path) == {r.name for r in runs[3:]}


def test_backups_are_not_counted_as_runs_and_go_with_their_run(tmp_path):
    runs = [_make_run(tmp_path, i, backups=3) for i in range(7)]
    cleanup_runs(tmp_path, retain=5, active_name="none")
    assert _names(tmp_path) == {r.name for r in runs[2:]}
    for run in runs[2:]:
        assert len(list(run.path.iterdir())) == 5  # main, 3 backups, lock
    for run in runs[:2]:
        assert not run.path.exists()


def test_fewer_runs_than_retain_deletes_nothing(tmp_path):
    runs = [_make_run(tmp_path, i) for i in range(3)]
    cleanup_runs(tmp_path, retain=5, active_name="none")
    assert _names(tmp_path) == {r.name for r in runs}


def test_active_old_run_survives(tmp_path):
    runs = [_make_run(tmp_path, i, backups=1) for i in range(8)]
    oldest = runs[0]
    lock = FileLock(oldest.lock_path)
    assert lock.try_acquire()
    try:
        cleanup_runs(tmp_path, retain=5, active_name="none")
    finally:
        lock.release()
    # Newest five, plus the older run that is still held.
    assert _names(tmp_path) == {oldest.name, *(r.name for r in runs[3:])}
    assert sorted(p.name for p in oldest.path.iterdir()) == ["lock", "main.jsonl", "main.jsonl.1"]


def test_run_is_deletable_once_its_lock_is_released(tmp_path):
    runs = [_make_run(tmp_path, i) for i in range(7)]
    lock = FileLock(runs[0].lock_path)
    assert lock.try_acquire()
    cleanup_runs(tmp_path, retain=5, active_name="none")
    assert runs[0].path.exists()
    lock.release()
    cleanup_runs(tmp_path, retain=5, active_name="none")
    assert not runs[0].path.exists()
    assert not runs[1].path.exists()


def test_active_name_always_skipped(tmp_path):
    runs = [_make_run(tmp_path, i) for i in range(8)]
    current = runs[2]  # inside the deletion window
    cleanup_runs(tmp_path, retain=5, active_name=current.name)
    assert current.name in _names(tmp_path)
    assert runs[0].name not in _names(tmp_path)
    assert runs[1].name not in _names(tmp_path)


def test_unrelated_entries_are_left_alone(tmp_path):
    runs = [_make_run(tmp_path, i) for i in range(7)]
    (tmp_path / "notes.txt").write_text("keep")
    (tmp_path / "not-a-run").mkdir()
    (tmp_path / "not-a-run" / "f").write_text("keep")
    cleanup_runs(tmp_path, retain=5, active_name="none")
    assert "notes.txt" in _names(tmp_path)
    assert (tmp_path / "not-a-run" / "f").read_text() == "keep"
    assert not runs[0].path.exists()


def test_directory_with_a_lock_but_not_a_run_name_is_left_alone(tmp_path):
    runs = [_make_run(tmp_path, i) for i in range(7)]
    lookalike = tmp_path / "0000-lookalike"
    lookalike.mkdir()
    (lookalike / "lock").write_text("")
    (lookalike / "keep").write_text("keep")
    cleanup_runs(tmp_path, retain=5, active_name="none")
    assert (lookalike / "keep").read_text() == "keep"
    assert not runs[0].path.exists()


def test_symlinked_run_dir_is_not_followed(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "lock").write_text("")
    (outside / "precious").write_text("keep")
    root = tmp_path / "root"
    root.mkdir()
    # Sorts before every real run, so retention would reach it first.
    (root / "0000-link").symlink_to(outside, target_is_directory=True)
    for i in range(6):
        _make_run(root, i)
    cleanup_runs(root, retain=5, active_name="none")
    assert (outside / "precious").read_text() == "keep"
    assert (root / "0000-link").is_symlink()


def test_symlink_inside_run_is_unlinked_not_followed(tmp_path):
    runs = [_make_run(tmp_path, i) for i in range(6)]
    target = tmp_path.parent / f"{tmp_path.name}-target.txt"
    target.write_text("keep")
    (runs[0].path / "link").symlink_to(target)
    cleanup_runs(tmp_path, retain=5, active_name="none")
    assert not runs[0].path.exists()
    assert target.read_text() == "keep"


def test_run_with_foreign_subdirectory_stays_in_place(tmp_path):
    runs = [_make_run(tmp_path, i) for i in range(6)]
    (runs[0].path / "extra").mkdir()
    (runs[0].path / "extra" / "f").write_text("keep")
    cleanup_runs(tmp_path, retain=5, active_name="none")
    assert (runs[0].path / "extra" / "f").read_text() == "keep"


def _record_coord_state(monkeypatch, log_dir):
    """Wrap `cleanup_runs` to record whether another opener sees `.coord` held."""
    states = []
    real = runtime_mod.cleanup_runs

    def spy(root, retain, active_name):
        probe = FileLock(log_dir / ".coord")
        states.append(not probe.try_acquire())
        probe.release()
        real(root, retain, active_name)

    monkeypatch.setattr(runtime_mod, "cleanup_runs", spy)
    return states


def test_configure_and_shutdown_clean_up_under_coord_lock(tmp_path, monkeypatch):
    states = _record_coord_state(monkeypatch, tmp_path)
    config = LoggingConfig(app="a", family="a", console=False, log_dir=tmp_path, retain_runs=2)
    runtime = configure(config)
    runtime.shutdown()
    assert states == [True, True]


def test_setup_and_shutdown_keep_only_retained_runs(tmp_path):
    config = LoggingConfig(app="a", family="a", console=False, log_dir=tmp_path, retain_runs=2)
    for _ in range(4):
        configure(config).shutdown()
    runs = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert len(runs) == 2


def test_running_runtime_survives_another_runtimes_cleanup(tmp_path):
    first_cfg = LoggingConfig(app="a", family="a", console=False, log_dir=tmp_path, retain_runs=1)
    first = configure(first_cfg)
    active = next(tmp_path.glob("*/lock")).parent
    # Simulate a second process: its cleanup sees the first run's held lock.
    for i in range(3):
        _make_run(tmp_path, i + 100)
    cleanup_runs(tmp_path, retain=1, active_name="other")
    assert active.exists()
    first.shutdown()
