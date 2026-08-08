# Playwright MCP wiring — design note

## Purpose

Give personas (jarvis first) real interactive-browsing capability — navigate, click,
fill forms, extract data — as the first MCP server actually configured on the bridge
built 2026-08-08. Not a new admin API or UI; matches the bridge's existing env-var-only
configuration philosophy.

## Decisions

**Removed `browser_agent`, kept `browse_web`.** `life_graph/tools/browser.py` had a
second tool, `browser_agent`, that wrapped the third-party `browser-use` package (itself
wrapping Playwright) plus a hardcoded `ChatOpenAI(model="gpt-4o-mini")` — neither
dependency was installed, no OpenAI key is configured, so it was dead code returning an
"not installed" error on every call. It also nested a whole separate LLM agent loop
inside a single tool call, redundant with `AgentOrchestrator`'s own tool-calling loop.
Playwright MCP's individual action tools (navigate, click, fill, ...) called directly
through that same orchestrator loop is the architecturally cleaner replacement — no
reason to maintain both. `browse_web` (plain `httpx` GET + text extraction, no
JavaScript) is unaffected and still the right tool for "just fetch this page's text."

**Playwright MCP runs as its own container, not a stdio subprocess of the app.**
`services/mcp_bridge.py` only supported stdio transport (spawn `command` as a child
process of the app) until this branch. Baking Node.js + Chromium into the Life Graph
app image and running a headless browser inside the same container as the API server
was rejected — real memory-contention risk on this VM (2 vCPU / 8GB shared across
postgres, redis, app, worker, dashboard, caddy, minio, backup) and a browser crash/OOM
could destabilize the API server itself. Instead: the official
`mcr.microsoft.com/playwright/mcp` image runs as its own `docker-compose.production.yml`
service (`playwright-mcp`, port 8931, `--headless --no-sandbox --isolated`), and the
bridge gained an **HTTP transport** to reach it.

## `services/mcp_bridge.py` changes

- `_connect_one` now branches on `server_config.get("transport", "stdio")`: `"http"`
  connects via `mcp.client.streamable_http.streamable_http_client(url)`; anything else
  (including omitted) keeps the original stdio subprocess-spawn path.
- **Bug found and fixed while adding this**, applies to both transports: connection
  setup now happens on a *local* `AsyncExitStack`, only transferred to the caller's
  long-lived one (`exit_stack.push_async_callback(local_stack.pop_all().aclose)`) on
  success. Previously, entering context managers directly on the caller's exit_stack
  meant a failure that only surfaces from a background task during teardown (which HTTP
  transport failures can — unlike a stdio subprocess's synchronous, immediate spawn
  failure) would propagate at the CALLER's eventual shutdown instead of being caught by
  `connect_all`'s per-server `try/except`, defeating the per-server isolation the whole
  design exists to guarantee. Confirmed via a real unreachable-URL test
  (`test_http_transport_bad_url_is_isolated_like_stdio`) that failed before this fix and
  passes after.
- `life_graph/config.py`'s `mcp_servers` doc comment and `.env.example` updated with the
  http shape and a real Playwright example.

## Schema-compatibility check (resolves part of the bridge design's deferred risk)

The bridge design doc flagged that a bridged tool's `inputSchema` is forwarded verbatim,
and a schema using `$defs`/`$ref`/`anyOf` could break tool-calling for every persona that
can see it (some providers, e.g. Gemini's function declarations, reject those). Checked
all ~25 of Playwright MCP's tool schemas directly (via the already-running local
`@playwright/mcp` instance) — every one is a flat top-level object with primitive/array/
enum properties, no `$defs`/`$ref`/`anyOf` anywhere. **Verified safe for this specific
server.** The general validation gap for *arbitrary* future servers is unchanged and
still deferred — this only closes the risk for Playwright.

## Granting jarvis access

`jarvis`'s `allowed_tools` updated via `PATCH /kernel/personas/{id}` to include the
registered `mcp_playwright_*` tool names. Durable across restarts thanks to the
persona-reconciliation fix from earlier the same day (`28098d0`) — before that fix, this
grant would have been silently wiped on the next app restart.

## Testing

`tests/unit/test_mcp_bridge.py` extended with an HTTP-transport counterpart to every
existing stdio test (register, round-trip a call, isolate a bad connection from a good
one) — a real HTTP subprocess (`tests/fixtures/reference_mcp_server.py --http PORT`),
not a mock, matching the file's existing "real protocol, not mocks" convention.

**Local-environment note, not a code finding:** the 3 `test_mcp_bridge.py` failures
observed repeatedly earlier this session (both by an implementer and by re-running
myself), and dismissed both times as "pre-existing flakiness under full-suite load," were
actually caused by `fastmcp` never being installed in this local dev venv — the reference
server subprocess crashed on import every time, deterministically, not flakily. Installing
`fastmcp>=2.0` locally (already a base `pyproject.toml` dependency, just missing from this
particular venv) fixed all of them permanently, no code change involved.

## Deployed

`docker-compose.production.yml`: new `playwright-mcp` service; `app` now
`depends_on: playwright-mcp` (start-order only, `condition: service_started` — the
official image has no healthcheck to wait on). `.env.production`:
`LIFE_GRAPH_MCP_SERVERS=[{"name":"playwright","transport":"http","url":"http://playwright-mcp:8931/mcp"}]`.
