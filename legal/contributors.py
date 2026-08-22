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
UmerOS Legal & Compliance — Contributors & Attribution Subsystem
===================================================================================

Tracks, verifies, and credits contributors, open-source maintainers, and
AI engineering intelligence pairing in accordance with TLDP Appendix D and DCO.


Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


class ContributorRole(str):
    FOUNDER_AUTHOR = "Founder & Chief Architect"
    AI_PAIRING = "AI Engineering Intelligence"
    KERNEL_DEV = "Kernel & Low-Level Systems"
    SECURITY_RESEARCH = "Zero-Trust & Cryptography"
    DOCUMENTATION = "Documentation & Standards"
    COMMUNITY = "Community Contributor"


@dataclass
class ContributorRecord:
    """Represents a recognized contributor to UmerOS."""
    name: str
    role: str
    email_or_handle: str
    organization: str
    contributions: List[str] = field(default_factory=list)
    dco_signed: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Canonical Contributors Roster ─────────────────────────────────────────

CANONICAL_CONTRIBUTORS: List[ContributorRecord] = [
    ContributorRecord(
        name="Muhammad Umer Yasin (MUmerYasin)",
        role=ContributorRole.FOUNDER_AUTHOR,
        email_or_handle="mumeryasin123456789@gmail.com",
        organization="UmerOS Project",
        contributions=["OS Architecture", "Quantum-Hybrid Microkernel Design", "QFS Filesystem", "Fluidic UI"],
        dco_signed=True,
    ),
    
    ContributorRecord(
        name="The Linux Documentation Project (TLDP)",
        role=ContributorRole.DOCUMENTATION,
        email_or_handle="tldp@tldp.org",
        organization="TLDP Community",
        contributions=["Linux Filesystem Hierarchy Standard Guide", "FSSTND Specifications", "UNIX System V Documentation"],
        dco_signed=True,
    ),
    ContributorRecord(
        name="Free Standards Group / Linux Foundation",
        role=ContributorRole.DOCUMENTATION,
        email_or_handle="fhs@freestandards.org",
        organization="Linux Foundation",
        contributions=["Filesystem Hierarchy Standard (FHS 2.3 & 3.0)"],
        dco_signed=True,
    ),
]


class ContributorRegistry:
    """Registry and verification engine for UmerOS contributors."""

    def __init__(self, initial_roster: Optional[List[ContributorRecord]] = None) -> None:
        self._roster: Dict[str, ContributorRecord] = {}
        for c in (initial_roster or CANONICAL_CONTRIBUTORS):
            self._roster[c.name.lower()] = c

    def add_contributor(
        self,
        name: str,
        role: str = ContributorRole.COMMUNITY,
        email_or_handle: str = "",
        organization: str = "Independent",
        contributions: Optional[List[str]] = None,
        dco_signed: bool = True,
    ) -> ContributorRecord:
        """Registers a new contributor in the roster."""
        rec = ContributorRecord(
            name=name,
            role=role,
            email_or_handle=email_or_handle,
            organization=organization,
            contributions=contributions or [],
            dco_signed=dco_signed,
        )
        self._roster[name.lower()] = rec
        return rec

    def get_contributor(self, name: str) -> Optional[ContributorRecord]:
        return self._roster.get(name.lower())

    def list_contributors(self) -> List[ContributorRecord]:
        return list(self._roster.values())

    def verify_dco(self, name: str) -> bool:
        """Verifies if a contributor has signed the Developer Certificate of Origin."""
        c = self.get_contributor(name)
        return bool(c and c.dco_signed)

    def generate_acknowledgements_md(self) -> str:
        """Generates a formatted markdown document of all contributors."""
        lines = [
            "# UmerOS Project Contributors & Acknowledgements",
            "",
            "We gratefully acknowledge the foundational contributions of the following individuals and organizations:",
            "",
        ]
        for c in self._roster.values():
            dco_str = " (DCO Certified)" if c.dco_signed else ""
            lines.append(f"### {c.name}{dco_str}")
            lines.append(f"- **Role:** {c.role}")
            lines.append(f"- **Organization:** {c.organization}")
            if c.email_or_handle:
                lines.append(f"- **Contact:** `{c.email_or_handle}`")
            if c.contributions:
                lines.append(f"- **Key Contributions:** {', '.join(c.contributions)}")
            lines.append("")
        return "\n".join(lines)
