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
UmerOS Glossary
================================================================================

Exhaustive definitions and architecture reference for filesystem, kernel,
and system administration terminology.



Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3) 
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GlossaryEntry:
    """Represents a term definition in the Filesystem Hierarchy glossary."""
    term: str
    definition: str
    category: str = "general"
    see_also: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Canonical TLDP Glossary Entries ────────────────────────────────────────

GLOSSARY_DATA: List[GlossaryEntry] = [

    GlossaryEntry(
        term="BASH",
        definition="The Bourne Again Shell (sh compatible command interpreter), the standard default interactive shell on Linux systems.",
        category="shell",
        see_also=["Bourne Shell", "CLI"],
    ),

    GlossaryEntry(
        term="CLI",
        definition="Command Line Interface: a textual user interface in which commands are typed on a line to interact with the operating system.",
        category="shell",
        see_also=["GUI", "BASH"],
    ),
    GlossaryEntry(
        term="core",
        definition="A core dump file created when a process terminates unexpectedly (e.g. SIGSEGV). Contains the memory image and state at death for debugging.",
        category="kernel",
        see_also=["signals", "ulimit"],
    ),
    GlossaryEntry(
        term="daemon",
        definition="A background service process lurking in the operating system without a controlling terminal, waiting to service events or requests.",
        category="architecture",
        see_also=["init", "sysvinit"],
    ),
    GlossaryEntry(
        term="devfs",
        definition="Dynamic device filesystem managing /dev entries automatically as hardware is connected or detected by the kernel.",
        category="filesystem",
        see_also=["udev", "mknod"],
    ),
    GlossaryEntry(
        term="DNS",
        definition="Domain Name System: translates human-readable hostnames into IP network addresses.",
        category="networking",
        see_also=["TCP/IP"],
    ),
    GlossaryEntry(
        term="EXT2",
        definition="Second Extended Filesystem: standard non-journaling Linux filesystem designed by Remy Card.",
        category="filesystem",
        see_also=["EXT3", "inode"],
    ),
    GlossaryEntry(
        term="EXT3",
        definition="Third Extended Filesystem: journaling extension to EXT2 for high reliability and rapid crash recovery.",
        category="filesystem",
        see_also=["EXT2", "fsck"],
    ),
    GlossaryEntry(
        term="FHS",
        definition="Filesystem Hierarchy Standard: the industry specification defining directory structure and contents in Linux/Unix OSes.",
        category="filesystem",
        see_also=["FSSTND", "TLDP"],
    ),
    GlossaryEntry(
        term="FIFO",
        definition="First In, First Out named pipe: a special file type allowing inter-process communication (IPC) via filesystem paths.",
        category="filesystem",
        see_also=["mknod", "IPC"],
    ),
    GlossaryEntry(
        term="FSSTND",
        definition="Linux Filesystem Standard: historical forerunner standard to FHS established in 1994.",
        category="filesystem",
        see_also=["FHS"],
    ),
    GlossaryEntry(
        term="GID",
        definition="Group Identifier: numerical ID representing user groups for file ownership and permission control.",
        category="security",
        see_also=["UID", "permissions"],
    ),
    GlossaryEntry(
        term="GRUB",
        definition="Grand Unified Bootloader: multiboot-capable bootloader that loads the kernel and initrd into memory.",
        category="boot",
        see_also=["LILO", "initrd"],
    ),
    GlossaryEntry(
        term="GUI",
        definition="Graphical User Interface: desktop environment allowing visual interaction via windows, menus, and pointers.",
        category="ui",
        see_also=["CLI", "X11"],
    ),
    GlossaryEntry(
        term="Hard link",
        definition="A directory entry that maps a filename directly to an existing inode on the same filesystem without duplicating data blocks.",
        category="filesystem",
        see_also=["inode", "Soft link"],
    ),
    GlossaryEntry(
        term="inode",
        definition="Index node: filesystem data structure holding metadata about a file (size, permissions, timestamps, block pointers), excluding its name.",
        category="filesystem",
        see_also=["Hard link", "stat"],
    ),
    GlossaryEntry(
        term="initrd",
        definition="Initial RAM disk: small memory-resident filesystem loaded by the bootloader containing drivers needed to mount the real rootfs.",
        category="boot",
        see_also=["pivot_root", "kernel"],
    ),
    GlossaryEntry(
        term="IPC",
        definition="Inter-Process Communication: mechanisms (pipes, sockets, message queues, shared memory, signals) for processes to exchange data.",
        category="kernel",
        see_also=["FIFO", "socket", "signals"],
    ),
    GlossaryEntry(
        term="kernel",
        definition="The core program of the operating system managing hardware, CPU scheduling, memory, filesystems, and device drivers.",
        category="kernel",
        see_also=["system call", "driver"],
    ),
    GlossaryEntry(
        term="LILO",
        definition="Linux Loader: classic bootloader for Linux on x86 architectures.",
        category="boot",
        see_also=["GRUB"],
    ),
    GlossaryEntry(
        term="loopback",
        definition="Network interface (lo / 127.0.0.1) that routes network traffic back to the local host machine.",
        category="networking",
        see_also=["TCP/IP"],
    ),
    GlossaryEntry(
        term="man page",
        definition="Online manual page documentation accessed via the man command, traditionally organized into sections 1 through 9.",
        category="documentation",
        see_also=["info"],
    ),
    GlossaryEntry(
        term="mount point",
        definition="A directory in the root hierarchy where a filesystem partition or remote storage volume is attached.",
        category="filesystem",
        see_also=["fstab", "mount"],
    ),
    GlossaryEntry(
        term="NFS",
        definition="Network File System: protocol allowing client machines to access and mount files over a network as if local.",
        category="networking",
        see_also=["Samba", "mount"],
    ),
    GlossaryEntry(
        term="PAM",
        definition="Pluggable Authentication Modules: modular architecture for system authentication, account policies, and session limits.",
        category="security",
        see_also=["SELinux"],
    ),
    GlossaryEntry(
        term="PID",
        definition="Process Identifier: a unique non-negative integer assigned by the kernel to each running process.",
        category="kernel",
        see_also=["PPID", "procfs"],
    ),
    GlossaryEntry(
        term="POSIX",
        definition="Portable Operating System Interface: IEEE standards specifying API, shell, and utilities for Unix compatibility.",
        category="standards",
        see_also=["FHS", "System V"],
    ),
    GlossaryEntry(
        term="procfs",
        definition="Virtual pseudo-filesystem mounted on /proc providing a process table and kernel runtime diagnostics in text format.",
        category="filesystem",
        see_also=["sysfs", "PID"],
    ),
    GlossaryEntry(
        term="quota",
        definition="Filesystem mechanism restricting the maximum disk space or inode count allowed for a specific user or group.",
        category="filesystem",
        see_also=["UID", "GID"],
    ),
    GlossaryEntry(
        term="RAID",
        definition="Redundant Array of Independent Disks: storage technology combining multiple physical disk drives for performance or redundancy.",
        category="storage",
        see_also=["filesystem"],
    ),
    GlossaryEntry(
        term="runlevel",
        definition="Operating state in System V init systems (0=halt, 1=single user, 2-5=multiuser, 6=reboot).",
        category="boot",
        see_also=["sysvinit", "init"],
    ),
    GlossaryEntry(
        term="SANE",
        definition="Scanner Access Now Easy: universal API and network protocol for accessing raster image scanners.",
        category="hardware",
        see_also=["drivers"],
    ),
    GlossaryEntry(
        term="SELinux",
        definition="Security-Enhanced Linux: Linux kernel security module implementing Flask-based Mandatory Access Control (MAC).",
        category="security",
        see_also=["PAM", "permissions"],
    ),
    GlossaryEntry(
        term="setuid",
        definition="Permission bit flag (04000) allowing an executable file to run with the privileges of the file's owner (often root).",
        category="security",
        see_also=["setgid", "sticky bit"],
    ),
    GlossaryEntry(
        term="signal",
        definition="Asynchronous software interrupt sent to a process to notify it of an event (e.g. SIGTERM, SIGKILL, SIGSEGV).",
        category="kernel",
        see_also=["IPC", "core"],
    ),
    GlossaryEntry(
        term="socket",
        definition="Communication endpoint for inter-process communication across network (AF_INET) or local filesystem (AF_UNIX).",
        category="networking",
        see_also=["FIFO", "IPC"],
    ),
    GlossaryEntry(
        term="Soft link",
        definition="Symbolic link (symlink): a special file containing a path reference to another target file or directory.",
        category="filesystem",
        see_also=["Hard link"],
    ),
    GlossaryEntry(
        term="spool",
        definition="Simultaneous Peripheral Operations On-Line: queue directory (/var/spool) holding print jobs, mail, or cron tasks.",
        category="filesystem",
        see_also=["var", "daemon"],
    ),
    GlossaryEntry(
        term="sticky bit",
        definition="Permission bit flag (01000) on directories (e.g. /tmp) restricting deletion of files only to the file owner or root.",
        category="security",
        see_also=["permissions", "tmp"],
    ),
    GlossaryEntry(
        term="swap",
        definition="Dedicated disk partition or file used by virtual memory management to page out inactive RAM pages.",
        category="storage",
        see_also=["swapon", "memory"],
    ),
    GlossaryEntry(
        term="sysvinit",
        definition="Classic System V style initialization daemon (/sbin/init) orchestrating service startup via runlevels.",
        category="boot",
        see_also=["runlevel", "systemd"],
    ),
    GlossaryEntry(
        term="TCP/IP",
        definition="Transmission Control Protocol / Internet Protocol: the foundational suite of networking communication protocols.",
        category="networking",
        see_also=["DNS", "socket"],
    ),
    GlossaryEntry(
        term="TFTP",
        definition="Trivial File Transfer Protocol: simple lockstep file transfer protocol used for booting diskless clients and PXE.",
        category="networking",
        see_also=["PXE", "boot"],
    ),
    GlossaryEntry(
        term="tmpfs",
        definition="RAM-backed temporary filesystem that dynamically expands and shrinks in memory with no persistent disk I/O.",
        category="filesystem",
        see_also=["tmp", "ramdisk"],
    ),
    GlossaryEntry(
        term="UID",
        definition="User Identifier: numerical ID representing a system user account for authentication and access control.",
        category="security",
        see_also=["GID", "permissions"],
    ),
    GlossaryEntry(
        term="umask",
        definition="User file-creation mode mask: specifies the permission bits automatically disabled when new files/directories are created.",
        category="security",
        see_also=["permissions"],
    ),
    GlossaryEntry(
        term="VFS",
        definition="Virtual Filesystem Switch: kernel abstraction layer enabling programs to access various concrete filesystem types transparently.",
        category="filesystem",
        see_also=["EXT3", "procfs"],
    ),
    GlossaryEntry(
        term="zombie",
        definition="A terminated child process whose exit status has not yet been read by its parent process via wait().",
        category="kernel",
        see_also=["PID", "signals"],
    ),
]


class GlossaryRegistry:
    """Registry and query engine for the Linux Filesystem Hierarchy Glossary."""

    def __init__(self, entries: Optional[List[GlossaryEntry]] = None) -> None:
        self._entries: Dict[str, GlossaryEntry] = {}
        for e in (entries or GLOSSARY_DATA):
            self._entries[e.term.lower()] = e

    def get(self, term: str) -> Optional[GlossaryEntry]:
        return self._entries.get(term.lower())

    def list_all(self) -> List[GlossaryEntry]:
        return sorted(self._entries.values(), key=lambda e: e.term.lower())

    def search(self, query: str) -> List[GlossaryEntry]:
        q = query.lower()
        results = []
        for e in self._entries.values():
            if q in e.term.lower() or q in e.definition.lower() or q in e.category.lower() or any(q in s.lower() for s in e.see_also):
                results.append(e)
        return results

    def filter_by_category(self, category: str) -> List[GlossaryEntry]:
        return [e for e in self._entries.values() if e.category.lower() == category.lower()]
