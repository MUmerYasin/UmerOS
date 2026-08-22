"""
pytest test suite for UmerOS /tmp filesystem hierarchy.
"""

import os
import sys
import tempfile
import time
from pathlib import Path
import pytest

_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from tmp import (
    FHSValidator,
    TmpHierarchy,
    SecureIO,
    SecureTempFile,
    SecureTempDir,
    ProcessLock,
    TmpReaper,
    TmpPermissionManager,
    TmpFS,
    TmpManager,
    mktemp,
    get_temp_file,
    get_temp_dir,
    clean_temp,
)


@pytest.fixture
def temp_tmp():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = (Path(tmpdir) / "tmp").resolve()
        tmp_root.mkdir(parents=True, exist_ok=True)
        yield tmp_root


def test_fhs_validation(temp_tmp):
    val = FHSValidator.validate_tmp_root(temp_tmp)
    assert val.is_compliant


def test_hierarchy_bootstrap(temp_tmp):
    hier = TmpHierarchy(temp_tmp)
    created = hier.bootstrap()
    assert (temp_tmp / ".X11-unix").exists()
    assert (temp_tmp / ".ICE-unix").exists()
    assert (temp_tmp / ".font-unix").exists()
    assert (temp_tmp / "user").exists()


def test_secure_io(temp_tmp):
    f = SecureIO.create_temp_file(prefix="test_", dir_path=temp_tmp, content="hello")
    assert f.exists()
    assert f.read_text(encoding="utf-8") == "hello"

    d = SecureIO.create_temp_dir(prefix="dir_", dir_path=temp_tmp)
    assert d.exists()
    assert d.is_dir()

    with SecureTempFile(dir_path=temp_tmp, content="ephemeral") as tf:
        assert tf.exists()
        path = tf
    assert not path.exists()


def test_process_lock(temp_tmp):
    with ProcessLock("sync_job", tmp_root=temp_tmp) as lock:
        assert lock.is_locked
        assert (temp_tmp / "sync_job.lock").exists()
    assert not (temp_tmp / "sync_job.lock").exists()


def test_reaper(temp_tmp):
    TmpHierarchy(temp_tmp).bootstrap()
    reaper = TmpReaper(tmp_root=temp_tmp)

    f = temp_tmp / "sample.tmp"
    f.write_text("data", encoding="utf-8")
    past = time.time() - 1000000
    os.utime(str(f), (past, past))

    rep = reaper.clean_by_age(max_age_seconds=500000)
    assert not f.exists()
    assert len(rep.reaped_files) >= 1
    assert (temp_tmp / ".X11-unix").exists()


def test_tmpfs():
    tfs = TmpFS(max_bytes=2048)
    tfs.write_file("test.bin", b"RAM DATA")
    assert tfs.read_file("test.bin") == b"RAM DATA"
    assert tfs.used_bytes == 8
    tfs.clear()
    assert tfs.used_bytes == 0


def test_tmp_manager(temp_tmp):
    mgr = TmpManager(tmp_root=temp_tmp)
    f = mgr.create_temp_file(content="data")
    assert f.exists()

    summary = mgr.get_summary()
    assert summary["total_files"] >= 1

    audit = mgr.audit_all()
    assert audit["fhs_compliant"]


def test_tmpfs_sync_refuses_traversal(temp_tmp):
    """H282: a virtual-file name like '../../escape.txt' must NOT be written
    outside the sync target dir."""
    from tmp.tmpfs import TmpFSNode

    tfs = TmpFS(max_bytes=1_000_000)
    tfs.write_file("normal.txt", b"data")
    # Simulate a malicious stored node name (the key is unsanitized in memory).
    tfs._nodes["../../escape.txt"] = TmpFSNode(
        name="../../escape.txt", data=bytearray(b"pwn")
    )

    target = temp_tmp / "synced"
    count = tfs.sync_to_disk(target)

    # Only the legitimate node is written; the traversal one is refused.
    assert count == 1
    assert (target / "normal.txt").exists()
    assert not (temp_tmp.parent / "escape.txt").exists(), \
        "CRITICAL: tmpfs sync path-traversal succeeded!"
