"""
UmerOS /etc/chrony.conf and /etc/chrony.d/ Configuration Manager
Manages NTP time synchronization via chrony.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ChronyServer:
    """A chrony NTP server entry."""
    address: str
    options: str = "iburst"
    pool: bool = False


@dataclass
class ChronyConfig:
    """Chrony configuration."""
    servers: List[ChronyServer] = field(default_factory=list)
    pool_servers: List[ChronyServer] = field(default_factory=list)
    driftfile: str = "/var/lib/chrony/drift"
    makestep: str = "1.0 3"
    rtcsync: bool = True
    logdir: str = "/var/log/chrony"


class ChronyConfigManager:
    """Manages /etc/chrony.conf and /etc/chrony.d/ configuration."""

    def __init__(self, chrony_path: str = "/etc"):
        self.chrony_path = Path(chrony_path)
        self.config = ChronyConfig()
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create chrony directory structure."""
        chrony_d = self.chrony_path / "chrony.d"
        chrony_d.mkdir(parents=True, exist_ok=True)

    def add_server(self, address: str, options: str = "iburst") -> None:
        """Add an NTP server."""
        server = ChronyServer(address=address, options=options)
        self.config.servers.append(server)

    def add_pool(self, address: str, options: str = "iburst") -> None:
        """Add an NTP pool."""
        pool = ChronyServer(address=address, options=options, pool=True)
        self.config.pool_servers.append(pool)

    def set_driftfile(self, path: str) -> None:
        """Set the driftfile path."""
        self.config.driftfile = path

    def set_makestep(self, threshold: str) -> None:
        """Set the makestep threshold."""
        self.config.makestep = threshold

    def write_config(self) -> None:
        """Write chrony.conf configuration file."""
        content = "# UmerOS Chrony Configuration\n\n"
        
        # Servers
        for server in self.config.servers:
            content += f"server {server.address} {server.options}\n"
        
        # Pools
        for pool in self.config.pool_servers:
            content += f"pool {pool.address} {pool.options}\n"
        
        content += f"\ndriftfile {self.config.driftfile}\n"
        content += f"makestep {self.config.makestep}\n"
        
        if self.config.rtcsync:
            content += "rtcsync\n"
        
        content += f"logdir {self.config.logdir}\n"
        
        config_path = self.chrony_path / "chrony.conf"
        config_path.write_text(content, encoding='utf-8')

    def get_config(self) -> ChronyConfig:
        """Get the current chrony configuration."""
        return self.config
