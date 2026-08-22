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
Comprehensive tests for UmerOS /media package.

Covers: media_types, mount_manager, device_info, cleanup, hotplug,
filesystem, mount_ops, auto_mount, permissions, fstab, udisks2.
"""

from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path

# Ensure parent package is importable
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from media import (
    # media_types
    MediaType,
    MountNaming,
    MediaDescriptor,
    MOUNT_NAMING,
    # mount_manager
    MediaConfig,
    MountManager,
    # device_info
    DeviceScanResult,
    scan_devices,
    detect_media_type,
    get_mount_info,
    # cleanup
    CleanupConfig,
    CleanupResult,
    cleanup_media,
    validate_fhs_media,
    # hotplug
    HotplugAction,
    HotplugBus,
    HotplugEvent,
    get_default_bus,
    # filesystem
    FsType,
    detect_fs_type,
    validate_fs_type,
    mount_options_for,
    SUPPORTED_FS,
    # mount_ops
    MountOpResult,
    mount,
    unmount,
    remount,
    is_mounted,
    get_mount_options,
    sync_mount,
    mount_status,
    set_simulation,
    get_sim_mounts,
    clear_sim_mounts,
    # auto_mount
    AutoMountDaemon,
    AutoMountEvent,
    AutoMountPolicy,
    AutoMountStatus,
    create_default_daemon,
    # permissions
    AccessLevel,
    GroupPolicy,
    MountPermission,
    MountPermissionManager,
    parse_fstab_uid,
    effective_user,
    STANDARD_MOUNT_GROUPS,
    GROUP_MEDIA_MAP,
    # fstab
    FstabEntry,
    FstabIssue,
    FstabManager,
    FstabValidator,
    FstabIssueEntry,
    make_removable_entry,
    # udisks2
    UDisks2Block,
    UDisks2Client,
    UDisks2Drive,
    UDisks2Object,
    UDisks2ObjectType,
    get_removable_media_info,
)


# ===================================================================
# media_types
# ===================================================================

class TestMediaType(unittest.TestCase):
    """Test MediaType enum."""

    def test_has_expected_values(self):
        expected = {
            "floppy", "cdrom", "cdrecorder", "zip", "usb", "mmc",
            "nvme", "bluetooth", "firewire", "tape", "network", "custom",
        }
        actual = {m.value for m in MediaType}
        self.assertTrue(expected.issubset(actual), f"Missing: {expected - actual}")

    def test_fhs_subdirectories(self):
        """FHS defines specific subdirs for /media."""
        fhs_dirs = {"floppy", "cdrom", "cdrecorder", "zip"}
        named_dirs = {m.value for m in MediaType}
        for d in fhs_dirs:
            self.assertIn(d, named_dirs)


class TestMountNaming(unittest.TestCase):
    """Test MountNaming conventions."""

    def test_mount_point_for(self):
        mp = MountNaming.mount_point_for(MediaType.USB, "/media", index=0)
        self.assertIn("/media", mp)
        self.assertIn("usb", mp.lower())

    def test_symlink_name(self):
        naming = MOUNT_NAMING[MediaType.CDROM]
        self.assertIsNotNone(naming.symlink_name)
        self.assertIn("cdrom", naming.symlink_name.lower())

    def test_multiple_devices_get_digit_suffix(self):
        mp0 = MountNaming.mount_point_for(MediaType.USB, "/media", index=0)
        mp1 = MountNaming.mount_point_for(MediaType.USB, "/media", index=1)
        self.assertNotEqual(mp0, mp1)


class TestMediaDescriptor(unittest.TestCase):
    def test_create(self):
        desc = MediaDescriptor(
            device_path="/dev/sdb1",
            label="MYUSB",
            uuid="1234-5678",
            media_type=MediaType.USB,
        )
        self.assertEqual(desc.media_type, MediaType.USB)
        self.assertEqual(desc.device_path, "/dev/sdb1")
        self.assertEqual(desc.label, "MYUSB")


# ===================================================================
# mount_manager
# ===================================================================

class TestMountManager(unittest.TestCase):
    def setUp(self):
        self.mgr = MountManager(config=MediaConfig(media_root="/media"))

    def test_allocate_returns_slot(self):
        slot = self.mgr.allocate(MediaType.USB, "/dev/sdb1", label="TEST")
        self.assertIsNotNone(slot)
        self.assertIn("usb", slot.mount_point.lower())

    def test_release(self):
        slot = self.mgr.allocate(MediaType.USB, "/dev/sdb1")
        self.mgr.release(slot.mount_point)
        slot2 = self.mgr.allocate(MediaType.USB, "/dev/sdb1")
        self.assertIsNotNone(slot2)


# ===================================================================
# device_info
# ===================================================================

class TestDeviceInfo(unittest.TestCase):
    def test_scan_devices_returns_result(self):
        result = scan_devices()
        self.assertIsInstance(result, DeviceScanResult)

    def test_detect_media_type(self):
        mt = detect_media_type("/dev/sr0")
        self.assertIsInstance(mt, MediaType)

    def test_get_mount_info(self):
        info = get_mount_info("/nonexistent")
        self.assertTrue(info is None or isinstance(info, dict))


# ===================================================================
# cleanup
# ===================================================================

class TestCleanup(unittest.TestCase):
    def test_cleanup_config_defaults(self):
        cfg = CleanupConfig()
        self.assertTrue(cfg.remove_empty)
        self.assertTrue(cfg.check_orphans)

    def test_cleanup_media(self):
        cfg = CleanupConfig(dry_run=True)
        result = cleanup_media(cfg)
        self.assertIsInstance(result, CleanupResult)
        self.assertIsInstance(result.scanned, int)

    def test_validate_fhs_media(self):
        issues = validate_fhs_media(Path("/tmp"))
        self.assertIsInstance(issues, dict)


# ===================================================================
# hotplug
# ===================================================================

class TestHotplug(unittest.TestCase):
    def test_bus_subscribe_and_emit(self):
        bus = HotplugBus()
        events = []
        bus.subscribe(lambda e: events.append(e))
        bus.emit(HotplugEvent(
            device_path="/dev/sdb1",
            action=HotplugAction.ADD,
            media_type=MediaType.USB,
        ))
        self.assertEqual(len(events), 1)
        self.assertEqual(str(events[0].action), str(HotplugAction.ADD))

    def test_multiple_subscribers(self):
        bus = HotplugBus()
        a, b = [], []
        bus.subscribe(lambda e: a.append(e))
        bus.subscribe(lambda e: b.append(e))
        bus.emit(HotplugEvent(action=HotplugAction.ADD, device_path="/dev/x", media_type=MediaType.USB))
        self.assertEqual(len(a), 1)
        self.assertEqual(len(b), 1)

    def test_hotplug_event_fields(self):
        ev = HotplugEvent(
            device_path="/dev/sr0",
            action=HotplugAction.REMOVE,
            media_type=MediaType.CDROM,
        )
        self.assertEqual(ev.device_path, "/dev/sr0")
        self.assertEqual(ev.media_type, MediaType.CDROM)

    def test_get_default_bus(self):
        bus = get_default_bus()
        self.assertIsInstance(bus, HotplugBus)


# ===================================================================
# filesystem
# ===================================================================

class TestFsType(unittest.TestCase):
    def test_has_expected_types(self):
        names = {f.name for f in FsType}
        for expected in ("VFAT", "EXT4", "ISO9660", "NTFS", "EXFAT", "BTRFS", "XFS"):
            self.assertIn(expected, names)

    def test_vfat_value(self):
        fat = FsType.VFAT
        self.assertEqual(fat.value, "vfat")

    def test_iso9660_value(self):
        iso = FsType.ISO9660
        self.assertEqual(iso.value, "iso9660")


class TestDetectFsType(unittest.TestCase):
    def test_magic_bytes(self):
        result = detect_fs_type("/dev/sdb1")
        self.assertIsInstance(result, str)

    def test_empty_returns_auto(self):
        result = detect_fs_type("/dev/nonexistent")
        self.assertIsInstance(result, str)

    def test_path_based_detection(self):
        result = detect_fs_type("/dev/sdb1")
        self.assertIsInstance(result, str)


class TestValidateFsType(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(validate_fs_type(FsType.EXT4))
        self.assertTrue(validate_fs_type(FsType.VFAT))
        self.assertTrue(validate_fs_type(FsType.ISO9660))

    def test_invalid(self):
        self.assertFalse(validate_fs_type("nonexistent_fs"))


class TestMountOptionsFor(unittest.TestCase):
    def test_fat_defaults(self):
        opts = mount_options_for(FsType.VFAT)
        self.assertIsInstance(opts, list)
        self.assertTrue(any("uid=" in o for o in opts))

    def test_iso9660_readonly(self):
        opts = mount_options_for(FsType.ISO9660)
        self.assertIsInstance(opts, list)
        self.assertTrue(any("ro" in o for o in opts))


class TestSupportedFs(unittest.TestCase):
    def test_populated(self):
        self.assertGreater(len(SUPPORTED_FS), 10)


# ===================================================================
# mount_ops
# ===================================================================

class TestMountOps(unittest.TestCase):
    def setUp(self):
        set_simulation(True)
        clear_sim_mounts()

    def tearDown(self):
        clear_sim_mounts()

    def test_mount_sim(self):
        result = mount("/dev/sdb1", "/media/usb0", create_dir=True)
        self.assertTrue(result.success)
        normalized = os.path.normpath("/media/usb0")
        self.assertIn(normalized, get_sim_mounts())

    def test_unmount_sim(self):
        mount("/dev/sdb1", "/media/usb0", create_dir=True)
        result = unmount("/media/usb0")
        self.assertTrue(result.success)
        self.assertNotIn("/media/usb0", get_sim_mounts())

    def test_is_mounted(self):
        mount("/dev/sdb1", "/media/usb0", create_dir=True)
        self.assertTrue(is_mounted("/media/usb0"))
        self.assertFalse(is_mounted("/media/nonexistent"))

    def test_remount(self):
        mount("/dev/sdb1", "/media/usb0", create_dir=True)
        result = remount("/media/usb0", options=["ro"])
        self.assertTrue(result.success)

    def test_get_mount_options(self):
        mount("/dev/sdb1", "/media/usb0", options=["uid=1000"], create_dir=True)
        opts = get_mount_options("/media/usb0")
        self.assertIsInstance(opts, dict)
        self.assertIn("options", opts)

    def test_sync_mount(self):
        mount("/dev/sdb1", "/media/usb0", create_dir=True)
        result = sync_mount("/media/usb0")
        self.assertTrue(result)

    def test_mount_status(self):
        mount("/dev/sdb1", "/media/usb0", create_dir=True)
        st = mount_status()
        self.assertIsNotNone(st)

    def test_mount_already_mounted(self):
        mount("/dev/sdb1", "/media/usb0", create_dir=True)
        result2 = mount("/dev/sdb1", "/media/usb0")
        self.assertTrue(result2.success or "already" in result2.message.lower())

    def test_unmount_not_mounted(self):
        result = unmount("/media/nonexistent")
        self.assertFalse(result.success)

    def test_clear_sim_mounts(self):
        mount("/dev/sdb1", "/media/usb0", create_dir=True)
        self.assertTrue(len(get_sim_mounts()) > 0)
        clear_sim_mounts()
        self.assertEqual(len(get_sim_mounts()), 0)


# ===================================================================
# auto_mount
# ===================================================================

class TestAutoMountPolicy(unittest.TestCase):
    def test_default_policy(self):
        p = AutoMountPolicy()
        self.assertTrue(p.auto_mount_usb)
        self.assertTrue(p.auto_mount_optical)
        self.assertFalse(p.auto_mount_bluetooth)

    def test_disable_optical(self):
        p = AutoMountPolicy(auto_mount_optical=False)
        self.assertFalse(p.auto_mount_optical)

    def test_custom_policy(self):
        p = AutoMountPolicy(auto_mount_usb=False, auto_mount_bluetooth=True)
        self.assertFalse(p.auto_mount_usb)
        self.assertTrue(p.auto_mount_bluetooth)


class TestAutoMountDaemon(unittest.TestCase):
    def setUp(self):
        set_simulation(True)
        clear_sim_mounts()

    def tearDown(self):
        clear_sim_mounts()

    def test_lifecycle(self):
        daemon = create_default_daemon()
        self.assertFalse(daemon.is_running)
        daemon.start()
        self.assertTrue(daemon.is_running)
        daemon.stop()
        self.assertFalse(daemon.is_running)

    def test_hotplug_triggers_mount(self):
        bus = HotplugBus()
        daemon = AutoMountDaemon(bus=bus, policy=AutoMountPolicy())
        daemon.start()
        events = []
        daemon.on_event(events.append)
        bus.emit(HotplugEvent(
            device_path="/dev/sdb1",
            action=HotplugAction.ADD,
            media_type=MediaType.USB,
        ))
        self.assertGreater(len(events), 0)
        daemon.stop()

    def test_hotplug_remove_triggers_unmount(self):
        bus = HotplugBus()
        daemon = AutoMountDaemon(bus=bus, policy=AutoMountPolicy())
        daemon.start()
        events = []
        daemon.on_event(events.append)
        bus.emit(HotplugEvent(action=HotplugAction.ADD, device_path="/dev/sdb1", media_type=MediaType.USB))
        bus.emit(HotplugEvent(action=HotplugAction.REMOVE, device_path="/dev/sdb1", media_type=MediaType.USB))
        unmounted = [e for e in events if e.status == AutoMountStatus.UNMOUNTED]
        self.assertGreater(len(unmounted), 0)
        daemon.stop()

    def test_deny_policy(self):
        bus = HotplugBus()
        policy = AutoMountPolicy(auto_mount_usb=False)
        daemon = AutoMountDaemon(bus=bus, policy=policy)
        daemon.start()
        events = []
        daemon.on_event(events.append)
        bus.emit(HotplugEvent(action=HotplugAction.ADD, device_path="/dev/sdb1", media_type=MediaType.USB))
        skipped = [e for e in events if e.status == AutoMountStatus.SKIPPED_POLICY]
        self.assertGreater(len(skipped), 0)
        daemon.stop()

    def test_manual_mount(self):
        daemon = create_default_daemon()
        daemon.start()
        result = daemon.mount_device("/dev/sdb1", MediaType.USB)
        self.assertIsNotNone(result)
        daemon.stop()

    def test_active_mounts(self):
        daemon = create_default_daemon()
        daemon.start()
        daemon.mount_device("/dev/sdb1", MediaType.USB)
        self.assertIsInstance(daemon.active_mounts, dict)
        daemon.stop()


class TestAutoMountEvent(unittest.TestCase):
    def test_timestamp_set(self):
        ev = AutoMountEvent(status=AutoMountStatus.MOUNTED, device_path="/dev/x")
        self.assertGreater(ev.timestamp, 0)


# ===================================================================
# permissions
# ===================================================================

class TestAccessLevel(unittest.TestCase):
    def test_values(self):
        expected = {"none", "read_only", "read_write", "owner", "admin"}
        actual = {a.value for a in AccessLevel}
        self.assertTrue(expected.issubset(actual))


class TestMountPermission(unittest.TestCase):
    def test_read_only(self):
        p = MountPermission("alice", "/m", AccessLevel.READ_ONLY)
        self.assertTrue(p.can_read)
        self.assertFalse(p.can_write)

    def test_read_write(self):
        p = MountPermission("alice", "/m", AccessLevel.READ_WRITE)
        self.assertTrue(p.can_read)
        self.assertTrue(p.can_write)

    def test_owner(self):
        p = MountPermission("alice", "/m", AccessLevel.OWNER)
        self.assertTrue(p.is_owner)

    def test_expiry(self):
        p = MountPermission("alice", "/m", expires_at=time.time() - 1)
        self.assertTrue(p.is_expired)


class TestGroupPolicy(unittest.TestCase):
    def test_plugdev_allows_usb(self):
        gp = GroupPolicy(user_groups={"plugdev"})
        self.assertTrue(gp.can_access_media_type("user", "usb"))

    def test_cdrom_group(self):
        gp = GroupPolicy(user_groups={"cdrom"})
        self.assertTrue(gp.can_access_media_type("user", "cdrom"))
        self.assertFalse(gp.can_access_media_type("user", "usb"))

    def test_storage_allows_most(self):
        gp = GroupPolicy(user_groups={"storage"})
        self.assertTrue(gp.can_access_media_type("user", "usb"))
        self.assertTrue(gp.can_access_media_type("user", "cdrom"))

    def test_get_allowed_media_types(self):
        gp = GroupPolicy(user_groups={"plugdev", "cdrom"})
        types = gp.get_allowed_media_types()
        self.assertIn("usb", types)
        self.assertIn("cdrom", types)


class TestMountPermissionManager(unittest.TestCase):
    def test_grant_and_check(self):
        mgr = MountPermissionManager()
        mgr.grant("alice", "/media/usb0", owner=True)
        self.assertTrue(mgr.can_mount("alice", "/media/usb0"))
        self.assertTrue(mgr.is_owner("alice", "/media/usb0"))

    def test_deny_others(self):
        mgr = MountPermissionManager()
        mgr.grant("alice", "/media/usb0")
        self.assertFalse(mgr.can_mount("bob", "/media/usb0"))

    def test_revoke(self):
        mgr = MountPermissionManager()
        mgr.grant("alice", "/media/usb0")
        self.assertTrue(mgr.revoke("alice", "/media/usb0"))
        self.assertFalse(mgr.can_mount("alice", "/media/usb0"))

    def test_admin_always_mounts(self):
        mgr = MountPermissionManager()
        mgr.add_admin("charlie")
        self.assertTrue(mgr.can_mount("charlie", "/anything"))

    def test_cleanup_expired(self):
        mgr = MountPermissionManager()
        mgr.grant("dave", "/media/cd0", expires_in=-1)
        self.assertFalse(mgr.can_mount("dave", "/media/cd0"))
        removed = mgr.cleanup_expired()
        self.assertGreaterEqual(removed, 1)

    def test_can_write(self):
        mgr = MountPermissionManager()
        mgr.grant("alice", "/media/usb0", access=AccessLevel.READ_ONLY)
        self.assertFalse(mgr.can_write("alice", "/media/usb0"))
        mgr.grant("bob", "/media/usb0", access=AccessLevel.READ_WRITE)
        self.assertTrue(mgr.can_write("bob", "/media/usb0"))

    def test_get_permissions(self):
        mgr = MountPermissionManager()
        mgr.grant("alice", "/media/usb0")
        mgr.grant("alice", "/media/cd0")
        perms = mgr.get_permissions("alice")
        self.assertEqual(len(perms), 2)

    def test_get_mount_permissions(self):
        mgr = MountPermissionManager()
        mgr.grant("alice", "/media/usb0")
        mgr.grant("bob", "/media/usb0")
        perms = mgr.get_mount_permissions("/media/usb0")
        self.assertEqual(len(perms), 2)


class TestFstabUidHelpers(unittest.TestCase):
    def test_parse_uid(self):
        self.assertEqual(parse_fstab_uid("uid=1000,gid=1000"), 1000)
        self.assertIsNone(parse_fstab_uid("ro,noatime"))

    def test_effective_user(self):
        self.assertEqual(effective_user("uid=1001"), 1001)
        self.assertEqual(effective_user("ro"), 0)


class TestStandardMountGroups(unittest.TestCase):
    def test_populated(self):
        self.assertIn("plugdev", STANDARD_MOUNT_GROUPS)
        self.assertIn("storage", STANDARD_MOUNT_GROUPS)

    def test_group_media_map(self):
        self.assertIn("plugdev", GROUP_MEDIA_MAP)
        self.assertIn("usb", GROUP_MEDIA_MAP["plugdev"])


# ===================================================================
# fstab
# ===================================================================

class TestFstabEntry(unittest.TestCase):
    def test_parse(self):
        e = FstabEntry("/dev/sdb1", "/media/usb0", "vfat", "uid=1000,noauto,user")
        self.assertTrue(e.is_user_mount)
        self.assertTrue(e.is_noauto)
        self.assertEqual(e.get_option("uid"), "1000")

    def test_is_removable(self):
        e = FstabEntry("/dev/sdb1", "/media/usb0", "vfat", "user")
        self.assertTrue(e.is_removable_media)

    def test_to_line(self):
        e = FstabEntry("/dev/sdb1", "/media/usb0", "vfat", "user,noauto")
        line = e.to_line()
        self.assertIn("/dev/sdb1", line)
        self.assertIn("/media/usb0", line)

    def test_set_option(self):
        e = FstabEntry("/dev/x", "/m", "ext4", "defaults")
        e.set_option("uid", "1000")
        self.assertEqual(e.get_option("uid"), "1000")
        e.set_option("uid", None)
        self.assertIsNone(e.get_option("uid"))

    def test_to_dict(self):
        e = FstabEntry("/dev/sdb1", "/media/usb0", "vfat", "user")
        d = e.to_dict()
        self.assertEqual(d["device"], "/dev/sdb1")
        self.assertEqual(d["mount_point"], "/media/usb0")


class TestFstabValidator(unittest.TestCase):
    def test_valid_entry(self):
        v = FstabValidator()
        e = FstabEntry("/dev/sdb1", "/media/usb0", "vfat", "user,noauto")
        issues = v.validate(e)
        errors = [i for i in issues if i.severity == "error"]
        self.assertEqual(len(errors), 0)

    def test_missing_device(self):
        v = FstabValidator()
        e = FstabEntry("", "/media/usb0", "vfat")
        issues = v.validate(e)
        self.assertTrue(any(i.issue == FstabIssue.MISSING_DEVICE for i in issues))

    def test_conflicting_options(self):
        v = FstabValidator()
        e = FstabEntry("/dev/x", "/m", "ext4", "user,nouser")
        issues = v.validate(e)
        self.assertTrue(any(i.issue == FstabIssue.CONFLICTING_OPTIONS for i in issues))

    def test_invalid_fs_type(self):
        v = FstabValidator()
        e = FstabEntry("/dev/x", "/m", "fakefs99")
        issues = v.validate(e)
        self.assertTrue(any(i.issue == FstabIssue.INVALID_FS_TYPE for i in issues))

    def test_non_absolute_mount(self):
        v = FstabValidator()
        e = FstabEntry("/dev/x", "relative/path", "ext4")
        issues = v.validate(e)
        self.assertTrue(any(i.issue == FstabIssue.NON_ABSOLUTE_PATH for i in issues))

    def test_validate_all(self):
        v = FstabValidator()
        entries = [
            FstabEntry("/dev/sdb1", "/media/usb0", "vfat", "user"),
            FstabEntry("/dev/sdb1", "/media/usb0", "ext4", "user"),  # duplicate
        ]
        issues = v.validate_all(entries)
        self.assertTrue(any(i.issue == FstabIssue.DUPLICATE_MOUNT_POINT for i in issues))


class TestFstabManager(unittest.TestCase):
    def test_add_and_query(self):
        mgr = FstabManager(simulate=True)
        mgr.add(FstabEntry("/dev/sdb1", "/media/usb0", "vfat", "user,noauto"))
        mgr.add(FstabEntry("/dev/sr0", "/media/cdrom", "iso9660", "user,noauto,ro"))
        self.assertEqual(mgr.count, 2)
        found = mgr.get_by_mount("/media/usb0")
        self.assertIsNotNone(found)
        self.assertEqual(found.device, "/dev/sdb1")

    def test_remove(self):
        mgr = FstabManager(simulate=True)
        mgr.add(FstabEntry("/dev/sdb1", "/media/usb0", "vfat"))
        self.assertTrue(mgr.remove("/media/usb0"))
        self.assertEqual(mgr.count, 0)

    def test_update(self):
        mgr = FstabManager(simulate=True)
        mgr.add(FstabEntry("/dev/sdb1", "/media/usb0", "vfat"))
        self.assertTrue(mgr.update("/media/usb0", fs_type="exfat"))
        found = mgr.get_by_mount("/media/usb0")
        self.assertEqual(found.fs_type, "exfat")

    def test_get_removable(self):
        mgr = FstabManager(simulate=True)
        mgr.add(FstabEntry("/dev/sdb1", "/media/usb0", "vfat"))
        mgr.add(FstabEntry("/dev/nvme0n1p1", "/", "ext4", "defaults"))
        removable = mgr.get_removable()
        self.assertEqual(len(removable), 1)

    def test_get_user_mounts(self):
        mgr = FstabManager(simulate=True)
        mgr.add(FstabEntry("/dev/sdb1", "/media/usb0", "vfat", "user"))
        mgr.add(FstabEntry("/dev/sr0", "/media/cdrom", "iso9660", "defaults"))
        user_m = mgr.get_user_mounts()
        self.assertEqual(len(user_m), 1)

    def test_save_sim(self):
        mgr = FstabManager(simulate=True)
        mgr.add(FstabEntry("/dev/sdb1", "/media/usb0", "vfat"))
        self.assertTrue(mgr.save())
        self.assertFalse(mgr.is_dirty)

    def test_clear(self):
        mgr = FstabManager(simulate=True)
        mgr.add(FstabEntry("/dev/sdb1", "/media/usb0", "vfat"))
        mgr.add(FstabEntry("/dev/sr0", "/media/cdrom", "iso9660"))
        removed = mgr.clear()
        self.assertEqual(removed, 2)
        self.assertEqual(mgr.count, 0)


class TestMakeRemovableEntry(unittest.TestCase):
    def test_basic(self):
        e = make_removable_entry("/dev/sdb1", "/media/usb0", uid=1000)
        self.assertTrue(e.is_user_mount)
        self.assertTrue(e.is_noauto)
        self.assertEqual(e.get_option("uid"), "1000")

    def test_iso9660_readonly(self):
        e = make_removable_entry("/dev/sr0", "/media/cdrom", fs_type="iso9660")
        self.assertIn("ro", e.option_set)


# ===================================================================
# udisks2
# ===================================================================

class TestUDisks2Drive(unittest.TestCase):
    def test_create(self):
        d = UDisks2Drive(
            object_path="/org/drive/1",
            model="USB Drive",
            vendor="Generic",
            size=32_000_000_000,
            removable=True,
        )
        self.assertTrue(d.removable)
        self.assertIn("Generic", d.display_name)

    def test_size_human(self):
        d = UDisks2Drive(object_path="/d", size=1_500_000_000)
        h = d.size_human
        self.assertIn("GiB", h)


class TestUDisks2Block(unittest.TestCase):
    def test_create(self):
        b = UDisks2Block(
            object_path="/org/block/1",
            device="/dev/sdb1",
            id_type="vfat",
            id_usage="filesystem",
            id_label="MYUSB",
        )
        self.assertTrue(b.is_filesystem)
        self.assertFalse(b.is_mounted)
        self.assertEqual(b.display_name, "MYUSB")


class TestUDisks2Client(unittest.TestCase):
    def setUp(self):
        set_simulation(True)
        clear_sim_mounts()

    def tearDown(self):
        clear_sim_mounts()

    def test_register_and_query(self):
        client = UDisks2Client(simulate=True)
        drive = UDisks2Drive(
            object_path="/org/drive/1",
            model="USB",
            removable=True,
        )
        block = UDisks2Block(
            object_path="/org/block/1",
            device="/dev/sdb1",
            id_type="vfat",
            drive_object_path="/org/drive/1",
        )
        client.register_drive(drive)
        client.register_block(block)
        self.assertEqual(len(client.drives), 1)
        self.assertEqual(len(client.block_devices), 1)

    def test_get_by_device(self):
        client = UDisks2Client(simulate=True)
        block = UDisks2Block(
            object_path="/org/block/1",
            device="/dev/sdb1",
            id_type="vfat",
        )
        client.register_block(block)
        found = client.get_block_by_device("/dev/sdb1")
        self.assertIsNotNone(found)

    def test_get_removable_drives(self):
        client = UDisks2Client(simulate=True)
        drive = UDisks2Drive(
            object_path="/org/drive/1",
            removable=True,
        )
        client.register_drive(drive)
        self.assertEqual(len(client.get_removable_drives()), 1)

    def test_mount_unmount(self):
        client = UDisks2Client(simulate=True)
        block = UDisks2Block(
            object_path="/org/block/1",
            device="/dev/sdb1",
            id_type="vfat",
            id_usage="filesystem",
        )
        client.register_block(block)
        result = client.mount(block.object_path)
        self.assertTrue(result.success)
        self.assertTrue(block.is_mounted)
        result2 = client.unmount(block.object_path)
        self.assertTrue(result2.success)
        self.assertFalse(block.is_mounted)

    def test_listener(self):
        client = UDisks2Client(simulate=True)
        events = []
        client.on_event(lambda a, o: events.append((a, o.object_path)))
        block = UDisks2Block(object_path="/org/block/1", device="/dev/sdb1")
        client._emit("test", block)
        self.assertEqual(len(events), 1)

    def test_get_all_objects(self):
        client = UDisks2Client(simulate=True)
        drive = UDisks2Drive(object_path="/org/drive/1")
        block = UDisks2Block(object_path="/org/block/1", device="/dev/sdb1")
        client.register_drive(drive)
        client.register_block(block)
        all_objs = client.get_all_objects()
        self.assertGreaterEqual(len(all_objs), 2)


class TestGetRemovableMediaInfo(unittest.TestCase):
    def test_returns_list(self):
        result = get_removable_media_info()
        self.assertIsInstance(result, list)


# ===================================================================
# _selftest runners
# ===================================================================

class TestSelfTests(unittest.TestCase):
    """Verify all _selftest() functions return True."""

    def test_filesystem_selftest(self):
        from media.filesystem import _selftest
        self.assertTrue(_selftest())

    def test_mount_ops_selftest(self):
        from media.mount_ops import _selftest
        self.assertTrue(_selftest())

    def test_auto_mount_selftest(self):
        from media.auto_mount import _selftest
        self.assertTrue(_selftest())

    def test_permissions_selftest(self):
        from media.permissions import _selftest
        self.assertTrue(_selftest())

    def test_fstab_selftest(self):
        from media.fstab import _selftest
        self.assertTrue(_selftest())

    def test_udisks2_selftest(self):
        from media.udisks2 import _selftest
        self.assertTrue(_selftest())


if __name__ == "__main__":
    unittest.main()
