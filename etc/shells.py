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
UmerOS /etc/shells Configuration Manager
Manages valid login shells.
"""

from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class ShellInfo:
    """Shell entry."""
    path: str
    name: str
    description: str = ""


class ShellsManager:
    """Manages /etc/shells - valid login shells."""

    DEFAULT_SHELLS = [
        ShellInfo("/bin/bash", "bash", "Bourne Again Shell"),
        ShellInfo("/bin/sh", "sh", "POSIX Shell"),
        ShellInfo("/bin/dash", "dash", "Debian Almquist Shell"),
        ShellInfo("/usr/bin/zsh", "zsh", "Z Shell"),
        ShellInfo("/usr/bin/fish", "fish", "Friendly Interactive Shell"),
    ]

    def __init__(self, shells_path: str = "/etc/shells"):
        self.shells_path = Path(shells_path)
        self.shells: List[ShellInfo] = []
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Load default shell entries."""
        self.shells = list(self.DEFAULT_SHELLS)
        self._write_shells()

    def add_shell(self, shell: ShellInfo) -> None:
        """Add a valid shell."""
        if not any(s.path == shell.path for s in self.shells):
            self.shells.append(shell)
            self._write_shells()

    def remove_shell(self, path: str) -> bool:
        """Remove a shell from valid list."""
        for i, s in enumerate(self.shells):
            if s.path == path:
                self.shells.pop(i)
                self._write_shells()
                return True
        return False

    def is_valid_shell(self, path: str) -> bool:
        """Check if a shell is in the valid list."""
        return any(s.path == path for s in self.shells)

    def get_shells(self) -> List[str]:
        """Get list of valid shell paths."""
        return [s.path for s in self.shells]

    def _write_shells(self) -> None:
        """Write /etc/shells file."""
        content = "# /etc/shells - valid login shells\n"
        content += "# Managed by UmerOS\n\n"
        for shell in self.shells:
            content += f"{shell.path}\n"
        self.shells_path.write_text(content, encoding='utf-8')
