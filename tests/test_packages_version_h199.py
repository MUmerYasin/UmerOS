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
Regression test for packages/umer_pkg.py YELLOW finding H199.

``UmerPackageManager.update`` compared version *strings* lexicographically
(``if manifest.version <= current:``), so ``"1.10.0" <= "1.9.0"`` was True
and genuine upgrades were silently skipped.  The comparison must be
semantic over dotted-decimal versions.
"""

from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

import core.capability_gate as cg                           # noqa: E402
from packages.umer_pkg import UmerPackageManager, _version_key  # noqa: E402


class TestVersionKey(unittest.TestCase):
    """The parser that replaces the string comparison."""

    def test_plain_dotted_decimal(self):
        self.assertEqual(_version_key("1.10.0"), (1, 10))
        self.assertEqual(_version_key("0.0.0"), ())
        self.assertEqual(_version_key("2"), (2,))

    def test_optional_v_prefix(self):
        self.assertEqual(_version_key("v1.10.0"), (1, 10))
        self.assertEqual(_version_key("V2.1"), (2, 1))

    def test_semantic_ordering(self):
        # The exact pair the old string compare got wrong.
        self.assertGreater(_version_key("1.10.0"), _version_key("1.9.0"))
        self.assertGreater(_version_key("2.0.0"), _version_key("1.99.99"))
        self.assertGreater(_version_key("1.0.1"), _version_key("1.0.0"))
        # trailing zeros normalise: "1.0" == "1.0.0" == "1"
        self.assertEqual(_version_key("1.0"), _version_key("1.0.0"))
        self.assertEqual(_version_key("1.0"), _version_key("1"))
        self.assertEqual(_version_key("0.0.0"), ())

    def test_rejects_non_dotted_decimal(self):
        for bad in ("", "   ", "abc", "1.0.0-beta", "1.0.0+build5", "1..0",
                    "1.a", "-1", "²", "١.٠"):
            with self.subTest(version=bad):
                self.assertIsNone(_version_key(bad))

    def test_non_string_input_is_coerced_not_raised(self):
        self.assertEqual(_version_key(1), (1,))
        self.assertIsNone(_version_key(None))


class _FakeManifest(SimpleNamespace):
    """Minimal stand-in for PackageManifest (only .version is consulted)."""


class TestUpdateOrdering(unittest.TestCase):
    """update() must decide with a semantic comparison."""

    def setUp(self) -> None:
        self._prev_strict = cg.gate.strict
        self.addCleanup(cg.gate.set_strict, self._prev_strict)
        cg.gate.set_strict(False)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.pkg = UmerPackageManager(
            install_dir=str(base / "install"),
            registry_dir=str(base / "registry"),
            cache_dir=str(base / "cache"),
        )
        self.calls: list = []

        def _remove(name: str) -> bool:
            self.calls.append(("remove", name))
            return True

        def _install(name: str, path: str) -> bool:
            self.calls.append(("install", name, path))
            return True

        self.pkg.remove = _remove                       # type: ignore[assignment]
        self.pkg._install_single = _install             # type: ignore[assignment]

    def _prepare(self, installed: str, registry: str) -> None:
        self.pkg._db = {"demo": {"version": installed, "path": "/old"}}
        self.pkg._find_in_registry = lambda name: "/reg/demo.umerpkg"  # type: ignore[assignment]
        self.pkg._read_manifest = lambda path: _FakeManifest(  # type: ignore[assignment]
            name="demo", version=registry
        )

    def test_real_upgrade_is_not_skipped(self):
        """The H199 bug: 1.10.0 over 1.9.0 must actually update."""
        self._prepare("1.9.0", "1.10.0")
        results = self.pkg.update("demo")
        self.assertEqual(results, {"demo": True})
        self.assertEqual(
            [c[0] for c in self.calls], ["remove", "install"],
            "a genuine upgrade must remove + reinstall",
        )

    def test_v_prefixed_upgrade(self):
        self._prepare("1.9.0", "v1.10.0")
        self.pkg.update("demo")
        self.assertEqual([c[0] for c in self.calls], ["remove", "install"])

    def test_downgrade_is_refused(self):
        """Registry older than installed — update must not silently downgrade."""
        self._prepare("1.10.0", "1.9.0")
        results = self.pkg.update("demo")
        self.assertEqual(results, {"demo": True})
        self.assertEqual(self.calls, [], "no remove/install for a downgrade")

    def test_equal_versions_skip(self):
        self._prepare("1.10.0", "1.10.0")
        self.pkg.update("demo")
        self.assertEqual(self.calls, [])

    def test_equal_versions_different_spelling_skip(self):
        self._prepare("1.0", "1.0.0")
        self.pkg.update("demo")
        self.assertEqual(self.calls, [])

    def test_unparseable_registry_version_reinstalls_with_warning(self):
        """Never silently skip: unknown ordering => reinstall + loud log."""
        self._prepare("1.0.0", "stable")
        with self.assertLogs("UmerOS.UmerPkg", level="WARNING") as ctx:
            self.pkg.update("demo")
        self.assertEqual([c[0] for c in self.calls], ["remove", "install"])
        self.assertTrue(
            any("cannot order versions" in m for m in ctx.output),
            f"expected a warning, got: {ctx.output}",
        )

    def test_unparseable_installed_version_reinstalls_with_warning(self):
        self._prepare("stable", "1.0.0")
        with self.assertLogs("UmerOS.UmerPkg", level="WARNING"):
            self.pkg.update("demo")
        self.assertEqual([c[0] for c in self.calls], ["remove", "install"])

    def test_byte_identical_unparseable_versions_skip(self):
        """Same unparseable string on both sides is still 'up-to-date'."""
        self._prepare("stable", "stable")
        self.pkg.update("demo")
        self.assertEqual(self.calls, [])

    def test_multi_component_comparison(self):
        self._prepare("1.9.9", "1.10.0")
        self.pkg.update("demo")
        self.assertEqual([c[0] for c in self.calls], ["remove", "install"])

    def test_update_still_gated(self):
        """H198 must keep holding: strict mode refuses before any FS work."""
        cg.gate.set_strict(True)
        self._prepare("1.9.0", "1.10.0")
        with self.assertRaises(PermissionError):
            self.pkg.update("demo")
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
