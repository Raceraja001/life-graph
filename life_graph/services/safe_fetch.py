"""Fetch a URL an agent or a monitor chose, without reaching the private network.

``browse_web`` and the page monitors fetch URLs that come from model output or
from a user's monitor list. A plain ``httpx.get`` would happily fetch
``http://localhost:8080/api/v1/...``, the cloud metadata address or a router's
admin page, and hand the response to the model. Every such fetch goes through
here instead:

- only ``http`` and ``https``;
- the host is resolved and **every** address it resolves to must be public
  (no loopback, private, link-local, reserved, multicast or unspecified);
- redirects are followed by hand, and each hop is checked the same way;
- the body is capped at ``max_bytes``.

Hosts in ``fetch_allow_hosts`` skip the address check, for a self-hosted
service the user wants the agents to reach (a SearXNG instance, a status page
on the LAN).

The check resolves the name and httpx resolves it again, so a DNS server that
answers differently the second time (rebinding) can still get through. Closing
that needs connecting to the checked address itself; for an assistant that
fetches pages on its owner's behalf, the check above is the proportionate
control and the residual risk is recorded here.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from life_graph.config import settings

USER_AGENT = "LifeGraph-Agent/1.0 (+personal assistant)"
MAX_REDIRECTS = 5


class FetchBlockedError(Exception):
    """The URL points somewhere an agent may not fetch; the message says why."""


@dataclass
class FetchResult:
    url: str  # final URL after redirects
    status_code: int
    content_type: str
    text: str
    truncated: bool


def _allowed_hosts() -> set[str]:
    return {h.strip().lower() for h in settings.fetch_allow_hosts.split(",") if h.strip()}


def _is_public(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr.split("%", 1)[0])
    except ValueError:
        return False  # fail closed on anything that is not an address
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


async def _resolve(host: str, port: int) -> set[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return {info[4][0] for info in infos}


async def check_url(url: str) -> None:
    """Raise :class:`FetchBlockedError` unless ``url`` may be fetched."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise FetchBlockedError(
            f"only http and https URLs can be fetched, not {parts.scheme or 'none'}"
        )
    host = (parts.hostname or "").lower()
    if not host:
        raise FetchBlockedError("the URL has no host")
    if host in _allowed_hosts():
        return
    try:
        addrs = await _resolve(host, parts.port or (443 if parts.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise FetchBlockedError(f"{host} does not resolve") from exc
    private = sorted(a for a in addrs if not _is_public(a))
    if private:
        raise FetchBlockedError(
            f"{host} resolves to a private or local address ({private[0]}); "
            "add it to LIFE_GRAPH_FETCH_ALLOW_HOSTS if it should be reachable"
        )


async def fetch(
    url: str,
    *,
    method: str = "GET",
    data: dict[str, str] | None = None,
    timeout: float = 15.0,
    max_bytes: int = 2_000_000,
    client: httpx.AsyncClient | None = None,
) -> FetchResult:
    """Fetch ``url`` with every hop checked; raises FetchBlockedError or httpx errors."""
    own = client is None
    http = client or httpx.AsyncClient(timeout=timeout, headers={"User-Agent": USER_AGENT})
    try:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            await check_url(current)
            request = http.build_request(method, current, data=data)
            response = await http.send(request, stream=True, follow_redirects=False)
            try:
                if response.is_redirect and response.headers.get("location"):
                    current = urljoin(current, response.headers["location"])
                    # A 303 (and, by browser convention, 301/302 after POST) turns into GET.
                    if response.status_code in (301, 302, 303):
                        method, data = "GET", None
                    continue
                body = bytearray()
                truncated = False
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        truncated = True
                        del body[max_bytes:]
                        break
                response.raise_for_status()
                encoding = response.encoding or "utf-8"
                return FetchResult(
                    url=current,
                    status_code=response.status_code,
                    content_type=response.headers.get("content-type", ""),
                    text=bytes(body).decode(encoding, errors="replace"),
                    truncated=truncated,
                )
            finally:
                await response.aclose()
        raise FetchBlockedError(f"more than {MAX_REDIRECTS} redirects")
    finally:
        if own:
            await http.aclose()
