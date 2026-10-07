from labs_logging.normalize import normalize


def test_native_values_pass_through():
    assert normalize({"a": [1, 2.5, "x", None, True]}) == {"a": [1, 2.5, "x", None, True]}


def test_containers_are_copied():
    original = {"k": [1]}
    result = normalize(original)
    original["k"].append(2)
    assert result == {"k": [1]}


def test_shared_reference_is_not_a_cycle():
    shared = [1]
    assert normalize([shared, shared]) == [[1], [1]]


def test_cycle_is_marked():
    data: list = [1]
    data.append(data)
    assert normalize(data) == [1, "<cycle>"]


def test_non_finite_float_and_odd_keys():
    assert normalize({1: float("nan")}) == {"1": "nan"}


def test_unsupported_type_is_labelled_and_hostile_falls_back_to_type_name():
    class Bad:
        def __repr__(self):
            raise RuntimeError

    assert normalize(object()).startswith("object: ")
    assert normalize(Bad()) == "Bad"


def test_deep_nesting_does_not_crash():
    data: list = []
    for _ in range(5000):
        data = [data]
    assert isinstance(normalize(data), str | list)
