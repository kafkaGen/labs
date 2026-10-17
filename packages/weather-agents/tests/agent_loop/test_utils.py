from weather_agents.agent_loop.utils import truncate


def test_a_short_value_is_unchanged():
    assert truncate("sunny", 10) == "sunny"


def test_a_long_value_is_cut_and_says_how_much():
    assert truncate("x" * 25, 10) == "xxxxxxxxxx… [cut 15 chars]"


def test_dicts_and_lists_are_rendered_as_json():
    assert truncate({"latitude": 52.5}, 100) == '{"latitude": 52.5}'
    assert truncate([1, 2], 100) == "[1, 2]"


def test_other_values_use_str():
    assert truncate(42, 100) == "42"
