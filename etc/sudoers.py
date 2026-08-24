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
UmerOS /etc/sudoers Configuration Manager
Manages sudo privilege escalation rules.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

import os
import sys
import logging

logger = logging.getLogger(__name__)


# [FIX H73] Zero-trust capability gate for privileged /etc (sudoers) writes.
# Writing /etc/sudoers can grant privilege escalation, so it requires the
# `fs.admin` capability when a CapabilityManager is wired (fail-closed);
# standalone it is permissive (warning) so existing tooling still works.
try:
    from core.capability_gate import gate, CAP_FS_ADMIN
except Exception:  # pragma: no cover - standalone fallback
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.capability_gate import gate, CAP_FS_ADMIN


def _validate_sudoers_rule(rule) -> None:
    """[FIX H73] Reject blanket privilege-escalation grants.

    A ``NOPASSWD`` rule that applies to *all* users or *all* commands is a
    blanket escalation (e.g. ``ALL ALL=(root) NOPASSWD: ALL``). Scoped
    NOPASSWD rules (a specific user + a specific command) are permitted.
    """
    if getattr(rule, "nopasswd", False) and (
        rule.user == "ALL" or rule.command == "ALL"
    ):
        raise ValueError(
            "refusing sudoers rule that grants blanket NOPASSWD escalation: "
            f"{rule.user} ... NOPASSWD: {rule.command}"
        )


def _is_host_etc(path) -> bool:
    """[FIX H73] True if *path* resolves to a top-level /etc tree of a filesystem root.

    On POSIX that is ``/etc/...``; on Windows the equivalent is ``C:\\etc\\...``.
    A UmerOS-managed path such as ``/mnt/umos/etc`` (or ``C:\\umos\\etc``) is NOT
    a top-level ``etc`` and is therefore not treated as the host tree.
    """
    try:
        resolved = os.path.realpath(str(path))
    except Exception:
        resolved = os.path.abspath(str(path))
    norm = os.path.normpath(resolved)
    parts = norm.split(os.path.sep)
    # parts[1] is the first directory below the filesystem root ('' on POSIX, 'C:' on Windows).
    if len(parts) >= 2 and parts[1] == "etc":
        return True
    return False


@dataclass
class SudoRule:
    """A single sudoers rule."""
    user: str
    command: str = "ALL"
    nopasswd: bool = False
    runas: str = "root"
    tags: List[str] = field(default_factory=list)


class SudoersManager:
    """Manages /etc/sudoers privilege configuration."""

    def __init__(self, sudoers_path: str = "/etc/sudoers",
                 allow_host_etc: bool = False):
        self.sudoers_path = Path(sudoers_path)
        # [FIX H73] Writes to the real host /etc are fail-closed unless the
        # caller explicitly opts in (e.g. a containerized UmerOS that *is* the
        # system). Tests / tooling should pass a temp path instead.
        self.allow_host_etc = allow_host_etc
        self.rules: List[SudoRule] = []
        self.includes: List[str] = ["/etc/sudoers.d/*"]
        self.defaults: Dict[str, str] = {
            "env_reset": "true",
            "mail_badpass": "true",
            "use_pty": "true",
        }
        self._ensure_directories()

    def _assert_host_etc(self, path) -> None:
        """[FIX H73] Refuse to write into the real host /etc unless authorized."""
        if self.allow_host_etc:
            return
        if _is_host_etc(path):
            raise ValueError(
                f"refusing to write to host /etc ({path}); pass allow_host_etc=True "
                f"to authorize writes to the real system /etc"
            )

    def _ensure_directories(self) -> None:
        """Create sudoers directory structure."""
        sudoers_d = self.sudoers_path.parent / "sudoers.d"
        self._assert_host_etc(sudoers_d)
        sudoers_d.mkdir(parents=True, exist_ok=True)

    def add_rule(self, rule: SudoRule) -> None:
        """Add a sudoers rule (capability-gated; rejects blanket NOPASSWD grants)."""
        _validate_sudoers_rule(rule)
        self.rules.append(rule)
        self._write_sudoers()

    def set_default(self, key: str, value: str) -> None:
        """Set a sudoers default option."""
        self.defaults[key] = value
        self._write_sudoers()

    def remove_rule(self, user: str, command: str = "ALL") -> bool:
        """Remove a sudoers rule."""
        for i, rule in enumerate(self.rules):
            if rule.user == user and rule.command == command:
                self.rules.pop(i)
                self._write_sudoers()
                return True
        return False

    def get_user_rules(self, user: str) -> List[SudoRule]:
        """Get all rules for a specific user."""
        return [r for r in self.rules if r.user == user]

    def write_include_file(self, filename: str, rules: List[SudoRule]) -> None:
        """Write a separate include file in /etc/sudoers.d/ (capability-gated)."""
        for rule in rules:
            _validate_sudoers_rule(rule)
        sudoers_d = self.sudoers_path.parent / "sudoers.d"
        self._assert_host_etc(sudoers_d)
        gate.require(CAP_FS_ADMIN)
        content = f"# Managed by UmerOS - {filename}\n"
        for rule in rules:
            line = self._format_rule(rule)
            content += line + "\n"
        (sudoers_d / filename).write_text(content, encoding='utf-8')

    def _format_rule(self, rule: SudoRule) -> str:
        """Format a single rule."""
        parts = []
        if rule.user == "ALL":
            parts.append("ALL")
        else:
            parts.append(rule.user)
        if rule.runas and rule.runas != "root":
            parts.append(f"({rule.runas})")
        if rule.nopasswd:
            parts.append("NOPASSWD:")
        parts.append(rule.command)
        return " ".join(parts)

    def _write_sudoers(self) -> None:
        """Write the main sudoers file (capability-gated; refuses host /etc)."""
        self._assert_host_etc(self.sudoers_path)
        gate.require(CAP_FS_ADMIN)
        content = "# /etc/sudoers - managed by UmerOS\n"
        content += "# DO NOT EDIT BY HAND - use visudo\n"
        content += "\nDefaults        " + "\nDefaults        ".join(
            [f"{k}={v}" if v != "true" else k for k, v in self.defaults.items()]
        ) + "\n"
        content += "\n"
        for rule in self.rules:
            content += self._format_rule(rule) + "\n"
        if self.includes:
            content += "\n@includedir " + self.includes[0] + "\n"
        self.sudoers_path.write_text(content, encoding='utf-8')
