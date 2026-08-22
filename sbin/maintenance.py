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
UmerOS /sbin Maintenance Commands
===================================
System maintenance, filesystem repair/tuning, keyboard utilities.
tune2fs, e2fsck, mke2fs, ctrlaltdel, kbdrate, loadkeys, dump, restore, sln, mktemp, setfdprm, rdev
"""

from __future__ import annotations
import os
import sys
import time
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


# ─── Virtual Ext2/3/4 Superblock ────────────────────────────────────────────

_SUPERBLOCKS: Dict[str, Dict[str, Any]] = {}


def _get_superblock(device: str) -> Dict[str, Any]:
    """Get or create a virtual superblock for a device."""
    if device not in _SUPERBLOCKS:
        _SUPERBLOCKS[device] = {
            "state": "clean",
            "mount_count": 0,
            "max_mount_count": 30,
            "created": time.time(),
            "block_size": 4096,
            "inode_count": 65536,
            "block_count": 262144,
            "uuid": f"deadbeef-{device.replace('/dev/', '').replace('/', '_')[:8]}",
            "label": "",
            "reserved_blocks": 5,
            "last_check": 0.0,
            "check_interval": 180 * 86400,
            "features": ["has_journal", "dir_index", "extent"],
        }
    return _SUPERBLOCKS[device]


# ─── Filesystem Maintenance ─────────────────────────────────────────────────

class Tune2fsCommand(SbinCommand):
    """Tune ext2/3/4 filesystem parameters."""
    name = "tune2fs"
    description = "Adjust tunable filesystem parameters on ext2/ext3/ext4 filesystems"
    usage = "tune2fs [-c max-mount-count] [-i interval] [-l -L label -U uuid] device"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args:
            print("tune2fs: missing device", file=sys.stderr)
            return 1

        # List mode
        if args[0] == "-l":
            if len(args) < 2:
                print("tune2fs: missing device for -l", file=sys.stderr)
                return 1
            sb = _get_superblock(args[1])
            print(f"tune2fs {sb['state']}")
            print(f"Filesystem volume name: {sb['label'] or '<none>'}")
            print(f"Filesystem UUID: {sb['uuid']}")
            print(f"Filesystem state: {sb['state']}")
            print(f"Block size: {sb['block_size']}")
            print(f"Block count: {sb['block_count']}")
            print(f"Inode count: {sb['inode_count']}")
            print(f"Mount count: {sb['mount_count']}")
            print(f"Maximum mount count: {sb['max_mount_count']}")
            print(f"Reserved blocks: {sb['reserved_blocks']}")
            print(f"Features: {', '.join(sb['features'])}")
            return 0

        # Help mode
        if args[0] in ("-h", "--help"):
            return 0

        device = None
        max_mount = None
        interval = None
        label = None
        uuid_val = None

        i = 0
        while i < len(args):
            if args[i] == "-c" and i + 1 < len(args):
                max_mount = int(args[i + 1])
                i += 2
            elif args[i] == "-i" and i + 1 < len(args):
                interval = args[i + 1]
                i += 2
            elif args[i] == "-L" and i + 1 < len(args):
                label = args[i + 1]
                i += 2
            elif args[i] == "-U" and i + 1 < len(args):
                uuid_val = args[i + 1]
                i += 2
            elif not args[i].startswith("-"):
                device = args[i]
                i += 1
            else:
                i += 1

        if device is None:
            print("tune2fs: missing device", file=sys.stderr)
            return 1

        sb = _get_superblock(device)
        if max_mount is not None:
            sb["max_mount_count"] = max_mount
            print(f"[*] tune2fs: max mount count set to {max_mount} on {device}")
        if interval is not None:
            print(f"[*] tune2fs: check interval set to {interval} on {device}")
        if label is not None:
            sb["label"] = label
            print(f"[*] tune2fs: label set to '{label}' on {device}")
        if uuid_val is not None:
            sb["uuid"] = uuid_val
            print(f"[*] tune2fs: UUID set to {uuid_val} on {device}")

        if max_mount is None and interval is None and label is None and uuid_val is None:
            print("tune2fs: nothing to do", file=sys.stderr)
            return 1

        return 0


class E2fsckCommand(SbinCommand):
    """Check ext2/3/4 filesystem."""
    name = "e2fsck"
    description = "Check a Linux ext2/ext3/ext4 filesystem"
    usage = "e2fsck [-p -n -y -f] device"

    def execute(self, args: Optional[List[str]] = None) -> int:
        args = args or []
        if not args:
            print("restore: missing device", file=sys.stderr)
            return 1

        force = False
        preen = False
        yes = False
        readonly = False
        device = None

        for a in args:
            if a == "-f":
                force = True
            elif a == "-p":
                preen = True
            elif a == "-y":
                yes = True
            elif a == "-n":
                readonly = True
            elif a == "-h":
                print(self.help())
                return 0
            elif not a.startswith("-"):
                device = a

        if device is None:
            print("e2fsck: missing device", file=sys.stderr)
            return 1

        sb = _get_superblock(device)

        print(f"e2fsck {device}: checking filesystem")

        if force or sb["state"] == "clean":
            if preen or yes or readonly:
                print(f"[*] e2fsck: {device}: clean, no errors")
            else:
                print(f"[*] e2fsck: {device}: clean, no errors")
            sb["state"] = "clean"
            sb["last_check"] = time.time()
            sb["mount_count"] = 0
            return 0
        else:
            if yes:
                print(f"[*] e2fsck: {device}: correcting errors")
                sb["state"] = "clean"
                sb["last_check"] = time.time()
                return 0
            elif readonly:
                print(f"e2fsck: {device}: errors detected (read-only, not corrected)")
                return 1
            else:
                print(f"[*] e2fsck: {device}: fixing errors")
                sb["state"] = "clean"
                sb["last_check"] = time.time()
                return 0


class Mke2fsCommand(SbinCommand):
    """Create ext2/3/4 filesystem."""
    name = "mke2fs"
    description = "Create an ext2/ext3/ext4 filesystem"
    usage = "mke2fs [-t type] [-b blocks-size] [-L label] device"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args:
            print("mke2fs: missing device", file=sys.stderr)
            return 1

        fstype = "ext4"
        block_size = 4096
        label = ""
        device = None

        i = 0
        while i < len(args):
            if args[i] == "-t" and i + 1 < len(args):
                fstype = args[i + 1]
                i += 2
            elif args[i] == "-b" and i + 1 < len(args):
                block_size = int(args[i + 1])
                i += 2
            elif args[i] == "-L" and i + 1 < len(args):
                label = args[i + 1]
                i += 2
            elif args[i] == "-n":
                # dry run
                print(f"[*] mke2fs: dry run for {args[i+1] if i+1 < len(args) else 'device'}")
                return 0
            elif args[i] == "-h":
                print(self.help())
                return 0
            elif not args[i].startswith("-"):
                device = args[i]
                i += 1
            else:
                i += 1

        if device is None:
            print("mke2fs: missing device", file=sys.stderr)
            return 1

        sb = _get_superblock(device)
        sb["state"] = "clean"
        sb["block_size"] = block_size
        sb["label"] = label
        sb["mount_count"] = 0
        sb["created"] = time.time()

        print(f"[*] mke2fs: creating {fstype} filesystem on {device}")
        if label:
            print(f"[*] mke2fs: label = '{label}'")
        print(f"[*] mke2fs: block size = {block_size}")
        print(f"[*] mke2fs: done")
        return 0


class CtrlaltdelCommand(SbinCommand):
    """Control what happens when Ctrl-Alt-Del is pressed."""
    name = "ctrlaltdel"
    description = "Set the function of the Ctrl-Alt-Del combination"
    usage = "ctrlaltdel hard|soft"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args:
            print("hard")
            return 0

        mode = args[0].lower()
        if mode == "hard":
            print("[*] ctrlaltdel: set to hard (immediate reboot)")
            return 0
        elif mode == "soft":
            print("[*] ctrlaltdel: set to soft (init reboot)")
            return 0
        else:
            print(f"ctrlaltdel: invalid mode '{args[0]}'", file=sys.stderr)
            return 1


class KbdrateCommand(SbinCommand):
    """Set keyboard repeat rate and delay."""
    name = "kbdrate"
    description = "Reset the keyboard repeat rate and delay time"
    usage = "kbdrate [-r rate] [-d delay] [-s]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        args = args or []
        rate = 30
        delay = 250
        silent = False

        i = 0
        while i < len(args):
            if args[i] == "-r" and i + 1 < len(args):
                rate = int(args[i + 1])
                i += 2
            elif args[i] == "-d" and i + 1 < len(args):
                delay = int(args[i + 1])
                i += 2
            elif args[i] == "-s":
                silent = True
                i += 1
            elif args[i] == "-h":
                print(self.help())
                return 0
            else:
                i += 1

        if not silent:
            print(f"[*] kbdrate: rate={rate} chars/sec, delay={delay}ms")
        return 0


class LoadkeysCommand(SbinCommand):
    """Load keyboard translation tables."""
    name = "loadkeys"
    description = "Load keyboard translation tables"
    usage = "loadkeys [-d -c -q -u] keymap"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args:
            print("loadkeys: missing keymap", file=sys.stderr)
            return 1

        keymap = None
        silent = False

        for a in args:
            if a in ("-d", "--default"):
                keymap = "defkeymap"
            elif a in ("-q", "--quiet"):
                silent = True
            elif a in ("-u", "--unicode"):
                pass
            elif a in ("-c", "--clearcompose"):
                pass
            elif a == "-h":
                print(self.help())
                return 0
            elif not a.startswith("-"):
                keymap = a

        if keymap is None:
            print("loadkeys: missing keymap", file=sys.stderr)
            return 1

        if not silent:
            print(f"[*] loadkeys: loading keymap '{keymap}'")
        return 0


class DumpCommand(SbinCommand):
    """Backup filesystem to tape."""
    name = "dump"
    description = "Backup a filesystem to tape or file"
    usage = "dump [-level] [-u] [-f file] filesystem"

    def execute(self, args: Optional[List[str]] = None) -> int:
        args = args or []
        level = 0
        use_file = None
        filesystem = None

        i = 0
        while i < len(args):
            if args[i].startswith("-") and not args[i][1:].isdigit():
                if args[i] == "-u":
                    pass  # update /etc/dumpdates
                elif args[i] == "-f" and i + 1 < len(args):
                    use_file = args[i + 1]
                    i += 2
                    continue
                elif args[i] == "-h":
                    print(self.help())
                    return 0
                i += 1
            elif args[i].isdigit():
                level = int(args[i])
                i += 1
            else:
                filesystem = args[i]
                i += 1

        if filesystem is None:
            print("dump: missing filesystem", file=sys.stderr)
            return 1

        target = use_file or "tape"
        print(f"[*] dump: level {level} dump of {filesystem} to {target}")
        return 0


class RestoreCommand(SbinCommand):
    """Restore a filesystem from dump."""
    name = "restore"
    description = "Restore files from a dump"
    usage = "restore [-r -R -x -C -v] [-f file] [-T dir]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        args = args or []
        use_file = None
        target_dir = "."
        mode = "restore"

        i = 0
        while i < len(args):
            if args[i] == "-r":
                mode = "rebuild"
                i += 1
            elif args[i] == "-R":
                mode = "multi-volume"
                i += 1
            elif args[i] == "-x":
                mode = "extract"
                i += 1
            elif args[i] == "-C":
                mode = "compare"
                i += 1
            elif args[i] == "-v":
                i += 1
            elif args[i] == "-f" and i + 1 < len(args):
                use_file = args[i + 1]
                i += 2
            elif args[i] == "-T" and i + 1 < len(args):
                target_dir = args[i + 1]
                i += 2
            elif args[i] == "-h":
                print(self.help())
                return 0
            else:
                i += 1

        target = use_file or "tape"
        print(f"[*] restore: {mode} from {target} into {target_dir}")
        return 0


class SlnCommand(SbinCommand):
    """Create symbolic links statically."""
    name = "sln"
    description = "Create symbolic links statically (for use in rescue environments)"
    usage = "sln source target"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args or len(args) < 2:
            print("sln: missing source or target", file=sys.stderr)
            return 1
        source = args[0]
        target = args[1]
        print(f"[*] sln: {source} -> {target}")
        return 0


class MktempCommand(SbinCommand):
    """Create temporary files securely."""
    name = "mktemp"
    description = "Create a temporary file or directory"
    usage = "mktemp [-d] [-t template] [template]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        args = args or []
        make_dir = False
        template = None

        i = 0
        while i < len(args):
            if args[i] == "-d":
                make_dir = True
                i += 1
            elif args[i] == "-t" and i + 1 < len(args):
                template = args[i + 1]
                i += 2
            elif args[i] == "-h":
                print(self.help())
                return 0
            elif not args[i].startswith("-"):
                template = args[i]
                i += 1
            else:
                i += 1

        import tempfile
        if template:
            suffix = template.split(".")[-1] if "." in template else ""
            prefix = template.split(".XXXXXX")[0] if ".XXXXXX" in template else template
            # Strip directory components from prefix (e.g. /tmp/tmp -> tmp) so
            # tempfile.mkstemp uses the system temp dir instead of looking for
            # a literal /tmp/ directory on Windows.
            import ntpath
            prefix = ntpath.basename(prefix)
            if make_dir:
                result = tempfile.mkdtemp(prefix=prefix, suffix=suffix)
            else:
                fd, result = tempfile.mkstemp(prefix=prefix, suffix=suffix)
                os.close(fd)
        else:
            if make_dir:
                result = tempfile.mkdtemp()
            else:
                fd, result = tempfile.mkstemp()
                os.close(fd)

        print(result)
        return 0


class SetfdprmCommand(SbinCommand):
    """Set floppy disk parameters."""
    name = "setfdprm"
    description = "Set floppy disk drive parameters"
    usage = "setfdprm [-c] [-y] device size"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args or len(args) < 2:
            print("setfdprm: missing device or parameters", file=sys.stderr)
            return 1
        device = args[0]
        print(f"[*] setfdprm: parameters set on {device}")
        return 0


class RdevCommand(SbinCommand):
    """Set or view the root device."""
    name = "rdev"
    description = "Set or display the root device"
    usage = "rdev [device [root_device]]"

    def execute(self, args: Optional[List[str]] = None) -> int:
        if not args:
            print("/dev/sda1")
            return 0
        if len(args) == 1:
            print(f"Root device: {args[0]}")
            return 0
        root_dev = args[0]
        kernel = args[1]
        print(f"[*] rdev: root device set to {root_dev} in {kernel}")
        return 0


def _selftest() -> bool:
    """Run self-tests for /sbin maintenance commands."""
    tests_passed = 0
    tests_failed = 0

    def check(condition: bool, msg: str):
        nonlocal tests_passed, tests_failed
        if condition:
            tests_passed += 1
        else:
            tests_failed += 1
            print(f"  FAIL: {msg}")

    # Tune2fsCommand
    cmd = Tune2fsCommand()
    check(cmd.name == "tune2fs", "tune2fs name")
    check(cmd.description, "tune2fs description")
    check(cmd.execute() == 1, "tune2fs no args -> 1")
    check(cmd.execute(["-h"]) == 0, "tune2fs -h -> 0")
    check(cmd.execute(["-l", "/dev/sda1"]) == 0, "tune2fs -l -> 0")
    check(cmd.execute(["-c", "5", "/dev/sda1"]) == 0, "tune2fs -c -> 0")
    check(cmd.execute(["-L", "test", "/dev/sda1"]) == 0, "tune2fs -L -> 0")
    check(cmd.execute(["-U", "1234-5678", "/dev/sda1"]) == 0, "tune2fs -U -> 0")
    check(cmd.execute(["-i", "30", "/dev/sda1"]) == 0, "tune2fs -i -> 0")

    # E2fsckCommand
    cmd = E2fsckCommand()
    check(cmd.name == "e2fsck", "e2fsck name")
    check(cmd.execute() == 1, "e2fsck no args -> 1")
    check(cmd.execute(["-h"]) == 0, "e2fsck -h -> 0")
    check(cmd.execute(["/dev/sda1"]) == 0, "e2fsck clean -> 0")
    check(cmd.execute(["-f", "/dev/sda1"]) == 0, "e2fsck -f -> 0")
    check(cmd.execute(["-y", "/dev/sda1"]) == 0, "e2fsck -y -> 0")
    check(cmd.execute(["-n", "/dev/sda1"]) == 0, "e2fsck -n -> 0")
    check(cmd.execute(["-p", "/dev/sda1"]) == 0, "e2fsck -p -> 0")

    # Mke2fsCommand
    cmd = Mke2fsCommand()
    check(cmd.name == "mke2fs", "mke2fs name")
    check(cmd.execute() == 1, "mke2fs no args -> 1")
    check(cmd.execute(["-h"]) == 0, "mke2fs -h -> 0")
    check(cmd.execute(["/dev/sdb1"]) == 0, "mke2fs /dev/sdb1 -> 0")
    check(cmd.execute(["-t", "ext3", "/dev/sdb1"]) == 0, "mke2fs -t ext3 -> 0")
    check(cmd.execute(["-b", "2048", "/dev/sdb1"]) == 0, "mke2fs -b 2048 -> 0")
    check(cmd.execute(["-L", "rootfs", "/dev/sdb1"]) == 0, "mke2fs -L -> 0")
    check(cmd.execute(["-n", "/dev/sdb1"]) == 0, "mke2fs -n -> 0")

    # CtrlaltdelCommand
    cmd = CtrlaltdelCommand()
    check(cmd.name == "ctrlaltdel", "ctrlaltdel name")
    check(cmd.execute() == 0, "ctrlaltdel no args -> 0")
    check(cmd.execute(["hard"]) == 0, "ctrlaltdel hard -> 0")
    check(cmd.execute(["soft"]) == 0, "ctrlaltdel soft -> 0")
    check(cmd.execute(["invalid"]) == 1, "ctrlaltdel invalid -> 1")

    # KbdrateCommand
    cmd = KbdrateCommand()
    check(cmd.name == "kbdrate", "kbdrate name")
    check(cmd.execute() == 0, "kbdrate no args -> 0")
    check(cmd.execute(["-r", "50"]) == 0, "kbdrate -r 50 -> 0")
    check(cmd.execute(["-d", "500"]) == 0, "kbdrate -d 500 -> 0")
    check(cmd.execute(["-s"]) == 0, "kbdrate -s -> 0")
    check(cmd.execute(["-h"]) == 0, "kbdrate -h -> 0")
    check(cmd.execute(["-r", "20", "-d", "500"]) == 0, "kbdrate -r -d -> 0")

    # LoadkeysCommand
    cmd = LoadkeysCommand()
    check(cmd.name == "loadkeys", "loadkeys name")
    check(cmd.execute() == 1, "loadkeys no args -> 1")
    check(cmd.execute(["us"]) == 0, "loadkeys us -> 0")
    check(cmd.execute(["-d", "defkeymap"]) == 0, "loadkeys -d -> 0")
    check(cmd.execute(["-q", "us"]) == 0, "loadkeys -q us -> 0")
    check(cmd.execute(["-h"]) == 0, "loadkeys -h -> 0")
    check(cmd.execute(["-u", "us"]) == 0, "loadkeys -u -> 0")

    # DumpCommand
    cmd = DumpCommand()
    check(cmd.name == "dump", "dump name")
    check(cmd.execute() == 1, "dump no args -> 1")
    check(cmd.execute(["-h"]) == 0, "dump -h -> 0")
    check(cmd.execute(["0", "/dev/sda1"]) == 0, "dump 0 /dev/sda1 -> 0")
    check(cmd.execute(["-f", "/tmp/dump.img", "0", "/dev/sda1"]) == 0, "dump -f -> 0")

    # RestoreCommand
    cmd = RestoreCommand()
    check(cmd.name == "restore", "restore name")
    check(cmd.execute() == 0, "restore no args -> 0")
    check(cmd.execute(["-h"]) == 0, "restore -h -> 0")
    check(cmd.execute(["-r"]) == 0, "restore -r -> 0")
    check(cmd.execute(["-R"]) == 0, "restore -R -> 0")
    check(cmd.execute(["-x"]) == 0, "restore -x -> 0")
    check(cmd.execute(["-C"]) == 0, "restore -C -> 0")
    check(cmd.execute(["-f", "/tmp/dump.img"]) == 0, "restore -f -> 0")
    check(cmd.execute(["-T", "/tmp"]) == 0, "restore -T -> 0")

    # SlnCommand
    cmd = SlnCommand()
    check(cmd.name == "sln", "sln name")
    check(cmd.execute() == 1, "sln no args -> 1")
    check(cmd.execute(["/lib/libc.so"]) == 1, "sln one arg -> 1")
    check(cmd.execute(["/lib/libc.so", "/lib/libc.so.6"]) == 0, "sln two args -> 0")

    # MktempCommand
    cmd = MktempCommand()
    check(cmd.name == "mktemp", "mktemp name")
    check(cmd.execute() == 0, "mktemp no args -> 0")
    check(cmd.execute(["-d"]) == 0, "mktemp -d -> 0")
    check(cmd.execute(["-t", "test.XXXXXX"]) == 0, "mktemp -t -> 0")
    check(cmd.execute(["-h"]) == 0, "mktemp -h -> 0")
    check(cmd.execute(["/tmp/tmp.XXXXXX"]) == 0, "mktemp template -> 0")

    # SetfdprmCommand
    cmd = SetfdprmCommand()
    check(cmd.name == "setfdprm", "setfdprm name")
    check(cmd.execute() == 1, "setfdprm no args -> 1")
    check(cmd.execute(["/dev/fd0"]) == 1, "setfdprm one arg -> 1")
    check(cmd.execute(["/dev/fd0", "1440"]) == 0, "setfdprm device size -> 0")

    # RdevCommand
    cmd = RdevCommand()
    check(cmd.name == "rdev", "rdev name")
    check(cmd.execute() == 0, "rdev no args -> 0")
    check(cmd.execute(["/dev/sda1"]) == 0, "rdev device -> 0")
    check(cmd.execute(["/dev/sda1", "/boot/vmlinuz"]) == 0, "rdev device kernel -> 0")

    print(f"sbin/maintenance.py: {tests_passed} passed, {tests_failed} failed")
    return tests_failed == 0


if __name__ == "__main__":
    _selftest()
