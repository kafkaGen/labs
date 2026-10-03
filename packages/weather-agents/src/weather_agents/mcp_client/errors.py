"""Errors the MCP client raises. Every runtime failure names its server."""

__all__ = ["ConfigError", "McpClientError"]


class McpClientError(Exception):
    """A server could not be reached, dropped, or answered with a protocol error.

    Args:
        server: The name of the server in the `mcpServers` file.
        cause: What went wrong, in one sentence.
    """

    def __init__(self, server: str, cause: str) -> None:
        super().__init__(f"MCP server '{server}': {cause}")
        self.server = server
        self.cause = cause


class ConfigError(Exception):
    """The `mcpServers` file is missing, unreadable, or has an entry the client cannot use."""
