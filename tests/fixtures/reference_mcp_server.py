"""Reference MCP server for mcp_bridge tests. Launched as a real subprocess
by tests/unit/test_mcp_bridge.py — not imported directly.

Defaults to stdio transport (the original tests). Pass ``--http PORT`` to
run as a real streamable-HTTP server instead, for testing mcp_bridge's HTTP
transport path (used by the Playwright MCP integration, which runs as its
own container rather than a stdio subprocess of the app)."""

import sys

from fastmcp import FastMCP

mcp = FastMCP("reference-test-server")


@mcp.tool()
def echo(text: str) -> str:
    """Echo the input text back."""
    return text


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--http":
        mcp.run(transport="streamable-http", host="127.0.0.1", port=int(sys.argv[2]))
    else:
        mcp.run()
