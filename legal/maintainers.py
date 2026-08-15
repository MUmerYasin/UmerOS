"""
UmerOS Legal & Compliance — Maintainers & Authorship Subsystem (TLDP Appendix C)
================================================================================

Maintains cryptographic identities, signing fingerprints, and maintainer
profiles for the core architects and contributors of UmerOS.


Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MaintainerProfile:
    """Represents a verified UmerOS subsystem maintainer."""
    name: str
    handle: str
    email: str
    role: str
    pqc_public_key_fingerprint: str
    pgp_fingerprint: str
    bio: str
    subsystems_maintained: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Canonical Core Maintainers ───────────────────────────────────────────

CORE_MAINTAINERS: List[MaintainerProfile] = [
    MaintainerProfile(
        name="Muhammad Umer Yasin (Umer)",
        handle="MUmerYasin",
        email="mumeryasin123456789@gmail.com",
        role="Lead Architect & Kernel Maintainer",
        pqc_public_key_fingerprint="DILITHIUM5:8f3a9e2b1c4d701e65fa890bc41235de",
        pgp_fingerprint="4A9F 82C1 3E0B 9D82 17F6 448E 993B 2108 CD81 99A2",
        bio="Founder and lead architect of UmerOS, pioneering Python-first quantum-classical hybrid OS architectures.",
        subsystems_maintained=["kernel", "quantum", "qfs", "security", "fs", "hal"],
    ),
]


class MaintainerRegistry:
    """Registry of trusted core subsystem maintainers."""

    def __init__(self, maintainers: Optional[List[MaintainerProfile]] = None) -> None:
        self._maintainers: Dict[str, MaintainerProfile] = {}
        for m in (maintainers or CORE_MAINTAINERS):
            self._maintainers[m.handle.lower()] = m

    def get(self, handle: str) -> Optional[MaintainerProfile]:
        return self._maintainers.get(handle.lower())

    def list_all(self) -> List[MaintainerProfile]:
        return list(self._maintainers.values())
