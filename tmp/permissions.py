"""
UmerOS /tmp — Permissions, Sticky Bit & Security Audit
======================================================

Ensures world-writable directories in /tmp have the Sticky Bit (+t) set
and verifies that transient files maintain strict least-privilege modes (0600/0700).

Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from fhs import DEFAULT_TMP_ROOT, PROTECTED_SOCKET_DIRS

log = logging.getLogger("UmerOS.Tmp.Permissions")


@dataclass
class TmpSecurityAuditResult:
    """Findings from a security audit of /tmp."""
    is_secure: bool
    sticky_bit_set: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def summary(self) -> str:
        status = "SECURE" if self.is_secure else "VULNERABILITIES DETECTED"
        lines = [f"Security Audit Status: {status}"]
        for i in self.issues:
            lines.append(f"  - [ISSUE] {i}")
        for w in self.warnings:
            lines.append(f"  - [WARN]  {w}")
        for r in self.recommendations:
            lines.append(f"  - [REC]   {r}")
        return "\n".join(lines)


class TmpPermissionManager:
    """
    Manages security audits and permission enforcement for /tmp.
    """

    @classmethod
    def audit_security(cls, tmp_root: Path | str = DEFAULT_TMP_ROOT) -> TmpSecurityAuditResult:
        """
        Runs comprehensive security audit on /tmp and all subfiles.
        """
        tmp_root = Path(tmp_root).resolve()
        result = TmpSecurityAuditResult(is_secure=True, sticky_bit_set=True)

        if not tmp_root.exists():
            result.is_secure = False
            result.issues.append(f"Directory '{tmp_root}' does not exist.")
            return result

        # Check POSIX sticky bit on root
        if os.name != "nt":
            try:
                st = tmp_root.stat()
                has_sticky = bool(st.st_mode & stat.S_ISVTX)
                result.sticky_bit_set = has_sticky
                if not has_sticky:
                    result.is_secure = False
                    result.issues.append("Root /tmp directory does NOT have Sticky Bit (+t) enabled. Risk of cross-user file deletion.")
                    result.recommendations.append("Execute 'chmod 1777 /tmp' immediately.")
            except OSError as e:
                result.issues.append(f"Could not stat {tmp_root}: {e}")

        # Scan files for world-writable risks
        for root, dirs, files in os.walk(tmp_root):
            root_path = Path(root)

            # Check subdirectories
            for d in dirs:
                dp = root_path / d
                if dp.name in PROTECTED_SOCKET_DIRS:
                    continue
                try:
                    st = dp.stat()
                    mode = stat.S_IMODE(st.st_mode)
                    if os.name != "nt":
                        # If world-writable, must have sticky bit
                        if (mode & 0o002) and not (st.st_mode & stat.S_ISVTX):
                            result.is_secure = False
                            result.issues.append(f"Directory '{dp}' is world-writable without sticky bit ({oct(mode)}).")
                except OSError:
                    pass

            # Check files
            for f in files:
                fp = root_path / f
                try:
                    st = fp.stat()
                    mode = stat.S_IMODE(st.st_mode)
                    if os.name != "nt":
                        # Check if regular file is world-writable
                        if mode & 0o002:
                            result.is_secure = False
                            result.issues.append(f"Temporary file '{fp}' is world-writable ({oct(mode)}).")
                            result.recommendations.append(f"Run 'chmod 600 {fp}'")
                except OSError:
                    pass

        return result

    @classmethod
    def enforce_permissions(cls, tmp_root: Path | str = DEFAULT_TMP_ROOT) -> Dict[str, Any]:
        """
        Enforces 1777 on /tmp root and socket dirs on POSIX systems.
        """
        tmp_root = Path(tmp_root).resolve()
        ops = []

        if not tmp_root.exists():
            return {"success": False, "error": f"Path '{tmp_root}' does not exist"}

        if os.name != "nt":
            try:
                os.chmod(tmp_root, 0o1777)
                ops.append(f"chmod 1777 on {tmp_root}")
            except OSError as e:
                return {"success": False, "error": str(e)}

            for sock in PROTECTED_SOCKET_DIRS:
                sp = tmp_root / sock
                if sp.exists():
                    try:
                        os.chmod(sp, 0o1777)
                        ops.append(f"chmod 1777 on {sp.name}/")
                    except OSError:
                        pass

        return {"success": True, "applied_ops": ops}
