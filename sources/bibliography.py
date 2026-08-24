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
UmerOS Sources & Bibliography Subsystem
========================================

Complete bibliography, citation registry, and reference repository



Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3) 
"""

from __future__ import annotations

import enum
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set


class SourceCategory(str, enum.Enum):
    """Classification of reference sources."""
    BOOK = "book"
    STANDARD = "standard"
    KERNEL_DOC = "kernel_doc"
    ONLINE_REFERENCE = "online_reference"
    PAPER = "paper"
    RFC = "rfc"


@dataclass
class SourceReference:
    """Represents a bibliographical reference or standard."""
    key: str
    title: str
    authors: List[str]
    year: Optional[int]
    category: SourceCategory
    publisher_or_org: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        return d

    def to_bibtex(self) -> str:
        entry_type = "book" if self.category == SourceCategory.BOOK else "misc"
        authors_str = " and ".join(self.authors) if self.authors else "Unknown"
        lines = [f"@{entry_type}{{{self.key},"]
        lines.append(f"  title = {{{self.title}}},")
        lines.append(f"  author = {{{authors_str}}},")
        if self.year:
            lines.append(f"  year = {{{self.year}}},")
        if self.publisher_or_org:
            lines.append(f"  publisher = {{{self.publisher_or_org}}},")
        if self.url:
            lines.append(f"  url = {{{self.url}}},")
        lines.append("}")
        return "\n".join(lines)


# ── Canonical Sources Database ───────────────────────────────────────

TLDP_SOURCES: List[SourceReference] = [
    SourceReference(
        key="kernighan1984unix",
        title="The UNIX Programming Environment",
        authors=["Brian W. Kernighan", "Rob Pike"],
        year=1984,
        category=SourceCategory.BOOK,
        publisher_or_org="Prentice Hall, New Jersey",
        description="Foundational Unix architecture, file philosophy, and shell programming environment.",
        tags=["unix", "foundations", "shell", "c"],
    ),
    SourceReference(
        key="heath1998newnes",
        title="Newnes UNIX Pocket Book",
        authors=["Steve Heath"],
        year=1998,
        category=SourceCategory.BOOK,
        publisher_or_org="Butterworth-Heinemann, Great Britain",
        description="Concise handbook of Unix administration, file commands, and process management.",
        tags=["unix", "handbook", "commands"],
    ),
    SourceReference(
        key="eldirghami2000suse",
        title="SuSE Linux Installation and Configuration",
        authors=["Nazeeh Amin El-Dirghami", "Youssef A. Abu Kwaik"],
        year=2000,
        category=SourceCategory.BOOK,
        publisher_or_org="QUE Corporation, USA",
        description="Linux system distribution setup, partition layouts, and runlevel initialization.",
        tags=["linux", "suse", "installation", "sysvinit"],
    ),
    SourceReference(
        key="tobler2001inside",
        title="Inside Linux",
        authors=["Michael J. Tobler"],
        year=2001,
        category=SourceCategory.BOOK,
        publisher_or_org="New Riders Publishing, USA",
        description="Comprehensive guide to the Linux kernel, memory management, and file systems.",
        tags=["linux", "kernel", "internals", "filesystem"],
    ),
    SourceReference(
        key="siever1999nut",
        title="Linux in a Nutshell (2nd Edition)",
        authors=["Ellen Siever"],
        year=1999,
        category=SourceCategory.BOOK,
        publisher_or_org="O'Reilly & Associates Inc., CA, USA",
        description="Standard reference for Linux utilities, command syntax, and configuration files.",
        tags=["linux", "reference", "commands", "oreilly"],
    ),
    SourceReference(
        key="smart1999caldera",
        title="Using Caldera OpenLinux Special Edition",
        authors=["Allan Smart", "Erik Ratcliffe", "Tim Bird", "David Bandel"],
        year=1999,
        category=SourceCategory.BOOK,
        publisher_or_org="QUE Corporation, USA",
        description="Linux system administration and bootloader configurations.",
        tags=["linux", "caldera", "admin"],
    ),
    SourceReference(
        key="mann2000security",
        title="Linux System Security (The Administrator's Guide to Open Source Security Tools)",
        authors=["Scott Mann", "Ellen L. Mitchell"],
        year=2000,
        category=SourceCategory.BOOK,
        publisher_or_org="Prentice-Hall, New Jersey",
        description="Hardening Linux filesystem permissions, PAM, SELinux, and network services.",
        tags=["security", "permissions", "hardening", "pam"],
    ),
    SourceReference(
        key="hsiao1999xfree86",
        title="XFree86 For Linux (Uncommon Solutions for the Technical Professional)",
        authors=["Aron Hsiao"],
        year=1999,
        category=SourceCategory.BOOK,
        publisher_or_org="QUE Corporation, USA",
        description="X11 Window System architecture, socket directories (/tmp/.X11-unix), and font paths.",
        tags=["x11", "gui", "sockets", "xfree86"],
    ),
    SourceReference(
        key="lions1996commentary",
        title="Lions' Commentary on UNIX 6th Edition with Source Code",
        authors=["John Lions"],
        year=1996,
        category=SourceCategory.BOOK,
        publisher_or_org="Peer-to-Peer Communications Incorporated, USA",
        description="Classic commentary on the Unix V6 kernel source code.",
        tags=["unix", "kernel", "source_code", "history"],
    ),
    SourceReference(
        key="wirzenius1998sag",
        title="The Linux System Administrators' Guide Version 0.6.1",
        authors=["Lars Wirzenius"],
        year=1998,
        category=SourceCategory.ONLINE_REFERENCE,
        publisher_or_org="Linux Documentation Project (TLDP)",
        url="https://tldp.org/LDP/sag/html/index.html",
        description="Standard TLDP guide covering filesystem layout, backups, user accounts, and disks.",
        tags=["tldp", "sysadmin", "guide"],
    ),
    SourceReference(
        key="veerararaghavan1999shell",
        title="SAMS Teach Yourself Shell Programming in 24 Hours",
        authors=["Sriranga Veerararaghavan"],
        year=1999,
        category=SourceCategory.BOOK,
        publisher_or_org="SAMS Publishing, USA",
        description="BASH and POSIX shell scripting for system automation.",
        tags=["shell", "bash", "scripting"],
    ),
    SourceReference(
        key="fhs_spec",
        title="Filesystem Hierarchy Standard (FHS)",
        authors=["Rusty Russell", "Daniel Quinlan", "Christopher Yeoh"],
        year=2004,
        category=SourceCategory.STANDARD,
        publisher_or_org="Free Standards Group",
        url="http://www.pathname.com/fhs",
        description="The authoritative specification defining the directory structure and contents in Linux systems.",
        tags=["fhs", "standard", "filesystem", "root"],
    ),
    SourceReference(
        key="fsstnd_spec",
        title="Linux Filesystem Standard (FSSTND)",
        authors=["FSSTND Group"],
        year=1995,
        category=SourceCategory.STANDARD,
        publisher_or_org="Linux Community",
        url="http://www.linuxsa.org.au/meetings/1997-06/fsstnd/fsstnd.html",
        description="The historical predecessor standard to FHS.",
        tags=["fsstnd", "history", "standard"],
    ),
    SourceReference(
        key="devfs_spec",
        title="The DevFS Dynamic Device Filesystem",
        authors=["Richard Gooch"],
        year=2001,
        category=SourceCategory.PAPER,
        publisher_or_org="CSIRO / Linux Kernel Archives",
        url="http://www.atnf.csiro.au/people/rgooch/linux/docs/devfs.html",
        description="Dynamic device filesystem specification and architecture.",
        tags=["devfs", "devices", "dev", "kernel"],
    ),
    SourceReference(
        key="proc_doc",
        title="/usr/src/linux/Documentation/filesystems/proc.txt",
        authors=["Terrehon Bowden", "Bodo Bauer", "Jorge Nerin"],
        year=2001,
        category=SourceCategory.KERNEL_DOC,
        publisher_or_org="Linux Kernel Documentation",
        description="Official specification of the Linux /proc pseudo-filesystem structure and metrics.",
        tags=["proc", "procfs", "kernel_doc"],
    ),
    SourceReference(
        key="initrd_doc",
        title="/usr/src/linux/Documentation/initrd.txt",
        authors=["Werner Almesberger", "Hans Lermen"],
        year=2000,
        category=SourceCategory.KERNEL_DOC,
        publisher_or_org="Linux Kernel Documentation",
        description="Initial RAM disk architecture, two-stage boot sequence, and pivot_root operations.",
        tags=["initrd", "boot", "ramdisk", "kernel_doc"],
    ),
    SourceReference(
        key="sysvinit_runlevels",
        title="/usr/share/doc/sysvinit/README.runlevels.gz",
        authors=["Miquel van Smoorenburg"],
        year=1999,
        category=SourceCategory.KERNEL_DOC,
        publisher_or_org="Debian / System V Init Project",
        description="System V init runlevel definitions (0=Halt, 1=Single, 2-5=Multiuser, 6=Reboot).",
        tags=["sysvinit", "runlevels", "init", "boot"],
    ),
    SourceReference(
        key="selinux_spec",
        title="SELinux Security Contexts & Mandatory Access Control",
        authors=["National Security Agency (NSA)"],
        year=2001,
        category=SourceCategory.STANDARD,
        publisher_or_org="National Security Agency",
        url="http://www.nsa.gov/selinux/",
        description="Flask architecture and security context labeling on Linux filesystem nodes.",
        tags=["selinux", "security", "mac", "labels"],
    ),
]


class BibliographyRegistry:
    """Registry and query engine for all FHS and Linux standards citations."""

    def __init__(self, sources: Optional[List[SourceReference]] = None) -> None:
        self._sources: Dict[str, SourceReference] = {}
        for s in (sources or TLDP_SOURCES):
            self._sources[s.key] = s

    def get(self, key: str) -> Optional[SourceReference]:
        return self._sources.get(key)

    def list_all(self) -> List[SourceReference]:
        return list(self._sources.values())

    def search(self, query: str) -> List[SourceReference]:
        q = query.lower()
        results = []
        for s in self._sources.values():
            if (
                q in s.key.lower()
                or q in s.title.lower()
                or any(q in a.lower() for a in s.authors)
                or any(q in t.lower() for t in s.tags)
                or (s.description and q in s.description.lower())
            ):
                results.append(s)
        return results

    def filter_by_category(self, category: SourceCategory) -> List[SourceReference]:
        return [s for s in self._sources.values() if s.category == category]

    def export(self, format_type: str = "json") -> str:
        if format_type.lower() == "bibtex":
            return "\n\n".join(s.to_bibtex() for s in self._sources.values())
        elif format_type.lower() == "markdown":
            lines = ["# Linux Filesystem Hierarchy — Bibliography & Sources\n"]
            for s in self._sources.values():
                authors = ", ".join(s.authors)
                year_str = f"({s.year})" if s.year else ""
                lines.append(f"### {s.title} {year_str}")
                lines.append(f"- **Authors:** {authors}")
                lines.append(f"- **Category:** {s.category.value}")
                if s.publisher_or_org:
                    lines.append(f"- **Publisher/Org:** {s.publisher_or_org}")
                if s.url:
                    lines.append(f"- **URL:** [{s.url}]({s.url})")
                if s.description:
                    lines.append(f"- **Description:** {s.description}")
                lines.append(f"- **Tags:** `{', '.join(s.tags)}`\n")
            return "\n".join(lines)
        else:
            return json.dumps([s.to_dict() for s in self._sources.values()], indent=2)
