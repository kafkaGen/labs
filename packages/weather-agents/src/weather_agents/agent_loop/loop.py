"""One agent run: call the model, run the tools it asks for, repeat until it answers.

The run ends with an answer only on `end_turn`. `tool_use` and `pause_turn` continue it. Every
other stop reason, a reached USD cap, and a passed deadline raise `RunError`.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence
from typing import Annotated

from anthropic.types import (
    Message,
    MessageParam,
    TextBlock,
    ToolParam,
    ToolResultBlockParam,
    ToolUseBlock,
)
from labs_logging import get_logger
from pydantic import BaseModel, ConfigDict, SkipValidation

from weather_agents.agent_loop.answer import (
    ANSWER_SCHEMA,
    Answer,
    InvalidAnswerError,
    RunLedger,
    resolve_answer,
)
from weather_agents.agent_loop.errors import ConfigurationError, RunError, RunLimit
from weather_agents.agent_loop.pricing import cost_usd, price_of
from weather_agents.agent_loop.tools import ToolOutcome, ToolProvider, ToolSpec
from weather_agents.agent_loop.trace import truncate
from weather_agents.agent_loop.usage import TokenUsage
from weather_agents.settings import Settings

__all__ = ["SOURCE_ID_PREFIX", "CreateMessage", "LoopOutcome", "run_agent"]

log = get_logger(__name__)

# Opens every tool result, so the model can copy the id into the answer's resources. The id
# is otherwise only block metadata, and models invent ids when they cannot see one.
SOURCE_ID_PREFIX = "[source id: "

# `AsyncAnthropic().messages.create`, or a fake with the same keyword arguments.
CreateMessage = Callable[..., Awaitable[Message]]


class LoopOutcome(BaseModel):
    """A finished run.

    `messages` is the whole conversation the run ended with: the history it was given, the
    question, and every assistant and tool turn, with assistant content exactly as the API
    returned it.
    """

    model_config = ConfigDict(frozen=True)

    answer: Answer
    messages: Annotated[list[MessageParam], SkipValidation]
    usage: TokenUsage
    cost_usd: float
    turns: int
    tool_calls: int


class _Run:
    # Running totals for one request, and the log fields every step line carries.

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.usage = TokenUsage()
        self.cost_usd = 0.0
        self.turns = 0
        self.tool_calls = 0
        self.ledger = RunLedger()
        self.started = time.monotonic()

    @property
    def seconds_left(self) -> float:
        return round(self.settings.deadline_seconds - (time.monotonic() - self.started), 3)

    def add(self, response: Message) -> None:
        self.turns += 1
        self.usage.add(response.usage)
        self.cost_usd = cost_usd(self.usage, self.settings.model)

    def progress(self) -> dict[str, object]:
        return {"tokens_so_far": self.usage.total, "seconds_left": self.seconds_left}

    def fail(self, partial_text: str = "", **cause: object) -> RunError:
        error = RunError(
            usage=self.usage.model_copy(),
            cost_usd=self.cost_usd,
            partial_text=partial_text,
            **cause,  # ty: ignore[invalid-argument-type]
        )
        log.error("run.error", error=str(error), **self.progress())
        return error

    def truncated(self, name: str, value: object) -> dict[str, object]:
        return truncate(name, value, self.settings.log_truncate_chars)


async def run_agent(
    *,
    create_message: CreateMessage,
    tools: ToolProvider,
    history: Sequence[MessageParam],
    question: str,
    settings: Settings,
    system: str,
) -> LoopOutcome:
    """Run one question to a structured answer.

    The caller's `history` is not changed. The returned `LoopOutcome.messages` holds the
    conversation to keep if the run succeeded.

    Args:
        create_message: Sends one Messages API request.
        tools: Supplies the tools and runs the calls.
        history: Earlier turns of the session, oldest first.
        question: The user's new question.
        settings: Model, limits, and log settings for this run.
        system: The system prompt.

    Raises:
        ConfigurationError: The model has no price entry. No model call is made.
        RunError: The model stopped with a reason other than `end_turn`, the answer did not
            match its schema, the USD cap was reached, or the deadline passed.
    """
    run = _Run(settings)
    outcome = "error"
    try:
        try:
            price_of(settings.model)
        except ConfigurationError as error:
            log.error("run.error", error=str(error))
            raise
        tool_params = _tool_params(await tools.tool_specs())
        messages: list[MessageParam] = [*history, {"role": "user", "content": question}]
        try:
            async with asyncio.timeout(settings.deadline_seconds):
                result = await _loop(create_message, tools, tool_params, messages, system, run)
        except TimeoutError:
            raise run.fail(
                limit=RunLimit.DEADLINE, detail=f"{settings.deadline_seconds:g}s passed"
            ) from None
        outcome = "ok"
        return result
    finally:
        log.info(
            "run.end",
            outcome=outcome,
            input_tokens=run.usage.input_tokens,
            output_tokens=run.usage.output_tokens,
            total_tokens=run.usage.total,
            cost_usd=round(run.cost_usd, 6),
            elapsed_seconds=round(time.monotonic() - run.started, 3),
            deadline_seconds=settings.deadline_seconds,
            tool_calls=run.tool_calls,
            turns=run.turns,
        )


async def _loop(
    create_message: CreateMessage,
    tools: ToolProvider,
    tool_params: list[ToolParam],
    messages: list[MessageParam],
    system: str,
    run: _Run,
) -> LoopOutcome:
    settings = run.settings
    while True:
        if run.cost_usd >= settings.usd_cap:
            raise run.fail(
                limit=RunLimit.USD_CAP,
                detail=f"spent ${run.cost_usd:.4f} of ${settings.usd_cap:g}",
            )
        log.debug("model.request", **run.truncated("input", messages[-1]), **run.progress())
        response = await create_message(
            model=settings.model,
            max_tokens=settings.max_tokens,
            system=system,
            messages=messages,
            tools=tool_params,
            output_config={"format": {"type": "json_schema", "schema": ANSWER_SCHEMA}},
        )
        run.add(response)
        log.debug(
            "model.response",
            stop_reason=response.stop_reason,
            blocks=[block.type for block in response.content],
            # Thinking blocks carry only a signature here, which would fill the truncated value.
            **run.truncated(
                "output", [b.to_dict() for b in response.content if b.type != "thinking"]
            ),
            **run.progress(),
        )
        messages.append({"role": "assistant", "content": response.content})

        match response.stop_reason:
            case "end_turn":
                return _finish(response, messages, run)
            case "tool_use":
                results = await _run_tools(response, tools, run)
                messages.append({"role": "user", "content": results})
            case "pause_turn":
                continue
            case other:
                raise run.fail(stop_reason=str(other), partial_text=_text_of(response))


def _finish(response: Message, messages: list[MessageParam], run: _Run) -> LoopOutcome:
    text = _text_of(response)
    try:
        answer = resolve_answer(text, run.ledger)
    except InvalidAnswerError as error:
        raise run.fail(stop_reason="end_turn", detail=str(error), partial_text=text) from error
    return LoopOutcome(
        answer=answer,
        messages=messages,
        usage=run.usage.model_copy(),
        cost_usd=run.cost_usd,
        turns=run.turns,
        tool_calls=run.tool_calls,
    )


async def _run_tools(
    response: Message, tools: ToolProvider, run: _Run
) -> list[ToolResultBlockParam]:
    calls = [block for block in response.content if isinstance(block, ToolUseBlock)]
    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(_call_tool(call, tools, run)) for call in calls]
    return [task.result() for task in tasks]


async def _call_tool(call: ToolUseBlock, tools: ToolProvider, run: _Run) -> ToolResultBlockParam:
    arguments = call.input if isinstance(call.input, dict) else {}
    run.tool_calls += 1
    run.ledger.record_call(call.id, call.name, arguments)
    log.debug(
        "tool.call", tool=call.name, tool_use_id=call.id, **run.truncated("arguments", arguments)
    )
    try:
        outcome = await tools.call(call.name, arguments)
    except Exception as error:  # any provider failure goes back to the model, never up
        outcome = ToolOutcome(text=f"tool call failed: {error}", is_error=True)
    if not outcome.is_error:
        run.ledger.record_result(outcome.text)
    log.debug(
        "tool.result",
        tool=call.name,
        tool_use_id=call.id,
        is_error=outcome.is_error,
        **run.truncated("result", outcome.text),
        **run.progress(),
    )
    return {
        "type": "tool_result",
        "tool_use_id": call.id,
        "content": f"{SOURCE_ID_PREFIX}{call.id}]\n{outcome.text}",
        "is_error": outcome.is_error,
    }


def _tool_params(specs: list[ToolSpec]) -> list[ToolParam]:
    # Not strict: the MCP server validates arguments (see design decision 3).
    return [
        {"name": spec.name, "description": spec.description, "input_schema": spec.input_schema}
        for spec in specs
    ]


def _text_of(response: Message) -> str:
    return "".join(block.text for block in response.content if isinstance(block, TextBlock))
