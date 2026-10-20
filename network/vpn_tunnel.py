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

#!/usr/bin/env python3
"""VPN tunnel abstraction for UmerOS.

TODAY:
    Provides a safe simulation interface for encrypted tunnel flows and can use
    a supplied crypto engine object.

EXPERIMENTAL:
    A real WireGuard wrapper lives in ``network_stack.VPNClient``.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging
import secrets
from typing import Any, Optional

log = logging.getLogger("UmerOS.Network.VPN")


class VPNTunnel:
    """Simulated encrypted network tunnel.

    The fallback mode does not provide real encryption. It is intentionally
    labeled as simulation so UmerOS never claims cryptographic protection that
    is not actually present.
    """

    def __init__(
        self,
        crypto_engine: Optional[Any] = None,
        *,
        allow_simulation: bool = False,
    ) -> None:
        """Initialize the tunnel.

        Args:
            crypto_engine: Optional object with ``random_bytes``, ``encrypt``,
                and ``decrypt`` methods.  **Required for real transport.**
            allow_simulation: Explicit opt-in to the reversible-XOR frame
                transform.  Without it, ``send()``/``receive()`` refuse to
                run rather than silently producing malleable output.

        the default used to be "no engine, fall back to XOR", so a
        caller that forgot to inject a crypto engine got bytes that look
        encrypted and are not.  XOR with a repeating key is malleable and
        known-plaintext-recoverable, so it must never be the silent
        default -- it is now reachable only via an explicit opt-in.
        """
        self.crypto = crypto_engine
        self.allow_simulation = allow_simulation
        self.connected = False
        self.peer_address: str | None = None
        self.session_key: bytes | None = None

    def connect(self, peer: str, port: int = 51820) -> bool:
        """Establish a simulated tunnel to a peer."""
        if not peer.strip():
            raise ValueError("peer must not be empty")
        self.peer_address = f"{peer.strip()}:{port}"
        self.session_key = self._random_bytes(32)
        self.connected = True
        log.info("VPN tunnel connected to %s", self.peer_address)
        return True

    def send(self, data: bytes) -> bytes:
        """Encrypt or frame data for transport through the tunnel."""
        self._require_transport()
        if self.crypto and hasattr(self.crypto, "encrypt"):
            encrypted = self.crypto.encrypt(data)
            if isinstance(encrypted, tuple):
                _nonce, ciphertext = encrypted
                return ciphertext
            return encrypted
        return self._xor_frame(data)

    def receive(self, ciphertext: bytes, nonce: bytes | None = None) -> bytes:
        """Decrypt or unframe data received from the tunnel."""
        self._require_transport()
        if self.crypto and hasattr(self.crypto, "decrypt"):
            if nonce is not None:
                return self.crypto.decrypt(nonce, ciphertext)
            return self.crypto.decrypt(ciphertext)
        return self._xor_frame(ciphertext)

    def disconnect(self) -> None:
        """Close the simulated tunnel and erase session material."""
        log.info("VPN tunnel disconnected from %s", self.peer_address)
        self.connected = False
        self.peer_address = None
        self.session_key = None

    def status(self) -> dict:
        """Return tunnel status.

        ``mode`` now distinguishes an *opted-in* simulation from a
        missing engine, so a status dump cannot mislead an operator into
        thinking a well-configured tunnel is running.
        """
        if self.crypto is not None:
            mode = "crypto-engine"
        elif self.allow_simulation:
            mode = "simulation"
        else:
            mode = "no-crypto-engine"
        return {
            "connected": self.connected,
            "peer": self.peer_address,
            "mode": mode,
        }

    def _random_bytes(self, length: int) -> bytes:
        """Get random bytes from the crypto engine or the standard library."""
        if self.crypto and hasattr(self.crypto, "random_bytes"):
            return self.crypto.random_bytes(length)
        return secrets.token_bytes(length)

    def _xor_frame(self, data: bytes) -> bytes:
        """Simulation-only reversible frame transform."""
        if not self.session_key:
            raise ConnectionError("VPN tunnel has no session key")
        key = self.session_key
        return bytes(byte ^ key[index % len(key)] for index, byte in enumerate(data))

    def _require_transport(self) -> None:
        """Fail closed unless real crypto (or an explicit opt-in) is present.

        ``send()``/``receive()`` used to fall back to the reversible
        XOR frame silently when no ``crypto_engine`` was injected.  That is a
        footgun: the output is indistinguishable from ciphertext to the
        caller but is malleable and known-plaintext-recoverable.  The
        fallback is now reachable only when the caller explicitly passed
        ``allow_simulation=True``.
        """
        if not self.connected:
            raise ConnectionError("VPN tunnel not connected")
        if self.crypto is None and not self.allow_simulation:
            raise PermissionError(
                "VPNTunnel has no crypto_engine, so send()/receive() would "
                "use the reversible XOR simulation frame -- malleable and "
                "known-plaintext-recoverable.  Supply a crypto_engine, or "
                "construct VPNTunnel(..., allow_simulation=True) to opt in "
                "explicitly."
            )


class _CryptoEngineStub:
    """Minimal engine used only by :func:`_selftest`."""

    def random_bytes(self, length: int) -> bytes:
        return b"\x01" * length

    def encrypt(self, data: bytes):
        return b"nonce", b"CIPHER:" + data

    def decrypt(self, ciphertext: bytes) -> bytes:
        if ciphertext.startswith(b"CIPHER:"):
            return ciphertext[len(b"CIPHER:"):]
        raise ValueError("not our frame")


def _selftest() -> bool:
    """Exercise the gate and the engine / opt-in paths."""
    # Default construction must refuse to produce malleable output.
    default = VPNTunnel()
    default.connect("peer.example")
    if default.status()["mode"] != "no-crypto-engine":
        print("default status should report no-crypto-engine")
        return False
    try:
        default.send(b"payload")
        print("default send() must refuse without a crypto engine or opt-in")
        return False
    except PermissionError:
        pass
    try:
        default.receive(b"payload")
        print("default receive() must refuse without a crypto engine or opt-in")
        return False
    except PermissionError:
        pass

    # A real engine must take precedence.
    real = VPNTunnel(crypto_engine=_CryptoEngineStub())
    real.connect("peer.example")
    if real.status()["mode"] != "crypto-engine":
        print("default status should report crypto-engine")
        return False
    framed = real.send(b"payload")
    if framed != b"CIPHER:payload":
        print(f"engine path produced {framed!r}")
        return False
    if real.receive(framed) != b"payload":
        print("engine round-trip failed")
        return False

    # Explicit opt-in must keep the documented simulation usable.
    sim = VPNTunnel(allow_simulation=True)
    sim.connect("peer.example")
    if sim.status()["mode"] != "simulation":
        print("opt-in status should report simulation")
        return False
    sim_framed = sim.send(b"payload")
    if sim.receive(sim_framed) != b"payload":
        print("simulation round-trip failed")
        return False

    # An engine *and* an opt-in still prefers the engine.
    both = VPNTunnel(crypto_engine=_CryptoEngineStub(), allow_simulation=True)
    both.connect("peer.example")
    if both.send(b"payload") != b"CIPHER:payload":
        print("engine should win over the opt-in")
        return False

    print("vpn_tunnel selftest: OK")
    return True


if __name__ == "__main__":
    import sys as _sys

    _sys.exit(0 if _selftest() else 1)
