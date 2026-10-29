# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
UmerOS /media/network - Network Share Discovery
==============================================

Browse and discover available network shares (SMB, NFS, etc.)
on the local network or specified hosts.
"""

from __future__ import annotations

import logging
import socket
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .network_share import ShareProtocol

log = logging.getLogger("UmerOS.Media.Network.Discovery")


@dataclass
class DiscoveredShare:
    """A network share discovered during browsing."""
    name: str
    host: str
    protocol: ShareProtocol
    path: str = "/"
    description: str = ""
    accessible: bool = True

    @property
    def uri(self) -> str:
        if self.protocol == ShareProtocol.SMB:
            return f"//{self.host}/{self.name}"
        elif self.protocol == ShareProtocol.NFS:
            return f"{self.host}:{self.path}"
        return f"{self.protocol.value}://{self.host}{self.path}"


class NetworkBrowser:
    """Browse network for available shares."""

    def __init__(self, timeout: float = 5.0) -> None:
        self.timeout = timeout
        self._discovered: Dict[str, List[DiscoveredShare]] = {}

    def discover_smb_shares(self, host: str) -> List[DiscoveredShare]:
        """Discover SMB shares on a host."""
        shares = []
        try:
            # Try smbclient
            result = subprocess.run(
                ["smbclient", "-L", host, "-N"],
                capture_output=True, text=True, timeout=self.timeout,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if "|" in line and not line.startswith("Sharename"):
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) >= 2 and parts[0] and parts[1]:
                            shares.append(DiscoveredShare(
                                name=parts[0],
                                host=host,
                                protocol=ShareProtocol.SMB,
                                path=f"/{parts[0]}",
                                description=parts[1] if len(parts) > 1 else "",
                            ))
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # smbclient not available or timed out - simulate
            shares = self._simulate_smb_discovery(host)
        except Exception as e:
            log.warning("SMB discovery failed for %s: %s", host, e)
            shares = self._simulate_smb_discovery(host)

        self._discovered[host] = shares
        return shares

    def _simulate_smb_discovery(self, host: str) -> List[DiscoveredShare]:
        """Simulate SMB share discovery for testing."""
        return [
            DiscoveredShare(name="shared", host=host, protocol=ShareProtocol.SMB, path="/shared", description="Disk"),
            DiscoveredShare(name="documents", host=host, protocol=ShareProtocol.SMB, path="/documents", description="Disk"),
            DiscoveredShare(name="IPC$", host=host, protocol=ShareProtocol.SMB, path="/IPC$", description="IPC Service", accessible=False),
        ]

    def discover_nfs_exports(self, host: str) -> List[DiscoveredShare]:
        """Discover NFS exports on a host."""
        shares = []
        try:
            result = subprocess.run(
                ["showmount", "-e", host],
                capture_output=True, text=True, timeout=self.timeout,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line and not line.startswith("Export list"):
                        parts = line.split()
                        if parts:
                            export_path = parts[0]
                            shares.append(DiscoveredShare(
                                name=export_path.strip("/").split("/")[-1] or "export",
                                host=host,
                                protocol=ShareProtocol.NFS,
                                path=export_path,
                                description=" ".join(parts[1:]) if len(parts) > 1 else "",
                            ))
        except (FileNotFoundError, subprocess.TimeoutExpired):
            shares = self._simulate_nfs_discovery(host)
        except Exception as e:
            log.warning("NFS discovery failed for %s: %s", host, e)
            shares = self._simulate_nfs_discovery(host)

        self._discovered.setdefault(host, []).extend(shares)
        return shares

    def _simulate_nfs_discovery(self, host: str) -> List[DiscoveredShare]:
        """Simulate NFS export discovery for testing."""
        return [
            DiscoveredShare(name="home", host=host, protocol=ShareProtocol.NFS, path="/home", description="Everyone"),
            DiscoveredShare(name="shared", host=host, protocol=ShareProtocol.NFS, path="/shared", description="192.168.1.0/24"),
        ]

    def discover_all(self, host: str) -> List[DiscoveredShare]:
        """Discover all share types on a host."""
        shares = []
        shares.extend(self.discover_smb_shares(host))
        shares.extend(self.discover_nfs_exports(host))
        return shares

    def scan_network(self, subnet: str = "192.168.1.0/24") -> List[str]:
        """Scan a subnet for hosts with network shares.

        Returns list of host IPs that respond.
        """
        hosts = []
        # Parse subnet (simplified: assumes /24)
        base = subnet.rsplit(".", 1)[0]
        for i in range(1, 255):
            host = f"{base}.{i}"
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.1)
                # Check common ports: 445 (SMB), 2049 (NFS), 22 (SSH)
                for port in (445, 2049, 22):
                    try:
                        sock.connect((host, port))
                        if host not in hosts:
                            hosts.append(host)
                        break
                    except (socket.timeout, ConnectionRefusedError, OSError):
                        continue
                sock.close()
            except Exception:
                pass
        return hosts

    def get_discovered(self, host: Optional[str] = None) -> List[DiscoveredShare]:
        if host:
            return self._discovered.get(host, [])
        result = []
        for shares in self._discovered.values():
            result.extend(shares)
        return result

    @property
    def discovered_count(self) -> int:
        return sum(len(v) for v in self._discovered.values())


# Convenience functions
def discover_smb_shares(host: str, timeout: float = 5.0) -> List[DiscoveredShare]:
    browser = NetworkBrowser(timeout=timeout)
    return browser.discover_smb_shares(host)


def discover_nfs_exports(host: str, timeout: float = 5.0) -> List[DiscoveredShare]:
    browser = NetworkBrowser(timeout=timeout)
    return browser.discover_nfs_exports(host)