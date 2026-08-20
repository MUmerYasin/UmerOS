"""
UmerOS Kernel Image Manager
============================
Manages vmlinuz (compressed), vmlinux (uncompressed), System.map, and config-*.

Standard files managed:
    /boot/vmlinuz-<ver>        Compressed kernel image
    /boot/vmlinux-<ver>        Uncompressed kernel (debug)
    /boot/System.map-<ver>     Kernel symbol table
    /boot/config-<ver>         Kernel build config
    /boot/vmlinux.bz2-<ver>    Bzip2 compressed vmlinux

FHS reference: https://refspecs.linuxfoundation.org/FHS_3.0/fhs/ch03s09.html
"""

from __future__ import annotations

import hashlib
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


class KernelArchitecture(Enum):
    X86_64 = "x86_64"
    ARM64 = "aarch64"
    ARM = "arm"
    I386 = "i386"
    PPC64LE = "ppc64le"
    S390X = "s390x"
    RISCV64 = "riscv64"
    UNKNOWN = "unknown"


class KernelCompression(Enum):
    NONE = "none"       # vmlinux
    GZIP = "gzip"       # vmlinuz.gz
    BZIP2 = "bzip2"     # vmlinuz.bz2
    XZ = "xz"           # vmlinuz.xz
    LZ4 = "lz4"         # vmlinuz.lz4
    ZSTD = "zstd"       # vmlinuz.zst
    LZO = "lzo"         # vmlinuz.lzo


class KernelSignatureType(Enum):
    UNSIGNED = "unsigned"
    PKCS7 = "pkcs7"
    PGP = "pgp"


@dataclass
class KernelSymbol:
    address: int
    symbol_type: str
    name: str
    module: Optional[str] = None

    def __str__(self) -> str:
        mod = f" [{self.module}]" if self.module else ""
        return f"{self.address:016x} {self.symbol_type} {self.name}{mod}"


@dataclass
class KernelConfig:
    version: str
    config_path: Path
    options: Dict[str, str] = field(default_factory=dict)
    booleans: Dict[str, bool] = field(default_factory=dict)

    def get(self, key: str, default: str = "") -> str:
        return self.options.get(key, default)

    def is_enabled(self, key: str) -> bool:
        val = self.options.get(key, "")
        if val == "y":
            return True
        if val == "m":
            return True
        return self.booleans.get(key, False)

    def is_module(self, key: str) -> bool:
        return self.options.get(key, "") == "m"

    def summary(self) -> Dict[str, int]:
        enabled = sum(1 for v in self.options.values() if v == "y")
        modules = sum(1 for v in self.options.values() if v == "m")
        disabled = sum(1 for v in self.options.values() if v == "n")
        return {
            "enabled_built_in": enabled,
            "enabled_as_module": modules,
            "disabled": disabled,
            "total_options": len(self.options),
        }


@dataclass
class KernelImage:
    version: str
    vmlinuz_path: Path
    architecture: KernelArchitecture = KernelArchitecture.X86_64
    compression: KernelCompression = KernelCompression.NONE
    build_time: Optional[datetime] = None
    vmlinux_path: Optional[Path] = None
    system_map_path: Optional[Path] = None
    config: Optional[KernelConfig] = None
    signature_type: KernelSignatureType = KernelSignatureType.UNSIGNED
    is_default: bool = False

    @property
    def vmlinuz_size(self) -> int:
        if self.vmlinuz_path.exists():
            return self.vmlinuz_path.stat().st_size
        return 0

    @property
    def vmlinuz_hash(self) -> str:
        if not self.vmlinuz_path.exists():
            return ""
        h = hashlib.sha256()
        with open(self.vmlinuz_path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()


class KernelImageManager:
    """Manages kernel images under /boot/."""

    MAGIC_GZIP = b"\x1f\x8b"
    MAGIC_BZIP2 = b"BZ"
    MAGIC_XZ = b"\xfd7zXZ\x00"
    MAGIC_LZ4 = b"\x02\x21\x4c\x18"
    MAGIC_ZSTD = b"\x28\xb5\x2f\xfd"
    MAGIC_LZO = b"\x89"
    ELF_MAGIC = b"\x7fELF"

    def __init__(self, boot_dir: Path):
        self.boot_dir = Path(boot_dir)
        self.boot_dir.mkdir(parents=True, exist_ok=True)
        self._kernels: Dict[str, KernelImage] = {}
        self._default_version: Optional[str] = None
        self._scan()

    def _scan(self) -> None:
        """Scan /boot for existing kernel images."""
        self._kernels.clear()

        # Find vmlinuz files
        for p in self.boot_dir.glob("vmlinuz-*"):
            ver = p.name[len("vmlinuz-"):]
            if ver.endswith(".sig"):
                continue

            vmlinux = self.boot_dir / f"vmlinux-{ver}"
            sysmap = self.boot_dir / f"System.map-{ver}"
            config = self.boot_dir / f"config-{ver}"

            comp = self._detect_compression(p)
            arch = self._detect_architecture(p)
            sig = self._detect_signature(p)

            kc = None
            if config.exists():
                kc = self._parse_config(config, ver)

            ki = KernelImage(
                version=ver,
                vmlinuz_path=p,
                architecture=arch,
                compression=comp,
                vmlinux_path=vmlinux if vmlinux.exists() else None,
                system_map_path=sysmap if sysmap.exists() else None,
                config=kc,
                signature_type=sig,
            )
            self._kernels[ver] = ki

        # Determine default (latest or last configured)
        if self._kernels and not self._default_version:
            self._default_version = max(self._kernels.keys())

    def _detect_compression(self, path: Path) -> KernelCompression:
        try:
            with open(path, "rb") as f:
                magic = f.read(6)
        except (OSError, IOError):
            return KernelCompression.NONE

        if magic[:2] == self.MAGIC_GZIP:
            return KernelCompression.GZIP
        if magic[:3] == self.MAGIC_BZIP2:
            return KernelCompression.BZIP2
        if magic[:6] == self.MAGIC_XZ:
            return KernelCompression.XZ
        if magic[:4] == self.MAGIC_LZ4:
            return KernelCompression.LZ4
        if magic[:4] == self.MAGIC_ZSTD:
            return KernelCompression.ZSTD
        if magic[:1] == self.MAGIC_LZO:
            return KernelCompression.LZO
        return KernelCompression.NONE

    def _detect_architecture(self, path: Path) -> KernelArchitecture:
        try:
            with open(path, "rb") as f:
                magic = f.read(4)
            if magic == self.ELF_MAGIC:
                with open(path, "rb") as f:
                    f.seek(4)
                    ei_class = f.read(1)
                    ei_data = f.read(1)
                    if ei_class == b"\x02":
                        return KernelArchitecture.X86_64
                    elif ei_class == b"\x01":
                        return KernelArchitecture.I386
        except (OSError, IOError):
            pass
        # Fallback: guess from hostname
        try:
            machine = subprocess.check_output(
                ["uname", "-m"], text=True, timeout=5
            ).strip()
            mapping = {
                "x86_64": KernelArchitecture.X86_64,
                "aarch64": KernelArchitecture.ARM64,
                "armv7l": KernelArchitecture.ARM,
                "i686": KernelArchitecture.I386,
                "i386": KernelArchitecture.I386,
                "ppc64le": KernelArchitecture.PPC64LE,
                "s390x": KernelArchitecture.S390X,
                "riscv64": KernelArchitecture.RISCV64,
            }
            return mapping.get(machine, KernelArchitecture.UNKNOWN)
        except Exception:
            return KernelArchitecture.UNKNOWN

    def _detect_signature(self, path: Path) -> KernelSignatureType:
        sig_file = Path(str(path) + ".sig")
        if sig_file.exists():
            return KernelSignatureType.PGP
        return KernelSignatureType.UNSIGNED

    def _parse_config(self, config_path: Path, version: str) -> KernelConfig:
        options: Dict[str, str] = {}
        booleans: Dict[str, bool] = {}
        try:
            with open(config_path, "r", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, _, val = line.partition("=")
                        key = key.strip()
                        val = val.strip()
                        if val in ("y", "n", "m"):
                            options[key] = val
                            booleans[key] = val == "y"
                        else:
                            options[key] = val
        except (OSError, IOError):
            pass
        return KernelConfig(version=version, config_path=config_path,
                            options=options, booleans=booleans)

    # --- public API ---

    @property
    def kernels(self) -> Dict[str, KernelImage]:
        return dict(self._kernels)

    @property
    def default_version(self) -> Optional[str]:
        return self._default_version

    def set_default(self, version: str) -> bool:
        if version not in self._kernels:
            return False
        self._default_version = version
        for k in self._kernels.values():
            k.is_default = (k.version == version)
        return True

    def register_kernel(
        self,
        version: str,
        vmlinuz_path: Path,
        vmlinux_path: Optional[Path] = None,
        system_map_path: Optional[Path] = None,
        config_path: Optional[Path] = None,
        set_as_default: bool = False,
    ) -> KernelImage:
        """Register a kernel image into the manager."""
        target = self.boot_dir / f"vmlinuz-{version}"
        if vmlinuz_path != target and vmlinuz_path.exists():
            shutil.copy2(str(vmlinuz_path), str(target))

        if vmlinux_path and vmlinux_path.exists():
            vt = self.boot_dir / f"vmlinux-{version}"
            if vmlinux_path != vt:
                shutil.copy2(str(vmlinux_path), str(vt))

        if system_map_path and system_map_path.exists():
            st = self.boot_dir / f"System.map-{version}"
            if system_map_path != st:
                shutil.copy2(str(system_map_path), str(st))

        config = None
        if config_path and config_path.exists():
            ct = self.boot_dir / f"config-{version}"
            if config_path != ct:
                shutil.copy2(str(config_path), str(ct))
            config = self._parse_config(ct, version)

        comp = self._detect_compression(target)
        arch = self._detect_architecture(target)
        sig = self._detect_signature(target)

        ki = KernelImage(
            version=version,
            vmlinuz_path=target,
            architecture=arch,
            compression=comp,
            build_time=datetime.now(),
            vmlinux_path=self.boot_dir / f"vmlinux-{version}"
            if (self.boot_dir / f"vmlinux-{version}").exists()
            else None,
            system_map_path=self.boot_dir / f"System.map-{version}"
            if (self.boot_dir / f"System.map-{version}").exists()
            else None,
            config=config,
            signature_type=sig,
            is_default=set_as_default,
        )
        self._kernels[version] = ki
        if set_as_default:
            self._default_version = version
        return ki

    def get_kernel(self, version: str) -> Optional[KernelImage]:
        return self._kernels.get(version)

    def remove_kernel(self, version: str) -> bool:
        if version not in self._kernels:
            return False

        ki = self._kernels[version]
        removed_files = []
        for attr in ("vmlinuz_path", "vmlinux_path", "system_map_path"):
            p = getattr(ki, attr, None)
            if p and Path(p).exists():
                Path(p).unlink()
                removed_files.append(str(p))

        if ki.config and ki.config.config_path.exists():
            ki.config.config_path.unlink()
            removed_files.append(str(ki.config.config_path))

        del self._kernels[version]
        if self._default_version == version:
            self._default_version = (
                max(self._kernels.keys()) if self._kernels else None
            )
        return True

    def list_versions(self) -> List[str]:
        return sorted(self._kernels.keys())

    def get_vmlinuz_path(self, version: Optional[str] = None) -> Optional[Path]:
        ver = version or self._default_version
        if not ver:
            return None
        ki = self._kernels.get(ver)
        return ki.vmlinuz_path if ki else None

    def get_cmdline_from_config(self, version: Optional[str] = None) -> str:
        """Extract suggested kernel command line from config."""
        ver = version or self._default_version
        if not ver:
            return ""
        ki = self._kernels.get(ver)
        if not ki or not ki.config:
            return ""

        parts = []
        root = ki.config.get("CONFIG_ROOT_UUID", "")
        if root:
            parts.append(f"root=UUID={root}")
        else:
            parts.append("root=/dev/sda1")

        ro = ki.config.is_enabled("CONFIG_ROOT_FSReadOnly")
        if ro:
            parts.append("ro")

        if ki.config.is_enabled("CONFIG_HIBERNATION"):
            parts.append("resume=/dev/sda2")

        if ki.config.is_enabled("CONFIG_VT"):
            console = ki.config.get("CONFIG_VT_CONSOLE", "")
            if console:
                parts.append(f"console={console}")

        return " ".join(parts)

    def verify_integrity(self, version: Optional[str] = None) -> Dict[str, Any]:
        """Verify kernel image integrity."""
        ver = version or self._default_version
        if not ver:
            return {"valid": False, "error": "No kernel version specified"}

        ki = self._kernels.get(ver)
        if not ki:
            return {"valid": False, "error": f"Kernel {ver} not found"}

        results = {
            "version": ver,
            "vmlinuz_exists": ki.vmlinuz_path.exists(),
            "vmlinuz_size": ki.vmlinuz_size,
            "vmlinuz_hash": ki.vmlinuz_hash,
            "compression": ki.compression.value,
            "architecture": ki.architecture.value,
            "signature": ki.signature_type.value,
            "vmlinux_exists": ki.vmlinux_path is not None
            and ki.vmlinux_path.exists(),
            "system_map_exists": ki.system_map_path is not None
            and ki.system_map_path.exists(),
            "config_exists": ki.config is not None,
        }

        # Try to read the kernel header if uncompressed
        if ki.compression == KernelCompression.NONE:
            try:
                with open(ki.vmlinuz_path, "rb") as f:
                    elf_magic = f.read(4)
                results["elf_valid"] = (elf_magic == self.ELF_MAGIC)
            except (OSError, IOError):
                results["elf_valid"] = False

        # Summary
        results["valid"] = (
            results["vmlinuz_exists"]
            and results["vmlinuz_size"] > 0
            and (ki.compression != KernelCompression.NONE
                 or results.get("elf_valid", False))
        )
        return results

    def create_sample_kernel(
        self, version: str = "6.8.0-umerOS", size_kb: int = 256
    ) -> KernelImage:
        """Create a sample kernel image for testing."""
        vmlinuz = self.boot_dir / f"vmlinuz-{version}"

        # Write a gzip-compressed fake kernel (magic + padding)
        content = self.MAGIC_GZIP + os.urandom(size_kb * 1024 - 2)
        with open(vmlinuz, "wb") as f:
            f.write(content)

        # System.map
        sysmap = self.boot_dir / f"System.map-{version}"
        symbols = [
            f"ffffffff81000000 T _text",
            f"ffffffff82000000 D _data",
            f"ffffffff83000000 B _bss",
            f"ffffffff81000100 T startup_64",
            f"ffffffff81001000 T start_kernel",
            f"ffffffff81100000 t rest_init",
            f"ffffffff81200000 T kernel_init",
            f"ffffffff82000000 D init_task",
            f"                 t vfs_read",
            f"                 T sys_read",
            f"                 U __stack_chk_fail",
        ]
        with open(sysmap, "w") as f:
            for sym in symbols:
                parts = sym.split()
                if len(parts) >= 3:
                    f.write(f"{parts[0]} {parts[1]} {parts[2]}\n")

        # config
        config_path = self.boot_dir / f"config-{version}"
        with open(config_path, "w") as f:
            f.write(f"# UmerOS kernel config {version}\n")
            f.write("CONFIG_X86_64=y\n")
            f.write("CONFIG_SMP=y\n")
            f.write("CONFIG_ROOT_FSReadOnly=y\n")
            f.write("CONFIG_VT=y\n")
            f.write("CONFIG_VT_CONSOLE=y\n")
            f.write("CONFIG_HIBERNATION=m\n")
            f.write("CONFIG_EXT4_FS=y\n")
            f.write("CONFIG_BTRFS_FS=m\n")
            f.write("CONFIG_ZRAM=m\n")
            f.write("CONFIG_MODULES=y\n")
            f.write("CONFIG_MODULE_UNLOAD=y\n")

        return self.register_kernel(
            version,
            vmlinuz,
            system_map_path=sysmap,
            config_path=config_path,
            set_as_default=True,
        )


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    """Round-trip the kernel image manager against a temp /boot.

    Creates a sample kernel, registers it, lists versions, and checks
    that the integrity verifier accepts the new image.
    """
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        bd = Path(tmp)
        mgr = KernelImageManager(bd)
        ki = mgr.create_sample_kernel("6.8.0-umerOS", size_kb=8)
        if ki.vmlinuz_size <= 0:
            return False
        if "6.8.0-umerOS" not in mgr.list_versions():
            return False
        if mgr.default_version != "6.8.0-umerOS":
            return False
        integrity = mgr.verify_integrity()
        if not integrity.get("vmlinuz_exists"):
            return False
        # Register a second kernel and remove it.
        mgr.create_sample_kernel("6.9.0-umerOS", size_kb=4)
        if len(mgr.list_versions()) != 2:
            return False
        if not mgr.remove_kernel("6.9.0-umerOS"):
            return False
        if len(mgr.list_versions()) != 1:
            return False
        # set_default round-trip
        if not mgr.set_default("6.8.0-umerOS"):
            return False
        cmd = mgr.get_cmdline_from_config()
        if "root=" not in cmd:
            return False
    return True
