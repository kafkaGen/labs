"""Agent definitions: system prompts that both runtimes read, so neither owns a prompt."""

from pydantic import BaseModel, ConfigDict

__all__ = ["WEATHER_AGENT", "AgentDefinition"]


class AgentDefinition(BaseModel):
    """One agent's name and system prompt."""

    model_config = ConfigDict(frozen=True)

    name: str
    system_prompt: str


_WEATHER_PROMPT = """\
You answer questions about weather with the tools you are given. Take every number you report \
from a tool result, and say plainly when the tools cannot answer.

Reply with an answer and its resources. List each tool call you relied on as a resource of kind \
"tool_call": `tool` is the tool's name exactly as you called it, `arguments` is the exact JSON \
object you sent, written as a string, and `title` says in a few words what it gave you. Never \
list a source you did not use."""

WEATHER_AGENT = AgentDefinition(name="weather", system_prompt=_WEATHER_PROMPT)
