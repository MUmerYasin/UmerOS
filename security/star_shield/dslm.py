"""Device Security Level Management (DSLM) for UmerOS Star Shield.

Classifies nodes from SL1 (Basic) to SL5 (Formally verified).
Data is labeled from S1 (Public) to S4 (Critical).
Enforces: Data Security Level <= Target Device Security Level
"""
from __future__ import annotations

import enum
import hashlib
import time
from dataclasses import dataclass
from typing import Optional


class DeviceSecurityLevel(enum.IntEnum):
    SL1 = 1  # Basic unverified user space
    SL2 = 2  # Standard runtime with integrity checks
    SL3 = 3  # Signed modules, post-quantum crypto, clean kernel taint
    SL4 = 4  # Hardware-backed credentials and verified boot
    SL5 = 5  # Formally verified / Hardware TEE


class DataSensitivity(enum.IntEnum):
    S1_PUBLIC = 1
    S2_INTERNAL = 2
    S3_CONFIDENTIAL = 3
    S4_CRITICAL = 4


@dataclass
class NodeAttestation:
    node_id: str
    security_level: DeviceSecurityLevel
    attestation_hash: str
    timestamp: float
    verified: bool = False


class DSLMAuthority:
    """Security rating engine for UmerOS Star Shield."""

    def __init__(self, local_node_id: str, local_sl: DeviceSecurityLevel = DeviceSecurityLevel.SL2) -> None:
        self.local_node_id = local_node_id
        self.local_sl = local_sl
        self._attestations: dict[str, NodeAttestation] = {}
        self._audit_log: list[dict] = []

    def attest_local(self) -> NodeAttestation:
        """Generate local node attestation."""
        att = NodeAttestation(
            node_id=self.local_node_id,
            security_level=self.local_sl,
            attestation_hash=hashlib.sha256(f"{self.local_node_id}:{self.local_sl}:{time.time()}".encode()).hexdigest(),
            timestamp=time.time(),
            verified=True,
        )
        self._attestations[self.local_node_id] = att
        return att

    def register_peer(self, node_id: str, sl: DeviceSecurityLevel, attestation_hash: str = "") -> NodeAttestation:
        """Register a peer node with its security level."""
        att = NodeAttestation(
            node_id=node_id,
            security_level=sl,
            attestation_hash=attestation_hash or hashlib.sha256(f"{node_id}:{sl}".encode()).hexdigest(),
            timestamp=time.time(),
            verified=sl >= DeviceSecurityLevel.SL3,
        )
        self._attestations[node_id] = att
        return att

    def get_peer_sl(self, node_id: str) -> Optional[DeviceSecurityLevel]:
        att = self._attestations.get(node_id)
        return att.security_level if att else None

    def can_route_data(self, data_sensitivity: DataSensitivity, target_node_id: str) -> bool:
        """Check if data can be routed to target node based on SL matching."""
        target_sl = self.get_peer_sl(target_node_id)
        if target_sl is None:
            # Unknown node - treat as SL1
            target_sl = DeviceSecurityLevel.SL1
        allowed = data_sensitivity.value <= target_sl.value
        if not allowed:
            self._audit_log.append({
                "timestamp": time.time(),
                "event": "DATA_ROUTING_DENIED",
                "data_sensitivity": data_sensitivity.name,
                "target_node": target_node_id,
                "target_sl": target_sl.name,
                "reason": f"S{data_sensitivity.value} > SL{target_sl.value}",
            })
        return allowed

    def audit_log(self) -> list[dict]:
        return list(self._audit_log)

    @property
    def peer_count(self) -> int:
        return len(self._attestations) - (1 if self.local_node_id in self._attestations else 0)