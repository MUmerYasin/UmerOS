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
Regression tests for H83 (home/home_backup.py).

H83 was an unsafe ``restore_backup`` that did ``shutil.rmtree(user_home)`` then
``tarfile.extractall`` with NO traversal filter -- a tar-slip / arbitrary file
write + data-loss exposure (CVE-2007-4559). The fix makes restore:
  * fail-closed behind the ``home.admin`` capability,
  * traversal-safe (reject ``..``/absolute/symlink members, ``filter='data'``),
  * non-destructive (snapshot the live home, swap in only after verified),
  * checksum-verified against any known BackupRecord.
"""

import importlib.util
import io
import os
import sys
import tarfile

import pytest

# Ensure the project root is importable (needed for the `core` package that
# home_backup imports).
_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

# [H83 test] Load home_backup.py by FILE PATH under a unique module name.
# The repo has sibling modules `bin/home.py` and `root/home.py`; some other
# test files insert `bin/`/`root/` onto sys.path and `import home`, which caches
# sys.modules['home'] as a *module* (not the package). Importing the bare
# `home.home_backup` package then fails with "'home' is not a package". Loading
# the file directly under a collision-free name keeps this test isolated and
# green regardless of collection order. (home_backup is a standalone module and
# does not depend on the `home` package context.)
_HOME_BACKUP_PATH = os.path.join(_PROJ, "home", "home_backup.py")
_spec = importlib.util.spec_from_file_location("umeros_home_backup_test", _HOME_BACKUP_PATH)
home_backup = importlib.util.module_from_spec(_spec)
sys.modules["umeros_home_backup_test"] = home_backup
_spec.loader.exec_module(home_backup)

HomeBackupManager = home_backup.HomeBackupManager
_is_safe_segment = home_backup._is_safe_segment
from core.capability_gate import gate, CAP_HOME_ADMIN  # noqa: E402

PY_GE_312 = sys.version_info >= (3, 12)


def _write_user(home_root, username, content="original data"):
    user_home = os.path.join(home_root, username)
    os.makedirs(user_home, exist_ok=True)
    with open(os.path.join(user_home, "note.txt"), "w") as fh:
        fh.write(content)
    return user_home


def _make_tar(path, members):
    """members: iterable of (name, bytes)."""
    with tarfile.open(path, "w:gz") as tar:
        for name, data in members:
            ti = tarfile.TarInfo(name=name)
            ti.size = len(data)
            tar.addfile(ti, io.BytesIO(data))


@pytest.fixture
def mgr(tmp_path):
    home = tmp_path / "home"
    back = tmp_path / "back"
    home.mkdir()
    back.mkdir()
    return HomeBackupManager(home_path=str(home), backup_path=str(back))


@pytest.fixture(autouse=True)
def _gate_state():
    """The capability gate is process-global; restore it after every test."""
    was_strict = gate.strict
    gate.set_strict(False)
    gate.unwire()
    yield
    gate.set_strict(was_strict)
    gate.unwire()


def test_create_and_restore_happy_path(mgr, tmp_path):
    _write_user(str(tmp_path / "home"), "alice")
    rec = mgr.create_backup("alice")
    assert rec is not None

    # corrupt the live home, then restore from backup
    with open(os.path.join(str(tmp_path / "home"), "alice", "note.txt"), "w") as fh:
        fh.write("CORRUPTED")

    assert mgr.restore_backup("alice", rec.backup_path) is True
    with open(os.path.join(str(tmp_path / "home"), "alice", "note.txt")) as fh:
        assert fh.read() == "original data"


def test_snapshot_removed_after_success(mgr, tmp_path):
    _write_user(str(tmp_path / "home"), "alice")
    rec = mgr.create_backup("alice")
    mgr.restore_backup("alice", rec.backup_path)
    leftovers = [p for p in os.listdir(str(tmp_path / "home")) if "restore-bak" in p]
    assert leftovers == []


def test_traversal_member_rejected(mgr, tmp_path):
    _write_user(str(tmp_path / "home"), "alice")
    rec = mgr.create_backup("alice")
    evil = str(tmp_path / "evil.tar.gz")
    _make_tar(evil, [("../escaped.txt", b"pwned")])

    assert mgr.restore_backup("alice", evil) is False
    # nothing was written outside the home tree
    assert not (tmp_path / "escaped.txt").exists()


def test_absolute_member_rejected(mgr, tmp_path):
    _write_user(str(tmp_path / "home"), "alice")
    rec = mgr.create_backup("alice")
    absf = str(tmp_path / "abs.tar.gz")
    _make_tar(absf, [("/etc/abs_evil.txt", b"x")])

    assert mgr.restore_backup("alice", absf) is False
    assert not (tmp_path / "etc" / "abs_evil.txt").exists()


def test_unsafe_username_rejected(mgr, tmp_path):
    _write_user(str(tmp_path / "home"), "alice")
    rec = mgr.create_backup("alice")
    # ../etc would escape the home root
    assert mgr.restore_backup("../etc", rec.backup_path) is False
    assert mgr.restore_backup("..", rec.backup_path) is False
    assert mgr.restore_backup("a/../b", rec.backup_path) is False


def test_checksum_mismatch_rejected(mgr, tmp_path):
    _write_user(str(tmp_path / "home"), "alice")
    rec = mgr.create_backup("alice")
    # tamper the on-disk backup so its checksum no longer matches the record
    with open(rec.backup_path, "ab") as fh:
        fh.write(b"corruption")
    assert mgr.restore_backup("alice", rec.backup_path) is False
    # live home data must still be intact (no partial swap)
    with open(os.path.join(str(tmp_path / "home"), "alice", "note.txt")) as fh:
        assert fh.read() == "original data"


def test_fail_closed_strict_mode_denies(mgr, tmp_path):
    _write_user(str(tmp_path / "home"), "alice")
    rec = mgr.create_backup("alice")
    gate.set_strict(True)
    with pytest.raises(PermissionError):
        mgr.restore_backup("alice", rec.backup_path)


def test_is_safe_segment_helper():
    assert _is_safe_segment("alice")
    assert _is_safe_segment("a.b-c_1")
    assert not _is_safe_segment("")
    assert not _is_safe_segment(".")
    assert not _is_safe_segment("..")
    assert not _is_safe_segment("a/b")
    assert not _is_safe_segment("a\\b")
    assert not _is_safe_segment("../etc")


def test_missing_backup_returns_false(mgr):
    assert mgr.restore_backup("nobody", "/nonexistent/path.tar.gz") is False
