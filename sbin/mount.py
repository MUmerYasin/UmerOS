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
UmerOS /sbin Mount Commands
===========================
Filesystem mounting and device management.
mount, umount, mknod, losetup, pivot_root

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations
import os
import sys
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Tuple

# Zero-trust execution guard (H233): every command's `execute()` is
# capability-gated and audit-logged the moment its class is defined.
try:
    from .command_guard import install_guard
except ImportError:  # pragma: no cover - run as a standalone script
    from command_guard import install_guard

# Path + mount-option policy (H234): every path this module stores is
# validated now, so wiring the simulation to a real syscall cannot turn
# stored text into a traversing path.
try:
    from . import path_policy
    from .path_policy import UnsafePathError
except ImportError:  # pragma: no cover - run as a standalone script
    import path_policy  # type: ignore[no-redef]
    from path_policy import UnsafePathError  # type: ignore[no-redef]


class SbinCommand:
    """Base class for /sbin commands."""

    # Gate + audit every subclass's `execute()` at class-creation time
    # (H233), so a direct `SomeCommand().execute()` cannot bypass the
    # capability check that `SbinManager.execute()` performs.
    __init_subclass__ = install_guard

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

#: Mode bits requested with ``mknod -m``.  The parsed value used to be
#: computed and discarded, so ``-m`` silently did nothing.
_DEVICE_MODES: Dict[str, int] = {}


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
            print("[simulated] mount: mounting all from /etc/fstab")
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
            print("[simulated] mount: fake mount (dry run)")
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
            # Validate before storing: this text becomes a real mount(2)
            # argument the moment the simulation is wired up (H234).
            try:
                device = path_policy.validate_source(device)
                mount_point = path_policy.normalise(mount_point, "mount point")
            except UnsafePathError as exc:
                print(f"mount: {exc}", file=sys.stderr)
                return 1

            # Check if already mounted at that mount_point
            for existing in _MOUNT_TABLE:
                if existing["mount_point"] == mount_point:
                    print(f"mount: {mount_point} already mounted", file=sys.stderr)
                    return 1

            # Hardened by default: a newly mounted filesystem must not honour
            # setuid bits, device nodes or executable payloads planted on it
            # -- the same flags mnt/mount_ops.harden_user_options applies.
            options, _hardened = path_policy.harden_mount_options(options)
            entry = {
                "device": device,
                "mount_point": mount_point,
                "fstype": fstype,
                "options": options,
                "dump": 0,
                "pass": 0,
            }
            _MOUNT_TABLE.append(entry)
            print(f"[simulated] mount: {device} on {mount_point} type {fstype} ({options})")
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
                print(f"[simulated] umount: unmounted {m['mount_point']}")
            return 0

        if args[0] in ("-h", "--help"):
            print(self.help())
            return 0

        if args[0] in ("-V", "--version"):
            print("umount from util-linux 2.37.2")
            return 0

        try:
            target = path_policy.normalise(args[0], "mount point")
        except UnsafePathError as exc:
            print(f"umount: {exc}", file=sys.stderr)
            return 1

        # Virtual paths are always considered mounted in UmerOS
        virtual_paths = {"/tmp", "/dev/shm", "/dev/pts", "/dev", "/proc", "/sys"}
        if target in virtual_paths:
            print(f"[simulated] umount: unmounted {target}")
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
                print(f"[simulated] umount: unmounted {m['mount_point']}")
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

        devtype = remaining[1]
        try:
            name = path_policy.require_under(
                remaining[0], path_policy.DEV_PREFIX, "device node"
            )
        except UnsafePathError as exc:
            print(f"mknod: {exc}", file=sys.stderr)
            return 1

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
            _DEVICE_MODES[name] = mode
            print(f"[simulated] mknod: created {devtype} device '{name}' "
                  f"({major}, {minor}) mode {mode:04o}")
        else:
            _DEVICE_NODES[name] = (0, 0)
            _DEVICE_MODES[name] = mode
            print(f"[simulated] mknod: created named pipe '{name}' mode {mode:04o}")
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
                    print(f"[simulated] losetup: detached {dev}")
                    return 0
                print(f"losetup: {dev}: not a loop device", file=sys.stderr)
                return 1
            # Detach all
            _LOOP_DEVICES.clear()
            print("[simulated] losetup: detached all loop devices")
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
                try:
                    offset = int(args[i + 1])
                except ValueError:
                    print(f"losetup: invalid offset '{args[i + 1]}'", file=sys.stderr)
                    return 1
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
            try:
                loopdev = path_policy.require_loop_device(loopdev)
                filepath = path_policy.normalise(filepath, "backing file")
            except UnsafePathError as exc:
                print(f"losetup: {exc}", file=sys.stderr)
                return 1
            _LOOP_DEVICES[loopdev] = filepath
            print(f"[simulated] losetup: {loopdev} -> {filepath} (offset {offset})")
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
        try:
            new_root = path_policy.normalise(args[0], "new root")
            put_old = path_policy.normalise(args[1], "put_old directory")
        except UnsafePathError as exc:
            print(f"pivot_root: {exc}", file=sys.stderr)
            return 1
        print(f"[simulated] pivot_root: changing root to {new_root}, old root moved to {put_old}")
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
    _DEVICE_MODES.clear()
    _LOOP_DEVICES.clear()

    # Save so we can restore after selftest
    import copy
    saved_mount_table = copy.deepcopy(_MOUNT_TABLE)
    saved_device_nodes = copy.deepcopy(_DEVICE_NODES)
    saved_device_modes = copy.deepcopy(_DEVICE_MODES)
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
        _DEVICE_MODES.clear()
        _DEVICE_MODES.update(saved_device_modes)
        _LOOP_DEVICES.clear()
        _LOOP_DEVICES.update(saved_loop_devices)

    print(f"sbin/mount.py: {tests_passed} passed, {tests_failed} failed")
    return tests_failed == 0


if __name__ == "__main__":
    _selftest()
