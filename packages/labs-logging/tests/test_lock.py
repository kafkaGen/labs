import subprocess
import sys
import textwrap

from labs_logging.lock import FileLock


def test_acquire_and_release(tmp_path):
    first = FileLock(tmp_path / "lock")
    assert not first.locked
    assert first.try_acquire() is True
    assert first.locked
    other = FileLock(tmp_path / "lock")
    assert other.try_acquire() is False
    first.release()
    assert other.try_acquire() is True
    other.release()


def test_context_manager(tmp_path):
    with FileLock(tmp_path / "lock") as lock:
        assert lock.locked
    assert FileLock(tmp_path / "lock").try_acquire() is True


def test_lock_releases_on_process_exit(tmp_path):
    code = textwrap.dedent(
        f"""
        from labs_logging.lock import FileLock
        lock = FileLock({str(tmp_path / "lock")!r})
        lock.acquire()
        # exit without releasing: the OS must drop the lock
        """
    )
    subprocess.run([sys.executable, "-c", code], check=True, cwd=tmp_path)
    assert FileLock(tmp_path / "lock").try_acquire() is True
