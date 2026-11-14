"""Call the model, run the tools it asks for, send the results back, repeat until end_turn."""

import asyncio
import logging

import anthropic
from anthropic.types import (
    CacheControlEphemeralParam,
    MessageParam,
    ToolParam,
    ToolResultBlockParam,
    ToolUseBlock,
)

from weather_agents.agent_loop.errors import RunError
from weather_agents.agent_loop.messages_api import MessagesApi
from weather_agents.agent_loop.tools import ToolProvider, ToolSpec

__all__ = ["run_loop"]

_logger = logging.getLogger(__name__)

# Automatic prompt caching on every request, with the 5-minute lifetime the backlog rules set.
_CACHE: CacheControlEphemeralParam = {"type": "ephemeral", "ttl": "5m"}


async def run_loop(
    api: MessagesApi,
    tools: ToolProvider,
    *,
    model: str,
    max_tokens: int,
    system: str,
    question: str,
) -> str:
    """Answer one question, calling tools until the model ends its turn.

    Args:
        api: The Messages API, or a fake of it.
        tools: Where the tools come from. Listed once per run.
        model: The model id.
        max_tokens: The output cap for each model call.
        system: The system prompt.
        question: The user's question.

    Returns:
        The text of the model's final turn.

    Raises:
        RunError: The API call failed after the client's own retries, the model stopped for a
            reason other than `end_turn` or `tool_use`, or a tool call raised.
    """
    tool_params = [_tool_param(spec) for spec in await tools.list_tools()]
    messages: list[MessageParam] = [{"role": "user", "content": question}]
    while True:
        try:
            response = await api.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                tools=tool_params,
                messages=messages,
                cache_control=_CACHE,
            )
        except anthropic.APIError as error:
            raise _fail(RunError(f"model call failed: {error}"), error) from error
        # The blocks go back exactly as they came. Thinking blocks must not be altered.
        messages.append({"role": "assistant", "content": response.content})
        match response.stop_reason:
            case "end_turn":
                return "".join(block.text for block in response.content if block.type == "text")
            case "tool_use":
                calls = [block for block in response.content if block.type == "tool_use"]
                messages.append({"role": "user", "content": await _run_tools(tools, calls)})
            case other:
                # Includes a turn cut off mid tool call, so no tool from it ever runs.
                message = f"the model stopped with '{other}' instead of ending its turn"
                raise _fail(RunError(message, stop_reason=other), None)


async def _run_tools(tools: ToolProvider, calls: list[ToolUseBlock]) -> list[ToolResultBlockParam]:
    # One TaskGroup, so a raising call cancels its siblings. Results keep the model's order.
    try:
        async with asyncio.TaskGroup() as group:
            tasks = [group.create_task(_call(tools, call)) for call in calls]
    except ExceptionGroup as group:
        # `_call` turns every failure into a RunError, so the leaves are all RunErrors.
        first = group.exceptions[0]
        if not isinstance(first, RunError):
            raise
        raise _fail(first, first.__cause__) from first.__cause__
    return [task.result() for task in tasks]


async def _call(tools: ToolProvider, call: ToolUseBlock) -> ToolResultBlockParam:
    try:
        outcome = await tools.call(call.name, call.input)
    except Exception as error:
        # Not logged here: when several calls fail, only the one the run raises is logged.
        raise RunError(f"tool '{call.name}' failed: {error}", tool=call.name) from error
    result: ToolResultBlockParam = {
        "type": "tool_result",
        "tool_use_id": call.id,
        "content": outcome.text,
    }
    if outcome.is_error:
        result["is_error"] = True
    return result


def _fail(error: RunError, cause: BaseException | None) -> RunError:
    # Every RunError the run raises passes through here once, so its cause is logged once.
    if cause is None:
        _logger.error("run failed: %s", error)
    else:
        _logger.error("run failed: %s (cause: %r)", error, cause)
    return error


def _tool_param(spec: ToolSpec) -> ToolParam:
    param: ToolParam = {"name": spec.name, "input_schema": spec.input_schema}
    if spec.description is not None:
        param["description"] = spec.description
    return param
