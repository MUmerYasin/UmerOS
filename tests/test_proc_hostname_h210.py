"""H210 — hostname/domainname trailing-newline + docstring mismatch.

The row flagged two issues in ``proc/sysctl_fs.py``:

1. **Trailing-newline persisted:** ``write=lambda text: setattr(adapter,
   "hostname", text.strip() + "\\n")`` stored the value WITH a trailing
   newline, so reads (which also append ``"\\n"``) returned a double
   newline after a write — ``"newhost\\n\\n"`` instead of ``"newhost\\n"``.

2. **Docstring/impl mismatch:** the module docstring claimed "Writes are
   validated and persisted by the kernel's ``SysctlRegistry``", but
   hostname/domainname bypass the registry entirely (they are dynamic
   ``KernelAdapter`` attributes).

The fix removes the trailing ``"\\n"`` from the stored value (reads still
append it for procfs convention) and documents the bypass in the module
docstring.
"""
from __future__ import annotations

import pathlib
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
SYSCTL_FS = (REPO / "proc" / "sysctl_fs.py").read_text(encoding="utf-8")


class TestNoTrailingNewlineStored(unittest.TestCase):
    """The write handler must store stripped values (no trailing \\n)."""

    def test_hostname_write_no_trailing_newline(self):
        """hostname write handler must not append \\n to the stored value."""
        # The old code was: text.strip() + "\\n"
        # The new code is:  text.strip()
        self.assertNotIn(
            'text.strip() + "\\n"', SYSCTL_FS,
            "sysctl_fs.py still appends a trailing newline to a stored value")

    def test_hostname_write_stores_stripped(self):
        """The hostname write must use text.strip() without + \\n."""
        lines = SYSCTL_FS.splitlines()
        hostname_write_lines = [
            i for i, l in enumerate(lines)
            if "hostname" in l and "setattr" in l
        ]
        # Also check the continuation line
        found_stripped = False
        for i, l in enumerate(lines):
            if 'setattr(adapter, "hostname"' in l:
                window = "\n".join(lines[i:i + 3])
                self.assertIn("text.strip()", window)
                self.assertNotIn('text.strip() + "\\n"', window)
                found_stripped = True
        self.assertTrue(found_stripped,
                        "hostname setattr write handler not found")

    def test_domainname_write_stores_stripped(self):
        """The domainname write must use text.strip() without + \\n."""
        lines = SYSCTL_FS.splitlines()
        for i, l in enumerate(lines):
            if 'setattr(adapter, "_domainname"' in l:
                window = "\n".join(lines[i:i + 3])
                self.assertIn("text.strip()", window)
                self.assertNotIn('text.strip() + "\\n"', window)
                return
        self.fail("domainname setattr write handler not found")


class TestDocstringDocumentsBypass(unittest.TestCase):
    """The module docstring must acknowledge the hostname/domainname bypass."""

    def test_docstring_mentions_adapter_attributes(self):
        """Docstring must mention that hostname/domainname are adapter attrs."""
        self.assertIn(
            "KernelAdapter", SYSCTL_FS,
            "sysctl_fs.py docstring must mention KernelAdapter for the "
            "hostname/domainname bypass")

    def test_docstring_mentions_hostname_exception(self):
        """Docstring must mention hostname as an exception to the registry rule."""
        # Check the docstring region (first ~40 lines)
        docstring_region = "\n".join(SYSCTL_FS.splitlines()[:40])
        self.assertIn(
            "hostname", docstring_region,
            "sysctl_fs.py docstring must mention hostname as an exception")


class TestWriteReadRoundTrip(unittest.TestCase):
    """End-to-end: write hostname, read it back — no double newline."""

    def setUp(self):
        from proc.kernel_adapter import KernelAdapter
        from proc.procfs import ProcFileSystem

        class _MockKernel:
            sysctl = None
        self.adapter = KernelAdapter(kernel=_MockKernel())
        self.fs = ProcFileSystem(self.adapter)

    def test_hostname_write_then_read(self):
        """Writing 'newhost' then reading must return 'newhost\\n' (not 'newhost\\n\\n')."""
        self.fs.write("/proc/sys/kernel/hostname", "newhost")
        data = self.fs.read("/proc/sys/kernel/hostname")
        self.assertEqual(data, "newhost\n",
                         "read after write must be 'newhost\\n', not "
                         f"{data!r}")

    def test_hostname_write_strips_input_newline(self):
        """Writing 'myhost\\n' must store 'myhost' (stripped)."""
        self.fs.write("/proc/sys/kernel/hostname", "myhost\n")
        self.assertEqual(self.adapter.hostname, "myhost",
                         "stored hostname must be stripped (no trailing \\n)")
        data = self.fs.read("/proc/sys/kernel/hostname")
        self.assertEqual(data, "myhost\n")

    def test_domainname_write_then_read(self):
        """Writing domainname then reading must return value + single \\n."""
        self.fs.write("/proc/sys/kernel/domainname", "example.com")
        data = self.fs.read("/proc/sys/kernel/domainname")
        self.assertEqual(data, "example.com\n",
                         f"read after write must be 'example.com\\n', not "
                         f"{data!r}")

    def test_domainname_default(self):
        """Default domainname (never written) must return '(none)\\n'."""
        data = self.fs.read("/proc/sys/kernel/domainname")
        self.assertEqual(data, "(none)\n")

    def test_hostname_default(self):
        """Default hostname must be 'umeros-node1\\n'."""
        data = self.fs.read("/proc/sys/kernel/hostname")
        self.assertEqual(data, "umeros-node1\n")


if __name__ == "__main__":
    unittest.main()
