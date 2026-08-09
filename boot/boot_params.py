"""
UmerOS Boot Parameters Manager
================================
Manages kernel command line parameters and sysctl-style runtime configuration.

Kernel parameters (passed via GRUB/systemd-boot cmdline):
    root=         Root filesystem device
    ro / rw       Read-only/read-write root
    init=         Init process path
    console=      Console device(s)
    quiet         Suppress most boot messages
    splash        Enable boot splash
    panic=        Reboot timeout after kernel panic
    memtest       Enable memory testing
    elevator=     I/O scheduler

Sysctl runtime parameters:
    /proc/sys/    Runtime kernel parameters
    /etc/sysctl.d/  Persistent sysctl config files
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class ParamCategory(Enum):
    ROOT = "root"
    CONSOLE = "console"
    SECURITY = "security"
    DEBUG = "debug"
    PERFORMANCE = "performance"
    MEMORY = "memory"
    NETWORK = "network"
    FILESYSTEM = "filesystem"
    BOOT = "boot"
    SYSTEMD = "systemd"
    OTHER = "other"


@dataclass
class KernelParam:
    """A single kernel command line parameter."""
    key: str
    value: Optional[str] = None
    category: ParamCategory = ParamCategory.OTHER
    description: str = ""
    is_flag: bool = False  # True if key-only (no =value)
    required: bool = False
    default_value: Optional[str] = None
    allowed_values: Optional[List[str]] = None
    validator: Optional[str] = None  # Name of validation function

    @property
    def as_string(self) -> str:
        if self.is_flag or self.value is None:
            return self.key
        return f"{self.key}={self.value}"

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "key": self.key,
            "category": self.category.value,
            "description": self.description,
            "is_flag": self.is_flag,
            "required": self.required,
        }
        if self.value is not None:
            d["value"] = self.value
        if self.default_value is not None:
            d["default_value"] = self.default_value
        if self.allowed_values:
            d["allowed_values"] = self.allowed_values
        return d


@dataclass
class SysctlParam:
    """A sysctl runtime parameter."""
    path: str  # e.g., "net.ipv4.ip_forward"
    value: Any = None
    category: ParamCategory = ParamCategory.OTHER
    description: str = ""
    data_type: str = "string"  # string, int, bool
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    sysctl_file: str = ""  # Source config file

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "path": self.path,
            "value": self.value,
            "category": self.category.value,
            "description": self.description,
            "data_type": self.data_type,
        }
        if self.min_value is not None:
            d["min_value"] = self.min_value
        if self.max_value is not None:
            d["max_value"] = self.max_value
        return d


class KernelCommandLine:
    """Manages kernel command line parameters."""

    # Common kernel parameters with descriptions
    COMMON_PARAMS: Dict[str, Dict[str, Any]] = {
        "root": {
            "category": ParamCategory.ROOT,
            "description": "Root filesystem device",
            "required": True,
        },
        "ro": {
            "category": ParamCategory.ROOT,
            "description": "Mount root filesystem read-only",
            "is_flag": True,
        },
        "rw": {
            "category": ParamCategory.ROOT,
            "description": "Mount root filesystem read-write",
            "is_flag": True,
        },
        "init": {
            "category": ParamCategory.BOOT,
            "description": "Path to init process",
        },
        "console": {
            "category": ParamCategory.CONSOLE,
            "description": "Console device(s)",
        },
        "quiet": {
            "category": ParamCategory.BOOT,
            "description": "Suppress most boot messages",
            "is_flag": True,
        },
        "splash": {
            "category": ParamCategory.BOOT,
            "description": "Enable boot splash screen",
            "is_flag": True,
        },
        "panic": {
            "category": ParamCategory.DEBUG,
            "description": "Seconds before reboot after kernel panic",
        },
        "memtest": {
            "category": ParamCategory.DEBUG,
            "description": "Enable memory testing at boot",
            "is_flag": True,
        },
        "elevator": {
            "category": ParamCategory.PERFORMANCE,
            "description": "I/O scheduler",
            "allowed_values": ["none", "mq-deadline", "bfq", "kyber", "kyber"],
        },
        "selinux": {
            "category": ParamCategory.SECURITY,
            "description": "SELinux mode",
            "allowed_values": ["0", "1", "enforcing", "permissive", "disabled"],
        },
        "enforcing": {
            "category": ParamCategory.SECURITY,
            "description": "SELinux enforcing mode",
            "is_flag": True,
        },
        "nomodeset": {
            "category": ParamCategory.DEBUG,
            "description": "Disable kernel mode setting",
            "is_flag": True,
        },
        "nokaslr": {
            "category": ParamCategory.SECURITY,
            "description": "Disable Kernel Address Space Layout Randomization",
            "is_flag": True,
        },
        "acpi": {
            "category": ParamCategory.BOOT,
            "description": "ACPI behavior",
            "allowed_values": ["off", "force", "noirq", "ht", "strict"],
        },
        "noapic": {
            "category": ParamCategory.BOOT,
            "description": "Disable APIC",
            "is_flag": True,
        },
        "nosmp": {
            "category": ParamCategory.BOOT,
            "description": "Disable SMP",
            "is_flag": True,
        },
        "maxcpus": {
            "category": ParamCategory.BOOT,
            "description": "Maximum number of CPUs to use",
        },
        "reserve": {
            "category": ParamCategory.MEMORY,
            "description": "Reserve memory regions",
        },
        "mem": {
            "category": ParamCategory.MEMORY,
            "description": "Limit available memory",
        },
        "hugepages": {
            "category": ParamCategory.MEMORY,
            "description": "Number of huge pages to reserve",
        },
        "net.ifnames": {
            "category": ParamCategory.NETWORK,
            "description": "Predictable network interface naming",
            "allowed_values": ["0", "1"],
        },
        "systemd.unit": {
            "category": ParamCategory.SYSTEMD,
            "description": "Systemd unit to start",
        },
        "systemd.log_level": {
            "category": ParamCategory.SYSTEMD,
            "description": "Systemd log level",
        },
        "systemd.log_target": {
            "category": ParamCategory.SYSTEMD,
            "description": "Systemd log target",
            "allowed_values": ["console", "journal", "kmsg", "journal-or-kmsg"],
        },
        "rd.break": {
            "category": ParamCategory.DEBUG,
            "description": "Break into initramfs shell",
            "is_flag": True,
        },
        "rd.shell": {
            "category": ParamCategory.DEBUG,
            "description": "Drop to shell on initramfs errors",
            "is_flag": True,
        },
        "rd.debug": {
            "category": ParamCategory.DEBUG,
            "description": "Enable initramfs debugging",
            "is_flag": True,
        },
    }

    def __init__(self):
        self._params: Dict[str, KernelParam] = {}
        self._init_common_params()

    def _init_common_params(self) -> None:
        for key, info in self.COMMON_PARAMS.items():
            self._params[key] = KernelParam(
                key=key,
                category=info.get("category", ParamCategory.OTHER),
                description=info.get("description", ""),
                is_flag=info.get("is_flag", False),
                required=info.get("required", False),
                allowed_values=info.get("allowed_values"),
                default_value=info.get("default_value"),
            )

    def parse(self, cmdline: str) -> Dict[str, KernelParam]:
        """Parse a kernel command line string."""
        parsed = {}
        tokens = cmdline.split()
        for token in tokens:
            if "=" in token:
                key, _, value = token.partition("=")
                key = key.strip()
                value = value.strip()
                if key in self._params:
                    param = KernelParam(
                        key=key,
                        value=value,
                        category=self._params[key].category,
                        description=self._params[key].description,
                        is_flag=False,
                        required=self._params[key].required,
                        default_value=self._params[key].default_value,
                        allowed_values=self._params[key].allowed_values,
                    )
                else:
                    param = KernelParam(key=key, value=value)
                parsed[key] = param
            else:
                token = token.strip()
                if token:
                    if token in self._params:
                        parsed[token] = KernelParam(
                            key=token,
                            category=self._params[token].category,
                            description=self._params[token].description,
                            is_flag=True,
                            required=self._params[token].required,
                            default_value=self._params[token].default_value,
                            allowed_values=self._params[token].allowed_values,
                        )
                    else:
                        parsed[token] = KernelParam(key=token, is_flag=True)
        return parsed

    def build(self, params: Dict[str, KernelParam]) -> str:
        """Build a kernel command line string from params."""
        parts = []
        for key in sorted(params.keys()):
            p = params[key]
            parts.append(p.as_string)
        return " ".join(parts)

    def set_param(
        self,
        key: str,
        value: Optional[str] = None,
        category: ParamCategory = ParamCategory.OTHER,
        description: str = "",
        is_flag: bool = False,
    ) -> KernelParam:
        param = KernelParam(
            key=key,
            value=value,
            category=category,
            description=description,
            is_flag=is_flag,
        )
        self._params[key] = param
        return param

    def get_param(self, key: str) -> Optional[KernelParam]:
        return self._params.get(key)

    def remove_param(self, key: str) -> bool:
        if key in self._params:
            del self._params[key]
            return True
        return False

    def list_params(self, category: Optional[ParamCategory] = None) -> List[KernelParam]:
        if category:
            return [p for p in self._params.values() if p.category == category]
        return list(self._params.values())

    def validate(self, cmdline: str) -> List[str]:
        """Validate a kernel command line string."""
        errors = []
        params = self.parse(cmdline)

        # Check required params
        for key, param_def in self._params.items():
            if param_def.required and key not in params:
                errors.append(f"Missing required parameter: {key}")

        # Check allowed values
        for key, param in params.items():
            if key in self._params:
                allowed = self._params[key].allowed_values
                if allowed and param.value not in allowed:
                    errors.append(
                        f"Invalid value for {key}: {param.value} "
                        f"(allowed: {', '.join(allowed)})"
                    )
        return errors

    def get_preset(self, preset_name: str) -> str:
        """Get a preset kernel command line."""
        presets = {
            "default": "root=/dev/sda1 ro quiet splash",
            "recovery": "root=/dev/sda1 ro single",
            "debug": "root=/dev/sda1 ro nomodeset rd.debug rd.shell",
            "server": "root=/dev/sda1 ro console=ttyS0,115200 quiet",
            "live": "root=/dev/sdb1 rw live-media=removable quiet splash",
            "install": "root=/dev/sdb1 rw preseed/file=/cdrom/preseed.cfg quiet",
            "memtest": "memtest",
            "secure": "root=/dev/sda1 ro selinux=enforcing enforcing",
            "minimal": "root=/dev/sda1 ro console=tty0",
        }
        return presets.get(preset_name, presets["default"])

    def get_by_category(self, category: ParamCategory) -> List[KernelParam]:
        return [p for p in self._params.values() if p.category == category]

    def status(self) -> Dict[str, Any]:
        categories = {}
        for cat in ParamCategory:
            params = self.get_by_category(cat)
            if params:
                categories[cat.value] = [p.key for p in params]
        return {
            "total_params": len(self._params),
            "categories": categories,
            "required": [p.key for p in self._params.values() if p.required],
        }


class SysctlManager:
    """Manages sysctl runtime and persistent kernel parameters."""

    # Common sysctl parameters with descriptions
    COMMON_SYSCTL: Dict[str, Dict[str, Any]] = {
        "net.ipv4.ip_forward": {
            "category": ParamCategory.NETWORK,
            "description": "Enable IP forwarding",
            "data_type": "bool",
        },
        "net.ipv4.conf.all.rp_filter": {
            "category": ParamCategory.NETWORK,
            "description": "Reverse path filtering",
            "data_type": "int",
        },
        "net.ipv4.conf.default.rp_filter": {
            "category": ParamCategory.NETWORK,
            "description": "Default reverse path filtering",
            "data_type": "int",
        },
        "net.ipv4.icmp_echo_ignore_broadcasts": {
            "category": ParamCategory.NETWORK,
            "description": "Ignore ICMP broadcast requests",
            "data_type": "bool",
        },
        "net.ipv4.tcp_syncookies": {
            "category": ParamCategory.NETWORK,
            "description": "TCP SYN cookie protection",
            "data_type": "bool",
        },
        "net.ipv4.tcp_max_syn_backlog": {
            "category": ParamCategory.NETWORK,
            "description": "Max SYN backlog",
            "data_type": "int",
        },
        "net.ipv4.tcp_tw_reuse": {
            "category": ParamCategory.NETWORK,
            "description": "Reuse TIME_WAIT sockets",
            "data_type": "int",
        },
        "net.ipv4.tcp_fin_timeout": {
            "category": ParamCategory.NETWORK,
            "description": "FIN-WAIT-2 timeout (seconds)",
            "data_type": "int",
            "min_value": 1,
            "max_value": 300,
        },
        "net.ipv6.conf.all.forwarding": {
            "category": ParamCategory.NETWORK,
            "description": "Enable IPv6 forwarding",
            "data_type": "bool",
        },
        "net.core.somaxconn": {
            "category": ParamCategory.NETWORK,
            "description": "Max socket connections",
            "data_type": "int",
            "min_value": 1,
            "max_value": 4096,
        },
        "net.core.rmem_max": {
            "category": ParamCategory.NETWORK,
            "description": "Max receive buffer size",
            "data_type": "int",
        },
        "net.core.wmem_max": {
            "category": ParamCategory.NETWORK,
            "description": "Max send buffer size",
            "data_type": "int",
        },
        "vm.swappiness": {
            "category": ParamCategory.MEMORY,
            "description": "Swappiness (0-200)",
            "data_type": "int",
            "min_value": 0,
            "max_value": 200,
        },
        "vm.dirty_ratio": {
            "category": ParamCategory.MEMORY,
            "description": "Max dirty pages before writeback",
            "data_type": "int",
            "min_value": 1,
            "max_value": 100,
        },
        "vm.dirty_background_ratio": {
            "category": ParamCategory.MEMORY,
            "description": "Background dirty page threshold",
            "data_type": "int",
            "min_value": 1,
            "max_value": 100,
        },
        "vm.overcommit_memory": {
            "category": ParamCategory.MEMORY,
            "description": "Memory overcommit policy",
            "data_type": "int",
            "min_value": 0,
            "max_value": 2,
        },
        "vm.overcommit_ratio": {
            "category": ParamCategory.MEMORY,
            "description": "Overcommit ratio percentage",
            "data_type": "int",
            "min_value": 0,
            "max_value": 500,
        },
        "vm.min_free_kbytes": {
            "category": ParamCategory.MEMORY,
            "description": "Min free memory (KB)",
            "data_type": "int",
        },
        "kernel.hostname": {
            "category": ParamCategory.SYSTEMD,
            "description": "System hostname",
            "data_type": "string",
        },
        "kernel.domainname": {
            "category": ParamCategory.SYSTEMD,
            "description": "NIS domain name",
            "data_type": "string",
        },
        "kernel.msgmax": {
            "category": ParamCategory.SYSTEMD,
            "description": "Max size of message (bytes)",
            "data_type": "int",
        },
        "kernel.msgmnb": {
            "category": ParamCategory.SYSTEMD,
            "description": "Max bytes in message queue",
            "data_type": "int",
        },
        "kernel.shmmax": {
            "category": ParamCategory.SYSTEMD,
            "description": "Max shared memory segment size",
            "data_type": "int",
        },
        "kernel.shmall": {
            "category": ParamCategory.SYSTEMD,
            "description": "Max total shared memory pages",
            "data_type": "int",
        },
        "kernel.pid_max": {
            "category": ParamCategory.SYSTEMD,
            "description": "Max PID value",
            "data_type": "int",
        },
        "kernel.threads-max": {
            "category": ParamCategory.SYSTEMD,
            "description": "Max threads",
            "data_type": "int",
        },
        "kernel.panic": {
            "category": ParamCategory.DEBUG,
            "description": "Seconds before reboot after panic",
            "data_type": "int",
        },
        "kernel.panic_on_oops": {
            "category": ParamCategory.DEBUG,
            "description": "Panic on oops",
            "data_type": "bool",
        },
        "kernel.sysrq": {
            "category": ParamCategory.DEBUG,
            "description": "Magic SysRq key enable",
            "data_type": "int",
        },
        "kernel.dmesg_restrict": {
            "category": ParamCategory.SECURITY,
            "description": "Restrict dmesg access",
            "data_type": "bool",
        },
        "kernel.kptr_restrict": {
            "category": ParamCategory.SECURITY,
            "description": "Restrict kernel pointer exposure",
            "data_type": "int",
        },
        "fs.file-max": {
            "category": ParamCategory.FILESYSTEM,
            "description": "Max open files",
            "data_type": "int",
        },
        "fs.inotify.max_user_watches": {
            "category": ParamCategory.FILESYSTEM,
            "description": "Max inotify watches per user",
            "data_type": "int",
        },
        "fs.inotify.max_user_instances": {
            "category": ParamCategory.FILESYSTEM,
            "description": "Max inotify instances per user",
            "data_type": "int",
        },
        "fs.aio-max-nr": {
            "category": ParamCategory.FILESYSTEM,
            "description": "Max async I/O operations",
            "data_type": "int",
        },
    }

    # Profile presets
    PROFILES: Dict[str, Dict[str, str]] = {
        "server": {
            "net.ipv4.ip_forward": "1",
            "net.ipv4.tcp_syncookies": "1",
            "net.ipv4.tcp_max_syn_backlog": "4096",
            "net.core.somaxconn": "4096",
            "net.core.rmem_max": "16777216",
            "net.core.wmem_max": "16777216",
            "vm.swappiness": "10",
            "vm.dirty_ratio": "10",
            "vm.dirty_background_ratio": "5",
            "vm.overcommit_memory": "0",
            "vm.min_free_kbytes": "131072",
            "fs.file-max": "2097152",
            "fs.inotify.max_user_watches": "524288",
            "kernel.pid_max": "4194304",
            "kernel.threads-max": "4194304",
            "kernel.panic": "10",
            "kernel.panic_on_oops": "1",
            "kernel.dmesg_restrict": "1",
            "kernel.kptr_restrict": "2",
        },
        "desktop": {
            "vm.swappiness": "60",
            "vm.dirty_ratio": "20",
            "vm.dirty_background_ratio": "10",
            "fs.file-max": "524288",
            "fs.inotify.max_user_watches": "524288",
            "kernel.panic": "10",
            "kernel.sysrq": "176",
        },
        "workstation": {
            "vm.swappiness": "30",
            "vm.dirty_ratio": "15",
            "vm.dirty_background_ratio": "5",
            "vm.overcommit_memory": "0",
            "fs.file-max": "1048576",
            "fs.inotify.max_user_watches": "1048576",
            "kernel.pid_max": "65536",
            "kernel.panic": "10",
            "kernel.sysrq": "176",
            "kernel.dmesg_restrict": "0",
        },
        "embedded": {
            "vm.swappiness": "0",
            "vm.overcommit_memory": "1",
            "vm.min_free_kbytes": "16384",
            "fs.file-max": "65536",
            "fs.inotify.max_user_watches": "8192",
            "kernel.panic": "1",
            "kernel.panic_on_oops": "1",
            "kernel.dmesg_restrict": "1",
            "kernel.kptr_restrict": "2",
        },
        "security-hardened": {
            "kernel.dmesg_restrict": "1",
            "kernel.kptr_restrict": "2",
            "kernel.sysrq": "0",
            "net.ipv4.icmp_echo_ignore_broadcasts": "1",
            "net.ipv4.conf.all.rp_filter": "1",
            "net.ipv4.conf.default.rp_filter": "1",
            "vm.swappiness": "10",
            "fs.protected_hardlinks": "1",
            "fs.protected_symlinks": "1",
        },
    }

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path("/etc/sysctl.d")
        self._params: Dict[str, SysctlParam] = {}
        self._init_common_params()

    def _init_common_params(self) -> None:
        for path, info in self.COMMON_SYSCTL.items():
            self._params[path] = SysctlParam(
                path=path,
                category=info.get("category", ParamCategory.OTHER),
                description=info.get("description", ""),
                data_type=info.get("data_type", "string"),
                min_value=info.get("min_value"),
                max_value=info.get("max_value"),
            )

    def get(self, path: str) -> Optional[SysctlParam]:
        return self._params.get(path)

    def set(
        self,
        path: str,
        value: Any,
        category: ParamCategory = ParamCategory.OTHER,
        description: str = "",
        data_type: str = "string",
    ) -> SysctlParam:
        param = SysctlParam(
            path=path,
            value=value,
            category=category,
            description=description,
            data_type=data_type,
        )
        self._params[path] = param
        return param

    def remove(self, path: str) -> bool:
        if path in self._params:
            del self._params[path]
            return True
        return False

    def list_params(self, category: Optional[ParamCategory] = None) -> List[SysctlParam]:
        if category:
            return [p for p in self._params.values() if p.category == category]
        return list(self._params.values())

    def apply_profile(self, profile_name: str) -> int:
        """Apply a sysctl profile, returns number of params applied."""
        profile = self.PROFILES.get(profile_name, {})
        count = 0
        for path, value in profile.items():
            if path in self._params:
                self._params[path].value = value
                count += 1
            else:
                self.set(path=path, value=value)
                count += 1
        return count

    def generate_config(self, filename: str = "99-umeros.conf") -> str:
        """Generate a sysctl config file."""
        lines = [
            "# UmerOS sysctl configuration",
            f"# Generated: {datetime.now().isoformat()}",
            "#",
            "",
        ]
        for path in sorted(self._params.keys()):
            param = self._params[path]
            if param.value is not None:
                lines.append(f"# {param.description}")
                lines.append(f"{path} = {param.value}")
                lines.append("")
        return "\n".join(lines)

    def save_config(self, filename: str = "99-umeros.conf") -> Path:
        """Save sysctl config to file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        config_path = self.config_dir / filename
        config_path.write_text(self.generate_config(filename))
        config_path.chmod(0o644)
        return config_path

    def load_config(self, filepath: Path) -> int:
        """Load sysctl config from file, returns number of params loaded."""
        count = 0
        try:
            content = filepath.read_text()
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    path, _, value = line.partition("=")
                    path = path.strip()
                    value = value.strip()
                    if path:
                        self.set(path=path, value=value, data_type="string")
                        self._params[path].sysctl_file = str(filepath)
                        count += 1
        except (OSError, IOError):
            pass
        return count

    def validate(self, path: str, value: Any) -> List[str]:
        """Validate a sysctl value."""
        errors = []
        param = self._params.get(path)
        if param:
            if param.data_type == "int":
                try:
                    int_val = int(value)
                    if param.min_value is not None and int_val < param.min_value:
                        errors.append(
                            f"{path}: value {int_val} below minimum {param.min_value}"
                        )
                    if param.max_value is not None and int_val > param.max_value:
                        errors.append(
                            f"{path}: value {int_val} above maximum {param.max_value}"
                        )
                except (ValueError, TypeError):
                    errors.append(f"{path}: expected integer, got '{value}'")
            elif param.data_type == "bool":
                if value not in ("0", "1", "true", "false", "yes", "no"):
                    errors.append(
                        f"{path}: expected boolean (0/1/true/false), got '{value}'"
                    )
        return errors

    def get_by_category(self, category: ParamCategory) -> List[SysctlParam]:
        return [p for p in self._params.values() if p.category == category]

    def status(self) -> Dict[str, Any]:
        categories = {}
        for cat in ParamCategory:
            params = self.get_by_category(cat)
            if params:
                categories[cat.value] = len(params)
        return {
            "total_params": len(self._params),
            "categories": categories,
            "profiles": list(self.PROFILES.keys()),
            "config_dir": str(self.config_dir),
        }


class BootParamsManager:
    """Top-level boot parameters manager combining kernel cmdline and sysctl."""

    def __init__(self, sysctl_config_dir: Optional[Path] = None):
        self.kernel = KernelCommandLine()
        self.sysctl = SysctlManager(sysctl_config_dir)
        self._boot_config_dir = Path("/var/lib/umerOS/boot-params")
        self._boot_config_dir.mkdir(parents=True, exist_ok=True)

    def load_kernel_config(self, cmdline_path: Optional[Path] = None) -> str:
        """Load kernel command line from file or /proc/cmdline."""
        if cmdline_path and cmdline_path.exists():
            return cmdline_path.read_text().strip()
        # Simulated
        return self.kernel.get_preset("default")

    def save_kernel_config(self, cmdline: str, name: str = "default") -> Path:
        """Save kernel command line to file."""
        target = self._boot_config_dir / f"cmdline-{name}.conf"
        target.write_text(cmdline)
        return target

    def get_active_config(self) -> Dict[str, Any]:
        """Get the currently active boot configuration."""
        return {
            "kernel_cmdline": self.load_kernel_config(),
            "sysctl_profile": "default",
        }

    def apply_sysctl_profile(self, profile_name: str) -> Dict[str, Any]:
        """Apply a sysctl profile."""
        count = self.sysctl.apply_profile(profile_name)
        return {
            "profile": profile_name,
            "params_applied": count,
        }

    def generate_grub_config(self, cmdline: str) -> str:
        """Generate GRUB menuentry with given cmdline."""
        return (
            "menuentry 'UmerOS' {\n"
            f"    linux /boot/vmlinuz {cmdline}\n"
            "    initrd /boot/initrd.img\n"
            "}"
        )

    def generate_systemd_boot_entry(self, cmdline: str) -> str:
        """Generate systemd-boot entry with given cmdline."""
        return (
            "title   UmerOS\n"
            "linux   /vmlinuz\n"
            f"options {cmdline}\n"
            "initrd  /initrd.img\n"
        )

    def status(self) -> Dict[str, Any]:
        return {
            "kernel": self.kernel.status(),
            "sysctl": self.sysctl.status(),
            "config_dir": str(self._boot_config_dir),
        }
