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

"""Live data adapter feeding the UmerOS procfs.

``KernelAdapter`` normalises the (sometimes placeholder-shaped) UmerOS
kernel objects into the plain dictionaries the /proc handlers need:

* tasks — from ``kernel.scheduler._tasks`` (works for both the inline
  placeholder scheduler and the real ``kernel/scheduler.py``)
* memory — from ``kernel.memory.stats()`` (handles both the real page
  based stats and the "4GB" string placeholder)
* sysctl — the kernel's ``SysctlRegistry`` (or a standalone one)
* resources / softirq / ipc / partition — best effort via getattr

Without a kernel the adapter still serves a coherent simulated
system (idle task list, 4 GiB RAM, standard mounts), so the procfs is
fully usable standalone — mirroring how /proc reflects the running
kernel, whatever its state.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional

_ROOT_LOGGER = logging.getLogger()

# Task state -> Linux /proc/stat state letter (R/S/D/Z/T)
_STATE_LETTER = {
    "RUNNING": "R",
    "READY": "S",
    "WAITING": "S",
    "BLOCKED": "D",
    "DONE": "Z",
    "EXITING": "Z",
    "STOPPED": "T",
}

_UNIT_MULT = {
    "B": 1, "KB": 1000, "MB": 1000 ** 2, "GB": 1000 ** 3,
    "KIB": 1024, "MIB": 1024 ** 2, "GIB": 1024 ** 3,
}


class KernelRingLog(logging.Handler):
    """Bounded kernel-message ring buffer backing /proc/kmsg."""

    def __init__(self, capacity: int = 512) -> None:
        super().__init__(level=logging.INFO)
        self.capacity = capacity
        self._lines: List[str] = []
        self._t0 = time.monotonic()

    def _stamp(self) -> str:
        return f"[{time.monotonic() - self._t0:12.6f}]"

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        try:
            line = f"{self._stamp()} {record.levelname}: {record.getMessage()}"
        except Exception:  # noqa: BLE001 - a log handler must never raise
            line = f"{self._stamp()} {record.levelname}: <unformattable>"
        self._lines.append(line)
        if len(self._lines) > self.capacity:
            del self._lines[: len(self._lines) - self.capacity]

    def append(self, text: str) -> None:
        """Append a raw kernel-style message (kernel printk)."""
        for line in str(text).splitlines():
            self._lines.append(f"{self._stamp()} {line}")
        if len(self._lines) > self.capacity:
            del self._lines[: len(self._lines) - self.capacity]

    def tail(self, n: Optional[int] = None) -> str:
        lines = self._lines if n is None else self._lines[-n:]
        return "".join(line + "\n" for line in lines)

    def clear(self) -> None:
        self._lines.clear()

    def __len__(self) -> int:
        return len(self._lines)


class LoadAvgTracker:
    """Exponential 1/5/15-minute load averages from runnable counts."""

    def __init__(self) -> None:
        self._ema = [0.0, 0.0, 0.0]
        self._last = time.monotonic()
        self._seeded = False
        self.last_pid = 0
        self.total_threads = 0

    def update(self, runnable: int, total: int) -> None:
        now = time.monotonic()
        dt = max(now - self._last, 1e-6)
        self._last = now
        for i, window in enumerate((60.0, 300.0, 900.0)):
            # [RECONCILE] On the very first sample the time since construction is
            # ~0, so the EMA smoothing factor `alpha = dt/(dt + window/8)` is
            # ~0 and the estimate never moved off 0.0 — which failed
            # TestLoadAvgTracker::test_update_increases (expected one > 0.0).
            # Seed the estimate from the first sample instead of blending from 0.
            if not self._seeded:
                self._ema[i] = float(runnable)
            else:
                alpha = dt / (dt + window / 8.0)
                self._ema[i] += alpha * (runnable - self._ema[i])
        self._seeded = True
        self.total_threads = total

    def values(self) -> tuple:
        return (round(max(self._ema[0], 0.0), 2),
                round(max(self._ema[1], 0.0), 2),
                round(max(self._ema[2], 0.0), 2))


class KernelAdapter:
    """Normalised, kernel-attached data source for the procfs."""

    def __init__(self, kernel: Any = None,
                 network_stack: Any = None,
                 hostname: str = "umeros-node1") -> None:
        self.kernel = kernel
        self.network_stack = network_stack
        self.hostname = hostname
        self.kmsg = KernelRingLog()
        self.loadavg = LoadAvgTracker()
        self._boot_wall = time.time()
        # Writable state that lives outside the sysctl registry.
        self.irq_affinity: Dict[int, str] = {}
        self.oom_adj: Dict[int, int] = {}
        self._standalone_sysctl: Any = None
        try:
            _ROOT_LOGGER.addHandler(self.kmsg)
        except Exception:  # noqa: BLE001 - logging must never break boot
            pass
        self.kmsg.append("procfs: kernel adapter online")

    # ── tasks / processes ───────────────────────────────────────────

    def tasks(self) -> List[Dict[str, Any]]:
        """All scheduler tasks as normalised dicts (pid 0 excluded)."""
        sched = getattr(self.kernel, "scheduler", None)
        raw = getattr(sched, "_tasks", None) or {}
        tasks = []
        for pid, task in raw.items():
            tasks.append({
                "pid": getattr(task, "pid", int(pid)),
                "name": getattr(task, "name", f"task-{pid}"),
                "state": str(getattr(task, "state", "READY")).upper(),
                "priority": getattr(task, "priority", 0.5),
                "cpu_time": getattr(task, "cpu_time", 0.0),
                "parent_pid": getattr(task, "parent_pid", None),
            })
        tasks.sort(key=lambda t: t["pid"])
        return tasks

    def task(self, pid: int) -> Optional[Dict[str, Any]]:
        """One task by pid; pid 0 yields the synthetic kernel task."""
        if pid == 0:
            return {"pid": 0, "name": "umer_kernel", "state": "RUNNING",
                    "priority": 1.0, "cpu_time": self.uptime(),
                    "parent_pid": None}
        for task in self.tasks():
            if task["pid"] == pid:
                return task
        return None

    def pids(self) -> List[int]:
        return [task["pid"] for task in self.tasks()]

    def current_pid(self) -> int:
        """The pid /proc/self points at (init if present, else kernel)."""
        pids = self.pids()
        return pids[0] if pids else 0

    @staticmethod
    def state_letter(state: str) -> str:
        return _STATE_LETTER.get(str(state).upper(), "S")

    # ── time ────────────────────────────────────────────────────────

    def uptime(self) -> float:
        uptime_fn = getattr(self.kernel, "uptime", None)
        if callable(uptime_fn):
            try:
                return float(uptime_fn())
            except Exception:  # noqa: BLE001
                pass
        return time.monotonic()

    def boot_epoch(self) -> float:
        boot_time = getattr(self.kernel, "_boot_time", None)
        if boot_time is None:
            return self._boot_wall
        import time as _time
        return _time.time() - self.uptime()

    # ── memory ──────────────────────────────────────────────────────

    @staticmethod
    def _parse_size(text: str) -> Optional[int]:
        match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*([A-Za-z]+)?\s*$",
                         str(text))
        if not match:
            return None
        number = float(match.group(1))
        unit = (match.group(2) or "B").upper()
        mult = _UNIT_MULT.get(unit)
        if mult is None:
            return None
        return int(number * mult)

    def memory(self) -> Dict[str, Any]:
        """Normalised memory stats in bytes/kib (multi-shape aware)."""
        stats_fn = getattr(getattr(self.kernel, "memory", None), "stats", None)
        stats: Dict[str, Any] = {}
        if callable(stats_fn):
            try:
                stats = stats_fn() or {}
            except Exception:  # noqa: BLE001
                stats = {}

        total = free = None
        page_size = int(stats.get("page_size", 4096) or 4096)
        if "total_pages" in stats:
            total = int(stats["total_pages"]) * page_size
            free = int(stats.get("free_pages", 0)) * page_size
        else:
            total = self._parse_size(stats.get("total", "")) if stats else None
            free = self._parse_size(stats.get("free", "")) if stats else None
            if total is not None and free is None:
                used = self._parse_size(stats.get("used", ""))
                free = total - used if used is not None else total // 2
        if total is None:
            total = 4 * 1024 ** 3
            free = total // 2

        used = max(total - free, 0)
        cached = int(free * 0.48)
        return {
            "total": total, "free": free, "used": used,
            "available": free + cached,
            "buffers": int(total * 0.026),
            "cached": cached,
            "swap_total": 2 * 1024 ** 3, "swap_free": 2 * 1024 ** 3,
            "slab": int(total * 0.03),
            "page_size": page_size,
            "live_allocations": int(stats.get("live_allocations", 0) or 0),
            "total_kib": total // 1024, "free_kib": free // 1024,
        }

    def memory_by_pid(self) -> Dict[int, int]:
        """Bytes resident per pid from the memory manager's allocations."""
        allocs = getattr(getattr(self.kernel, "memory", None), "_allocs", None)
        if not allocs:
            return {}
        usage: Dict[int, int] = {}
        for entry in allocs.values():
            try:
                if isinstance(entry, tuple) and len(entry) == 3:
                    pid, _pages, size = entry
                elif isinstance(entry, tuple) and len(entry) == 2:
                    pid, size = entry
                else:
                    continue
                usage[int(pid)] = usage.get(int(pid), 0) + int(size)
            except (TypeError, ValueError):
                continue
        return usage

    # ── sysctl ──────────────────────────────────────────────────────

    def sysctl_registry(self) -> Any:
        registry = getattr(self.kernel, "sysctl", None)
        if registry is not None:
            return registry
        if self._standalone_sysctl is None:
            from kernel.sysctl import SysctlRegistry  # lazy: avoid cycles
            self._standalone_sysctl = SysctlRegistry()
        return self._standalone_sysctl

    # ── subsystems (best effort) ────────────────────────────────────

    def resources(self) -> Any:
        return getattr(self.kernel, "resources", None)

    def softirq_counts(self) -> Dict[str, int]:
        counts_fn = getattr(getattr(self.kernel, "softirq", None),
                            "counts", None)
        if callable(counts_fn):
            try:
                return dict(counts_fn())
            except Exception:  # noqa: BLE001
                return {}
        return {}

    def ipc_info(self) -> Dict[str, Any]:
        ipc = getattr(self.kernel, "ipc", None)
        queues: Dict[int, int] = {}
        for pid, queue in (getattr(ipc, "_queues", None) or {}).items():
            pending_fn = getattr(ipc, "pending", None)
            if callable(pending_fn):
                try:
                    queues[int(pid)] = int(pending_fn(int(pid)))
                except Exception:  # noqa: BLE001
                    queues[int(pid)] = 0
            else:
                queues[int(pid)] = getattr(queue, "qsize", lambda: 0)()
        channels = {}
        for channel, pids in (getattr(ipc, "_subscribers", None) or {}).items():
            channels[str(channel)] = [int(p) for p in pids]
        return {"queues": queues, "channels": channels}

    def partition(self) -> Optional[Dict[str, Any]]:
        part = getattr(self.kernel, "root_partition", None)
        if part is None:
            return None
        sb = getattr(part, "superblock", None)
        block_size = int(getattr(sb, "block_size", 4096) or 4096)
        total_blocks = int(getattr(sb, "total_blocks", 0) or 0)
        return {
            "name": getattr(part, "name", "qfs_root"),
            "major": 254, "minor": 0,
            "blocks_kib": total_blocks * block_size // 1024,
            "total_blocks": total_blocks,
            "total_inodes": int(getattr(sb, "total_inodes", 0) or 0),
        }

    def taint_summary(self) -> str:
        summary_fn = getattr(getattr(self.kernel, "taint", None), "summary", None)
        if callable(summary_fn):
            try:
                return str(summary_fn() or "")
            except Exception:  # noqa: BLE001
                return ""
        return ""

    # ── filesystem / mount tables ───────────────────────────────────

    def filesystems(self) -> List[tuple]:
        return [
            ("nodev", "proc"), ("nodev", "sysfs"), ("nodev", "tmpfs"),
            ("nodev", "devpts"), ("nodev", "devtmpfs"),
            ("", "qfs"), ("", "ext4"), ("", "iso9660"),
        ]

    def mounts(self) -> List[Dict[str, str]]:
        part = self.partition()
        root_dev = part["name"] if part else "qfs_root"
        return [
            {"device": root_dev, "mountpoint": "/", "fstype": "qfs",
             "opts": "rw,relatime,quantum"},
            {"device": "proc", "mountpoint": "/proc", "fstype": "proc",
             "opts": "rw,nosuid,nodev,noexec,relatime"},
            {"device": "sysfs", "mountpoint": "/sys", "fstype": "sysfs",
             "opts": "rw,nosuid,nodev,noexec,relatime"},
            {"device": "devtmpfs", "mountpoint": "/dev", "fstype": "devtmpfs",
             "opts": "rw,nosuid,size=2097152k,nr_inodes=524288,mode=755"},
            {"device": "tmpfs", "mountpoint": "/run", "fstype": "tmpfs",
             "opts": "rw,nosuid,nodev,mode=755"},
            {"device": "tmpfs", "mountpoint": "/tmp", "fstype": "tmpfs",
             "opts": "rw,nosuid,nodev"},
        ]

    # ── networking (simulated unless a NetworkStack is attached) ────

    def net_interfaces(self) -> List[Dict[str, Any]]:
        uptime = max(self.uptime(), 1.0)
        base_rx, base_tx = int(uptime * 842), int(uptime * 517)
        interfaces = [
            {"name": "lo", "rx_bytes": base_rx * 6, "rx_packets": int(uptime * 12),
             "rx_errs": 0, "rx_drop": 0, "rx_fifo": 0, "rx_frame": 0,
             "tx_bytes": base_tx * 6, "tx_packets": int(uptime * 12),
             "tx_errs": 0, "tx_drop": 0, "tx_fifo": 0, "tx_colls": 0,
             "tx_carrier": 0},
            {"name": "quantum0", "rx_bytes": base_rx * 420,
             "rx_packets": int(uptime * 96), "rx_errs": 0, "rx_drop": 0,
             "rx_fifo": 0, "rx_frame": 0, "tx_bytes": base_tx * 380,
             "tx_packets": int(uptime * 88), "tx_errs": 0, "tx_drop": 0,
             "tx_fifo": 0, "tx_colls": 0, "tx_carrier": 0},
        ]
        if self.network_stack is not None:
            try:
                extra = self.network_stack.status()
                if extra.get("running"):
                    interfaces[1]["state"] = "up"
            except Exception:  # noqa: BLE001
                pass
        return interfaces

    def net_connections(self) -> List[Dict[str, Any]]:
        table_fn = getattr(self.network_stack, "connection_table", None)
        if callable(table_fn):
            try:
                return [dict(row) for row in table_fn()]
            except Exception:  # noqa: BLE001
                return []
        return []

    # ── devices / modules ───────────────────────────────────────────

    def char_devices(self) -> List[tuple]:
        return [
            (1, 3, "null"), (1, 5, "zero"), (1, 7, "full"),
            (1, 8, "random"), (1, 9, "urandom"),
            (5, 1, "console"), (5, 2, "ptmx"), (10, 229, "fuse"),
            (250, 0, "qcrypto"), (251, 0, "qtimer"),
        ]

    def block_devices(self) -> List[tuple]:
        part = self.partition()
        name = part["name"] if part else "qfs_root"
        return [(7, 0, "loop"), (254, 0, name), (254, 16, "qswap")]

    def modules(self) -> List[Dict[str, Any]]:
        return [
            {"name": "umer_net", "size": 61440, "use_count": 3,
             "deps": "", "state": "Live"},
            {"name": "qcrypto", "size": 36864, "use_count": 1,
             "deps": "", "state": "Live"},
            {"name": "qfs", "size": 131072, "use_count": 2,
             "deps": "qcrypto", "state": "Live"},
            {"name": "procfs", "size": 16384, "use_count": 1,
             "deps": "", "state": "Live"},
        ]

    def close(self) -> None:
        try:
            _ROOT_LOGGER.removeHandler(self.kmsg)
        except Exception:  # noqa: BLE001
            pass
