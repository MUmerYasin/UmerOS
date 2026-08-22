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
UmerOS /etc Host Access Control
=================================
Manages TCP Wrappers configuration and hostname resolution ordering.

FHS 3.0 entries:
  /etc/hosts.allow  — TCP Wrappers: hosts allowed to connect
  /etc/hosts.deny   — TCP Wrappers: hosts denied from connecting
  /etc/host.conf    — Host resolution ordering
  /etc/resolv.conf  — DNS resolver configuration (managed by NetworkConfigManager)

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Etc.HostsAccess")


@dataclass
class HostsEntry:
    """Represents a TCP Wrappers entry."""
    daemon_list: str
    client_list: str
    options: str = ""
    comment: str = ""


@dataclass
class HostConfEntry:
    """Represents a host.conf resolution option."""
    key: str
    value: str


class HostsAccessManager:
    """
    Manages TCP Wrappers and host resolution configuration.

    Handles /etc/hosts.allow, /etc/hosts.deny, and /etc/host.conf.
    """

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)

    def initialize(self) -> bool:
        """Create all host access control files with defaults."""
        try:
            self._create_hosts_allow()
            self._create_hosts_deny()
            self._create_host_conf()
            log.info("Initialized host access control files")
            return True
        except Exception as e:
            log.error("Failed to initialize host access files: %s", e)
            return False

    # ── /etc/hosts.allow ─────────────────────────────────────────────────

    def _create_hosts_allow(self) -> None:
        """Create /etc/hosts.allow (TCP Wrappers allowed hosts)."""
        filepath = self.etc_path / "hosts.allow"
        if filepath.exists():
            return
        content = """# /etc/hosts.allow - TCP Wrappers allowed hosts
# UmerOS Host Access Control
# See hosts_access(5) for format information.
#
# Format: daemon_list : client_list [ : option ... ]
#
# Examples:
# sshd: 192.168.1. 10.0.0.
# sendmail: ALL
# ALL: LOCAL .example.com

# Allow all local connections
ALL: LOCAL

# Allow SSH from local network
#sshd: 192.168.1.0/24

# Allow specific daemons from anywhere
# sshd: ALL
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/hosts.allow")

    # ── /etc/hosts.deny ──────────────────────────────────────────────────

    def _create_hosts_deny(self) -> None:
        """Create /etc/hosts.deny (TCP Wrappers denied hosts)."""
        filepath = self.etc_path / "hosts.deny"
        if filepath.exists():
            return
        content = """# /etc/hosts.deny - TCP Wrappers denied hosts
# UmerOS Host Access Control
# See hosts_access(5) for format information.
#
# Format: daemon_list : client_list [ : option ... ]
#
# WARNING: Do NOT add anything here that would lock you out!
# The default policy is to allow all connections.

# Deny all by default (restrictive)
# ALL: ALL

# Log and deny known bad hosts
# ALL: .evil.com 10.0.0.0/8

# Deny specific daemons
# in.ftpd: ALL
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/hosts.deny")

    # ── /etc/host.conf ───────────────────────────────────────────────────

    def _create_host_conf(self) -> None:
        """Create /etc/host.conf (host resolution ordering)."""
        filepath = self.etc_path / "host.conf"
        if filepath.exists():
            return
        content = """# /etc/host.conf - Host resolution ordering
# UmerOS Host Resolution Configuration
# Determines the order in which name resolution is attempted.
#
# Valid options:
#   multi on/off   - Allow multiple IP addresses for a host
#   order on/off   - Check /etc/hosts first if on, DNS first if off
#   trim domain    - Remove domain suffix before lookup

# Order hosts first, then DNS
order hosts,bind

# Allow multiple addresses per host (round-robin)
multi on

# Trim domain suffix before lookup
#trim umeros.local
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/host.conf")

    # ── Utility Methods ──────────────────────────────────────────────────

    def parse_hosts_allow(self) -> List[HostsEntry]:
        """Parse /etc/hosts.allow into a list of entries."""
        filepath = self.etc_path / "hosts.allow"
        if not filepath.exists():
            return []
        entries = []
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) >= 3:
                entries.append(HostsEntry(
                    daemon_list=parts[0].strip(),
                    client_list=parts[1].strip(),
                    options=parts[2].strip(),
                ))
            elif len(parts) == 2:
                entries.append(HostsEntry(
                    daemon_list=parts[0].strip(),
                    client_list=parts[1].strip(),
                ))
        return entries

    def parse_hosts_deny(self) -> List[HostsEntry]:
        """Parse /etc/hosts.deny into a list of entries."""
        filepath = self.etc_path / "hosts.deny"
        if not filepath.exists():
            return []
        entries = []
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) >= 3:
                entries.append(HostsEntry(
                    daemon_list=parts[0].strip(),
                    client_list=parts[1].strip(),
                    options=parts[2].strip(),
                ))
            elif len(parts) == 2:
                entries.append(HostsEntry(
                    daemon_list=parts[0].strip(),
                    client_list=parts[1].strip(),
                ))
        return entries

    def parse_host_conf(self) -> List[HostConfEntry]:
        """Parse /etc/host.conf into a list of resolution options."""
        filepath = self.etc_path / "host.conf"
        if not filepath.exists():
            return []
        entries = []
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                entries.append(HostConfEntry(key=parts[0], value=parts[1]))
        return entries

    def add_hosts_allow_entry(self, daemon: str, client: str, options: str = "") -> bool:
        """Append an entry to /etc/hosts.allow."""
        filepath = self.etc_path / "hosts.allow"
        entry = f"{daemon}: {client}"
        if options:
            entry += f" : {options}"
        try:
            with filepath.open("a", encoding="utf-8") as f:
                f.write(f"\n{entry}")
            log.info("Added hosts.allow entry: %s", entry)
            return True
        except Exception as e:
            log.error("Failed to add hosts.allow entry: %s", e)
            return False

    def add_hosts_deny_entry(self, daemon: str, client: str, options: str = "") -> bool:
        """Append an entry to /etc/hosts.deny."""
        filepath = self.etc_path / "hosts.deny"
        entry = f"{daemon}: {client}"
        if options:
            entry += f" : {options}"
        try:
            with filepath.open("a", encoding="utf-8") as f:
                f.write(f"\n{entry}")
            log.info("Added hosts.deny entry: %s", entry)
            return True
        except Exception as e:
            log.error("Failed to add hosts.deny entry: %s", e)
            return False

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of host access configuration."""
        return {
            "hosts_allow_exists": (self.etc_path / "hosts.allow").exists(),
            "hosts_deny_exists": (self.etc_path / "hosts.deny").exists(),
            "host_conf_exists": (self.etc_path / "host.conf").exists(),
            "hosts_allow_entries": len(self.parse_hosts_allow()),
            "hosts_deny_entries": len(self.parse_hosts_deny()),
        }
