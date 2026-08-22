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
UmerOS /etc Shell Configuration
=================================
Manages /etc/profile, /etc/shells, and shell environment configuration.

FHS 3.0:
  /etc/profile    — System-wide environment and startup programs
  /etc/shells     — Valid login shells
  /etc/bash.bashrc — System-wide bash configuration
  /etc/environment — System-wide environment variables

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Etc.ShellConfig")


class ShellConfigManager:
    """
    Manages shell configuration files in /etc.

    Handles /etc/profile, /etc/shells, /etc/bash.bashrc, /etc/environment.
    """

    def __init__(self, etc_path: str = "/etc"):
        self.etc_path = Path(etc_path)
        self.profile_path = self.etc_path / "profile"
        self.shells_path = self.etc_path / "shells"
        self.bashrc_path = self.etc_path / "bash.bashrc"
        self.environment_path = self.etc_path / "environment"

    # ── /etc/shells ────────────────────────────────────────────────────

    def parse_shells(self) -> List[str]:
        """Parse /etc/shells and return list of valid shell paths."""
        if not self.shells_path.exists():
            return ["/bin/sh", "/bin/bash"]
        shells = []
        for line in self.shells_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                shells.append(line)
        return shells

    def is_valid_shell(self, shell_path: str) -> bool:
        """Check if a shell is listed in /etc/shells."""
        return shell_path in self.parse_shells()

    def add_shell(self, shell_path: str) -> bool:
        """Add a shell to /etc/shells."""
        shells = self.parse_shells()
        if shell_path in shells:
            return True
        shells.append(shell_path)
        return self._write_shells(shells)

    def remove_shell(self, shell_path: str) -> bool:
        """Remove a shell from /etc/shells."""
        shells = self.parse_shells()
        if shell_path not in shells:
            return False
        shells.remove(shell_path)
        return self._write_shells(shells)

    def _write_shells(self, shells: List[str]) -> bool:
        """Write shells list to /etc/shells."""
        lines = ["# /etc/shells - Valid login shells"]
        lines.extend(shells)
        try:
            self.shells_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return True
        except Exception as e:
            log.error("Failed to write /etc/shells: %s", e)
            return False

    # ── /etc/profile ───────────────────────────────────────────────────

    def parse_profile(self) -> Dict[str, str]:
        """Parse /etc/profile and return environment variables."""
        if not self.profile_path.exists():
            return {}
        env = {}
        for line in self.profile_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[7:]
            if "=" in line and not line.startswith("#"):
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    env[key] = value
        return env

    def get_profile_variable(self, name: str) -> Optional[str]:
        """Get a single variable from /etc/profile."""
        env = self.parse_profile()
        return env.get(name)

    def set_profile_variable(self, name: str, value: str) -> bool:
        """Add or update a variable in /etc/profile."""
        content = self.profile_path.read_text(encoding="utf-8") if self.profile_path.exists() else ""
        lines = content.splitlines()
        found = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("export "):
                stripped = stripped[7:]
            if "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key == name:
                    lines[i] = f'export {name}="{value}"'
                    found = True
                    break
        if not found:
            lines.append(f'export {name}="{value}"')
        try:
            self.profile_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return True
        except Exception as e:
            log.error("Failed to update /etc/profile: %s", e)
            return False

    # ── /etc/environment ───────────────────────────────────────────────

    def parse_environment(self) -> Dict[str, str]:
        """Parse /etc/environment (KEY=VALUE format, no shell syntax)."""
        if not self.environment_path.exists():
            return {}
        env = {}
        for line in self.environment_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip('"').strip("'")
        return env

    def set_environment_variable(self, name: str, value: str) -> bool:
        """Add or update a variable in /etc/environment."""
        env = self.parse_environment()
        env[name] = value
        lines = [f'{k}="{v}"' for k, v in env.items()]
        try:
            self.environment_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return True
        except Exception as e:
            log.error("Failed to write /etc/environment: %s", e)
            return False

    def remove_environment_variable(self, name: str) -> bool:
        """Remove a variable from /etc/environment."""
        env = self.parse_environment()
        if name not in env:
            return False
        del env[name]
        lines = [f'{k}="{v}"' for k, v in env.items()]
        try:
            self.environment_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return True
        except Exception as e:
            log.error("Failed to write /etc/environment: %s", e)
            return False

    # ── /etc/bash.bashrc ───────────────────────────────────────────────

    def parse_bashrc(self) -> Dict[str, str]:
        """Parse /etc/bash.bashrc for alias and variable definitions."""
        if not self.bashrc_path.exists():
            return {}
        config = {}
        for line in self.bashrc_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("alias "):
                alias_def = line[6:]
                if "=" in alias_def:
                    name, _, value = alias_def.partition("=")
                    config[f"alias:{name.strip()}"] = value.strip().strip("'\"")
            elif "=" in line and not line.startswith("#"):
                key, _, value = line.partition("=")
                config[key.strip()] = value.strip()
        return config

    # ── Utility ────────────────────────────────────────────────────────

    def get_all_shell_config(self) -> Dict:
        """Get summary of all shell configuration."""
        return {
            "valid_shells": self.parse_shells(),
            "profile_vars": self.parse_profile(),
            "environment_vars": self.parse_environment(),
            "bashrc_aliases": {
                k: v for k, v in self.parse_bashrc().items() if k.startswith("alias:")
            },
        }
