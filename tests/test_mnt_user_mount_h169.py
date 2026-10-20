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
UmerOS - regression tests for H169
===================================

H169 (🟡 ``mnt/``): user-mountable mounts were hardened with ``nosuid``
and ``nodev`` but **not** ``noexec``::

    opts = ["user", "noauto", "nosuid", "nodev"]     # no noexec

and ``MountManager.mount`` accepted whatever option string it was handed,
never applying the removable-media hardening despite ``is_under_mnt``
existing on both ``FstabEntry`` and ``MountRecord``.  A non-root user
could therefore mount a USB stick and execute a payload from it — the
same class of bug the ``media`` H157 fix closed for ``/media``.

The fix adds ``noexec`` to both fstab entry builders (opt-out via
``noexec=False``) and makes ``MountManager.mount`` auto-append
``noexec,nosuid,nodev`` to any ``user``/``users`` mount, while preserving
an explicit ``exec``/``suid``/``dev`` chosen by a privileged caller.

Note: these tests use ``tempfile.TemporaryDirectory()`` rather than
pytest's ``tmp_path`` on purpose — ``mnt/fstab.py`` splits fstab lines on
whitespace, so a temp directory whose path contains a space (the Windows
user profile here does) corrupts the field offsets.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import inspect
import os
import tempfile
from pathlib import Path

import pytest

from mnt.fstab import make_user_mount
from mnt.mount_ops import MountManager, harden_user_options
from mnt.user_mount import UserMountManager

REPO = Path(__file__).resolve().parent.parent


def _opts(text: str) -> set:
    return {o.strip() for o in text.split(",") if o.strip()}


# ---------------------------------------------------------------------------
# harden_user_options() — the core policy
# ---------------------------------------------------------------------------

def test_hardens_user_mounts() -> None:
    assert harden_user_options("user,noauto") == "user,noauto,noexec,nosuid,nodev"


def test_hardens_users_mounts() -> None:
    assert harden_user_options("users") == "users,noexec,nosuid,nodev"


def test_leaves_non_user_mounts_alone() -> None:
    assert harden_user_options("defaults") == "defaults"
    assert harden_user_options("ro,noatime") == "ro,noatime"


def test_no_duplicate_flags() -> None:
    parts = harden_user_options("user,noexec,nosuid,nodev").split(",")
    assert parts.count("noexec") == 1
    assert parts.count("nosuid") == 1
    assert parts.count("nodev") == 1


def test_explicit_exec_is_preserved() -> None:
    out = harden_user_options("user,exec")
    assert "exec" in _opts(out)
    assert "noexec" not in _opts(out)


def test_explicit_suid_and_dev_are_preserved() -> None:
    out = _opts(harden_user_options("user,suid,dev"))
    assert "suid" in out and "nosuid" not in out
    assert "dev" in out and "nodev" not in out


def test_preserves_option_order() -> None:
    assert harden_user_options("user,noauto,uid=1000").startswith("user,noauto,uid=1000,")


# ---------------------------------------------------------------------------
# fstab entry builders
# ---------------------------------------------------------------------------

def test_make_user_mount_is_hardened() -> None:
    entry = make_user_mount("/dev/fd0", "/mnt/dosfloppy", "msdos", uid=1000, gid=100)
    assert entry.is_noexec
    assert entry.is_nosuid
    assert entry.is_nodev
    assert entry.is_user_mount


def test_make_user_mount_can_opt_out_of_noexec() -> None:
    entry = make_user_mount("/dev/fd0", "/mnt/x", "msdos", noexec=False)
    assert not entry.is_noexec
    # nosuid/nodev must still be present.
    assert entry.is_nosuid and entry.is_nodev


def test_make_user_mount_noexec_switch_default() -> None:
    assert inspect.signature(make_user_mount).parameters["noexec"].default is True


def test_make_fstab_entry_is_hardened() -> None:
    entry = UserMountManager.make_fstab_entry("/dev/sdb1", "/mnt/usb", "vfat")
    assert "noexec" in _opts(entry.options)
    assert "nosuid" in _opts(entry.options)
    assert "nodev" in _opts(entry.options)


def test_make_fstab_entry_can_opt_out() -> None:
    entry = UserMountManager.make_fstab_entry("/dev/sdb1", "/mnt/usb", "vfat", noexec=False)
    assert "noexec" not in _opts(entry.options)


def test_make_fstab_entry_noexec_switch_default() -> None:
    sig = inspect.signature(UserMountManager.make_fstab_entry)
    assert sig.parameters["noexec"].default is True


# ---------------------------------------------------------------------------
# MountManager.mount enforcement
# ---------------------------------------------------------------------------

def test_mount_manager_hardens_user_mount() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        mp = os.path.join(tmp, "usb")
        os.makedirs(mp)
        mgr = MountManager(proc_mounts=os.path.join(tmp, "none"), enforce_noauto=False)
        rec = mgr.mount("/dev/sdb1", mp, "vfat", "user,noauto,uid=1000")
        assert {"noexec", "nosuid", "nodev"} <= _opts(rec.options)


def test_mount_manager_leaves_system_mount_alone() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        mp = os.path.join(tmp, "data")
        os.makedirs(mp)
        mgr = MountManager(proc_mounts=os.path.join(tmp, "none"), enforce_noauto=False)
        rec = mgr.mount("/dev/sdb1", mp, "ext4", "defaults")
        assert "noexec" not in _opts(rec.options)


def test_mount_manager_respects_explicit_exec() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        mp = os.path.join(tmp, "usb")
        os.makedirs(mp)
        mgr = MountManager(proc_mounts=os.path.join(tmp, "none"), enforce_noauto=False)
        rec = mgr.mount("/dev/sdb1", mp, "vfat", "user,exec")
        assert "exec" in _opts(rec.options)
        assert "noexec" not in _opts(rec.options)


# ---------------------------------------------------------------------------
# End-to-end: UserMountManager.user_mount
# ---------------------------------------------------------------------------

def test_user_mount_end_to_end_is_hardened() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        mnt_root = os.path.join(tmp, "mnt")
        usb = os.path.join(mnt_root, "usb")
        os.makedirs(usb)
        fstab_path = os.path.join(tmp, "fstab")
        with open(fstab_path, "w", encoding="utf-8") as fh:
            fh.write(f"/dev/sdb1 {usb} vfat user,noauto,uid=1000,gid=100 0 0\n")
        mgr = UserMountManager(
            fstab_path=fstab_path, mtab_path=os.path.join(tmp, "mtab")
        )
        rec = mgr.user_mount("alice", "/dev/sdb1", usb, "vfat", uid=1000)
        assert {"noexec", "nosuid", "nodev"} <= _opts(rec.options)


# ---------------------------------------------------------------------------
# Source invariants + self-test contracts
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("relpath", ["mnt/fstab.py", "mnt/user_mount.py"])
def test_source_appends_noexec(relpath: str) -> None:
    src = (REPO / relpath).read_text(encoding="utf-8")
    assert 'opts.append("noexec")' in src


def test_mount_manager_calls_hardening() -> None:
    src = (REPO / "mnt" / "mount_ops.py").read_text(encoding="utf-8")
    assert "options = harden_user_options(options)" in src


def test_all_three_selftests_pass() -> None:
    from mnt.fstab import _selftest as fstab_st
    from mnt.mount_ops import _selftest as mops_st
    from mnt.user_mount import _selftest as umount_st

    assert mops_st() is True
    assert fstab_st() is True
    assert umount_st() is True
