"""The structured answer a run returns: the text and the sources that back it."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["Answer", "Resource", "ToolCallResource", "UrlResource"]


class UrlResource(BaseModel):
    """A web page the answer relied on."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["url"]
    url: str
    title: str


class ToolCallResource(BaseModel):
    """A tool call whose result the answer relied on.

    `arguments` is JSON text rather than an object, because strict structured output forbids an
    object with free-form keys.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["tool_call"]
    tool: str
    arguments: str
    title: str


Resource = Annotated[UrlResource | ToolCallResource, Field(discriminator="kind")]


class Answer(BaseModel):
    """What the model must return when it finishes."""

    model_config = ConfigDict(frozen=True)

    answer: str
    resources: list[Resource]
