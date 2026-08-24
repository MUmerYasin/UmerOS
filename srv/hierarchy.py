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
UmerOS /srv — Directory Hierarchy and Provisioning Engine
==========================================================

Manages the physical directory tree of ``/srv`` in UmerOS, supporting
the single-tree paradigm per service described.

 Key Principles:
--------------------------
1. Unified Service Tree:
   Services requiring read-only data, writable data, and scripts (such as CGI)
   can house them cleanly inside a single root:
       /srv/<service_name>/
           ├── html/ (or htdocs/ or data/)
           ├── cgi-bin/ (or scripts/)
           ├── uploads/ (or incoming/)
           └── conf/ (site configuration)

2. Provisioning & Skeleton Generation:
   Standard skeletons for www, ftp, git, rsync, tftp, svn, cvs, nfs, samba.

3. Administrative Preservation:
   Protects existing site data from unintended deletion or overwriting during
   re-provisioning or system maintenance.

Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3) 
"""

from __future__ import annotations

import logging
import os
import shutil
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# [FIX H268] Zero-trust capability gate for destructive /srv tree removal.
from core.capability_gate import CAP_FS_ADMIN, gate

from .fhs import (
    DEFAULT_SRV_ROOT,
    STANDARD_PROTOCOL_DIRS,
    FHSValidator,
    OrganizationScheme,
    StandardProtocol,
)

log = logging.getLogger("UmerOS.Srv.Hierarchy")


@dataclass
class ServiceTreeLayout:
    """Specification for a single-tree service layout."""
    service_name: str
    base_dir: Path
    data_dir: Path
    cgi_dir: Optional[Path] = None
    upload_dir: Optional[Path] = None
    conf_dir: Optional[Path] = None
    extra_dirs: Dict[str, Path] = field(default_factory=dict)

    def all_dirs(self) -> List[Path]:
        dirs = [self.base_dir, self.data_dir]
        if self.cgi_dir:
            dirs.append(self.cgi_dir)
        if self.upload_dir:
            dirs.append(self.upload_dir)
        if self.conf_dir:
            dirs.append(self.conf_dir)
        dirs.extend(self.extra_dirs.values())
        return dirs


class SrvHierarchy:
    """
    Manages physical directory structure creation, verification, and inspection
    for the /srv filesystem hierarchy.
    """

    def __init__(self, srv_root: Path | str = DEFAULT_SRV_ROOT) -> None:
        self.root = Path(srv_root).resolve()
        self._ensure_root()

    def _ensure_root(self) -> None:
        """Ensure that the /srv root directory exists."""
        self.root.mkdir(parents=True, exist_ok=True)

    def bootstrap(self, create_standard_skeletons: bool = True) -> Dict[str, Path]:
        """
        Bootstrap the /srv hierarchy with standard FHS skeletons.
        Does not overwrite or delete any existing files.
        """
        self._ensure_root()
        created: Dict[str, Path] = {"root": self.root}

        if not create_standard_skeletons:
            return created

        # 1. /srv/www (Web / HTTP / HTTPS)
        www_tree = self.create_service_tree(
            service_name="www",
            protocol=StandardProtocol.WWW,
            subdirs=["html", "cgi-bin", "uploads", "conf", "vhosts"],
        )
        created["www"] = www_tree.base_dir
        # Create default index.html if not present
        default_index = www_tree.data_dir / "index.html"
        if not default_index.exists():
            default_index.write_text(
                "<!DOCTYPE html>\n<html>\n<head><title>Welcome to UmerOS /srv</title></head>\n"
                "<body><h1>UmerOS /srv Web Service</h1><p>Site-specific data served by UmerOS.</p></body>\n</html>",
                encoding="utf-8",
            )

        # 2. /srv/ftp (FTP / Anonymous & User)
        ftp_tree = self.create_service_tree(
            service_name="ftp",
            protocol=StandardProtocol.FTP,
            subdirs=["pub", "incoming", "conf"],
        )
        created["ftp"] = ftp_tree.base_dir

        # 3. /srv/git (Git Repositories)
        git_tree = self.create_service_tree(
            service_name="git",
            protocol=StandardProtocol.GIT,
            subdirs=["repositories", "hooks", "conf"],
        )
        created["git"] = git_tree.base_dir

        # 4. /srv/rsync (Rsync Mirrors & Shares)
        rsync_tree = self.create_service_tree(
            service_name="rsync",
            protocol=StandardProtocol.RSYNC,
            subdirs=["shares", "conf"],
        )
        created["rsync"] = rsync_tree.base_dir

        # 5. /srv/tftp (TFTP Boot Images)
        tftp_tree = self.create_service_tree(
            service_name="tftp",
            protocol=StandardProtocol.TFTP,
            subdirs=["boot", "pxelinux.cfg", "images"],
        )
        created["tftp"] = tftp_tree.base_dir

        # 6. /srv/nfs & /srv/samba (Network Shared Storage)
        nfs_dir = self.root / "nfs" / "exports"
        nfs_dir.mkdir(parents=True, exist_ok=True)
        created["nfs"] = self.root / "nfs"

        samba_dir = self.root / "samba" / "shares"
        samba_dir.mkdir(parents=True, exist_ok=True)
        created["samba"] = self.root / "samba"

        return created

    def create_service_tree(
        self,
        service_name: str,
        protocol: StandardProtocol = StandardProtocol.WWW,
        scheme: OrganizationScheme = OrganizationScheme.BY_PROTOCOL,
        domain_or_dept: Optional[str] = None,
        subdirs: Optional[List[str]] = None,
    ) -> ServiceTreeLayout:
        """
        Creates a single-tree service directory structure.
        """
        if scheme == OrganizationScheme.BY_DOMAIN and domain_or_dept:
            base_dir = self.root / domain_or_dept / service_name
        elif scheme == OrganizationScheme.BY_DEPARTMENT and domain_or_dept:
            base_dir = self.root / domain_or_dept / service_name
        else:
            base_dir = self.root / service_name

        base_dir.mkdir(parents=True, exist_ok=True)

        # Determine subfolder structure
        if subdirs is None:
            if protocol in (StandardProtocol.WWW, StandardProtocol.HTTP, StandardProtocol.HTTPS):
                subdirs = ["html", "cgi-bin", "uploads", "conf"]
            elif protocol == StandardProtocol.FTP:
                subdirs = ["pub", "incoming", "conf"]
            elif protocol in (StandardProtocol.GIT, StandardProtocol.SVN, StandardProtocol.CVS):
                subdirs = ["repositories", "hooks", "conf"]
            elif protocol == StandardProtocol.TFTP:
                subdirs = ["boot", "images", "conf"]
            elif protocol == StandardProtocol.RSYNC:
                subdirs = ["shares", "conf"]
            else:
                subdirs = ["data", "cgi-bin", "uploads", "conf"]

        data_dir = base_dir / subdirs[0]
        data_dir.mkdir(parents=True, exist_ok=True)

        cgi_dir = None
        upload_dir = None
        conf_dir = None
        extra_dirs = {}

        for sub in subdirs:
            target = base_dir / sub
            target.mkdir(parents=True, exist_ok=True)
            if sub in ("cgi-bin", "scripts"):
                cgi_dir = target
            elif sub in ("uploads", "incoming"):
                upload_dir = target
            elif sub in ("conf", "config"):
                conf_dir = target
            elif sub != subdirs[0]:
                extra_dirs[sub] = target

        return ServiceTreeLayout(
            service_name=service_name,
            base_dir=base_dir,
            data_dir=data_dir,
            cgi_dir=cgi_dir,
            upload_dir=upload_dir,
            conf_dir=conf_dir,
            extra_dirs=extra_dirs,
        )

    def scan_hierarchy(self) -> List[Dict[str, Any]]:
        """
        Scans /srv and returns details of all top-level and structured service trees.
        """
        results = []
        if not self.root.exists():
            return results

        for item in sorted(self.root.iterdir()):
            if item.is_dir() and not item.name.startswith((".", "__")) and not item.name.endswith(".py"):
                # Determine size and file count
                size, files, subdirs = self.get_dir_stats(item)
                scheme, classified_name = FHSValidator.classify_path(item, self.root)
                fhs_check = FHSValidator.validate_service_path(item, self.root)

                results.append({
                    "name": item.name,
                    "path": str(item),
                    "scheme": scheme.value,
                    "classified_name": classified_name,
                    "size_bytes": size,
                    "file_count": files,
                    "dir_count": subdirs,
                    "is_fhs_compliant": fhs_check.is_compliant,
                    "warnings": fhs_check.warnings,
                    "violations": fhs_check.violations,
                })
        return results

    def get_dir_stats(self, path: Path) -> Tuple[int, int, int]:
        """
        Computes total size in bytes, file count, and subdirectory count.
        """
        total_size = 0
        total_files = 0
        total_dirs = 0

        try:
            for root, dirs, files in os.walk(path):
                total_dirs += len(dirs)
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        total_size += os.path.getsize(fp)
                        total_files += 1
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            pass

        return total_size, total_files, total_dirs

    def delete_service_tree(self, service_name: str, force: bool = False) -> bool:
        """
        Deletes a service tree.
        Per TLDP / FHS caution, requires explicit admin confirmation (force=True).
        [FIX H268] Additionally requires CAP_FS_ADMIN (zero-trust): the
        force flag alone is not a privilege grant.
        """
        # [FIX H268] destructive /srv tree removal -> zero-trust capability gate
        gate.require(CAP_FS_ADMIN)
        target = self.root / service_name
        if not target.exists():
            return False

        if not force:
            raise PermissionError(
                f"Safety: Removing '{target}' without explicit force/confirmation is forbidden. "
                "Distributions and utilities must not remove files in /srv without administrator permission."
            )

        shutil.rmtree(target)
        return True
