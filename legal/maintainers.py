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
UmerOS Legal & Compliance — Maintainers & Authorship Subsystem (Appendix C)
================================================================================

Maintains cryptographic identities, signing fingerprints, and maintainer
profiles for the core architects and contributors of UmerOS.


Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3)
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
