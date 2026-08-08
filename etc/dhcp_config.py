"""
UmerOS /etc DHCP & DNS Configuration
======================================
Manages DHCP client and DNS resolver configuration.

FHS 3.0 entries:
  /etc/dhclient.conf   — DHCP client configuration
  /etc/resolv.conf     — DNS resolver configuration
  /etc/resolvconf/     — Dynamic DNS resolver configuration directory

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Etc.DHCPConfig")


@dataclass
class DHClientOption:
    """Represents a dhclient.conf option."""
    name: str
    value: str
    interface: str = ""


@dataclass
class ResolverEntry:
    """Represents a DNS resolver configuration entry."""
    nameservers: List[str] = field(default_factory=lambda: ["8.8.8.8", "8.8.4.4"])
    search_domains: List[str] = field(default_factory=list)
    options: List[str] = field(default_factory=list)


class DHCPConfigManager:
    """
    Manages DHCP client and DNS resolver configuration.

    Handles /etc/dhclient.conf, /etc/resolv.conf, and /etc/resolvconf/.
    """

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.resolvconf_path = self.etc_path / "resolvconf"

    def initialize(self) -> bool:
        """Create all DHCP and DNS configuration files with defaults."""
        try:
            self._create_dhclient_conf()
            self._create_resolv_conf()
            self._create_resolvconf_dir()
            log.info("Initialized DHCP and DNS configuration files")
            return True
        except Exception as e:
            log.error("Failed to initialize DHCP/DNS config: %s", e)
            return False

    # ── /etc/dhclient.conf ───────────────────────────────────────────────

    def _create_dhclient_conf(self) -> None:
        """Create /etc/dhclient.conf (DHCP client configuration)."""
        filepath = self.etc_path / "dhclient.conf"
        if filepath.exists():
            return
        content = """# /etc/dhclient.conf - DHCP client configuration
# UmerOS DHCP Client Configuration
# See dhclient.conf(5) for details.

# Request these options from the DHCP server
#request subnet-mask, broadcast-address, routers, domain-name, domain-name-servers, host-name;

# Timeout for waiting for DHCP server responses
timeout 60;

# Retry interval in seconds
retry 60;

# Selects the interface to use for DHCP
#interface "eth0";

# Use the following DUID for DHCPv6
#send dhcp6.client-id 00:01:00:01:xx:xx:xx:xx:xx:xx:xx:xx;

# Request a specific lease time
#request time-offset, domain-name-servers, domain-name, netbios-name-servers, netbios-scope;

# Don't request a hostname
#send host-name "";

# Don't request domain name
#request domain-name;

# Don't request domain search list
#request domain-search;

# Use the following class identifier
#send vendor-class-identifier "UmerOS";

# Override the default lease time
#default-lease-time 600;
#max-lease-time 7200;

# Always use the same IP address for a given MAC address
#send dhcp-lease-time 3600;

# Request specific options
#option rfc3442-classless-static-routes code 121 = array of unsigned integer 8;

# Media Independent Interface (MII)
#medium "eth0";
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/dhclient.conf")

    # ── /etc/resolv.conf ─────────────────────────────────────────────────

    def _create_resolv_conf(self) -> None:
        """Create /etc/resolv.conf (DNS resolver configuration)."""
        filepath = self.etc_path / "resolv.conf"
        if filepath.exists():
            return
        content = """# /etc/resolv.conf - DNS resolver configuration
# UmerOS DNS Resolver Configuration
# This file is managed by the system. Do not edit manually.
# Use resolvconf or NetworkManager for dynamic updates.

# Domain name (append to short names)
#domain umeros.local

# Search domains (append to short names, in order)
#search umeros.local localdomain

# DNS nameservers (up to 3)
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1

# Options
# options timeout:2 attempts:3

# Sort list (sort addresses by this order)
# sortlist 192.168.1.0/24
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/resolv.conf")

    # ── /etc/resolvconf/ ─────────────────────────────────────────────────

    def _create_resolvconf_dir(self) -> None:
        """Create /etc/resolvconf directory with base configuration."""
        self.resolvconf_path.mkdir(parents=True, exist_ok=True)
        base = self.resolvconf_path / "resolv.conf.d" / "base.conf"
        if not base.exists():
            base.parent.mkdir(parents=True, exist_ok=True)
            content = """# /etc/resolvconf/resolv.conf.d/base.conf
# Base resolver configuration
# These options are applied to all interfaces

#options timeout:2 attempts:3 rotate
#options edns0
"""
            base.write_text(content, encoding="utf-8")
            log.debug("Created /etc/resolvconf/resolv.conf.d/base.conf")

    # ── Utility Methods ──────────────────────────────────────────────────

    def parse_dhclient_conf(self) -> List[DHClientOption]:
        """Parse /etc/dhclient.conf into a list of options."""
        filepath = self.etc_path / "dhclient.conf"
        if not filepath.exists():
            return []
        options = []
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                options.append(DHClientOption(name=parts[0], value=parts[1]))
        return options

    def parse_resolv_conf(self) -> ResolverEntry:
        """Parse /etc/resolv.conf into a ResolverEntry."""
        filepath = self.etc_path / "resolv.conf"
        if not filepath.exists():
            return ResolverEntry()
        entry = ResolverEntry()
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            keyword = parts[0].lower()
            value = parts[1]
            if keyword == "nameserver":
                entry.nameservers.append(value)
            elif keyword == "search":
                entry.search_domains.extend(parts[1:])
            elif keyword == "domain":
                entry.search_domains.append(value)
            elif keyword == "options":
                entry.options.extend(parts[1:])
        return entry

    def set_nameservers(self, servers: List[str]) -> bool:
        """Update /etc/resolv.conf with new nameservers."""
        filepath = self.etc_path / "resolv.conf"
        current = self.parse_resolv_conf()
        content = "# /etc/resolv.conf - DNS resolver configuration\n"
        content += "# Managed by UmerOS\n\n"
        for server in servers:
            content += f"nameserver {server}\n"
        if current.search_domains:
            content += f"search {' '.join(current.search_domains)}\n"
        if current.options:
            content += f"options {' '.join(current.options)}\n"
        try:
            filepath.write_text(content, encoding="utf-8")
            log.info("Updated /etc/resolv.conf with nameservers: %s", servers)
            return True
        except Exception as e:
            log.error("Failed to update resolv.conf: %s", e)
            return False

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of DHCP/DNS configuration."""
        resolver = self.parse_resolv_conf()
        return {
            "dhclient_conf_exists": (self.etc_path / "dhclient.conf").exists(),
            "resolv_conf_exists": (self.etc_path / "resolv.conf").exists(),
            "resolvconf_dir_exists": self.resolvconf_path.exists(),
            "nameservers": resolver.nameservers,
            "search_domains": resolver.search_domains,
        }
