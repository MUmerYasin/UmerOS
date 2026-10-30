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
UmerOS Distributed Soft Bus Manager (DSoftBus).

Orchestrates peer discovery, session channel management, frame encoding/decoding,
and message dispatching between interconnected UmerOS nodes.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from network.softbus.discovery import SoftBusDiscovery, SoftBusPeer
from network.softbus.session import SoftBusFrame, SoftBusSession

log = logging.getLogger("UmerOS.Network.SoftBus.Manager")


class SoftBusManager:
    """Central management and routing engine for UmerSoftBus."""

    def __init__(
        self,
        node_name: str = "UmerOS-Station",
        device_class: str = "Desktop",
        shared_secret: bytes = b"umeros_softbus_mesh_secret_2026",
    ) -> None:
        self.discovery: SoftBusDiscovery = SoftBusDiscovery(
            node_name=node_name,
            device_class=device_class,
        )
        self.session: SoftBusSession = SoftBusSession(shared_secret=shared_secret)
        self._handlers: Dict[int, List[Callable[[SoftBusPeer, bytes], Any]]] = {}
        self._msg_counter: int = 1
        self._lock = asyncio.Lock()

    @property
    def node_id(self) -> str:
        return self.discovery.node_id

    @property
    def node_name(self) -> str:
        return self.discovery.node_name

    def register_handler(
        self,
        msg_type: int,
        handler: Callable[[SoftBusPeer, bytes], Any],
    ) -> None:
        """Register a callback for a specific message type."""
        if msg_type not in self._handlers:
            self._handlers[msg_type] = []
        if handler not in self._handlers[msg_type]:
            self._handlers[msg_type].append(handler)

    def unregister_handler(
        self,
        msg_type: int,
        handler: Callable[[SoftBusPeer, bytes], Any],
    ) -> None:
        """Unregister a message handler."""
        if msg_type in self._handlers and handler in self._handlers[msg_type]:
            self._handlers[msg_type].remove(handler)
            if not self._handlers[msg_type]:
                del self._handlers[msg_type]

    async def send_to_peer(
        self,
        peer: SoftBusPeer,
        msg_type: int,
        payload: bytes,
    ) -> bytes:
        """Encode and frame a message targeted at a peer.

        Returns:
            The raw encoded binary SoftBus frame bytes ready for transport.
        """
        async with self._lock:
            msg_id = self._msg_counter
            self._msg_counter += 1

        frame_bytes = self.session.encode_frame(
            msg_type=msg_type,
            msg_id=msg_id,
            payload=payload,
        )
        log.debug(
            "SoftBus: prepared frame %d (type=%d, size=%dB) for peer %s (%s)",
            msg_id,
            msg_type,
            len(payload),
            peer.node_name,
            peer.node_id,
        )
        return frame_bytes

    async def handle_incoming_frame(
        self,
        frame_bytes: bytes,
        sender_host: str,
    ) -> Optional[SoftBusFrame]:
        """Decode, verify, and dispatch an incoming binary SoftBus frame.

        Args:
            frame_bytes: Raw received frame bytes.
            sender_host: Network IP of the sender.

        Returns:
            Decoded SoftBusFrame if valid, None if invalid or tampered.
        """
        is_valid, frame = self.session.decode_frame(frame_bytes)
        if not is_valid or frame is None or not frame.is_valid:
            log.warning("SoftBus: dropped invalid or tampered frame from %s", sender_host)
            return None

        # Resolve or create dummy peer info for dispatch
        active_peers = await self.discovery.get_peers()
        peer = next((p for p in active_peers if p.host == sender_host), None)
        if peer is None:
            peer = SoftBusPeer(
                node_id="unknown_peer",
                node_name=f"Peer@{sender_host}",
                host=sender_host,
            )

        handlers = self._handlers.get(frame.msg_type, [])
        for handler in handlers:
            try:
                res = handler(peer, frame.payload)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as exc:  # noqa: BLE001
                log.error("SoftBus handler error for msg_type %d: %s", frame.msg_type, exc)

        return frame

    async def get_mesh_status(self) -> Dict[str, Any]:
        """Return summary of the local node and all discovered mesh peers."""
        peers = await self.discovery.get_peers()
        return {
            "local_node": {
                "node_id": self.node_id,
                "node_name": self.node_name,
                "device_class": self.discovery.device_class,
                "capabilities": self.discovery.capabilities,
            },
            "peers_count": len(peers),
            "peers": [p.to_dict() for p in peers],
            "registered_handlers": list(self._handlers.keys()),
        }
