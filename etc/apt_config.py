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
UmerOS /etc APT Configuration
================================
Manages APT package manager configuration.

FHS 3.0 entries:
  /etc/apt/           — APT package manager configuration directory
  /etc/apt/sources.list     — APT package sources
  /etc/apt/sources.list.d/  — Additional APT sources
  /etc/apt/apt.conf         — APT configuration
  /etc/apt/apt.conf.d/      — APT configuration directory
  /etc/apt/preferences      — APT package preferences
  /etc/apt/preferences.d/   — APT preferences directory
  /etc/apt/trusted.gpg.d/   — APT trusted GPG keys
  /etc/apt/keyrings/        — APT keyrings

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Etc.AptConfig")


@dataclass
class APTSource:
    """Represents an APT package source."""
    uri: str
    distribution: str
    components: List[str] = field(default_factory=list)
    options: Dict[str, str] = field(default_factory=dict)
    comments: List[str] = field(default_factory=list)


@dataclass
class APTPreference:
    """Represents an APT package preference."""
    package: str
    pin: str
    priority: int
    comments: List[str] = field(default_factory=list)


class AptConfigManager:
    """
    Manages APT package manager configuration.

    Handles /etc/apt/sources.list, /etc/apt/apt.conf, /etc/apt/preferences,
    and related directories.
    """

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.apt_path = self.etc_path / "apt"
        self.sources_list_d_path = self.apt_path / "sources.list.d"
        self.apt_conf_d_path = self.apt_path / "apt.conf.d"
        self.preferences_d_path = self.apt_path / "preferences.d"
        self.trusted_gpg_d_path = self.apt_path / "trusted.gpg.d"
        self.keyrings_path = self.apt_path / "keyrings"

    def initialize(self) -> bool:
        """Create all APT configuration files with defaults."""
        try:
            self.apt_path.mkdir(parents=True, exist_ok=True)
            self._create_sources_list()
            self._create_apt_conf()
            self._create_apt_conf_d()
            self._create_preferences()
            self._create_preferences_d()
            self._create_sources_list_d()
            self._create_trusted_gpg_d()
            self._create_keyrings()
            log.info("Initialized APT configuration files")
            return True
        except Exception as e:
            log.error("Failed to initialize APT config: %s", e)
            return False

    # ── /etc/apt/sources.list ────────────────────────────────────────────

    def _create_sources_list(self) -> None:
        """Create /etc/apt/sources.list (APT package sources)."""
        filepath = self.apt_path / "sources.list"
        if filepath.exists():
            return
        content = """# /etc/apt/sources.list - APT package sources
# UmerOS APT Sources Configuration
# See sources.list(5) for details.

# Main repository
deb http://archive.ubuntu.com/ubuntu/ jammy main restricted universe multiverse
deb-src http://archive.ubuntu.com/ubuntu/ jammy main restricted universe multiverse

# Security updates
deb http://security.ubuntu.com/ubuntu/ jammy-security main restricted universe multiverse
deb-src http://security.ubuntu.com/ubuntu/ jammy-security main restricted universe multiverse

# Updates
deb http://archive.ubuntu.com/ubuntu/ jammy-updates main restricted universe multiverse
deb-src http://archive.ubuntu.com/ubuntu/ jammy-updates main restricted universe multiverse

# Backports (uncomment to enable)
#deb http://archive.ubuntu.com/ubuntu/ jammy-backports main restricted universe multiverse
#deb-src http://archive.ubuntu.com/ubuntu/ jammy-backports main restricted universe multiverse

# Partner repository (uncomment to enable)
#deb http://archive.canonical.com/ubuntu/ jammy partner
#deb-src http://archive.canonical.com/ubuntu/ jammy partner
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/apt/sources.list")

    # ── /etc/apt/apt.conf ────────────────────────────────────────────────

    def _create_apt_conf(self) -> None:
        """Create /etc/apt/apt.conf (APT configuration)."""
        filepath = self.apt_path / "apt.conf"
        if filepath.exists():
            return
        content = """// /etc/apt/apt.conf - APT configuration
// UmerOS APT Configuration
// See apt.conf(5) for details.

// Default options
APT::Get::Assume-Yes "false";
APT::Get::Force-LoopBreak "false";
APT::Get::Fix-Broken "true";

// Cache options
Dir::Cache "/var/cache/apt";
Dir::State "/var/lib/apt";

// Network options
Acquire::http::Timeout "30";
Acquire::ftp::Timeout "30";

// Download options
Acquire::Max-Loop "13";
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/apt/apt.conf")

    # ── /etc/apt/apt.conf.d/ ─────────────────────────────────────────────

    def _create_apt_conf_d(self) -> None:
        """Create /etc/apt/apt.conf.d/ directory with common configurations."""
        self.apt_conf_d_path.mkdir(parents=True, exist_ok=True)

        configs = {
            "00aptitude": """// /etc/apt/apt.conf.d/00aptitude
// Aptitude configuration
Aptitude::Delete-Unused "true";
""",
            "01autoremove": """// /etc/apt/apt.conf.d/01autoremove
// Auto-remove configuration
APT::AutoRemove::SuggestsImportant "false";
""",
            "02periodic": """// /etc/apt/apt.conf.d/02periodic
// Periodic update configuration
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "0";
APT::Periodic::Unattended-Upgrade "0";
""",
        }

        for filename, content in configs.items():
            filepath = self.apt_conf_d_path / filename
            if not filepath.exists():
                filepath.write_text(content, encoding="utf-8")
                log.debug("Created /etc/apt/apt.conf.d/%s", filename)

    # ── /etc/apt/preferences ─────────────────────────────────────────────

    def _create_preferences(self) -> None:
        """Create /etc/apt/preferences (APT package preferences)."""
        filepath = self.apt_path / "preferences"
        if filepath.exists():
            return
        content = """# /etc/apt/preferences - APT package preferences
# UmerOS APT Preferences Configuration
# See apt_preferences(5) for details.
#
# Format:
#   Package: package-name
#   Pin: pin-expression
#   Pin-Priority: priority-value

# Default priority
Package: *
Pin: release a=jammy
Pin-Priority: 990

# Security updates
Package: *
Pin: release a=jammy-security
Pin-Priority: 500

# Backports
Package: *
Pin: release a=jammy-backports
Pin-Priority: 100
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/apt/preferences")

    # ── /etc/apt/preferences.d/ ──────────────────────────────────────────

    def _create_preferences_d(self) -> None:
        """Create /etc/apt/preferences.d/ directory with base preferences."""
        self.preferences_d_path.mkdir(parents=True, exist_ok=True)
        base = self.preferences_d_path / "default"
        if not base.exists():
            content = """# /etc/apt/preferences.d/default
# Default APT preferences

Package: *
Pin: release a=jammy
Pin-Priority: 990
"""
            base.write_text(content, encoding="utf-8")
            log.debug("Created /etc/apt/preferences.d/default")

    # ── /etc/apt/sources.list.d/ ─────────────────────────────────────────

    def _create_sources_list_d(self) -> None:
        """Create /etc/apt/sources.list.d/ directory with base configuration."""
        self.sources_list_d_path.mkdir(parents=True, exist_ok=True)
        base = self.sources_list_d_path / "base.list"
        if not base.exists():
            content = """# /etc/apt/sources.list.d/base.list
# Base APT sources

deb http://archive.ubuntu.com/ubuntu/ jammy main restricted universe multiverse
deb-src http://archive.ubuntu.com/ubuntu/ jammy main restricted universe multiverse
"""
            base.write_text(content, encoding="utf-8")
            log.debug("Created /etc/apt/sources.list.d/base.list")

    # ── /etc/apt/trusted.gpg.d/ ──────────────────────────────────────────

    def _create_trusted_gpg_d(self) -> None:
        """Create /etc/apt/trusted.gpg.d/ directory."""
        self.trusted_gpg_d_path.mkdir(parents=True, exist_ok=True)
        readme = self.trusted_gpg_d_path / "README"
        if not readme.exists():
            content = """This directory contains GPG keyrings used to authenticate
packages. Do not modify files in this directory unless
you know what you are doing.
"""
            readme.write_text(content, encoding="utf-8")
            log.debug("Created /etc/apt/trusted.gpg.d/README")

    # ── /etc/apt/keyrings/ ───────────────────────────────────────────────

    def _create_keyrings(self) -> None:
        """Create /etc/apt/keyrings/ directory."""
        self.keyrings_path.mkdir(parents=True, exist_ok=True)
        readme = self.keyrings_path / "README"
        if not readme.exists():
            content = """This directory contains APT keyrings for signed packages.
Do not modify files in this directory unless you know what
you are doing.
"""
            readme.write_text(content, encoding="utf-8")
            log.debug("Created /etc/apt/keyrings/README")

    # ── Utility Methods ──────────────────────────────────────────────────

    def parse_sources_list(self) -> List[APTSource]:
        """Parse /etc/apt/sources.list into a list of sources."""
        filepath = self.apt_path / "sources.list"
        if not filepath.exists():
            return []
        sources = []
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 4 and parts[0] in ("deb", "deb-src"):
                sources.append(APTSource(
                    uri=parts[1],
                    distribution=parts[2],
                    components=parts[3:],
                ))
        return sources

    def parse_preferences(self) -> List[APTPreference]:
        """Parse /etc/apt/preferences into a list of preferences."""
        filepath = self.apt_path / "preferences"
        if not filepath.exists():
            return []
        prefs = []
        package = ""
        pin = ""
        priority = 0
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                if key == "Package":
                    package = value
                elif key == "Pin":
                    pin = value
                elif key == "Pin-Priority":
                    try:
                        priority = int(value)
                    except ValueError:
                        priority = 0
            elif line == "" or line.startswith(" "):
                # End of entry
                if package:
                    prefs.append(APTPreference(
                        package=package,
                        pin=pin,
                        priority=priority,
                    ))
                    package = ""
                    pin = ""
                    priority = 0
        if package:
            prefs.append(APTPreference(
                package=package,
                pin=pin,
                priority=priority,
            ))
        return prefs

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of APT configuration."""
        return {
            "apt_path_exists": self.apt_path.exists(),
            "sources_list_exists": (self.apt_path / "sources.list").exists(),
            "apt_conf_exists": (self.apt_path / "apt.conf").exists(),
            "preferences_exists": (self.apt_path / "preferences").exists(),
            "sources_list_d_exists": self.sources_list_d_path.exists(),
            "apt_conf_d_exists": self.apt_conf_d_path.exists(),
            "preferences_d_exists": self.preferences_d_path.exists(),
            "trusted_gpg_d_exists": self.trusted_gpg_d_path.exists(),
            "keyrings_exists": self.keyrings_path.exists(),
        }
