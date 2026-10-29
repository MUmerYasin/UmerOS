"""H211 — fabricated capability mask + fake environ in pid_entries.py.

The row flagged two issues in ``proc/pid_entries.py``:

1. **Fabricated CapEff:** ``status`` hardcodes ``CapEff: 0000003fffffffff``
   (full caps) when ``uid==0`` — a fabricated mask that misrepresents
   process state and can mislead auditors reading ``/proc/<pid>/status``.

2. **Fake environ:** ``environ`` is a fully hardcoded dict, not the real
   process environment.

The remedy (per the row): "Clearly label ``CapEff``/``environ`` as
simulated, or derive from real adapter state when available."

Since UmerOS is a simulator and the kernel adapter does not track real
per-process capabilities or environments, the fix labels both as
simulated:

* ``environ`` now includes ``UMEROS_SIMULATED=1`` so tooling reading
  ``/proc/<pid>/environ`` can detect the simulation.
* ``status`` now includes a ``Note:`` line after ``CapAmb`` stating that
  ``CapEff``/``CapPrm``/``CapBnd`` are simulated.
* Code comments explain the simulation rationale.
"""
from __future__ import annotations

import pathlib
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
PID_ENTRIES = (REPO / "proc" / "pid_entries.py").read_text(encoding="utf-8")


# ── Mock kernel (mirrors tests/test_proc.py) ──────────────────────────

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
            1001: _MockTask(1001, "shell", "READY", 0.8, 2.0),
        })
        self.memory = _MockMemory()
        self._boot_time = 0.0
        self._LOSTFOUND_AVAILABLE = False


# ── Source-level invariants ───────────────────────────────────────────

class TestEnvironLabeledSimulated(unittest.TestCase):
    """The environ dict must carry UMEROS_SIMULATED=1."""

    def test_environ_has_simulated_flag(self):
        self.assertIn("UMEROS_SIMULATED", PID_ENTRIES)

    def test_environ_simulated_flag_value(self):
        self.assertIn('"UMEROS_SIMULATED": "1"', PID_ENTRIES)

    def test_environ_has_simulated_comment(self):
        self.assertIn("Simulated", PID_ENTRIES)


class TestCapEffLabeledSimulated(unittest.TestCase):
    """The status block must label CapEff as simulated."""

    def test_status_has_simulated_note(self):
        self.assertIn("simulated", PID_ENTRIES)

    def test_status_note_after_capamb(self):
        lines = PID_ENTRIES.splitlines()
        capamb_line = None
        note_line = None
        for i, line in enumerate(lines):
            if "CapAmb" in line and "ProcFile" not in line:
                capamb_line = i
            if "Note:" in line and "simulated" in line:
                note_line = i
        self.assertIsNotNone(capamb_line)
        self.assertIsNotNone(note_line)
        self.assertGreater(note_line, capamb_line)

    def test_cap_eff_uses_variable(self):
        self.assertIn("cap_eff", PID_ENTRIES)
        lines = PID_ENTRIES.splitlines()
        for line in lines:
            if "CapEff:" in line and "ProcFile" not in line:
                self.assertNotIn("if uid == 0", line)
                self.assertIn("cap_eff", line)
                return
        self.fail("CapEff line not found")


# ── End-to-end with mock kernel ───────────────────────────────────────

class TestEnvironContent(unittest.TestCase):
    """Verify the simulated environ still has the expected keys."""

    def setUp(self):
        from proc.kernel_adapter import KernelAdapter
        from proc.procfs import ProcFileSystem
        self.kernel = _MockKernel()
        self.adapter = KernelAdapter(kernel=self.kernel)
        self.fs = ProcFileSystem(self.adapter)

    def test_environ_has_home(self):
        data = self.fs.read("/proc/1000/environ")
        self.assertIn("HOME=/home/umer", data)

    def test_environ_has_path(self):
        data = self.fs.read("/proc/1000/environ")
        self.assertIn("PATH=/usr/local/sbin", data)

    def test_environ_has_simulated_flag(self):
        data = self.fs.read("/proc/1000/environ")
        self.assertIn("UMEROS_SIMULATED=1", data)


class TestStatusContent(unittest.TestCase):
    """Verify the status block has the simulated label."""

    def setUp(self):
        from proc.kernel_adapter import KernelAdapter
        from proc.procfs import ProcFileSystem
        self.kernel = _MockKernel()
        self.adapter = KernelAdapter(kernel=self.kernel)
        self.fs = ProcFileSystem(self.adapter)

    def test_status_has_cap_eff(self):
        data = self.fs.read("/proc/1000/status")
        self.assertIn("CapEff:", data)

    def test_status_has_simulated_note(self):
        data = self.fs.read("/proc/1000/status")
        self.assertIn("simulated", data)
        self.assertIn("Note:", data)

    def test_status_has_basic_fields(self):
        data = self.fs.read("/proc/1000/status")
        self.assertIn("Name:", data)
        self.assertIn("Pid:\t1000", data)
        self.assertIn("VmSize:", data)


if __name__ == "__main__":
    unittest.main()
