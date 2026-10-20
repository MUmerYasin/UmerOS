# ---------------------------------------------------------------------------
# UmerOS — H175 regression tests
#
# `mnt/mount_ops.py` used to build *shell-shaped command strings* purely to
# log them:
#
#     cmd = "umount"
#     cmd += " " + " ".join(flag_parts)
#     cmd += f" {mount_point}"
#     log.info(cmd)
#
# Nothing executed them, but the lines read exactly like the code was about
# to shell out to `mount(8)`/`umount(8)` — and because the fields are
# space-separated, a device path or mount point containing a space silently
# splits into what looks like two arguments, while `$(...)` or `;` in a path
# reads like a shell injection attempt.
#
# These tests pin the fix: structured `key=value!r` intent lines, the dead
# argv construction removed, and every field preserved.
# ---------------------------------------------------------------------------

import logging
import os
import tempfile

import pytest

from mnt.audit import AuditLog
from mnt.mount_ops import (
    MountManager,
    MountRecord,
    format_mount_intent,
)


@pytest.fixture
def manager():
    with tempfile.TemporaryDirectory() as td:
        root = os.path.join(td, "mnt")
        os.makedirs(os.path.join(root, "plain"))
        mgr = MountManager(proc_mounts=os.path.join(td, "absent"), mnt_root=root)
        mgr._root = root
        yield mgr


# -- format_mount_intent ---------------------------------------------------


def test_fields_are_repr_quoted():
    """A space in a path must not look like an argv separator."""
    line = format_mount_intent(
        "mount", device="/dev/sdb1", target="/mnt/my usb", fstype="vfat"
    )
    assert "'/mnt/my usb'" in line
    assert " /mnt/my usb " not in line


def test_shell_metacharacters_stay_inert():
    """`$(...)` and `;` must stay inside one quoted value."""
    line = format_mount_intent("umount", target="/mnt/$(rm -rf /)", mode="lazy")
    assert "'/mnt/$(rm -rf /)'" in line
    assert line.count("mode=") == 1


def test_semicolon_in_path_is_not_a_command_separator():
    line = format_mount_intent("remount", target="/mnt/a;b", options="rw")
    assert "'/mnt/a;b'" in line
    assert not line.strip().endswith(";")


def test_operation_and_simulated_marker():
    line = format_mount_intent("mount", device="/dev/sdb1")
    assert line.startswith("mount ")
    assert line.endswith("(simulated)")


def test_percent_in_a_path_is_not_a_format_spec():
    """`%s`/`%d` in a path must survive rendering untouched."""
    line = format_mount_intent(
        "mount", device="/dev/100%s", target="/mnt/x%d", fstype="vfat"
    )
    assert "'/dev/100%s'" in line
    assert "'/mnt/x%d'" in line


def test_order_of_fields_is_preserved():
    line = format_mount_intent("mount", a="1", b="2", c="3")
    assert line.index("a='1'") < line.index("b='2'") < line.index("c='3'")


def test_no_fields_still_renders():
    assert format_mount_intent("umount") == "umount [] (simulated)"


# -- the log sites are intent lines, not argv -------------------------------


def test_mount_logs_intent(manager, caplog):
    with caplog.at_level(logging.INFO, logger="UmerOS.Mnt.MountOps"):
        manager.mount("/dev/sdb1", manager._root + "/plain", "vfat")
    line = next(r.getMessage() for r in caplog.records if "mount [" in r.getMessage())
    for field in ("device='/dev/sdb1'", "target=", "fstype='vfat'", "options="):
        assert field in line
    assert "(simulated)" in line
    # must not look like an argv
    assert " -t " not in line
    assert " -o " not in line


def test_umount_logs_mode_not_argv(manager, caplog):
    manager.mount("/dev/sdb1", manager._root + "/plain", "vfat")
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="UmerOS.Mnt.MountOps"):
        manager.umount(manager._root + "/plain", lazy=True, force=True)
    line = next(r.getMessage() for r in caplog.records if "umount [" in r.getMessage())
    assert "mode='lazy,force,remount-ro'" in line
    assert "target=" in line
    assert "device='/dev/sdb1'" in line
    assert not line.startswith("umount --")


def test_umount_remount_ro_default_is_preserved(manager, caplog):
    """`remount_ro=True` is the pre-existing default; the mode must show it."""
    manager.mount("/dev/sdb1", manager._root + "/plain", "vfat")
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="UmerOS.Mnt.MountOps"):
        manager.umount(manager._root + "/plain")
    line = next(r.getMessage() for r in caplog.records if "umount [" in r.getMessage())
    assert "mode='remount-ro'" in line


def test_umount_ro_filesystem_drops_remount_ro(manager, caplog):
    """Read-only filesystem: `remount-ro` is skipped, as before H175."""
    manager.mount("/dev/sdb1", manager._root + "/plain", "vfat", "ro")
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="UmerOS.Mnt.MountOps"):
        manager.umount(manager._root + "/plain")
    line = next(r.getMessage() for r in caplog.records if "umount [" in r.getMessage())
    assert "mode='normal'" in line


def test_remount_logs_intent_with_previous(manager, caplog):
    manager.mount("/dev/sdb1", manager._root + "/plain", "vfat", "rw")
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="UmerOS.Mnt.MountOps"):
        manager.remount(manager._root + "/plain", "ro")
    line = next(
        r.getMessage() for r in caplog.records if "remount [" in r.getMessage()
    )
    assert "options='ro'" in line
    assert "previous='rw'" in line
    assert "(was: " not in line  # the old argv-ish tail is gone


def test_remount_all_logs_no_fake_command(manager, caplog):
    """`umount_all` routes through `umount`, so it inherits the fix."""
    manager.mount("/dev/sdb1", manager._root + "/plain", "vfat")
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="UmerOS.Mnt.MountOps"):
        manager.umount_all()
    lines = [r.getMessage() for r in caplog.records]
    assert any("umount [" in l and "(simulated)" in l for l in lines)
    # a bare argv (no `key=value` fields, no simulated marker) would be old-style
    assert not any(
        l.startswith("umount ") and "[" not in l and "(simulated)" not in l
        for l in lines
    )


# -- no dead argv construction remains -------------------------------------


def test_umount_has_no_cmd_local():
    locals_ = MountManager.umount.__code__.co_varnames
    assert "cmd" not in locals_


def test_umount_keeps_mode_parts():
    assert "mode_parts" in MountManager.umount.__code__.co_varnames


def test_no_flag_parts_either():
    assert "flag_parts" not in MountManager.umount.__code__.co_varnames


def test_mount_record_repr_agrees_with_the_log_convention():
    """Both use repr()-quoting, so record reprs and log lines now match."""
    rec = MountRecord(
        device="/dev/sdb1", mount_point="/mnt/my usb",
        fstype="vfat", options="defaults",
    )
    assert "'/mnt/my usb'" in repr(rec)
    assert repr(rec).count("'") >= 4


# -- behaviour is unchanged -------------------------------------------------


def test_mount_still_records(manager):
    rec = manager.mount("/dev/sdb1", manager._root + "/plain", "vfat")
    assert manager.is_mounted(manager._root + "/plain")
    assert rec.fstype == "vfat"


def test_umount_still_removes(manager):
    manager.mount("/dev/sdb1", manager._root + "/plain", "vfat")
    manager.umount(manager._root + "/plain")
    assert not manager.is_mounted(manager._root + "/plain")


def test_umount_all_still_works(manager):
    manager.mount("/dev/sdb1", manager._root + "/plain", "vfat")
    mgr = manager.umount_all()
    assert len(mgr) == 1


def test_audit_trail_is_unchanged(manager):
    """The audit log is separate and must not be affected by the log-line fix."""
    audit = AuditLog(log_path=os.path.join(manager._root, "audit.log"))
    mgr = MountManager(
        proc_mounts="/nonexistent",
        mnt_root=manager._root,
        audit=audit,
    )
    mgr.mount("/dev/sdb1", os.path.join(manager._root, "plain"), "vfat")
    records = audit.records
    assert records
    assert any(r.mount_point and r.device for r in records)


def test_audit_trail_still_records_umount(manager):
    audit = AuditLog(log_path=os.path.join(manager._root, "audit.log"))
    mgr = MountManager(
        proc_mounts="/nonexistent", mnt_root=manager._root, audit=audit
    )
    mgr.mount("/dev/sdb1", os.path.join(manager._root, "plain"), "vfat")
    mgr.umount(os.path.join(manager._root, "plain"))
    points = {r.mount_point for r in audit.records}
    assert os.path.join(manager._root, "plain") in points
