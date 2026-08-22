"""
UmerOS /srv — Service Models and Data Structures
=================================================

Defines the data models, configurations, and lifecycle structures for
services hosted within the /srv filesystem hierarchy.

Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import enum
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .fhs import OrganizationScheme, StandardProtocol


class ServiceStatus(str, enum.Enum):
    """Operational status of a service in /srv."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    ERROR = "error"
    STOPPED = "stopped"


class ServiceAccessMode(str, enum.Enum):
    """Access mode for service data."""
    READ_ONLY = "ro"
    READ_WRITE = "rw"
    RESTRICTED = "restricted"


@dataclass
class ServiceConfig:
    """Configuration specifications for a service in /srv."""
    name: str
    protocol: StandardProtocol = StandardProtocol.WWW
    scheme: OrganizationScheme = OrganizationScheme.BY_PROTOCOL
    domain: Optional[str] = None
    department: Optional[str] = None
    port: Optional[int] = None
    admin_contact: str = "admin@umeros.local"
    access_mode: ServiceAccessMode = ServiceAccessMode.READ_WRITE
    allow_anonymous: bool = False
    enable_cgi: bool = False
    enable_ssl: bool = False
    quota_bytes: int = 0  # 0 means unlimited
    custom_settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["protocol"] = self.protocol.value if isinstance(self.protocol, StandardProtocol) else str(self.protocol)
        d["scheme"] = self.scheme.value if isinstance(self.scheme, OrganizationScheme) else str(self.scheme)
        d["access_mode"] = self.access_mode.value if isinstance(self.access_mode, ServiceAccessMode) else str(self.access_mode)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceConfig":
        data_copy = dict(data)
        if "protocol" in data_copy and isinstance(data_copy["protocol"], str):
            try:
                data_copy["protocol"] = StandardProtocol(data_copy["protocol"])
            except ValueError:
                data_copy["protocol"] = StandardProtocol.CUSTOM
        if "scheme" in data_copy and isinstance(data_copy["scheme"], str):
            try:
                data_copy["scheme"] = OrganizationScheme(data_copy["scheme"])
            except ValueError:
                data_copy["scheme"] = OrganizationScheme.CUSTOM
        if "access_mode" in data_copy and isinstance(data_copy["access_mode"], str):
            try:
                data_copy["access_mode"] = ServiceAccessMode(data_copy["access_mode"])
            except ValueError:
                data_copy["access_mode"] = ServiceAccessMode.READ_WRITE
        return cls(**{k: v for k, v in data_copy.items() if k in cls.__dataclass_fields__})


@dataclass
class ServiceRecord:
    """Comprehensive metadata record for a registered /srv service."""
    name: str
    base_path: str
    data_path: str
    cgi_path: Optional[str] = None
    upload_path: Optional[str] = None
    conf_path: Optional[str] = None
    config: ServiceConfig = field(default_factory=lambda: ServiceConfig(name=""))
    status: ServiceStatus = ServiceStatus.ACTIVE
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    size_bytes: int = 0
    file_count: int = 0
    dir_count: int = 0
    is_fhs_compliant: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "base_path": self.base_path,
            "data_path": self.data_path,
            "cgi_path": self.cgi_path,
            "upload_path": self.upload_path,
            "conf_path": self.conf_path,
            "config": self.config.to_dict(),
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "size_bytes": self.size_bytes,
            "file_count": self.file_count,
            "dir_count": self.dir_count,
            "is_fhs_compliant": self.is_fhs_compliant,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceRecord":
        cfg_data = data.get("config", {})
        config = ServiceConfig.from_dict(cfg_data) if isinstance(cfg_data, dict) else ServiceConfig(name=data.get("name", ""))
        
        status_val = data.get("status", "active")
        try:
            status = ServiceStatus(status_val)
        except ValueError:
            status = ServiceStatus.ACTIVE

        return cls(
            name=data.get("name", ""),
            base_path=data.get("base_path", ""),
            data_path=data.get("data_path", ""),
            cgi_path=data.get("cgi_path"),
            upload_path=data.get("upload_path"),
            conf_path=data.get("conf_path"),
            config=config,
            status=status,
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            size_bytes=data.get("size_bytes", 0),
            file_count=data.get("file_count", 0),
            dir_count=data.get("dir_count", 0),
            is_fhs_compliant=data.get("is_fhs_compliant", True),
            metadata=data.get("metadata", {}),
        )
