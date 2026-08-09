"""
UmerOS systemd-boot Manager
==============================
Manages systemd-boot (systemd-bootctl), the simple UEFI boot manager.

Standard files:
    /boot/loader/                 systemd-boot root
    /boot/loader/loader.conf      Main configuration
    /boot/loader/entries/         Boot entries (*.conf)
    /boot/loader/entries/*.conf   Individual boot entries

Reference: https://www.freedesktop.org/software/systemd/man/systemd-boot.html
"""

from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class BootEntryType(Enum):
    LINUX = "linux"
    UEFI_SHELL = "efi-shell"
    UEFI_FIRMWARE = "efi-firmware"
    SNAPSHOTS = "snapshots"
    AUTO = "auto"


class EntrySortMode(Enum):
    VERSION = "version"
    ID = "id"
    DESCRIPTION = "description"
    DEFAULT = "default"


@dataclass
class BootEntry:
    title: str
    linux: Optional[str] = None
    initrd: Optional[str] = None
    options: str = ""
    version: Optional[str] = None
    machine_id: Optional[str] = None
    entry_type: BootEntryType = BootEntryType.LINUX
    sort_key: Optional[str] = None
    entry_filename: Optional[str] = None

    def to_conf(self) -> str:
        lines = []
        lines.append(f"title\t{self.title}")
        if self.linux:
            lines.append(f"linux\t{self.linux}")
        if self.initrd:
            lines.append(f"initrd\t{self.initrd}")
        if self.options:
            lines.append(f"options\t{self.options}")
        if self.version:
            lines.append(f"version\t{self.version}")
        if self.machine_id:
            lines.append(f"machine-id\t{self.machine_id}")
        if self.sort_key:
            lines.append(f"sort-key\t{self.sort_key}")
        return "\n".join(lines) + "\n"

    @classmethod
    def from_conf(cls, content: str, filename: Optional[str] = None) -> BootEntry:
        data: Dict[str, str] = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "\t" in line:
                key, _, val = line.partition("\t")
            elif " " in line:
                key, _, val = line.partition(" ")
            else:
                continue
            data[key.strip().lower()] = val.strip()

        entry_type = BootEntryType.LINUX
        if "efi-shell" in (filename or "").lower():
            entry_type = BootEntryType.UEFI_SHELL
        elif "efi-firmware" in (filename or "").lower():
            entry_type = BootEntryType.UEFI_FIRMWARE

        return cls(
            title=data.get("title", "Unknown"),
            linux=data.get("linux"),
            initrd=data.get("initrd"),
            options=data.get("options", ""),
            version=data.get("version"),
            machine_id=data.get("machine-id"),
            entry_type=entry_type,
            sort_key=data.get("sort-key"),
            entry_filename=filename,
        )


@dataclass
class LoaderConfig:
    default: str = "UmerOS.conf"
    timeout: int = 5
    console_mode: Optional[str] = None
    editor: bool = True
    auto_entries: bool = True
    auto_firmware: bool = True
    sort_key: Optional[str] = None
    beep_on_error: bool = True
    secure_boot_enroll: str = "no"

    def to_conf(self) -> str:
        lines = []
        lines.append(f"default\t{self.default}")
        lines.append(f"timeout\t{self.timeout}")
        if self.console_mode:
            lines.append(f"console-mode\t{self.console_mode}")
        lines.append(f"editor\t{'yes' if self.editor else 'no'}")
        lines.append(f"auto-entries\t{'yes' if self.auto_entries else 'no'}")
        lines.append(f"auto-firmware\t{'yes' if self.auto_firmware else 'no'}")
        if self.sort_key:
            lines.append(f"sort-key\t{self.sort_key}")
        lines.append(f"beep-on-error\t{'yes' if self.beep_on_error else 'no'}")
        lines.append(f"secure-boot-enroll\t{self.secure_boot_enroll}")
        return "\n".join(lines) + "\n"

    @classmethod
    def from_conf(cls, content: str) -> LoaderConfig:
        data: Dict[str, str] = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "\t" in line:
                key, _, val = line.partition("\t")
            elif " " in line:
                key, _, val = line.partition(" ")
            else:
                continue
            data[key.strip().lower()] = val.strip()

        def parse_bool(key: str, default: bool) -> bool:
            val = data.get(key, "").lower()
            if val in ("yes", "true", "1"):
                return True
            if val in ("no", "false", "0"):
                return False
            return default

        return cls(
            default=data.get("default", "UmerOS.conf"),
            timeout=int(data.get("timeout", "5")),
            console_mode=data.get("console-mode"),
            editor=parse_bool("editor", True),
            auto_entries=parse_bool("auto-entries", True),
            auto_firmware=parse_bool("auto-firmware", True),
            sort_key=data.get("sort-key"),
            beep_on_error=parse_bool("beep-on-error", True),
            secure_boot_enroll=data.get("secure-boot-enroll", "no"),
        )


class SystemdBootManager:
    """Manages systemd-boot configuration."""

    def __init__(self, boot_dir: Path):
        self.boot_dir = Path(boot_dir)
        self.loader_dir = self.boot_dir / "loader"
        self.entries_dir = self.loader_dir / "entries"
        self.config = LoaderConfig()
        self._entries: Dict[str, BootEntry] = {}
        self._init_dirs()
        self._scan_entries()

    def _init_dirs(self) -> None:
        self.loader_dir.mkdir(parents=True, exist_ok=True)
        self.entries_dir.mkdir(parents=True, exist_ok=True)

    def _scan_entries(self) -> None:
        self._entries.clear()
        if not self.entries_dir.exists():
            return
        for p in sorted(self.entries_dir.glob("*.conf")):
            try:
                content = p.read_text()
                entry = BootEntry.from_conf(content, filename=p.name)
                self._entries[p.name] = entry
            except (OSError, IOError):
                pass

    # --- Configuration ---

    def set_default(self, entry_name: str) -> None:
        self.config.default = entry_name

    def set_timeout(self, seconds: int) -> None:
        self.config.timeout = max(0, min(seconds, 60))

    def set_editor(self, enabled: bool) -> None:
        self.config.editor = enabled

    def set_console_mode(self, mode: str) -> None:
        self.config.console_mode = mode

    def write_loader_conf(self) -> Path:
        conf_path = self.loader_dir / "loader.conf"
        conf_path.write_text(self.config.to_conf())
        return conf_path

    def read_loader_conf(self) -> Optional[str]:
        conf_path = self.loader_dir / "loader.conf"
        if conf_path.exists():
            return conf_path.read_text()
        return None

    # --- Entries ---

    def add_entry(
        self,
        title: str,
        linux: str,
        initrd: Optional[str] = None,
        options: str = "root=LABEL=UmerOS ro",
        version: Optional[str] = None,
        machine_id: Optional[str] = None,
        filename: Optional[str] = None,
        set_as_default: bool = False,
    ) -> BootEntry:
        if not filename:
            safe_title = title.lower().replace(" ", "-")
            filename = f"{safe_title}.conf"

        entry = BootEntry(
            title=title,
            linux=linux,
            initrd=initrd,
            options=options,
            version=version,
            machine_id=machine_id,
            entry_filename=filename,
        )
        self._entries[filename] = entry

        entry_path = self.entries_dir / filename
        entry_path.write_text(entry.to_conf())

        if set_as_default:
            self.config.default = filename

        return entry

    def remove_entry(self, filename: str) -> bool:
        if filename in self._entries:
            entry_path = self.entries_dir / filename
            if entry_path.exists():
                entry_path.unlink()
            del self._entries[filename]
            if self.config.default == filename:
                remaining = list(self._entries.keys())
                self.config.default = remaining[0] if remaining else "UmerOS.conf"
            return True
        return False

    def get_entry(self, filename: str) -> Optional[BootEntry]:
        return self._entries.get(filename)

    def list_entries(self) -> Dict[str, BootEntry]:
        return dict(self._entries)

    def update_entry(self, filename: str, **kwargs: Any) -> bool:
        entry = self._entries.get(filename)
        if not entry:
            return False
        for key, val in kwargs.items():
            if hasattr(entry, key):
                setattr(entry, key, val)
        entry_path = self.entries_dir / filename
        entry_path.write_text(entry.to_conf())
        return True

    # --- Auto-generation ---

    def generate_entries_from_kernels(self, kernels: Dict[str, Any]) -> List[BootEntry]:
        """Auto-generate systemd-boot entries from detected kernels."""
        self._entries.clear()
        for p in self.entries_dir.glob("*.conf"):
            p.unlink()

        entries = []
        sorted_versions = sorted(kernels.keys())
        default_set = False
        for ver in sorted_versions:
            ki = kernels[ver]
            initrd_path = f"/boot/initrd.img-{ver}"
            if not Path(initrd_path).exists():
                initrd_path_alt = f"/boot/initrd-{ver}.img"
                if Path(initrd_path_alt).exists():
                    initrd_path = initrd_path_alt
                else:
                    initrd_path = None

            entry = self.add_entry(
                title=f"UmerOS {ver}",
                linux=f"/boot/vmlinuz-{ver}",
                initrd=initrd_path,
                options="root=LABEL=UmerOS ro quiet splash",
                version=ver,
                set_as_default=(not default_set),
            )
            entries.append(entry)
            default_set = True

        # Add recovery entry
        if entries:
            first = entries[0]
            self.add_entry(
                title=f"UmerOS {first.version} (recovery)",
                linux=first.linux,
                initrd=first.initrd,
                options="root=LABEL=UmerOS ro recovery nomodeset",
                version=first.version,
            )

        return entries

    # --- Backup / Restore ---

    def backup_entries(self, backup_dir_name: Optional[str] = None) -> Path:
        name = backup_dir_name or f"entries-backup-{int(time.time())}"
        backup_dir = self.loader_dir / name
        backup_dir.mkdir(parents=True, exist_ok=True)

        loader_conf = self.loader_dir / "loader.conf"
        if loader_conf.exists():
            shutil.copy2(str(loader_conf), str(backup_dir / "loader.conf"))

        for p in self.entries_dir.glob("*.conf"):
            shutil.copy2(str(p), str(backup_dir / p.name))

        return backup_dir

    def restore_entries(self, backup_dir_name: str) -> bool:
        backup_dir = self.loader_dir / backup_dir_name
        if not backup_dir.exists():
            return False

        loader_conf_bak = backup_dir / "loader.conf"
        if loader_conf_bak.exists():
            shutil.copy2(str(loader_conf_bak), str(self.loader_dir / "loader.conf"))

        for p in backup_dir.glob("*.conf"):
            if p.name == "loader.conf":
                continue
            shutil.copy2(str(p), str(self.entries_dir / p.name))

        self._scan_entries()
        return True

    def list_backups(self) -> List[str]:
        backups = []
        for d in self.loader_dir.iterdir():
            if d.is_dir() and d.name.startswith("entries-backup-"):
                backups.append(d.name)
        return sorted(backups)

    # --- Status ---

    def status(self) -> Dict[str, Any]:
        loader_conf_exists = (self.loader_dir / "loader.conf").exists()
        return {
            "loader_dir": str(self.loader_dir),
            "entries_dir": str(self.entries_dir),
            "loader_conf_exists": loader_conf_exists,
            "default_entry": self.config.default,
            "timeout": self.config.timeout,
            "editor_enabled": self.config.editor,
            "auto_entries": self.config.auto_entries,
            "total_entries": len(self._entries),
            "entries": list(self._entries.keys()),
        }
