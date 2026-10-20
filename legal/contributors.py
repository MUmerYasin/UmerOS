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

Tracks and credits contributors, open-source maintainers, and AI engineering
intelligence pairing, and records their **declared** Developer Certificate of
Origin (DCO) status.  DCO status here is a recorded declaration, not a
cryptographic verification.


Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .creator_config import get_founder_contact


class ContributorRole(str):
    FOUNDER_AUTHOR = "Founder & Chief Architect"
    AI_PAIRING = "AI Engineering Intelligence"
    KERNEL_DEV = "Kernel & Low-Level Systems"
    SECURITY_RESEARCH = "Zero-Trust & Cryptography"
    DOCUMENTATION = "Documentation & Standards"
    COMMUNITY = "Community Contributor"


@dataclass
class ContributorRecord:
    """Represents a recognized contributor to UmerOS.

    ``dco_flag`` records whether the contributor has *declared* acceptance of
    the Developer Certificate of Origin (e.g. a ``Signed-off-by`` trailer or a
    CLA on file).  It is a recorded **declaration**, not a cryptographic
    verification — see :meth:`ContributorRegistry.has_dco_declaration`.
    """
    name: str
    role: str
    email_or_handle: str
    organization: str
    contributions: List[str] = field(default_factory=list)
    #: Declared DCO acceptance. Fail-closed default: NOT assumed signed.
    dco_flag: bool = False

    @property
    def dco_signed(self) -> bool:
        """Legacy alias for :attr:`dco_flag` (the old name over-claimed)."""
        return self.dco_flag

    @dco_signed.setter
    def dco_signed(self, value: bool) -> None:
        self.dco_flag = bool(value)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Canonical Contributors Roster ─────────────────────────────────────────

CANONICAL_CONTRIBUTORS: List[ContributorRecord] = [
    ContributorRecord(
        name="Muhammad Umer Yasin (MUmerYasin)",
        role=ContributorRole.FOUNDER_AUTHOR,
        # Contact is loaded from the git-ignored creator config; the
        # default is a non-PII public handle.
        email_or_handle=get_founder_contact(),
        organization="UmerOS Project",
        contributions=["OS Architecture", "Quantum-Hybrid Microkernel Design", "QFS Filesystem", "Fluidic UI"],
        dco_flag=True,
    ),
    
    ContributorRecord(
        name="The Linux Documentation Project (TLDP)",
        role=ContributorRole.DOCUMENTATION,
        email_or_handle="tldp@tldp.org",
        organization="TLDP Community",
        contributions=["Linux Filesystem Hierarchy Standard Guide", "FSSTND Specifications", "UNIX System V Documentation"],
        dco_flag=True,
    ),
    ContributorRecord(
        name="Free Standards Group / Linux Foundation",
        role=ContributorRole.DOCUMENTATION,
        email_or_handle="fhs@freestandards.org",
        organization="Linux Foundation",
        contributions=["Filesystem Hierarchy Standard (FHS 2.3 & 3.0)"],
        dco_flag=True,
    ),
]


class ContributorRegistry:
    """Roster of UmerOS contributors and their **declared** DCO status.

    This class records whether a contributor has *declared* acceptance of the
    Developer Certificate of Origin; it does **not** cryptographically verify a
    signed DCO/CLA.  The flag is therefore named ``dco_flag`` and the query is
    :meth:`has_dco_declaration`.
    """

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
        dco_flag: bool = False,
    ) -> ContributorRecord:
        """Registers a new contributor in the roster.

        ``dco_flag`` defaults to ``False``: a new contributor is **not**
        assumed to have accepted the DCO (fail-closed).
        """
        rec = ContributorRecord(
            name=name,
            role=role,
            email_or_handle=email_or_handle,
            organization=organization,
            contributions=contributions or [],
            dco_flag=dco_flag,
        )
        self._roster[name.lower()] = rec
        return rec

    def get_contributor(self, name: str) -> Optional[ContributorRecord]:
        return self._roster.get(name.lower())

    def list_contributors(self) -> List[ContributorRecord]:
        return list(self._roster.values())

    def has_dco_declaration(self, name: str) -> bool:
        """Return whether ``name`` has a **declared** DCO acceptance on record.

        This reports a recorded declaration; it is NOT a cryptographic
        signature check.
        """
        c = self.get_contributor(name)
        return bool(c and c.dco_flag)

    def verify_dco(self, name: str) -> bool:
        """Deprecated alias for :meth:`has_dco_declaration`.

        The old name over-claimed: nothing is *verified* here, only a
        declaration is reported.
        """
        return self.has_dco_declaration(name)

    def generate_acknowledgements_md(self) -> str:
        """Generates a formatted markdown document of all contributors."""
        lines = [
            "# UmerOS Project Contributors & Acknowledgements",
            "",
            "We gratefully acknowledge the foundational contributions of the following individuals and organizations:",
            "",
        ]
        for c in self._roster.values():
            dco_str = " (DCO declared)" if c.dco_flag else ""
            lines.append(f"### {c.name}{dco_str}")
            lines.append(f"- **Role:** {c.role}")
            lines.append(f"- **Organization:** {c.organization}")
            if c.email_or_handle:
                lines.append(f"- **Contact:** `{c.email_or_handle}`")
            if c.contributions:
                lines.append(f"- **Key Contributions:** {', '.join(c.contributions)}")
            lines.append("")
        return "\n".join(lines)
