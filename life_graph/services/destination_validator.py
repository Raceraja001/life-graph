"""Decide whether a URL names somewhere a browser may actually be sent.

A browser errand's destination arrives from model output or from a page the
model just read, so "go here" is an instruction from an untrusted source. The
driver is not the place to judge it: a Playwright page will happily open
``file:///etc/passwd``, a CDP driver will evaluate ``javascript:``, and either
will fetch ``http://169.254.169.254/latest/meta-data/`` and hand the cloud
credentials back as page text. So the destination is judged here, at the
application boundary, before any driver sees it:

- only ``http`` and ``https`` — no ``file:``, ``data:``, ``javascript:``,
  ``ftp:`` or anything else;
- no userinfo (``user:pass@host``), no control characters, no malformed
  authority and no invalid port;
- names that mean "this machine" or "the cloud control plane"
  (``localhost``, ``*.localhost``, ``ip6-localhost``,
  ``metadata.google.internal``) are refused by name;
- the host is resolved and **every** address it resolves to must be public:
  no loopback, private, link-local, carrier-NAT, reserved, multicast or
  unspecified address, and none of the known metadata addresses;
- an address written as an address is judged without any lookup, in every
  spelling a resolver would accept — dotted quad, bare decimal
  (``http://2130706433/``), octal and hex (``http://0x7f.1/``), IPv6,
  IPv4-mapped IPv6 (``::ffff:127.0.0.1``), NAT64 and 6to4 — because the
  connection goes to the address the spelling encodes, not to the spelling.

This is deliberately stricter than :mod:`life_graph.services.safe_fetch`,
which does the same job for ``browse_web`` and the page monitors. That path
has an operator allowlist (``LIFE_GRAPH_FETCH_ALLOW_HOSTS``) so the agents can
read a status page on the LAN, and it permits carrier-NAT addresses, which is
where a tailnet lives. Neither applies here: a browser errand types the
owner's real passwords into whatever page it is on, and a self-hosted box or a
tailnet host is not a place to send one on an agent's say-so. There is no
allowlist on this path, on purpose.

**What this does not close.** The name is resolved here and resolved again by
the browser when it connects, so a DNS server that answers differently the
second time (rebinding) can still be reached — the usual time-of-check /
time-of-use gap. Closing it needs the connection pinned to the address that
was checked, which is the egress proxy's job, not this module's. Redirects
have the same shape: this module judges one URL, so a caller that follows
redirects must call it again for every hop, as ``safe_fetch.fetch`` does.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

#: Schemes a browser errand may be sent to. Everything else is refused: the
#: point of a list is that it is a list, not a set of exclusions someone has
#: to remember to extend.
DEFAULT_SCHEMES: tuple[str, ...] = ("http", "https")

#: Longer than any real destination, and short enough that a refusal message
#: and an audit record stay readable.
MAX_URL_CHARS = 2048

#: Anything that is not a character a URL may contain. A newline or a NUL is
#: either a parser-confusion attempt or a mistake; a space means the authority
#: was never well-formed.
_FORBIDDEN_CHARS = re.compile(r"[\x00-\x20\x7f-\x9f  ]")

#: What a DNS name may be made of, once lowercased and IDNA-encoded.
_HOSTNAME_CHARS = re.compile(r"^[a-z0-9._-]+$")

#: Names that mean "this machine" or "the cloud control plane", refused before
#: anything is resolved — a resolver that answers one of these with a public
#: address has still been asked the wrong question.
BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
        "metadata",
        "metadata.google.internal",
        "metadata.goog",
        "instance-data",
        "instance-data.ec2.internal",
    }
)

#: Suffixes with the same meaning. ``.localhost`` is reserved for the loopback
#: interface (RFC 6761) and ``.internal`` for private use, so neither names
#: anywhere an errand should go.
BLOCKED_HOST_SUFFIXES: tuple[str, ...] = (".localhost", ".internal")

#: Cloud instance-metadata endpoints, named outright. Most are already
#: link-local or private, but they are the single most valuable thing an SSRF
#: can reach, so they are refused by their own name in the audit trail rather
#: than as an incidental "link-local address".
METADATA_ADDRESSES = frozenset(
    {
        ipaddress.ip_address("169.254.169.254"),  # AWS, Azure, GCP, DigitalOcean
        ipaddress.ip_address("169.254.170.2"),  # ECS task metadata
        ipaddress.ip_address("fd00:ec2::254"),  # AWS IMDS over IPv6
        ipaddress.ip_address("100.100.100.200"),  # Alibaba Cloud
        ipaddress.ip_address("192.0.0.192"),  # Oracle Cloud
    }
)

#: RFC 6052 well-known prefix: a DNS64 resolver (this host's among them)
#: answers with the IPv4 address embedded in the low 32 bits, and the
#: connection really goes there — so that is what is judged.
_NAT64_WELL_KNOWN = ipaddress.IPv6Network("64:ff9b::/96")

#: RFC 6598 shared address space. Not ``is_private`` in Python's view, and
#: where a tailnet lives.
_CARRIER_NAT = ipaddress.IPv4Network("100.64.0.0/10")


class DestinationRefusedError(ValueError):
    """The URL names somewhere a browser may not go; the message says why.

    A ``ValueError`` so a caller that only wants "this is not a usable URL"
    can catch that, and a distinct type so the browser errand executor can
    turn it into a refused step.
    """


@dataclass(frozen=True, slots=True)
class Destination:
    """A destination that parsed cleanly, before anything was resolved."""

    #: The canonical URL: lowercased scheme and host, default port dropped, an
    #: address spelt the one way it is spelt.
    url: str
    scheme: str
    #: The canonical host, without brackets even when it is IPv6.
    hostname: str
    #: The port the URL declared, or ``None`` when it relied on the default.
    port: int | None
    #: The address, when the host *was* an address in some spelling. ``None``
    #: for a DNS name, which is the only case needing a lookup.
    address: ipaddress.IPv4Address | ipaddress.IPv6Address | None = None

    @property
    def effective_port(self) -> int:
        """The port a connection would use."""
        return self.port or (443 if self.scheme == "https" else 80)

    @property
    def origin(self) -> str:
        """``scheme://host[:port]`` — what an origin check compares."""
        host = f"[{self.hostname}]" if ":" in self.hostname else self.hostname
        default = 443 if self.scheme == "https" else 80
        port = f":{self.port}" if self.port not in (None, default) else ""
        return f"{self.scheme}://{host}{port}"


# ── Judging an address ───────────────────────────────────────────────────


def _unwrap(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """The address a connection would really reach.

    Several IPv6 forms carry an IPv4 address inside them, and a packet sent to
    the wrapper arrives at the wrapped address. ``::ffff:127.0.0.1`` is the
    loopback, and ``2002:7f00:1::`` is the loopback by way of a 6to4 relay.
    (Teredo, ``2001::/32``, is left to the generic checks: Python already
    counts the whole prefix as private.)
    """
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped:
            return ip.ipv4_mapped
        if ip in _NAT64_WELL_KNOWN:
            return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
        if ip.sixtofour:
            return ip.sixtofour
    return ip


def address_refusal(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str | None:
    """Why *ip* may not be reached, in words, or ``None`` if it may.

    A phrase rather than a bool, so the refusal and the audit record say which
    rule caught it.
    """
    ip = _unwrap(ip)
    if ip in METADATA_ADDRESSES:
        return "a cloud metadata address"
    if ip.is_unspecified:
        return "the unspecified address"
    if ip.is_loopback:
        return "a loopback address"
    if ip.is_link_local:
        return "a link-local address"
    if ip.is_multicast:
        return "a multicast address"
    if ip.is_private:
        return "a private address"
    if ip.is_reserved:
        return "a reserved address"
    if isinstance(ip, ipaddress.IPv4Address) and ip in _CARRIER_NAT:
        return "a carrier-NAT address"
    return None


def address_is_public(addr: str) -> bool:
    """Whether *addr* — an address as a string — is somewhere public.

    Fails closed: anything that is not an address at all is not public.
    """
    try:
        ip = ipaddress.ip_address(addr.split("%", 1)[0])
    except ValueError:
        return False
    return address_refusal(ip) is None


def _parse_legacy_ipv4(host: str) -> ipaddress.IPv4Address | None:
    """The address *host* means to ``inet_aton``, or ``None`` if it is a name.

    ``ipaddress`` accepts only the dotted quad, but a browser (and every
    resolver underneath it) also accepts one to four parts in decimal, octal
    or hex, with the last part filling the remaining low bytes: ``2130706433``,
    ``0x7f.1`` and ``0177.0.0.1`` are all 127.0.0.1. These are the classic
    SSRF-filter bypass, so they are parsed rather than passed through as "some
    hostname".
    """
    parts = host.split(".")
    if not 1 <= len(parts) <= 4:
        return None
    values: list[int] = []
    for part in parts:
        if not part:
            return None
        try:
            if part.lower().startswith("0x"):
                value = int(part, 16)
            elif part.startswith("0") and len(part) > 1:
                value = int(part, 8)
            else:
                value = int(part, 10)
        except ValueError:
            return None  # a label that is not a number: this is a name
        if value < 0:
            return None
        values.append(value)
    if any(value > 0xFF for value in values[:-1]):
        return None
    if values[-1] >= 1 << (8 * (5 - len(values))):
        return None
    total = values[-1]
    for position, value in enumerate(values[:-1]):
        total += value << (8 * (3 - position))
    return ipaddress.IPv4Address(total)


def parse_host_address(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """The address *host* names in any spelling, or ``None`` if it is a name."""
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return _parse_legacy_ipv4(host)


# ── Parsing a destination ────────────────────────────────────────────────


def split_destination(
    url: str, *, allowed_schemes: tuple[str, ...] = DEFAULT_SCHEMES
) -> Destination:
    """Parse and canonicalise *url*, resolving nothing.

    Everything that can be decided from the URL itself is decided here, so a
    caller can refuse ``file:``, userinfo tricks and loopback literals without
    making a DNS query — a query is an outbound signal, and a destination that
    was never going to be allowed should not produce one.

    Raises :class:`DestinationRefusedError` with a reason.
    """
    if not isinstance(url, str):
        raise DestinationRefusedError("the destination is not a URL")
    text = url.strip()
    if not text:
        raise DestinationRefusedError("the destination is empty")
    if len(text) > MAX_URL_CHARS:
        raise DestinationRefusedError(
            f"the destination URL is longer than {MAX_URL_CHARS} characters"
        )
    if _FORBIDDEN_CHARS.search(text):
        raise DestinationRefusedError("the destination URL contains control characters or spaces")

    allowed = tuple(scheme.lower() for scheme in allowed_schemes)
    try:
        parts = urlsplit(text)
    except ValueError as exc:
        raise DestinationRefusedError("the destination URL cannot be parsed") from exc

    scheme = parts.scheme.lower()
    if scheme not in allowed:
        shown = scheme or "none"
        raise DestinationRefusedError(
            f"scheme {shown[:20]!r} is not allowed; only {' and '.join(allowed)}"
        )
    if "@" in parts.netloc:
        # ``http://expected.com@evil.io/`` reads as expected.com to a human and
        # resolves evil.io. Nothing legitimate needs it.
        raise DestinationRefusedError("the destination URL carries userinfo (user@host)")

    try:
        hostname, port = parts.hostname, parts.port
    except ValueError as exc:  # an out-of-range or non-numeric port
        raise DestinationRefusedError("the destination URL has an invalid port") from exc
    if not hostname:
        raise DestinationRefusedError("the destination URL has no host")
    if port is not None and not 0 < port < 65536:
        raise DestinationRefusedError("the destination URL has an invalid port")

    host = hostname.strip().rstrip(".").lower()  # a trailing dot is the DNS root
    if not host:
        raise DestinationRefusedError("the destination URL has no host")
    if not host.isascii():
        try:
            host = host.encode("idna").decode("ascii").lower()
        except (UnicodeError, ValueError) as exc:
            raise DestinationRefusedError("the destination hostname is not a usable name") from exc

    address = parse_host_address(host)
    if address is None:
        if not _HOSTNAME_CHARS.match(host):
            raise DestinationRefusedError(
                "the destination hostname has characters a host may not have"
            )
        if any(not label or len(label) > 63 for label in host.split(".")):
            raise DestinationRefusedError("the destination hostname is malformed")
        if host in BLOCKED_HOSTNAMES or host.endswith(BLOCKED_HOST_SUFFIXES):
            raise DestinationRefusedError(f"{host[:60]} is a local or metadata name")
    else:
        refusal = address_refusal(address)
        if refusal:
            raise DestinationRefusedError(f"the destination is {refusal} ({address.compressed})")
        host = address.compressed

    default_port = 443 if scheme == "https" else 80
    shown_host = f"[{host}]" if ":" in host else host
    netloc = shown_host if port in (None, default_port) else f"{shown_host}:{port}"
    canonical = urlunsplit((scheme, netloc, parts.path or "/", parts.query, parts.fragment))
    return Destination(
        url=canonical,
        scheme=scheme,
        hostname=host,
        port=None if port == default_port else port,
        address=address,
    )


# ── Resolving it ─────────────────────────────────────────────────────────


def _getaddrinfo(host: str, port: int) -> list[str]:
    """Every address *host* resolves to. The one place this module does I/O.

    Separate, and module-level, so a test can replace it and still exercise
    every rule above and below it.
    """
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [info[4][0] for info in infos]


def _check_resolved(host: str, addrs: list[str]) -> None:
    """Refuse unless every address *host* resolved to is public.

    Every one, not the first: a name that answers with one public and one
    private address is a DNS-rebinding setup, and which of them the browser
    picks is not ours to decide.
    """
    if not addrs:
        raise DestinationRefusedError(f"{host[:60]} does not resolve")
    for addr in sorted(addrs):
        try:
            ip = ipaddress.ip_address(addr.split("%", 1)[0])
        except ValueError as exc:
            raise DestinationRefusedError(
                f"{host[:60]} resolves to something that is not an address"
            ) from exc
        refusal = address_refusal(ip)
        if refusal:
            raise DestinationRefusedError(f"{host[:60]} resolves to {refusal} ({addr[:45]})")


def resolve_destination(destination: Destination) -> str:
    """The canonical URL of an already-parsed *destination*, name resolved.

    Split from :func:`split_destination` so a caller can settle the cheap
    structural questions early and leave the lookup until it knows this is a
    destination it still wants: a DNS query is an outbound signal, and a URL
    that was never going to be opened should not tell its owner it was
    considered.
    """
    if destination.address is None:
        try:
            addrs = _getaddrinfo(destination.hostname, destination.effective_port)
        except OSError as exc:  # socket.gaierror and friends
            raise DestinationRefusedError(f"{destination.hostname[:60]} does not resolve") from exc
        _check_resolved(destination.hostname, addrs)
    return destination.url


async def resolve_destination_async(destination: Destination) -> str:
    """:func:`resolve_destination` without blocking the event loop."""
    if destination.address is None:
        loop = asyncio.get_running_loop()
        try:
            addrs = await loop.run_in_executor(
                None, _getaddrinfo, destination.hostname, destination.effective_port
            )
        except OSError as exc:
            raise DestinationRefusedError(f"{destination.hostname[:60]} does not resolve") from exc
        _check_resolved(destination.hostname, addrs)
    return destination.url


def validate_destination_url(
    url: str, *, allowed_schemes: tuple[str, ...] = DEFAULT_SCHEMES
) -> str:
    """The canonical URL, or :class:`DestinationRefusedError` saying why not.

    Blocking: it resolves the name. Async callers want
    :func:`validate_destination_url_async`.
    """
    return resolve_destination(split_destination(url, allowed_schemes=allowed_schemes))


async def validate_destination_url_async(
    url: str, *, allowed_schemes: tuple[str, ...] = DEFAULT_SCHEMES
) -> str:
    """:func:`validate_destination_url` without blocking the event loop."""
    return await resolve_destination_async(split_destination(url, allowed_schemes=allowed_schemes))


__all__ = [
    "BLOCKED_HOSTNAMES",
    "BLOCKED_HOST_SUFFIXES",
    "DEFAULT_SCHEMES",
    "MAX_URL_CHARS",
    "METADATA_ADDRESSES",
    "Destination",
    "DestinationRefusedError",
    "address_is_public",
    "address_refusal",
    "parse_host_address",
    "resolve_destination",
    "resolve_destination_async",
    "split_destination",
    "validate_destination_url",
    "validate_destination_url_async",
]
