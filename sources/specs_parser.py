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
UmerOS /sources — Kernel Documentation & Specifications Parser
==============================================================

Parses and provides reference models documentation
cited in the Linux Filesystem Hierarchy standard (sources.html).


Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3) 
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class KernelDocSection:
    """A section of kernel documentation."""
    title: str
    content: str
    subsections: Dict[str, str] = field(default_factory=dict)


class KernelDocsRegistry:
    """Registry of core kernel and system specifications cited in sources."""

    _DOCS: Dict[str, Dict[str, Any]] = {
        "proc.txt": {
            "title": "/usr/src/linux/Documentation/filesystems/proc.txt",
            "authors": ["Terrehon Bowden", "Bodo Bauer", "Jorge Nerin"],
            "summary": "The /proc file system acts as an interface to internal data structures in the running kernel.",
            "sections": {
                "1.1 /proc/cpuinfo": "Provides collection of CPU and system architecture dependent items (model, cores, MHz, cache, bogomips).",
                "1.2 /proc/meminfo": "Provides memory usage diagnostics: MemTotal, MemFree, Buffers, Cached, SwapTotal, SwapFree.",
                "1.3 /proc/mounts": "Lists currently mounted filesystems, devices, mount points, fs types, and mount flags.",
                "1.4 /proc/uptime": "Two numbers: system uptime in seconds, and time spent in the idle process in seconds.",
                "1.5 /proc/version": "Linux kernel version, compiler version (GCC), and kernel build timestamp.",
                "1.6 /proc/stat": "CPU ticks, page stats, swap stats, interrupt counts, context switches, boot time, process count.",
                "1.7 /proc/sys": "Runtime configurable kernel parameters (fs, kernel, net, vm) matching sysctl.",
                "1.8 /proc/[pid]": "Per-process runtime directories containing cmdline, environ, fd, status, statm, maps.",
            },
        },
        "initrd.txt": {
            "title": "/usr/src/linux/Documentation/initrd.txt",
            "authors": ["Werner Almesberger", "Hans Lermen"],
            "summary": "Mechanics of initial RAM disk (initrd) for booting modular kernels and mounting rootfs.",
            "sections": {
                "1. Boot Sequence": "1. Bootloader loads kernel & initrd into RAM -> 2. Kernel creates rootfs from initrd -> 3. Executes /linuxrc -> 4. /linuxrc loads SCSI/RAID drivers -> 5. pivot_root switches root to real hard disk partition.",
                "2. pivot_root Operation": "pivot_root(new_root, put_old) swaps root directory atomically without reboot.",
                "3. Memory Reclamation": "After root transition, initrd memory pages are freed back to kernel memory pool.",
            },
        },
        "runlevels": {
            "title": "/usr/share/doc/sysvinit/README.runlevels.gz",
            "authors": ["Miquel van Smoorenburg"],
            "summary": "System V init runlevel architecture and execution sequence.",
            "sections": {
                "Runlevel 0": "Halt / Poweroff system cleanly.",
                "Runlevel 1 / S": "Single-User / Maintenance mode (no network, root shell).",
                "Runlevel 2": "Multi-user mode without network file sharing (Debian/Ubuntu default).",
                "Runlevel 3": "Full Multi-user mode with networking and console logins (RedHat/SuSE default).",
                "Runlevel 4": "Unused / User-customizable runlevel.",
                "Runlevel 5": "Full Multi-user mode with Graphical Display Manager (X11 / Wayland).",
                "Runlevel 6": "Reboot system cleanly.",
            },
        },
    }

    @classmethod
    def get_doc(cls, name: str) -> Optional[Dict[str, Any]]:
        name_clean = name.lower().replace(".gz", "")
        for k, v in cls._DOCS.items():
            if name_clean in k.lower():
                return v
        return None

    @classmethod
    def list_docs(cls) -> List[str]:
        return list(cls._DOCS.keys())

    @classmethod
    def search_docs(cls, query: str) -> List[Dict[str, Any]]:
        q = query.lower()
        results = []
        for k, doc in cls._DOCS.items():
            if q in k.lower() or q in doc["title"].lower() or q in doc["summary"].lower():
                results.append(doc)
            elif any(q in s_title.lower() or q in s_content.lower() for s_title, s_content in doc["sections"].items()):
                results.append(doc)
        return results
