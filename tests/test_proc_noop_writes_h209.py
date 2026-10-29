"""H209 — silent no-op writes behind rw mode in proc/sysctl_fs.py.

Several /proc/sys/kernel/* entries (ctrl-alt-del, acct, printk, sem,
auto_msgmni, randomize_va_space) and /proc/parport/0/irq carried
``write=lambda text: None`` — the write "succeeded" and did nothing,
a contract mismatch with the sysctl_fs docstring ("Writes are validated
and persisted").  The fix removes the no-op write handlers so
``ProcFile._write`` is ``None`` and ``ProcFile.write()`` raises
``PermissionError`` — the honest behaviour for entries with no backing
store.

This test pins the invariant: those entries are now read-only (write
raises), and a grep for ``write=lambda text: None`` finds nothing in
either file.
"""
from __future__ import annotations

import pathlib
import unittest

# ── helpers ────────────────────────────────────────────────────────────

REPO = pathlib.Path(__file__).resolve().parent.parent
SYSCTL_FS = (REPO / "proc" / "sysctl_fs.py").read_text(encoding="utf-8")
SYSTEM_FILES = (REPO / "proc" / "system_files.py").read_text(encoding="utf-8")

# Entries that previously had write=lambda text: None — now read-only.
NO_OP_ENTRIES = [
    ("sysctl_fs.py", "ctrl-alt-del"),
    ("sysctl_fs.py", "acct"),
    ("sysctl_fs.py", "printk"),
    ("sysctl_fs.py", "sem"),
    ("sysctl_fs.py", "auto_msgmni"),
    ("sysctl_fs.py", "randomize_va_space"),
]
# parport/0/irq in system_files.py
PARPORT_IRQ = "parport"


class TestNoOpWritesRemoved(unittest.TestCase):
    """Verify no ``write=lambda text: None`` remains in the proc modules."""

    def test_sysctl_fs_no_noop_writes(self):
        """sysctl_fs.py must not contain write=lambda text: None."""
        self.assertNotIn(
            "write=lambda text: None", SYSCTL_FS,
            "sysctl_fs.py still has a silent no-op write handler")

    def test_system_files_no_noop_writes(self):
        """system_files.py must not contain write=lambda text: None."""
        self.assertNotIn(
            "write=lambda text: None", SYSTEM_FILES,
            "system_files.py still has a silent no-op write handler")

    def test_noop_entries_are_readonly(self):
        """Each formerly no-op entry must not have a write= kwarg."""
        for fname, entry in NO_OP_ENTRIES:
            src = SYSCTL_FS if fname == "sysctl_fs.py" else SYSTEM_FILES
            # Find the ProcFile line for this entry
            self.assertIn(f'"{entry}"', src,
                          f"{fname}: entry {entry!r} not found")
            # The entry must NOT have write=lambda
            # Find the line(s) containing the entry name
            lines = src.splitlines()
            entry_lines = [i for i, l in enumerate(lines)
                           if f'"{entry}"' in l and "ProcFile" in l]
            self.assertGreater(len(entry_lines), 0,
                               f"{fname}: no ProcFile line for {entry!r}")
            for lineno in entry_lines:
                # Check the next 2 lines for write= (multiline call)
                window = "\n".join(lines[lineno:lineno + 3])
                self.assertNotIn("write=lambda", window,
                                 f"{fname}:{lineno+1}: {entry!r} still has "
                                 f"a write= handler")


class TestParportIrqReadonly(unittest.TestCase):
    """parport/0/irq previously had write=lambda text: None."""

    def test_parport_irq_no_write_handler(self):
        """The parport irq ProcFile must not have a write handler."""
        lines = SYSTEM_FILES.splitlines()
        irq_lines = [i for i, l in enumerate(lines)
                     if "ProcFile" in l and '"irq"' in l]
        self.assertGreater(len(irq_lines), 0,
                           "system_files.py: parport irq ProcFile not found")
        for lineno in irq_lines:
            window = "\n".join(lines[lineno:lineno + 3])
            self.assertNotIn("write=lambda", window,
                             f"system_files.py:{lineno+1}: parport irq still "
                             f"has a write= handler")
            self.assertNotIn("mode=\"rw", window,
                             f"system_files.py:{lineno+1}: parport irq still "
                             f"advertises rw mode")


class TestProcFileWriteRejects(unittest.TestCase):
    """Verify ProcFile.write() raises PermissionError when _write is None."""

    def test_readonly_procfile_raises(self):
        """A ProcFile without a write handler must reject writes."""
        from proc.nodes import ProcFile
        f = ProcFile("test", read=lambda: "data\n")
        self.assertFalse(f.writable)
        with self.assertRaises(PermissionError):
            f.write("bogus")

    def test_writable_procfile_accepts(self):
        """A ProcFile with a real write handler must accept writes."""
        from proc.nodes import ProcFile
        sink = []
        f = ProcFile("test", read=lambda: "data\n",
                     write=lambda text: sink.append(text))
        self.assertTrue(f.writable)
        f.write("value")
        self.assertEqual(sink, ["value"])


if __name__ == "__main__":
    unittest.main()
