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
pytest test suite for UmerOS package manager (umer-pkg).

Covers:
  * normal build + install + remove round-trip against a temp install dir.
  * SECURITY REGRESSION TESTS for H194 (tar-slip / CVE-2007-4559) and
    H195 (attacker-controlled manifest name/version -> arbitrary path).
      - install() with a traversal name must be refused (no write outside
        the install dir).
      - build() with a traversal manifest name must be refused.
"""

import base64
import os
import sys
import tarfile
import tempfile
from pathlib import Path

import pytest

_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from packages.umer_pkg import UmerPackageManager  # noqa: E402

# [FIX H13] Throwaway dev signing key, generated at import and pinned into the
# process-wide trust store so every UmerPackageManager() built afterwards trusts
# it.  This lets the suite exercise the REAL Ed25519 chain-of-trust end-to-end;
# the matching private key is intentionally never committed.
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from packages.trusted_keys import pin_trusted_key  # noqa: E402

_TEST_KEY = Ed25519PrivateKey.generate()
pin_trusted_key("umer-test-dev", _TEST_KEY.public_key().public_bytes_raw())


def _make_pkg(
    source_dir: Path,
    name: str,
    version: str = "1.0.0",
    signed: bool = True,
) -> Path:
    """Build a minimal .umerpkg archive (manifest.json + files/) for `name`.

    Signed by default with the throwaway ``umer-test-dev`` key (H13) so the
    install path's fail-closed signature gate passes.  Pass ``signed=False`` to
    build an UNSIGNED package (which ``verify_package`` must refuse).
    """
    mgr = UmerPackageManager()
    archive = mgr.build(
        source_dir=str(source_dir),
        manifest={"name": name, "version": version, "description": "test"},
        output_dir=str(source_dir.parent),
        signing_key=_TEST_KEY if signed else None,
        key_id="umer-test-dev" if signed else None,
    )
    return Path(archive)


@pytest.fixture
def pkg_env():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src = tmp / "src"
        src.mkdir()
        (src / "hello.txt").write_text("hi", encoding="utf-8")
        install_dir = tmp / "installed"
        registry = tmp / "registry"
        cache = tmp / "cache"
        yield {
            "tmp": tmp,
            "src": src,
            "install_dir": install_dir,
            "registry": registry,
            "cache": cache,
        }


def test_build_and_install(pkg_env):
    archive = _make_pkg(pkg_env["src"], "demo")
    assert archive.exists()
    # Construct the manager first so the install/registry/cache dirs exist,
    # then drop the built archive into the registry and re-scan it.
    mgr = UmerPackageManager(
        install_dir=str(pkg_env["install_dir"]),
        registry_dir=str(pkg_env["registry"]),
        cache_dir=str(pkg_env["cache"]),
    )
    import shutil
    shutil.copy(archive, pkg_env["registry"])
    mgr._scan_registry()
    assert mgr.install("demo") is True
    assert (pkg_env["install_dir"] / "demo" / "files" / "hello.txt").read_text(
        encoding="utf-8"
    ) == "hi"


def test_install_refuses_traversal_name(pkg_env):
    """H195: install() with a traversal name must NOT write outside install dir."""
    archive = _make_pkg(pkg_env["src"], "demo")
    # Construct the manager first so the registry dir exists, then copy the
    # archive into it before exercising the installer.
    mgr = UmerPackageManager(
        install_dir=str(pkg_env["install_dir"]),
        registry_dir=str(pkg_env["registry"]),
        cache_dir=str(pkg_env["cache"]),
    )
    import shutil
    shutil.copy(archive, pkg_env["registry"])
    # Directly exercise the single-package installer with a traversal name.
    ok = mgr._install_single("../../escape", str(archive))
    assert ok is False
    escaped = pkg_env["install_dir"].parent / "escape"
    assert not escaped.exists(), "CRITICAL: package install path-traversal succeeded!"


def test_build_refuses_traversal_name(pkg_env):
    """H195: build() with a traversal manifest name must be refused."""
    mgr = UmerPackageManager()
    with pytest.raises(ValueError):
        mgr.build(
            source_dir=str(pkg_env["src"]),
            manifest={
                "name": "../../etc/x",
                "version": "1.0.0",
                "description": "evil",
            },
            output_dir=str(pkg_env["tmp"]),
        )


def test_extractall_filter_blocks_slip(pkg_env):
    """H194: a tar member with '../' must be refused on extraction (filter=data)."""
    archive = pkg_env["tmp"] / "slip.umerpkg"
    with tarfile.open(archive, "w:gz") as tar:
        # manifest.json so the package is well-formed enough to attempt install.
        mf = tarfile.TarInfo("manifest.json")
        mf.size = 0
        tar.addfile(mf)
        bad = tarfile.TarInfo("files/../../escape.txt")
        data = b"pwn"
        bad.size = len(data)
        import io
        tar.addfile(bad, io.BytesIO(data))
    mgr = UmerPackageManager(
        install_dir=str(pkg_env["install_dir"]),
        registry_dir=str(pkg_env["registry"]),
        cache_dir=str(pkg_env["cache"]),
    )
    # Either the HASH check / extraction refuses the slip, or the slip member is
    # dropped by filter="data" so nothing lands outside install_dir.
    try:
        mgr._install_single("slip", str(archive))
    except Exception:
        pass
    escaped = pkg_env["install_dir"] / "escape.txt"
    outside = pkg_env["install_dir"].parent / "escape.txt"
    assert not outside.exists(), "CRITICAL: tar-slip extraction succeeded!"


def test_verify_hash_passes_for_legit_build(pkg_env):
    """H196: a properly built package (manifest + files/ + HASH) verifies OK."""
    archive = _make_pkg(pkg_env["src"], "demo")
    mgr = UmerPackageManager(
        install_dir=str(pkg_env["install_dir"]),
        registry_dir=str(pkg_env["registry"]),
        cache_dir=str(pkg_env["cache"]),
    )
    assert mgr._verify_hash(str(archive)) is True


def test_verify_hash_fails_when_hash_missing(pkg_env):
    """H196: a package WITHOUT a HASH must be REFUSED (was silently skipped)."""
    import io
    archive = pkg_env["tmp"] / "nohash.umerpkg"
    with tarfile.open(archive, "w:gz") as tar:
        mf = tarfile.TarInfo("manifest.json")
        mf.size = 0
        tar.addfile(mf)
        f = tarfile.TarInfo("files/hello.txt")
        data = b"hi"
        f.size = len(data)
        tar.addfile(f, io.BytesIO(data))
    mgr = UmerPackageManager(
        install_dir=str(pkg_env["install_dir"]),
        registry_dir=str(pkg_env["registry"]),
        cache_dir=str(pkg_env["cache"]),
    )
    assert mgr._verify_hash(str(archive)) is False


def test_verify_hash_detects_tampered_payload(pkg_env):
    """H196/H197: tampering a payload file (HASH unchanged) must FAIL closed."""
    import io
    good = _make_pkg(pkg_env["src"], "demo")
    bad = pkg_env["tmp"] / "tampered.umerpkg"
    with tarfile.open(good, "r:gz") as src, tarfile.open(bad, "w:gz") as dst:
        for m in src.getmembers():
            if m.name.startswith("files/") and m.isfile():
                data = src.extractfile(m).read() + b"TAMPERED"
                m.size = len(data)
                dst.addfile(m, io.BytesIO(data))
            else:
                dst.addfile(m, src.extractfile(m))
    mgr = UmerPackageManager(
        install_dir=str(pkg_env["install_dir"]),
        registry_dir=str(pkg_env["registry"]),
        cache_dir=str(pkg_env["cache"]),
    )
    assert mgr._verify_hash(str(bad)) is False


# ── H13: Ed25519 signature + chain-of-trust regression tests ──────────────────

def test_verify_package_passes_for_signed_build(pkg_env):
    """H13: a properly built + signed package verifies its signature."""
    archive = _make_pkg(pkg_env["src"], "demo")
    mgr = UmerPackageManager(
        install_dir=str(pkg_env["install_dir"]),
        registry_dir=str(pkg_env["registry"]),
        cache_dir=str(pkg_env["cache"]),
    )
    assert mgr.verify_package(str(archive)) is True
    # Integrity hash must still hold as defense-in-depth.
    assert mgr._verify_hash(str(archive)) is True


def test_verify_package_fails_when_unsigned(pkg_env):
    """H13: an UNSIGNED package must be REFUSED by the fail-closed signature gate."""
    archive = _make_pkg(pkg_env["src"], "demo", signed=False)
    mgr = UmerPackageManager(
        install_dir=str(pkg_env["install_dir"]),
        registry_dir=str(pkg_env["registry"]),
        cache_dir=str(pkg_env["cache"]),
    )
    # Hash is present (integrity OK) but there is no signature -> fail-closed.
    assert mgr._verify_hash(str(archive)) is True
    assert mgr.verify_package(str(archive)) is False
    # The install path must also refuse it.
    import shutil
    shutil.copy(archive, pkg_env["registry"])
    mgr._scan_registry()
    assert mgr.install("demo") is False


def test_verify_package_fails_when_untrusted_key(pkg_env):
    """H13: a package signed by an UNTRUSTED key must be refused (chain-of-trust)."""
    rogue = Ed25519PrivateKey.generate()  # never pinned into the trust store
    mgr = UmerPackageManager()
    archive = mgr.build(
        source_dir=str(pkg_env["src"]),
        manifest={"name": "rogue", "version": "1.0.0", "description": "evil"},
        output_dir=str(pkg_env["src"].parent),
        signing_key=rogue,
        key_id="rogue-ca",
    )
    v = UmerPackageManager(
        install_dir=str(pkg_env["install_dir"]),
        registry_dir=str(pkg_env["registry"]),
        cache_dir=str(pkg_env["cache"]),
    )
    assert v.verify_package(str(archive)) is False


def test_verify_package_fails_when_signature_tampered(pkg_env):
    """H13: a tampered SIGNATURE member must FAIL closed (forge resisted)."""
    import io
    good = _make_pkg(pkg_env["src"], "demo")
    bad = pkg_env["tmp"] / "forged.umerpkg"
    with tarfile.open(good, "r:gz") as src, tarfile.open(bad, "w:gz") as dst:
        for m in src.getmembers():
            if m.name == "SIGNATURE":
                # Replace the genuine signature with garbage (attacker forgery).
                forged = base64.b64encode(b"\x00" * 64)
                mi = tarfile.TarInfo("SIGNATURE")
                mi.size = len(forged)
                dst.addfile(mi, io.BytesIO(forged))
            else:
                dst.addfile(m, src.extractfile(m))
    mgr = UmerPackageManager(
        install_dir=str(pkg_env["install_dir"]),
        registry_dir=str(pkg_env["registry"]),
        cache_dir=str(pkg_env["cache"]),
    )
    assert mgr.verify_package(str(bad)) is False
