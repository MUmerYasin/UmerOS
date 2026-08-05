"""
UmerOS /bin Device File Commands
=================================
Implements mknod for creating block and character device files.

FSSTND / TLDP Required:
  mknod - make block or character special files
"""

from __future__ import annotations

import os
import stat as stat_mod
from typing import List, Tuple, Any


class MknodCommand:
    """
    Make block or character special files.

    Usage:
      mknod [-m mode] NAME TYPE [MAJOR MINOR]

    Types: b (block), c or u (character), p (FIFO/named pipe)

    Creates a device node with the specified type and major/minor numbers.
    """

    description = "make block or character special files"

    def execute(self, args: List[str], stdin: Any = None, stdout: Any = None) -> Tuple[int, str]:
        if not args:
            return 2, "mknod: missing operand"

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

        if "--help" in remaining or "-h" in remaining:
            return 0, self._usage()

        if not remaining:
            return 2, "mknod: missing operand"

        name = remaining[0]
        dev_type = remaining[1] if len(remaining) > 1 else ""

        if dev_type in ("b", "c", "u", "p"):
            pass
        else:
            return 2, f"mknod: invalid device type '{dev_type}'"

        major_num = 0
        minor_num = 0
        if dev_type in ("b", "c", "u"):
            if len(remaining) < 4:
                return 2, f"mknod: missing device number"
            try:
                major_num = int(remaining[2])
                minor_num = int(remaining[3])
            except ValueError:
                return 2, "mknod: invalid device number"

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
                return 0, f"mknod: {name}: {type_name} special ({major_num},{minor_num}) created"

            return 0, ""

        except FileExistsError:
            return 1, f"mknod: {name}: File exists"
        except PermissionError:
            return 1, f"mknod: {name}: Permission denied"
        except OSError as e:
            return 1, f"mknod: {name}: {e}"

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
            "  -v, --verbose     explain what is being done"
        )
