"""The model caller backed by the Anthropic SDK."""

import anthropic
from anthropic import AsyncAnthropic, omit
from anthropic.types import Message, OutputConfigParam, ThinkingConfigParam, ToolParam

from weather_agents.agent_loop.answer import Answer
from weather_agents.agent_loop.errors import ApiCallError
from weather_agents.agent_loop.interfaces import ModelRequest
from weather_agents.settings import Settings

__all__ = ["ANSWER_SCHEMA", "FAST_MODE_BETA", "AnthropicModelCaller"]

ANSWER_SCHEMA = anthropic.transform_schema(Answer)
FAST_MODE_BETA = "fast-mode-2026-02-01"


class AnthropicModelCaller:
    """Sends one request to the Messages API and returns the assembled final message.

    It always streams, so a long request never trips the SDK's limit on non-streamed calls.
    The answer schema goes in `output_config`, never `output_format`: with `output_format` the
    SDK parses every text block as the stream ends, and raises on a tool-use preamble or on a
    reply cut off at `max_tokens` before the loop can see the stop reason.

    Args:
        client: The SDK client. It keeps its own retries.
        settings: The model, effort, thinking, token limit, and fast mode for every call.
    """

    def __init__(self, client: AsyncAnthropic, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    async def call(self, request: ModelRequest) -> Message:
        """Send one request and return the model's final message.

        Raises:
            ApiCallError: The SDK raised, after its own retries.
        """
        settings = self._settings
        tools: list[ToolParam] = [
            {
                "name": spec.name,
                "description": spec.description,
                "input_schema": spec.input_schema,
                "strict": True,
            }
            for spec in request.tools
        ]
        thinking: ThinkingConfigParam = (
            {"type": "adaptive"} if settings.thinking else {"type": "disabled"}
        )
        output_config: OutputConfigParam = {
            "effort": settings.effort,
            "format": {"type": "json_schema", "schema": ANSWER_SCHEMA},
        }
        try:
            async with self._client.messages.stream(
                model=settings.model,
                max_tokens=settings.max_tokens,
                system=request.system,
                messages=request.messages,
                tools=tools or omit,
                thinking=thinking,
                output_config=output_config,
                speed="fast" if settings.fast_mode else omit,
                extra_headers={"anthropic-beta": FAST_MODE_BETA} if settings.fast_mode else None,
            ) as stream:
                return await stream.get_final_message()
        except anthropic.APIStatusError as error:
            raise ApiCallError(
                f"the API returned {error.status_code}: {error.message}",
                status_code=error.status_code,
            ) from error
        except anthropic.APIError as error:
            raise ApiCallError(f"the API call failed: {error.message}", status_code=None) from error
