"""
UmerOS Legal & Compliance — Licenses & Open-Source Compliance Subsystem
======================================================================

Provides GPL-3.0-exclusive license compliance scanning, header enforcement,
and audit reporting across all UmerOS subsystems.

Approved Licenses:
------------------
- GPL-3.0 (GNU General Public License Version 3)  [FIX H128]
  Exclusive License for all UmerOS source code (canonical decision H7).

Author: UmerOS Project
Licence: GPL-3.0 
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger("UmerOS.Legal.Licenses")


@dataclass
class LicenseScanResult:
    """Findings from a project-wide license compliance scan."""
    total_files_scanned: int = 0
    compliant_files: int = 0
    missing_license_files: List[str] = field(default_factory=list)
    license_distribution: Dict[str, int] = field(default_factory=dict)
    is_fully_compliant: bool = True

    def summary(self) -> str:
        return (
            f"License Scan Report (GPL-3.0 Exclusive):\n"
            f"  - Total Scanned:      {self.total_files_scanned}\n"
            f"  - Compliant Files:    {self.compliant_files}\n"
            f"  - Missing License:    {len(self.missing_license_files)}\n"
            f"  - Distribution:       {self.license_distribution}\n"
            f"  - Fully Compliant:    {'YES' if self.is_fully_compliant else 'NO'}"
        )


class LicenseManager:
    """Manages GPL-3.0 license text and verifies compliance."""

    GPL_HEADER_TEMPLATE = (
        "# This program is free software: you can redistribute it and/or modify\n"
        "# it under the terms of the GNU General Public License as published by\n"
        "# the Free Software Foundation, either version 3 of the License, or\n"
        "# (at your option) any later version.\n"
        "#\n"
        "# This program is distributed in the hope that it will be useful,\n"
        "# but WITHOUT ANY WARRANTY; without even the implied warranty of\n"
        "# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the\n"
        "# GNU General Public License for more details.\n"
        "#\n"
        "# You should have received a copy of the GNU General Public License\n"
        "# along with this program.  If not, see <https://www.gnu.org/licenses/>.\n"
    )

    @classmethod
    def get_full_license_text(cls) -> str:
        """Reads the full GPL-3.0 text from the local file."""
        gpl_path = Path(__file__).parent / "GPL-3.0.txt"
        if gpl_path.exists():
            return gpl_path.read_text(encoding="utf-8")
        return "GPL-3.0 text not found locally. Please fetch from gnu.org."

    @classmethod
    def get_license_text(cls, license_name: str = "GPL-3.0") -> str:
        # [FIX H130] Strictly GPL-3.0: raise on any other requested license instead
        # of silently substituting the wrong text (the old code returned Apache-2.0
        # for unknown names including "GPL-3.0"). Correctness/integrity of attribution.
        if license_name != "GPL-3.0":
            raise ValueError(f"UmerOS strictly uses GPL-3.0. Requested: {license_name}")
        return cls.GPL_HEADER_TEMPLATE

    @classmethod
    def scan_directory(cls, root_dir: Path | str) -> LicenseScanResult:
        """
        Scans Python source files in a directory to ensure GPL-3.0 headers exist.
        """
        root_path = Path(root_dir).resolve()
        result = LicenseScanResult()

        if not root_path.exists():
            return result

        for root, dirs, files in os.walk(root_path):
            # Skip hidden, build, and test caches, as well as 3rd party components
            parts = Path(root).parts
            if any(part.startswith((".", "__")) for part in parts):
                continue
            if any(part in {"liboqs", "node_modules", "build", "dist", "packages"} for part in parts):
                continue

            for f in files:
                if f.endswith(".py"):
                    result.total_files_scanned += 1
                    fp = os.path.join(root, f)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="ignore") as fo:
                            content = fo.read(2048)  # Read top 2KB

                            # [FIX H129] Fail-CLOSED license audit: a file is compliant ONLY
                            # when it carries an explicit GPL-3.0 license DECLARATION. A loose
                            # "GPL-3.0" substring (which any prose mention would satisfy) is NOT
                            # accepted — the old code counted such files compliant (fail-open),
                            # so proprietary/unknown files passed the audit. Accepted declarations:
                            #   1) the canonical GPL-3.0 header block, or
                            #   2) an explicit `License: GPL-3.0` grant line, or
                            #   3) a valid SPDX id (`SPDX-License-Identifier: GPL-3.0[-or-later]`).
                            found_lic = None
                            _declarations = (
                                "GNU General Public License as published by\n# the Free Software Foundation, either version 3",
                                "License: GPL-3.0",
                                "SPDX-License-Identifier: GPL-3.0",
                                "SPDX-License-Identifier: GPL-3.0-or-later",
                            )
                            for _marker in _declarations:
                                if _marker in content:
                                    found_lic = "GPL-3.0"
                                    break

                            if found_lic:
                                result.compliant_files += 1
                                result.license_distribution[found_lic] = (
                                    result.license_distribution.get(found_lic, 0) + 1
                                )
                            else:
                                result.missing_license_files.append(fp)
                    except Exception:
                        result.missing_license_files.append(fp)

        result.is_fully_compliant = len(result.missing_license_files) == 0
        return result

    @classmethod
    def apply_headers_to_missing(cls, root_dir: Path | str) -> int:
        """
        Automatically prepends the GPL-3.0 header to Python files missing it.
        """
        scan = cls.scan_directory(root_dir)
        applied_count = 0
        for fp in scan.missing_license_files:
            try:
                with open(fp, "r", encoding="utf-8") as fo:
                    content = fo.read()
                
                # Prepend the header
                new_content = cls.GPL_HEADER_TEMPLATE + "\n" + content
                
                with open(fp, "w", encoding="utf-8") as fw:
                    fw.write(new_content)
                applied_count += 1
            except Exception as e:
                log.error(f"Failed to apply header to {fp}: {e}")

        return applied_count
