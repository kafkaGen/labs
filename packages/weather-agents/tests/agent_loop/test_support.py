import pytest
from anthropic.types import Usage

from weather_agents.agent_loop.errors import (
    ConfigurationError,
    RunError,
    RunLimit,
    UnknownSessionError,
)
from weather_agents.agent_loop.pricing import cost_usd, price_of
from weather_agents.agent_loop.trace import truncate
from weather_agents.agent_loop.usage import TokenUsage


def test_run_error_names_its_stop_reason():
    error = RunError(stop_reason="max_tokens", partial_text="It will be")
    assert str(error) == "run stopped: stop reason 'max_tokens'"
    assert error.limit is None
    assert error.partial_text == "It will be"


def test_run_error_names_its_limit_and_detail():
    error = RunError(limit=RunLimit.DEADLINE, detail="120s passed", cost_usd=0.01)
    assert str(error) == "run stopped: the deadline was reached: 120s passed"
    assert error.stop_reason is None
    assert error.cost_usd == 0.01


@pytest.mark.parametrize("kwargs", [{}, {"stop_reason": "refusal", "limit": RunLimit.USD_CAP}])
def test_run_error_needs_exactly_one_cause(kwargs: dict[str, object]):
    with pytest.raises(ValueError, match="exactly one"):
        RunError(**kwargs)  # ty: ignore[invalid-argument-type]


def test_unknown_session_error_names_the_id():
    assert "abc123" in str(UnknownSessionError("abc123"))


def test_usage_sums_model_calls():
    usage = TokenUsage()
    usage.add(Usage(input_tokens=1_000, output_tokens=200))
    usage.add(Usage(input_tokens=1_500, output_tokens=300))
    assert (usage.input_tokens, usage.output_tokens, usage.total) == (2_500, 500, 3_000)


def test_cost_uses_the_model_price():
    usage = TokenUsage(input_tokens=1_000_000, output_tokens=200_000)
    # Haiku 5.5: $0.10 in, $0.50 out per million tokens.
    assert cost_usd(usage, "claude-haiku-5-5") == pytest.approx(0.20)


def test_an_unpriced_model_names_itself():
    with pytest.raises(ConfigurationError, match="claude-unknown-1"):
        price_of("claude-unknown-1")
    with pytest.raises(ConfigurationError, match="claude-unknown-1"):
        cost_usd(TokenUsage(), "claude-unknown-1")


def test_a_short_value_is_unchanged():
    assert truncate("result", "sunny", 200) == {"result": "sunny"}


def test_a_long_value_is_cut_and_marked():
    fields = truncate("result", "x" * 5_000, 200)
    assert fields == {"result": "x" * 200, "result_truncated": True, "result_length": 5_000}


def test_non_strings_are_serialized_before_the_cut():
    assert truncate("args", {"latitude": 49.8}, 200) == {"args": '{"latitude":49.8}'}
