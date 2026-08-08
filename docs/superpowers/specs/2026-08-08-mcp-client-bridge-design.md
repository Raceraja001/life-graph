# MCP-client bridge — design

## Purpose

Life Graph currently only acts as an MCP *server* (`life_graph/mcp_server.py` exposes its
own memory tools outward via `fastmcp`). Nothing lets it act as an MCP *client* — personas
can't call external MCP servers like the ones already vetted (`microsoft/playwright-mcp`
for browser automation, Google's official Calendar MCP server, `elevenlabs/elevenlabs-mcp`
for premium voice). This is the prerequisite for using any of those; it does not itself
wire up a specific external server.

## Non-goals

- No specific external server configured by default — v1 ships with zero configured
  servers; the bridge does nothing until an admin sets the `mcp_servers` env var.
- No admin CRUD API for managing configured servers — env-var-only configuration,
  matching this codebase's existing convention for external integration config
  (`GEMINI_API_KEY`, `cf_account_id`, etc.).
- No per-tool custom timeout mechanism — bridged tools go through the registry's existing
  global `TOOL_TIMEOUT_SECONDS=15`, unchanged. If a specific external tool needs longer,
  that's a tuning follow-up once a real server is in use, not solved preemptively.
- No fix to `ToolRegistry`'s existing silent-overwrite-on-name-collision behavior — this
  design sidesteps collisions via naming (see below) rather than changing the registry.

## Architecture

```
main.py lifespan startup
  -> mcp_bridge.connect_all(app.state.mcp_exit_stack)
       for each configured server in settings.mcp_servers_list:
         try:
           stdio_client(server) -> ClientSession  [entered into the AsyncExitStack]
           tools = await session.list_tools()
           for tool in tools:
             registry.register(
               name=f"mcp_{server.name}_{tool.name}",
               description=tool.description,
               parameters_schema=tool.inputSchema,
               handler=_make_bridge_handler(session, tool.name),
             )
         except Exception:
           logger.warning(...)  # skip this server, continue to the next

main.py lifespan shutdown
  -> app.state.mcp_exit_stack.aclose()  # closes every connected server's session/process
```

## Config — `life_graph/config.py`

New setting `mcp_servers: str = ""` (JSON string), parsed via a `mcp_servers_list`
`@property` mirroring the existing `tenant_plans` pattern (`config.py:160`,
`tenant_plans_dict` at `config.py:259-265` — `try/except json.JSONDecodeError`, fail-soft
to empty on malformed JSON rather than crashing startup). Shape:

```json
[{"name": "playwright", "command": "npx", "args": ["@playwright/mcp"], "env": {}}]
```

Each entry: `name` (used in the tool-name prefix), `command` + `args` (how to launch the
server's stdio process), `env` (extra environment variables for that process, e.g. API
keys the server itself needs).

## `life_graph/services/mcp_bridge.py` (new)

Not `tools/mcp_bridge.py` — this is orchestration logic (connection lifecycle, dynamic
registration), not a single `@tool`-decorated function like everything else in `tools/`.
It *calls* `registry.register(...)` per discovered tool; it doesn't decorate one.

- `async def connect_all(exit_stack: AsyncExitStack) -> int` — connects every configured
  server, registers its tools, returns the count of tools registered. Never raises — each
  server's connection is independently wrapped in `try/except`, logged and skipped on
  failure, matching `main.py`'s existing local-tool-registration failure pattern
  (`main.py:70-91`). One broken server config never blocks boot or the other servers.
- `_make_bridge_handler(session: ClientSession, tool_name: str) -> Callable` — returns an
  async handler matching the registry's expected signature. Calls
  `session.call_tool(tool_name, arguments=kwargs)`, extracts `.text` from any
  `TextContent` blocks in the result and joins them; non-text content blocks (images,
  etc.) become a short placeholder string (`"[non-text content: <type>]"`) rather than
  being silently dropped. Registry's existing truncation (`MAX_TOOL_RESULT_CHARS=4000`)
  and timeout (`TOOL_TIMEOUT_SECONDS=15`) apply unchanged, since this handler goes through
  the same `registry.register` path as every other tool.

## `life_graph/main.py`

Add to the lifespan startup (near the existing local-tool registration block,
`main.py:69-91`): create `app.state.mcp_exit_stack = AsyncExitStack()`, call
`await mcp_bridge.connect_all(app.state.mcp_exit_stack)`, log the returned tool count. Add
to lifespan shutdown: `await app.state.mcp_exit_stack.aclose()`.

## `pyproject.toml`

Add `mcp` as an explicit direct dependency (currently only present transitively via
`fastmcp` → `fastmcp-slim` → `mcp`, confirmed importable in the project's environment
today — this just pins it directly rather than relying on an unlisted transitive dep).

## Error handling

| Failure | Behavior |
|---|---|
| `mcp_servers` env var malformed JSON | `mcp_servers_list` returns `[]`, logged as a warning — same fail-soft pattern as `tenant_plans_dict`. App boots normally, zero bridged tools. |
| A configured server's process fails to launch (binary missing, bad `command`) | That server's `try/except` in `connect_all` catches it, logs a warning, skips to the next server. Other configured servers and all local tools are unaffected. |
| A configured server launches but `list_tools()` times out or errors | Same per-server catch — skipped, logged, boot continues. |
| Two servers (or a server and a local tool) both declare a tool with the same base name | Not possible by construction — bridged tool names are always prefixed `mcp_<server_name>_`, and server names are expected to be unique (not deduplicated in v1; a config with two identically-named servers is an admin error, not defended against). |
| A bridged tool call itself times out or the external process dies mid-call | Surfaces through the registry's existing `asyncio.wait_for` timeout / exception handling — same behavior as any other tool failing, no special-casing needed. |

## Testing

A tiny reference MCP server (a few lines, using the `mcp` SDK's own server-side API, e.g.
`FastMCP` or the low-level `Server` class) lives under `tests/fixtures/` and is spun up as
a real subprocess by the test suite — the bridge is tested against real MCP protocol
behavior, not mocks, with zero external service or credentials required.

- `connect_all` against the reference server: asserts the expected tool(s) get registered
  with the `mcp_<name>_<tool>` prefix, correct schema translation.
- Calling a bridged tool through the registry: asserts the real round-trip (registry →
  bridge handler → `ClientSession.call_tool` → reference server → text result back).
- Failure path: a config entry pointing at a nonexistent command; asserts `connect_all`
  logs a warning and returns without raising, and that a *second*, valid server in the
  same config still gets connected (isolation, not just graceful degradation of one).
- `mcp_servers_list` parsing: valid JSON, malformed JSON, empty string — matches the
  existing `tenant_plans_dict` test pattern if one exists, for consistency.

## Open items intentionally deferred

- Actually configuring Playwright/Calendar/ElevenLabs MCP servers — separate follow-up
  once credentials are ready.
- Per-tool timeout override — revisit only if a real bridged tool proves the 15s ceiling
  is actually too tight in practice.
- Admin API for managing server config without an env-var + restart — revisit only if
  env-var-only configuration proves too inconvenient in practice.
