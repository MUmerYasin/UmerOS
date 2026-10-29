# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
UmerOS System Information Tool
==============================

Gathers hardware and OS information for diagnostics and display.
"""

from __future__ import annotations

import logging
import os
import platform
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Tools.SystemInfo")


@dataclass
class CPUInfo:
    model: str = "Unknown"
    cores: int = 1
    threads: int = 1
    architecture: str = "unknown"
    frequency_mhz: float = 0.0


@dataclass
class MemoryInfo:
    total_bytes: int = 0
    available_bytes: int = 0
    used_bytes: int = 0
    percent_used: float = 0.0


@dataclass
class SystemInfo:
    os_name: str = "UmerOS"
    os_version: str = "1.0.0"
    kernel: str = "Python"
    hostname: str = "umeros"
    cpu: CPUInfo = field(default_factory=CPUInfo)
    memory: MemoryInfo = field(default_factory=MemoryInfo)
    python_version: str = ""
    platform: str = ""

    def to_dict(self) -> dict:
        return {
            "os_name": self.os_name,
            "os_version": self.os_version,
            "kernel": self.kernel,
            "hostname": self.hostname,
            "cpu": {
                "model": self.cpu.model,
                "cores": self.cpu.cores,
                "threads": self.cpu.threads,
                "architecture": self.cpu.architecture,
                "frequency_mhz": self.cpu.frequency_mhz,
            },
            "memory": {
                "total_bytes": self.memory.total_bytes,
                "available_bytes": self.memory.available_bytes,
                "used_bytes": self.memory.used_bytes,
                "percent_used": self.memory.percent_used,
            },
            "python_version": self.python_version,
            "platform": self.platform,
        }


def get_cpu_info() -> CPUInfo:
    """Gather CPU information."""
    info = CPUInfo()
    info.architecture = platform.machine()
    try:
        info.cores = os.cpu_count() or 1
        info.threads = info.cores
    except Exception:
        pass
    # Try to get model name
    try:
        if os.path.exists("/proc/cpuinfo"):
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        info.model = line.split(":")[1].strip()
                        break
    except Exception:
        info.model = platform.processor() or "Unknown"
    if info.model == "Unknown":
        info.model = platform.processor() or "Unknown CPU"
    return info


def get_memory_info() -> MemoryInfo:
    """Gather memory information."""
    info = MemoryInfo()
    try:
        if os.path.exists("/proc/meminfo"):
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        info.total_bytes = int(line.split()[1]) * 1024
                    elif line.startswith("MemAvailable:"):
                        info.available_bytes = int(line.split()[1]) * 1024
            info.used_bytes = info.total_bytes - info.available_bytes
            if info.total_bytes > 0:
                info.percent_used = (info.used_bytes / info.total_bytes) * 100
        else:
            # Fallback for non-Linux
            import shutil
            total, used, free = shutil.disk_usage("/")
            info.total_bytes = total
            info.available_bytes = free
            info.used_bytes = used
            if total > 0:
                info.percent_used = (used / total) * 100
    except Exception as e:
        log.warning("Failed to get memory info: %s", e)
    return info


def get_system_info() -> SystemInfo:
    """Gather complete system information."""
    info = SystemInfo()
    info.os_name = "UmerOS"
    info.os_version = "1.0.0-pre-alpha"
    info.kernel = "Python (userspace simulation)"
    info.hostname = platform.node() or "umeros"
    info.cpu = get_cpu_info()
    info.memory = get_memory_info()
    info.python_version = sys.version.split()[0]
    info.platform = f"{platform.system()} {platform.release()}"
    return info


# Convenience aliases
def get_cpu_info_alias():
    return get_cpu_info()


def get_memory_info_alias():
    return get_memory_info()