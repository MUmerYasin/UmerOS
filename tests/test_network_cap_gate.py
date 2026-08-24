# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
pytest suite proving the zero-trust capability gate is wired into the network
egress paths and that SSRF destination filtering is enforced (cap-gate cluster:
H177 network egress, H178 server-side request forgery).

Proves, per wired module:
  * H177  - HTTP egress (HTTPClient.request) and DNS egress (DNSResolver.
            resolve_all / reverse_lookup) raise PermissionError when the calling
            process LACKS CAP_NET_SEND under a real CapabilityManager, and
            succeed once the capability is granted.
  * H178  - When the zero-trust posture is active (manager wired OR strict mode)
            the egress client refuses internal / loopback / link-local /
            reserved / multicast destinations (SSRF), while a permissive
            standalone/dev build keeps loopback working (mirroring the project's
            "permissive when unwired" convention).

Mirror of tests/test_cap_gate.py / tests/test_proc_cap_gate.py: a real kernel
CapabilityManager is wired into a fresh CapabilityGate, and the module-level
``gate`` name is patched for the duration of each test, then restored.
"""

import asyncio
import os
import sys
from pathlib import Path

import pytest

_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from core.capability_gate import (  # noqa: E402
    CAP_NET_SEND,
    CapabilityGate,
)
from kernel.capability_manager import CapabilityManager  # noqa: E402

from network.dns_resolver import DNSResolver  # noqa: E402
from network.http_client import HTTPClient, HTTPResponse  # noqa: E402
from network.network_stack import NetworkStack, VPNClient  # noqa: E402
from network.tcp_server import TCPClient  # noqa: E402


def _make_wired_gate(pid: int, caps) -> CapabilityGate:
    """Build a gate wired to a real CapabilityManager that grants `caps` to `pid`."""
    cm = CapabilityManager()
    cm.register(pid)
    for c in caps:
        cm.grant(pid, c)
    g = CapabilityGate()
    g.wire(cm)
    return g


def _mock_transport(client: HTTPClient, status: int = 200, body_text: str = "ok") -> None:
    """Replace the real HTTP backend with a canned response (no real socket)."""

    async def _fake(method, url, body, headers):
        return HTTPResponse(status, body_text, {}, url)

    client._aiohttp_available = False
    client._request_urllib = _fake


# ── H177 — HTTP egress requires CAP_NET_SEND ─────────────────────────────────

def test_http_request_denied_without_cap():
    import network.http_client as mod

    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[])  # current pid lacks net.send
    try:
        client = HTTPClient()
        _mock_transport(client)
        with pytest.raises(PermissionError):
            asyncio.run(client.get("http://1.1.1.1/"))
    finally:
        mod.gate = prev


def test_http_request_allowed_with_cap():
    import network.http_client as mod

    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[CAP_NET_SEND])
    try:
        client = HTTPClient()
        _mock_transport(client)
        resp = asyncio.run(client.get("http://1.1.1.1/"))
        assert resp["status"] == 200  # gated op proceeds when authorized
    finally:
        mod.gate = prev


# ── H177 — DNS egress requires CAP_NET_SEND ──────────────────────────────────

def test_dns_resolve_denied_without_cap():
    import network.dns_resolver as mod

    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[])
    try:
        resolver = DNSResolver()
        with pytest.raises(PermissionError):
            asyncio.run(resolver.resolve_all("example.com"))
    finally:
        mod.gate = prev


def test_dns_resolve_allowed_with_cap():
    import network.dns_resolver as mod

    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[CAP_NET_SEND])
    try:
        resolver = DNSResolver()
        # Literal IP short-circuits before any real getaddrinfo call.
        out = asyncio.run(resolver.resolve_all("1.1.1.1"))
        assert out == ["1.1.1.1"]
    finally:
        mod.gate = prev


def test_dns_reverse_lookup_denied_without_cap():
    """reverse_lookup is also egress -> must be gated (H177 symmetry)."""
    import network.dns_resolver as mod

    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[])
    try:
        resolver = DNSResolver()
        with pytest.raises(PermissionError):
            asyncio.run(resolver.reverse_lookup("8.8.8.8"))
    finally:
        mod.gate = prev


def test_dns_reverse_lookup_validates_input_before_gate():
    """A malformed IP must raise ValueError regardless of the gate state."""
    import network.dns_resolver as mod

    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[CAP_NET_SEND])
    try:
        resolver = DNSResolver()
        with pytest.raises(ValueError):
            asyncio.run(resolver.reverse_lookup("not-an-ip"))
    finally:
        mod.gate = prev


# ── H178 — SSRF: refuse internal destinations when the posture is active ─────

def test_ssrf_enforced_in_strict_build():
    """With strict mode on, internal hosts are refused at URL validation (H178)."""
    import network.http_client as mod

    prev = mod.gate
    g = CapabilityGate()
    g.set_strict(True)  # enforcing without a manager
    mod.gate = g
    try:
        client = HTTPClient()
        for internal in (
            "http://127.0.0.1/",
            "http://10.0.0.1/",
            "http://192.168.1.1/",
            "http://169.254.169.254/",  # cloud metadata / link-local
            "http://[::1]/",            # IPv6 loopback
        ):
            with pytest.raises(ValueError):
                client._validate_url(internal)
        # A public literal is still allowed.
        client._validate_url("http://1.1.1.1/")
    finally:
        mod.gate = prev


def test_ssrf_relaxed_in_permissive_build():
    """A permissive/standalone build keeps loopback working (dev convenience)."""
    import network.http_client as mod

    prev = mod.gate
    g = CapabilityGate()
    g.set_strict(False)  # explicit permissive (mirrors default unwired dev build)
    mod.gate = g
    try:
        client = HTTPClient()
        # loopback + port must be accepted without raising.
        assert (
            client._validate_url("http://127.0.0.1:8080/status")
            == "http://127.0.0.1:8080/status"
        )
        client._validate_url("http://[::1]/")  # no raise
    finally:
        mod.gate = prev


def test_ssrf_blocks_internal_end_to_end_when_enforcing():
    """Even with CAP_NET_SEND held, internal destinations are refused (H178)."""
    import network.http_client as mod

    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[CAP_NET_SEND])  # enforcing + cap held
    try:
        client = HTTPClient()
        _mock_transport(client)
        for internal in (
            "http://127.0.0.1/",
            "http://10.0.0.1/",
            "http://169.254.169.254/",
            "http://[::1]/",
        ):
            with pytest.raises(ValueError):
                asyncio.run(client.get(internal))
    finally:
        mod.gate = prev


def test_ssrf_allows_public_end_to_end_when_enforcing():
    """With CAP_NET_SEND held and a public host, egress proceeds (H177+H178)."""
    import network.http_client as mod

    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[CAP_NET_SEND])
    try:
        client = HTTPClient()
        _mock_transport(client)
        resp = asyncio.run(client.get("http://1.1.1.1/"))
        assert resp["status"] == 200
    finally:
        mod.gate = prev


# ── Control — egress is permitted in a permissive (unwired) build ────────────

def test_egress_permissive_when_unwired():
    """Default dev build: egress allowed, mirroring existing loopback tests."""
    import network.dns_resolver as dns_mod
    import network.http_client as http_mod

    p1, p2 = http_mod.gate, dns_mod.gate
    g = CapabilityGate()
    g.set_strict(False)  # explicit permissive
    http_mod.gate = g
    dns_mod.gate = g
    try:
        client = HTTPClient()
        _mock_transport(client)
        resp = asyncio.run(client.get("http://1.1.1.1/"))
        assert resp["status"] == 200
        resolver = DNSResolver()
        assert asyncio.run(resolver.resolve_all("1.1.1.1")) == ["1.1.1.1"]
    finally:
        http_mod.gate = p1
        dns_mod.gate = p2


# ── H177 — raw TCP / VPN egress requires CAP_NET_SEND ────────────────────────

def test_tcp_client_connect_denied_without_cap():
    import network.tcp_server as mod

    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[])
    try:
        client = TCPClient()
        with pytest.raises(PermissionError):
            asyncio.run(client.connect("127.0.0.1", 9))
    finally:
        mod.gate = prev


def test_network_stack_send_tcp_denied_without_cap():
    import network.network_stack as mod

    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[])
    try:
        stack = NetworkStack()
        with pytest.raises(PermissionError):
            asyncio.run(stack.send_tcp("127.0.0.1", 9, b"x"))
    finally:
        mod.gate = prev


def test_vpn_client_connect_denied_without_cap():
    import network.network_stack as mod

    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[])
    try:
        vpn = VPNClient()
        with pytest.raises(PermissionError):
            vpn.connect("/etc/wireguard/wg0.conf")
    finally:
        mod.gate = prev
