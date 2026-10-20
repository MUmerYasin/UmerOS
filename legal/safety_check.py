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
UmerOS Legal & Safety — Pre-Execution Safety & Backup Checkpoint Engine
=======================================================================

Enforces the safety mandate from Appendix E:
"Users are strongly recommended to perform system backups before proceeding."

The gate is FAIL-CLOSED for HIGH/CRITICAL operations: ``verify_safety``
reports ``is_safe=True`` only when a pre-execution checkpoint backup was
actually created.

Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .disclaimer import RiskLevel

log = logging.getLogger("UmerOS.Legal.SafetyCheck")


@dataclass
class SafetyCheckResult:
    """Findings from a pre-execution safety inspection."""
    is_safe: bool
    operation: str
    risk_level: RiskLevel
    backup_path: Optional[str] = None
    backup_created: bool = False
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def summary(self) -> str:
        status = "PASSED (Safe to Proceed)" if self.is_safe else "BLOCKED (Safety Issue)"
        lines = [f"Safety Check [{self.operation}]: {status}"]
        lines.append(f"  - Risk Level: {self.risk_level.value}")
        if self.backup_path:
            lines.append(f"  - Checkpoint Backup: {self.backup_path}")
        elif self.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            lines.append("  - Checkpoint Backup: NONE (required for HIGH/CRITICAL)")
        for w in self.warnings:
            lines.append(f"  - [WARN] {w}")
        for r in self.recommendations:
            lines.append(f"  - [REC]  {r}")
        return "\n".join(lines)


class SafetyChecker:
    """Verifies system safety, disk headroom, and performs pre-execution backups."""

    @classmethod
    def verify_safety(
        cls,
        operation_name: str,
        risk_level: RiskLevel = RiskLevel.MODERATE,
        target_path: Optional[Path | str] = None,
        create_backup: bool = True,
        backup_dir: Optional[Path | str] = None,
    ) -> SafetyCheckResult:
        """
        Executes a pre-operation safety check and optionally creates a snapshot backup.

        Fail-CLOSED for ``RiskLevel.HIGH`` / ``RiskLevel.CRITICAL``: ``is_safe``
        is only True when a checkpoint backup was actually created.  A
        failed backup, ``create_backup=False``, or a missing/nonexistent target
        therefore blocks the operation.
        """
        result = SafetyCheckResult(
            is_safe=True,
            operation=operation_name,
            risk_level=risk_level,
        )

        target = Path(target_path).resolve() if target_path else None

        # 1. Disk Space Check
        if target:
            try:
                statv = shutil.disk_usage(str(target.parent if target.is_file() else target))
                free_mb = statv.free // (1024 * 1024)
                if free_mb < 500:
                    result.is_safe = False
                    result.warnings.append(f"Critically low disk space: only {free_mb} MB available.")
                elif free_mb < 2048:
                    result.warnings.append(f"Low disk space: {free_mb} MB available.")
            except Exception:
                pass

        # 2. Pre-operation Backup (if high risk or requested)
        if create_backup and target and target.exists():
            try:
                b_dir = Path(backup_dir or (target.parent / ".safety_backups")).resolve()
                b_dir.mkdir(parents=True, exist_ok=True)
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                backup_dest = b_dir / f"{target.name}_pre_{operation_name}_{timestamp}"

                if target.is_dir():
                    shutil.copytree(target, backup_dest)
                else:
                    shutil.copy2(target, backup_dest)

                result.backup_path = str(backup_dest)
                result.backup_created = True
                result.recommendations.append(f"Safety snapshot created at {backup_dest}")
            except Exception as e:
                result.warnings.append(f"Could not create pre-execution safety backup: {e}")

        # 3. Fail-CLOSED gate: a HIGH/CRITICAL operation is only "safe"
        #    once a checkpoint backup has actually been created.  Previously a
        #    failed backup on a HIGH operation (or create_backup=False) still
        #    reported is_safe=True — a soft/fail-open gate.
        if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL) and not result.backup_created:
            result.is_safe = False
            if not create_backup:
                reason = "the checkpoint backup was not requested (create_backup=False)"
            elif target is None:
                reason = "no target_path was given, so no checkpoint could be created"
            elif not target.exists():
                reason = f"the target {target} does not exist, so no checkpoint could be created"
            else:
                reason = "the checkpoint backup did not succeed"
            result.warnings.append(
                f"{risk_level.value.upper()} operation '{operation_name}' requires a "
                f"successful pre-execution checkpoint backup before it is safe to "
                f"proceed — {reason}."
            )

        return result
