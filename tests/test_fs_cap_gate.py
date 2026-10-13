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
pytest suite for  — capability gating on VFS/QFS mutations.
 `VirtualFileSystem` (`mkdir`/`write_file`/`delete`) and `QFS`
(`write_file`/`delete_file`/`snapshot`/`restore_snapshot`) mutated the
filesystem with **no** capability check (same family as H60/H66/H73). The fix
requires `fs.write` for file-level mutations and `fs.admin` for whole-filesystem
snapshot/restore — fail-closed when a `CapabilityManager` is wired, permissive
(warning) standalone.
"""

import os
import sys

import pytest

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

from core.capability_gate import gate, CAP_FS_WRITE, CAP_FS_ADMIN  # noqa: E402
from fs.qfs import QFS  # noqa: E402
from fs.vfs import VirtualFileSystem  # noqa: E402


class _Deny:
    def query(self, pid, cap):
        return False


class _AllowWriteOnly:
    def query(self, pid, cap):
        return cap == CAP_FS_WRITE


class _AllowAdmin:
    def query(self, pid, cap):
        return cap in (CAP_FS_WRITE, CAP_FS_ADMIN)


@pytest.fixture(autouse=True)
def _gate_state():
    was_strict = gate.strict
    gate.set_strict(False)
    gate.unwire()
    yield
    gate.set_strict(was_strict)
    gate.unwire()


# ── permissive standalone ───────────────────────────────────────────────────

def test_permissive_default_allows_mutations():
    v = VirtualFileSystem()
    v.write_file("/a/b.txt", b"hello")
    assert v.read_file("/a/b.txt") == b"hello"
    v.mkdir("/c")
    assert v.delete("/a/b.txt") is True


# ── strict mode fails closed ────────────────────────────────────────────────

@pytest.mark.parametrize("op", ["write", "mkdir", "delete"])
def test_strict_mode_denies_vfs_mutations(op):
    v = VirtualFileSystem()
    v.write_file("/keep.txt", b"k")
    gate.set_strict(True)
    with pytest.raises(PermissionError):
        if op == "write":
            v.write_file("/x.txt", b"x")
        elif op == "mkdir":
            v.mkdir("/y")
        else:
            v.delete("/keep.txt")


def test_strict_mode_denies_qfs_snapshot():
    q = QFS()
    gate.set_strict(True)
    with pytest.raises(PermissionError):
        q.snapshot()


# ── wired manager (fail-closed) ─────────────────────────────────────────────

def test_wired_deny_blocks_write():
    v = VirtualFileSystem()
    gate.wire(_Deny())
    with pytest.raises(PermissionError):
        v.write_file("/x.txt", b"x")


def test_wired_write_only_allows_write_but_not_snapshot():
    q = QFS()
    gate.wire(_AllowWriteOnly())
    q.write_file("/z.txt", b"z")          # fs.write -> allowed
    with pytest.raises(PermissionError):  # fs.admin -> denied
        q.snapshot()


def test_wired_admin_allows_snapshot_and_restore():
    q = QFS()
    gate.wire(_AllowAdmin())
    q.write_file("/z.txt", b"z")
    snap = q.snapshot()
    assert snap
    q.write_file("/z.txt", b"zzz")
    assert q.restore_snapshot(snap) is True


# ── read paths stay ungated ─────────────────────────────────────────────────

def test_reads_are_not_gated():
    v = VirtualFileSystem()
    v.write_file("/r.txt", b"data")
    gate.wire(_Deny())
    assert v.read_file("/r.txt") == b"data"
    assert v.exists("/r.txt") is True
    assert v.ls("/") == ["r.txt"]
