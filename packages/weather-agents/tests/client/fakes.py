"""Stand-ins for `mcp.Client`, so session and pool tests need no child process."""

from collections.abc import Mapping, Sequence
from types import TracebackType
from typing import Self

from mcp import StdioServerParameters
from mcp.types import (
    CallToolResult,
    GetPromptResult,
    ListPromptsResult,
    ListResourcesResult,
    ListResourceTemplatesResult,
    ListToolsResult,
    Prompt,
    ReadResourceResult,
    Resource,
    ResourceTemplate,
    TextContent,
    Tool,
)


def make_tool(name: str) -> Tool:
    return Tool(name=name, input_schema={"type": "object"})


def make_resource(uri: str) -> Resource:
    return Resource(name=uri, uri=uri)


def make_template(uri_template: str) -> ResourceTemplate:
    return ResourceTemplate(name=uri_template, uri_template=uri_template)


def make_prompt(name: str) -> Prompt:
    return Prompt(name=name)


class FakeClient:
    """Serves canned lists in pages of `page_size`, and can fail on entry or on every call.

    `open_error` raises when the client is entered, like a spawn failure. Set `error` after
    entering to simulate a session that drops.
    """

    def __init__(
        self,
        *,
        tools: Sequence[Tool] = (),
        resources: Sequence[Resource] = (),
        templates: Sequence[ResourceTemplate] = (),
        prompts: Sequence[Prompt] = (),
        page_size: int = 2,
        open_error: BaseException | None = None,
    ) -> None:
        self.tools = tools
        self.resources = resources
        self.templates = templates
        self.prompts = prompts
        self.page_size = page_size
        self.open_error = open_error
        self.error: BaseException | None = None
        self.calls: list[tuple[str, object]] = []
        self.tool_result = CallToolResult(content=[TextContent(type="text", text="ok")])
        self.resource_result = ReadResourceResult(contents=[])
        self.prompt_result = GetPromptResult(messages=[])
        self.closed = False

    async def __aenter__(self) -> Self:
        if self.open_error is not None:
            raise self.open_error
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.closed = True

    def _record(self, method: str, detail: object) -> None:
        self.calls.append((method, detail))
        if self.error is not None:
            raise self.error

    def _page[T](self, items: Sequence[T], cursor: str | None) -> tuple[list[T], str | None]:
        start = int(cursor or 0)
        end = start + self.page_size
        return list(items[start:end]), (str(end) if end < len(items) else None)

    async def list_tools(self, *, cursor: str | None = None) -> ListToolsResult:
        self._record("list_tools", cursor)
        page, next_cursor = self._page(self.tools, cursor)
        return ListToolsResult(tools=page, next_cursor=next_cursor)

    async def list_resources(self, *, cursor: str | None = None) -> ListResourcesResult:
        self._record("list_resources", cursor)
        page, next_cursor = self._page(self.resources, cursor)
        return ListResourcesResult(resources=page, next_cursor=next_cursor)

    async def list_resource_templates(
        self, *, cursor: str | None = None
    ) -> ListResourceTemplatesResult:
        self._record("list_resource_templates", cursor)
        page, next_cursor = self._page(self.templates, cursor)
        return ListResourceTemplatesResult(resource_templates=page, next_cursor=next_cursor)

    async def list_prompts(self, *, cursor: str | None = None) -> ListPromptsResult:
        self._record("list_prompts", cursor)
        page, next_cursor = self._page(self.prompts, cursor)
        return ListPromptsResult(prompts=page, next_cursor=next_cursor)

    async def call_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult:
        self._record("call_tool", (name, arguments))
        return self.tool_result

    async def read_resource(self, uri: str) -> ReadResourceResult:
        self._record("read_resource", uri)
        return self.resource_result

    async def get_prompt(
        self, name: str, arguments: dict[str, str] | None = None
    ) -> GetPromptResult:
        self._record("get_prompt", (name, arguments))
        return self.prompt_result


class FakeFactory:
    """Stands in for the `Client` class. Picks a client by the spawn command."""

    def __init__(self, clients: Mapping[str, FakeClient]) -> None:
        self.clients = clients
        self.calls: list[tuple[StdioServerParameters, dict[str, object]]] = []

    def __call__(self, params: StdioServerParameters, **kwargs: object) -> FakeClient:
        self.calls.append((params, kwargs))
        return self.clients[params.command]
