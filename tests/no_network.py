"""pytest plugin: run the suite as if it had no network (loopback only).

The dev-agent's verifier runs ``pytest tests/unit`` inside a container with no
network. A test that quietly needs DNS or an outbound connection passes on a
laptop and in CI, then fails there and blocks every dev task on this repo
(2026-11-20: one capability test did exactly that for every nightly task).

CI loads this plugin for the unit job (``-p tests.no_network``), so such a
test fails CI instead. Loopback stays open: tests may talk to a local
Postgres, Redis or model server and skip when it isn't there.
"""

from __future__ import annotations

import socket

_real_getaddrinfo = socket.getaddrinfo
_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex


def _is_local(host: object) -> bool:
    if host is None or host == "":
        return True
    name = host.decode() if isinstance(host, bytes) else str(host)
    return (
        name in {"localhost", "0.0.0.0", "::1"}
        or name.startswith("127.")
        or name.endswith(".localhost")
    )


def _getaddrinfo(host, *args, **kwargs):
    if _is_local(host):
        return _real_getaddrinfo(host, *args, **kwargs)
    raise socket.gaierror(
        socket.EAI_NONAME, f"{host}: no network in unit tests (tests/no_network.py)"
    )


def _target(address: object) -> object:
    return address[0] if isinstance(address, tuple) else None


def _connect(self, address):
    if self.family == socket.AF_UNIX or _is_local(_target(address)):
        return _real_connect(self, address)
    raise OSError(101, f"{address}: no network in unit tests (tests/no_network.py)")


def _connect_ex(self, address):
    if self.family == socket.AF_UNIX or _is_local(_target(address)):
        return _real_connect_ex(self, address)
    return 101


socket.getaddrinfo = _getaddrinfo
socket.socket.connect = _connect
socket.socket.connect_ex = _connect_ex


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "network: a live test that needs the internet; skipped when tests/no_network.py is loaded",
    )


def pytest_collection_modifyitems(config, items):
    import pytest

    skip = pytest.mark.skip(reason="needs the internet (tests/no_network.py is loaded)")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip)
