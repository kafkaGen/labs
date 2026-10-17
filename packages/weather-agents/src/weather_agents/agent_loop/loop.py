"""The agent loop: call the model, run the tools it asks for, and repeat until it answers."""

import asyncio
import time
from typing import cast

from anthropic.types import (
    ContentBlock,
    ContentBlockParam,
    Message,
    MessageParam,
    TextBlock,
    ToolUseBlock,
)
from labs_logging import get_logger
from pydantic import ValidationError

from weather_agents.agent_loop.answer import Answer, Resource, ToolCallResource
from weather_agents.agent_loop.errors import InvalidAnswerError, RunError, StopReasonError
from weather_agents.agent_loop.interfaces import (
    ModelCaller,
    ModelRequest,
    ToolOutcome,
    ToolProvider,
    ToolSpec,
)
from weather_agents.agent_loop.ledger import SourceLedger
from weather_agents.agent_loop.result import RunResult, TokenUsage
from weather_agents.agent_loop.utils import truncate
from weather_agents.agents import AgentDefinition
from weather_agents.settings import Settings

__all__ = ["run_agent"]

log = get_logger(__name__)


async def run_agent(
    *,
    caller: ModelCaller,
    tools: ToolProvider,
    tool_specs: list[ToolSpec],
    agent: AgentDefinition,
    settings: Settings,
    history: list[MessageParam],
    question: str,
    ledger: SourceLedger,
) -> tuple[RunResult, list[MessageParam]]:
    """Answer one question on top of `history`.

    The run continues on `tool_use` and `pause_turn`, returns on `end_turn`, and raises on every
    other stop reason. `history` is copied, never changed.

    Args:
        caller: Sends each model request.
        tools: Runs the tools the model asks for.
        tool_specs: The tools offered to the model, listed once by the caller.
        agent: Supplies the system prompt.
        settings: Supplies the debug log truncation length.
        history: The session's earlier messages.
        question: The new user message.
        ledger: The session's touched sources. Every tool call is recorded in it.

    Returns:
        The result, and the whole conversation: the history, the question, every intermediate
        reply and tool result, and the final answer. The result's `session_id` is empty.

    Raises:
        StopReasonError: The model stopped for a reason the loop does not continue on.
        InvalidAnswerError: The final reply is not a valid `Answer`.
        ApiCallError: A model call failed.
        Each carries the run's `usage` and the conversation so far in `messages`.
    """
    limit = settings.log_truncate
    messages: list[MessageParam] = [*history, {"role": "user", "content": question}]
    usage = TokenUsage()
    tool_calls = 0
    started = time.monotonic()
    step = 0
    try:
        while True:
            step += 1
            log.debug("model call", step=step, input=truncate(messages[-1], limit))
            request = ModelRequest(
                system=agent.system_prompt, messages=list(messages), tools=tool_specs
            )
            message = await caller.call(request)
            usage = usage.add(message.usage)
            messages.append(
                {"role": "assistant", "content": [_as_param(b) for b in message.content]}
            )
            tool_uses = [block for block in message.content if isinstance(block, ToolUseBlock)]
            names = [block.name for block in tool_uses]
            log.debug(
                "model replied",
                step=step,
                stop_reason=message.stop_reason,
                output=truncate(_text_of(message), limit),
                tool_uses=names,
                tokens=usage.model_dump(),
                elapsed_s=_elapsed(started),
            )

            if message.stop_reason == "tool_use":
                outcomes = await _run_tools(tools, tool_uses, ledger, limit)
                tool_calls += len(tool_uses)
                results: list[ContentBlockParam] = [
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": outcome.content,
                        "is_error": outcome.is_error,
                    }
                    for block, outcome in zip(tool_uses, outcomes, strict=True)
                ]
                messages.append({"role": "user", "content": results})
            elif message.stop_reason == "end_turn":
                answer = _drop_untouched(_parse_answer(message), ledger)
                log.info(
                    "run finished",
                    tokens=usage.model_dump(),
                    elapsed_s=_elapsed(started),
                    turns=step,
                    tool_calls=tool_calls,
                )
                result = RunResult(
                    answer=answer, session_id="", usage=usage, turns=step, tool_calls=tool_calls
                )
                return result, messages
            elif message.stop_reason != "pause_turn":
                raise StopReasonError(str(message.stop_reason), partial_text=_text_of(message))
            # pause_turn: call again with the paused reply already in `messages`.
    except RunError as error:
        error.usage = usage
        error.messages = messages
        raise


async def _run_tools(
    tools: ToolProvider, blocks: list[ToolUseBlock], ledger: SourceLedger, limit: int
) -> list[ToolOutcome]:
    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(_run_tool(tools, block, ledger, limit)) for block in blocks]
    return [task.result() for task in tasks]


async def _run_tool(
    tools: ToolProvider, block: ToolUseBlock, ledger: SourceLedger, limit: int
) -> ToolOutcome:
    ledger.record_tool_call(block.name, block.input)
    log.debug("tool call", tool=block.name, arguments=truncate(block.input, limit))
    try:
        outcome = await tools.call(block.name, block.input)
    # Any exception: one failing call must not cancel its siblings in the task group.
    except Exception as error:
        outcome = ToolOutcome(
            content=f"the tool raised {type(error).__name__}: {error}", is_error=True
        )
    log.debug(
        "tool result",
        tool=block.name,
        result=truncate(outcome.content, limit),
        is_error=outcome.is_error,
    )
    return outcome


def _parse_answer(message: Message) -> Answer:
    text = _text_of(message)
    try:
        return Answer.model_validate_json(text)
    except ValidationError as error:
        raise InvalidAnswerError(
            f"the final reply is not a valid answer ({error.error_count()} errors)",
            partial_text=text,
        ) from error


def _drop_untouched(answer: Answer, ledger: SourceLedger) -> Answer:
    kept: list[Resource] = []
    for resource in answer.resources:
        if isinstance(resource, ToolCallResource):
            is_touched = ledger.has_tool_call(resource.tool, resource.arguments)
        else:
            is_touched = ledger.has_url(resource.url)
        if is_touched:
            kept.append(resource)
        else:
            log.warning(
                "resource dropped",
                resource=resource.model_dump(),
                reason="the session never touched this source",
            )
    return answer.model_copy(update={"resources": kept})


def _as_param(block: ContentBlock) -> ContentBlockParam:
    return cast(ContentBlockParam, block.model_dump(mode="json", exclude_none=True))


def _text_of(message: Message) -> str:
    return "".join(block.text for block in message.content if isinstance(block, TextBlock))


def _elapsed(started: float) -> float:
    return round(time.monotonic() - started, 2)
