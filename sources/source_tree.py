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
UmerOS /sources — Source Tree and Package Source Subsystem
==========================================================

Manages source code hierarchies (/usr/src), kernel source trees, patches,
and source package repositories in UmerOS.

Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3) 
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Sources.SourceTree")

DEFAULT_SRC_ROOT = Path("F:/Pension Person Details/UmerOS/usr/src") if os.name == "nt" else Path("/usr/src")


@dataclass
class SourcePackageMeta:
    """Metadata for a source package."""
    name: str
    version: str
    source_dir: str
    upstream_url: Optional[str] = None
    build_system: str = "make"  # make, cmake, meson, setup.py
    patches_applied: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SourceTreeManager:
    """Manages the /usr/src source tree hierarchy in UmerOS."""

    def __init__(self, src_root: Path | str = DEFAULT_SRC_ROOT) -> None:
        self.root = Path(src_root).resolve()
        self._ensure_root()

    def _ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def bootstrap(self) -> Dict[str, Path]:
        """
        Bootstraps standard /usr/src kernel and packages directories.
        """
        self._ensure_root()
        created: Dict[str, Path] = {"root": self.root}

        # 1. /usr/src/linux (Kernel source skeleton)
        linux_dir = self.root / "linux"
        for sub in ("Documentation", "include", "drivers", "fs", "kernel", "arch"):
            (linux_dir / sub).mkdir(parents=True, exist_ok=True)
        created["linux"] = linux_dir

        # 2. /usr/src/packages (Source archives and RPM/Deb sources)
        packages_dir = self.root / "packages"
        for sub in ("SOURCES", "SPECS", "BUILD", "RPMS", "SRPMS"):
            (packages_dir / sub).mkdir(parents=True, exist_ok=True)
        created["packages"] = packages_dir

        # 3. /usr/src/debug (Debug symbol sources)
        debug_dir = self.root / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        created["debug"] = debug_dir

        return created

    def list_source_packages(self) -> List[Dict[str, Any]]:
        """Lists all source directories in /usr/src."""
        packages = []
        if not self.root.exists():
            return packages

        for item in sorted(self.root.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                files_count = sum(len(files) for _, _, files in os.walk(item))
                packages.append({
                    "name": item.name,
                    "path": str(item),
                    "file_count": files_count,
                })
        return packages

    def search_source_code(self, pattern: str) -> List[Dict[str, Any]]:
        """Searches source text across the /usr/src tree."""
        matches = []
        if not self.root.exists():
            return matches

        pat_lower = pattern.lower()
        for root, _, files in os.walk(self.root):
            for f in files:
                if f.endswith((".c", ".h", ".py", ".txt", ".md", ".sh", ".spec", "Makefile")):
                    fp = os.path.join(root, f)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="ignore") as file_obj:
                            for idx, line in enumerate(file_obj, 1):
                                if pat_lower in line.lower():
                                    matches.append({
                                        "file": fp,
                                        "line_number": idx,
                                        "line_content": line.strip(),
                                    })
                                    if len(matches) >= 50:
                                        return matches
                    except Exception:
                        continue
        return matches
