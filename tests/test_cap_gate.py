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
pytest suite for the zero-trust capability gate (core/capability_gate.py) and
its integration into the cap-gate remediation cluster (H227, H233, H267, H273,
H281, H283, H296, H304).

Proves:
  * When a real CapabilityManager is wired, `gate.require` enforces fail-closed
    (denies a PID that lacks the capability, allows one that holds it).
  * When no manager is wired, the gate is permissive (warning) by default, and
    switches to fail-closed under `set_strict(True)`.
  * The wired modules (srv backup/permissions, tmp reaper/permissions, root
    passwd, sbin execute) raise PermissionError when the required capability is
    denied by the wired manager.
"""

import importlib
import os
import sys

from pathlib import Path

import pytest

_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from core.capability_gate import (  # noqa: E402
    CapabilityGate,
    CAP_BACKUP,
    CAP_FS_ADMIN,
    CAP_FS_PERMS,
    CAP_REAPER,
    CAP_SYS_ADMIN,
)
from kernel.capability_manager import CapabilityManager  # noqa: E402


def _make_wired_gate(pid: int, caps) -> CapabilityGate:
    """Build a gate wired to a real CapabilityManager that grants `caps` to `pid`."""
    cm = CapabilityManager()
    cm.register(pid)
    for c in caps:
        cm.grant(pid, c)
    g = CapabilityGate()
    g.wire(cm)
    return g


# ── Core gate behaviour ────────────────────────────────────────────────────

def test_require_denies_when_capability_missing():
    g = _make_wired_gate(pid=4242, caps=[CAP_FS_PERMS])  # has perms, NOT backup
    with pytest.raises(PermissionError):
        g.require(CAP_BACKUP, pid=4242)


def test_require_allows_when_capability_held():
    g = _make_wired_gate(pid=4242, caps=[CAP_BACKUP])
    g.require(CAP_BACKUP, pid=4242)  # must not raise


def test_permissive_by_default_without_manager():
    g = CapabilityGate()  # no manager wired
    g.set_strict(False)
    g.require(CAP_SYS_ADMIN)  # must not raise (permissive)


def test_strict_denies_without_manager():
    g = CapabilityGate()
    g.set_strict(True)
    with pytest.raises(PermissionError):
        g.require(CAP_SYS_ADMIN)


def test_query_reflects_manager():
    g = _make_wired_gate(pid=99, caps=[CAP_REAPER])
    assert g.query(CAP_REAPER, pid=99) is True
    assert g.query(CAP_BACKUP, pid=99) is False


# ── Module integration (fail-closed when the process lacks the cap) ─────────

def test_srv_backup_restore_gated():
    from srv.backup import SrvBackupManager

    g = _make_wired_gate(pid=os.getpid(), caps=[])  # current process lacks backup
    # Patch the module-level gate so the call is enforced.
    import srv.backup as mod
    mod.gate = g
    mgr = SrvBackupManager(backup_dir="__nope_backup__", srv_root="__nope_srv__")
    with pytest.raises(PermissionError):
        mgr.restore_backup("does_not_exist.tar.gz")
    mod.gate = CapabilityGate()  # restore benign default


def test_tmp_reaper_gated():
    from tmp.reaper import TmpReaper

    g = _make_wired_gate(pid=os.getpid(), caps=[])
    import tmp.reaper as mod
    mod.gate = g
    reaper = TmpReaper(tmp_root="__nope_tmp__")
    with pytest.raises(PermissionError):
        reaper.clean_by_age()
    mod.gate = CapabilityGate()


def test_root_passwd_write_gated():
    from root.passwd import PasswdManager, PasswdEntry

    g = _make_wired_gate(pid=os.getpid(), caps=[])
    import root.passwd as mod
    mod.gate = g
    mgr = PasswdManager(path=os.path.join("__nope_etc__", "passwd"))
    with pytest.raises(PermissionError):
        mgr.write([PasswdEntry("root", "x", 0, 0, "root", "/root", "/bin/bash")])
    mod.gate = CapabilityGate()


def test_sbin_execute_gated():
    from sbin.sbin_manager import SbinManager

    g = _make_wired_gate(pid=os.getpid(), caps=[])
    import sbin.sbin_manager as mod
    mod.gate = g
    mgr = SbinManager()
    with pytest.raises(PermissionError):
        mgr.execute("reboot")
    mod.gate = CapabilityGate()


# ── H296 (/usr privileged FS) + H304 (/var managers) integration ─────────────


def test_require_allows_fs_admin_when_held():
    """Gate-level positive path: holding CAP_FS_ADMIN must pass require()."""
    g = _make_wired_gate(pid=os.getpid(), caps=[CAP_FS_ADMIN])
    g.require(CAP_FS_ADMIN)  # current process holds fs.admin -> must not raise


@pytest.mark.parametrize(
    "mod_name,cls_name,method,args",
    [
        # H296 — /usr privileged FS managers. Constructed via __new__ so the
        # class-level BASE_DIR.mkdir() in __init__ never touches the real FS
        # (the gate is the first statement, so no instance state is needed).
        ("usr.sendmail_manager", "SendmailManager", "create_sendmail_symlink", ("/tmp/mta",)),
        ("usr.misc_data_manager", "MiscDataManager", "create_misc_file", ("ascii",)),
        ("usr.bsd_compat_manager", "BSDCompatManager", "add_header", ("foo.h",)),
        ("usr.games_data_manager", "GamesDataManager", "add_game_data", ("chess", "data.txt")),
        ("usr.xml_manager", "XMLManager", "add_directory", ("docbook",)),
        # H304 — /var privileged FHS managers, constructed with a temp var_path
        # so the (post-gate) write lands in a throwaway directory.
        ("var.directory_manager", "VarDirectoryManager", "create_local_directory", ("local_sub",)),
        ("var.spool_manager", "SpoolManager", "write_mailbox", ("alice", "hi")),
        ("var.log_manager", "LogManager", "write_log", ("syslog", "hello")),
    ],
)
def test_fs_admin_gated_modules_deny(mod_name, cls_name, method, args, tmp_path):
    """Every privileged /usr and /var FS entry point must raise PermissionError
    when the current process lacks CAP_FS_ADMIN under a wired CapabilityManager.

    This proves the cap-gate is enforced at the integration seam (not merely at
    the unit level): with a real manager denying the caller, the privileged op is
    blocked before any filesystem mutation.
    """
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, cls_name)
    g = _make_wired_gate(pid=os.getpid(), caps=[])  # current pid lacks fs.admin
    prev = mod.gate
    mod.gate = g
    try:
        if mod_name.startswith("var."):
            inst = cls(var_path=str(tmp_path))
        else:
            # Bypass __init__ (which would mkdir the real /usr BASE_DIR) — the
            # gate is the first statement, so no instance state is needed.
            inst = cls.__new__(cls)
        with pytest.raises(PermissionError):
            getattr(inst, method)(*args)
    finally:
        mod.gate = prev  # restore benign permissive default


def test_var_spool_allows_when_fs_admin_held(tmp_path):
    """Positive integration path: with CAP_FS_ADMIN held, the privileged op
    proceeds and actually writes (proves the gate does not block legitimate,
    authorized callers)."""
    from var.spool_manager import SpoolManager

    g = _make_wired_gate(pid=os.getpid(), caps=[CAP_FS_ADMIN])
    import var.spool_manager as mod
    prev = mod.gate
    mod.gate = g
    try:
        mgr = SpoolManager(var_path=str(tmp_path))
        assert mgr.write_mailbox("alice", "hello") is True
        assert (tmp_path / "spool" / "mail" / "alice").read_text(encoding="utf-8").startswith("hello")
    finally:
        mod.gate = prev


# ── H166 (/mnt privileged mount paths) ────────────────────────────────────────

def test_mnt_mount_manager_denies_without_fs_admin():
    """MountManager.mount/umount/remount must raise when the caller lacks
    CAP_FS_ADMIN under a wired CapabilityManager (H166)."""
    from mnt.mount_ops import MountManager

    g = _make_wired_gate(pid=os.getpid(), caps=[])
    import mnt.mount_ops as mod
    prev = mod.gate
    mod.gate = g
    try:
        mgr = MountManager(proc_mounts="/nonexistent", enforce_noauto=False)
        with pytest.raises(PermissionError):
            mgr.mount("/dev/sdb1", "/mnt/usb", "vfat")
        # Populate an in-memory mount so umount/remount have something to act on.
        from mnt.mount_ops import MountRecord
        mgr._mounts.append(MountRecord(
            device="/dev/sdb1", mount_point="/mnt/usb", fstype="vfat", options="defaults"))
        with pytest.raises(PermissionError):
            mgr.umount("/mnt/usb")
        with pytest.raises(PermissionError):
            mgr.remount("/mnt/usb", "ro")
    finally:
        mod.gate = prev


def test_mnt_mount_point_manager_denies_without_fs_admin():
    """MountPointManager.create/remove must raise without CAP_FS_ADMIN (H166)."""
    from mnt.mount_point import MountPointManager

    g = _make_wired_gate(pid=os.getpid(), caps=[])
    import mnt.mount_point as mod
    prev = mod.gate
    mod.gate = g
    try:
        mgr = MountPointManager("/mnt", enforce_prefix=False)
        with pytest.raises(PermissionError):
            mgr.create("usb")
        with pytest.raises(PermissionError):
            mgr.remove("/mnt/usb")
    finally:
        mod.gate = prev


def test_mnt_fstab_write_denies_without_fs_admin(tmp_path):
    """Fstab.write_file (/etc/fstab) must raise without CAP_FS_ADMIN (H166)."""
    from mnt.fstab import Fstab

    g = _make_wired_gate(pid=os.getpid(), caps=[])
    import mnt.fstab as mod
    prev = mod.gate
    mod.gate = g
    try:
        fstab = Fstab()
        with pytest.raises(PermissionError):
            fstab.write_file(str(tmp_path / "fstab"))
    finally:
        mod.gate = prev


def test_mnt_mount_manager_allows_with_fs_admin(tmp_path):
    """Positive path: with CAP_FS_ADMIN held, MountManager.mount proceeds (H166)."""
    from mnt.mount_ops import MountManager

    g = _make_wired_gate(pid=os.getpid(), caps=[CAP_FS_ADMIN])
    import mnt.mount_ops as mod
    prev = mod.gate
    mod.gate = g
    try:
        mgr = MountManager(proc_mounts="/nonexistent", enforce_noauto=False)
        mp = os.path.join(str(tmp_path), "usb")
        os.makedirs(mp)
        rec = mgr.mount("/dev/sdb1", mp, "vfat")
        assert rec.mount_point == mp
    finally:
        mod.gate = prev


# ── H156 (/media privileged mount paths) ──────────────────────────────────────

def test_media_mount_ops_denies_without_fs_admin():
    """media.mount_ops.mount/unmount/remount must raise without CAP_FS_ADMIN (H156)."""
    from media.mount_ops import mount, unmount, remount, set_simulation, clear_sim_mounts

    set_simulation(True)
    clear_sim_mounts()
    g = _make_wired_gate(pid=os.getpid(), caps=[])
    import media.mount_ops as mod
    prev = mod.gate
    mod.gate = g
    try:
        with pytest.raises(PermissionError):
            mount("/dev/sdb1", "/media/test")
        with pytest.raises(PermissionError):
            unmount("/media/test")
        with pytest.raises(PermissionError):
            remount("/media/test", ["ro"])
    finally:
        mod.gate = prev
        clear_sim_mounts()


def test_media_udisks2_mount_denies_without_fs_admin():
    """UDisks2Client.mount funnels through the gated seam, so it raises (H156)."""
    from media.udisks2 import UDisks2Client, UDisks2Block, UDisks2Drive
    from media.mount_ops import set_simulation, clear_sim_mounts

    set_simulation(True)
    clear_sim_mounts()
    g = _make_wired_gate(pid=os.getpid(), caps=[])
    import media.mount_ops as mod
    prev = mod.gate
    mod.gate = g
    try:
        client = UDisks2Client(simulate=True)
        drive = UDisks2Drive(
            object_path="/org/freedesktop/UDisks2/drives/usb_sdb",
            model="USB", size=32_000_000_000, removable=True, media="usb")
        block = UDisks2Block(
            object_path="/org/freedesktop/UDisks2/block_devices/sdb1",
            device="/dev/sdb1", id_type="vfat", id_usage="filesystem",
            id_label="MYUSB", drive_object_path="/org/freedesktop/UDisks2/drives/usb_sdb")
        client.register_drive(drive)
        client.register_block(block)
        with pytest.raises(PermissionError):
            client.mount(block.object_path)
    finally:
        mod.gate = prev
        clear_sim_mounts()


def test_media_auto_mount_hotplug_denies_without_fs_admin():
    """auto_mount._handle_hotplug on ADD funnels through the gated seam (H156)."""
    from media.auto_mount import AutoMountDaemon, AutoMountPolicy
    from media.hotplug import HotplugBus, HotplugEvent, HotplugAction
    from media.media_types import MediaType
    from media.mount_ops import set_simulation, clear_sim_mounts

    set_simulation(True)
    clear_sim_mounts()
    g = _make_wired_gate(pid=os.getpid(), caps=[])
    import media.mount_ops as mod
    prev = mod.gate
    mod.gate = g
    try:
        bus = HotplugBus()
        daemon = AutoMountDaemon(bus=bus, policy=AutoMountPolicy(), base_path="/media")
        daemon.start()
        with pytest.raises(PermissionError):
            daemon._handle_hotplug(HotplugEvent(
                device_path="/dev/sdb1", action=HotplugAction.ADD,
                media_type=MediaType.USB))
    finally:
        mod.gate = prev
        clear_sim_mounts()


def test_media_mount_ops_allows_with_fs_admin(tmp_path):
    """Positive path: with CAP_FS_ADMIN held, media.mount_ops.mount proceeds (H156)."""
    from media.mount_ops import mount, is_mounted, set_simulation, clear_sim_mounts

    set_simulation(True)
    clear_sim_mounts()
    g = _make_wired_gate(pid=os.getpid(), caps=[CAP_FS_ADMIN])
    import media.mount_ops as mod
    prev = mod.gate
    mod.gate = g
    try:
        mp = str(tmp_path / "media" / "test")
        r = mount("/dev/sdb1", mp)
        assert r.success
        assert is_mounted(mp)
    finally:
        mod.gate = prev
        clear_sim_mounts()
