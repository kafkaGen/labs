"""What a model call costs, from a price table kept by hand.

The API has no per-request USD cap, so the loop counts spend itself and needs every model's
price. A model missing from `PRICES` cannot run, because its cap could not be enforced.
"""

from pydantic import BaseModel, ConfigDict

from weather_agents.agent_loop.errors import ConfigurationError
from weather_agents.agent_loop.usage import TokenUsage

__all__ = ["PRICES", "ModelPrice", "cost_usd", "price_of"]

_PER_TOKEN = 1 / 1_000_000


class ModelPrice(BaseModel):
    """USD per million tokens, at the base rate."""

    model_config = ConfigDict(frozen=True)

    input_per_mtok: float
    output_per_mtok: float


# Source: Anthropic's model pricing table, checked 2026-11-13. Base rates only. Cache reads and
# writes, Haiku 5.5's higher rate for prompts above 100K tokens, fast mode, and server-tool
# charges are not modelled yet.
PRICES: dict[str, ModelPrice] = {
    "claude-haiku-5-5": ModelPrice(input_per_mtok=0.10, output_per_mtok=0.50),
    "claude-sonnet-5-5": ModelPrice(input_per_mtok=2.00, output_per_mtok=10.00),
    "claude-opus-5-5": ModelPrice(input_per_mtok=4.00, output_per_mtok=20.00),
}


def price_of(model: str) -> ModelPrice:
    """Return the price of `model`.

    Raises:
        ConfigurationError: `model` has no entry in `PRICES`.
    """
    try:
        return PRICES[model]
    except KeyError:
        raise ConfigurationError(
            f"model '{model}' has no price entry, so its USD cap cannot be enforced"
        ) from None


def cost_usd(usage: TokenUsage, model: str) -> float:
    """Return what `usage` costs on `model`, in USD.

    Raises:
        ConfigurationError: `model` has no entry in `PRICES`.
    """
    price = price_of(model)
    return (
        usage.input_tokens * price.input_per_mtok + usage.output_tokens * price.output_per_mtok
    ) * _PER_TOKEN
