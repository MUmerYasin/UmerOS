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
Regression test for packages/umer_pkg.py YELLOW finding H201.

``_find_in_registry`` resolved a package with a filename *prefix* match
(``fname.startswith(name)``), so ``install("umer-core")`` could fetch
``umer-core-evil.umerpkg`` — an attacker-named archive shadowing a real
package.  Resolution must be by the manifest-declared name (exact, via the
index ``_scan_registry`` builds), with a tight filename fallback for
archives dropped into the registry after the last scan.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
)
from packages.trusted_keys import pin_trusted_key  # noqa: E402
from packages.umer_pkg import UmerPackageManager  # noqa: E402

# Throwaway dev signing key (same pattern as tests/test_packages.py) so the
# real fail-closed signature gate passes on the archives built here.  A
# dedicated key id: pin_trusted_key() overwrites by id in the process-wide
# trust store, and tests/test_packages.py pins its own key under
# "umer-test-dev" at import time.
_TEST_KEY = Ed25519PrivateKey.generate()
pin_trusted_key("umer-test-h201", _TEST_KEY.public_key().public_bytes_raw())


def _build(root: Path, tag: str, name: str, version: str = "1.0.0",
           marker: str = "hi") -> Path:
    """Build a signed .umerpkg for `name`; returns the archive path."""
    src = root / f"src-{tag}"
    src.mkdir(parents=True, exist_ok=True)
    (src / "payload.txt").write_text(marker, encoding="utf-8")
    mgr = UmerPackageManager()
    archive = mgr.build(
        source_dir=str(src),
        manifest={"name": name, "version": version, "description": "h201"},
        output_dir=str(root),
        signing_key=_TEST_KEY,
        key_id="umer-test-h201",
    )
    return Path(archive)


class _Env:
    """Isolated install/registry/cache roots."""

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.registry = self.root / "registry"
        self.install = self.root / "installed"
        self.cache = self.root / "cache"
        self.registry.mkdir(parents=True, exist_ok=True)
        # Constructed against the EMPTY registry so a later _scan_registry()
        # (or none at all) is what populates the index.
        self.mgr = UmerPackageManager(
            install_dir=str(self.install),
            registry_dir=str(self.registry),
            cache_dir=str(self.cache),
        )

    def drop(self, archive: Path, as_name: str) -> Path:
        dest = self.registry / as_name
        shutil.copy(archive, dest)
        return dest

    def cleanup(self) -> None:
        self._tmp.cleanup()


# ---------------------------------------------------------------------------
# Fallback resolution (archive added after the last scan): exact matches only
# ---------------------------------------------------------------------------

class TestFallbackResolution:
    def setup_method(self, method):
        self.env = _Env()
        self._cleanup = self.env.cleanup

    def teardown_method(self, method):
        self._cleanup()

    def test_evil_suffixed_file_is_never_selected(self):
        """umer-core must not resolve to umer-core-evil.umerpkg (the H201 bug)."""
        real = _build(self.env.root, "real", "umer-core", "1.0.0")
        evil = _build(self.env.root, "evil", "other-pkg", "9.9.9", marker="evil")
        self.env.drop(real, "umer-core-1.0.0.umerpkg")
        self.env.drop(evil, "umer-core-evil.umerpkg")
        found = self.env.mgr._find_in_registry("umer-core")
        assert found is not None
        assert Path(found).name == "umer-core-1.0.0.umerpkg", found

    def test_plain_prefix_no_longer_matches(self):
        """'demo' used to match 'demolition.umerpkg' via startswith()."""
        other = _build(self.env.root, "x", "demolition", "1.0.0")
        self.env.drop(other, "demolition.umerpkg")
        assert self.env.mgr._find_in_registry("demo") is None

    def test_exact_stem_matches(self):
        pkg = _build(self.env.root, "y", "demo", "1.0.0")
        self.env.drop(pkg, "demo.umerpkg")
        found = self.env.mgr._find_in_registry("demo")
        assert found is not None and Path(found).name == "demo.umerpkg"

    def test_highest_version_wins_deterministically(self):
        old = _build(self.env.root, "1", "demo", "1.0.0")
        new = _build(self.env.root, "2", "demo", "2.0.0")
        self.env.drop(old, "demo-1.0.0.umerpkg")
        self.env.drop(new, "demo-2.0.0.umerpkg")
        found = self.env.mgr._find_in_registry("demo")
        assert found is not None and Path(found).name == "demo-2.0.0.umerpkg"

    def test_non_version_suffix_rejected(self):
        """A 'demo-beta' stem is not '<name>-<version>' — refuse to guess."""
        beta = _build(self.env.root, "b", "demo", "1.0.0-beta")
        self.env.drop(beta, "demo-beta.umerpkg")
        assert self.env.mgr._find_in_registry("demo") is None

    def test_directory_named_like_archive_skipped(self):
        real = _build(self.env.root, "d", "demo", "1.0.0")
        self.env.drop(real, "demo-1.0.0.umerpkg")
        (self.env.registry / "demo-9.9.9.umerpkg").mkdir()
        found = self.env.mgr._find_in_registry("demo")
        assert found is not None and Path(found).name == "demo-1.0.0.umerpkg"

    def test_empty_registry_returns_none(self):
        assert self.env.mgr._find_in_registry("demo") is None

    def test_missing_registry_dir_returns_none(self):
        self.env.mgr._registry_dir = str(self.env.root / "does-not-exist")
        assert self.env.mgr._find_in_registry("demo") is None


# ---------------------------------------------------------------------------
# Index-first resolution (manifest-declared name is authoritative)
# ---------------------------------------------------------------------------

class TestIndexResolution:
    def setup_method(self, method):
        self.env = _Env()
        self._cleanup = self.env.cleanup

    def teardown_method(self, method):
        self._cleanup()

    def test_manifest_name_drives_resolution(self):
        """A file named demo-evil.umerpkg declaring 'evilpkg' resolves only
        under its declared name — never as 'demo'."""
        evil = _build(self.env.root, "e", "evilpkg", "1.0.0", marker="evil")
        self.env.drop(evil, "demo-evil.umerpkg")
        real = _build(self.env.root, "r", "demo", "1.0.0")
        self.env.drop(real, "demo-1.0.0.umerpkg")
        self.env.mgr._scan_registry()

        assert Path(self.env.mgr._find_in_registry("demo")).name == \
            "demo-1.0.0.umerpkg"
        assert Path(self.env.mgr._find_in_registry("evilpkg")).name == \
            "demo-evil.umerpkg"
        # The literal name 'demo-evil' is still reachable, but only by an
        # exact-stem match — never as a prefix of 'demo'.
        assert Path(self.env.mgr._find_in_registry("demo-evil")).name == \
            "demo-evil.umerpkg"

    def test_index_beats_later_dropped_confusing_file(self):
        real = _build(self.env.root, "r2", "demo", "1.0.0")
        self.env.drop(real, "demo-1.0.0.umerpkg")
        self.env.mgr._scan_registry()
        # A newer-looking archive dropped in afterwards must NOT hijack the
        # indexed entry without a re-scan.
        newer = _build(self.env.root, "n", "demo", "3.0.0")
        self.env.drop(newer, "demo-3.0.0.umerpkg")
        assert Path(self.env.mgr._find_in_registry("demo")).name == \
            "demo-1.0.0.umerpkg"

    def test_pre_release_manifest_resolves_by_declared_name(self):
        """After a scan the manifest name is authoritative, so a 1.0.0-beta
        package is reachable as its declared name."""
        beta = _build(self.env.root, "b2", "demo", "1.0.0-beta")
        self.env.drop(beta, "demo-1.0.0-beta.umerpkg")
        self.env.mgr._scan_registry()
        assert Path(self.env.mgr._find_in_registry("demo")).name == \
            "demo-1.0.0-beta.umerpkg"


# ---------------------------------------------------------------------------
# End-to-end: install() resolves through the fixed lookup
# ---------------------------------------------------------------------------

class TestInstallResolvesExactPackage:
    def setup_method(self, method):
        self.env = _Env()
        self._cleanup = self.env.cleanup

    def teardown_method(self, method):
        self._cleanup()

    def test_install_uses_the_real_package_not_the_shadow(self):
        real = _build(self.env.root, "a", "demo", "1.0.0", marker="real")
        shadow = _build(self.env.root, "b", "shadowpkg", "1.0.0", marker="shadow")
        self.env.drop(real, "demo-1.0.0.umerpkg")
        # Same prefix, different declared name, hostile filename.
        self.env.drop(shadow, "demo-evil.umerpkg")
        self.env.mgr._scan_registry()

        assert self.env.mgr.install("demo") is True
        installed = self.env.install / "demo" / "files" / "payload.txt"
        assert installed.read_text(encoding="utf-8") == "real"

    def test_install_by_declared_name_of_oddly_named_file(self):
        odd = _build(self.env.root, "c", "goodpkg", "2.0.0", marker="good")
        self.env.drop(odd, "zzz-unrelated.umerpkg")
        self.env.mgr._scan_registry()
        assert self.env.mgr.install("goodpkg") is True
        installed = self.env.install / "goodpkg" / "files" / "payload.txt"
        assert installed.read_text(encoding="utf-8") == "good"
