import logging

from labs_logging.rotation import JsonFileHandler


def _handler(tmp_path, max_bytes, backups):
    handler = JsonFileHandler(tmp_path / "main.jsonl", max_bytes=max_bytes, backups=backups)
    handler.setFormatter(logging.Formatter("%(message)s"))
    return handler


def _emit(handler, payload):
    handler.emit(logging.LogRecord("x", logging.INFO, "", 0, payload, (), None))


def test_writes_json_lines(tmp_path):
    handler = _handler(tmp_path, 100, 0)
    _emit(handler, "one")
    _emit(handler, "two")
    handler.close()
    assert (tmp_path / "main.jsonl").read_text() == "one\ntwo\n"


def test_discard_and_restart_at_size(tmp_path):
    handler = _handler(tmp_path, 10, 0)
    _emit(handler, "first")  # 6 bytes with newline
    _emit(handler, "second")  # 6 + 7 > 10, rollover discards "first"
    handler.close()
    assert (tmp_path / "main.jsonl").read_text() == "second\n"


def test_oversized_record_kept_intact(tmp_path):
    handler = _handler(tmp_path, 5, 0)
    _emit(handler, "way-too-long")
    handler.close()
    assert (tmp_path / "main.jsonl").read_text() == "way-too-long\n"


def test_backups_rotate(tmp_path):
    handler = _handler(tmp_path, 5, 2)
    for msg in ["aaaa", "bbbb", "cccc"]:
        _emit(handler, msg)
    handler.close()
    assert (tmp_path / "main.jsonl").read_text() == "cccc\n"
    assert (tmp_path / "main.jsonl.1").read_text() == "bbbb\n"
    assert (tmp_path / "main.jsonl.2").read_text() == "aaaa\n"