"""tests — source-tree integrity verification before copy (installer/).

`UmerInstaller.copy_os_files` previously copied whatever was at `source_dir`
with no integrity check. It now verifies the source tree against a pinned
SHA3-512 manifest (`umer-install-manifest.json`) BEFORE copying, fails closed on
any mismatch/missing/malformed case, and records the verified tree digest in the
install log.

Backward compatible: no manifest + non-strict -> permissive-with-warning.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from installer.installer import (  # noqa: E402
    INSTALL_MANIFEST_NAME,
    UmerInstaller,
    _sha3_512_file,
    _tree_digest,
)
from core.capability_gate import gate  # noqa: E402


@pytest.fixture(autouse=True)
def _gate_state():
    """Snapshot/restore strict mode + wiring so gates never leak."""
    strict = gate.strict
    try:
        gate.unwire()
    except Exception:
        pass
    gate.set_strict(False)
    yield
    gate.set_strict(strict)


@pytest.fixture()
def src(tmp_path):
    d = tmp_path / "src"
    d.mkdir()
    (d / "kernel.py").write_text("# kernel\n")
    (d / "ai.py").write_text("# ai\n")
    (d / "README.md").write_text("# readme\n")
    return d


def _write_manifest(src: Path, mapping, *, wrap=True):
    body = {"files": mapping} if wrap else mapping
    (src / INSTALL_MANIFEST_NAME).write_text(json.dumps(body), encoding="utf-8")


def _hash_map(src: Path):
    out = {}
    for p in src.iterdir():
        if p.is_file() and p.name != INSTALL_MANIFEST_NAME:
            out[p.name] = _sha3_512_file(str(p))
    return out


def _inst(src, tmp_path):
    dst = tmp_path / "dst"
    return UmerInstaller(source_dir=str(src), install_root=str(dst),
                         interactive=False), dst


# ── helpers ───────────────────────────────────────────────────────────────
def test_sha3_512_file_matches_hashlib(src):
    p = src / "kernel.py"
    assert _sha3_512_file(str(p)) == hashlib.sha3_512(p.read_bytes()).hexdigest()


def test_tree_digest_is_order_independent_and_deterministic():
    a = [("b.py", "11"), ("a.py", "22")]
    b = [("a.py", "22"), ("b.py", "11")]
    assert _tree_digest(a) == _tree_digest(b)
    assert len(_tree_digest(a)) == 128  # SHA3-512 hex


# ── no manifest ───────────────────────────────────────────────────────────
def test_no_manifest_non_strict_permits_with_warning(src, tmp_path):
    inst, dst = _inst(src, tmp_path)
    ok, digest = inst.verify_source_integrity(str(src))
    assert ok is True and digest is None
    assert any("UNVERIFIABLE" in e for e in inst._logger.get_entries())


def test_no_manifest_strict_refuses(src, tmp_path):
    inst, dst = _inst(src, tmp_path)
    ok, digest = inst.verify_source_integrity(str(src), require_manifest=True)
    assert ok is False and digest is None
    assert any("Refusing to copy" in e for e in inst._logger.get_entries())


def test_no_manifest_strict_via_gate_strict(src, tmp_path):
    inst, dst = _inst(src, tmp_path)
    gate.set_strict(True)
    ok, digest = inst.verify_source_integrity(str(src))
    assert ok is False and digest is None


def test_no_manifest_copy_still_works_non_strict(src, tmp_path):
    """Backward compat: existing behaviour preserved without a manifest."""
    inst, dst = _inst(src, tmp_path)
    n = inst.copy_os_files(source=str(src), dest=str(dst))
    assert n == 3
    assert (dst / "kernel.py").is_file()


# ── valid manifest ────────────────────────────────────────────────────────
def test_valid_manifest_verifies_and_records_digest(src, tmp_path):
    _write_manifest(src, _hash_map(src))
    inst, dst = _inst(src, tmp_path)
    ok, digest = inst.verify_source_integrity(str(src))
    assert ok is True
    assert digest is not None and len(digest) == 128
    assert any(f"tree SHA3-512={digest}" in e for e in inst._logger.get_entries())


def test_valid_manifest_copy_proceeds(src, tmp_path):
    _write_manifest(src, _hash_map(src))
    inst, dst = _inst(src, tmp_path)
    n = inst.copy_os_files(source=str(src), dest=str(dst))
    assert n == 4  # 3 files + the manifest itself
    assert (dst / "ai.py").is_file()


def test_manifest_without_wrapper_is_accepted(src, tmp_path):
    _write_manifest(src, _hash_map(src), wrap=False)
    inst, dst = _inst(src, tmp_path)
    ok, digest = inst.verify_source_integrity(str(src))
    assert ok is True and digest is not None


# ── tampering / mismatch ──────────────────────────────────────────────────
def test_digest_mismatch_fails_closed(src, tmp_path):
    m = _hash_map(src)
    m["kernel.py"] = "0" * 128  # wrong hash
    _write_manifest(src, m)
    inst, dst = _inst(src, tmp_path)
    ok, digest = inst.verify_source_integrity(str(src))
    assert ok is False and digest is None
    assert any("digest mismatch" in e for e in inst._logger.get_entries())


def test_tampered_file_after_manifest_fails(src, tmp_path):
    _write_manifest(src, _hash_map(src))
    (src / "ai.py").write_text("# TAMPERED\n")  # modify after manifest
    inst, dst = _inst(src, tmp_path)
    ok, _ = inst.verify_source_integrity(str(src))
    assert ok is False


def test_unlisted_file_fails(src, tmp_path):
    m = _hash_map(src)
    del m["README.md"]  # on disk but not attested
    _write_manifest(src, m)
    inst, dst = _inst(src, tmp_path)
    ok, _ = inst.verify_source_integrity(str(src))
    assert ok is False
    assert any("not listed in manifest" in e for e in inst._logger.get_entries())


def test_manifest_lists_missing_file_fails(src, tmp_path):
    m = _hash_map(src)
    m["ghost.py"] = "a" * 128  # attested but absent on disk
    _write_manifest(src, m)
    inst, dst = _inst(src, tmp_path)
    ok, _ = inst.verify_source_integrity(str(src))
    assert ok is False
    assert any("missing on disk" in e for e in inst._logger.get_entries())


def test_malformed_manifest_fails_closed(src, tmp_path):
    (src / INSTALL_MANIFEST_NAME).write_text("{not json", encoding="utf-8")
    inst, dst = _inst(src, tmp_path)
    ok, digest = inst.verify_source_integrity(str(src))
    assert ok is False and digest is None


def test_non_mapping_manifest_fails_closed(src, tmp_path):
    (src / INSTALL_MANIFEST_NAME).write_text("[1, 2, 3]", encoding="utf-8")
    inst, dst = _inst(src, tmp_path)
    ok, _ = inst.verify_source_integrity(str(src))
    assert ok is False


# ── copy refuses on failure ───────────────────────────────────────────────
def test_copy_refuses_on_mismatch_and_copies_nothing(src, tmp_path):
    m = _hash_map(src)
    m["kernel.py"] = "f" * 128
    _write_manifest(src, m)
    inst, dst = _inst(src, tmp_path)
    n = inst.copy_os_files(source=str(src), dest=str(dst))
    assert n == 0
    # destination must not contain the copied payload
    assert not (dst / "kernel.py").exists()
    assert not inst.get_state()["files_copied"]


def test_copy_refuses_when_strict_and_no_manifest(src, tmp_path):
    inst, dst = _inst(src, tmp_path)
    gate.set_strict(True)
    n = inst.copy_os_files(source=str(src), dest=str(dst))
    assert n == 0
    assert not (dst / "kernel.py").exists()


# ── source invariants ─────────────────────────────────────────────────────
def test_source_uses_sha3_512_and_manifest():
    src_text = (ROOT / "installer" / "installer.py").read_text(encoding="utf-8")
    assert "hashlib.sha3_512" in src_text
    assert "verify_source_integrity" in src_text
    assert "INSTALL_MANIFEST_NAME" in src_text
    # no live sha256 hashing in the installer
    assert "hashlib.sha256" not in src_text
