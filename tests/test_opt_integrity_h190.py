"""
H190 - ``OptPackage.verify_integrity`` only checked that the seven standard
subdirectories existed, while ``OptManager.verify``/``verify_all``,
``get_stats`` and ``list_packages`` all surfaced the result as package
"integrity" - false assurance with no tamper detection at all.

The check is now real: ``write_manifest()`` records a streamed SHA3-512
digest (the UmerOS design-mandate hash), permission bits and symlink
targets for the whole package tree, stored under ``/etc/opt`` - *outside*
the tree it protects - and ``verify_integrity()`` compares the live tree
against that record, failing closed when it is absent or unreadable.
The old directory-existence check survives under the honest name
``check_structure()``.

These tests pin: manifest placement and format, digest correctness, each
tamper class (content, permissions, deletion, addition, symlink swaps),
fail-closed behaviour without a manifest, and that every aggregate caller
(``verify_all``, ``get_stats``, ``list_packages``, the high-level
``OptManager.verify``) now reports genuine integrity.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from opt.manager import OptManager as HighLevelOptManager  # noqa: E402
from opt.package import (  # noqa: E402
    HASH_ALGORITHM,
    MANIFEST_NAME,
    OptManager as PackageOptManager,
    OptPackage,
)


def _roots(base: Path):
    return (
        base / "opt",
        base / "etc" / "opt",
        base / "var" / "opt",
    )


@pytest.fixture()
def pkg(tmp_path: Path):
    """A package with one installed binary payload."""
    root, etc, var = _roots(tmp_path)
    package = OptPackage("demo", "acme", str(root), str(etc), str(var))
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"payload-bytes")
    package.install_binary(str(payload))
    return package


def _symlink(link: Path, target: Path) -> None:
    """Create a symlink, skipping where the platform refuses to."""
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except OSError:  # pragma: no cover - platform without symlink support
        pytest.skip("platform cannot create symlinks")


# ── the honest rename ─────────────────────────────────────────────────────

def test_check_structure_reports_the_seven_fhs_dirs(pkg):
    structure = pkg.check_structure()
    assert set(structure) == {"bin", "lib", "include", "doc", "info", "man", "src"}
    assert all(structure.values()), structure
    assert all(isinstance(v, bool) for v in structure.values())


def test_check_structure_detects_a_removed_directory(pkg):
    shutil.rmtree(pkg.doc_path)
    assert pkg.check_structure()["doc"] is False


# ── manifest placement and format ────────────────────────────────────────

def test_hash_algorithm_is_the_repo_mandated_sha3_512():
    assert HASH_ALGORITHM == "sha3-512"


def test_manifest_is_stored_outside_the_package_tree(pkg):
    pkg.write_manifest()
    assert pkg.manifest_path.parent == pkg.etc_path
    inside = [p for p in pkg.base_path.rglob("*") if p.name == MANIFEST_NAME]
    assert inside == [], "manifest must not live inside the tree it protects"


def test_manifest_records_sha3_512_digests(pkg):
    pkg.write_manifest()
    data = json.loads(pkg.manifest_path.read_text(encoding="utf-8"))
    assert data["algorithm"] == "sha3-512"
    assert data["manifest_version"] == 1
    assert data["package"] == "demo"
    assert data["provider"] == "acme"
    assert data["entries"]["bin"]["type"] == "dir"
    entry = data["entries"]["bin/payload.bin"]
    assert entry["type"] == "file"
    assert entry["sha3-512"] == hashlib.sha3_512(b"payload-bytes").hexdigest()
    assert entry["mode"] == oct(pkg.bin_path.joinpath("payload.bin").stat().st_mode & 0o7777)


def test_manifest_keys_are_relative_posix_paths(pkg):
    pkg.write_manifest()
    data = json.loads(pkg.manifest_path.read_text(encoding="utf-8"))
    assert data["entries"]
    for rel in data["entries"]:
        assert not rel.startswith("/"), rel
        assert "\\" not in rel and ":" not in rel, rel


def test_symlinked_file_is_recorded_as_a_link_not_followed(pkg, tmp_path):
    outside = tmp_path / "outside-secret.txt"
    outside.write_bytes(b"do not hash me")
    _symlink(pkg.bin_path / "lnk", outside)
    pkg.write_manifest()
    data = json.loads(pkg.manifest_path.read_text(encoding="utf-8"))
    assert data["entries"]["bin/lnk"]["type"] == "link"


# ── happy path ───────────────────────────────────────────────────────────

def test_verify_integrity_passes_after_manifest(pkg):
    pkg.write_manifest()
    result = pkg.verify_integrity()
    assert result == {
        "structure": True,
        "manifest": True,
        "complete": True,
        "unmodified": True,
        "clean": True,
    }


def test_verify_integrity_values_are_all_booleans(pkg):
    pkg.write_manifest()
    assert all(isinstance(v, bool) for v in pkg.verify_integrity().values())


# ── tamper classes ───────────────────────────────────────────────────────

def test_tampered_content_is_detected(pkg):
    pkg.write_manifest()
    pkg.bin_path.joinpath("payload.bin").write_bytes(b"evil-bytes")
    result = pkg.verify_integrity()
    assert result["unmodified"] is False
    assert all(result.values()) is False
    assert pkg.integrity_details()["modified"] == ["bin/payload.bin"]


def test_deleted_file_is_detected(pkg):
    pkg.write_manifest()
    pkg.bin_path.joinpath("payload.bin").unlink()
    result = pkg.verify_integrity()
    assert result["complete"] is False
    assert pkg.integrity_details()["missing"] == ["bin/payload.bin"]


def test_added_file_is_detected(pkg):
    pkg.write_manifest()
    pkg.bin_path.joinpath("backdoor").write_bytes(b"#!/bin/sh\n")
    result = pkg.verify_integrity()
    assert result["clean"] is False
    assert "bin/backdoor" in pkg.integrity_details()["untracked"]


def test_added_empty_directory_is_detected(pkg):
    pkg.write_manifest()
    (pkg.base_path / "extra").mkdir()
    assert "extra" in pkg.integrity_details()["untracked"]
    assert pkg.verify_integrity()["clean"] is False


def test_directory_swapped_for_a_symlink_is_detected(pkg, tmp_path):
    pkg.write_manifest()
    shutil.rmtree(pkg.doc_path)
    _symlink(pkg.doc_path, tmp_path)
    result = pkg.verify_integrity()
    assert result["unmodified"] is False
    assert "doc" in pkg.integrity_details()["modified"]


def test_new_symlinked_directory_is_detected_as_untracked(pkg, tmp_path):
    pkg.write_manifest()
    _symlink(pkg.base_path / "sneak", tmp_path)
    assert "sneak" in pkg.integrity_details()["untracked"]
    assert pkg.verify_integrity()["clean"] is False


def test_file_replaced_by_a_directory_is_detected(pkg):
    pkg.write_manifest()
    pkg.bin_path.joinpath("payload.bin").unlink()
    pkg.bin_path.joinpath("payload.bin").mkdir()
    assert "bin/payload.bin" in pkg.integrity_details()["modified"]
    assert pkg.verify_integrity()["unmodified"] is False


def test_permission_change_is_detected(pkg):
    pkg.write_manifest()
    target = pkg.bin_path / "payload.bin"
    before = oct(target.stat().st_mode & 0o7777)
    os.chmod(target, 0o600)
    after = oct(target.stat().st_mode & 0o7777)
    if before == after:  # pragma: no cover - platform without mode bits
        pytest.skip("platform cannot represent a permission change")
    assert "bin/payload.bin" in pkg.integrity_details()["modified"]


def test_restoring_the_file_restores_integrity(pkg):
    pkg.write_manifest()
    target = pkg.bin_path / "payload.bin"
    original = target.read_bytes()
    try:
        target.write_bytes(b"tampered")
        assert pkg.verify_integrity()["unmodified"] is False
    finally:
        target.write_bytes(original)
    assert all(pkg.verify_integrity().values())


# ── fail-closed behaviour ────────────────────────────────────────────────

def test_missing_manifest_fails_closed(pkg):
    result = pkg.verify_integrity()
    assert result == {
        "structure": True,
        "manifest": False,
        "complete": False,
        "unmodified": False,
        "clean": False,
    }


def test_malformed_manifest_fails_closed(pkg):
    pkg.etc_path.mkdir(parents=True, exist_ok=True)
    pkg.manifest_path.write_text("this is not json", encoding="utf-8")
    result = pkg.verify_integrity()
    assert result["manifest"] is False
    assert all(result.values()) is False


def test_manifest_with_wrong_shape_fails_closed(pkg):
    pkg.etc_path.mkdir(parents=True, exist_ok=True)
    pkg.manifest_path.write_text(json.dumps({"files": {}}), encoding="utf-8")
    assert pkg.verify_integrity()["manifest"] is False


def test_deleted_manifest_fails_closed(pkg):
    pkg.write_manifest()
    pkg.manifest_path.unlink()
    assert pkg.verify_integrity()["manifest"] is False


# ── manifest lifecycle ───────────────────────────────────────────────────

def test_install_package_records_the_manifest(tmp_path):
    root, etc, var = _roots(tmp_path)
    mgr = PackageOptManager(str(root), str(etc), str(var))
    mgr.install_package("app", "acme")
    manifest = etc / "acme" / "app" / MANIFEST_NAME
    assert manifest.exists()
    assert mgr.get_package("app", "acme").verify_integrity()["manifest"] is True


def test_high_level_install_records_the_manifest(tmp_path):
    root, etc, var = _roots(tmp_path)
    mgr = HighLevelOptManager(str(root), str(etc), str(var))
    payload = tmp_path / "tool"
    payload.write_bytes(b"tool-bytes")
    result = mgr.install("hi", "prov", binaries=[str(payload)])
    assert result["success"] is True, result["errors"]
    manifest = etc / "prov" / "hi" / MANIFEST_NAME
    assert manifest.exists()
    verification = mgr.verify("hi", "prov")
    assert all(verification["integrity"].values()), verification


def test_high_level_verify_detects_tampering(tmp_path):
    root, etc, var = _roots(tmp_path)
    mgr = HighLevelOptManager(str(root), str(etc), str(var))
    payload = tmp_path / "tool"
    payload.write_bytes(b"tool-bytes")
    assert mgr.install("hi", "", binaries=[str(payload)])["success"] is True
    installed = root / "hi" / "bin" / "tool"
    installed.write_bytes(b"tampered")
    verification = mgr.verify("hi")
    assert verification["integrity"]["unmodified"] is False
    assert all(verification["integrity"].values()) is False


def test_remove_drops_the_manifest(pkg):
    pkg.write_manifest()
    assert pkg.manifest_path.exists()
    assert pkg.remove() is True
    assert not pkg.base_path.exists()
    assert not pkg.manifest_path.exists()


# ── aggregate callers now report real integrity ──────────────────────────

def test_verify_all_reflects_tampering(tmp_path):
    root, etc, var = _roots(tmp_path)
    mgr = PackageOptManager(str(root), str(etc), str(var))
    mgr.install_package("alpha")
    mgr.install_package("beta")
    tracked = root / "alpha" / "bin" / "tool"
    tracked.write_bytes(b"original")
    mgr.get_package("alpha").write_manifest()

    assert mgr.verify_all() == {"alpha": True, "beta": True}

    tracked.write_bytes(b"tampered")
    results = mgr.verify_all()
    assert results["alpha"] is False
    assert results["beta"] is True
    assert mgr.get_stats()["packages_with_integrity_issues"] == 1


def test_list_packages_integrity_is_real(tmp_path):
    root, etc, var = _roots(tmp_path)
    mgr = PackageOptManager(str(root), str(etc), str(var))
    mgr.install_package("solo")
    listed = {entry["name"]: entry for entry in mgr.list_packages()}
    assert listed["solo"]["integrity"]["manifest"] is True
    assert all(listed["solo"]["integrity"].values())

    (root / "solo" / "bin" / "backdoor").write_bytes(b"x")
    listed = {entry["name"]: entry for entry in mgr.list_packages()}
    assert listed["solo"]["integrity"]["clean"] is False


# ── the walk stays inside the package tree ───────────────────────────────

def test_symlinked_base_path_is_recorded_as_a_link(tmp_path):
    """A package dir that is itself a link is recorded, never walked."""
    root, etc, var = _roots(tmp_path)
    outside = tmp_path / "outside-tree"
    (outside / "bin").mkdir(parents=True)
    (outside / "bin" / "secret").write_bytes(b"secret")
    package = OptPackage("linked", "", str(root), str(etc), str(var))
    shutil.rmtree(package.base_path)
    _symlink(package.base_path, outside)
    package.write_manifest()
    data = json.loads(package.manifest_path.read_text(encoding="utf-8"))
    assert set(data["entries"]) == {"."}
    assert data["entries"]["."]["type"] == "link"
    assert not any("secret" in rel for rel in data["entries"])
    result = package.verify_integrity()
    assert result["manifest"] is True
    assert result["complete"] is True
    assert result["unmodified"] is True
    assert result["clean"] is True


def test_symlinked_base_replaced_by_a_real_dir_is_detected(tmp_path):
    root, etc, var = _roots(tmp_path)
    outside = tmp_path / "outside-tree"
    outside.mkdir()
    package = OptPackage("linked", "", str(root), str(etc), str(var))
    shutil.rmtree(package.base_path)
    _symlink(package.base_path, outside)
    package.write_manifest()
    assert package.verify_integrity()["unmodified"] is True

    package.base_path.unlink()
    package.base_path.mkdir()
    assert package.verify_integrity()["unmodified"] is False
