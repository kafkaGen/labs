"""The sources a session touched, so the answer can only cite those."""

import json

__all__ = ["SourceLedger"]


class SourceLedger:
    """Tool calls and URLs one session touched, kept for as long as the session lives."""

    def __init__(self) -> None:
        self._tool_calls: list[tuple[str, object]] = []
        self._urls: set[str] = set()

    def record_tool_call(self, name: str, arguments: dict[str, object]) -> None:
        """Remember a tool call by its prefixed name and its arguments."""
        self._tool_calls.append((name, arguments))

    def has_tool_call(self, name: str, arguments_json: str) -> bool:
        """Whether a call with this name and these arguments was made. Key order is ignored."""
        try:
            arguments = json.loads(arguments_json)
        except json.JSONDecodeError:
            return False
        return any(
            recorded == name and recorded_arguments == arguments
            for recorded, recorded_arguments in self._tool_calls
        )

    def record_url(self, url: str) -> None:
        """Remember a URL a tool searched or fetched."""
        self._urls.add(url)

    def has_url(self, url: str) -> bool:
        """Whether this URL was recorded."""
        return url in self._urls
