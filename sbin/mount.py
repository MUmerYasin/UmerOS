"""
UmerOS /sbin Mount Commands
===========================
Filesystem mounting and device management.
mount, umount, mknod, losetup, pivot_root
"""

from __future__ import annotations
import os
import sys
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Tuple


class SbinCommand:
    """Base class for /sbin commands."""

    name: str = ""
    description: str = ""
    usage: str = ""

    @abstractmethod
    def execute(self, args: Optional[List[str]] = None) -> int:
        pass

    def help(self) -> str:
        return f"Usage: {self.usage}\n{self.description}"


# ─── In-Memory Mount Table ──────────────────────────────────────────────────

_MOUNT_TABLE: List[Dict[str, Any]] = [
    {"device": "/dev/sda1", "mount_point": "/", "fstype": "ext4",
     "options": "rw,relatime", "dump": 0, "pass": 1},
    {"device": "proc", "mount_point": "/proc", "fstype": "proc",
     "options": "rw,nosuid,nodev,noexec,relatime", "dump": 0, "pass": 0},
    {"device": "sysfs", "mount_point": "/sys", "fstype": "sysfs",
     "options": "rw,nosuid,nodev,noexec,relatime", "dump": 0, "pass": 0},
    {"device": "tmpfs", "mount_point": "/tmp", "fstype": "tmpfs",
     "options": "rw,nosuid,nodev,noexec,relatime,size=4096k", "dump": 0, "pass": 0},
    {"device": "devtmpfs", "mount_point": "/dev", "fstype": "devtmpfs",
     "options": "rw,nosuid,relatime,size=4096k,mode=755", "dump": 0, "pass": 0},
]

_LOOP_DEVICES: Dict[str, str] = {}

_DEVICE_NODES: Dict[str, Tuple[int, int]] = {}


# ─── Mount Commands ─────────────────────────────────────────────────────────

class MountCommand(SbinCommand):
    """Mount a filesystem or list mounts."""
    name = "mount"
    description = "Mount a filesystem or list currently mounted filesystems"
    usage = "mount [-lhfv] [-t type] [-o options] device dir"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args:
            for m in _MOUNT_TABLE:
                print(f"{m['device']} on {m['mount_point']} type {m['fstype']} ({m['options']})")
            return 0

        if args[0] == "-a":
            print("[*] mount: mounting all from /etc/fstab")
            return 0

        if args[0] in ("-l", "--show-labels"):
            for m in _MOUNT_TABLE:
                print(f"{m['device']}        {m['mount_point']}       {m['fstype']}")
            return 0

        if args[0] in ("-h", "--help"):
            print(self.help())
            return 0

        if args[0] in ("-V", "--version"):
            print("mount from util-linux 2.37.2")
            return 0

        if args[0] in ("-f", "--fake"):
            print("[*] mount: fake mount (dry run)")
            return 0

        if args[0] in ("-v", "--verbose"):
            args = args[1:]
            if not args:
                for m in _MOUNT_TABLE:
                    print(f"{m['device']} on {m['mount_point']} type {m['fstype']} ({m['options']})")
                return 0

        # Parse mount arguments
        device = None
        mount_point = None
        fstype = "auto"
        options = "rw,relatime"

        i = 0
        while i < len(args):
            if args[i] == "-t" and i + 1 < len(args):
                fstype = args[i + 1]
                i += 2
            elif args[i] == "-o" and i + 1 < len(args):
                options = args[i + 1]
                i += 2
            elif not args[i].startswith("-"):
                if device is None:
                    device = args[i]
                else:
                    mount_point = args[i]
                i += 1
            else:
                i += 1

        if device and mount_point:
            # Check if already mounted at that mount_point
            for existing in _MOUNT_TABLE:
                if existing["mount_point"] == mount_point:
                    print(f"mount: {mount_point} already mounted", file=sys.stderr)
                    return 1
            entry = {
                "device": device,
                "mount_point": mount_point,
                "fstype": fstype,
                "options": options,
                "dump": 0,
                "pass": 0,
            }
            _MOUNT_TABLE.append(entry)
            print(f"[*] mount: {device} on {mount_point} type {fstype} ({options})")
            return 0

        print("mount: missing device or mount point", file=sys.stderr)
        return 1


class UmountCommand(SbinCommand):
    """Unmount filesystems."""
    name = "umount"
    description = "Unmount filesystems"
    usage = "umount [-a] [-t type] device|mountpoint"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args:
            print("umount: missing operand", file=sys.stderr)
            return 1

        if args[0] == "-a":
            # Unmount all except root
            global _MOUNT_TABLE
            removed = []
            remaining = []
            for m in _MOUNT_TABLE:
                if m["mount_point"] == "/":
                    remaining.append(m)
                else:
                    removed.append(m)
            _MOUNT_TABLE = remaining
            for m in removed:
                print(f"[*] umount: unmounted {m['mount_point']}")
            return 0

        if args[0] in ("-h", "--help"):
            print(self.help())
            return 0

        if args[0] in ("-V", "--version"):
            print("umount from util-linux 2.37.2")
            return 0

        target = args[0]
        # Virtual paths are always considered mounted in UmerOS
        virtual_paths = {"/tmp", "/dev/shm", "/dev/pts", "/dev", "/proc", "/sys"}
        if target in virtual_paths:
            print(f"[*] umount: unmounted {target}")
            # Also remove from mount table if present
            new_table = [m for m in _MOUNT_TABLE if m["mount_point"] != target]
            _MOUNT_TABLE[:] = new_table
            return 0

        # Try to find by mount_point or device
        found = False
        new_table = []
        for m in _MOUNT_TABLE:
            if m["mount_point"] == target or m["device"] == target:
                found = True
                print(f"[*] umount: unmounted {m['mount_point']}")
            else:
                new_table.append(m)

        if found:
            _MOUNT_TABLE[:] = new_table
            return 0

        print(f"umount: {target}: not mounted", file=sys.stderr)
        return 1


class MknodCommand(SbinCommand):
    """Make block or character special files."""
    name = "mknod"
    description = "Make block or character special files"
    usage = "mknod [-m mode] name type [major minor]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        args = args or []
        mode = 0o660
        i = 0
        if args and args[0] == "-m" and len(args) > 1:
            try:
                mode = int(args[1], 8)
            except ValueError:
                mode = 0o660
            i = 2

        remaining = args[i:]

        if len(remaining) < 2:
            print("mknod: missing operand", file=sys.stderr)
            print("Try 'mknod --help' for more information.", file=sys.stderr)
            return 1

        name = remaining[0]
        devtype = remaining[1]

        if devtype not in ("b", "c", "u", "p"):
            print(f"mknod: invalid device type '{devtype}'", file=sys.stderr)
            return 1

        if devtype in ("b", "c", "u"):
            if len(remaining) < 4:
                print("mknod: missing major/minor number", file=sys.stderr)
                return 1
            try:
                major = int(remaining[2])
                minor = int(remaining[3])
            except ValueError:
                print("mknod: invalid major/minor number", file=sys.stderr)
                return 1
            _DEVICE_NODES[name] = (major, minor)
            print(f"[*] mknod: created {devtype} device '{name}' ({major}, {minor})")
        else:
            _DEVICE_NODES[name] = (0, 0)
            print(f"[*] mknod: created named pipe '{name}'")
        return 0


class LosetupCommand(SbinCommand):
    """Set up loop devices."""
    name = "losetup"
    description = "Set up and control loop devices"
    usage = "losetup [-a] [-d] [-f] [-o offset] loopdev file"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args or args[0] in ("-a", "--list"):
            if _LOOP_DEVICES:
                for dev, filepath in _LOOP_DEVICES.items():
                    print(f"{dev}: [{os.path.getsize(filepath) if os.path.exists(filepath) else 0}] "
                          f"({filepath})")
            else:
                print("No loop devices configured")
            return 0

        if args[0] in ("-f", "--find"):
            # Find next available loop device
            idx = len(_LOOP_DEVICES)
            print(f"/dev/loop{idx}")
            return 0

        if args[0] in ("-d", "--detach"):
            if len(args) > 1:
                dev = args[1]
                if dev in _LOOP_DEVICES:
                    del _LOOP_DEVICES[dev]
                    print(f"[*] losetup: detached {dev}")
                    return 0
                print(f"losetup: {dev}: not a loop device", file=sys.stderr)
                return 1
            # Detach all
            _LOOP_DEVICES.clear()
            print("[*] losetup: detached all loop devices")
            return 0

        if args[0] in ("-h", "--help"):
            print(self.help())
            return 0

        if args[0] in ("-V", "--version"):
            print("losetup from util-linux 2.37.2")
            return 0

        # Attach: losetup [-o offset] loopdev file
        offset = 0
        loopdev = None
        filepath = None
        i = 0
        while i < len(args):
            if args[i] == "-o" and i + 1 < len(args):
                offset = int(args[i + 1])
                i += 2
            elif not args[i].startswith("-"):
                if loopdev is None:
                    loopdev = args[i]
                else:
                    filepath = args[i]
                i += 1
            else:
                i += 1

        if loopdev and filepath:
            _LOOP_DEVICES[loopdev] = filepath
            print(f"[*] losetup: {loopdev} -> {filepath} (offset {offset})")
            return 0

        print("losetup: missing arguments", file=sys.stderr)
        return 1


class PivotRootCommand(SbinCommand):
    """Change the root mount."""
    name = "pivot_root"
    description = "Change the root filesystem"
    usage = "pivot_root new_root put_old"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args or len(args) < 2:
            print("pivot_root: missing new_root or put_old", file=sys.stderr)
            return 1
        new_root = args[0]
        put_old = args[1]
        print(f"[*] pivot_root: changing root to {new_root}, old root moved to {put_old}")
        return 0


def _selftest() -> bool:
    """Run self-tests for /sbin mount commands."""
    tests_passed = 0
    tests_failed = 0

    # Reset global state to initial values so tests from other classes don't
    # leak into the selftest.
    _MOUNT_TABLE[:] = [
        {"device": "/dev/sda1", "mount_point": "/", "fstype": "ext4",
         "options": "rw,relatime", "dump": 0, "pass": 1},
        {"device": "proc", "mount_point": "/proc", "fstype": "proc",
         "options": "rw,nosuid,nodev,noexec,relatime", "dump": 0, "pass": 0},
        {"device": "sysfs", "mount_point": "/sys", "fstype": "sysfs",
         "options": "rw,nosuid,nodev,noexec,relatime", "dump": 0, "pass": 0},
        {"device": "tmpfs", "mount_point": "/tmp", "fstype": "tmpfs",
         "options": "rw,nosuid,nodev,noexec,relatime,size=4096k", "dump": 0, "pass": 0},
        {"device": "devtmpfs", "mount_point": "/dev", "fstype": "devtmpfs",
         "options": "rw,nosuid,relatime,size=4096k,mode=755", "dump": 0, "pass": 0},
    ]
    _DEVICE_NODES.clear()
    _LOOP_DEVICES.clear()

    # Save so we can restore after selftest
    import copy
    saved_mount_table = copy.deepcopy(_MOUNT_TABLE)
    saved_device_nodes = copy.deepcopy(_DEVICE_NODES)
    saved_loop_devices = copy.deepcopy(_LOOP_DEVICES)

    try:

        # Test MountCommand
        cmd = MountCommand()
        assert cmd.name == "mount"
        assert cmd.description
        assert cmd.usage
        ret = cmd.execute()
        assert ret == 0, "mount (no args) should return 0"
        tests_passed += 1

        ret = cmd.execute(["-l"])
        assert ret == 0, "mount -l should return 0"
        tests_passed += 1

        ret = cmd.execute(["-a"])
        assert ret == 0, "mount -a should return 0"
        tests_passed += 1

        ret = cmd.execute(["-V"])
        assert ret == 0, "mount -V should return 0"
        tests_passed += 1

        ret = cmd.execute(["-f"])
        assert ret == 0, "mount -f should return 0"
        tests_passed += 1

        ret = cmd.execute(["-h"])
        assert ret == 0, "mount -h should return 0"
        tests_passed += 1

        ret = cmd.execute(["/dev/sdb1", "/mnt/usb"])
        assert ret == 0, "mount device point should return 0"
        tests_passed += 1

        # Duplicate mount should fail
        ret = cmd.execute(["/dev/sdb2", "/mnt/usb"])
        assert ret == 1, "mount duplicate should return 1"
        tests_passed += 1

        ret = cmd.execute(["-t", "vfat", "-o", "rw", "/dev/sdb2", "/mnt/usb2"])
        assert ret == 0, "mount with -t and -o should return 0"
        tests_passed += 1

        # Test UmountCommand
        cmd = UmountCommand()
        assert cmd.name == "umount"
        ret = cmd.execute(["-h"])
        assert ret == 0, "umount -h should return 0"
        tests_passed += 1

        ret = cmd.execute(["-V"])
        assert ret == 0, "umount -V should return 0"
        tests_passed += 1

        ret = cmd.execute(["/proc"])
        assert ret == 0, "umount /proc should return 0"
        tests_passed += 1

        ret = cmd.execute(["/nonexistent"])
        assert ret == 1, "umount nonexistent should return 1"
        tests_passed += 1

        ret = cmd.execute()
        assert ret == 1, "umount no args should return 1"
        tests_passed += 1

        ret = cmd.execute(["-a"])
        assert ret == 0, "umount -a should return 0"
        tests_passed += 1

        # Test MknodCommand
        cmd = MknodCommand()
        assert cmd.name == "mknod"
        ret = cmd.execute()
        assert ret == 1, "mknod no args should return 1"
        tests_passed += 1

        ret = cmd.execute(["/dev/test", "b", "1", "0"])
        assert ret == 0, "mknod block device should return 0"
        tests_passed += 1

        ret = cmd.execute(["/dev/testchar", "c", "1", "1"])
        assert ret == 0, "mknod char device should return 0"
        tests_passed += 1

        ret = cmd.execute(["/dev/testpipe", "p"])
        assert ret == 0, "mknod pipe should return 0"
        tests_passed += 1

        ret = cmd.execute(["-m", "0644", "/dev/testm", "b", "1", "2"])
        assert ret == 0, "mknod with -m should return 0"
        tests_passed += 1

        ret = cmd.execute(["/dev/test", "x"])
        assert ret == 1, "mknod invalid type should return 1"
        tests_passed += 1

        ret = cmd.execute(["/dev/test", "b"])
        assert ret == 1, "mknod missing major/minor should return 1"
        tests_passed += 1

        # Test LosetupCommand
        cmd = LosetupCommand()
        assert cmd.name == "losetup"
        ret = cmd.execute()
        assert ret == 0, "losetup (no args) should return 0"
        tests_passed += 1

        ret = cmd.execute(["-f"])
        assert ret == 0, "losetup -f should return 0"
        tests_passed += 1

        ret = cmd.execute(["/dev/loop0", "/tmp/test.img"])
        assert ret == 0, "losetup attach should return 0"
        tests_passed += 1

        ret = cmd.execute(["-a"])
        assert ret == 0, "losetup -a should return 0"
        tests_passed += 1

        ret = cmd.execute(["-d", "/dev/loop0"])
        assert ret == 0, "losetup -d should return 0"
        tests_passed += 1

        ret = cmd.execute(["-d", "/dev/nonexistent"])
        assert ret == 1, "losetup -d nonexistent should return 1"
        tests_passed += 1

        ret = cmd.execute(["-V"])
        assert ret == 0, "losetup -V should return 0"
        tests_passed += 1

        ret = cmd.execute(["-h"])
        assert ret == 0, "losetup -h should return 0"
        tests_passed += 1

        # Test PivotRootCommand
        cmd = PivotRootCommand()
        assert cmd.name == "pivot_root"
        ret = cmd.execute()
        assert ret == 1, "pivot_root no args should return 1"
        tests_passed += 1

        ret = cmd.execute(["/new"])
        assert ret == 1, "pivot_root one arg should return 1"
        tests_passed += 1

        ret = cmd.execute(["/new", "/old"])
        assert ret == 0, "pivot_root with args should return 0"
        tests_passed += 1

    finally:
        # Restore global state
        _MOUNT_TABLE[:] = saved_mount_table
        _DEVICE_NODES.clear()
        _DEVICE_NODES.update(saved_device_nodes)
        _LOOP_DEVICES.clear()
        _LOOP_DEVICES.update(saved_loop_devices)

    print(f"sbin/mount.py: {tests_passed} passed, {tests_failed} failed")
    return tests_failed == 0


if __name__ == "__main__":
    _selftest()
