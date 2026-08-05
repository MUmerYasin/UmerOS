"""
UmerOS /etc Network Configuration
===================================
Manages /etc/hosts, /etc/resolv.conf, /etc/hostname, /etc/network/interfaces.

FHS 3.0:
  /etc/hosts     — Host name database
  /etc/resolv.conf — DNS resolver configuration
  /etc/hostname  — Local hostname
  /etc/network/  — Network interface configuration (Debian)

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Etc.NetworkConfig")


class NetworkConfigManager:
    """
    Manages network configuration files in /etc.

    Handles /etc/hosts, /etc/resolv.conf, /etc/hostname, /etc/network/.
    """

    def __init__(self, etc_path: str = "/etc"):
        self.etc_path = Path(etc_path)
        self.hosts_path = self.etc_path / "hosts"
        self.resolv_path = self.etc_path / "resolv.conf"
        self.hostname_path = self.etc_path / "hostname"
        self.network_dir = self.etc_path / "network"

    # ── /etc/hosts ─────────────────────────────────────────────────────

    def parse_hosts(self) -> List[Dict]:
        """Parse /etc/hosts."""
        if not self.hosts_path.exists():
            return []
        entries = []
        for line in self.hosts_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                entries.append({
                    "ip": parts[0],
                    "canonical": parts[1],
                    "aliases": parts[2:],
                })
        return entries

    def add_host(self, ip: str, hostname: str, aliases: Optional[List[str]] = None) -> bool:
        """Add a host entry to /etc/hosts."""
        entries = self.parse_hosts()
        for e in entries:
            if e["ip"] == ip and e["canonical"] == hostname:
                return True  # Already exists
        entries.append({"ip": ip, "canonical": hostname, "aliases": aliases or []})
        return self._write_hosts(entries)

    def remove_host(self, ip: str, hostname: str) -> bool:
        """Remove a host entry from /etc/hosts."""
        entries = self.parse_hosts()
        new = [e for e in entries if not (e["ip"] == ip and e["canonical"] == hostname)]
        if len(new) == len(entries):
            return False
        return self._write_hosts(new)

    def resolve(self, hostname: str) -> Optional[str]:
        """Resolve hostname to IP from /etc/hosts."""
        for e in self.parse_hosts():
            if e["canonical"] == hostname or hostname in e["aliases"]:
                return e["ip"]
        return None

    def reverse_resolve(self, ip: str) -> Optional[str]:
        """Reverse-resolve IP to hostname."""
        for e in self.parse_hosts():
            if e["ip"] == ip:
                return e["canonical"]
        return None

    def _write_hosts(self, entries: List[Dict]) -> bool:
        """Write entries back to /etc/hosts."""
        lines = [
            "# /etc/hosts - Host name database",
            "# Format: IP_ADDRESS canonical_name [aliases...]",
        ]
        for e in entries:
            parts = [e["ip"], e["canonical"]] + e.get("aliases", [])
            lines.append("       ".join(parts))
        try:
            self.hosts_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return True
        except Exception as e:
            log.error("Failed to write /etc/hosts: %s", e)
            return False

    # ── /etc/resolv.conf ───────────────────────────────────────────────

    def parse_resolv_conf(self) -> Dict:
        """Parse /etc/resolv.conf."""
        result = {"nameservers": [], "search": [], "domain": "", "options": []}
        if not self.resolv_path.exists():
            return result
        for line in self.resolv_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            keyword = parts[0]
            value = parts[1]
            if keyword == "nameserver":
                result["nameservers"].append(value)
            elif keyword == "search":
                result["search"].extend(parts[1:])
            elif keyword == "domain":
                result["domain"] = value
            elif keyword == "options":
                result["options"].extend(parts[1:])
        return result

    def set_nameservers(self, servers: List[str]) -> bool:
        """Set nameservers in /etc/resolv.conf."""
        config = self.parse_resolv_conf()
        config["nameservers"] = servers
        return self._write_resolv_conf(config)

    def add_nameserver(self, server: str) -> bool:
        """Add a nameserver if not already present."""
        config = self.parse_resolv_conf()
        if server not in config["nameservers"]:
            config["nameservers"].append(server)
        return self._write_resolv_conf(config)

    def set_domain(self, domain: str) -> bool:
        """Set the domain name."""
        config = self.parse_resolv_conf()
        config["domain"] = domain
        return self._write_resolv_conf(config)

    def _write_resolv_conf(self, config: Dict) -> bool:
        """Write resolv.conf."""
        lines = ["# /etc/resolv.conf - DNS resolver configuration"]
        if config.get("domain"):
            lines.append(f"domain {config['domain']}")
        for ns in config.get("nameservers", []):
            lines.append(f"nameserver {ns}")
        if config.get("search"):
            lines.append("search " + " ".join(config["search"]))
        if config.get("options"):
            lines.append("options " + " ".join(config["options"]))
        try:
            self.resolv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return True
        except Exception as e:
            log.error("Failed to write /etc/resolv.conf: %s", e)
            return False

    # ── /etc/hostname ──────────────────────────────────────────────────

    def get_hostname(self) -> str:
        """Read hostname from /etc/hostname."""
        if self.hostname_path.exists():
            return self.hostname_path.read_text(encoding="utf-8").strip()
        return "umeros"

    def set_hostname(self, hostname: str) -> bool:
        """Write hostname to /etc/hostname."""
        try:
            self.hostname_path.write_text(hostname + "\n", encoding="utf-8")
            log.info("Set hostname to: %s", hostname)
            return True
        except Exception as e:
            log.error("Failed to write /etc/hostname: %s", e)
            return False

    # ── /etc/network/interfaces ────────────────────────────────────────

    def parse_interfaces(self) -> List[Dict]:
        """Parse /etc/network/interfaces (Debian-style)."""
        iface_file = self.network_dir / "interfaces"
        if not iface_file.exists():
            return []
        interfaces = []
        current = None
        for line in iface_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("auto ") or line.startswith("allow-hotplug "):
                name = line.split()[1] if len(line.split()) > 1 else ""
                current = {"name": name, "method": "dhcp", "options": {}}
                interfaces.append(current)
            elif line.startswith("iface "):
                parts = line.split()
                if len(parts) >= 4:
                    name = parts[1]
                    method = parts[3] if len(parts) > 3 else "dhcp"
                    current = {"name": name, "method": method, "options": {}}
                    interfaces.append(current)
            elif current and ("address" in line or "netmask" in line or "gateway" in line):
                key, _, value = line.partition(" ")
                current["options"][key.strip()] = value.strip()
        return interfaces

    # ── Utility ────────────────────────────────────────────────────────

    def get_network_summary(self) -> Dict:
        """Get a summary of all network configuration."""
        return {
            "hostname": self.get_hostname(),
            "hosts_entries": len(self.parse_hosts()),
            "nameservers": self.parse_resolv_conf().get("nameservers", []),
            "interfaces": len(self.parse_interfaces()),
        }
