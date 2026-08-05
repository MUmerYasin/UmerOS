"""
UmerOS /bin System Information Commands
=========================================
Implementation of system information commands per FHS 3.0.

Commands implemented:
  uname    - Print system information
  dmesg    - Print or control the kernel ring buffer
  hostname - Show or set the system's hostname
  df       - Report file system disk space usage
  echo     - Display a line of text
  date     - Print or set the system date and time
  pwd      - Print name of current working directory
"""

from __future__ import annotations

import os
import platform
import re
import socket
import struct
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum, auto
from pathlib import Path
from typing import Any, Dict, IO, List, Optional, Tuple, Union


# ─── Constants ───────────────────────────────────────────────────────────────

DEFAULT_DATE_FORMAT = "%a %b %d %H:%M:%S %Z %Y"
KERNEL_RING_BUFFER_DEVICE = "/dev/kmsg"
HOSTNAME_FILE = "/etc/hostname"
HOSTS_FILE = "/etc/hosts"


# ─── Enums ───────────────────────────────────────────────────────────────────

class UnameFlag(IntEnum):
    """uname flags."""
    SYSNAME = 1     # -s: kernel name
    NODENAME = 2    # -n: hostname
    RELEASE = 4     # -r: kernel release
    VERSION = 8     # -v: kernel version
    MACHINE = 16    # -m: machine architecture
    ARCHITECTURE = 32  # -p: processor type
    ALL = 63        # -a: all flags
    KERNEL_NAME = 1
    HOSTNAME = 2
    KERNEL_RELEASE = 4
    KERNEL_VERSION = 8
    HARDWARE_PLATFORM = 16
    PROCESSOR = 32
    OPERATING_SYSTEM = 64


class DfFormat(IntEnum):
    """df output formats."""
    BLOCKS = 0       # -B: show in blocks
    HUMAN = 1        # -h: human-readable
    INODES = 2       # -i: show inodes
    KILO = 3         # -k: kilobytes (default)
    MEGA = 4         # -m: megabytes


class EchoEscape(IntEnum):
    """Echo escape sequence handling."""
    NONE = 0
    ENABLE = 1       # -e: enable backslash escapes
    DISABLE = 2      # -E: disable backslash escapes (default)


# ─── Exceptions ──────────────────────────────────────────────────────────────

class SystemInfoError(Exception):
    """Base exception for system info errors."""
    def __init__(self, command: str, message: str, exit_code: int = 1):
        self.command = command
        self.message = message
        self.exit_code = exit_code
        super().__init__(f"{command}: {message}")


# ─── Uname Command ──────────────────────────────────────────────────────────

@dataclass
class UnameInfo:
    """System information structure."""
    sysname: str = ""
    nodename: str = ""
    release: str = ""
    version: str = ""
    machine: str = ""
    processor: str = ""
    hardware_platform: str = ""
    operating_system: str = ""

    @classmethod
    def get_current(cls) -> "UnameInfo":
        """Get current system information."""
        info = cls()
        try:
            info.sysname = platform.system()  # e.g., "Linux"
            info.nodename = socket.gethostname()
            info.release = platform.release()  # e.g., "5.15.0-56-generic"
            info.version = platform.version()  # e.g., "#62-Ubuntu SMP Tue Nov 22 19:54:14 UTC 2022"
            info.machine = platform.machine()  # e.g., "x86_64"
            info.processor = platform.processor() or info.machine
            info.hardware_platform = platform.machine()
            info.operating_system = f"{info.sysname}"
        except Exception:
            pass
        return info

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary."""
        return {
            "sysname": self.sysname,
            "nodename": self.nodename,
            "release": self.release,
            "version": self.version,
            "machine": self.machine,
            "processor": self.processor,
            "hardware_platform": self.hardware_platform,
            "operating_system": self.operating_system,
        }


class UnameCommand:
    """
    uname - print system information.

    Usage: uname [OPTION]...

    Options:
      -a, --all                print all information
      -s, --kernel-name        print the kernel name
      -n, --nodename           print the network node hostname
      -r, --kernel-release     print the kernel release
      -v, --kernel-version     print the kernel version
      -m, --machine            print the machine hardware name
      -p, --processor          print the processor type
      -i, --hardware-platform  print the hardware platform
      -o, --operating-system   print the operating system
      --help                   display this help and exit
      --version                output version information and exit
    """

    def __init__(self) -> None:
        self.name = "uname"

    def execute(
        self,
        flags: int = UnameFlag.ALL,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute uname command."""
        out = output or sys.stdout
        info = UnameInfo.get_current()

        parts: List[str] = []

        if flags & UnameFlag.SYSNAME:
            parts.append(info.sysname)
        if flags & UnameFlag.NODENAME:
            parts.append(info.nodename)
        if flags & UnameFlag.RELEASE:
            parts.append(info.release)
        if flags & UnameFlag.VERSION:
            parts.append(info.version)
        if flags & UnameFlag.MACHINE:
            parts.append(info.machine)
        if flags & UnameFlag.ARCHITECTURE:
            parts.append(info.processor)
        if flags & (UnameFlag.HARDWARE_PLATFORM):
            parts.append(info.hardware_platform)
        if flags & UnameFlag.OPERATING_SYSTEM:
            parts.append(info.operating_system)

        if not parts:
            # Default: just sysname
            parts.append(info.sysname)

        print(" ".join(parts), file=out)
        return 0

    def get_info(self) -> UnameInfo:
        """Get system information without printing."""
        return UnameInfo.get_current()


# ─── Dmesg Command ──────────────────────────────────────────────────────────

@dataclass
class KernelMessage:
    """Represents a kernel ring buffer message."""
    timestamp: float
    level: int  # 0-7 (0=emerg, 7=debug)
    facility: int
    sequence: int
    message: str

    @property
    def level_name(self) -> str:
        """Get level name."""
        levels = {
            0: "emerg", 1: "alert", 2: "crit", 3: "err",
            4: "warn", 5: "notice", 6: "info", 7: "debug"
        }
        return levels.get(self.level, "unknown")

    @property
    def facility_name(self) -> str:
        """Get facility name."""
        facilities = {
            0: "kern", 1: "user", 2: "mail", 3: "daemon",
            4: "auth", 5: "syslog", 6: "lpr", 7: "news",
        }
        return facilities.get(self.facility, "unknown")


class DmesgCommand:
    """
    dmesg - print or control the kernel ring buffer.

    Usage: dmesg [OPTION]...

    Options:
      -c, --clear              read and clear all messages
      -C, --read-clear         read all messages and clear ring buffer
      -d, --decode             decode facility and level to printable prefix
      -e, --decode             alias for -d
      -f, --facility=LIST      filter output by facility name
      -h, --help               display this help and exit
      -l, --level=LIST         filter output by level
      -n, --console-level=LEVEL  set the level at which to log to console
      -r, --raw                print the raw message buffer
      -s, --buffer-size=SIZE   buffer size to query
      -T, --ctime              show human-readable timestamp
      -t, --no-timestamp       don't show timestamp
      -u, --userspace          show userspace messages
      -w, --follow             wait for new messages
      -x, --decode             facility and level (human-readable)
      --version                output version information and exit
    """

    def __init__(self) -> None:
        self.name = "dmesg"

    def execute(
        self,
        clear: bool = False,
        read_clear: bool = False,
        decode: bool = False,
        show_timestamp: bool = True,
        follow: bool = False,
        level_filter: Optional[List[int]] = None,
        facility_filter: Optional[List[int]] = None,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute dmesg command."""
        out = output or sys.stdout

        try:
            messages = self._read_ring_buffer()

            # Apply filters
            if level_filter:
                messages = [m for m in messages if m.level in level_filter]
            if facility_filter:
                messages = [m for m in messages if m.facility in facility_filter]

            # Format and print
            for msg in messages:
                line = self._format_message(msg, decode, show_timestamp)
                print(line, file=out)

            # Clear buffer if requested
            if clear or read_clear:
                self._clear_ring_buffer()

            return 0

        except PermissionError:
            print("dmesg: operation not permitted", file=sys.stderr)
            return 1
        except OSError as e:
            print(f"dmesg: {e}", file=sys.stderr)
            return 1

    def _read_ring_buffer(self) -> List[KernelMessage]:
        """Read kernel ring buffer."""
        messages: List[KernelMessage] = []

        # Try /dev/kmsg first
        if os.path.exists(KERNEL_RING_BUFFER_DEVICE):
            try:
                with open(KERNEL_RING_BUFFER_DEVICE, "r") as f:
                    for line in f:
                        msg = self._parse_kmsg_line(line.strip())
                        if msg:
                            messages.append(msg)
                return messages
            except (PermissionError, OSError):
                pass

        # Try dmesg command
        try:
            import subprocess
            result = subprocess.run(["dmesg"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    msg = self._parse_dmesg_line(line.strip())
                    if msg:
                        messages.append(msg)
                return messages
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Generate synthetic messages for UmerOS
        messages = self._get_synthetic_messages()
        return messages

    def _get_synthetic_messages(self) -> List[KernelMessage]:
        """Generate synthetic kernel messages for UmerOS."""
        now = time.time()
        return [
            KernelMessage(timestamp=now - 100, level=6, facility=0, sequence=1,
                          message="UmerOS kernel booting"),
            KernelMessage(timestamp=now - 99, level=6, facility=0, sequence=2,
                          message="Memory: 1024MB available"),
            KernelMessage(timestamp=now - 98, level=6, facility=0, sequence=3,
                          message="CPU: Python virtual processor"),
            KernelMessage(timestamp=now - 97, level=6, facility=0, sequence=4,
                          message="Filesystem: UmerFS initialized"),
            KernelMessage(timestamp=now - 96, level=4, facility=0, sequence=5,
                          message="Warning: running in emulation mode"),
        ]

    def _parse_kmsg_line(self, line: str) -> Optional[KernelMessage]:
        """Parse a /dev/kmsg line."""
        # Format: <level>,<facility>,<sequence>,<timestamp>;message
        match = re.match(r"<(\d+)>,(\d+),(\d+),(\d+);(.*)", line)
        if match:
            level_facility = int(match.group(1))
            return KernelMessage(
                timestamp=float(match.group(4)) / 1000000.0,
                level=level_facility & 7,
                facility=level_facility >> 3,
                sequence=int(match.group(3)),
                message=match.group(5),
            )
        return None

    def _parse_dmesg_line(self, line: str) -> Optional[KernelMessage]:
        """Parse a dmesg command output line."""
        # Common format: [timestamp] message
        match = re.match(r"\[\s*([\d.]+)\]\s*(.*)", line)
        if match:
            return KernelMessage(
                timestamp=float(match.group(1)),
                level=6,
                facility=0,
                sequence=0,
                message=match.group(2),
            )
        # Simple format
        return KernelMessage(
            timestamp=time.time(),
            level=6,
            facility=0,
            sequence=0,
            message=line,
        )

    def _format_message(
        self,
        msg: KernelMessage,
        decode: bool,
        show_timestamp: bool,
    ) -> str:
        """Format a kernel message for display."""
        parts: List[str] = []

        if show_timestamp:
            if decode:
                parts.append(f"[{msg.timestamp:10.6f}]")
            else:
                parts.append(f"[{msg.timestamp:8.2f}]")

        if decode:
            parts.append(f"[{msg.facility_name}.{msg.level_name}]")

        parts.append(msg.message)
        return " ".join(parts)

    def _clear_ring_buffer(self) -> None:
        """Clear the kernel ring buffer."""
        try:
            # Try /dev/kmsg
            if os.path.exists(KERNEL_RING_BUFFER_DEVICE):
                with open(KERNEL_RING_BUFFER_DEVICE, "w") as f:
                    f.write("1")  # Clear command
                return

            # Try dmesg -c
            import subprocess
            subprocess.run(["dmesg", "-c"], capture_output=True)
        except (PermissionError, OSError):
            pass


# ─── Hostname Command ───────────────────────────────────────────────────────

class HostnameCommand:
    """
    hostname - show or set the system's hostname.

    Usage: hostname [OPTION]... [NAME]

    Options:
      -a, --alias              alias names
      -d, --domain             DNS domain name
      -f, --fqdn, --long       DNS host name
      -i, --ip-address         addresses for the host name
      -s, --short              short host name
      -y, --yp, --nis          NIS/YP domain name
      -F, --file=FILE          read host name from FILE
      --help                   display this help and exit
      --version                output version information and exit

    When called without arguments, print the current hostname.
    """

    def __init__(self) -> None:
        self.name = "hostname"

    def execute(
        self,
        new_name: Optional[str] = None,
        alias: bool = False,
        domain: bool = False,
        fqdn: bool = False,
        ip_address: bool = False,
        short: bool = False,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute hostname command."""
        out = output or sys.stdout

        if new_name:
            return self._set_hostname(new_name)

        current = self._get_hostname()

        if fqdn or domain:
            try:
                current = socket.getfqdn()
            except Exception:
                pass
        elif short:
            current = current.split(".")[0]
        elif alias:
            try:
                aliases = socket.gethostbyaddr(socket.gethostname())[1]
                if aliases:
                    current = aliases[0]
            except Exception:
                pass
        elif ip_address:
            try:
                ips = socket.gethostbyname_ex(socket.gethostname())[2]
                if ips:
                    current = " ".join(ips)
            except Exception:
                pass

        print(current, file=out)
        return 0

    def _get_hostname(self) -> str:
        """Get current hostname."""
        try:
            # Try socket first
            return socket.gethostname()
        except Exception:
            pass

        try:
            # Try os.uname
            return os.uname().nodename
        except Exception:
            pass

        try:
            # Try hostname file
            if os.path.exists(HOSTNAME_FILE):
                with open(HOSTNAME_FILE, "r") as f:
                    return f.read().strip()
        except Exception:
            pass

        return "localhost"

    def _set_hostname(self, hostname: str) -> int:
        """Set hostname."""
        try:
            # Try writing to hostname file
            if os.path.exists(HOSTNAME_FILE):
                with open(HOSTNAME_FILE, "w") as f:
                    f.write(hostname + "\n")

            # Try socket.sethostname if available
            if hasattr(socket, "sethostname"):
                socket.sethostname(hostname)

            # Try hostname command
            import subprocess
            subprocess.run(["hostname", hostname], capture_output=True)

            return 0

        except PermissionError:
            print("hostname: operation not permitted", file=sys.stderr)
            return 1
        except OSError as e:
            print(f"hostname: {e}", file=sys.stderr)
            return 1

    def get_fqdn(self) -> str:
        """Get fully qualified domain name."""
        try:
            return socket.getfqdn()
        except Exception:
            return self._get_hostname()


# ─── Df Command ──────────────────────────────────────────────────────────────

@dataclass
class FilesystemInfo:
    """Filesystem information."""
    filesystem: str
    mount_point: str
    fstype: str
    total_bytes: int = 0
    used_bytes: int = 0
    available_bytes: int = 0
    inodes_total: int = 0
    inodes_used: int = 0
    inodes_free: int = 0

    @property
    def total_blocks(self) -> int:
        """Total 1K blocks."""
        return self.total_bytes // 1024

    @property
    def used_blocks(self) -> int:
        """Used 1K blocks."""
        return self.used_bytes // 1024

    @property
    def available_blocks(self) -> int:
        """Available 1K blocks."""
        return self.available_bytes // 1024

    @property
    def use_percent(self) -> int:
        """Usage percentage."""
        if self.total_bytes == 0:
            return 0
        return int((self.used_bytes / self.total_bytes) * 100)


class DfCommand:
    """
    df - report file system disk space usage.

    Usage: df [OPTION]... [FILE]...

    Options:
      -a, --all             include pseudo, duplicate, inaccessible file systems
      -B, --block-size=SIZE  scale sizes by SIZE before printing
      -h, --human-readable  print sizes in human readable format (e.g., 1K 234M 2G)
      -H, --si              same as -h, but use powers of 1000 not 1024
      -i, --inodes          list inode information instead of block usage
      -k                    like --block-size=1K
      -l, --local           limit listing to local file systems
      --max-depth=N         limit listing to depth N
      -m                    like --block-size=1M
      -P, --portability     use the POSIX output format
      --sync                invoke sync before getting usage info
      -t, --type=TYPE       limit listing to file systems of type TYPE
      -T, --print-type      print file system type
      -x, --exclude-type=TYPE   limit listing to file systems not of type TYPE
      --help                display this help and exit
      --version             output version information and exit
    """

    def __init__(self) -> None:
        self.name = "df"
        self._filesystems: List[FilesystemInfo] = []

    def execute(
        self,
        paths: Optional[List[str]] = None,
        human_readable: bool = False,
        show_inodes: bool = False,
        show_type: bool = False,
        block_size: int = 1024,
        exclude_type: Optional[str] = None,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute df command."""
        out = output or sys.stdout
        exit_code = 0

        # Get filesystem information
        filesystems = self._get_filesystems()

        # Filter by paths if specified
        if paths:
            filesystems = [fs for fs in filesystems if fs.mount_point in paths]

        # Filter by exclude type
        if exclude_type:
            filesystems = [fs for fs in filesystems if fs.fstype != exclude_type]

        if not filesystems:
            print("df: no file systems mounted", file=sys.stderr)
            return 1

        # Print header
        if show_inodes:
            self._print_inode_header(out)
        else:
            self._print_header(show_type, human_readable, out)

        # Print entries
        for fs in filesystems:
            if show_inodes:
                self._print_inode_entry(fs, out)
            else:
                self._print_entry(fs, human_readable, block_size, show_type, out)

        return exit_code

    def _print_header(
        self,
        show_type: bool,
        human_readable: bool,
        output: IO[str],
    ) -> None:
        """Print header line."""
        parts = ["Filesystem"]
        if show_type:
            parts.append("Type")
        parts.extend(["1K-blocks", "Used", "Available", "Use%", "Mounted on"])
        print(" ".join(f"{p:>14}" for p in parts), file=output)

    def _print_inode_header(self, output: IO[str]) -> None:
        """Print inode header line."""
        parts = ["Filesystem", "Inodes", "IUsed", "IFree", "IUse%", "Mounted on"]
        print(" ".join(f"{p:>14}" for p in parts), file=output)

    def _print_entry(
        self,
        fs: FilesystemInfo,
        human_readable: bool,
        block_size: int,
        show_type: bool,
        output: IO[str],
    ) -> None:
        """Print filesystem entry."""
        if human_readable:
            total = self._human_size(fs.total_bytes)
            used = self._human_size(fs.used_bytes)
            avail = self._human_size(fs.available_bytes)
        else:
            total = str(fs.total_blocks)
            used = str(fs.used_blocks)
            avail = str(fs.available_blocks)

        parts = [fs.filesystem]
        if show_type:
            parts.append(fs.fstype)
        parts.extend([total, used, avail, f"{fs.use_percent}%", fs.mount_point])

        print(" ".join(f"{p:>14}" for p in parts), file=output)

    def _print_inode_entry(
        self,
        fs: FilesystemInfo,
        output: IO[str],
    ) -> None:
        """Print inode entry."""
        inode_use = 0
        if fs.inodes_total > 0:
            inode_use = int((fs.inodes_used / fs.inodes_total) * 100)

        parts = [
            fs.filesystem,
            str(fs.inodes_total),
            str(fs.inodes_used),
            str(fs.inodes_free),
            f"{inode_use}%",
            fs.mount_point,
        ]
        print(" ".join(f"{p:>14}" for p in parts), file=output)

    def _human_size(self, size: int) -> str:
        """Convert size to human-readable format."""
        for unit in ("B", "K", "M", "G", "T", "P"):
            if abs(size) < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}E"

    def _get_filesystems(self) -> List[FilesystemInfo]:
        """Get mounted filesystems."""
        filesystems: List[FilesystemInfo] = []

        try:
            # Try os.statvfs for root filesystem
            st = os.statvfs("/")
            root = FilesystemInfo(
                filesystem="/dev/root",
                mount_point="/",
                fstype="ext4",
                total_bytes=st.f_blocks * st.f_frsize,
                used_bytes=(st.f_blocks - st.f_bfree) * st.f_frsize,
                available_bytes=st.f_bavail * st.f_frsize,
                inodes_total=st.f_files,
                inodes_used=st.f_files - st.f_ffree,
                inodes_free=st.f_ffree,
            )
            filesystems.append(root)
        except OSError:
            # Synthetic for UmerOS
            filesystems.append(FilesystemInfo(
                filesystem="umerfs0",
                mount_point="/",
                fstype="umerfs",
                total_bytes=1024 * 1024 * 1024,
                used_bytes=512 * 1024 * 1024,
                available_bytes=512 * 1024 * 1024,
                inodes_total=65536,
                inodes_used=1024,
                inodes_free=64512,
            ))

        # Try to read /proc/mounts
        try:
            if os.path.exists("/proc/mounts"):
                with open("/proc/mounts", "r") as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 3 and not parts[0].startswith("proc"):
                            mount_point = parts[1]
                            fstype = parts[2]
                            if mount_point != "/" and os.path.exists(mount_point):
                                try:
                                    st = os.statvfs(mount_point)
                                    filesystems.append(FilesystemInfo(
                                        filesystem=parts[0],
                                        mount_point=mount_point,
                                        fstype=fstype,
                                        total_bytes=st.f_blocks * st.f_frsize,
                                        used_bytes=(st.f_blocks - st.f_bfree) * st.f_frsize,
                                        available_bytes=st.f_bavail * st.f_frsize,
                                        inodes_total=st.f_files,
                                        inodes_used=st.f_files - st.f_ffree,
                                        inodes_free=st.f_ffree,
                                    ))
                                except OSError:
                                    pass
        except Exception:
            pass

        # Add UmerOS synthetic filesystems
        filesystems.append(FilesystemInfo(
            filesystem="umerfs0",
            mount_point="/proc",
            fstype="proc",
        ))
        filesystems.append(FilesystemInfo(
            filesystem="sysfs",
            mount_point="/sys",
            fstype="sysfs",
        ))
        filesystems.append(FilesystemInfo(
            filesystem="tmpfs",
            mount_point="/tmp",
            fstype="tmpfs",
            total_bytes=256 * 1024 * 1024,
            used_bytes=32 * 1024 * 1024,
            available_bytes=224 * 1024 * 1024,
        ))

        return filesystems


# ─── Echo Command ────────────────────────────────────────────────────────────

class EchoCommand:
    """
    echo - display a line of text.

    Usage: echo [SHORT-OPTION]... [STRING]...
           echo LONG-OPTION

    Options:
      -n    do not output the trailing newline
      -e    enable interpretation of backslash escapes
      -E    disable interpretation of backslash escapes (default)
      --help        display this help and exit
      --version     output version information and exit

    Backslash escapes:
      \a     alert (bell)
      \b     backspace
      \\c     suppress further output
      \\e     escape character
      \f     form feed
      \n     newline
      \r     carriage return
      \t     horizontal tab
      \v     vertical tab
      \\     backslash
      \\0NNN  byte with octal value NNN (1 to 3 digits)
      \\xHH   byte with hexadecimal value HH (1 to 2 digits)
      \\uHHHH unicode character with hex value HHHH (1 to 4 hex digits)
    """

    ESCAPE_SEQUENCES = {
        "a": "\a",
        "b": "\b",
        "e": "\x1b",
        "f": "\f",
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "v": "\v",
        "\\": "\\",
    }

    def __init__(self) -> None:
        self.name = "echo"

    def execute(
        self,
        args: List[str],
        no_newline: bool = False,
        enable_escapes: bool = False,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute echo command."""
        out = output or sys.stdout
        result = " ".join(args)

        if enable_escapes:
            result = self._process_escapes(result)

        print(result, end="" if no_newline else "\n", file=out)
        return 0

    def _process_escapes(self, text: str) -> str:
        """Process backslash escape sequences."""
        result: List[str] = []
        i = 0
        while i < len(text):
            if text[i] == "\\" and i + 1 < len(text):
                next_char = text[i + 1]

                if next_char in self.ESCAPE_SEQUENCES:
                    result.append(self.ESCAPE_SEQUENCES[next_char])
                    i += 2
                elif next_char == "0":
                    # Octal: \0NNN
                    oct_str = ""
                    j = i + 2
                    while j < len(text) and j < i + 5 and text[j].isdigit():
                        oct_str += text[j]
                        j += 1
                    if oct_str:
                        try:
                            result.append(chr(int(oct_str, 8)))
                        except ValueError:
                            result.append("\\" + next_char + oct_str)
                        i = j
                    else:
                        result.append("\\0")
                        i += 2
                elif next_char == "x":
                    # Hex: \xHH
                    hex_str = ""
                    j = i + 2
                    while j < len(text) and j < i + 4 and text[j] in "0123456789abcdefABCDEF":
                        hex_str += text[j]
                        j += 1
                    if hex_str:
                        try:
                            result.append(chr(int(hex_str, 16)))
                        except ValueError:
                            result.append("\\x" + hex_str)
                        i = j
                    else:
                        result.append("\\x")
                        i += 2
                elif next_char == "u":
                    # Unicode: \uHHHH
                    hex_str = ""
                    j = i + 2
                    while j < len(text) and j < i + 6 and text[j] in "0123456789abcdefABCDEF":
                        hex_str += text[j]
                        j += 1
                    if hex_str:
                        try:
                            codepoint = int(hex_str, 16)
                            result.append(chr(codepoint))
                        except ValueError:
                            result.append("\\u" + hex_str)
                        i = j
                    else:
                        result.append("\\u")
                        i += 2
                else:
                    result.append(text[i])
                    i += 1
            else:
                result.append(text[i])
                i += 1

        return "".join(result)

    def echo_file(self, filepath: str, output: Optional[IO[str]] = None) -> int:
        """Echo file contents to stdout."""
        try:
            with open(filepath, "r") as f:
                content = f.read()
            print(content, file=output or sys.stdout)
            return 0
        except FileNotFoundError:
            print(f"echo: {filepath}: No such file or directory", file=sys.stderr)
            return 1
        except IsADirectoryError:
            print(f"echo: {filepath}: Is a directory", file=sys.stderr)
            return 1
        except PermissionError:
            print(f"echo: {filepath}: Permission denied", file=sys.stderr)
            return 1


# ─── Date Command ────────────────────────────────────────────────────────────

class DateCommand:
    """
    date - print or set the system date and time.

    Usage: date [OPTION]... [+FORMAT]
           date [-u|--utc|--universal] [MMDDhhmm[[CC]YY][.ss]]

    Options:
      -d, --date=STRING        display time described by STRING, not 'now'
      -f, --file=DATEFILE      like --date; once for each line of DATEFILE
      -I, --iso-8601[=FMT]     output date/time in ISO 8601 format.
                               FMT='date' for date only (default), 'hours',
                               'minutes', 'seconds', or 'ns'
      -R, --rfc-email           output date and time in RFC 5322 style
      -r, --reference=FILE      display the last modification time of FILE
      -s, --set=STRING          set time described by STRING
      -u, --utc, --universal    print or set Coordinated Universal Time
      --help                    display this help and exit
      --version                 output version information and exit

    FORMAT controls the output.  Interpreted sequences are:
      %%   a literal %
      %a   abbreviated weekday name
      %A   full weekday name
      %b   abbreviated month name
      %B   full month name
      %c   date and time
      %d   day of month (01..31)
      %H   hour (00..23)
      %I   hour (01..12)
      %j   day of year (001..366)
      %m   month (01..12)
      %M   minute (00..59)
      %n   newline
      %p   AM or PM
      %S   second (00..60)
      %t   tab
      %U   week number of year (00..53)
      %w   day of week (0..6); Sunday=0
      %W   week number of year (00..53)
      %x   date (MM/DD/YY)
      %X   time (HH:MM:SS)
      %Y   full year
      %y   last two digits of year
      %Z   time zone (e.g., EDT)
    """

    def __init__(self) -> None:
        self.name = "date"

    def execute(
        self,
        fmt: Optional[str] = None,
        set_time: Optional[str] = None,
        utc: bool = False,
        iso_format: Optional[str] = None,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute date command."""
        out = output or sys.stdout

        if set_time:
            return self._set_time(set_time)

        now = datetime.now(timezone.utc if utc else None)

        if iso_format:
            if iso_format == "hours":
                print(now.strftime("%Y-%m-%dT%H"), file=out)
            elif iso_format == "minutes":
                print(now.strftime("%Y-%m-%dT%H:%M"), file=out)
            elif iso_format == "seconds":
                print(now.strftime("%Y-%m-%dT%H:%M:%S"), file=out)
            elif iso_format == "ns":
                print(now.strftime("%Y-%m-%dT%H:%M:%S.%f"), file=out)
            else:
                print(now.strftime("%Y-%m-%d"), file=out)
        elif fmt:
            print(now.strftime(fmt), file=out)
        else:
            print(now.strftime(DEFAULT_DATE_FORMAT), file=out)

        return 0

    def _set_time(self, time_str: str) -> int:
        """Set system time."""
        try:
            # Parse time string format: MMDDhhmm[[CC]YY][.ss]
            if len(time_str) < 10:
                print(f"date: invalid date '{time_str}'", file=sys.stderr)
                return 1

            month = int(time_str[0:2])
            day = int(time_str[2:4])
            hour = int(time_str[4:6])
            minute = int(time_str[6:8])

            if len(time_str) > 8:
                year_str = time_str[8:].split(".")[0]
                if len(year_str) == 4:
                    year = int(year_str)
                elif len(year_str) == 2:
                    year = 2000 + int(year_str)
                else:
                    year = datetime.now().year
            else:
                year = datetime.now().year

            second = 0
            if "." in time_str:
                second = int(time_str.split(".")[1])

            # Validate
            if not (1 <= month <= 12):
                raise ValueError(f"invalid month '{month}'")
            if not (1 <= day <= 31):
                raise ValueError(f"invalid day '{day}'")
            if not (0 <= hour <= 23):
                raise ValueError(f"invalid hour '{hour}'")
            if not (0 <= minute <= 59):
                raise ValueError(f"invalid minute '{minute}'")
            if not (0 <= second <= 59):
                raise ValueError(f"invalid second '{second}'")

            # Try to set time (requires root)
            import subprocess
            subprocess.run(["date", "-s", f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"], check=True)

            return 0

        except ValueError as e:
            print(f"date: invalid date '{time_str}': {e}", file=sys.stderr)
            return 1
        except subprocess.CalledProcessError as e:
            print(f"date: cannot set date: {e}", file=sys.stderr)
            return 1
        except PermissionError:
            print("date: operation not permitted", file=sys.stderr)
            return 1


# ─── Pwd Command ─────────────────────────────────────────────────────────────

class PwdCommand:
    """
    pwd - print name of current working directory.

    Usage: pwd [OPTION]...

    Options:
      -L, --logical    use PWD from environment, even if it contains symlinks
      -P, --physical   avoid all symlinks
      --help           display this help and exit
      --version        output version information and exit

    If no option is specified, -P is assumed.
    """

    def __init__(self) -> None:
        self.name = "pwd"

    def execute(
        self,
        logical: bool = False,
        physical: bool = True,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute pwd command."""
        out = output or sys.stdout

        if logical:
            # Use PWD from environment if available
            pwd = os.environ.get("PWD")
            if pwd and os.path.isdir(pwd):
                print(pwd, file=out)
                return 0

        # Physical path (resolve symlinks)
        try:
            cwd = os.getcwd()
            print(cwd, file=out)
            return 0
        except OSError as e:
            print(f"pwd: {e}", file=sys.stderr)
            return 1

    def get_path(self, logical: bool = False) -> str:
        """Get current working directory path."""
        if logical:
            pwd = os.environ.get("PWD")
            if pwd and os.path.isdir(pwd):
                return pwd
        return os.getcwd()


# ─── Module Exports ──────────────────────────────────────────────────────────

__all__ = [
    "UnameCommand",
    "DmesgCommand",
    "HostnameCommand",
    "DfCommand",
    "EchoCommand",
    "DateCommand",
    "PwdCommand",
    "UnameInfo",
    "KernelMessage",
    "FilesystemInfo",
    "UnameFlag",
    "DfFormat",
    "EchoEscape",
    "SystemInfoError",
]
