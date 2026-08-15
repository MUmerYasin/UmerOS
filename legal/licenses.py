"""
UmerOS Legal & Compliance — Licenses & Open-Source Compliance Subsystem
======================================================================

Provides software license compliance scanning, multi-license headers,
and compatibility auditing across all UmerOS subsystems.

Approved Licenses:
------------------
- Apache-2.0 (Primary UmerOS User-Space & Microkernel Framework)
- GPL-2.0-only (Linux Kernel Interop & HAL Drivers per torvalds/linux rules)
- MIT & BSD-3-Clause (Permissive User Utilities)
- CC-BY-SA-4.0 (Documentation & Specifications)

Author: UmerOS Project
Licence: Apache 2.0
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
            f"License Scan Report:\n"
            f"  - Total Scanned:      {self.total_files_scanned}\n"
            f"  - Compliant Files:    {self.compliant_files}\n"
            f"  - Missing License:    {len(self.missing_license_files)}\n"
            f"  - Distribution:       {self.license_distribution}\n"
            f"  - Fully Compliant:    {'YES' if self.is_fully_compliant else 'NO'}"
        )


class LicenseManager:
    """Manages license texts and verifies compliance."""

    _LICENSE_TEXTS: Dict[str, str] = {
        "Apache-2.0": (
            "Licensed under the Apache License, Version 2.0 (the 'License');\n"
            "you may not use this file except in compliance with the License.\n"
            "You may obtain a copy of the License at\n\n"
            "    http://www.apache.org/licenses/LICENSE-2.0\n"
        ),
        "GPL-2.0": (
            "This program is free software; you can redistribute it and/or modify\n"
            "it under the terms of the GNU General Public License as published by\n"
            "the Free Software Foundation; version 2 of the License.\n"
        ),
        "MIT": (
            "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
            "of this software and associated documentation files, to deal in the Software.\n"
        ),
    }

    @classmethod
    def get_license_text(cls, license_name: str = "Apache-2.0") -> str:
        return cls._LICENSE_TEXTS.get(license_name, cls._LICENSE_TEXTS["Apache-2.0"])

    @classmethod
    def scan_directory(cls, root_dir: Path | str) -> LicenseScanResult:
        """
        Scans Python source files in a directory to ensure license headers exist.
        """
        root_path = Path(root_dir).resolve()
        result = LicenseScanResult()

        if not root_path.exists():
            return result

        for root, dirs, files in os.walk(root_path):
            # Skip hidden, build, and test caches
            if any(part.startswith((".", "__")) for part in Path(root).parts):
                continue

            for f in files:
                if f.endswith(".py"):
                    result.total_files_scanned += 1
                    fp = os.path.join(root, f)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="ignore") as fo:
                            content = fo.read(2048)  # Read top 2KB
                            
                            found_lic = None
                            if "Apache" in content or "apache" in content:
                                found_lic = "Apache-2.0"
                            elif "GPL" in content or "General Public License" in content:
                                found_lic = "GPL-2.0"
                            elif "MIT" in content:
                                found_lic = "MIT"
                            elif "Licence" in content or "License" in content or "Copyright" in content:
                                found_lic = "Custom/Proprietary"

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
