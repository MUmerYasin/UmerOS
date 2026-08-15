"""
UmerOS /srv — Master Service & Hierarchy Manager
=================================================

Central manager for site-specific service data (/srv) in UmerOS.

Integrates:
- Hierarchy management & single-tree provisioning 
- FHS 2.3 & 3.0 Compliance auditing
- Security profiles & POSIX permissions
- Protocol-specific adapters (WWW, FTP, Git, Rsync, TFTP, Samba/NFS)
- Automated backup, snapshot & restore
- JSON persistence & live directory discovery

Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from backup import SrvBackupManager
from fhs import (
    DEFAULT_SRV_ROOT,
    STANDARD_PROTOCOL_DIRS,
    FHSValidationResult,
    FHSValidator,
    OrganizationScheme,
    StandardProtocol,
)
from hierarchy import ServiceTreeLayout, SrvHierarchy
from permissions import PermissionAuditResult, SrvPermissionManager
from service import (
    ServiceAccessMode,
    ServiceConfig,
    ServiceRecord,
    ServiceStatus,
)

log = logging.getLogger("UmerOS.Srv.Manager")

DEFAULT_REGISTRY_PATH = Path("F:/Pension Person Details/UmerOS/srv/registry.json") if os.name == "nt" else Path("/var/lib/umeros/srv-registry.json")


class SrvManager:
    """
    Master manager for all services and data trees hosted under /srv.
    """

    def __init__(
        self,
        srv_root: Path | str = DEFAULT_SRV_ROOT,
        registry_path: Optional[Path | str] = None,
    ) -> None:
        self.root = Path(srv_root).resolve()
        self.registry_file = Path(registry_path or (self.root / "registry.json")).resolve()
        self.hierarchy = SrvHierarchy(self.root)
        self.backup_manager = SrvBackupManager(
            backup_dir=self.root / ".backups",
            srv_root=self.root,
        )
        self._services: Dict[str, ServiceRecord] = {}
        self.load_registry()
        self.auto_discover()

    # -------------------------------------------------------------------------
    # Registry & Persistence
    # -------------------------------------------------------------------------
    def load_registry(self) -> None:
        """Loads registered service metadata from JSON."""
        if not self.registry_file.exists():
            return

        try:
            with open(self.registry_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    for name, rec_data in data.items():
                        if isinstance(rec_data, dict):
                            self._services[name] = ServiceRecord.from_dict(rec_data)
        except Exception as e:
            log.warning(f"Failed to load srv registry from {self.registry_file}: {e}")

    def save_registry(self) -> None:
        """Saves current service metadata to JSON."""
        try:
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)
            data = {name: rec.to_dict() for name, rec in self._services.items()}
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)
        except Exception as e:
            log.error(f"Failed to save srv registry to {self.registry_file}: {e}")

    def auto_discover(self) -> List[str]:
        """
        Scans physical /srv directory and automatically registers any unmanaged service folders.
        """
        discovered = []
        if not self.root.exists():
            return discovered

        for item in self.root.iterdir():
            if item.is_dir() and not item.name.startswith((".", "__")) and not item.name.endswith(".py"):
                name = item.name
                if name not in self._services:
                    scheme, proto_str = FHSValidator.classify_path(item, self.root)
                    protocol = StandardProtocol.WWW
                    if proto_str and proto_str in STANDARD_PROTOCOL_DIRS:
                        try:
                            protocol = StandardProtocol(proto_str)
                        except ValueError:
                            protocol = StandardProtocol.CUSTOM

                    size, files, dirs = self.hierarchy.get_dir_stats(item)
                    fhs_check = FHSValidator.validate_service_path(item, self.root)

                    config = ServiceConfig(
                        name=name,
                        protocol=protocol,
                        scheme=scheme,
                    )
                    record = ServiceRecord(
                        name=name,
                        base_path=str(item),
                        data_path=str(item),
                        config=config,
                        status=ServiceStatus.ACTIVE,
                        size_bytes=size,
                        file_count=files,
                        dir_count=dirs,
                        is_fhs_compliant=fhs_check.is_compliant,
                    )
                    self._services[name] = record
                    discovered.append(name)

        if discovered:
            self.save_registry()
        return discovered

    # -------------------------------------------------------------------------
    # Service Lifecycle Management
    # -------------------------------------------------------------------------
    def create_service(
        self,
        name: str,
        protocol: StandardProtocol = StandardProtocol.WWW,
        scheme: OrganizationScheme = OrganizationScheme.BY_PROTOCOL,
        domain_or_dept: Optional[str] = None,
        subdirs: Optional[List[str]] = None,
        admin_contact: str = "admin@umeros.local",
        access_mode: ServiceAccessMode = ServiceAccessMode.READ_WRITE,
        apply_security: bool = True,
    ) -> ServiceRecord:
        """
        Creates a new service tree, configures security profile, and registers it.
        """
        # 1. Provision tree
        tree = self.hierarchy.create_service_tree(
            service_name=name,
            protocol=protocol,
            scheme=scheme,
            domain_or_dept=domain_or_dept,
            subdirs=subdirs,
        )

        # 2. Apply security profile
        if apply_security:
            SrvPermissionManager.apply_profile(tree.base_dir, protocol)

        # 3. Create config & record
        config = ServiceConfig(
            name=name,
            protocol=protocol,
            scheme=scheme,
            domain=domain_or_dept if scheme == OrganizationScheme.BY_DOMAIN else None,
            department=domain_or_dept if scheme == OrganizationScheme.BY_DEPARTMENT else None,
            admin_contact=admin_contact,
            access_mode=access_mode,
        )

        fhs_check = FHSValidator.validate_service_path(tree.base_dir, self.root)
        size, files, dirs = self.hierarchy.get_dir_stats(tree.base_dir)

        record = ServiceRecord(
            name=name,
            base_path=str(tree.base_dir),
            data_path=str(tree.data_dir),
            cgi_path=str(tree.cgi_dir) if tree.cgi_dir else None,
            upload_path=str(tree.upload_dir) if tree.upload_dir else None,
            conf_path=str(tree.conf_dir) if tree.conf_dir else None,
            config=config,
            status=ServiceStatus.ACTIVE,
            size_bytes=size,
            file_count=files,
            dir_count=dirs,
            is_fhs_compliant=fhs_check.is_compliant,
        )

        self._services[name] = record
        self.save_registry()
        return record

    def register_service(
        self,
        name: str,
        path: Path | str,
        protocol: StandardProtocol = StandardProtocol.WWW,
        config: Optional[ServiceConfig] = None,
    ) -> ServiceRecord:
        """
        Registers an existing directory as a service in /srv.
        """
        path_obj = Path(path).resolve()
        path_obj.mkdir(parents=True, exist_ok=True)

        cfg = config or ServiceConfig(name=name, protocol=protocol)
        size, files, dirs = self.hierarchy.get_dir_stats(path_obj)
        fhs_check = FHSValidator.validate_service_path(path_obj, self.root)

        record = ServiceRecord(
            name=name,
            base_path=str(path_obj),
            data_path=str(path_obj),
            config=cfg,
            status=ServiceStatus.ACTIVE,
            size_bytes=size,
            file_count=files,
            dir_count=dirs,
            is_fhs_compliant=fhs_check.is_compliant,
        )
        self._services[name] = record
        self.save_registry()
        return record

    def get_service(self, name: str) -> Optional[ServiceRecord]:
        """Retrieves a service record by name."""
        return self._services.get(name)

    def get_service_path(self, name: str) -> Optional[str]:
        """Returns the base data path of a service."""
        rec = self._services.get(name)
        return rec.base_path if rec else None

    def list_services(self) -> Dict[str, ServiceRecord]:
        """Returns a copy of all registered service records."""
        self.refresh_stats()
        return dict(self._services)

    def remove_service(self, name: str, delete_files: bool = False, force: bool = False) -> bool:
        """
        Unregisters a service and optionally deletes its directory tree.
        """
        if name not in self._services:
            return False

        rec = self._services.pop(name)
        self.save_registry()

        if delete_files:
            return self.hierarchy.delete_service_tree(rec.name, force=force)
        return True

    def refresh_stats(self) -> None:
        """Refreshes file size and counts for all services."""
        changed = False
        for rec in self._services.values():
            p = Path(rec.base_path)
            if p.exists():
                size, files, dirs = self.hierarchy.get_dir_stats(p)
                if size != rec.size_bytes or files != rec.file_count:
                    rec.size_bytes = size
                    rec.file_count = files
                    rec.dir_count = dirs
                    rec.updated_at = time.time()
                    changed = True
        if changed:
            self.save_registry()

    def audit_all(self) -> Dict[str, Any]:
        """
        Performs full FHS compliance and permission security audit across /srv.
        """
        self.refresh_stats()
        service_audits = {}
        total_violations = 0
        total_warnings = 0

        for name, rec in self._services.items():
            fhs_res = FHSValidator.validate_service_path(rec.base_path, self.root)
            perm_res = SrvPermissionManager.audit_service(rec.base_path)
            
            total_violations += len(fhs_res.violations) + len(perm_res.issues)
            total_warnings += len(fhs_res.warnings)

            service_audits[name] = {
                "fhs_compliant": fhs_res.is_compliant,
                "fhs_violations": fhs_res.violations,
                "fhs_warnings": fhs_res.warnings,
                "permission_secure": perm_res.is_secure,
                "permission_issues": perm_res.issues,
                "recommendations": fhs_res.recommendations + perm_res.recommendations,
            }

        return {
            "srv_root": str(self.root),
            "total_services": len(self._services),
            "total_violations": total_violations,
            "total_warnings": total_warnings,
            "is_healthy": total_violations == 0,
            "services": service_audits,
        }

    def get_summary(self) -> Dict[str, Any]:
        """Returns high-level statistics of /srv."""
        self.refresh_stats()
        total_size = sum(r.size_bytes for r in self._services.values())
        total_files = sum(r.file_count for r in self._services.values())
        protocols = {}
        for r in self._services.values():
            proto = r.config.protocol.value if isinstance(r.config.protocol, StandardProtocol) else str(r.config.protocol)
            protocols[proto] = protocols.get(proto, 0) + 1

        return {
            "root": str(self.root),
            "total_services": len(self._services),
            "total_size_bytes": total_size,
            "total_files": total_files,
            "protocol_breakdown": protocols,
            "services": [r.name for r in self._services.values()],
        }


# ── Global Module API for backward compatibility ──────────────────────────

_global_manager: Optional[SrvManager] = None


def get_default_manager() -> SrvManager:
    global _global_manager
    if _global_manager is None:
        _global_manager = SrvManager()
    return _global_manager


def register_service(
    name: str,
    path: str,
    protocol: Union[StandardProtocol, str] = StandardProtocol.WWW,
) -> None:
    mgr = get_default_manager()
    proto = StandardProtocol(protocol) if isinstance(protocol, str) else protocol
    mgr.register_service(name=name, path=path, protocol=proto)


def get_service_path(name: str) -> Optional[str]:
    return get_default_manager().get_service_path(name)


def list_services() -> Dict[str, str]:
    mgr = get_default_manager()
    return {name: rec.base_path for name, rec in mgr.list_services().items()}
