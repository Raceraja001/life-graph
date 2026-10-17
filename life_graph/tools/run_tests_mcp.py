"""stdio MCP server that gives OpenCode the ``run_tests`` tool for one dev task.

OpenCode's own shell is denied (the host is not sandboxed), so before this it
could not run a test it wrote. The OpenCode driver starts this server per
dispatch through the ``mcp`` section of its config, with the task's worktree
and the project's sandbox setup in the environment; it runs the same
sandbox-only :func:`life_graph.tools.run_tests.run_tests` the local driver uses.

    LG_RUN_TESTS_WORKDIR=/tmp/.../wt LG_RUN_TESTS_SETUP="uv sync ..." \\
        python -m life_graph.tools.run_tests_mcp
"""

from __future__ import annotations

import os

from fastmcp import FastMCP

mcp = FastMCP("life-graph-tests")


@mcp.tool()
async def run_tests(paths: list[str] | str) -> str:
    """Run pytest on specific test files or test ids (e.g. tests/unit/test_x.py or
    tests/unit/test_x.py::test_name) in the project's sandbox, and see why they
    fail. Use it to check a test you wrote before you finish."""
    from life_graph.tools._guards import confine_to
    from life_graph.tools.run_tests import project_settings
    from life_graph.tools.run_tests import run_tests as run

    workdir = os.environ.get("LG_RUN_TESTS_WORKDIR")
    if not workdir:
        return '{"error": "run_tests is not configured for this task"}'
    ctx = {
        "sandbox_setup": os.environ.get("LG_RUN_TESTS_SETUP") or None,
        "sandbox_toolchain": os.environ.get("LG_RUN_TESTS_TOOLCHAIN") or "python",
    }
    with confine_to(workdir), project_settings(ctx):
        return await run(paths)


if __name__ == "__main__":
    mcp.run()
