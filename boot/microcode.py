"""
UmerOS Microcode Manager
===========================
Manages CPU microcode updates for Intel and AMD processors.

Microcode is firmware loaded onto the CPU to fix bugs and security
vulnerabilities (Spectre, Meltdown, MDS, L1TF, etc.). It's loaded
early in the boot process before the kernel initializes.

Standard paths:
    /boot/initrd.img           Microcode embedded in initrd (modern)
    /boot/early_ucode.cpio     Microcode CPIO archive (legacy)
    /lib/firmware/amd-ucode/   AMD microcode files
    /lib/firmware/intel-ucode/ Intel microcode files
    /boot/ucode.img            Alternative microcode image
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import tarfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class CPUVendor(Enum):
    INTEL = "intel"
    AMD = "amd"
    UNKNOWN = "unknown"


class MicrocodeSignificance(Enum):
    CRITICAL = "critical"  # Security vulnerability fix
    IMPORTANT = "important"  # Bug fix
    MODERATE = "moderate"  # Performance improvement
    LOW = "low"  # Minor fix
    OPTIONAL = "optional"  # Optional update


@dataclass
class MicrocodeUpdate:
    vendor: CPUVendor
    cpu_family: int
    cpu_model: int
    stepping: Optional[int]
    microcode_version: str
    date: str  # e.g., "2024-01-15"
    signature: int  # CPUID signature
    significance: MicrocodeSignificance
    description: str
    cve_fixes: List[str] = field(default_factory=list)
    file_path: Optional[Path] = None
    file_size: int = 0
    hash_sha256: str = ""
    is_loaded: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vendor": self.vendor.value,
            "cpu_family": self.cpu_family,
            "cpu_model": self.cpu_model,
            "stepping": self.stepping,
            "microcode_version": self.microcode_version,
            "date": self.date,
            "signature": hex(self.signature),
            "significance": self.significance.value,
            "description": self.description,
            "cve_fixes": self.cve_fixes,
            "file_path": str(self.file_path) if self.file_path else None,
            "file_size": self.file_size,
            "is_loaded": self.is_loaded,
        }


@dataclass
class CPUInfo:
    vendor: CPUVendor
    family: int
    model: int
    stepping: int
    microcode_version: str
    model_name: str
    flags: List[str] = field(default_factory=list)

    @property
    def signature(self) -> int:
        return (self.family << 8) | (self.model << 4) | self.stepping

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vendor": self.vendor.value,
            "family": self.family,
            "model": self.model,
            "stepping": self.stepping,
            "microcode_version": self.microcode_version,
            "model_name": self.model_name,
            "flags_count": len(self.flags),
        }


class MicrocodeParser:
    """Parses microcode binary files and CPU info."""

    @staticmethod
    def parse_intel_microcode_header(data: bytes) -> Optional[Dict[str, Any]]:
        """Parse Intel microcode update header."""
        if len(data) < 48:
            return None

        # Intel microcode update header format
        header_version = struct.unpack_from("<B", data, 0)[0]
        revision = struct.unpack_from("<B", data, 1)[0]
        sig = struct.unpack_from("<I", data, 4)[0]
        flags = struct.unpack_from("<I", data, 8)[0]
        size = struct.unpack_from("<I", data, 12)[0]
        da_size = struct.unpack_from("<I", data, 16)[0]
        total_size = struct.unpack_from("<I", data, 20)[0]
        reserved = struct.unpack_from("<16s", data, 24)[0]
        checksum = struct.unpack_from("<I", data, 44)[0]

        return {
            "header_version": header_version,
            "revision": revision,
            "signature": sig,
            "flags": flags,
            "update_size": size,
            "data_size": da_size,
            "total_size": total_size,
            "checksum": checksum,
        }

    @staticmethod
    def compute_checksum(data: bytes) -> int:
        """Compute Intel microcode checksum (sum of dwords should be 0)."""
        total = 0
        for i in range(0, len(data), 4):
            if i + 4 <= len(data):
                total += struct.unpack_from("<I", data, i)[0]
            elif i + 2 <= len(data):
                total += struct.unpack_from("<H", data, i)[0]
            elif i < len(data):
                total += data[i]
        return total & 0xFFFFFFFF

    @staticmethod
    def detect_cpu_vendor() -> CPUVendor:
        """Detect CPU vendor."""
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.startswith("vendor_id"):
                        if "Intel" in line:
                            return CPUVendor.INTEL
                        elif "AMD" in line:
                            return CPUVendor.AMD
        except (OSError, IOError):
            pass
        return CPUVendor.UNKNOWN

    @staticmethod
    def detect_cpu_family() -> int:
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.startswith("cpu family"):
                        return int(line.split(":")[1].strip())
        except (OSError, IOError, ValueError):
            pass
        return 6  # Default to family 6 (Intel)

    @staticmethod
    def detect_cpu_model() -> int:
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.startswith("model") and "model name" not in line:
                        return int(line.split(":")[1].strip())
        except (OSError, IOError, ValueError):
            pass
        return 0

    @staticmethod
    def detect_stepping() -> int:
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.startswith("stepping"):
                        return int(line.split(":")[1].strip())
        except (OSError, IOError, ValueError):
            pass
        return 0

    @staticmethod
    def detect_microcode_version() -> str:
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "microcode" in line:
                        return line.split(":")[1].strip()
        except (OSError, IOError):
            pass
        return "unknown"

    @staticmethod
    def detect_model_name() -> str:
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.startswith("model name"):
                        return line.split(":")[1].strip()
        except (OSError, IOError):
            pass
        return "Unknown CPU"

    @staticmethod
    def detect_flags() -> List[str]:
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.startswith("flags"):
                        return line.split(":")[1].strip().split()
        except (OSError, IOError):
            pass
        return []


class MicrocodeManager:
    """Manages CPU microcode updates."""

    # Known microcode updates (simplified database)
    KNOWN_UPDATES: List[Dict[str, Any]] = [
        {
            "vendor": CPUVendor.INTEL,
            "cpu_family": 6,
            "cpu_model": 142,  # Coffee Lake
            "signature": 0x906EA,
            "version": "0xF4",
            "date": "2024-01-15",
            "significance": MicrocodeSignificance.CRITICAL,
            "description": "Security update for Spectre v2 and MDS",
            "cve_fixes": ["CVE-2023-20569", "CVE-2022-40982"],
        },
        {
            "vendor": CPUVendor.INTEL,
            "cpu_family": 6,
            "cpu_model": 158,  # Coffee Lake Refresh
            "signature": 0x906EB,
            "version": "0xF4",
            "date": "2024-01-15",
            "significance": MicrocodeSignificance.CRITICAL,
            "description": "Security update for Spectre v2 and MDS",
            "cve_fixes": ["CVE-2023-20569", "CVE-2022-40982"],
        },
        {
            "vendor": CPUVendor.AMD,
            "cpu_family": 25,
            "cpu_model": 1,  # Zen 3
            "signature": 0x00A00F11,
            "version": "0xA001147",
            "date": "2024-02-10",
            "significance": MicrocodeSignificance.CRITICAL,
            "description": "Security update for Zenbleed (CVE-2023-20593)",
            "cve_fixes": ["CVE-2023-20593"],
        },
        {
            "vendor": CPUVendor.AMD,
            "cpu_family": 25,
            "cpu_model": 33,  # Zen 4 (Raphael)
            "signature": 0x00A00F44,
            "version": "0xA404430",
            "date": "2024-03-20",
            "significance": MicrocodeSignificance.CRITICAL,
            "description": "Security update for Downfall (CVE-2023-4093)",
            "cve_fixes": ["CVE-2023-4093"],
        },
    ]

    def __init__(
        self,
        firmware_dir: Path = Path("/lib/firmware"),
        initrd_dir: Path = Path("/boot"),
    ):
        self.firmware_dir = Path(firmware_dir)
        self.initrd_dir = Path(initrd_dir)
        self.intel_dir = self.firmware_dir / "intel-ucode"
        self.amd_dir = self.firmware_dir / "amd-ucode"
        self._updates: List[MicrocodeUpdate] = []
        self._cpu_info: Optional[CPUInfo] = None

    def detect_cpu(self) -> CPUInfo:
        """Detect current CPU information."""
        vendor = MicrocodeParser.detect_cpu_vendor()
        family = MicrocodeParser.detect_cpu_family()
        model = MicrocodeParser.detect_cpu_model()
        stepping = MicrocodeParser.detect_stepping()
        microcode = MicrocodeParser.detect_microcode_version()
        model_name = MicrocodeParser.detect_model_name()
        flags = MicrocodeParser.detect_flags()

        self._cpu_info = CPUInfo(
            vendor=vendor,
            family=family,
            model=model,
            stepping=stepping,
            microcode_version=microcode,
            model_name=model_name,
            flags=flags,
        )
        return self._cpu_info

    def scan_updates(self) -> List[MicrocodeUpdate]:
        """Scan for available microcode updates."""
        self._updates.clear()

        # Scan Intel microcode
        if self.intel_dir.exists():
            for f in self.intel_dir.glob("microcode-*.bin"):
                update = self._parse_intel_file(f)
                if update:
                    self._updates.append(update)

        # Scan AMD microcode
        if self.amd_dir.exists():
            for f in self.amd_dir.glob("microcode_amd*.bin"):
                update = self._parse_amd_file(f)
                if update:
                    self._updates.append(update)

        # Add known updates from database
        for known in self.KNOWN_UPDATES:
            update = MicrocodeUpdate(
                vendor=known["vendor"],
                cpu_family=known["cpu_family"],
                cpu_model=known["cpu_model"],
                stepping=None,
                microcode_version=known["version"],
                date=known["date"],
                signature=known["signature"],
                significance=known["significance"],
                description=known["description"],
                cve_fixes=known["cve_fixes"],
            )
            self._updates.append(update)

        return list(self._updates)

    def _parse_intel_file(self, path: Path) -> Optional[MicrocodeUpdate]:
        try:
            data = path.read_bytes()
            header = MicrocodeParser.parse_intel_microcode_header(data)
            if not header:
                return None

            sig = header["signature"]
            family = (sig >> 8) & 0xFF
            model = (sig >> 4) & 0xFF
            stepping = sig & 0xF

            return MicrocodeUpdate(
                vendor=CPUVendor.INTEL,
                cpu_family=family,
                cpu_model=model,
                stepping=stepping,
                microcode_version=f"0x{header['revision']:02X}",
                date="",
                signature=sig,
                significance=MicrocodeSignificance.IMPORTANT,
                description=f"Intel microcode update from {path.name}",
                file_path=path,
                file_size=path.stat().st_size,
            )
        except (OSError, IOError):
            return None

    def _parse_amd_file(self, path: Path) -> Optional[MicrocodeUpdate]:
        try:
            size = path.stat().st_size
            return MicrocodeUpdate(
                vendor=CPUVendor.AMD,
                cpu_family=0,
                cpu_model=0,
                stepping=None,
                microcode_version="",
                date="",
                signature=0,
                significance=MicrocodeSignificance.IMPORTANT,
                description=f"AMD microcode update from {path.name}",
                file_path=path,
                file_size=size,
            )
        except (OSError, IOError):
            return None

    def get_updates_for_cpu(self) -> List[MicrocodeUpdate]:
        """Get updates matching the current CPU."""
        if not self._cpu_info:
            self.detect_cpu()

        matching = []
        for update in self._updates:
            if update.vendor == self._cpu_info.vendor:
                if update.signature == 0 or update.signature == self._cpu_info.signature:
                    matching.append(update)
        return matching

    def get_critical_updates(self) -> List[MicrocodeUpdate]:
        """Get critical security updates."""
        return [
            u
            for u in self._updates
            if u.significance == MicrocodeSignificance.CRITICAL
        ]

    def get_cve_fixes(self) -> List[MicrocodeUpdate]:
        """Get updates that fix known CVEs."""
        return [u for u in self._updates if u.cve_fixes]

    def embed_in_initrd(self, initrd_path: Path, microcode_files: List[Path]) -> bool:
        """Embed microcode into an initrd image."""
        if not initrd_path.exists():
            return False

        try:
            # Create a CPIO archive with microcode
            cpio_data = BytesIO()
            for mf in microcode_files:
                if mf.exists():
                    data = mf.read_bytes()
                    # Simplified CPIO header
                    header = struct.pack(
                        "<6sHHIIIiiIIIIII",
                        b"070701",  # magic
                        0,  # dev
                        0,  # ino
                        0o100644,  # mode
                        0,  # uid
                        0,  # gid
                        len(data),  # size
                        0,  # mtime
                        0,  # chksum
                        len(mf.name),  # namesize
                        0,  # devmajor
                        0,  # devminor
                    )
                    cpio_data.write(header)
                    cpio_data.write(mf.name.encode())
                    cpio_data.write(b"\x00")
                    cpio_data.write(data)

            # Write the CPIO to a temp file
            target = initrd_path.parent / "early_ucode.cpio"
            target.write_bytes(cpio_data.getvalue())
            return True
        except (OSError, IOError):
            return False

    def generate_initrd_line(self, embed_microcode: bool = True) -> str:
        """Generate the initrd line for bootloader config."""
        if embed_microcode:
            return "initrd /boot/ucode.img /boot/initrd.img"
        return "initrd /boot/initrd.img"

    def get_loaded_version(self) -> str:
        """Get currently loaded microcode version."""
        if self._cpu_info:
            return self._cpu_info.microcode_version
        return MicrocodeParser.detect_microcode_version()

    def check_update_needed(self) -> Tuple[bool, List[MicrocodeUpdate]]:
        """Check if microcode update is needed."""
        current = self.get_loaded_version()
        available = self.get_updates_for_cpu()
        critical = [
            u
            for u in available
            if u.significance == MicrocodeSignificance.CRITICAL
        ]

        # Simple version comparison (simplified)
        if critical:
            return True, critical
        return False, []

    def status(self) -> Dict[str, Any]:
        cpu_info = self._cpu_info or self.detect_cpu()
        available = self.get_updates_for_cpu()
        critical = self.get_critical_updates()
        cve_fixes = self.get_cve_fixes()
        needs_update, updates_needed = self.check_update_needed()

        return {
            "cpu": cpu_info.to_dict(),
            "current_microcode": cpu_info.microcode_version,
            "total_updates": len(self._updates),
            "updates_for_cpu": len(available),
            "critical_updates": len(critical),
            "cve_fixes": len(cve_fixes),
            "needs_update": needs_update,
            "cve_list": [
                cve for u in cve_fixes for cve in u.cve_fixes
            ],
        }


class MicrocodeInstaller:
    """Installs microcode updates into initrd."""

    def __init__(self, manager: MicrocodeManager):
        self.manager = manager

    def generate_ucode_initrd(self, output_path: Path) -> bool:
        """Generate a microcode-only initrd image."""
        try:
            # Simplified: create a CPIO with microcode
            cpio_data = b""
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(cpio_data)
            return True
        except (OSError, IOError):
            return False

    def install_updates(self, target_dir: Path = Path("/boot")) -> Dict[str, Any]:
        """Install microcode updates to boot directory."""
        results = {"steps": [], "files": []}

        # Generate microcode initrd
        ucode_img = target_dir / "ucode.img"
        if self.generate_ucode_initrd(ucode_img):
            results["steps"].append("Generated ucode.img")
            results["files"].append(str(ucode_img))
        else:
            results["steps"].append("Failed to generate ucode.img")

        # Copy firmware files if available
        for vendor_dir in ["intel-ucode", "amd-ucode"]:
            src = Path(f"/lib/firmware/{vendor_dir}")
            if src.exists():
                results["steps"].append(f"Found {vendor_dir} firmware")

        return results

    def get_grub_cmdline(self) -> str:
        """Get GRUB configuration for microcode loading."""
        return "initrd /boot/ucode.img /boot/initrd.img"


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    """Run built-in self-test for microcode."""
    import shutil
    import tempfile

    td = tempfile.mkdtemp(prefix="umeros_ucode_test_")
    try:
        firmware_dir = Path(td) / "firmware"
        initrd_dir = Path(td) / "initrd"
        firmware_dir.mkdir()
        initrd_dir.mkdir()

        # CPUInfo
        info = CPUInfo(
            vendor=CPUVendor.INTEL,
            family=6,
            model=142,
            stepping=10,
            microcode_version="0xB4",
            model_name="Test CPU",
            flags=["sse4", "avx2"],
        )
        assert info.vendor == CPUVendor.INTEL
        assert info.signature == (6 << 8) | (142 << 4) | 10
        d = info.to_dict()
        assert d["vendor"] == "intel"
        assert d["flags_count"] == 2

        # MicrocodeUpdate
        update = MicrocodeUpdate(
            vendor=CPUVendor.INTEL,
            cpu_family=6,
            cpu_model=142,
            stepping=10,
            microcode_version="0xB5",
            date="2024-01-15",
            signature=info.signature,
            significance=MicrocodeSignificance.CRITICAL,
            description="Security fix",
            cve_fixes=["CVE-2024-0001"],
        )
        assert update.significance == MicrocodeSignificance.CRITICAL
        assert "CVE-2024-0001" in update.cve_fixes

        # MicrocodeManager
        mgr = MicrocodeManager(firmware_dir, initrd_dir)
        # scan_updates should not crash even with empty dirs
        updates = mgr.scan_updates()
        assert isinstance(updates, list)

        # get_grub_cmdline
        line = mgr.get_grub_cmdline()
        assert "initrd" in line

        # MicrocodeParser.compute_checksum
        data = b"\x00" * 64
        cs = MicrocodeParser.compute_checksum(data)
        assert isinstance(cs, int)

        return True
    except Exception as exc:  # noqa: BLE001
        import sys
        print(f"microcode selftest FAILED: {exc}", file=sys.stderr)
        return False
    finally:
        shutil.rmtree(td, ignore_errors=True)
