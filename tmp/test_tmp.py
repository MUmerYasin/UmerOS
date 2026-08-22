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
Comprehensive Test Suite for UmerOS /tmp Filesystem Hierarchy System
=====================================================================

Verifies all components of the /tmp subsystem per TLDP and FHS 2.3/3.0.
"""

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

# Add project root and tmp folder to sys.path
_tmp_dir = Path(__file__).resolve().parent
_root_dir = _tmp_dir.parent
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))
if str(_tmp_dir) not in sys.path:
    sys.path.insert(0, str(_tmp_dir))


def test_imports() -> bool:
    print("=" * 60)
    print("Test 1: Module Imports")
    print("=" * 60)
    try:
        import tmp
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
        print("[OK] All /tmp modules and classes imported successfully.")
        return True
    except Exception as e:
        print(f"[FAIL] Import failed: {e}")
        return False


def test_fhs_and_hierarchy() -> bool:
    print("\n" + "=" * 60)
    print("Test 2: FHS & Hierarchy Socket Provisioning")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = (Path(tmpdir) / "tmp").resolve()
        from tmp.fhs import FHSValidator
        from tmp.hierarchy import TmpHierarchy

        hier = TmpHierarchy(tmp_root)
        skeletons = hier.bootstrap()

        # Check standard socket folders
        assert (tmp_root / ".X11-unix").exists()
        assert (tmp_root / ".ICE-unix").exists()
        assert (tmp_root / ".font-unix").exists()
        assert (tmp_root / ".rpc-unix").exists()
        assert (tmp_root / ".Test-unix").exists()
        assert (tmp_root / "user").exists()

        # Check user temp dir
        u1000 = hier.get_user_temp_dir(1000)
        assert u1000.exists()

        # Check validation
        val = FHSValidator.validate_tmp_root(tmp_root)
        assert val.is_compliant

        # Check entries listing
        entries = hier.list_entries()
        assert len(entries) >= 6

        print(f"[OK] Bootstrapped {len(skeletons)} standard socket dirs and verified hierarchy.")
        return True


def test_secure_io_and_mktemp() -> bool:
    print("\n" + "=" * 60)
    print("Test 3: Secure IO, mktemp & Context Managers")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = (Path(tmpdir) / "tmp").resolve()
        from tmp.secure_io import SecureIO, SecureTempFile, SecureTempDir

        # 1. Atomic file creation
        f1 = SecureIO.create_temp_file(prefix="test_", suffix=".dat", dir_path=tmp_root, content="secret_data")
        assert f1.exists()
        assert f1.read_text(encoding="utf-8") == "secret_data"

        # 2. Atomic dir creation
        d1 = SecureIO.create_temp_dir(prefix="test_dir_", dir_path=tmp_root)
        assert d1.exists()
        assert d1.is_dir()

        # 3. POSIX mktemp replacement
        mk_file = SecureIO.mktemp(template="app.XXXXXXXX", tmp_dir=tmp_root)
        assert mk_file.exists()

        # 4. Context managers
        with SecureTempFile(dir_path=tmp_root, content="ephemeral") as temp_f:
            assert temp_f.exists()
            assert temp_f.read_text(encoding="utf-8") == "ephemeral"
            path_copy = temp_f
        assert not path_copy.exists()

        with SecureTempDir(dir_path=tmp_root) as temp_d:
            assert temp_d.exists()
            dir_copy = temp_d
        assert not dir_copy.exists()

        print("[OK] SecureIO, mktemp, and context managers validated.")
        return True


def test_process_lock() -> bool:
    print("\n" + "=" * 60)
    print("Test 4: Process Lockfile & Stale Lock Detection")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = (Path(tmpdir) / "tmp").resolve()
        from tmp.lockfile import ProcessLock, LockAcquisitionError

        # 1. Acquire and release lock
        lock = ProcessLock("worker_sync", tmp_root=tmp_root)
        assert lock.acquire()
        assert (tmp_root / "worker_sync.lock").exists()

        # Second lock attempt should fail with timeout 0
        lock2 = ProcessLock("worker_sync", tmp_root=tmp_root)
        try:
            lock2.acquire(timeout=0.0)
            assert False, "Should not acquire already held lock"
        except LockAcquisitionError:
            pass

        assert lock.release()
        assert not (tmp_root / "worker_sync.lock").exists()

        # 2. Context manager usage
        with ProcessLock("batch_job", tmp_root=tmp_root) as job_lock:
            assert job_lock.is_locked
            assert (tmp_root / "batch_job.lock").exists()
        assert not (tmp_root / "batch_job.lock").exists()

        # 3. List active locks
        with ProcessLock("monitor", tmp_root=tmp_root):
            locks = ProcessLock.list_all_locks(tmp_root)
            assert len(locks) == 1
            assert locks[0]["name"] == "monitor"

        print("[OK] Process locks and mutex mechanics validated.")
        return True


def test_reaper_and_cleanup() -> bool:
    print("\n" + "=" * 60)
    print("Test 5: TmpReaper & Cleanup Policies")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = (Path(tmpdir) / "tmp").resolve()
        from tmp.hierarchy import TmpHierarchy
        from tmp.reaper import TmpReaper

        TmpHierarchy(tmp_root).bootstrap()
        reaper = TmpReaper(tmp_root=tmp_root)

        # Create old and new files
        old_file = tmp_root / "old_transient.tmp"
        old_file.write_text("old content", encoding="utf-8")
        # Backdate mtime & atime by 20 days
        past_time = time.time() - (20 * 86400)
        os.utime(str(old_file), (past_time, past_time))

        new_file = tmp_root / "new_active.tmp"
        new_file.write_text("new content", encoding="utf-8")

        # 1. Clean by age (threshold 10 days = 864000s)
        rep = reaper.clean_by_age(max_age_seconds=864000)
        assert not old_file.exists()
        assert new_file.exists()
        assert len(rep.reaped_files) >= 1

        # Protected sockets must remain intact
        assert (tmp_root / ".X11-unix").exists()

        # 2. Boot-time wipe (cleans new_file as well)
        rep_boot = reaper.clean_on_boot()
        assert not new_file.exists()
        assert (tmp_root / ".X11-unix").exists()

        # 3. Quota pruning
        for i in range(5):
            f = tmp_root / f"data_{i}.bin"
            f.write_bytes(b"X" * 1024)  # 1 KB each
            # stagger timestamps
            os.utime(str(f), (time.time() + i, time.time() + i))

        rep_quota = reaper.clean_by_quota(max_total_bytes=2048)
        assert rep_quota.bytes_freed >= 2048

        print("[OK] TmpReaper (age, boot wipe, quota) validated.")
        return True


def test_tmpfs_virtual_ram() -> bool:
    print("\n" + "=" * 60)
    print("Test 6: In-Memory Virtual TmpFS")
    print("=" * 60)
    from tmp.tmpfs import TmpFS, TmpFSQuotaExceededError

    tfs = TmpFS(max_bytes=1024)

    # 1. Write & Read
    node = tfs.write_file("buffer.raw", b"Virtual Ram Buffer Data")
    assert node.size == 23
    assert tfs.read_file("buffer.raw") == b"Virtual Ram Buffer Data"
    assert tfs.used_bytes == 23

    # 2. Quota check
    try:
        tfs.write_file("huge.bin", b"A" * 2000)
        assert False, "Should raise TmpFSQuotaExceededError"
    except TmpFSQuotaExceededError:
        pass

    # 3. Sync to disk
    with tempfile.TemporaryDirectory() as tmpdir:
        count = tfs.sync_to_disk(tmpdir)
        assert count == 1
        assert (Path(tmpdir) / "buffer.raw").exists()

    tfs.clear()
    assert tfs.used_bytes == 0

    print("[OK] In-memory TmpFS virtual RAM layer validated.")
    return True


def test_tmp_manager_master() -> bool:
    print("\n" + "=" * 60)
    print("Test 7: TmpManager Master Coordinator")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = (Path(tmpdir) / "tmp").resolve()
        from tmp.manager import TmpManager

        mgr = TmpManager(tmp_root=tmp_root)

        # 1. Create file & dir
        f = mgr.create_temp_file(prefix="master_", content="hello")
        assert f.exists()

        d = mgr.create_temp_dir(prefix="master_dir_")
        assert d.exists()

        # 2. Lock
        lock = mgr.lock("mgr_test")
        assert lock.is_locked
        lock.release()

        # 3. Audit & Summary
        audit = mgr.audit_all()
        assert audit["fhs_compliant"]
        assert audit["security_secure"]

        summary = mgr.get_summary()
        assert summary["total_files"] >= 1

        print("[OK] TmpManager master coordinator validated.")
        return True


def test_cli() -> bool:
    print("\n" + "=" * 60)
    print("Test 8: CLI Execution (tmp_ctl)")
    print("=" * 60)
    from tmp.cli import main as cli_main

    assert cli_main(["summary"]) == 0
    assert cli_main(["list"]) == 0
    assert cli_main(["locks"]) == 0
    assert cli_main(["audit"]) == 0

    print("[OK] CLI commands executed successfully.")
    return True


def run_all_tests() -> bool:
    tests = [
        test_imports,
        test_fhs_and_hierarchy,
        test_secure_io_and_mktemp,
        test_process_lock,
        test_reaper_and_cleanup,
        test_tmpfs_virtual_ram,
        test_tmp_manager_master,
        test_cli,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            if t():
                passed += 1
            else:
                failed += 1
        except Exception as ex:
            print(f"[FAIL] Exception in {t.__name__}: {ex}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} PASSED, {failed} FAILED (Total: {len(tests)})")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
