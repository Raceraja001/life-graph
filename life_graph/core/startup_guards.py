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

Also here: :func:`langfuse_tracing_allowed`, the check that keeps Langfuse
tracing (every LLM prompt and reply) from going to a host off this machine,
the LAN or the tailnet unless the owner opts in (decision 2026-11-25).
"""

from __future__ import annotations

import ipaddress
import logging
import os
import sys
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from life_graph.config import settings as app_settings

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

logger = logging.getLogger(__name__)

# uvicorn's own default when no --host is given.
UVICORN_DEFAULT_HOST = "127.0.0.1"

# Tailscale gives tailnet devices addresses in the CGNAT range, which
# ipaddress does not count as private. Its IPv6 range (fd7a:115c:a1e0::/48)
# is inside fc00::/7, which it does.
TAILNET_V4 = ipaddress.ip_network("100.64.0.0/10")
# Host-name endings that cannot be on the public internet: this machine
# (RFC 6761), the tailnet (MagicDNS) and the LAN (mDNS).
SELF_HOSTED_SUFFIXES = (".localhost", ".ts.net", ".local")


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


def is_self_hosted_url(url: str) -> bool:
    """True when *url*'s host is on this machine, the LAN or the tailnet.

    Accepted: ``localhost`` and ``*.localhost``; loopback and private IPs
    (127.0.0.0/8, ::1, the RFC 1918 ranges, fc00::/7, link-local); the
    Tailscale ranges (100.64.0.0/10) and ``*.ts.net``; ``*.local``; and a
    one-word host name such as ``langfuse`` (a Docker service on this box).
    Anything else, a URL with no host, or one that does not parse, is not.
    Only the name is checked; it is not looked up.
    """
    try:
        host = (urlsplit(url.strip()).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    if not host:
        return False
    if host in ("localhost", "localhost.localdomain") or host.endswith(SELF_HOSTED_SUFFIXES):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return "." not in host
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_loopback or ip.is_private or ip in TAILNET_V4


def langfuse_tracing_allowed(settings: Any = None) -> bool:
    """Whether Langfuse tracing may start.

    Tracing sends every LiteLLM prompt and reply to ``langfuse_host``, and
    those carry the owner's personal data. So it starts only when a key is
    set and the host is self-hosted (:func:`is_self_hosted_url`), or when
    ``langfuse_allow_remote`` is true. A refused host is logged as a WARNING.
    """
    if settings is None:
        settings = app_settings
    if not settings.langfuse_public_key:
        return False
    if settings.langfuse_allow_remote or is_self_hosted_url(settings.langfuse_host):
        return True
    try:
        shown = urlsplit(settings.langfuse_host.strip()).hostname or settings.langfuse_host
    except ValueError:
        shown = "(unparseable URL)"
    logger.warning(
        "Langfuse tracing NOT enabled: langfuse_host %r is not on this machine, the LAN or "
        "the tailnet, and every LLM prompt and reply (personal data included) would be "
        "sent there. Point LIFE_GRAPH_LANGFUSE_HOST at a self-hosted Langfuse, or set "
        "LIFE_GRAPH_LANGFUSE_ALLOW_REMOTE=true to send them anyway.",
        shown,
    )
    return False


def langfuse_env(settings: Any = None) -> dict[str, str]:
    """The environment LiteLLM's Langfuse callback reads its host and keys from.

    LiteLLM never sees ``settings``: it reads ``LANGFUSE_HOST`` (else
    ``LANGFUSE_BASE_URL``, else Langfuse's cloud) and the two keys from the
    environment. Exporting the checked values makes the traces go to the
    host :func:`langfuse_tracing_allowed` approved, not to a stray env var
    or the cloud default.
    """
    if settings is None:
        settings = app_settings
    return {
        "LANGFUSE_HOST": settings.langfuse_host.strip(),
        "LANGFUSE_PUBLIC_KEY": settings.langfuse_public_key,
        "LANGFUSE_SECRET_KEY": settings.langfuse_secret_key,
    }


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
