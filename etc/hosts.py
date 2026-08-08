"""
UmerOS /etc/hosts Manager
===========================
Manages the FHS-required /etc/hosts file for static hostname-to-IP mappings.

FHS 3.0 §4.6:
  /etc/hosts — Contains the textual form of the Internet Protocol addresses
  of hosts in a local network. This file should contain one line for each IP
  address, followed by one or more hostnames, separated by spaces. Lines
  starting with # are comments.

  Example:
    127.0.0.1       localhost
    ::1             localhost
    192.168.1.10    umeros  umeros.local

Conventions:
  - All paths constructed relative to configurable base_path (default "/")
  - I/O uses pathlib.Path
  - Methods return Dict[str, Any] with "success" key

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("UmerOS.Etc.Hosts")


# ─── Data Structures ────────────────────────────────────────────────────────


@dataclass
class HostsEntry:
    """A single line from /etc/hosts."""
    address: str
    hostnames: List[str] = field(default_factory=list)
    comment: str = ""

    @property
    def canonical(self) -> str:
        return self.hostnames[0] if self.hostnames else ""

    def to_line(self) -> str:
        parts = [self.address] + self.hostnames
        line = "    ".join(parts)
        if self.comment:
            line += f"  # {self.comment}"
        return line


# ─── Default entries ────────────────────────────────────────────────────────

DEFAULT_HOSTS: List[HostsEntry] = [
    HostsEntry("127.0.0.1", ["localhost"], "Loopback"),
    HostsEntry("::1", ["localhost", "ip6-localhost", "ip6-loopback"], "IPv6 loopback"),
    HostsEntry("127.0.1.1", [], "Resolvable hostname (optional)"),
]


# ─── HostsManager ──────────────────────────────────────────────────────────


class HostsManager:
    """Manages /etc/hosts — static hostname-to-IP address mappings."""

    def __init__(self, base_path: str = "/") -> None:
        self._base = Path(base_path)
        self._hosts_file = self._base / "etc" / "hosts"
        self._entries: List[HostsEntry] = []
        self._load()

    # ── I/O ──────────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Parse /etc/hosts into memory."""
        self._entries = []
        if not self._hosts_file.exists():
            log.info("Creating default /etc/hosts")
            self._write_defaults()
            return

        try:
            text = self._hosts_file.read_text(encoding="utf-8")
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    if line.startswith("#") and line.strip("#").strip():
                        # Pure comment line — skip
                        pass
                    continue

                # Split comment from data
                comment = ""
                if "  #" in line:
                    line, comment = line.split("  #", 1)
                    comment = comment.strip()
                elif line.count("#") and not line.startswith("#"):
                    parts = line.split("#", 1)
                    line = parts[0].strip()
                    comment = parts[1].strip()

                parts = line.split()
                if len(parts) < 1:
                    continue

                address = parts[0]
                hostnames = parts[1:]
                self._entries.append(HostsEntry(address, hostnames, comment))

            log.debug("Loaded %d entries from /etc/hosts", len(self._entries))
        except Exception as exc:
            log.error("Failed to parse /etc/hosts: %s", exc)
            self._entries = list(DEFAULT_HOSTS)

    def _write(self) -> bool:
        """Write current entries to /etc/hosts."""
        try:
            self._hosts_file.parent.mkdir(parents=True, exist_ok=True)
            lines = [
                "# /etc/hosts — Hostname-to-IP mappings",
                "# Managed by UmerOS HostsManager",
                "#",
                "",
            ]
            for entry in self._entries:
                lines.append(entry.to_line())
            lines.append("")  # trailing newline
            self._hosts_file.write_text("\n".join(lines), encoding="utf-8")
            log.info("Wrote %d entries to /etc/hosts", len(self._entries))
            return True
        except Exception as exc:
            log.error("Failed to write /etc/hosts: %s", exc)
            return False

    def _write_defaults(self) -> bool:
        """Write default /etc/hosts."""
        self._entries = list(DEFAULT_HOSTS)
        return self._write()

    # ── Public API ───────────────────────────────────────────────────────

    def get_entries(self) -> List[HostsEntry]:
        """Return all hosts entries."""
        return list(self._entries)

    def add_entry(self, address: str, hostnames: List[str],
                  comment: str = "", overwrite: bool = False) -> Dict[str, Any]:
        """
        Add a new address→hostname mapping.

        Args:
            address: IPv4 or IPv6 address.
            hostnames: List of hostnames (first is canonical).
            comment: Optional comment.
            overwrite: If True, replace existing entry for same address.

        Returns:
            Dict with success/data/error.
        """
        if not address:
            return {"success": False, "error": "address required"}
        if not hostnames:
            return {"success": False, "error": "at least one hostname required"}

        # Check duplicate address
        for i, entry in enumerate(self._entries):
            if entry.address == address:
                if overwrite:
                    self._entries[i] = HostsEntry(address, hostnames, comment)
                    if self._write():
                        return {"success": True, "data": {"action": "updated", "address": address}}
                    return {"success": False, "error": "write failed"}
                else:
                    # Append hostnames to existing
                    for h in hostnames:
                        if h not in entry.hostnames:
                            entry.hostnames.append(h)
                    if self._write():
                        return {"success": True, "data": {"action": "merged", "address": address}}
                    return {"success": False, "error": "write failed"}

        self._entries.append(HostsEntry(address, hostnames, comment))
        if self._write():
            return {"success": True, "data": {"action": "added", "address": address}}
        return {"success": False, "error": "write failed"}

    def remove_entry(self, address: str) -> Dict[str, Any]:
        """Remove entry by address."""
        for i, entry in enumerate(self._entries):
            if entry.address == address:
                self._entries.pop(i)
                if self._write():
                    return {"success": True, "data": {"removed": address}}
                return {"success": False, "error": "write failed"}
        return {"success": False, "error": f"address {address} not found"}

    def remove_hostname(self, hostname: str) -> Dict[str, Any]:
        """Remove a hostname from all entries."""
        removed = False
        for entry in self._entries:
            if hostname in entry.hostnames:
                entry.hostnames.remove(hostname)
                removed = True
        if removed:
            # Clean up entries with no hostnames
            self._entries = [e for e in self._entries if e.hostnames]
            if self._write():
                return {"success": True, "data": {"removed_hostname": hostname}}
        return {"success": False, "error": f"hostname {hostname} not found"}

    def lookup_address(self, hostname: str) -> Optional[str]:
        """Resolve a hostname to its IP address."""
        for entry in self._entries:
            if hostname in entry.hostnames:
                return entry.address
        return None

    def lookup_hostnames(self, address: str) -> List[str]:
        """Resolve an address to its hostnames."""
        for entry in self._entries:
            if entry.address == address:
                return list(entry.hostnames)
        return []

    def list_hosts(self) -> List[Dict[str, str]]:
        """Return all entries as list of dicts."""
        return [
            {"address": e.address, "hostnames": " ".join(e.hostnames), "comment": e.comment}
            for e in self._entries
        ]

    def has_entry(self, address: str) -> bool:
        """Check if an address exists."""
        return any(e.address == address for e in self._entries)

    def get_localhost(self) -> Optional[HostsEntry]:
        """Return the 127.0.0.1 localhost entry."""
        for entry in self._entries:
            if entry.address == "127.0.0.1" and "localhost" in entry.hostnames:
                return entry
        return None

    def reset_defaults(self) -> Dict[str, Any]:
        """Reset /etc/hosts to defaults."""
        self._entries = list(DEFAULT_HOSTS)
        if self._write():
            return {"success": True, "data": {"action": "reset_defaults"}}
        return {"success": False, "error": "write failed"}

    def export_raw(self) -> str:
        """Return the raw /etc/hosts content."""
        return "\n".join(e.to_line() for e in self._entries)
