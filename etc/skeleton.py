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
UmerOS /etc Skeleton Directory
================================
Manages /etc/skel — default files copied to new home directories.

FHS 3.0 entries:
  /etc/skel/           — Skeleton directory for home directories
  /etc/skel/.profile  — Default shell profile
  /etc/skel/.bashrc   — Default bash configuration
  /etc/skel/.bash_logout — Default bash logout script

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

log = logging.getLogger("UmerOS.Etc.Skeleton")


class SkeletonManager:
    """Manages /etc/skel/ default home directory files."""

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.skel_path = self.etc_path / "skel"

    def initialize(self) -> bool:
        try:
            self.skel_path.mkdir(parents=True, exist_ok=True)
            self._create_profile()
            self._create_bashrc()
            self._create_bash_logout()
            log.info("Initialized /etc/skel")
            return True
        except Exception as e:
            log.error("Failed to initialize skeleton: %s", e)
            return False

    def _create_profile(self) -> None:
        fp = self.skel_path / ".profile"
        if fp.exists():
            return
        fp.write_text("# ~/.profile - executed by login shell\n\n"
                       "# Set PATH\nif [ -d \"$HOME/bin\" ] ; then\n"
                       "    PATH=\"$HOME/bin:$PATH\"\nfi\n", encoding="utf-8")
        log.debug("Created /etc/skel/.profile")

    def _create_bashrc(self) -> None:
        fp = self.skel_path / ".bashrc"
        if fp.exists():
            return
        fp.write_text("# ~/.bashrc - executed for interactive non-login shells\n\n"
                       "# If not running interactively, don't do anything\n"
                       "[ -z \"$PS1\" ] && return\n\n"
                       "# History settings\nHISTSIZE=1000\n"
                       "HISTFILESIZE=2000\nHISTCONTROL=ignoredups\n\n"
                       "# Aliases\nalias ls='ls --color=auto'\n"
                       "alias ll='ls -la'\nalias la='ls -A'\n", encoding="utf-8")
        log.debug("Created /etc/skel/.bashrc")

    def _create_bash_logout(self) -> None:
        fp = self.skel_path / ".bash_logout"
        if fp.exists():
            return
        fp.write_text("# ~/.bash_logout - executed when login shell exits\n\n"
                       "clear\n", encoding="utf-8")
        log.debug("Created /etc/skel/.bash_logout")

    def get_summary(self) -> Dict[str, Any]:
        return {
            "skel_exists": self.skel_path.exists(),
            "profile_exists": (self.skel_path / ".profile").exists(),
            "bashrc_exists": (self.skel_path / ".bashrc").exists(),
            "bash_logout_exists": (self.skel_path / ".bash_logout").exists(),
        }
