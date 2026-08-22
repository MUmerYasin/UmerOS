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

import os
import platform
import time
import json
from typing import Dict, Any, List

def _read_file(path: str) -> str:
    """Safely read a file from the real /proc if it exists."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def cpuinfo() -> Dict[str, Any]:
    """Return CPU information similar to /proc/cpuinfo.
    Falls back to platform.uname() if /proc/cpuinfo is unavailable.
    """
    raw = _read_file("/proc/cpuinfo")
    if raw:
        info = {}
        for line in raw.splitlines():
            if not line.strip():
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                info[key.strip()] = value.strip()
        return info
    uname = platform.uname()
    return {
        "processor": uname.processor,
        "machine": uname.machine,
        "system": uname.system,
        "release": uname.release,
        "version": uname.version,
    }

def meminfo() -> Dict[str, Any]:
    """Return memory information similar to /proc/meminfo.
    Falls back to os.sysconf values if /proc/meminfo is unavailable.
    """
    raw = _read_file("/proc/meminfo")
    if raw:
        info = {}
        for line in raw.splitlines():
            if not line.strip():
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                info[key.strip()] = value.strip()
        return info
    try:
        pages = os.sysconf('SC_PHYS_PAGES')
        page_size = os.sysconf('SC_PAGE_SIZE')
        total = pages * page_size
        return {"MemTotal": f"{total // 1024} kB"}
    except Exception:
        return {}

def uptime() -> Dict[str, float]:
    """Return system uptime similar to /proc/uptime.
    Provides total seconds and idle seconds.
    """
    raw = _read_file("/proc/uptime")
    if raw:
        parts = raw.split()
        if len(parts) >= 2:
            return {"total": float(parts[0]), "idle": float(parts[1])}
    try:
        import psutil
        boot = psutil.boot_time()
        now = time.time()
        return {"total": now - boot, "idle": 0.0}
    except Exception:
        return {"total": 0.0, "idle": 0.0}

def loadavg() -> Dict[str, float]:
    """Return load average similar to /proc/loadavg."""
    try:
        avg1, avg5, avg15 = os.getloadavg()
        return {"1min": avg1, "5min": avg5, "15min": avg15}
    except Exception:
        return {"1min": 0.0, "5min": 0.0, "15min": 0.0}

def version() -> str:
    """Return kernel version similar to /proc/version."""
    raw = _read_file("/proc/version")
    if raw:
        return raw.strip()
    try:
        import platform
        return platform.release()
    except Exception:
        return ""

def filesystems() -> List[str]:
    """Return supported filesystems similar to /proc/filesystems."""
    raw = _read_file("/proc/filesystems")
    if raw:
        return [line.split()[-1] for line in raw.splitlines() if line.strip()]
    return []

def partitions() -> List[Dict[str, Any]]:
    """Return partition info similar to /proc/partitions."""
    raw = _read_file("/proc/partitions")
    if raw:
        parts = []
        for line in raw.splitlines()[2:]:
            if not line.strip():
                continue
            fields = line.split()
            if len(fields) == 4:
                major, minor, blocks, name = fields
                parts.append({"major": int(major), "minor": int(minor), "blocks": int(blocks), "name": name})
        return parts
    return []

def swaps() -> List[Dict[str, Any]]:
    """Return swap info similar to /proc/swaps."""
    raw = _read_file("/proc/swaps")
    if raw:
        swaps = []
        for line in raw.splitlines()[1:]:
            if not line.strip():
                continue
            fields = line.split()
            if len(fields) >= 5:
                filename, type_, size, used, priority = fields[:5]
                swaps.append({"filename": filename, "type": type_, "size": int(size), "used": int(used), "priority": int(priority)})
        return swaps
    return []

def interrupts() -> List[Dict[str, Any]]:
    """Return interrupt info similar to /proc/interrupts."""
    raw = _read_file("/proc/interrupts")
    if raw:
        lines = raw.splitlines()
        header = lines[0].split()
        result = []
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split()
            irq = parts[0].rstrip(':')
            counts = parts[1:1+len(header)]
            description = " ".join(parts[1+len(header):])
            result.append({"irq": irq, "counts": counts, "description": description})
        return result
    return []

def ioports() -> List[str]:
    """Return I/O ports similar to /proc/ioports."""
    raw = _read_file("/proc/ioports")
    if raw:
        return [line.strip() for line in raw.splitlines() if line.strip()]
    return []

def dma() -> List[str]:
    """Return DMA channels similar to /proc/dma."""
    raw = _read_file("/proc/dma")
    if raw:
        return [line.strip() for line in raw.splitlines() if line.strip()]
    return []

def modules() -> List[Dict[str, Any]]:
    """Return loaded kernel modules similar to /proc/modules."""
    raw = _read_file("/proc/modules")
    if raw:
        mods = []
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) >= 6:
                name, size, usage, deps, state, offset = parts[:6]
                mods.append({"name": name, "size": int(size), "usage": int(usage), "deps": deps, "state": state, "offset": offset})
        return mods
    return []

def mounts() -> List[Dict[str, str]]:
    """Return mount information similar to /proc/mounts."""
    raw = _read_file("/proc/mounts")
    if raw:
        mounts = []
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                device, mountpoint, fstype = parts[:3]
                mounts.append({"device": device, "mountpoint": mountpoint, "fstype": fstype})
        return mounts
    return []

def process_info(pid: int) -> Dict[str, Any]:
    """Return basic information about a process.
    Mirrors the data you would find in /proc/<pid>/status.
    """
    proc_path = f"/proc/{pid}/status"
    raw = _read_file(proc_path)
    if raw:
        info = {}
        for line in raw.splitlines():
            if not line.strip():
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                info[key.strip()] = value.strip()
        return info
    try:
        import psutil
        p = psutil.Process(pid)
        return {
            "Name": p.name(),
            "Status": p.status(),
            "Cmdline": " ".join(p.cmdline()),
            "Memory": p.memory_info()._asdict(),
            "CPU%": p.cpu_percent(interval=0.1),
        }
    except Exception as e:
        return {"error": str(e)}

def process_cmdline(pid: int) -> List[str]:
    """Return command line arguments of a process similar to /proc/<pid>/cmdline."""
    raw = _read_file(f"/proc/{pid}/cmdline")
    if raw:
        return raw.split('\0')[:-1]
    try:
        import psutil
        return psutil.Process(pid).cmdline()
    except Exception:
        return []

def process_environ(pid: int) -> Dict[str, str]:
    """Return environment variables of a process similar to /proc/<pid>/environ."""
    raw = _read_file(f"/proc/{pid}/environ")
    if raw:
        env = {}
        for pair in raw.split('\0'):
            if '=' in pair:
                k, v = pair.split('=', 1)
                env[k] = v
        return env
    try:
        import psutil
        return psutil.Process(pid).environ()
    except Exception:
        return {}

def process_fd(pid: int) -> List[str]:
    """Return list of file descriptor paths for a process similar to /proc/<pid>/fd."""
    fd_dir = f"/proc/{pid}/fd"
    try:
        return os.listdir(fd_dir)
    except Exception:
        try:
            import psutil
            return [str(f.path) for f in psutil.Process(pid).open_files()]
        except Exception:
            return []

def all_pids() -> List[int]:
    """Return a list of all process IDs visible in /proc."""
    try:
        entries = os.listdir("/proc")
        return [int(entry) for entry in entries if entry.isdigit()]
    except Exception:
        try:
            import psutil
            return psutil.pids()
        except Exception:
            return []

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="UmerOS /proc emulation utilities")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("cpuinfo", help="Print CPU info")
    subparsers.add_parser("meminfo", help="Print memory info")
    subparsers.add_parser("uptime", help="Print system uptime")
    subparsers.add_parser("loadavg", help="Print load average")
    subparsers.add_parser("version", help="Print kernel version")
    subparsers.add_parser("filesystems", help="List supported filesystems")
    subparsers.add_parser("partitions", help="List partition table")
    subparsers.add_parser("swaps", help="List swap devices")
    subparsers.add_parser("interrupts", help="List interrupt info")
    subparsers.add_parser("ioports", help="List I/O ports")
    subparsers.add_parser("dma", help="List DMA channels")
    subparsers.add_parser("modules", help="List loaded kernel modules")
    subparsers.add_parser("mounts", help="List mounted filesystems")
    subparsers.add_parser("pids", help="List all PIDs")
    pid_parser = subparsers.add_parser("pid", help="Show info for a PID")
    pid_parser.add_argument("pid", type=int, help="Process ID")
    pid_parser.add_argument("info", choices=["status", "cmdline", "environ", "fd"], default="status")
    args = parser.parse_args()
    if args.command == "cpuinfo":
        print(json.dumps(cpuinfo(), indent=2))
    elif args.command == "meminfo":
        print(json.dumps(meminfo(), indent=2))
    elif args.command == "uptime":
        print(json.dumps(uptime(), indent=2))
    elif args.command == "loadavg":
        print(json.dumps(loadavg(), indent=2))
    elif args.command == "version":
        print(version())
    elif args.command == "filesystems":
        print(json.dumps(filesystems(), indent=2))
    elif args.command == "partitions":
        print(json.dumps(partitions(), indent=2))
    elif args.command == "swaps":
        print(json.dumps(swaps(), indent=2))
    elif args.command == "interrupts":
        print(json.dumps(interrupts(), indent=2))
    elif args.command == "ioports":
        print(json.dumps(ioports(), indent=2))
    elif args.command == "dma":
        print(json.dumps(dma(), indent=2))
    elif args.command == "modules":
        print(json.dumps(modules(), indent=2))
    elif args.command == "mounts":
        print(json.dumps(mounts(), indent=2))
    elif args.command == "pids":
        print(json.dumps(all_pids(), indent=2))
    elif args.command == "pid":
        pid = args.pid
        if args.info == "status":
            print(json.dumps(process_info(pid), indent=2))
        elif args.info == "cmdline":
            print(json.dumps(process_cmdline(pid), indent=2))
        elif args.info == "environ":
            print(json.dumps(process_environ(pid), indent=2))
        elif args.info == "fd":
            print(json.dumps(process_fd(pid), indent=2))
    else:
        parser.print_help()
