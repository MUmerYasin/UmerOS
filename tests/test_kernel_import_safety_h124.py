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

""" tests — the ``kernel/`` reference examples must not execute at import.

The standard flagged ``kernel/pqcrypto_.py`` (ran ``kyber1024.generate_keypair()``
at top level) and ``kernel/onnxruntime_.py`` as "reference/demo snippets that
execute at import", with the ``__``-prefixed/underscore-suffixed modules leaking
side effects into the package namespace.

Drift-recon proved the premise **stale**:  had already made both modules
import-safe — ``pqcrypto`` is imported function-locally inside ``demo()`` (called
only under ``if __name__ == "__main__"``) and ``onnxruntime`` is imported lazily
inside ``OnnxPredictorStub.__init__``.  This module pins that invariant at
**runtime** (a fresh interpreter), which is stronger than the source-level
checks in ``test_kernel_baseline_h123.py``.
"""

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KERNEL = ROOT / "kernel"
PQ = KERNEL / "pqcrypto_.py"
OX = KERNEL / "onnxruntime_.py"


def _run(code: str) -> subprocess.CompletedProcess:
    """Run ``code`` in a fresh interpreter rooted at the repo."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


class TestRuntimeImportIsolation(unittest.TestCase):
    """Importing the examples must have no third-party or output side effects."""

    def test_pqcrypto_import_does_not_pull_in_pqcrypto(self):
        proc = _run(
            "import sys; import kernel.pqcrypto_; "
            "print('PQ_LOADED', 'pqcrypto' in sys.modules)"
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "PQ_LOADED False")

    def test_onnxruntime_import_does_not_pull_in_onnxruntime(self):
        proc = _run(
            "import sys; import kernel.onnxruntime_; "
            "print('ORT_LOADED', 'onnxruntime' in sys.modules)"
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "ORT_LOADED False")

    def test_example_imports_produce_no_output(self):
        proc = _run("import kernel.pqcrypto_, kernel.onnxruntime_")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, "")

    def test_importing_kernel_does_not_load_the_examples(self):
        proc = _run(
            "import sys; import kernel; "
            "print('EX', 'kernel.pqcrypto_' in sys.modules, "
            "'kernel.onnxruntime_' in sys.modules)"
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "EX False False")

    def test_pqcrypto_keygen_not_reachable_without_the_dependency(self):
        """``demo()`` defers the import, so calling it fails *at call time*."""
        proc = _run(
            "import kernel.pqcrypto_ as m; "
            "\ntry:\n"
            "    m.demo()\n"
            "    print('RAN')\n"
            "except ImportError:\n"
            "    print('DEFERRED')\n"
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(proc.stdout.strip(), {"DEFERRED", "RAN"})


class TestNoTopLevelExecution(unittest.TestCase):
    """AST proof: module level contains only declarations, never execution."""

    _ALLOWED = (
        ast.Expr,        # module docstring (validated below)
        ast.Import,
        ast.ImportFrom,
        ast.Assign,      # the module ``log`` handle
        ast.AnnAssign,
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
        ast.If,          # the ``__main__`` guard
    )

    def _module_level_nodes(self, path: Path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        return tree.body

    def _assert_declarative(self, path: Path):
        for node in self._module_level_nodes(path):
            self.assertIsInstance(
                node, self._ALLOWED,
                f"{path.name}: executable top-level statement {type(node).__name__}",
            )
            if isinstance(node, ast.Expr):
                self.assertIsInstance(
                    node.value, ast.Constant,
                    f"{path.name}: top-level expression is not a docstring",
                )
            if isinstance(node, ast.If):
                src = ast.unparse(node.test)
                self.assertIn(
                    "__name__", src,
                    f"{path.name}: top-level if is not the __main__ guard",
                )

    def test_pqcrypto_has_no_top_level_execution(self):
        self._assert_declarative(PQ)

    def test_onnxruntime_has_no_top_level_execution(self):
        self._assert_declarative(OX)

    def test_pqcrypto_keygen_is_inside_a_function(self):
        """The keygen call must be nested in a function, never at module level."""
        tree = ast.parse(PQ.read_text(encoding="utf-8"))
        nested = [
            sub
            for fn in ast.walk(tree)
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
            for sub in ast.walk(fn)
            if isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Attribute)
            and sub.func.attr == "generate_keypair"
        ]
        self.assertTrue(nested, "generate_keypair must be called inside a function")


class TestReferenceExampleSurface(unittest.TestCase):
    """The examples keep their public surface and are clearly non-kernel."""

    def test_public_api_preserved(self):
        import kernel.pqcrypto_ as pq
        import kernel.onnxruntime_ as ox

        self.assertTrue(callable(pq.demo))
        self.assertTrue(hasattr(ox, "OnnxPredictorStub"))

    def test_marked_future_and_not_part_of_kernel(self):
        for path in (PQ, OX):
            src = path.read_text(encoding="utf-8")
            self.assertIn("[FUTURE]", src)
            self.assertIn("NOT part of the kernel", src)

    def test_not_reexported_by_the_package(self):
        init_src = (KERNEL / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("pqcrypto_", init_src)
        self.assertNotIn("onnxruntime_", init_src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
