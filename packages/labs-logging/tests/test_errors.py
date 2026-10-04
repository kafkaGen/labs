from labs_logging import AlreadyConfiguredError, LoggingError, SetupError


def test_error_hierarchy():
    assert issubclass(SetupError, LoggingError)
    assert issubclass(AlreadyConfiguredError, SetupError)


def test_errors_are_raisable():
    err = SetupError("boom")
    assert str(err) == "boom"
    assert isinstance(err, LoggingError)
