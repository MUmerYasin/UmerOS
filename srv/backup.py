"""
UmerOS /srv — Backup, Archive, and Restore Subsystem
====================================================

Provides automated snapshotting, archiving (tar.gz/zip), export, and restore
capabilities for site-specific service data hosted in /srv.

Features:
---------
* Atomic snapshots of service trees.
* Embedded metadata manifests in backups for perfect restoration.
* Support for tar.gz and zip formats.
* Safety checks to prevent accidental clobbering without explicit flags.

Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tarfile
import time
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# [FIX H265/H266] Guard against path traversal (CWE-22) when restoring service
# trees and when building the destination from the (attacker-controlled)
# manifest `service_name`.
import sys

try:
    from core.path_guard import safe_join, PathTraversalError
except Exception:  # pragma: no cover - standalone fallback
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.path_guard import safe_join, PathTraversalError

# [FIX H265/H266] Python < 3.12 lacks the fail-closed `filter=` argument on
# extractall(); fall back to no filter there (matching the >=3.12 target).
_FILTER_KW = {} if sys.version_info < (3, 12) else {"filter": "data"}

from .fhs import DEFAULT_SRV_ROOT
from .service import ServiceRecord

log = logging.getLogger("UmerOS.Srv.Backup")

DEFAULT_BACKUP_DIR = Path("F:/Pension Person Details/UmerOS/var/backups/srv") if os.name == "nt" else Path("/var/backups/srv")


@dataclass
class BackupManifest:
    """Manifest describing a service backup archive."""
    service_name: str
    backup_timestamp: float
    format: str
    original_base_path: str
    size_bytes: int
    file_count: int
    service_record: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BackupManifest":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SrvBackupManager:
    """Manages backup, archive, export, and restore operations for /srv."""

    def __init__(self, backup_dir: Path | str = DEFAULT_BACKUP_DIR, srv_root: Path | str = DEFAULT_SRV_ROOT) -> None:
        self.backup_dir = Path(backup_dir).resolve()
        self.srv_root = Path(srv_root).resolve()
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(
        self,
        service_path: Path | str,
        service_name: Optional[str] = None,
        archive_format: str = "tar.gz",
        service_record: Optional[ServiceRecord] = None,
    ) -> Path:
        """
        Creates a compressed backup archive of a service directory.
        """
        service_path = Path(service_path).resolve()
        if not service_path.exists():
            raise FileNotFoundError(f"Service path '{service_path}' does not exist.")

        name = service_name or service_path.name
        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        
        # Calculate stats
        total_size = 0
        total_files = 0
        for root, _, files in os.walk(service_path):
            for f in files:
                total_files += 1
                try:
                    total_size += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass

        manifest = BackupManifest(
            service_name=name,
            backup_timestamp=time.time(),
            format=archive_format,
            original_base_path=str(service_path),
            size_bytes=total_size,
            file_count=total_files,
            service_record=service_record.to_dict() if service_record else None,
        )

        manifest_file = self.backup_dir / f"{name}_manifest_{timestamp_str}.json"
        manifest_file.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")

        if archive_format in ("tar.gz", "tgz", "tar"):
            archive_file = self.backup_dir / f"{name}_{timestamp_str}.tar.gz"
            with tarfile.open(archive_file, "w:gz") as tar:
                tar.add(service_path, arcname=name)
                tar.add(manifest_file, arcname="manifest.json")
        elif archive_format == "zip":
            archive_file = self.backup_dir / f"{name}_{timestamp_str}.zip"
            with zipfile.ZipFile(archive_file, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(service_path):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, service_path.parent)
                        zipf.write(full_path, arcname=rel_path)
                zipf.write(manifest_file, arcname="manifest.json")
        else:
            raise ValueError(f"Unsupported backup format: {archive_format}")

        # Clean temp manifest
        if manifest_file.exists():
            manifest_file.unlink()

        return archive_file

    def restore_backup(
        self,
        archive_path: Path | str,
        target_root: Optional[Path | str] = None,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """
        Restores a service tree from a backup archive.
        """
        archive_path = Path(archive_path).resolve()
        target_root = Path(target_root or self.srv_root).resolve()

        if not archive_path.exists():
            raise FileNotFoundError(f"Backup archive '{archive_path}' not found.")

        manifest_data = {}
        # Extract to temporary directory first
        temp_dir = self.backup_dir / f"_temp_restore_{int(time.time())}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            if tarfile.is_tarfile(archive_path):
                with tarfile.open(archive_path, "r:*") as tar:
                    # [FIX H265] filter="data" makes tar extraction
                    # fail-closed against zip/tar-slip (CVE-2007-4559): members
                    # with ".." or absolute paths are rejected instead of
                    # escaping temp_dir.
                    tar.extractall(temp_dir, **_FILTER_KW)
            elif zipfile.is_zipfile(archive_path):
                with zipfile.ZipFile(archive_path, "r") as zipf:
                    # [FIX H266] same fail-closed extraction for zip archives.
                    zipf.extractall(temp_dir, **_FILTER_KW)
            else:
                raise ValueError("Unknown archive format.")

            manifest_path = temp_dir / "manifest.json"
            service_name = None
            if manifest_path.exists():
                manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
                service_name = manifest_data.get("service_name")
                manifest_path.unlink()

            # Find extracted service folder
            extracted_items = [p for p in temp_dir.iterdir() if p.is_dir()]
            if not extracted_items:
                raise RuntimeError("No service directory found in archive.")

            src_folder = extracted_items[0]
            # [FIX H195] Contain the destination against the manifest-supplied
            # `service_name` (attacker-controlled). A name like "../../etc" is
            # refused instead of writing the restored tree outside target_root.
            if service_name:
                try:
                    dest_folder = safe_join(target_root, service_name)
                except PathTraversalError:
                    raise ValueError(
                        f"Refusing unsafe service_name in backup: {service_name!r}"
                    )
            else:
                dest_folder = safe_join(target_root, src_folder.name)

            if dest_folder.exists():
                if not overwrite:
                    raise FileExistsError(
                        f"Destination '{dest_folder}' already exists. Use overwrite=True to replace."
                    )
                shutil.rmtree(dest_folder)

            shutil.copytree(src_folder, dest_folder)
            return {
                "success": True,
                "service_name": service_name or dest_folder.name,
                "restored_path": str(dest_folder),
                "manifest": manifest_data,
            }
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def list_backups(self) -> List[Dict[str, Any]]:
        """
        Lists all available backups in the backup directory.
        """
        backups = []
        if not self.backup_dir.exists():
            return backups

        for item in sorted(self.backup_dir.iterdir()):
            if item.is_file() and item.suffix in (".gz", ".zip", ".tar", ".tgz"):
                size = item.stat().st_size
                mtime = item.stat().st_mtime
                backups.append({
                    "filename": item.name,
                    "path": str(item),
                    "size_bytes": size,
                    "created_at": mtime,
                })
        return backups
