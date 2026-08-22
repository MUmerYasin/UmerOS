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
UmerOS /etc Fonts Configuration
==================================
Manages font configuration files.

FHS 3.0 entries:
  /etc/fonts/              — Font configuration
  /etc/fonts/fonts.conf    — Fontconfig main configuration
  /etc/fonts/conf.d/       — Fontconfig additional configuration
  /etc/fonts/local.conf    — Local fontconfig overrides

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger("UmerOS.Etc.FontsConfig")


class FontsConfigManager:
    """Manages /etc/fonts/ configuration."""

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.fonts_path = self.etc_path / "fonts"

    def initialize(self) -> bool:
        try:
            self.fonts_path.mkdir(parents=True, exist_ok=True)
            (self.fonts_path / "conf.d").mkdir(parents=True, exist_ok=True)
            (self.fonts_path / "conf.avail").mkdir(parents=True, exist_ok=True)
            self._create_fonts_conf()
            self._create_local_conf()
            self._create_default_conf_links()
            log.info("Initialized /etc/fonts/")
            return True
        except Exception as e:
            log.error("Failed to initialize fonts config: %s", e)
            return False

    def _create_fonts_conf(self) -> None:
        fp = self.fonts_path / "fonts.conf"
        if fp.exists():
            return
        fp.write_text(
            "<?xml version=\"1.0\"?>\n"
            "<!DOCTYPE fontconfig SYSTEM \"urn:fontconfig:fonts.dtd\">\n"
            "<!-- /etc/fonts/fonts.conf - Fontconfig main configuration -->\n"
            "<!-- UmerOS Font Configuration -->\n"
            "<fontconfig>\n"
            "  <!-- Directories for font search -->\n"
            "  <dir>/usr/share/fonts</dir>\n"
            "  <dir>/usr/local/share/fonts</dir>\n"
            "  <dir>~/.fonts</dir>\n"
            "  <dir>~/.local/share/fonts</dir>\n\n"
            "  <!-- System font directories -->\n"
            "  <dir prefix=\"xdg\" fontdirs=\"fonts\">/etc/fonts/conf.d</dir>\n\n"
            "  <!-- Default sans-serif font -->\n"
            "  <alias>\n"
            "    <family>sans-serif</family>\n"
            "    <prefer>\n"
            "      <family>DejaVu Sans</family>\n"
            "      <family>Liberation Sans</family>\n"
            "      <family>Noto Sans</family>\n"
            "    </prefer>\n"
            "  </alias>\n\n"
            "  <!-- Default serif font -->\n"
            "  <alias>\n"
            "    <family>serif</family>\n"
            "    <prefer>\n"
            "      <family>DejaVu Serif</family>\n"
            "      <family>Liberation Serif</family>\n"
            "      <family>Noto Serif</family>\n"
            "    </prefer>\n"
            "  </alias>\n\n"
            "  <!-- Default monospace font -->\n"
            "  <alias>\n"
            "    <family>monospace</family>\n"
            "    <prefer>\n"
            "      <family>DejaVu Sans Mono</family>\n"
            "      <family>Liberation Mono</family>\n"
            "      <family>Noto Sans Mono</family>\n"
            "    </prefer>\n"
            "  </alias>\n\n"
            "  <!-- Subpixel rendering -->\n"
            "  <match target=\"font\">\n"
            "    <edit mode=\"assign\" name=\"rgba\"><const>rgb</const></edit>\n"
            "  </match>\n\n"
            "  <!-- Antialiasing -->\n"
            "  <match target=\"font\">\n"
            "    <edit mode=\"assign\" name=\"antialias\"><bool>true</bool></edit>\n"
            "  </match>\n"
            "</fontconfig>\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/fonts/fonts.conf")

    def _create_local_conf(self) -> None:
        fp = self.fonts_path / "local.conf"
        if fp.exists():
            return
        fp.write_text(
            "<?xml version=\"1.0\"?>\n"
            "<!DOCTYPE fontconfig SYSTEM \"urn:fontconfig:fonts.dtd\">\n"
            "<!-- /etc/fonts/local.conf - Local fontconfig overrides -->\n"
            "<!-- UmerOS Local Font Configuration -->\n"
            "<fontconfig>\n"
            "  <!-- Add custom font directories here -->\n"
            "  <!-- <dir>/opt/custom-fonts</dir> -->\n\n"
            "  <!-- Add custom font substitutions here -->\n"
            "</fontconfig>\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/fonts/local.conf")

    def _create_default_conf_links(self) -> None:
        """Create default conf.d files."""
        defaults = {
            "10-hinting-slight.conf": "<?xml version=\"1.0\"?>\n<!DOCTYPE fontconfig SYSTEM \"urn:fontconfig:fonts.dtd\">\n<fontconfig>\n  <match target=\"font\">\n    <edit mode=\"assign\" name=\"hinting\"><bool>true</bool></edit>\n    <edit mode=\"assign\" name=\"hintstyle\"><const>hintslight</const></edit>\n  </match>\n</fontconfig>\n",
            "10-scale-bitmap-fonts.conf": "<?xml version=\"1.0\"?>\n<!DOCTYPE fontconfig SYSTEM \"urn:fontconfig:fonts.dtd\">\n<fontconfig>\n  <match target=\"font\">\n    <edit mode=\"assign\" name=\"scalable\"><bool>true</bool></edit>\n  </match>\n</fontconfig>\n",
        }
        for name, content in defaults.items():
            fp = self.fonts_path / "conf.d" / name
            if not fp.exists():
                fp.write_text(content, encoding="utf-8")
                log.debug("Created /etc/fonts/conf.d/%s", name)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "fonts_path_exists": self.fonts_path.exists(),
            "fonts_conf_exists": (self.fonts_path / "fonts.conf").exists(),
            "local_conf_exists": (self.fonts_path / "local.conf").exists(),
            "conf_d_files": len(list((self.fonts_path / "conf.d").iterdir())) if (self.fonts_path / "conf.d").exists() else 0,
        }
