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

    def __init__(self, sudoers_path: str = "/etc/sudoers"):
        self.sudoers_path = Path(sudoers_path)
        self.rules: List[SudoRule] = []
        self.includes: List[str] = ["/etc/sudoers.d/*"]
        self.defaults: Dict[str, str] = {
            "env_reset": "true",
            "mail_badpass": "true",
            "use_pty": "true",
        }
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create sudoers directory structure."""
        sudoers_dir = Path("/etc/sudoers.d")
        sudoers_dir.mkdir(parents=True, exist_ok=True)

    def add_rule(self, rule: SudoRule) -> None:
        """Add a sudoers rule."""
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
        """Write a separate include file in /etc/sudoers.d/."""
        sudoers_d = Path("/etc/sudoers.d")
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
        """Write the main sudoers file."""
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
