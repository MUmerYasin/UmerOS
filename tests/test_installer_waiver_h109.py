"""tests — installer waiver/docstring must not over-promise capability.

The module docstring listed 5 "non-negotiable" requirements, but #3 (real
bootloader/partition-table backup) and #4 (full pre-install restore) are not
implemented: `backup_bootloader` is metadata-only and `rollback` only removes
the install root. The text is now softened and the full contract marked
[FUTURE], with machine-readable capability flags.
"""
from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from installer import installer as inst_mod  # noqa: E402
from installer.installer import (  # noqa: E402
    BACKUP_CAPTURES_BOOT_BYTES,
    ROLLBACK_RESTORES_BOOT_STATE,
    UmerInstaller,
)
from core.capability_gate import gate  # noqa: E402

SRC = ROOT / "installer" / "installer.py"


@pytest.fixture(autouse=True)
def _gate_state():
    strict = gate.strict
    try:
        gate.unwire()
    except Exception:
        pass
    gate.set_strict(False)
    yield
    gate.set_strict(strict)


# ── capability flags ──────────────────────────────────────────────────────
def test_capability_flags_are_false_today():
    assert BACKUP_CAPTURES_BOOT_BYTES is False
    assert ROLLBACK_RESTORES_BOOT_STATE is False


def test_flags_are_module_level_and_bool():
    src = SRC.read_text(encoding="utf-8")
    tree = ast.parse(src)
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in (
                    "BACKUP_CAPTURES_BOOT_BYTES", "ROLLBACK_RESTORES_BOOT_STATE",
                ):
                    found[t.id] = node.value
    assert set(found) == {"BACKUP_CAPTURES_BOOT_BYTES", "ROLLBACK_RESTORES_BOOT_STATE"}
    for v in found.values():
        assert isinstance(v, ast.Constant) and v.value is False


# ── docstring accuracy ────────────────────────────────────────────────────
def test_module_docstring_no_overclaim_phrases():
    text = SRC.read_text(encoding="utf-8")
    assert "non-negotiable" not in text
    assert "fully restores the pre-installation state" not in text
    assert "System restored to pre-installation state" not in text


def test_module_docstring_marks_partial_future():
    doc = inst_mod.__doc__ or ""
    assert "Honored guarantees" in doc
    assert "Partial / [FUTURE] guarantees" in doc
    assert "metadata-only" in doc
    assert "does NOT restore a bootloader or partition" in doc
    assert "BACKUP_CAPTURES_BOOT_BYTES" in doc
    assert "ROLLBACK_RESTORES_BOOT_STATE" in doc


def test_backup_docstring_is_honest():
    doc = UmerInstaller.backup_bootloader.__doc__ or ""
    assert "metadata-only" in doc
    assert "does **not** capture MBR/GPT" in doc
    assert "BACKUP_CAPTURES_BOOT_BYTES" in doc


def test_rollback_docstring_is_honest():
    doc = UmerInstaller.rollback.__doc__ or ""
    assert "best-effort cleanup" in doc
    assert "not a full restore" in doc.lower()
    assert "ROLLBACK_RESTORES_BOOT_STATE" in doc


# ── behaviour matches the softened text ───────────────────────────────────
def test_backup_writes_only_metadata(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("x")
    bkp = tmp_path / "bkp"
    inst = UmerInstaller(source_dir=str(src), install_root=str(tmp_path / "dst"),
                         backup_dir=str(bkp), interactive=False)
    path = inst.backup_bootloader()
    assert os.path.isfile(path)
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    # only metadata keys — no raw boot bytes / no partition table
    assert set(data) <= {"timestamp", "platform", "install_root", "note"}
    assert "mbr" not in json.dumps(data).lower()
    assert "gpt" not in json.dumps(data).lower()
    assert "efi" not in json.dumps(data).lower()


def test_rollback_removes_root_but_restores_nothing(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("x")
    dst = tmp_path / "dst"
    inst = UmerInstaller(source_dir=str(src), install_root=str(dst),
                         backup_dir=str(tmp_path / "bkp"), interactive=False)
    inst.copy_os_files(source=str(src), dest=str(dst))
    assert dst.is_dir()
    assert inst.rollback() is True
    assert not dst.exists()
    # rollback must not fabricate a bootloader/partition restore artefact
    assert not (tmp_path / "bkp" / "restored_boot").exists()


def test_log_message_no_longer_overclaims(tmp_path, caplog):
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("x")
    dst = tmp_path / "dst"
    inst = UmerInstaller(source_dir=str(src), install_root=str(dst),
                         backup_dir=str(tmp_path / "bkp"), interactive=False)
    inst.copy_os_files(source=str(src), dest=str(dst))
    with caplog.at_level("INFO", logger="UmerOS.Installer"):
        inst.rollback()
    joined = "\n".join(r.message for r in caplog.records)
    assert "System restored to pre-installation state" not in joined
    assert "Installed files removed" in joined
