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
UmerOS /etc/default/ Configuration Manager
Manages default settings for various programs.
"""

from pathlib import Path
from typing import Dict, Optional


class DefaultConfigManager:
    """Manages /etc/default/ - default settings for programs."""

    def __init__(self, default_path: str = "/etc/default"):
        self.default_path = Path(default_path)
        self.configs: Dict[str, Dict[str, str]] = {}
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create default directory."""
        self.default_path.mkdir(parents=True, exist_ok=True)

    def set_value(self, program: str, key: str, value: str) -> None:
        """Set a default value for a program."""
        if program not in self.configs:
            self.configs[program] = {}
        self.configs[program][key] = value
        self._write_config(program)

    def get_value(self, program: str, key: str) -> Optional[str]:
        """Get a default value for a program."""
        return self.configs.get(program, {}).get(key)

    def remove_value(self, program: str, key: str) -> bool:
        """Remove a default value."""
        if program in self.configs and key in self.configs[program]:
            del self.configs[program][key]
            self._write_config(program)
            return True
        return False

    def get_program_config(self, program: str) -> Dict[str, str]:
        """Get all default values for a program."""
        return dict(self.configs.get(program, {}))

    def list_programs(self) -> list:
        """List all programs with default configs."""
        return list(self.configs.keys())

    def _write_config(self, program: str) -> None:
        """Write a program's default config."""
        config = self.configs.get(program, {})
        content = f"# /etc/default/{program} - default settings\n"
        content += "# Managed by UmerOS\n\n"
        for key, value in config.items():
            content += f'{key}="{value}"\n'
        filepath = self.default_path / program
        filepath.write_text(content, encoding='utf-8')
