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
UmerOS Distributed Soft Bus - Peer Discovery (DSoftBus).

Provides zero-configuration automatic discovery of nearby UmerOS instances
over local area networks (Wi-Fi, Ethernet, virtual bridges) using UDP broadcast/multicast.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Callable, Dict, List, Optional

log = logging.getLogger("UmerOS.Network.SoftBus.Discovery")

DEFAULT_DISCOVERY_PORT: int = 48899
BEACON_INTERVAL_SECONDS: float = 2.0
PEER_TTL_SECONDS: float = 6.0


@dataclass
class SoftBusPeer:
    """Represents a discovered UmerOS node on the network."""

    node_id: str
    node_name: str
    device_class: str = "Desktop"
    host: str = "127.0.0.1"
    port: int = 8420
    capabilities: List[str] = field(default_factory=lambda: ["quantum", "ai", "fs"])
    last_seen: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SoftBusPeer:
        return cls(
            node_id=data["node_id"],
            node_name=data["node_name"],
            device_class=data.get("device_class", "Desktop"),
            host=data.get("host", "127.0.0.1"),
            port=data.get("port", 8420),
            capabilities=data.get("capabilities", []),
            last_seen=time.time(),
        )


class SoftBusDiscovery:
    """Peer discovery agent using UDP broadcast and dynamic peer caching."""

    def __init__(
        self,
        node_name: str = "UmerOS-Node",
        device_class: str = "Workstation",
        listen_port: int = DEFAULT_DISCOVERY_PORT,
        broadcast_port: int = DEFAULT_DISCOVERY_PORT,
    ) -> None:
        self.node_id: str = str(uuid.uuid4())
        self.node_name: str = node_name
        self.device_class: str = device_class
        self.listen_port: int = listen_port
        self.broadcast_port: int = broadcast_port
        self.capabilities: List[str] = ["quantum", "ai", "dfs", "softbus"]

        self._peers: Dict[str, SoftBusPeer] = {}
        self._running: bool = False
        self._lock: asyncio.Lock = asyncio.Lock()
        self._listeners: List[Callable[[SoftBusPeer], None]] = []

    def make_beacon(self) -> bytes:
        """Construct the JSON beacon payload."""
        payload = {
            "magic": "UMEROS_SOFTBUS_V1",
            "node_id": self.node_id,
            "node_name": self.node_name,
            "device_class": self.device_class,
            "port": self.listen_port,
            "capabilities": self.capabilities,
            "timestamp": time.time(),
        }
        return json.dumps(payload).encode("utf-8")

    def parse_beacon(self, data: bytes, sender_host: str) -> Optional[SoftBusPeer]:
        """Validate and parse a received beacon."""
        try:
            parsed = json.loads(data.decode("utf-8"))
            if parsed.get("magic") != "UMEROS_SOFTBUS_V1":
                return None
            if parsed.get("node_id") == self.node_id:
                return None  # Ignore self-broadcast

            peer = SoftBusPeer(
                node_id=parsed["node_id"],
                node_name=parsed.get("node_name", "Unknown"),
                device_class=parsed.get("device_class", "Node"),
                host=sender_host,
                port=int(parsed.get("port", self.listen_port)),
                capabilities=parsed.get("capabilities", []),
                last_seen=time.time(),
            )
            return peer
        except Exception as exc:  # noqa: BLE001
            log.debug("Discarding malformed softbus beacon: %s", exc)
            return None

    async def register_peer(self, peer: SoftBusPeer) -> None:
        """Register or refresh a discovered peer."""
        async with self._lock:
            is_new = peer.node_id not in self._peers
            self._peers[peer.node_id] = peer

        if is_new:
            log.info("Discovered new UmerSoftBus peer: %s (%s@%s)", peer.node_name, peer.node_id, peer.host)
            for listener in list(self._listeners):
                try:
                    listener(peer)
                except Exception as exc:  # noqa: BLE001
                    log.warning("Peer discovery listener failed: %s", exc)

    async def evict_stale_peers(self, ttl: float = PEER_TTL_SECONDS) -> int:
        """Remove peers that have not refreshed within the TTL window."""
        now = time.time()
        evicted = 0
        async with self._lock:
            stale_ids = [nid for nid, p in self._peers.items() if (now - p.last_seen) > ttl]
            for nid in stale_ids:
                del self._peers[nid]
                evicted += 1
        if evicted > 0:
            log.debug("Evicted %d stale SoftBus peer(s)", evicted)
        return evicted

    async def get_peers(self) -> List[SoftBusPeer]:
        """Return list of all currently active peers (after evicting stale ones)."""
        await self.evict_stale_peers()
        async with self._lock:
            return list(self._peers.values())

    def peer_count(self) -> int:
        """Return active peer count."""
        return len(self._peers)

    def on_peer_discovered(self, callback: Callable[[SoftBusPeer], None]) -> None:
        """Add a callback invoked whenever a new peer is discovered."""
        if callback not in self._listeners:
            self._listeners.append(callback)
