"""
UmerOS /tmp — TLDP & FHS Compliance and Specification
======================================================

Implements the Linux Filesystem Hierarchy Standard (FHS 2.3 & 3.0) and TLDP
specifications for the ``/tmp`` directory.

TLDP Reference:
https://tldp.org/LDP/Linux-Filesystem-Hierarchy/html/tmp.html

FHS Specification Summary:
--------------------------
1. Purpose:
   /tmp contains temporary files required by running programs. Programs
   and users must NOT assume that files or directories in /tmp are preserved
   between program invocations or system reboots.

2. /tmp vs /var/tmp Distinction:
   - /tmp: Short-lived transient files, cleared during boot/shutdown or by periodic
           reapers (e.g. files older than 10-30 days, or on every reboot).
   - /var/tmp: Preserved across reboots, for larger or multi-session temporary files.

3. Standard Protected Subdirectories:
   - /tmp/.X11-unix/     (X11 display sockets)
   - /tmp/.ICE-unix/     (Inter-Client Exchange sockets)
   - /tmp/.font-unix/    (Font server sockets)
   - /tmp/.rpc-unix/     (RPC sockets)
   - /tmp/.Test-unix/    (Test runtime sockets)

4. Security Requirements:
   - Directory permissions MUST be 01777 (drwxrwxrwt) with the Sticky Bit set.
   - Symlink/Hardlink attack prevention in world-writable spaces.
   - Secure random filename generation (O_EXCL | O_CREAT with 0600/0700).

Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import enum
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# Default root path for /tmp in UmerOS
DEFAULT_TMP_ROOT = Path("F:/Pension Person Details/UmerOS/tmp") if os.name == "nt" else Path("/tmp")

# Standard UNIX socket & system subdirectories reserved in /tmp
PROTECTED_SOCKET_DIRS: Set[str] = {
    ".X11-unix",
    ".ICE-unix",
    ".font-unix",
    ".rpc-unix",
    ".Test-unix",
    ".systemd-private",
}

# Standard temporary file prefixes
RECOMMENDED_PREFIXES: Set[str] = {
    "tmp",
    "umeros-",
    "tmp.",
    "temp_",
    "sess_",
    "lock_",
}


@dataclass
class FHSValidationResult:
    """Findings from an FHS compliance validation on /tmp."""
    is_compliant: bool
    warnings: List[str] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def summary(self) -> str:
        status = "COMPLIANT" if self.is_compliant else "NON-COMPLIANT"
        lines = [f"FHS /tmp Status: {status}"]
        for v in self.violations:
            lines.append(f"  - [ERROR] {v}")
        for w in self.warnings:
            lines.append(f"  - [WARN] {w}")
        for r in self.recommendations:
            lines.append(f"  - [INFO] {r}")
        return "\n".join(lines)


class FHSValidator:
    """Validates /tmp files and directories against FHS and TLDP standards."""

    @staticmethod
    def validate_tmp_root(tmp_root: Path | str = DEFAULT_TMP_ROOT) -> FHSValidationResult:
        """
        Validates the root /tmp directory attributes.
        """
        tmp_root = Path(tmp_root).resolve()
        result = FHSValidationResult(is_compliant=True)

        if not tmp_root.exists():
            result.is_compliant = False
            result.violations.append(f"Directory '{tmp_root}' does not exist.")
            return result

        if not tmp_root.is_dir():
            result.is_compliant = False
            result.violations.append(f"Path '{tmp_root}' is not a directory.")
            return result

        # Check permissions on POSIX
        if os.name != "nt":
            st = tmp_root.stat()
            mode = stat.S_IMODE(st.st_mode)
            has_sticky = bool(st.st_mode & stat.S_ISVTX)

            if not has_sticky:
                result.is_compliant = False
                result.violations.append("Sticky Bit (+t) is NOT set on /tmp (required mode: 1777).")

            if mode != 0o1777 and mode != 0o777:
                result.warnings.append(f"Permissions are {oct(mode)}, standard FHS requires 01777.")

        return result

    @staticmethod
    def is_protected_directory(name: str) -> bool:
        """Checks if a subdirectory is a protected system socket directory."""
        return name in PROTECTED_SOCKET_DIRS
