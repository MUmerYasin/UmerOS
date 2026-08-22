# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
UmerOS Memtest Module
====================
Memory testing integration for the boot process.

Manages:
- Memtest86+ boot loader entries and kernel params
- Memory test result parsing
- GRUB and BLS entry generation for memory diagnostics

Reference: https://www.memtest86.com/
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

log = logging.getLogger("UmerOS.Boot.Memtest")


class MemtestVersion(Enum):
    MEMTEST86_5 = "memtest86+5.0"
    MEMTEST86_6 = "memtest86+6.0"
    MEMTEST86_7 = "memtest86+7.0"
    MEMTEST86_LATEST = "memtest86+latest"
    UNKNOWN = "unknown"


class MemtestStatus(Enum):
    NOT_CONFIGURED = "not_configured"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ERROR = "error"


class MemtestTestType(Enum):
    BASIC = "basic"
    STRESS = "stress"
    ALL = "all"


class MemoryErrorType(Enum):
    SINGLE_BIT = "single_bit"
    DOUBLE_BIT = "double_bit"
    ECC = "ecc"
    UNKNOWN = "unknown"


@dataclass
class MemtestConfig:
    version: MemtestVersion = MemtestVersion.MEMTEST86_LATEST
    test_passes: int = 1
    test_type: MemtestTestType = MemtestTestType.BASIC
    cpu_cores: int = 1
    address_range: Optional[Tuple[int, int]] = None
    bail_on_error: bool = True
    max_errors: int = 100

    def as_dict(self) -> dict:
        return {
            "version": self.version.value,
            "test_passes": self.test_passes,
            "test_type": self.test_type.value,
            "cpu_cores": self.cpu_cores,
            "address_range": list(self.address_range) if self.address_range else None,
            "bail_on_error": self.bail_on_error,
            "max_errors": self.max_errors,
        }


@dataclass
class MemoryError:
    address: int
    expected: int
    actual: int
    error_type: MemoryErrorType = MemoryErrorType.UNKNOWN
    pass_num: int = 0
    test_num: int = 0

    def as_dict(self) -> dict:
        return {
            "address": hex(self.address),
            "expected": hex(self.expected),
            "actual": hex(self.actual),
            "error_type": self.error_type.value,
            "pass_num": self.pass_num,
            "test_num": self.test_num,
        }


@dataclass
class MemtestResult:
    status: MemtestStatus = MemtestStatus.NOT_CONFIGURED
    config: MemtestConfig = field(default_factory=MemtestConfig)
    errors: List[MemoryError] = field(default_factory=list)
    total_passes: int = 0
    total_tests: int = 0
    memory_size_mb: int = 0
    test_duration_sec: float = 0.0

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def success(self) -> bool:
        return self.status == MemtestStatus.COMPLETED and self.error_count == 0

    def as_dict(self) -> dict:
        return {
            "status": self.status.value,
            "error_count": self.error_count,
            "total_passes": self.total_passes,
            "memory_size_mb": self.memory_size_mb,
            "success": self.success,
        }


@dataclass
class MemtestBinary:
    path: Path
    version: MemtestVersion
    size: int
    checksum: str = ""
    is_kernel: bool = False

    def as_dict(self) -> dict:
        return {
            "path": str(self.path),
            "version": self.version.value,
            "size": self.size,
            "checksum": self.checksum,
            "is_kernel": self.is_kernel,
        }


class MemtestDetector:
    BINARY_NAMES = [
        "memtest86+.bin", "memtest86+.efi", "memtest86", "memtest",
    ]
    KERNEL_PATTERNS = ["vmlinuz-memtest*", "memtest*-kernel*"]

    def __init__(self, boot_dir: str = "/boot") -> None:
        self.boot_dir = Path(boot_dir)

    def detect(self) -> List[MemtestBinary]:
        binaries: List[MemtestBinary] = []
        for name in self.BINARY_NAMES:
            path = self.boot_dir / name
            if path.exists() and path.is_file():
                binaries.append(self._inspect(path))
        for pattern in self.KERNEL_PATTERNS:
            for path in self.boot_dir.glob(pattern):
                if path.is_file():
                    binaries.append(self._inspect(path, is_kernel=True))
        return binaries

    def _inspect(self, path: Path, is_kernel: bool = False) -> MemtestBinary:
        size = path.stat().st_size
        checksum = self._checksum(path)
        version = self._detect_version(path)
        return MemtestBinary(
            path=path, version=version, size=size,
            checksum=checksum, is_kernel=is_kernel,
        )

    def _checksum(self, path: Path) -> str:
        h = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
        except OSError:
            return ""
        return h.hexdigest()[:16]

    def _detect_version(self, path: Path) -> MemtestVersion:
        name = path.name.lower()
        if "6.0" in name or "v6" in name:
            return MemtestVersion.MEMTEST86_6
        if "7.0" in name or "v7" in name:
            return MemtestVersion.MEMTEST86_7
        if "5.0" in name or "v5" in name:
            return MemtestVersion.MEMTEST86_5
        return MemtestVersion.MEMTEST86_LATEST


class MemtestCommandBuilder:
    PRESETS = {
        "quick": {"test_passes": 1, "test_type": MemtestTestType.BASIC},
        "standard": {"test_passes": 2, "test_type": MemtestTestType.BASIC},
        "thorough": {"test_passes": 4, "test_type": MemtestTestType.ALL},
        "stress": {"test_passes": 8, "test_type": MemtestTestType.STRESS},
    }

    def __init__(self, config: Optional[MemtestConfig] = None) -> None:
        self.config = config or MemtestConfig()

    def build_cmdline(self) -> str:
        parts: List[str] = []
        if self.config.test_passes > 1:
            parts.append(f"memtest86+{self.config.test_passes}")
        if self.config.address_range:
            start, end = self.config.address_range
            parts.append(f"memtest_start={hex(start)}")
            parts.append(f"memtest_end={hex(end)}")
        if self.config.cpu_cores > 1:
            parts.append(f"cpus={self.config.cpu_cores}")
        return " ".join(parts) if parts else "memtest86+"

    def build_grub_entry(self, title: str = "Memory Test (memtest86+)") -> str:
        cmdline = self.build_cmdline()
        return (
            f"menuentry '{title}' {{\n"
            f"    linux /boot/memtest86+.bin {cmdline}\n"
            f"}}\n"
        )

    def build_bls_entry(self, title: str = "Memory Test (memtest86+)") -> str:
        cmdline = self.build_cmdline()
        lines = [f"title   {title}", f"linux   /memtest86+.bin"]
        if cmdline != "memtest86+":
            lines.append(f"options {cmdline}")
        return "\n".join(lines) + "\n"

    @classmethod
    def from_preset(cls, name: str) -> MemtestCommandBuilder:
        if name not in cls.PRESETS:
            raise ValueError(f"Unknown preset: {name}. Available: {list(cls.PRESETS)}")
        config = MemtestConfig(**cls.PRESETS[name])
        return cls(config)


class MemtestResultParser:
    ERROR_PATTERNS = ["Failure", "Error", "FAIL", "Bit:", "Work"]

    def parse_log(self, log_path: Path) -> MemtestResult:
        result = MemtestResult()
        if not log_path.exists():
            result.status = MemtestStatus.ERROR
            return result
        try:
            with open(log_path, "r", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            result.status = MemtestStatus.ERROR
            return result

        error_count = 0
        for line in lines:
            for pattern in self.ERROR_PATTERNS:
                if pattern in line:
                    error_count += 1
                    break

        result.total_passes = sum(
            1 for l in lines if "pass" in l.lower() and "completed" in l.lower()
        )
        result.errors = [
            MemoryError(address=i, expected=0, actual=0) for i in range(error_count)
        ]
        result.status = (
            MemtestStatus.FAILED if error_count > 0 else MemtestStatus.COMPLETED
        )
        return result


class MemtestManager:
    def __init__(self, boot_dir: str = "/boot") -> None:
        self.boot_dir = Path(boot_dir)
        self.detector = MemtestDetector(boot_dir)
        self.parser = MemtestResultParser()

    def detect_binaries(self) -> List[MemtestBinary]:
        return self.detector.detect()

    def configure(self, config: MemtestConfig) -> MemtestConfig:
        return config

    def build_entry(self, config: MemtestConfig, fmt: str = "grub") -> str:
        builder = MemtestCommandBuilder(config)
        if fmt == "bls":
            return builder.build_bls_entry()
        return builder.build_grub_entry()

    def get_status(self) -> MemtestStatus:
        binaries = self.detect_binaries()
        return MemtestStatus.READY if binaries else MemtestStatus.NOT_CONFIGURED


def _selftest() -> bool:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        boot = Path(tmp) / "boot"
        boot.mkdir()
        mgr = MemtestManager(boot_dir=str(boot))
        if mgr.get_status() != MemtestStatus.NOT_CONFIGURED:
            return False
        (boot / "memtest86+.bin").write_bytes(b"MEMTEST86+" + b"\x00" * 100)
        bins = mgr.detect_binaries()
        if len(bins) != 1:
            return False
        if bins[0].version == MemtestVersion.UNKNOWN:
            return False
        builder = MemtestCommandBuilder.from_preset("thorough")
        if builder.config.test_passes != 4:
            return False
        if "memtest86+.bin" not in builder.build_grub_entry():
            return False
        if "title" not in builder.build_bls_entry():
            return False
        cfg = MemtestConfig(test_passes=3, cpu_cores=4)
        if cfg.as_dict()["test_passes"] != 3:
            return False
        result = MemtestResult()
        if result.error_count != 0:
            return False
        if result.success:
            return False
        empty = Path(tmp) / "empty.log"
        empty.write_text("nothing here\n")
        parsed = mgr.parser.parse_log(empty)
        if parsed.status != MemtestStatus.COMPLETED:
            return False
        errfile = Path(tmp) / "errors.log"
        errfile.write_text("Error at 0x1000\nFailure at 0x2000\nPASS completed\n")
        parsed_err = mgr.parser.parse_log(errfile)
        if parsed_err.error_count != 2:
            return False
    return True


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    print("memtest selftest:", "OK" if _selftest() else "FAIL")
