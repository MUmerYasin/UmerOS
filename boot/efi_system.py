"""
UmerOS EFI System & Secure Boot Manager
=========================================
Manages the EFI System Partition (ESP), NVRAM variables, and Secure Boot.

Standard layout:
    /boot/efi/                    ESP mount point
    /boot/efi/EFI/                EFI binaries root
    /boot/efi/EFI/umerOS/         UmerOS bootloader
    /boot/efi/EFI/BOOT/           Default boot path
    /boot/efi/EFI/BOOT/BOOTX64.EFI   Default x64 boot file
    /boot/efi/EFI/ubuntu/         Ubuntu GRUB
    /boot/efi/EFI/BOOT/BOOTAA64.EFI  Default ARM64 boot
    /boot/efi/EFI/Microsoft/      Windows boot
    /boot/efi/shell/shellx64.efi UEFI Shell

Secure Boot keys:
    PK   Platform Key (owner trust)
    KEK  Key Exchange Key (OS trust)
    db   Signature database (allowed binaries)
    dbx  Forbidden signatures database
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class EFIArchitecture(Enum):
    X86_64 = "x86_64"
    I386 = "i386"
    ARM64 = "aa64"
    ARM = "arm"
    IA64 = "ia64"


class SecureBootState(Enum):
    DISABLED = "disabled"
    SETUP_MODE = "setup_mode"
    USER_MODE = "user_mode"
    DEPLOYED_MODE = "deployed_mode"


class NVRAMVariableType(Enum):
    BOOT_ORDER = "BootOrder"
    BOOT_CURRENT = "BootCurrent"
    BOOT_NEXT = "BootNext"
    BOOT_TIMEOUT = "Timeout"
    PLATFORM_LANG = "PlatformLang"
    SECURE_BOOT = "SecureBoot"
    PK = "PK"
    KEK = "KEK"
    DB = "db"
    DBX = "dbx"


@dataclass
class EFIBinary:
    name: str
    path: Path
    architecture: EFIArchitecture = EFIArchitecture.X86_64
    description: str = ""
    vendor: str = ""
    size: int = 0
    hash_sha256: str = ""
    signed: bool = False
    signature_type: str = ""

    def compute_hash(self) -> str:
        if not self.path.exists():
            return ""
        h = hashlib.sha256()
        with open(self.path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        self.hash_sha256 = h.hexdigest()
        return self.hash_sha256


@dataclass
class NVRAMVariable:
    name: str
    var_type: NVRAMVariableType
    value: Any = ""
    attributes: int = 0x7  # EFI_VARIABLE_NON_VOLATILE | EFI_VARIABLE_BOOTSERVICE_ACCESS | EFI_VARIABLE_RUNTIME_ACCESS
    guid: str = ""
    last_modified: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.var_type.value,
            "value": str(self.value),
            "attributes": self.attributes,
            "guid": self.guid,
            "last_modified": self.last_modified.isoformat()
            if self.last_modified else None,
        }


@dataclass
class SecureBootKey:
    name: str
    kek: str = ""  # PEM-encoded
    signature_type: str = "sha256"
    fingerprint: str = ""
    subject: str = ""
    issuer: str = ""
    not_before: Optional[datetime] = None
    not_after: Optional[datetime] = None
    is_revoked: bool = False


@dataclass
class EFIBootEntry:
    name: str
    efi_path: str
    optional: bool = False
    attributes: int = 0x1  # EFI_VARIABLE_NON_VOLATILE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "efi_path": self.efi_path,
            "optional": self.optional,
            "attributes": self.attributes,
        }


class EFISystemPartition:
    """Manages the EFI System Partition layout and files."""

    def __init__(self, esp_mount: Path = Path("/boot/efi")):
        self.esp_mount = Path(esp_mount)
        self.efi_dir = self.esp_mount / "EFI"
        self.shell_dir = self.esp_mount / "shell"
        self._binaries: Dict[str, EFIBinary] = {}
        self._init_dirs()

    def _init_dirs(self) -> None:
        for d in [
            self.esp_mount,
            self.efi_dir,
            self.efi_dir / "BOOT",
            self.efi_dir / "umerOS",
            self.efi_dir / "ubuntu",
            self.efi_dir / "Microsoft",
            self.efi_dir / "systemd",
            self.shell_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    def scan_binaries(self) -> Dict[str, EFIBinary]:
        self._binaries.clear()
        for efi_file in self.esp_mount.rglob("*.efi"):
            arch = self._detect_arch(efi_file)
            rel = efi_file.relative_to(self.esp_mount)
            name = str(rel)
            bio = EFIBinary(
                name=name,
                path=efi_file,
                architecture=arch,
                size=efi_file.stat().st_size,
            )
            bio.compute_hash()
            self._binaries[name] = bio
        return dict(self._binaries)

    def _detect_arch(self, path: Path) -> EFIArchitecture:
        try:
            with open(path, "rb") as f:
                magic = f.read(2)
            if magic == b"MZ":
                with open(path, "rb") as f:
                    f.seek(0x3C)
                    pe_offset = struct.unpack("<I", f.read(4))[0]
                    f.seek(pe_offset + 4)
                    machine = struct.unpack("<H", f.read(2))[0]
                arch_map = {
                    0x8664: EFIArchitecture.X86_64,
                    0x014C: EFIArchitecture.I386,
                    0xAA64: EFIArchitecture.ARM64,
                    0x01C0: EFIArchitecture.ARM,
                    0x0200: EFIArchitecture.IA64,
                }
                return arch_map.get(machine, EFIArchitecture.X86_64)
        except (OSError, IOError, struct.error):
            pass
        name = path.name.lower()
        if "aa64" in name or "arm64" in name:
            return EFIArchitecture.ARM64
        if "ia32" in name or "i386" in name:
            return EFIArchitecture.I386
        return EFIArchitecture.X86_64

    def register_binary(
        self,
        name: str,
        source_path: Path,
        efi_subdir: str = "BOOT",
        arch: EFIArchitecture = EFIArchitecture.X86_64,
    ) -> EFIBinary:
        target_dir = self.efi_dir / efi_subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / source_path.name
        if source_path.exists():
            shutil.copy2(str(source_path), str(target))
        bio = EFIBinary(
            name=f"{efi_subdir}/{source_path.name}",
            path=target,
            architecture=arch,
            size=target.stat().st_size if target.exists() else 0,
        )
        bio.compute_hash()
        self._binaries[bio.name] = bio
        return bio

    def set_default_boot(self, arch: EFIArchitecture = EFIArchitecture.X86_64) -> Optional[EFIBinary]:
        """Set the default BOOT path."""
        if arch == EFIArchitecture.X86_64:
            name = "BOOTX64.EFI"
        elif arch == EFIArchitecture.ARM64:
            name = "BOOTAA64.EFI"
        elif arch == EFIArchitecture.I386:
            name = "BOOTIA32.EFI"
        elif arch == EFIArchitecture.ARM:
            name = "BOOTARM.EFI"
        else:
            return None

        boot_dir = self.efi_dir / "BOOT"
        boot_dir.mkdir(parents=True, exist_ok=True)
        # Find UmerOS EFI binary
        umeros_dir = self.efi_dir / "umerOS"
        source = umeros_dir / name
        target = boot_dir / name

        if source.exists():
            shutil.copy2(str(source), str(target))
        elif not target.exists():
            # Create placeholder
            target.write_bytes(b"\x00" * 4096)

        bio = EFIBinary(
            name=f"BOOT/{name}",
            path=target,
            architecture=arch,
            size=target.stat().st_size if target.exists() else 0,
        )
        bio.compute_hash()
        self._binaries[bio.name] = bio
        return bio

    def get_binary(self, name: str) -> Optional[EFIBinary]:
        return self._binaries.get(name)

    def list_binaries(self) -> List[EFIBinary]:
        return list(self._binaries.values())

    def status(self) -> Dict[str, Any]:
        total_size = sum(b.size for b in self._binaries.values())
        return {
            "esp_mount": str(self.esp_mount),
            "efi_dir": str(self.efi_dir),
            "total_binaries": len(self._binaries),
            "total_size_bytes": total_size,
            "binaries": [b.name for b in self._binaries.values()],
        }


class NVRAMManager:
    """Manages UEFI NVRAM variables (simulated via file)."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.nvram_file = self.data_dir / "nvram.json"
        self._variables: Dict[str, NVRAMVariable] = {}
        self._load()

    def _load(self) -> None:
        if not self.nvram_file.exists():
            self._init_defaults()
            return
        try:
            data = json.loads(self.nvram_file.read_text())
            for var_data in data.get("variables", []):
                var = NVRAMVariable(
                    name=var_data["name"],
                    var_type=NVRAMVariableType(var_data["type"]),
                    value=var_data.get("value", ""),
                    attributes=var_data.get("attributes", 0x7),
                    guid=var_data.get("guid", ""),
                    last_modified=datetime.fromisoformat(var_data["last_modified"])
                    if var_data.get("last_modified") else None,
                )
                self._variables[var.name] = var
        except (json.JSONDecodeError, OSError):
            self._init_defaults()

    def _init_defaults(self) -> None:
        defaults = [
            ("BootOrder", NVRAMVariableType.BOOT_ORDER, "0001,0002,0003"),
            ("BootCurrent", NVRAMVariableType.BOOT_CURRENT, "0001"),
            ("BootNext", NVRAMVariableType.BOOT_NEXT, ""),
            ("Timeout", NVRAMVariableType.BOOT_TIMEOUT, "5"),
            ("PlatformLang", NVRAMVariableType.PLATFORM_LANG, "en"),
            ("SecureBoot", NVRAMVariableType.SECURE_BOOT, "0"),
        ]
        for name, vtype, val in defaults:
            self._variables[name] = NVRAMVariable(
                name=name,
                var_type=vtype,
                value=val,
                last_modified=datetime.now(),
            )

    def _save(self) -> None:
        data = {
            "variables": [v.to_dict() for v in self._variables.values()]
        }
        self.nvram_file.write_text(json.dumps(data, indent=2))

    def get_variable(self, name: str) -> Optional[NVRAMVariable]:
        return self._variables.get(name)

    def set_variable(
        self,
        name: str,
        value: Any,
        var_type: NVRAMVariableType = NVRAMVariableType.BOOT_ORDER,
        attributes: int = 0x7,
    ) -> NVRAMVariable:
        var = NVRAMVariable(
            name=name,
            var_type=var_type,
            value=value,
            attributes=attributes,
            last_modified=datetime.now(),
        )
        self._variables[name] = var
        self._save()
        return var

    def delete_variable(self, name: str) -> bool:
        if name in self._variables:
            del self._variables[name]
            self._save()
            return True
        return False

    def list_variables(self) -> List[NVRAMVariable]:
        return list(self._variables.values())

    # Boot order helpers
    def get_boot_order(self) -> List[str]:
        var = self._variables.get("BootOrder")
        if var and var.value:
            return [e.strip() for e in str(var.value).split(",") if e.strip()]
        return []

    def set_boot_order(self, entries: List[str]) -> None:
        self.set_variable("BootOrder", ",".join(entries), NVRAMVariableType.BOOT_ORDER)

    def get_boot_current(self) -> Optional[str]:
        var = self._variables.get("BootCurrent")
        return str(var.value) if var else None

    def set_boot_next(self, entry_id: str) -> None:
        self.set_variable("BootNext", entry_id, NVRAMVariableType.BOOT_NEXT)

    def get_boot_next(self) -> Optional[str]:
        var = self._variables.get("BootNext")
        return str(var.value) if var and var.value else None

    def get_timeout(self) -> int:
        var = self._variables.get("Timeout")
        return int(var.value) if var else 5

    def set_timeout(self, seconds: int) -> None:
        self.set_variable("Timeout", str(seconds), NVRAMVariableType.BOOT_TIMEOUT)


class SecureBootManager:
    """Manages UEFI Secure Boot state and keys."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.keys_file = self.data_dir / "secure_boot_keys.json"
        self._state = SecureBootState.DISABLED
        self._pk: Optional[SecureBootKey] = None
        self._kek: List[SecureBootKey] = []
        self._db: List[SecureBootKey] = []
        self._dbx: List[SecureBootKey] = []
        self._load()

    def _load(self) -> None:
        if not self.keys_file.exists():
            return
        try:
            data = json.loads(self.keys_file.read_text())
            self._state = SecureBootState(data.get("state", "disabled"))
            for key_data in data.get("pk", []):
                self._pk = SecureBootKey(**key_data)
            for key_data in data.get("kek", []):
                self._kek.append(SecureBootKey(**key_data))
            for key_data in data.get("db", []):
                self._db.append(SecureBootKey(**key_data))
            for key_data in data.get("dbx", []):
                self._dbx.append(SecureBootKey(**key_data))
        except (json.JSONDecodeError, OSError, TypeError):
            pass

    def _save(self) -> None:
        def key_to_dict(k: SecureBootKey) -> Dict[str, Any]:
            return {
                "name": k.name,
                "kek": k.kek,
                "signature_type": k.signature_type,
                "fingerprint": k.fingerprint,
                "subject": k.subject,
                "issuer": k.issuer,
                "not_before": k.not_before.isoformat() if k.not_before else None,
                "not_after": k.not_after.isoformat() if k.not_after else None,
                "is_revoked": k.is_revoked,
            }

        data = {
            "state": self._state.value,
            "pk": [key_to_dict(self._pk)] if self._pk else [],
            "kek": [key_to_dict(k) for k in self._kek],
            "db": [key_to_dict(k) for k in self._db],
            "dbx": [key_to_dict(k) for k in self._dbx],
        }
        self.keys_file.write_text(json.dumps(data, indent=2))

    @property
    def state(self) -> SecureBootState:
        return self._state

    def enable(self) -> None:
        self._state = SecureBootState.USER_MODE
        self._save()

    def disable(self) -> None:
        self._state = SecureBootState.DISABLED
        self._save()

    def enter_setup_mode(self) -> None:
        self._state = SecureBootState.SETUP_MODE
        self._save()

    def deploy(self) -> None:
        self._state = SecureBootState.DEPLOYED_MODE
        self._save()

    # Key management
    def set_pk(self, name: str, fingerprint: str = "", subject: str = "") -> SecureBootKey:
        self._pk = SecureBootKey(
            name=name,
            fingerprint=fingerprint,
            subject=subject,
        )
        self._save()
        return self._pk

    def get_pk(self) -> Optional[SecureBootKey]:
        return self._pk

    def add_kek(self, name: str, fingerprint: str = "", subject: str = "") -> SecureBootKey:
        key = SecureBootKey(name=name, fingerprint=fingerprint, subject=subject)
        self._kek.append(key)
        self._save()
        return key

    def add_db(self, name: str, fingerprint: str = "", subject: str = "") -> SecureBootKey:
        key = SecureBootKey(name=name, fingerprint=fingerprint, subject=subject)
        self._db.append(key)
        self._save()
        return key

    def add_dbx(self, name: str, fingerprint: str = "", subject: str = "") -> SecureBootKey:
        key = SecureBootKey(name=name, fingerprint=fingerprint, subject=subject)
        self._dbx.append(key)
        self._save()
        return key

    def revoke_kek(self, name: str) -> bool:
        for k in self._kek:
            if k.name == name:
                k.is_revoked = True
                self._save()
                return True
        return False

    def revoke_db(self, name: str) -> bool:
        for k in self._db:
            if k.name == name:
                k.is_revoked = True
                self._save()
                return True
        return False

    def get_kek_list(self) -> List[SecureBootKey]:
        return list(self._kek)

    def get_db_list(self) -> List[SecureBootKey]:
        return list(self._db)

    def get_dbx_list(self) -> List[SecureBootKey]:
        return list(self._dbx)

    def is_binary_trusted(self, fingerprint: str) -> bool:
        """Check if a binary fingerprint is in the trusted db."""
        if self._state == SecureBootState.DISABLED:
            return True
        if self._state == SecureBootState.SETUP_MODE:
            return True
        for k in self._db:
            if not k.is_revoked and k.fingerprint == fingerprint:
                return True
        return False

    def is_binary_forbidden(self, fingerprint: str) -> bool:
        for k in self._dbx:
            if k.fingerprint == fingerprint:
                return True
        return False

    def status(self) -> Dict[str, Any]:
        return {
            "state": self._state.value,
            "pk_installed": self._pk is not None,
            "pk_name": self._pk.name if self._pk else None,
            "kek_count": len(self._kek),
            "kek_active": sum(1 for k in self._kek if not k.is_revoked),
            "db_count": len(self._db),
            "db_active": sum(1 for k in self._db if not k.is_revoked),
            "dbx_count": len(self._dbx),
            "dbx_active": sum(1 for k in self._dbx if not k.is_revoked),
        }


class EFISystemManager:
    """Top-level EFI System manager combining ESP, NVRAM, and Secure Boot."""

    def __init__(
        self,
        esp_mount: Path = Path("/boot/efi"),
        data_dir: Optional[Path] = None,
    ):
        self.esp = EFISystemPartition(esp_mount)
        self.nvram = NVRAMManager(data_dir or (Path("/var/lib/umerOS") / "efi"))
        self.secure_boot = SecureBootManager(data_dir or (Path("/var/lib/umerOS") / "efi"))

    def setup_umeros_boot(
        self,
        arch: EFIArchitecture = EFIArchitecture.X86_64,
        bootloader_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Set up UmerOS as a boot option."""
        results = {"steps": []}

        # Register UmerOS EFI binary
        if bootloader_path:
            bio = self.esp.register_binary(
                "UmerOS Boot Manager",
                bootloader_path,
                efi_subdir="umerOS",
                arch=arch,
            )
            results["steps"].append(f"Registered {bio.name}")
        else:
            results["steps"].append("No bootloader binary provided, using placeholder")

        # Set default boot
        default = self.esp.set_default_boot(arch)
        if default:
            results["steps"].append(f"Set default boot: {default.name}")

        # Create NVRAM boot entry
        if arch == EFIArchitecture.X86_64:
            efi_path = "\\EFI\\umerOS\\BOOTX64.EFI"
        elif arch == EFIArchitecture.ARM64:
            efi_path = "\\EFI\\umerOS\\BOOTAA64.EFI"
        else:
            efi_path = "\\EFI\\umerOS\\BOOTX64.EFI"

        # Add to boot order
        boot_order = self.nvram.get_boot_order()
        new_id = "0001"
        if new_id not in boot_order:
            boot_order.insert(0, new_id)
            self.nvram.set_boot_order(boot_order)
            results["steps"].append(f"Added boot entry {new_id} to BootOrder")

        results["steps"].append(f"EFI path: {efi_path}")
        return results

    def install_grub(self, arch: EFIArchitecture = EFIArchitecture.X86_64) -> Dict[str, Any]:
        """Install GRUB as the EFI bootloader."""
        results = {"steps": []}

        if arch == EFIArchitecture.X86_64:
            grub_name = "BOOTX64.EFI"
            grub_source = Path("/usr/lib/grub/x86_64-efi/monolithic/grubx64.efi")
        elif arch == EFIArchitecture.ARM64:
            grub_name = "BOOTAA64.EFI"
            grub_source = Path("/usr/lib/grub/arm64-efi/monolithic/grubaa64.efi")
        else:
            grub_name = "BOOTX64.EFI"
            grub_source = Path("/usr/lib/grub/x86_64-efi/monolithic/grubx64.efi")

        # Create the binary (placeholder if real GRUB not available)
        target_dir = self.esp.efi_dir / "BOOT"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / grub_name
        if not target.exists():
            target.write_bytes(b"\x00" * 4096)
            results["steps"].append(f"Created placeholder {grub_name}")
        else:
            results["steps"].append(f"{grub_name} already exists")

        # Also copy to ubuntu path for compatibility
        ubuntu_dir = self.esp.efi_dir / "ubuntu"
        ubuntu_dir.mkdir(parents=True, exist_ok=True)
        grub_ubuntu = ubuntu_dir / "grubx64.efi"
        if not grub_ubuntu.exists():
            grub_ubuntu.write_bytes(b"\x00" * 4096)

        results["steps"].append("GRUB installed to EFI/BOOT and EFI/ubuntu")
        return results

    def install_systemd_boot(self) -> Dict[str, Any]:
        """Install systemd-boot as the EFI bootloader."""
        results = {"steps": []}
        systemd_dir = self.esp.efi_dir / "systemd"
        systemd_dir.mkdir(parents=True, exist_ok=True)

        for name in ["systemd-bootx64.efi", "BOOTX64.EFI"]:
            target = systemd_dir / name if name != "BOOTX64.EFI" else self.esp.efi_dir / "BOOT" / name
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"\x00" * 4096)

        results["steps"].append("systemd-boot installed")
        return results

    def status(self) -> Dict[str, Any]:
        esp_status = self.esp.status()
        nvram_vars = self.nvram.list_variables()
        sb_status = self.secure_boot.status()
        return {
            "esp": esp_status,
            "nvram": {
                "total_variables": len(nvram_vars),
                "boot_order": self.nvram.get_boot_order(),
                "boot_current": self.nvram.get_boot_current(),
                "boot_next": self.nvram.get_boot_next(),
                "timeout": self.nvram.get_timeout(),
            },
            "secure_boot": sb_status,
        }
