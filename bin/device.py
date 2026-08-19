"""Device node management: mknod."""

from __future__ import annotations

import os
import stat as stat_mod
import sys
from typing import Any, List, Optional, Tuple


class MknodCommand:
    """Make block or character special files."""

    name = "mknod"
    description = "make block or character special files"

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if "--help" in args or "-h" in args:
            print(self._usage(), file=stdout or sys.stdout)
            return 0
        if "--version" in args:
            print("mknod (UmerOS) 1.0", file=stdout or sys.stdout)
            return 0
        if not args:
            print("mknod: missing operand", file=sys.stderr)
            print("Try 'mknod --help' for more information.", file=sys.stderr)
            return 1
        mode = None
        remaining = list(args)
        verbose = False
        if "-m" in remaining:
            idx = remaining.index("-m")
            if idx + 1 < len(remaining):
                mode = remaining[idx + 1]
                del remaining[idx:idx + 2]
        if "-v" in remaining:
            verbose = True
            remaining.remove("-v")
        if not remaining:
            print("mknod: missing operand", file=sys.stderr)
            return 1
        name = remaining[0]
        dev_type = remaining[1] if len(remaining) > 1 else ""
        if dev_type not in ("b", "c", "u", "p"):
            print(f"mknod: invalid device type '{dev_type}'", file=sys.stderr)
            return 1
        major_num = 0
        minor_num = 0
        if dev_type in ("b", "c", "u"):
            if len(remaining) < 4:
                print("mknod: missing device number", file=sys.stderr)
                return 1
            try:
                major_num = int(remaining[2])
                minor_num = int(remaining[3])
            except ValueError:
                print("mknod: invalid device number", file=sys.stderr)
                return 1
        try:
            if dev_type == "p":
                os.mkfifo(name, 0o644)
            elif dev_type == "b":
                os.mknod(name, 0o60600 | stat_mod.S_IFBLK, os.makedev(major_num, minor_num))
            elif dev_type in ("c", "u"):
                os.mknod(name, 0o60600 | stat_mod.S_IFCHR, os.makedev(major_num, minor_num))
            if mode is not None:
                try:
                    os.chmod(name, int(mode, 8))
                except ValueError:
                    os.chmod(name, int(mode))
            if verbose:
                type_name = {"b": "block", "c": "character", "u": "character", "p": "fifo"}[dev_type]
                print(f"mknod: {name}: {type_name} special ({major_num},{minor_num}) created", file=sys.stderr)
            return 0
        except FileExistsError:
            print(f"mknod: {name}: File exists", file=sys.stderr)
            return 1
        except PermissionError:
            print(f"mknod: {name}: Permission denied", file=sys.stderr)
            return 1
        except OSError as e:
            print(f"mknod: {name}: {e}", file=sys.stderr)
            return 1

    def _usage(self) -> str:
        return (
            "Usage: mknod [-m mode] [-v] NAME TYPE [MAJOR MINOR]\n"
            "\n"
            "Create a block or character special file.\n"
            "\n"
            "Types:\n"
            "  b        create a block (buffered) special file\n"
            "  c, u     create a character (unbuffered) special file\n"
            "  p        create a FIFO (named pipe)\n"
            "\n"
            "Options:\n"
            "  -m, --mode MODE   set file permission bits\n"
            "  -v, --verbose     explain what is being done\n"
            "  -h, --help        display this help"
        )


def _selftest() -> bool:
    """Run self-tests for device module."""
    try:
        mc = MknodCommand()
        # --help
        assert mc.execute(["--help"]) == 0
        # --version
        assert mc.execute(["--version"]) == 0
        # no-args returns 1
        assert mc.execute([]) == 1
        # missing device type
        assert mc.execute(["test_node"]) == 1
        # invalid type
        assert mc.execute(["test_node", "x"]) == 1
        # missing device number for block
        assert mc.execute(["test_node", "b"]) == 1

        return True
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"_selftest FAILED: {e}")
        return False
