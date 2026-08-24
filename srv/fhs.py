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
UmerOS /srv —  Compliance and Specification
======================================================

Implements the Linux Filesystem Hierarchy Standard (FHS 2.3 & 3.0) 
specifications for the ``/srv`` directory.


FHS Specification Summary:
--------------------------
1. Purpose:
   /srv contains site-specific data which is served by this system.
   The main purpose is so users and administrators can find the location
   of data files for a particular service, and so that services requiring
   a single tree for read-only data, writable data, and scripts (such as
   CGI scripts) may be reasonably organized.

2. Structure & Organization:
   The FHS does not mandate a single rigid subdirectory structure, but defines
   common standardized conventions:
   - Protocol-based: /srv/www, /srv/ftp, /srv/rsync, /srv/cvs, /srv/svn, /srv/git,
                     /srv/tftp, /srv/gopher, /srv/nfs, /srv/samba
   - Context/Domain-based: /srv/physics/www, /srv/compsci/cvs, /srv/example.com/www
   - Single-tree layout for service subdirectories:
     - data/ (or htdocs/html/pub)
     - cgi-bin/ (or scripts/)
     - uploads/ (or incoming/)
     - conf/ (service-specific site config)

3. Administrative Protection & Isolation:
   - Distributions/OS MUST NOT remove files in /srv without administrator consent.
   - User-specific private data belongs in /home/<user>, NOT in /srv.
   - Non-served internal state/libraries belong in /var/lib, NOT in /srv.
   - Executable binaries belong in /usr/bin or /usr/sbin, NOT in /srv.

Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3) 
"""

from __future__ import annotations

import enum
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# Default root path for /srv in UmerOS
DEFAULT_SRV_ROOT = Path("F:/Pension Person Details/UmerOS/srv") if os.name == "nt" else Path("/srv")


class OrganizationScheme(str, enum.Enum):
    """Supported organization schemes for /srv subdirectories."""
    BY_PROTOCOL = "by_protocol"        # e.g., /srv/www, /srv/ftp, /srv/git
    BY_DOMAIN = "by_domain"            # e.g., /srv/example.com/www, /srv/api.org/v1
    BY_DEPARTMENT = "by_department"    # e.g., /srv/physics/www, /srv/cs/git
    CUSTOM = "custom"                  # administrator custom structure


class StandardProtocol(str, enum.Enum):
    """Standard protocols commonly hosted in /srv."""
    WWW = "www"
    HTTP = "http"
    HTTPS = "https"
    FTP = "ftp"
    RSYNC = "rsync"
    GIT = "git"
    SVN = "svn"
    CVS = "cvs"
    TFTP = "tftp"
    GOPHER = "gopher"
    NFS = "nfs"
    SAMBA = "samba"
    WEBDAV = "webdav"
    CUSTOM = "custom"


# Canonical protocol subdirectories recognized.
STANDARD_PROTOCOL_DIRS: Set[str] = {
    "www", "http", "https", "ftp", "rsync", "git", "svn", "cvs",
    "tftp", "gopher", "nfs", "samba", "webdav"
}

# Directories and files prohibited in /srv (violation of FHS isolation)
PROHIBITED_IN_SRV: Set[str] = {
    "bin", "sbin", "lib", "lib64", "usr", "etc", "var", "tmp", "dev", "proc", "sys"
}


@dataclass
class FHSValidationResult:
    """Result of an FHS compliance check on a path or service."""
    is_compliant: bool
    warnings: List[str] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def summary(self) -> str:
        status = "COMPLIANT" if self.is_compliant else "NON-COMPLIANT"
        lines = [f"FHS Validation Status: {status}"]
        if self.violations:
            lines.append("Violations:")
            for v in self.violations:
                lines.append(f"  - [ERROR] {v}")
        if self.warnings:
            lines.append("Warnings:")
            for w in self.warnings:
                lines.append(f"  - [WARN] {w}")
        if self.recommendations:
            lines.append("Recommendations:")
            for r in self.recommendations:
                lines.append(f"  - [INFO] {r}")
        return "\n".join(lines)


class FHSValidator:
    """Validates /srv paths and structures."""

    @staticmethod
    def validate_service_path(path: Path | str, srv_root: Path | str = DEFAULT_SRV_ROOT) -> FHSValidationResult:
        """
        Validate whether a given path conforms to /srv requirements.
        """
        path = Path(path).resolve()
        srv_root = Path(srv_root).resolve()
        result = FHSValidationResult(is_compliant=True)

        # Check 1: Must be inside or relative to /srv
        try:
            rel = path.relative_to(srv_root)
        except ValueError:
            result.is_compliant = False
            result.violations.append(f"Path '{path}' is not within the /srv root '{srv_root}'.")
            return result

        parts = rel.parts
        if not parts:
            # The root /srv itself is valid
            return result

        top_dir = parts[0].lower()

        # Check 2: Must not mimic top-level root system directories
        if top_dir in PROHIBITED_IN_SRV:
            result.is_compliant = False
            result.violations.append(
                f"Directory name '{top_dir}' in /srv conflicts with root system hierarchy ({top_dir})."
            )

        # Check 3: Check user home directory leakage
        if top_dir in ("home", "users", "root"):
            result.is_compliant = False
            result.violations.append(
                "Personal user data belongs in /home/<user>, not directly in /srv."
            )

        # Check 4: Check if protocol or domain based
        is_known_proto = top_dir in STANDARD_PROTOCOL_DIRS
        is_valid_domain = bool(re.match(r"^[a-zA-Z0-9][-a-zA-Z0-9]*(\.[a-zA-Z0-9][-a-zA-Z0-9]*)+$", top_dir))
        is_alphanumeric = bool(re.match(r"^[a-zA-Z0-9_-]+$", top_dir))

        if not (is_known_proto or is_valid_domain or is_alphanumeric):
            result.warnings.append(
                f"Subdirectory '{top_dir}' does not match standard protocol naming or valid domain/context convention."
            )

        # Check 5: Check single-tree subfolder recommendations
        if len(parts) >= 2:
            sub = parts[1].lower()
            recommended_subs = {"html", "htdocs", "data", "pub", "incoming", "uploads", "cgi-bin", "scripts", "conf", "repos"}
            if sub not in recommended_subs:
                result.recommendations.append(
                    f"Subdirectory '{sub}' in service tree is non-standard. Consider standard names: {sorted(recommended_subs)}"
                )

        return result

    @staticmethod
    def classify_path(path: Path | str, srv_root: Path | str = DEFAULT_SRV_ROOT) -> Tuple[OrganizationScheme, Optional[str]]:
        """
        Classifies the organization scheme of a given path in /srv.
        Returns (OrganizationScheme, protocol_or_domain_name).
        """
        path = Path(path).resolve()
        srv_root = Path(srv_root).resolve()
        try:
            rel = path.relative_to(srv_root)
        except ValueError:
            return OrganizationScheme.CUSTOM, None

        parts = rel.parts
        if not parts:
            return OrganizationScheme.CUSTOM, None

        top = parts[0].lower()
        if top in STANDARD_PROTOCOL_DIRS:
            return OrganizationScheme.BY_PROTOCOL, top
        elif "." in top:
            return OrganizationScheme.BY_DOMAIN, top
        elif len(parts) >= 2 and parts[1].lower() in STANDARD_PROTOCOL_DIRS:
            return OrganizationScheme.BY_DEPARTMENT, f"{top}/{parts[1]}"
        else:
            return OrganizationScheme.CUSTOM, top
