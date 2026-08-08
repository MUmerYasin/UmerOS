"""
UmerOS /etc/host.conf Configuration Manager
Manages resolver configuration.
"""

from pathlib import Path
from typing import List
from dataclasses import dataclass


@dataclass
class ResolverConfig:
    """Resolver configuration options."""
    order: str = "hosts,bind"
    multi: bool = True
    nospoof: bool = True
    spoofalert: bool = True
    spoof: str = "warn"
    trim: str = ""


class HostConfManager:
    """Manages /etc/host.conf - resolver configuration."""

    def __init__(self, hostconf_path: str = "/etc/host.conf"):
        self.hostconf_path = Path(hostconf_path)
        self.config = ResolverConfig()
        self._write_config()

    def set_order(self, order: str) -> None:
        """Set resolver order (e.g., 'hosts,bind')."""
        self.config.order = order
        self._write_config()

    def set_multi(self, enabled: bool) -> None:
        """Enable/disable multi-homed hosts."""
        self.config.multi = enabled
        self._write_config()

    def set_nospoof(self, enabled: bool) -> None:
        """Enable/disable spoof checking."""
        self.config.nospoof = enabled
        self._write_config()

    def set_trim(self, domains: str) -> None:
        """Set domains to trim from hostnames."""
        self.config.trim = domains
        self._write_config()

    def _write_config(self) -> None:
        """Write host.conf file."""
        content = "# /etc/host.conf - resolver configuration\n"
        content += "# Managed by UmerOS\n\n"
        content += f"order {self.config.order}\n"
        if self.config.multi:
            content += "multi on\n"
        if self.config.nospoof:
            content += "nospoof on\n"
        if self.config.spoofalert:
            content += "spoofalert warn\n"
        if self.config.trim:
            content += f"trim {self.config.trim}\n"
        self.hostconf_path.write_text(content, encoding='utf-8')
