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
UmerOS /etc/vconsole.conf Configuration Manager
Manages virtual console configuration.
"""

from pathlib import Path
from typing import Dict
from dataclasses import dataclass


@dataclass
class VConsoleConfig:
    """Virtual console configuration."""
    keymap: str = "us"
    font: str = "Lat2-Terminus16"
    font_map: str = "8859-15"
    font_unimap: str = ""
    unicode_font: str = ""


class VConsoleManager:
    """Manages /etc/vconsole.conf - virtual console configuration."""

    def __init__(self, vconsole_path: str = "/etc/vconsole.conf"):
        self.vconsole_path = Path(vconsole_path)
        self.config = VConsoleConfig()
        self._write_config()

    def set_keymap(self, keymap: str) -> None:
        """Set the console keymap (e.g., 'us', 'gb', 'de')."""
        self.config.keymap = keymap
        self._write_config()

    def set_font(self, font: str) -> None:
        """Set the console font."""
        self.config.font = font
        self._write_config()

    def set_font_map(self, font_map: str) -> None:
        """Set the console font map."""
        self.config.font_map = font_map
        self._write_config()

    def get_keymap(self) -> str:
        """Get the current keymap."""
        return self.config.keymap

    def get_font(self) -> str:
        """Get the current font."""
        return self.config.font

    def _write_config(self) -> None:
        """Write vconsole.conf file."""
        content = "# /etc/vconsole.conf - virtual console configuration\n"
        content += "# Managed by UmerOS\n\n"
        content += f'KEYMAP="{self.config.keymap}"\n'
        content += f'FONT="{self.config.font}"\n'
        if self.config.font_map:
            content += f'FONT_MAP="{self.config.font_map}"\n'
        if self.config.font_unimap:
            content += f'FONT_UNIMAP="{self.config.font_unimap}"\n'
        self.vconsole_path.write_text(content, encoding='utf-8')
