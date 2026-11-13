"""The structured answer: what the model returns, and what the caller receives.

The model answers in JSON that matches `ANSWER_SCHEMA`. It points at the tool calls it used by
their `tool_use_id`, because a strict schema cannot hold a free-form arguments object. The loop
keeps a `RunLedger` of what the run touched, and `resolve_answer` turns the model's pointers into
resources with the real tool name and arguments, dropping any that point at nothing.
"""

import re
from typing import Annotated, Literal

from labs_logging import get_logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError

__all__ = [
    "ANSWER_SCHEMA",
    "Answer",
    "InvalidAnswerError",
    "Resource",
    "RunLedger",
    "ToolCallSource",
    "UrlSource",
    "resolve_answer",
]

log = get_logger(__name__)

# Stops at whitespace, quotes, brackets, and the escapes JSON puts around them.
_URL = re.compile(r"""https?://[^\s"'<>()\[\]{}\\]+""")
_TRAILING = ".,;:!?"


class InvalidAnswerError(ValueError):
    """The model's final text does not match the answer schema."""


# What the model writes. `extra="forbid"` puts `additionalProperties: false` on every object,
# which strict structured output requires.
class _ToolCallPointer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["tool_call"]
    tool_use_id: Annotated[str, Field(description="The id of a tool call made in this run.")]


class _UrlPointer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["url"]
    url: Annotated[str, Field(description="A URL that appeared in a tool result in this run.")]


class _ModelResource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, Field(description="A short title for the source.")]
    source: _ToolCallPointer | _UrlPointer


class _ModelAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: Annotated[str, Field(description="The answer to the user's question.")]
    resources: Annotated[
        list[_ModelResource],
        Field(description="Only the tool calls and URLs this answer is built from."),
    ]


ANSWER_SCHEMA: dict[str, object] = _ModelAnswer.model_json_schema()


class ToolCallSource(BaseModel):
    """An MCP tool call the run made."""

    model_config = ConfigDict(frozen=True)

    type: Literal["tool_call"] = "tool_call"
    tool: str
    arguments: dict[str, object]


class UrlSource(BaseModel):
    """A URL that appeared in a tool result during the run."""

    model_config = ConfigDict(frozen=True)

    type: Literal["url"] = "url"
    url: str


class Resource(BaseModel):
    """One source that backs the answer."""

    model_config = ConfigDict(frozen=True)

    title: str
    source: Annotated[ToolCallSource | UrlSource, Field(discriminator="type")]


class Answer(BaseModel):
    """The answer text and the resources that back it."""

    model_config = ConfigDict(frozen=True)

    text: str
    resources: list[Resource]


class RunLedger:
    """Everything one run touched: the tool calls it made and the URLs their results held."""

    def __init__(self) -> None:
        self.tool_calls: dict[str, ToolCallSource] = {}
        self.urls: set[str] = set()

    def record_call(self, tool_use_id: str, tool: str, arguments: dict[str, object]) -> None:
        """Record a tool call the run made."""
        self.tool_calls[tool_use_id] = ToolCallSource(tool=tool, arguments=arguments)

    def record_result(self, text: str) -> None:
        """Record every URL in a tool result's text."""
        self.urls.update(match.rstrip(_TRAILING) for match in _URL.findall(text))


def resolve_answer(text: str, ledger: RunLedger) -> Answer:
    """Parse the model's final text and keep only resources the run touched.

    A resource that points at an unknown tool call or URL is dropped, and a warning names it.

    Raises:
        InvalidAnswerError: `text` does not match `ANSWER_SCHEMA`.
    """
    try:
        raw = _ModelAnswer.model_validate_json(text)
    except ValidationError as error:
        raise InvalidAnswerError(f"the answer did not match its schema: {error}") from error
    resources: list[Resource] = []
    for item in raw.resources:
        source = _resolve(item.source, ledger)
        if source is None:
            log.warning(
                "answer resource dropped", title=item.title, source=item.source.model_dump()
            )
            continue
        resources.append(Resource(title=item.title, source=source))
    return Answer(text=raw.answer, resources=resources)


def _resolve(
    pointer: _ToolCallPointer | _UrlPointer, ledger: RunLedger
) -> ToolCallSource | UrlSource | None:
    if isinstance(pointer, _ToolCallPointer):
        return ledger.tool_calls.get(pointer.tool_use_id)
    url = pointer.url.rstrip(_TRAILING)
    return UrlSource(url=url) if url in ledger.urls else None
