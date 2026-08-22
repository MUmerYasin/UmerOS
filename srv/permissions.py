"""
UmerOS /srv — Permissions and Security Profiles
================================================

Implements security, access control, and permission management for /srv
services, following Linux best practices and security hardening standards.

Security Models:
----------------
1. WWW (Web / HTTP):
   - htdocs/html: 0755 (read & execute for web server/world, write for admin/deploy)
   - cgi-bin: 0750 or 0755 (executable scripts)
   - uploads: 0770 or 0775 with Sticky Bit (01775 or 01777) to prevent user deletion
   - conf: 0700 or 0750 (protected from web crawlers)

2. FTP:
   - pub: 0755 / 0555 (anonymous read-only archive)
   - incoming: 01777 / 01733 (drop-box write with sticky bit, prevents overwrites)

3. Git / VCS:
   - repositories: 0770 (group write for git team, no public direct write)
   - hooks: 0750 (restricted executable scripts)

4. TFTP / Rsync:
   - boot / shares: 0755 / 0555 (publicly readable network boot images & mirrors)

Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .fhs import StandardProtocol

log = logging.getLogger("UmerOS.Srv.Permissions")


@dataclass
class PermissionAuditResult:
    """Findings from a permission security audit."""
    path: str
    is_secure: bool
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class SecurityProfile:
    """Security template for a service directory structure."""
    name: str
    default_dir_mode: int = 0o755
    default_file_mode: int = 0o644
    cgi_mode: int = 0o755
    upload_mode: int = 0o1775  # Includes sticky bit
    conf_mode: int = 0o700
    owner_user: str = "root"
    owner_group: str = "root"


# Standard protocol profiles
PROFILES: Dict[StandardProtocol, SecurityProfile] = {
    StandardProtocol.WWW: SecurityProfile(
        name="www",
        default_dir_mode=0o755,
        default_file_mode=0o644,
        cgi_mode=0o755,
        upload_mode=0o1775,
        conf_mode=0o700,
        owner_user="www-data",
        owner_group="www-data",
    ),
    StandardProtocol.HTTP: SecurityProfile(
        name="http",
        default_dir_mode=0o755,
        default_file_mode=0o644,
        cgi_mode=0o755,
        upload_mode=0o1775,
        conf_mode=0o700,
        owner_user="www-data",
        owner_group="www-data",
    ),
    StandardProtocol.FTP: SecurityProfile(
        name="ftp",
        default_dir_mode=0o755,
        default_file_mode=0o644,
        upload_mode=0o1777,
        conf_mode=0o700,
        owner_user="ftp",
        owner_group="ftp",
    ),
    StandardProtocol.GIT: SecurityProfile(
        name="git",
        default_dir_mode=0o770,
        default_file_mode=0o660,
        cgi_mode=0o750,
        conf_mode=0o700,
        owner_user="git",
        owner_group="git",
    ),
    StandardProtocol.RSYNC: SecurityProfile(
        name="rsync",
        default_dir_mode=0o755,
        default_file_mode=0o644,
        conf_mode=0o700,
        owner_user="rsync",
        owner_group="rsync",
    ),
    StandardProtocol.TFTP: SecurityProfile(
        name="tftp",
        default_dir_mode=0o755,
        default_file_mode=0o644,
        conf_mode=0o700,
        owner_user="tftp",
        owner_group="tftp",
    ),
}


class SrvPermissionManager:
    """Manages permissions, audits, and security profiles across /srv."""

    @classmethod
    def get_profile(cls, protocol: StandardProtocol | str) -> SecurityProfile:
        if isinstance(protocol, str):
            try:
                protocol = StandardProtocol(protocol)
            except ValueError:
                protocol = StandardProtocol.CUSTOM

        return PROFILES.get(protocol, SecurityProfile(name="default"))

    @classmethod
    def apply_profile(cls, base_dir: Path | str, protocol: StandardProtocol | str) -> Dict[str, Any]:
        """
        Applies standard permission modes to subfolders in a service tree.
        """
        base_dir = Path(base_dir).resolve()
        profile = cls.get_profile(protocol)
        applied_ops = []

        if not base_dir.exists():
            return {"success": False, "error": f"Path '{base_dir}' does not exist"}

        try:
            # Set base dir mode
            if os.name != "nt":
                os.chmod(base_dir, profile.default_dir_mode)
            applied_ops.append(f"chmod {oct(profile.default_dir_mode)} on {base_dir.name}")

            for item in base_dir.iterdir():
                if item.is_dir():
                    name = item.name.lower()
                    if name in ("cgi-bin", "scripts"):
                        mode = profile.cgi_mode
                    elif name in ("uploads", "incoming"):
                        mode = profile.upload_mode
                    elif name in ("conf", "config"):
                        mode = profile.conf_mode
                    else:
                        mode = profile.default_dir_mode

                    if os.name != "nt":
                        try:
                            os.chmod(item, mode)
                        except OSError as e:
                            log.warning(f"Could not chmod {item}: {e}")
                    applied_ops.append(f"chmod {oct(mode)} on {item.name}/")

            return {"success": True, "applied_ops": applied_ops, "profile": profile.name}
        except Exception as ex:
            return {"success": False, "error": str(ex)}

    @classmethod
    def audit_service(cls, base_dir: Path | str) -> PermissionAuditResult:
        """
        Audits permissions of a service tree for security issues.
        """
        base_dir = Path(base_dir).resolve()
        result = PermissionAuditResult(path=str(base_dir), is_secure=True)

        if not base_dir.exists():
            result.is_secure = False
            result.issues.append("Service directory does not exist.")
            return result

        try:
            for root, dirs, files in os.walk(base_dir):
                for d in dirs:
                    dp = Path(root) / d
                    try:
                        st = dp.stat()
                        mode = stat.S_IMODE(st.st_mode)
                        # Check world-writable without sticky bit on POSIX
                        if os.name != "nt":
                            if (mode & 0o002) and not (st.st_mode & stat.S_ISVTX):
                                result.is_secure = False
                                result.issues.append(f"Directory '{dp}' is world-writable without sticky bit (+t).")
                                result.recommendations.append(f"Run chmod +t on '{dp}' or remove world-write.")
                    except (OSError, PermissionError):
                        continue

                for f in files:
                    fp = Path(root) / f
                    try:
                        st = fp.stat()
                        mode = stat.S_IMODE(st.st_mode)
                        # Check sensitive config files readable by world
                        if "conf" in root.lower() or "secret" in f.lower() or "key" in f.lower():
                            if os.name != "nt" and (mode & 0o004):
                                result.is_secure = False
                                result.issues.append(f"Sensitive configuration file '{fp}' is world-readable ({oct(mode)}).")
                                result.recommendations.append(f"Run chmod 600 or 640 on '{fp}'.")
                    except (OSError, PermissionError):
                        continue
        except Exception as e:
            result.issues.append(f"Audit encountered error: {e}")

        return result
