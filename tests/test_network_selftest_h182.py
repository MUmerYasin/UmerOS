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

"""H182 tests — every ``network/`` module carries a working ``_selftest()``.

The standard flagged ``network/`` (💭 H182): "No ``_selftest()`` in any module -
contrast mnt/ where all 7 were functional; reduces regression safety for the
networking subsystem. Add ``_selftest()`` to each (start with ``tcp_server``
abuse-control + ``dns_resolver`` resolution tests)."

Drift-recon corrected the wording, not the substance:

* **``network/__init__.py`` already had one.** The row says "any module", but
  the package ``__init__`` carried the ``__all__``-importability check that
  ``mnt/__init__.py`` and ``media/__init__.py`` also carry. So four modules
  needed work, not six.
* **``network/vpn_tunnel.py`` also already had one**, added during H179
  (``vpn_tunnel selftest: OK``) — that study's own note says it "lands part of
  H182".
* The genuine gap was the four leaf modules: ``dns_resolver.py``,
  ``tcp_server.py``, ``http_client.py`` and ``network_stack.py``.

Conventions pinned here:

* Each new ``_selftest()`` is a **sync function driving an async body** via
  ``asyncio.run`` — no async ``_selftest`` existed anywhere in the tree, so
  this establishes the pattern for async modules. ``vpn_tunnel`` keeps its
  purely sync one because it needs no event loop.
* A passing selftest prints **nothing**; the ``"X selftest: OK"`` line and the
  process exit code come from the ``__main__`` block, so ``python -m
  network.<module>`` works as a standalone smoke test.
* ``network/__init__.py``'s package selftest was strengthened to *run* every
  leaf selftest, making it a one-command regression check for the subsystem.

Nothing here touches the network: the loopback interface only.  The HTTP test
drives a throwaway ``http.server`` on an ephemeral port, the DoH test points at
two closed loopback ports so resolution must fail closed, and the DNS test only
resolves ``"localhost"`` through the host resolver.
"""

from __future__ import annotations

import ast
import importlib
import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

NETWORK = ROOT / "network"

#: All six modules of the package.
ALL_SIX = (
    "__init__.py",
    "dns_resolver.py",
    "http_client.py",
    "network_stack.py",
    "tcp_server.py",
    "vpn_tunnel.py",
)

#: The four modules that gained a selftest in H182.
LEAVES = ("dns_resolver", "http_client", "network_stack", "tcp_server")

#: The five modules the strengthened package selftest drives.
PACKAGE_CHILDREN = ("dns_resolver", "http_client", "network_stack", "tcp_server", "vpn_tunnel")

#: Modules whose ``_selftest`` drives an async body through ``asyncio.run``.
ASYNC_DRIVEN = LEAVES


def _module_names() -> set[str]:
    return {p.stem for p in NETWORK.glob("*.py") if p.stem != "__init__"} | {"__init__"}


class TestEveryModuleHasSelftest(unittest.TestCase):
    """The H182 code fact: a top-level ``_selftest`` in every module."""

    def test_network_has_the_expected_modules(self):
        self.assertIn("dns_resolver", _module_names())
        self.assertIn("vpn_tunnel", _module_names())

    def test_every_module_defines_a_top_level_selftest(self):
        for name in ALL_SIX:
            with self.subTest(module=name):
                tree = ast.parse((NETWORK / name).read_text(encoding="utf-8"))
                funcs = [
                    node.name
                    for node in tree.body
                    if isinstance(node, ast.FunctionDef)
                ]
                self.assertIn("_selftest", funcs, f"{name} defines no _selftest()")

    def test_async_driven_modules_expose_an_async_body(self):
        """The four new ones pair ``_selftest`` with ``_selftest_async``."""
        for name in ASYNC_DRIVEN:
            with self.subTest(module=name):
                tree = ast.parse((NETWORK / f"{name}.py").read_text(encoding="utf-8"))
                funcs = [
                    node.name
                    for node in tree.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                self.assertIn("_selftest_async", funcs, f"{name} has no async body")
                # and _selftest() must be the sync driver, not the async body
                self.assertTrue(
                    any(isinstance(node, ast.AsyncFunctionDef) and node.name == "_selftest_async"
                        for node in tree.body),
                    f"{name}._selftest_async must be a coroutine function",
                )

    def test_vpn_tunnel_keeps_its_sync_selftest(self):
        """H179's selftest needs no event loop and must stay sync."""
        tree = ast.parse((NETWORK / "vpn_tunnel.py").read_text(encoding="utf-8"))
        names = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        self.assertIn("_selftest", names)
        self.assertNotIn("_selftest_async", names)

    def test_every_module_has_a_main_block(self):
        """``python -m network.<module>`` must run the selftest and exit."""
        for name in ALL_SIX:
            with self.subTest(module=name):
                tree = ast.parse((NETWORK / name).read_text(encoding="utf-8"))
                main_blocks = [
                    node
                    for node in tree.body
                    if isinstance(node, ast.If)
                    and isinstance(node.test, ast.Compare)
                    and "__main__" in ast.dump(node.test)
                ]
                self.assertTrue(main_blocks, f"{name} has no __main__ block")


class TestLeafSelftestsPass(unittest.TestCase):
    """Each selftest must actually return ``True``."""

    def test_leaf_selftests_pass(self):
        for name in LEAVES:
            with self.subTest(module=name):
                module = importlib.import_module(f"network.{name}")
                self.assertIs(module._selftest(), True, f"{name}._selftest() failed")

    def test_vpn_tunnel_selftest_still_passes(self):
        module = importlib.import_module("network.vpn_tunnel")
        self.assertIs(module._selftest(), True)

    def test_package_selftest_passes(self):
        package = importlib.import_module("network")
        self.assertIs(package._selftest(), True)

    def test_passing_selftests_are_quiet(self):
        """A green selftest never announces a failure.

        The four modules follow the repo-wide ``mnt/`` convention:
        ``_selftest()`` returns a bool and prints **nothing**, and the
        ``"X selftest: OK"`` line plus the exit code come from the ``__main__``
        block.  ``vpn_tunnel`` instead prints its own OK line from
        inside ``_selftest()`` -- a harmless one-off, tolerated here.
        """
        for name in LEAVES + ("vpn_tunnel",):
            with self.subTest(module=name):
                module = importlib.import_module(f"network.{name}")
                out, err = io.StringIO(), io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    ok = module._selftest()
                self.assertTrue(ok, f"{name}._selftest() failed")
                self.assertNotIn("FAIL", out.getvalue() + err.getvalue())
                expected = "" if name in LEAVES else "vpn_tunnel selftest: OK\n"
                self.assertEqual(out.getvalue(), expected)


class TestPackageSelftestDrivesChildren(unittest.TestCase):
    """The H182 strengthening: the package selftest runs every leaf."""

    def test_package_selftest_invokes_every_child(self):
        package = importlib.import_module("network")
        modules = {name: importlib.import_module(f"network.{name}") for name in PACKAGE_CHILDREN}
        originals = {name: mod._selftest for name, mod in modules.items()}
        calls: list[str] = []
        try:
            for name, module in modules.items():
                module._selftest = lambda name=name: (calls.append(name), True)[1]  # type: ignore[method-assign]
            self.assertTrue(package._selftest(), "package selftest failed while spied on")
        finally:
            for name, module in modules.items():
                module._selftest = originals[name]  # type: ignore[method-assign]
        self.assertEqual(sorted(calls), sorted(PACKAGE_CHILDREN), "not every child was run")

    def test_package_selftest_fails_when_a_child_fails(self):
        package = importlib.import_module("network")
        modules = {name: importlib.import_module(f"network.{name}") for name in PACKAGE_CHILDREN}
        originals = {name: mod._selftest for name, mod in modules.items()}
        try:
            modules["dns_resolver"]._selftest = lambda: False  # type: ignore[method-assign]
            with redirect_stderr(io.StringIO()) as err:
                self.assertFalse(package._selftest())
            self.assertIn("dns_resolver", err.getvalue())
        finally:
            for name, module in modules.items():
                module._selftest = originals[name]  # type: ignore[method-assign]

    def test_package_selftest_reports_a_missing_child_selftest(self):
        package = importlib.import_module("network")
        modules = {name: importlib.import_module(f"network.{name}") for name in PACKAGE_CHILDREN}
        originals = {name: mod._selftest for name, mod in modules.items()}
        try:
            del modules["tcp_server"]._selftest  # type: ignore[attr-defined]
            with redirect_stderr(io.StringIO()) as err:
                self.assertFalse(package._selftest())
            self.assertIn("tcp_server", err.getvalue())
        finally:
            for name, module in modules.items():
                module._selftest = originals[name]  # type: ignore[method-assign]


if __name__ == "__main__":
    unittest.main()
