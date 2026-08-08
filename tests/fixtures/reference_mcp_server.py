"""Reference MCP server for mcp_bridge tests. Launched as a real subprocess
by tests/unit/test_mcp_bridge.py — not imported directly."""

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
    mcp.run()
