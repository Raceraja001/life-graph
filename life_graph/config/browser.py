"""The isolated browser runtime and its egress proxy.

One part of :class:`life_graph.config.Settings`; the fields are read as
``LIFE_GRAPH_<NAME>`` like every other setting.
"""

from __future__ import annotations

from pydantic import BaseModel


class BrowserSettings(BaseModel):
    """The isolated browser runtime and its egress proxy."""

    # ── Isolated browser runtime (services/browser_sandbox_driver.py) ───────
    # Where the sandboxed headless Chromium answers. A browser errand drives a
    # page the owner did not write, so it never runs on the host beside the
    # application's credentials: it runs in the container from
    # compose.sandbox.yaml, reached over Playwright's browser-server websocket
    # on the internal-only network ("ws://browser:9222/"). An http(s) URL is
    # accepted and read as ws(s); a missing port means the sandbox's own 9222.
    #
    # Empty is the code default, and empty means *no browser errands*. There is
    # no fallback to a host or bridged-MCP browser — a browser control endpoint
    # is remote code execution on that browser, and an errand that cannot have
    # a contained one does not run (docs/AI_WORK_ORDER.md §3).
    browser_sandbox_url: str = ""
    # An explicit websocket override, when the control endpoint is not simply
    # the URL above (a broker in front of the browser, say). Wins over it.
    browser_sandbox_ws_url: str = ""

    # ── The control channel's shared secret (path token) ───────────────────
    # Playwright's browser server is started with `--path /<token>`
    # (Dockerfile.browser, SANDBOX_BROWSER_PATH), which makes it accept a
    # websocket upgrade on that one path and refuse every other. The token is
    # therefore the credential for a remote-code-execution handle on the
    # browser: it must be long, random and never written into
    # compose.sandbox.yaml (the sandbox policy refuses a configured secret
    # appearing in that file). Generate one with
    # `python -c "import secrets;print(secrets.token_urlsafe(32))"`.
    #
    # It is only needed when browser_sandbox_url has no path of its own; a URL
    # that already carries one ("ws://browser:9222/<token>") is more specific
    # and wins. Either way the path never reaches a log — every message is
    # written through browser_sandbox_driver.redacted().
    browser_sandbox_token: str = ""
    # Whether a browser errand may run over an *unauthenticated* control
    # channel. Off, and off is the fail-closed answer: Playwright's browser
    # server with no --path accepts any connection that can reach the port,
    # and anything that can open it can drive a browser that may be holding
    # the owner's logged-in session (docs/AI_WORK_ORDER.md §3, "separate
    # authenticated control channel"). Turning this off is for a deployment
    # that authenticates the channel somewhere else (an mTLS gateway in front
    # of 9222) and is a decision to write down.
    browser_sandbox_require_token: bool = True
    # "isolated" (the only mode that produces a browser), "disabled" (browser
    # errands are off), or "mock" (tests inject their own driver through the
    # seam in tools/errand.py). An unknown value reads as disabled, because a
    # setting nobody understands must not be the one that grants a browser.
    browser_sandbox_mode: str = "isolated"
    # Ceiling on connecting to the runtime and on each driver call. Exceeding
    # it is a closed failure: the session is marked lost and the rest of the
    # errand is refused rather than running against an unknown page state.
    browser_sandbox_timeout_seconds: int = 30

    # ── The browser's only way out (services/browser_egress_proxy.py) ───────
    # A forward proxy the sandboxed browser is pointed at, which judges every
    # destination the *browser* asks for — first navigation, every redirect,
    # every sub-resource and XHR — and connects to the address it resolved
    # rather than to the name. That pin is what closes DNS rebinding: the
    # application-level check in services/destination_validator.py resolves a
    # name and the browser then resolves it again, and a zone that answers
    # differently the second time wins that race (docs/AI_WORK_ORDER.md §3).
    #
    # Set this to a proxy the browser container can actually reach — in a
    # compose deployment, a service on both the sandbox's internal bridge and
    # an egress network. Empty means "mint an ephemeral per-errand proxy in
    # this process", which is reachable from the application and from tests
    # but *not* from a container on an internal-only bridge.
    browser_sandbox_egress_proxy_url: str = ""
    # Whether a browser errand may run at all without a proxy in front of it.
    # On, and on is the fail-closed answer: a browser with no egress control is
    # a browser that can be redirected at the metadata endpoint. Turning it off
    # is for a deployment that enforces egress somewhere else (an eBPF/iptables
    # policy, a service mesh) and is a decision to write down, not a toggle to
    # flip when an errand fails.
    browser_sandbox_enforce_egress_proxy: bool = True
