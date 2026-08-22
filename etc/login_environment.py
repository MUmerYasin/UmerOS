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

#!/usr/bin/env python3
"""
UmerOS - /etc/environment manager
FHS 3.0: /etc/environment contains variable assignments for PAM sessions.
Read by pam_env module on login. Sets PATH, LANG, etc. for all users.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, List

ENVIRONMENT_PATH = Path(os.environ.get("UMEROS_ENVIRONMENT", "/etc/environment"))

DEFAULT_ENVIRONMENT = """# /etc/environment - UmerOS login environment
# Read by pam_env for all users at login
PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
LANG="en_US.UTF-8"
"""


class LoginEnvironmentManager:
    """Manages /etc/environment for PAM-based login environment."""

    def __init__(self, path: str = None):
        self.path = Path(path) if path else ENVIRONMENT_PATH

    def _ensure_file(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(DEFAULT_ENVIRONMENT, encoding="utf-8")

    def read_environment(self) -> Dict[str, str]:
        self._ensure_file()
        env = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip().strip('"').strip("'")
        return env

    def write_environment(self, env: Dict[str, str]) -> None:
        lines = ["# /etc/environment - UmerOS login environment"]
        for key, val in env.items():
            lines.append(f'{key}="{val}"')
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def set_var(self, key: str, value: str) -> None:
        env = self.read_environment()
        env[key] = value
        self.write_environment(env)

    def unset_var(self, key: str) -> bool:
        env = self.read_environment()
        if key in env:
            del env[key]
            self.write_environment(env)
            return True
        return False
