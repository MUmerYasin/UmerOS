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

Maintains maintainer profiles for the core architects and contributors of
UmerOS.  The key-fingerprint fields are illustrative **placeholders**
(prefixed ``PLACEHOLDER:``); they are NOT derived from real key material and
must not be treated as trust anchors.


Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .creator_config import get_founder_email

#: Prefix marking a fingerprint value as an illustrative placeholder rather
#: than a real key fingerprint (H138).
PLACEHOLDER_PREFIX = "PLACEHOLDER:"


def is_placeholder_fingerprint(value: str) -> bool:
    """Return True when ``value`` is an illustrative placeholder, not a real key."""
    return not value or value.startswith(PLACEHOLDER_PREFIX)


@dataclass
class MaintainerProfile:
    """Represents a UmerOS subsystem maintainer profile.

    ``pqc_public_key_fingerprint`` and ``pgp_fingerprint`` are **illustrative
    placeholders** (prefixed with :data:`PLACEHOLDER_PREFIX`) — they are not
    derived from real key material and are not trust anchors.
    """
    name: str
    handle: str
    email: str
    role: str
    pqc_public_key_fingerprint: str
    pgp_fingerprint: str
    bio: str
    subsystems_maintained: List[str] = field(default_factory=list)

    @property
    def key_fingerprints_are_placeholders(self) -> bool:
        """True when both fingerprints are placeholders, not real key material."""
        return (is_placeholder_fingerprint(self.pqc_public_key_fingerprint)
                and is_placeholder_fingerprint(self.pgp_fingerprint))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Canonical Core Maintainers ───────────────────────────────────────────

CORE_MAINTAINERS: List[MaintainerProfile] = [
    MaintainerProfile(
        name="Muhammad Umer Yasin (Umer)",
        handle="MUmerYasin",
        # E-mail is loaded from the git-ignored creator config; the
        # default is a non-PII project address.
        email=get_founder_email(),
        role="Lead Architect & Kernel Maintainer",
        pqc_public_key_fingerprint=PLACEHOLDER_PREFIX + "DILITHIUM5:8f3a9e2b1c4d701e65fa890bc41235de",
        pgp_fingerprint=PLACEHOLDER_PREFIX + "4A9F 82C1 3E0B 9D82 17F6 448E 993B 2108 CD81 99A2",
        bio="Founder and lead architect of UmerOS, pioneering Python-first quantum-classical hybrid OS architectures.",
        subsystems_maintained=["kernel", "quantum", "qfs", "security", "fs", "hal"],
    ),
]


class MaintainerRegistry:
    """Registry of core subsystem maintainers.

    The profiles' key fingerprints are illustrative placeholders, not verified
    keys.
    """

    def __init__(self, maintainers: Optional[List[MaintainerProfile]] = None) -> None:
        self._maintainers: Dict[str, MaintainerProfile] = {}
        for m in (maintainers or CORE_MAINTAINERS):
            self._maintainers[m.handle.lower()] = m

    def get(self, handle: str) -> Optional[MaintainerProfile]:
        return self._maintainers.get(handle.lower())

    def list_all(self) -> List[MaintainerProfile]:
        return list(self._maintainers.values())
