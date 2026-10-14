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

"""tests — no hard dependency on the phantom ``umer_kernel1.py``.

The standard claimed ``kernel/umer_kernel.py`` had a hard dependency on a
``umer_kernel1.py`` module ("the enhanced one") that is not in ``kernel/``, so
``UmerKernel.__init__`` would raise if it were missing.

Drift-recon proved the premise STALE: there is **no** live import of
``umer_kernel1``; the enhanced ``AIResourceManager`` / ``QuantumScheduler``
classes were already **inlined** in the module, and a ~718-line fully
commented-out duplicate of the whole module (an earlier "umer_kernel1"
snapshot) was accumulating at the tail. removed that dead block and the
misleading comments that implied a live dependency.
"""

import io
import contextlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SRC_PATH = ROOT / "kernel" / "umer_kernel.py"


def _read_src() -> str:
    return SRC_PATH.read_text(encoding="utf-8")


class TestNoPhantomDependency(unittest.TestCase):
    """The module must not (and does not) depend on ``umer_kernel1.py``."""

    def test_phantom_module_does_not_exist(self):
        # Exclude the reference-only legacy tree.
        hits = [
            p
            for p in ROOT.rglob("umer_kernel1*")
            if "Old Linux Code" not in p.parts
        ]
        self.assertEqual(hits, [], f"phantom module unexpectedly present: {hits}")

    def test_no_live_import_of_phantom_module(self):
        src = _read_src()
        self.assertNotIn("import umer_kernel1", src)
        self.assertNotIn("from umer_kernel1 import", src)

    def test_no_misleading_from_umer_kernel1_phrasing(self):
        # The old comments said "from umer_kernel1.py" / "from umer_kernel1.py)".
        src = _read_src()
        self.assertNotIn("from umer_kernel1.py", src)

    def test_no_live_umer_kernel1_reference_outside_explanatory_notes(self):
        # Any remaining mention must be inside the explicit "no dependency"
        # explanation (docstring note or the [FIX H120] tail note).
        for i, line in enumerate(_read_src().splitlines(), 1):
            if "umer_kernel1" not in line:
                continue
            self.assertTrue(
                "no dependency" in line
                or "does not ship" in line
                or "scratch file was merged" in line
                or "snapshot" in line,
                f"L{i} still carries an unexplained umer_kernel1 reference: {line!r}",
            )


class TestInlinedClassesPresent(unittest.TestCase):
    """The enhanced classes are inlined (not imported)."""

    def test_ai_resource_manager_defined_with_prediction(self):
        import kernel.umer_kernel as uk

        self.assertTrue(hasattr(uk, "AIResourceManager"))
        self.assertTrue(hasattr(uk.AIResourceManager, "predict_allocation"))
        # Prediction logic is real (returns a per-task allocation map).
        mgr = uk.AIResourceManager()
        alloc = mgr.predict_allocation(["a", "b"])
        self.assertEqual(set(alloc), {"a", "b"})
        self.assertTrue(all(isinstance(v, float) for v in alloc.values()))

    def test_quantum_scheduler_defined_with_superposition(self):
        import kernel.umer_kernel as uk

        self.assertTrue(hasattr(uk, "QuantumScheduler"))
        self.assertTrue(hasattr(uk.QuantumScheduler, "execute_superposition"))

    def test_source_marks_components_as_inlined(self):
        src = _read_src()
        self.assertIn("MERGED COMPONENT (inlined): Enhanced AIResourceManager", src)
        self.assertIn("MERGED COMPONENT (inlined): Enhanced QuantumScheduler", src)


class TestKernelConstructs(unittest.TestCase):
    """``UmerKernel.__init__`` works without any phantom module."""

    def test_umer_kernel_constructs_and_uses_inlined_classes(self):
        with contextlib.redirect_stdout(io.StringIO()):
            import kernel.umer_kernel as uk

            k = uk.UmerKernel()
        self.assertIsInstance(k.ai_manager, uk.AIResourceManager)
        self.assertIsInstance(k.q_scheduler, uk.QuantumScheduler)

    def test_init_references_inlined_classes(self):
        src = _read_src()
        self.assertIn("self.ai_manager = AIResourceManager(", src)
        self.assertIn("self.q_scheduler = QuantumScheduler()", src)


class TestDeadDuplicateRemoved(unittest.TestCase):
    """The ~718-line commented-out duplicate at the tail is gone."""

    def test_no_dead_duplicate_markers(self):
        src = _read_src()
        # Signatures of the removed commented-out copy of the module.
        self.assertNotIn("# import sys", src)
        self.assertNotIn("# # --- MERGED COMPONENT", src)
        self.assertNotIn("# class UmerKernel:", src)
        self.assertNotIn("#     async def boot(self", src)

    def test_no_long_dead_comment_run(self):
        # No contiguous run of >= 100 comment/blank lines should remain
        # (the removed block was 718 lines).
        longest = run = 0
        for line in _read_src().splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                run += 1
                longest = max(longest, run)
            else:
                run = 0
        self.assertLess(
            longest, 100, f"a {longest}-line dead comment run still exists"
        )

    def test_live_main_block_intact(self):
        # The real ``__main__`` guard survived the truncation.
        src = _read_src()
        self.assertIn('if __name__ == "__main__":', src)
        self.assertIn("asyncio.run(kernel.shutdown())", src)


if __name__ == "__main__":
    unittest.main()
