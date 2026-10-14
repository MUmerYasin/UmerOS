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

""" tests — ``panic()`` must be able to taint the kernel.

The standard flagged ``kernel/umer_kernel.py``'s ``panic()`` calling
``self.taint.add("TAINT_KERNEL_PANIC")`` — a string that was **not** registered
in ``KernelTaint._FLAG_INDEX``.  Since ``KernelTaint.add`` raises ``ValueError``
on unknown flags, the fatal-error handler **crashed on itself** before it could
reboot or hang.

 registers a real ``TAINT_KERNEL_PANIC`` flag in ``kernel/taint.py`` and
makes ``panic()`` reference the imported constant instead of a bare literal
(the three unrelated taint constants that were imported but never used are
dropped, and ``kernel/__init__.py``'s stale taint re-export — which named three
non-existent symbols — now names the real public surface).
"""

import asyncio
import contextlib
import io
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

KERNEL_SRC = ROOT / "kernel" / "umer_kernel.py"
TAINT_SRC = ROOT / "kernel" / "taint.py"
INIT_SRC = ROOT / "kernel" / "__init__.py"

# The eight flags that existed before H127, with their (monotonic) bit values.
LEGACY_FLAGS = {
    "TAINT_PROPRIETARY": 1 << 0,
    "TAINT_UNSIGNED_MODULE": 1 << 1,
    "TAINT_BAD_PAGE": 1 << 2,
    "TAINT_OOM_KILL": 1 << 3,
    "TAINT_CRYPTO_FAIL": 1 << 4,
    "TAINT_SANDBOX_VIOLATION": 1 << 5,
    "TAINT_IPC_TAMPER": 1 << 6,
    "TAINT_HUNG_TASK": 1 << 7,
}


class TestTaintFlagRegistered(unittest.TestCase):
    """``TAINT_KERNEL_PANIC`` is a first-class, registered taint flag."""

    def test_constant_defined(self):
        from kernel import taint

        self.assertTrue(hasattr(taint, "TAINT_KERNEL_PANIC"))
        self.assertEqual(taint.TAINT_KERNEL_PANIC, "TAINT_KERNEL_PANIC")

    def test_registered_in_flag_index(self):
        from kernel.taint import TAINT_KERNEL_PANIC, _FLAG_INDEX, _FLAGS

        self.assertIn(TAINT_KERNEL_PANIC, _FLAG_INDEX)
        self.assertIn(TAINT_KERNEL_PANIC, _FLAGS)

    def test_flag_count_is_nine(self):
        from kernel.taint import _FLAGS

        self.assertEqual(len(_FLAGS), 9)

    def test_appended_monotonically(self):
        """The new flag is appended — legacy bit positions must not shift."""
        from kernel.taint import TAINT_KERNEL_PANIC, _FLAG_INDEX

        for name, bit in LEGACY_FLAGS.items():
            self.assertEqual(_FLAG_INDEX[name], bit, f"{name} bit shifted")
        self.assertEqual(_FLAG_INDEX[TAINT_KERNEL_PANIC], 1 << 8)

    def test_bit_is_unique_power_of_two(self):
        from kernel.taint import TAINT_KERNEL_PANIC, _FLAG_INDEX

        bits = list(_FLAG_INDEX.values())
        self.assertEqual(len(bits), len(set(bits)), "duplicate bit positions")
        bit = _FLAG_INDEX[TAINT_KERNEL_PANIC]
        self.assertTrue(bit > 0 and (bit & (bit - 1)) == 0, "not a power of two")

    def test_add_does_not_raise_and_summary(self):
        from kernel.taint import KernelTaint, TAINT_KERNEL_PANIC

        t = KernelTaint()
        t.add(TAINT_KERNEL_PANIC)  # must NOT raise ValueError
        self.assertTrue(t.has(TAINT_KERNEL_PANIC))
        self.assertTrue(t.is_tainted())
        self.assertEqual(t.summary(), "KERNEL_PANIC")

    def test_add_is_idempotent(self):
        from kernel.taint import KernelTaint, TAINT_KERNEL_PANIC

        t = KernelTaint()
        t.add(TAINT_KERNEL_PANIC)
        t.add(TAINT_KERNEL_PANIC)
        self.assertEqual(t.summary(), "KERNEL_PANIC")
        self.assertEqual(t.mask, 1 << 8)


class TestFailLoudPreserved(unittest.TestCase):
    """Registering the panic flag must not soften the unknown-flag contract."""

    def test_unknown_flag_still_raises(self):
        from kernel.taint import KernelTaint

        with self.assertRaises(ValueError):
            KernelTaint().add("TAINT_DOES_NOT_EXIST")

    def test_has_unknown_flag_is_false(self):
        from kernel.taint import KernelTaint

        self.assertFalse(KernelTaint().has("TAINT_DOES_NOT_EXIST"))


class TestPanicTaintsKernel(unittest.TestCase):
    """End-to-end: ``panic()`` runs to completion and taints the kernel."""

    def _run_panic(self):
        from kernel.umer_kernel import UmerKernel

        kernel = UmerKernel()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            asyncio.run(kernel.panic("h127 unit-test panic"))
        return kernel, buf.getvalue()

    def test_panic_does_not_crash_on_itself(self):
        kernel, _ = self._run_panic()  # would raise ValueError before H127
        self.assertIsNotNone(kernel)

    def test_panic_taints_the_kernel(self):
        from kernel.taint import TAINT_KERNEL_PANIC

        kernel, _ = self._run_panic()
        self.assertTrue(
            kernel.taint.has(TAINT_KERNEL_PANIC),
            "panic() did not set TAINT_KERNEL_PANIC",
        )

    def test_panic_halts_the_kernel(self):
        kernel, _ = self._run_panic()
        self.assertFalse(kernel.running)
        self.assertTrue(getattr(kernel, "_shutdown_requested", True))


class TestSourceInvariants(unittest.TestCase):
    """Pin *code facts*, never the cosmetic ``[FIX Hxxx]`` tag."""

    def test_panic_uses_constant_not_literal(self):
        src = KERNEL_SRC.read_text(encoding="utf-8")
        self.assertNotIn(
            'self.taint.add("TAINT_KERNEL_PANIC")', src,
            "panic() still uses the bare string literal",
        )
        self.assertIn("self.taint.add(TAINT_KERNEL_PANIC)", src)

    def test_kernel_imports_the_constant(self):
        src = KERNEL_SRC.read_text(encoding="utf-8")
        self.assertRegex(
            src,
            r"from kernel\.taint import [^\n]*\bTAINT_KERNEL_PANIC\b",
        )

    def test_dead_taint_imports_removed(self):
        """The three imported-but-unused taint constants are gone."""
        src = KERNEL_SRC.read_text(encoding="utf-8")
        m = re.search(r"from kernel\.taint import ([^\n]*)", src)
        self.assertIsNotNone(m)
        imported = m.group(1)
        for dead in ("TAINT_OOM_KILL", "TAINT_CRYPTO_FAIL", "TAINT_SANDBOX_VIOLATION"):
            self.assertNotIn(dead, imported, f"{dead} still imported but unused")

    def test_init_reexport_names_real_symbols(self):
        src = INIT_SRC.read_text(encoding="utf-8")
        self.assertNotIn('("taint", ("TaintFlag", "TaintFlags", "TaintReason"))', src)
        self.assertIn('("taint", ("KernelTaint", "TAINT_KERNEL_PANIC"))', src)

    def test_flag_defined_and_registered_in_source(self):
        src = TAINT_SRC.read_text(encoding="utf-8")
        self.assertIn('TAINT_KERNEL_PANIC:  str = "TAINT_KERNEL_PANIC"', src)
        self.assertIn("    TAINT_KERNEL_PANIC,\n]", src)


class TestPackageReexport(unittest.TestCase):
    """``kernel/__init__.py`` now re-exports the real taint surface."""

    def test_kernel_exposes_kernel_taint(self):
        import kernel

        self.assertTrue(hasattr(kernel, "KernelTaint"))

    def test_kernel_exposes_panic_flag(self):
        import kernel

        self.assertTrue(hasattr(kernel, "TAINT_KERNEL_PANIC"))
        self.assertEqual(kernel.TAINT_KERNEL_PANIC, "TAINT_KERNEL_PANIC")

    def test_stale_names_not_exported(self):
        import kernel

        for stale in ("TaintFlag", "TaintFlags", "TaintReason"):
            self.assertFalse(hasattr(kernel, stale), f"{stale} should not exist")


if __name__ == "__main__":
    unittest.main(verbosity=2)
