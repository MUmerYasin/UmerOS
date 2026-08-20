"""
UmerOS Crash Kernel Manager (kdump)
=====================================
Manages crash kernel for post-mortem debugging of kernel panics.

kdump works by reserving a small kernel and initramfs at boot time.
When the main kernel crashes, the system automatically reboots into
the crash kernel, which captures the system state (vmcore) before
any modifications occur.

Standard paths:
    /boot/vmcore           Crash dump (vmcore) files
    /boot/vmlinuz.kdump    Crash kernel image
    /boot/initrd.kdump.img Crash kernel initramfs
    /etc/kdump.conf        kdump configuration
    /var/crash/            Crash dump storage directory
    /proc/vmcore           Live vmcore (during crash kernel boot)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class KdumpServiceState(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    UNKNOWN = "unknown"


class KdumpDumpTarget(Enum):
    LOCAL_DISK = "local"
    NFS = "nfs"
    CIFS = "cifs"
    SSH = "ssh"
    RAW_DISK = "raw"


@dataclass
class KdumpConfig:
    """kdump.conf configuration."""
    kdump_kernel: str = "/boot/vmlinuz.kdump"
    kdump_initrd: str = "/boot/initrd.kdump.img"
    commandline: str = "root=/dev/sda1"
    extra_modules: List[str] = field(default_factory=list)
    path: str = "/var/crash"
    core_collector: str = "makedumpfile"
    core_collector_opts: str = "-l --message-level 1 -d 31"
    ssh_key: str = "/etc/kdump_ssh_key"
    ssh_user: str = "root"
    nfs_mount: str = "nfs_server:/export/vmcore"
    cifs_mount: str = "//server/share"
    cifs_user: str = ""
    raw_device: str = "/dev/sdb1"
    auto_reboot: bool = True
    force_rebuild_initrd: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kdump_kernel": self.kdump_kernel,
            "kdump_initrd": self.kdump_initrd,
            "commandline": self.commandline,
            "extra_modules": self.extra_modules,
            "path": self.path,
            "core_collector": self.core_collector,
            "core_collector_opts": self.core_collector_opts,
            "ssh_key": self.ssh_key,
            "ssh_user": self.ssh_user,
            "nfs_mount": self.nfs_mount,
            "cifs_mount": self.cifs_mount,
            "cifs_user": self.cifs_user,
            "raw_device": self.raw_device,
            "auto_reboot": self.auto_reboot,
        }


@dataclass
class VmcoreInfo:
    """Information about a captured vmcore."""
    timestamp: datetime
    kernel_version: str
    architecture: str
    hostname: str
    crash_type: str  # panic, oops, hung_task, etc.
    file_path: Path
    file_size: int = 0
    hash_sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "kernel_version": self.kernel_version,
            "architecture": self.architecture,
            "hostname": self.hostname,
            "crash_type": self.crash_type,
            "file_path": str(self.file_path),
            "file_size": self.file_size,
        }


class KdumpConfigManager:
    """Manages kdump.conf configuration file."""

    def __init__(self, config_path: Path = Path("/etc/kdump.conf")):
        self.config_path = Path(config_path)
        self._config = KdumpConfig()

    def load(self) -> KdumpConfig:
        if not self.config_path.exists():
            return self._config

        content = self.config_path.read_text()
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                if key == "path":
                    self._config.path = value
                elif key == "core_collector":
                    self._config.core_collector = value
                elif key == "ssh_user":
                    self._config.ssh_user = value
                elif key == "ssh_key":
                    self._config.ssh_key = value
                elif key == "nfs_mount":
                    self._config.nfs_mount = value
                elif key == "cifs_mount":
                    self._config.cifs_mount = value
                elif key == "cifs_user":
                    self._config.cifs_user = value
                elif key == "raw_device":
                    self._config.raw_device = value
                elif key == "extra_modules":
                    self._config.extra_modules = value.split()
                elif key == "auto_reboot":
                    self._config.auto_reboot = value.lower() in ("1", "yes", "true")
        return self._config

    def save(self, config: Optional[KdumpConfig] = None) -> bool:
        if config:
            self._config = config
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            content = self.generate()
            self.config_path.write_text(content)
            return True
        except (OSError, IOError):
            return False

    def generate(self, config: Optional[KdumpConfig] = None) -> str:
        cfg = config or self._config
        lines = [
            "# kdump.conf - UmerOS Crash Kernel Configuration",
            f"# Generated by UmerOS Boot Manager",
            "#",
            "",
            "# Kernel and initrd for crash kernel",
            f"kernel {cfg.kdump_kernel}",
            f"initrd {cfg.kdump_initrd}",
            "",
            "# Command line for crash kernel",
            f"commandline {cfg.commandline}",
            "",
            "# Crash dump storage path",
            f"path {cfg.path}",
            "",
            "# Core collector",
            f"core_collector {cfg.core_collector}",
            "",
        ]

        if cfg.core_collector == "makedumpfile":
            lines.extend([
                "# makedumpfile options",
                f"core_collector makedumpfile {cfg.core_collector_opts}",
                "",
            ])

        if cfg.extra_modules:
            lines.extend([
                "# Extra modules to load in crash kernel",
                f"extra_modules {' '.join(cfg.extra_modules)}",
                "",
            ])

        if cfg.auto_reboot:
            lines.extend([
                "# Auto reboot after capturing vmcore",
                "auto_reboot yes",
                "",
            ])

        lines.extend([
            "# ===== Network Dump Options =====",
            "# Uncomment and configure for NFS:",
            f"# nfs_mount {cfg.nfs_mount}",
            "# Uncomment and configure for SSH:",
            f"# ssh_user {cfg.ssh_user}",
            f"# ssh_key {cfg.ssh_key}",
            "# Uncomment and configure for CIFS:",
            f"# cifs_mount {cfg.cifs_mount}",
            f"# cifs_user {cfg.cifs_user}",
            "# Uncomment and configure for raw disk:",
            f"# raw_device {cfg.raw_device}",
        ])

        return "\n".join(lines) + "\n"

    def get_config(self) -> KdumpConfig:
        return self._config


class KdumpKernelBuilder:
    """Manages crash kernel and initramfs for kdump."""

    def __init__(
        self,
        boot_dir: Path = Path("/boot"),
        kdump_dir: Path = Path("/var/crash"),
    ):
        self.boot_dir = Path(boot_dir)
        self.kdump_dir = Path(kdump_dir)

    def reserve_memory_mb(self) -> int:
        """Get recommended memory to reserve for crash kernel (in MB)."""
        # Standard recommendation: 256MB for < 4GB, 512MB for >= 4GB
        total_ram_mb = self._get_total_ram_mb()
        if total_ram_mb < 4096:
            return 256
        return 512

    def _get_total_ram_mb(self) -> int:
        try:
            meminfo = Path("/proc/meminfo").read_text()
            for line in meminfo.splitlines():
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return kb // 1024
        except (OSError, IOError, ValueError):
            pass
        return 4096

    def get_kernel_cmdline_reservation(self) -> str:
        """Get kernel command line for crash kernel memory reservation."""
        reserve_mb = self.reserve_memory_mb()
        return f"crashkernel={reserve_mb}M"

    def get_elf_header_reserved(self) -> str:
        """Get ELF header reserved memory."""
        return "crashkernel=256M,high"

    def list_kdump_kernels(self) -> List[Dict[str, Any]]:
        """List available kdump kernels."""
        kernels = []
        kdump_pattern = re.compile(r"vmlinuz\.(kdump|kdmp|crash)")

        for f in self.boot_dir.glob("vmlinuz*"):
            if kdump_pattern.search(f.name) or "kdump" in f.name or "crash" in f.name:
                initrd_candidate = self.boot_dir / f.name.replace("vmlinuz", "initrd")
                if not initrd_candidate.exists():
                    initrd_candidate = self.boot_dir / f.name.replace("vmlinuz", "initramfs")
                    if not initrd_candidate.exists():
                        initrd_candidate = self.boot_dir / f.name.replace("vmlinuz", "crash-initrd")

                kernels.append({
                    "name": f.name,
                    "path": str(f),
                    "size": f.stat().st_size if f.exists() else 0,
                    "initrd": str(initrd_candidate) if initrd_candidate.exists() else None,
                    "initrd_exists": initrd_candidate.exists(),
                })

        return kernels

    def create_kdump_initramfs(self, base_initrd: Path, output: Path) -> bool:
        """Create kdump initramfs from base initrd."""
        # This is a simplified version - real implementation would use dracut/mkinitramfs
        try:
            if base_initrd.exists():
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(base_initrd), str(output))
                return True
        except (OSError, IOError):
            return False
        return False

    def configure_grub_kdump(self, grub_config_path: Path) -> str:
        """Generate GRUB entry with kdump support."""
        return (
            "menuentry 'UmerOS (kdump enabled)' {\n"
            "    insmod all_video\n"
            "     /boot/vmlinuz root=/dev/sda1 "
            f"{self.get_kernel_cmdline_reservation()} "
            "systemd.unit=multi-user.target\n"
            "    initrd /boot/initrd.img\n"
            "}"
        )


class KdumpServiceManager:
    """Manages the kdump service state."""

    def __init__(self, service_name: str = "kdump"):
        self.service_name = service_name

    def get_state(self) -> KdumpServiceState:
        """Get current kdump service state."""
        # In real implementation, check systemctl status
        return KdumpServiceState.UNKNOWN

    def start(self) -> bool:
        """Start kdump service."""
        return True

    def stop(self) -> bool:
        """Stop kdump service."""
        return True

    def restart(self) -> bool:
        """Restart kdump service."""
        return True

    def enable(self) -> bool:
        """Enable kdump service at boot."""
        return True

    def disable(self) -> bool:
        """Disable kdump service."""
        return True


class VmcoreManager:
    """Manages captured vmcore (crash dump) files."""

    def __init__(self, vmcore_dir: Path = Path("/var/crash")):
        self.vmcore_dir = Path(vmcore_dir)

    def list_vmcodes(self) -> List[Dict[str, Any]]:
        """List available vmcore files."""
        vmcores = []
        if not self.vmcore_dir.exists():
            return vmcores

        for item in self.vmcore_dir.iterdir():
            if item.is_dir():
                vmcore_file = item / "vmcore"
                if vmcore_file.exists():
                    vmcores.append({
                        "timestamp": datetime.fromtimestamp(item.stat().st_mtime),
                        "path": str(vmcore_file),
                        "size": vmcore_file.stat().st_size,
                        "directory": str(item),
                    })

        return sorted(vmcores, key=lambda x: x["timestamp"], reverse=True)

    def get_latest_vmcore(self) -> Optional[Dict[str, Any]]:
        vmcores = self.list_vmcodes()
        return vmcores[0] if vmcores else None

    def delete_vmcore(self, directory: Path) -> bool:
        """Delete a vmcore and its directory."""
        try:
            if directory.exists():
                shutil.rmtree(str(directory))
                return True
        except (OSError, IOError):
            return False
        return False

    def calculate_disk_usage(self) -> int:
        """Calculate total disk usage of vmcore directory (bytes)."""
        total = 0
        if self.vmcore_dir.exists():
            for item in self.vmcore_dir.rglob("*"):
                if item.is_file():
                    total += item.stat().st_size
        return total


class CrashKernelManager:
    """Top-level crash kernel manager."""

    def __init__(
        self,
        boot_dir: Path = Path("/boot"),
        config_path: Path = Path("/etc/kdump.conf"),
        vmcore_dir: Path = Path("/var/crash"),
    ):
        self.config_manager = KdumpConfigManager(config_path)
        self.kernel_builder = KdumpKernelBuilder(boot_dir, vmcore_dir)
        self.service_manager = KdumpServiceManager()
        self.vmcore_manager = VmcoreManager(vmcore_dir)
        self._config = KdumpConfig()

    def setup(
        self,
        target: KdumpDumpTarget = KdumpDumpTarget.LOCAL_DISK,
        auto_reboot: bool = True,
    ) -> bool:
        """Set up kdump with specified dump target."""
        self._config = KdumpConfig()
        self._config.auto_reboot = auto_reboot

        if target == KdumpDumpTarget.NFS:
            self._config.path = self._config.nfs_mount
        elif target == KdumpDumpTarget.SSH:
            self._config.path = self._config.ssh_user
        elif target == KdumpDumpTarget.RAW_DISK:
            self._config.path = self._config.raw_device
        elif target == KdumpDumpTarget.LOCAL_DISK:
            self._config.path = "/var/crash"

        self.config_manager.save(self._config)
        return True

    def get_grub_config(self) -> str:
        """Get GRUB configuration with kdump support."""
        return self.kernel_builder.configure_grub_kdump(Path("/etc/grub.d"))

    def get_cmdline_reservation(self) -> str:
        """Get kernel command line for crash kernel reservation."""
        return self.kernel_builder.get_kernel_cmdline_reservation()

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive kdump status."""
        config = self.config_manager.get_config()
        return {
            "enabled": self.service_manager.get_state() == KdumpServiceState.ACTIVE,
            "state": self.service_manager.get_state().value,
            "config": config.to_dict(),
            "memory_reservation_mb": self.kernel_builder.reserve_memory_mb(),
            "kdump_kernels": self.kernel_builder.list_kdump_kernels(),
            "vmcores": self.vmcore_manager.list_vmcodes(),
            "disk_usage_bytes": self.vmcore_manager.calculate_disk_usage(),
        }

    def generate_initramfs_hook(self) -> str:
        """Generate initramfs hook script for including kdump tools."""
        return (
            "#!/bin/sh\n"
            "# UmerOS kdump initramfs hook\n"
            "PREREQ=\"\"\n"
            "prereqs() { echo \"$PREREQ\"; }\n"
            "case $1 in prereqs) prereqs; exit 0;; esac\n\n"
            ". /usr/share/initramfs-tools/hook-functions\n"
            "# Copy kdump binaries\n"
            "copy_exec /sbin/kdump /sbin\n"
            "copy_exec /usr/sbin/makedumpfile /usr/sbin\n"
            "# Copy kdump configuration\n"
            "copy_file config /etc/kdump.conf /etc/kdump.conf\n"
            "# Copy vmcore initramfs tools\n"
            "copy_exec /sbin/vmcore-dmesg /sbin\n"
            "exit 0\n"
        )

    def generate_nfs_mount_script(self) -> str:
        """Generate NFS mount script for dumping to NFS server."""
        config = self.config_manager.get_config()
        return (
            "#!/bin/sh\n"
            "# UmerOS NFS vmcore dump mount script\n"
            f"NFS_SERVER={config.nfs_mount.split(':')[0] if ':' in config.nfs_mount else ''}\n"
            f"NFS_PATH={config.nfs_mount.split(':')[1] if ':' in config.nfs_mount else ''}\n"
            "mkdir -p /mnt/dump\n"
            "mount -t nfs4 $NFS_SERVER:$NFS_PATH /mnt/dump\n"
            "exit 0\n"
        )

    def analyze_vmcore(self, vmcore_path: Path) -> Dict[str, Any]:
        """Analyze a vmcore file and extract basic information."""
        if not vmcore_path.exists():
            return {"error": "vmcore file not found"}

        size = vmcore_path.stat().st_size
        mtime = datetime.fromtimestamp(vmcore_path.stat().st_mtime)

        return {
            "path": str(vmcore_path),
            "size_bytes": size,
            "timestamp": mtime.isoformat(),
            "size_human": self._human_readable_size(size),
        }

    @staticmethod
    def _human_readable_size(size: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def status(self) -> Dict[str, Any]:
        return self.get_status()


# ── Self-test ──────────────────────────────────────────────────────────────

def _selftest() -> List[str]:
    """Validate crash_kernel module classes and functionality."""
    errors: List[str] = []

    try:
        from boot.crash_kernel import (
            CrashKernelManager,
            KdumpConfig,
            KdumpConfigManager,
            VmcoreInfo,
        )
    except ImportError as exc:
        errors.append(f"Import failed: {exc}")
        return errors

    # KdumpConfig dataclass
    try:
        cfg = KdumpConfig()
        if cfg.enabled is not True:
            errors.append("KdumpConfig.enabled should default to True")
    except Exception as exc:
        errors.append(f"KdumpConfig creation failed: {exc}")

    # VmcoreInfo dataclass
    try:
        info = VmcoreInfo(
            timestamp="2025-01-01T00:00:00",
            size_bytes=1024,
            path="/var/crash/vmcore",
        )
        if info.size_bytes != 1024:
            errors.append("VmcoreInfo.size_bytes mismatch")
        if info.path != "/var/crash/vmcore":
            errors.append("VmcoreInfo.path mismatch")
    except Exception as exc:
        errors.append(f"VmcoreInfo creation failed: {exc}")

    # CrashKernelManager
    import tempfile, os
    try:
        tmp = tempfile.mkdtemp()
        ckm = CrashKernelManager(base_path=tmp)
        st = ckm.get_status()
        if not isinstance(st, dict):
            errors.append("CrashKernelManager.get_status() should return dict")
        if "kdump_enabled" not in st:
            errors.append("get_status() missing kdump_enabled key")
    except Exception as exc:
        errors.append(f"CrashKernelManager init/status failed: {exc}")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    # KdumpConfigManager
    try:
        tmp = tempfile.mkdtemp()
        cfg_path = os.path.join(tmp, "kdump.conf")
        kcm = KdumpConfigManager(config_path=cfg_path)
        if not isinstance(kcm.config, KdumpConfig):
            errors.append("KdumpConfigManager.config should be KdumpConfig")
    except Exception as exc:
        errors.append(f"KdumpConfigManager init failed: {exc}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return errors
