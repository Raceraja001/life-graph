"""Checks that must stop the API from starting, not merely degrade it.

Audit M5 (docs/audits/2026-11-19-code-quality-audit.html): with no API key
configured, ``api/auth.py`` lets every request through in development, and the
default ``environment`` is ``development``. That is fine on loopback (whoever
can reach 127.0.0.1 is already on the box), and wide open anywhere else. The
default is deliberately not flipped (local scripts and both editions rely on
it); instead the API refuses to start in the one combination that exposes it.

Meant to be called from ``lifespan`` in ``main.py`` before anything else
starts (right after the "Running in DEVELOPMENT mode" warning), outside
``startup_step()`` (which swallows exceptions) because this one must be fatal.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import sys
from typing import TYPE_CHECKING, Any

from life_graph.config import settings as app_settings

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

logger = logging.getLogger(__name__)

# uvicorn's own default when no --host is given.
UVICORN_DEFAULT_HOST = "127.0.0.1"


class InsecureStartupError(RuntimeError):
    """The API would serve unauthenticated requests beyond this machine."""


def _host_from_argv(argv: Sequence[str]) -> str | None:
    """The ``--host`` uvicorn was started with, if it was started from the CLI.

    ``--uds`` (a Unix socket) is local by construction and counts as loopback.
    """
    for i, arg in enumerate(argv):
        if arg == "--host" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--host="):
            return arg.split("=", 1)[1]
        if arg == "--uds" or arg.startswith("--uds="):
            return "localhost"
    return None


def detect_bind_host(
    argv: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> str:
    """Where this process listens, as best the app itself can tell.

    The app is not told its bind address, so: uvicorn's ``--host`` on the
    command line (what dev.sh, start.sh, restart-api.sh and the Dockerfiles
    all pass), else ``LIFE_GRAPH_BIND_HOST`` (what those scripts read it
    from), else uvicorn's default, loopback.
    """
    argv = sys.argv if argv is None else argv
    environ = os.environ if environ is None else environ
    host = _host_from_argv(argv)
    if host is None:
        host = environ.get("LIFE_GRAPH_BIND_HOST") or UVICORN_DEFAULT_HOST
    return host.strip()


def is_loopback_host(host: str) -> bool:
    """True for 127.0.0.0/8, ::1 and ``localhost``; False for 0.0.0.0, ::, LAN/tailnet addresses."""
    host = host.strip().strip("[]")
    if host.lower() in ("localhost", "localhost.localdomain"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        # A hostname other than localhost: it may resolve anywhere. Not loopback.
        return False


def _has_api_keys(settings: Any) -> bool:
    """The same "any key configured" test ``api/auth.verify_service_key`` uses."""
    return bool(settings.service_api_keys_list or settings.api_key)


def check_auth_exposure(settings: Any = None, bind_host: str | None = None) -> None:
    """Refuse to start an unauthenticated API on a non-loopback address.

    * No API key and a non-loopback bind: raise :class:`InsecureStartupError`,
      whatever ``environment`` says (in development every request would get
      through; in production every request would get 401, a broken service).
    * No API key, development, loopback: start, with a loud WARNING.
    * Any key configured: nothing to say.

    Args:
        settings: The settings object (defaults to ``life_graph.config.settings``).
        bind_host: Where the API listens (defaults to :func:`detect_bind_host`).
    """
    if settings is None:
        settings = app_settings
    if _has_api_keys(settings):
        return
    host = detect_bind_host() if bind_host is None else bind_host
    if not is_loopback_host(host):
        raise InsecureStartupError(
            f"Refusing to start: no API key is configured and the API is bound to {host!r}, "
            "which is reachable from other machines. Set LIFE_GRAPH_SERVICE_API_KEYS "
            "(or bind to 127.0.0.1 with LIFE_GRAPH_BIND_HOST / uvicorn --host 127.0.0.1)."
        )
    if settings.is_development:
        logger.warning(
            "AUTH IS OFF: no API key is configured and environment=development, so every "
            "request on %s is accepted as the owner with no credential. Fine for a local "
            "dev stack only; set LIFE_GRAPH_SERVICE_API_KEYS before exposing it.",
            host,
        )
