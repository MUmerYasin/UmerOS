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

"""H179 tests — the reversible-XOR fallback is an explicit opt-in.

``network/vpn_tunnel.py::VPNTunnel`` used to fall back to a repeating-key XOR
frame transform whenever no ``crypto_engine`` was injected.  XOR with a
repeating key is malleable and known-plaintext-recoverable, and the output is
indistinguishable from ciphertext to the caller — so a forgotten engine
produced bytes that *look* encrypted and are not.

The fallback is preserved (the module is deliberately a documented simulation
and that is useful for tests), but it is now reachable only via an explicit
``allow_simulation=True``.  These tests pin the gate, the precedence rules and
the status reporting.
"""

from __future__ import annotations

import pytest

from network.vpn_tunnel import VPNTunnel


class FakeCrypto:
    """A stand-in real engine: nonce/ct tuple, functions the stub encrypt/decrypt."""

    def random_bytes(self, length: int) -> bytes:
        return b"\x01" * length

    def encrypt(self, data: bytes):
        return b"nonce", b"CIPHER:" + data

    def decrypt(self, ciphertext: bytes) -> bytes:
        if not ciphertext.startswith(b"CIPHER:"):
            raise ValueError("not our frame")
        return ciphertext[len(b"CIPHER:"):]


# -- the default path is fail-closed ---------------------------------------


def test_default_construction_refuses_send():
    t = VPNTunnel()
    t.connect("peer.example")
    with pytest.raises(PermissionError):
        t.send(b"payload")


def test_default_construction_refuses_receive():
    t = VPNTunnel()
    t.connect("peer.example")
    with pytest.raises(PermissionError):
        t.receive(b"payload")


def test_default_status_reports_no_crypto_engine():
    t = VPNTunnel()
    t.connect("peer.example")
    assert t.status()["mode"] == "no-crypto-engine"


def test_not_connected_still_raises_connection_error():
    """The pre-existing guard must not be shadowed by the new one."""
    t = VPNTunnel(allow_simulation=True)
    with pytest.raises(ConnectionError):
        t.send(b"payload")


def test_not_connected_error_wins_even_without_an_engine():
    """Connection state is checked before the crypto question."""
    t = VPNTunnel()
    with pytest.raises(ConnectionError):
        t.send(b"payload")


def test_default_connect_still_works():
    """Gating the *transport* must not break tunnel setup."""
    t = VPNTunnel()
    assert t.connect("peer.example") is True
    assert t.status()["connected"] is True


def test_empty_peer_still_rejected():
    with pytest.raises(ValueError):
        VPNTunnel().connect("   ")


# -- a real engine takes precedence ----------------------------------------


def test_engine_path_produces_ciphertext():
    t = VPNTunnel(crypto_engine=FakeCrypto())
    t.connect("peer.example")
    framed = t.send(b"payload")
    assert framed == b"CIPHER:payload"
    assert framed != b"payload"


def test_engine_round_trip():
    t = VPNTunnel(crypto_engine=FakeCrypto())
    t.connect("peer.example")
    assert t.receive(t.send(b"payload")) == b"payload"


def test_engine_status_reports_crypto_engine():
    t = VPNTunnel(crypto_engine=FakeCrypto())
    t.connect("peer.example")
    assert t.status()["mode"] == "crypto-engine"


def test_engine_does_not_need_the_opt_in():
    """A real engine must never require `allow_simulation`."""
    t = VPNTunnel(crypto_engine=FakeCrypto())
    t.connect("peer.example")
    assert t.send(b"payload")  # no PermissionError


def test_engine_wins_over_an_explicit_opt_in():
    t = VPNTunnel(crypto_engine=FakeCrypto(), allow_simulation=True)
    t.connect("peer.example")
    assert t.send(b"payload") == b"CIPHER:payload"


# -- the opt-in keeps the documented simulation usable ----------------------


def test_opt_in_allows_the_simulation():
    t = VPNTunnel(allow_simulation=True)
    t.connect("peer.example")
    framed = t.send(b"payload")
    assert framed != b"payload"  # still transformed
    assert t.receive(framed) == b"payload"  # and reversible


def test_opt_in_status_reports_simulation():
    t = VPNTunnel(allow_simulation=True)
    t.connect("peer.example")
    assert t.status()["mode"] == "simulation"


def test_opt_in_is_keyword_only():
    """Positional misuse must not silently enable the XOR fallback."""
    with pytest.raises(TypeError):
        VPNTunnel(None, True)  # noqa: B018 -- positional not allowed


# -- nothing else regressed ------------------------------------------------


def test_disconnect_clears_state():
    t = VPNTunnel(allow_simulation=True)
    t.connect("peer.example")
    t.disconnect()
    assert t.status() == {"connected": False, "peer": None, "mode": "simulation"}


def test_xor_frame_requires_a_session_key():
    t = VPNTunnel(allow_simulation=True)
    with pytest.raises(ConnectionError):
        t._xor_frame(b"data")  # never connected -> no session key


def test_session_key_is_random_per_tunnel():
    a, b = VPNTunnel(allow_simulation=True), VPNTunnel(allow_simulation=True)
    a.connect("peer.example")
    b.connect("peer.example")
    assert a.session_key != b.session_key


def test_package_still_exports_vpntunnel():
    import network

    assert network.VPNTunnel is VPNTunnel


def test_selftest_passes():
    """`python -m network.vpn_tunnel` must exit 0."""
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "network.vpn_tunnel"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert "selftest: OK" in proc.stdout
