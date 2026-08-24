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
pytest suite proving the zero-trust capability gate is wired into the
privileged /proc write paths and the destructive /srv tree removal
(cap-gate cluster: H205, H206, H207, H208, H268).

Proves, per wired module:
  * A write/delete performed by a process that LACKS the required capability
    raises PermissionError (fail-closed when a real CapabilityManager is wired).
  * The same operation SUCCEEDS once the capability is granted (allow-when-held).
  * Reads remain unaffected (only mutations are gated).

Mirror of tests/test_cap_gate.py: a real kernel CapabilityManager is wired
into a fresh CapabilityGate, and the module-level ``gate`` name is patched
for the duration of each test, then restored.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from core.capability_gate import (  # noqa: E402
    CAP_FS_ADMIN,
    CAP_SYS_ADMIN,
    CapabilityGate,
)
from kernel.capability_manager import CapabilityManager  # noqa: E402

from proc.kernel_adapter import KernelAdapter  # noqa: E402
from proc.procfs import ProcFileSystem  # noqa: E402
from srv.hierarchy import SrvHierarchy  # noqa: E402


def _make_wired_gate(pid: int, caps) -> CapabilityGate:
    """Build a gate wired to a real CapabilityManager that grants `caps` to `pid`."""
    cm = CapabilityManager()
    cm.register(pid)
    for c in caps:
        cm.grant(pid, c)
    g = CapabilityGate()
    g.wire(cm)
    return g


# ── minimal mock kernel (so PID dirs + oom_score_adj exist) ──────────────────

class _MockTask:
    def __init__(self, pid, name, state="READY", priority=0.5, cpu_time=1.0):
        self.pid = pid
        self.name = name
        self.state = state
        self.priority = priority
        self.cpu_time = cpu_time
        self.parent_pid = None


class _MockScheduler:
    def __init__(self, tasks):
        self._tasks = tasks


class _MockMemory:
    PAGE_SIZE = 4096

    def stats(self):
        return {"total_pages": 1048576, "free_pages": 524288,
                "page_size": 4096, "live_allocations": 3}


class _MockKernel:
    def __init__(self):
        self.scheduler = _MockScheduler({
            1000: _MockTask(1000, "init", "RUNNING", 1.0, 5.0),
        })
        self.memory = _MockMemory()
        self._boot_time = 0.0
        self._LOSTFOUND_AVAILABLE = False


# ── H205 — ProcFileSystem.write chokepoint ───────────────────────────────────

def test_procfs_write_denied_without_cap():
    import proc.procfs as mod
    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[])
    try:
        fs = ProcFileSystem(KernelAdapter(_MockKernel()))
        with pytest.raises(PermissionError):
            fs.write("/proc/sys/kernel/hostname", "evil")
    finally:
        mod.gate = prev


def test_procfs_write_allowed_with_cap():
    import proc.procfs as mod
    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[CAP_SYS_ADMIN])
    try:
        fs = ProcFileSystem(KernelAdapter(_MockKernel()))
        fs.write("/proc/sys/kernel/hostname", "newhost")
        assert fs.read("/proc/sys/kernel/hostname").strip() == "newhost"
    finally:
        mod.gate = prev


def test_procfs_read_not_gated():
    """Reads must keep working even when writes are denied."""
    import proc.procfs as mod
    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[])
    try:
        fs = ProcFileSystem(KernelAdapter(_MockKernel()))
        assert "MemTotal" in fs.read("/proc/meminfo")  # read unaffected
    finally:
        mod.gate = prev


# ── H206 — /proc/sys/* tunables ─────────────────────────────────────────────

def test_sysctl_write_denied_without_cap():
    import proc.sysctl_fs as mod
    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[])
    try:
        fs = ProcFileSystem(KernelAdapter(_MockKernel()))
        with pytest.raises(PermissionError):
            fs.write("/proc/sys/fs/file-max", "65536")
    finally:
        mod.gate = prev


def test_sysctl_write_allowed_with_cap():
    import proc.sysctl_fs as mod
    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[CAP_SYS_ADMIN])
    try:
        fs = ProcFileSystem(KernelAdapter(_MockKernel()))
        # The standalone sysctl registry ships with no registered keys, so a
        # _rfile write would otherwise KeyError on set(). Register the param
        # (mirrors how the real kernel seeds the registry) to exercise the
        # gated mutation end-to-end.
        fs.adapter.sysctl_registry().register(
            "fs.file_max", 0, ptype="int", min_val=0, max_val=10 ** 9)
        fs.write("/proc/sys/fs/file-max", "65536")
        assert fs.read("/proc/sys/fs/file-max").strip() == "65536"
    finally:
        mod.gate = prev


# ── H207 — per-PID oom_score_adj ────────────────────────────────────────────

def test_oom_score_adj_denied_without_cap():
    import proc.pid_entries as mod
    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[])
    try:
        fs = ProcFileSystem(KernelAdapter(_MockKernel()))
        with pytest.raises(PermissionError):
            fs.write("/proc/1000/oom_score_adj", "500")
    finally:
        mod.gate = prev


def test_oom_score_adj_allowed_with_cap():
    import proc.pid_entries as mod
    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[CAP_SYS_ADMIN])
    try:
        fs = ProcFileSystem(KernelAdapter(_MockKernel()))
        fs.write("/proc/1000/oom_score_adj", "500")
        assert fs.read("/proc/1000/oom_score_adj").strip() == "500"
    finally:
        mod.gate = prev


# ── H208 — /proc/irq/<n>/smp_affinity ──────────────────────────────────────

def test_smp_affinity_denied_without_cap():
    import proc.system_files as mod
    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[])
    try:
        fs = ProcFileSystem(KernelAdapter(_MockKernel()))
        with pytest.raises(PermissionError):
            fs.write("/proc/irq/0/smp_affinity", "1")
    finally:
        mod.gate = prev


def test_smp_affinity_allowed_with_cap():
    import proc.system_files as mod
    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[CAP_SYS_ADMIN])
    try:
        fs = ProcFileSystem(KernelAdapter(_MockKernel()))
        fs.write("/proc/irq/0/smp_affinity", "1")
        assert fs.read("/proc/irq/0/smp_affinity").strip() == "1"
    finally:
        mod.gate = prev


# ── H268 — destructive /srv service-tree removal ────────────────────────────

def test_srv_hierarchy_delete_denied_without_cap():
    import srv.hierarchy as mod
    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[])
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "srv"
            svc = root / "web"
            svc.mkdir(parents=True)
            mgr = SrvHierarchy(srv_root=root)
            with pytest.raises(PermissionError):
                mgr.delete_service_tree("web", force=True)
            assert svc.exists()  # nothing deleted
    finally:
        mod.gate = prev


def test_srv_hierarchy_delete_allowed_with_cap():
    import srv.hierarchy as mod
    prev = mod.gate
    mod.gate = _make_wired_gate(os.getpid(), caps=[CAP_FS_ADMIN])
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "srv"
            svc = root / "web"
            svc.mkdir(parents=True)
            mgr = SrvHierarchy(srv_root=root)
            assert mgr.delete_service_tree("web", force=True) is True
            assert not svc.exists()  # removed
    finally:
        mod.gate = prev
