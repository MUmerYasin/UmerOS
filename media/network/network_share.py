# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

"""
UmerOS /media/network - Network Share Definitions
=================================================

Defines network share types, protocols, credentials, and management.
Supports SMB/CIFS, NFS, SSHFS, FTP, WebDAV, and more.
"""

from __future__ import annotations

import enum
import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Media.Network.Share")


class ShareProtocol(str, enum.Enum):
    """Network share protocols."""
    SMB = "smb"           # SMB/CIFS (Windows shares)
    NFS = "nfs"           # NFS (Unix/Linux shares)
    SSHFS = "sshfs"       # SSH filesystem
    FTP = "ftp"           # FTP
    SFTP = "sftp"         # SFTP
    WEBDAV = "webdav"     # WebDAV
    AFP = "afp"           # Apple Filing Protocol
    GLUSTERFS = "glusterfs"  # GlusterFS
    CEPHFS = "cephfs"     # CephFS

    @property
    def display_name(self) -> str:
        _NAMES = {
            "smb": "SMB/CIFS (Windows)",
            "nfs": "NFS (Unix/Linux)",
            "sshfs": "SSHFS",
            "ftp": "FTP",
            "sftp": "SFTP",
            "webdav": "WebDAV",
            "afp": "AFP (Apple)",
            "glusterfs": "GlusterFS",
            "cephfs": "CephFS",
        }
        return _NAMES.get(self.value, self.value.upper())

    @property
    def default_port(self) -> int:
        _PORTS = {
            "smb": 445,
            "nfs": 2049,
            "sshfs": 22,
            "ftp": 21,
            "sftp": 22,
            "webdav": 80,
            "afp": 548,
            "glusterfs": 24007,
            "cephfs": 6789,
        }
        return _PORTS.get(self.value, 0)

    @property
    def mount_type(self) -> str:
        """Linux mount type string."""
        _TYPES = {
            "smb": "cifs",
            "nfs": "nfs",
            "sshfs": "fuse.sshfs",
            "ftp": "curlftpfs",
            "sftp": "fuse.sshfs",
            "webdav": "davfs2",
            "afp": "afpfs",
            "glusterfs": "glusterfs",
            "cephfs": "ceph",
        }
        return _TYPES.get(self.value, self.value)


class ShareStatus(str, enum.Enum):
    """Network share status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    MOUNTED = "mounted"
    ERROR = "error"
    UNMOUNTING = "unmounting"


@dataclass
class ShareCredentials:
    """Credentials for accessing a network share."""
    username: Optional[str] = None
    password: Optional[str] = None
    domain: Optional[str] = None
    key_file: Optional[str] = None  # SSH key file path
    anonymous: bool = False

    def to_mount_options(self, protocol: ShareProtocol) -> List[str]:
        """Convert credentials to mount options."""
        opts = []
        if self.anonymous:
            opts.append("guest")
        elif self.username:
            opts.append(f"username={self.username}")
            if self.password:
                opts.append(f"password={self.password}")
            if self.domain:
                opts.append(f"domain={self.domain}")
        if protocol == ShareProtocol.SMB:
            opts.append("iocharset=utf8")
            opts.append("file_mode=0777")
            opts.append("dir_mode=0777")
        elif protocol == ShareProtocol.NFS:
            opts.append("hard")
            opts.append("intr")
            opts.append("rsize=8192")
            opts.append("wsize=8192")
        return opts

    def redacted(self) -> dict:
        """Return credentials with password redacted."""
        return {
            "username": self.username,
            "password": "***" if self.password else None,
            "domain": self.domain,
            "key_file": self.key_file,
            "anonymous": self.anonymous,
        }


@dataclass
class NetworkShare:
    """A network share definition."""
    name: str
    protocol: ShareProtocol
    host: str
    path: str = "/"
    port: Optional[int] = None
    credentials: Optional[ShareCredentials] = None
    mount_point: Optional[str] = None
    status: ShareStatus = ShareStatus.DISCONNECTED
    auto_mount: bool = False
    read_only: bool = False
    created_at: float = 0.0
    last_connected: Optional[float] = None
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
        if self.port is None:
            self.port = self.protocol.default_port

    @property
    def uri(self) -> str:
        """Full URI for this share."""
        if self.protocol == ShareProtocol.SMB:
            return f"//{self.host}/{self.path.lstrip('/')}"
        elif self.protocol == ShareProtocol.NFS:
            return f"{self.host}:{self.path}"
        elif self.protocol in (ShareProtocol.SSHFS, ShareProtocol.SFTP):
            return f"{self.credentials.username if self.credentials and self.credentials.username else 'user'}@{self.host}:{self.path}"
        elif self.protocol == ShareProtocol.WEBDAV:
            return f"http://{self.host}:{self.port}{self.path}"
        elif self.protocol == ShareProtocol.FTP:
            return f"ftp://{self.host}:{self.port}{self.path}"
        return f"{self.protocol.value}://{self.host}{self.path}"

    @property
    def mount_type(self) -> str:
        return self.protocol.mount_type

    @property
    def is_mounted(self) -> bool:
        return self.status == ShareStatus.MOUNTED

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "protocol": self.protocol.value,
            "host": self.host,
            "path": self.path,
            "port": self.port,
            "credentials": self.credentials.redacted() if self.credentials else None,
            "mount_point": self.mount_point,
            "status": self.status.value,
            "auto_mount": self.auto_mount,
            "read_only": self.read_only,
            "created_at": self.created_at,
            "last_connected": self.last_connected,
            "error_message": self.error_message,
            "uri": self.uri,
        }


class NetworkShareManager:
    """Manages network shares and their mount state."""

    def __init__(self, media_root: str = "/media/network") -> None:
        self.media_root = media_root
        self._shares: Dict[str, NetworkShare] = {}
        self._mount_counter = 0

    def add_share(
        self,
        name: str,
        protocol: ShareProtocol,
        host: str,
        path: str = "/",
        port: Optional[int] = None,
        credentials: Optional[ShareCredentials] = None,
        auto_mount: bool = False,
        read_only: bool = False,
    ) -> NetworkShare:
        """Add a new network share."""
        if name in self._shares:
            raise ValueError(f"Share '{name}' already exists")
        share = NetworkShare(
            name=name,
            protocol=protocol,
            host=host,
            path=path,
            port=port,
            credentials=credentials,
            auto_mount=auto_mount,
            read_only=read_only,
        )
        self._shares[name] = share
        log.info("Added network share: %s (%s)", name, share.uri)
        return share

    def remove_share(self, name: str) -> bool:
        """Remove a network share. Unmounts first if mounted."""
        share = self._shares.get(name)
        if share is None:
            return False
        if share.is_mounted:
            self.unmount(name)
        del self._shares[name]
        log.info("Removed network share: %s", name)
        return True

    def get_share(self, name: str) -> Optional[NetworkShare]:
        return self._shares.get(name)

    def list_shares(self) -> List[NetworkShare]:
        return list(self._shares.values())

    def find_by_host(self, host: str) -> List[NetworkShare]:
        return [s for s in self._shares.values() if s.host == host]

    def find_by_protocol(self, protocol: ShareProtocol) -> List[NetworkShare]:
        return [s for s in self._shares.values() if s.protocol == protocol]

    @property
    def share_count(self) -> int:
        return len(self._shares)

    @property
    def mounted_count(self) -> int:
        return sum(1 for s in self._shares.values() if s.is_mounted)

    def mount(self, name: str, media_root: str = "/media/network", simulation: bool = True) -> "NetworkMountResult":
        """Mount a share by name."""
        from .network_mount import mount_share
        share = self._shares.get(name)
        if share is None:
            from .network_mount import NetworkMountResult
            return NetworkMountResult(success=False, error=f"Share '{name}' not found")
        result = mount_share(share, media_root=media_root, simulation=simulation)
        return result

    def unmount(self, name: str, force: bool = False, simulation: bool = True) -> "NetworkMountResult":
        """Unmount a share by name."""
        from .network_mount import unmount_share
        share = self._shares.get(name)
        if share is None:
            from .network_mount import NetworkMountResult
            return NetworkMountResult(success=False, error=f"Share '{name}' not found")
        result = unmount_share(share, force=force, simulation=simulation)
        return result