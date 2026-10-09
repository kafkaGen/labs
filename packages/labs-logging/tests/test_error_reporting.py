import logging

from labs_logging import LoggingConfig, configure


class _Broken(logging.Handler):
    def emit(self, record):
        raise RuntimeError("broken")


def _config(tmp_path, *handlers):
    return LoggingConfig(
        app="a",
        family="a",
        console=False,
        file=False,
        synchronous=True,
        log_dir=tmp_path,
        extra_handlers=list(handlers),
    )


def test_diagnostic_prints_once_per_failing_handler(tmp_path, capsys):
    with configure(_config(tmp_path, _Broken())) as runtime:
        for _ in range(3):
            logging.getLogger("lib").warning("x")
    assert runtime.error_count == 3
    assert capsys.readouterr().err.count("failed") == 1


def test_two_handlers_of_one_class_each_report(tmp_path, capsys):
    with configure(_config(tmp_path, _Broken(), _Broken())) as runtime:
        logging.getLogger("lib").warning("x")
    assert runtime.error_count == 2
    assert capsys.readouterr().err.count("failed") == 2
