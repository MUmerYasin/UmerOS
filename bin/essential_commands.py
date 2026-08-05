"""
UmerOS /bin Essential File Operation Commands
==============================================
Implementation of core file manipulation commands per FHS 3.0.

Commands implemented:
  cat    - Concatenate files and print to stdout
  cp     - Copy files and directories
  mv     - Move/rename files and directories
  rm     - Remove files and directories
  ls     - List directory contents
  mkdir  - Make directories
  ln     - Create hard/symbolic links
  rmdir  - Remove empty directories
  dd     - Convert and copy files
  mknod  - Make block/character device files
  more   - Pager for viewing files
"""

from __future__ import annotations

import os
import shutil
import stat
import sys
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any, BinaryIO, IO, List, Optional, Tuple, Union


# ─── Constants ───────────────────────────────────────────────────────────────

DEFAULT_BLOCK_SIZE = 512
LS_COLORS = {
    "dir": "\033[34m",       # Blue
    "link": "\033[36m",      # Cyan
    "exec": "\033[32m",      # Green
    "pipe": "\033[33m",      # Yellow
    "sock": "\033[35m",      # Magenta
    "block": "\033[33;40m",  # Yellow on black
    "char": "\033[33;40m",   # Yellow on black
    "reset": "\033[0m",
}


# ─── Enums ───────────────────────────────────────────────────────────────────

class CatOptions(IntEnum):
    """Cat command options."""
    NONE = 0
    NUMBER_NONBLANK = 1    # -b: number nonblank output lines
    NUMBER_ALL = 2         # -n: number all output lines
    SHOW_ENDS = 4          # -E: show $ at end of lines
    SHOW_TABS = 8          # -T: show ^I for tabs
    SHOW_ALL = 16          # -v: show non-printing chars
    SQUEEZE_BLANK = 32     # -s: squeeze multiple blank lines


class CpFlags(IntEnum):
    """cp command flags."""
    NONE = 0
    FORCE = 1              # -f: force overwrite
    INTERACTIVE = 2        # -i: prompt before overwrite
    NO_DEREF = 4           # -d: no-dereference (preserve links)
    PRESERVE = 8           # -p: preserve attributes
    RECURSIVE = 16         # -r: recursive copy
    VERBOSE = 32           # -v: verbose output
    UPDATE = 64            # -u: update only when newer
    LINK = 128             # -l: hard link instead of copy
    SYMBOLIC = 256         # -s: symbolic link instead of copy


class MvFlags(IntEnum):
    """mv command flags."""
    NONE = 0
    FORCE = 1              # -f: force overwrite
    INTERACTIVE = 2        # -i: prompt before overwrite
    NO_DEREF = 4           # -n: no-clobber
    VERBOSE = 8            # -v: verbose output
    UPDATE = 16            # -u: update only when newer
    STRIP_TRAILING = 32    # -T: treat dest as file, not dir


class RmFlags(IntEnum):
    """rm command flags."""
    NONE = 0
    FORCE = 1              # -f: force, no prompt
    INTERACTIVE = 2        # -i: prompt before each removal
    RECURSIVE = 4          # -r: recursive removal
    VERBOSE = 8            # -v: verbose output
    DIR = 16               # -d: remove empty directories


class LsFlags(IntEnum):
    """ls command flags."""
    NONE = 0
    ALL = 1                # -a: show hidden files
    LONG = 2               # -l: long format
    CLASSIFY = 4           # -F: append indicator
    HUMAN = 8              # -h: human-readable sizes
    INODE = 16             # -i: show inode numbers
    REVERSE = 32           # -r: reverse sort
    RECURSIVE = 64         # -R: recursive
    COLOR = 128            # --color: colorized output
    DIRECTORY = 256        # -d: list directories, not contents
    SIZE_SORT = 512        # -S: sort by size
    TIME_SORT = 1024       # -t: sort by time


# ─── Exceptions ──────────────────────────────────────────────────────────────

class CommandError(Exception):
    """Base exception for command errors."""
    def __init__(self, command: str, message: str, exit_code: int = 1):
        self.command = command
        self.message = message
        self.exit_code = exit_code
        super().__init__(f"{command}: {message}")


class FileNotFoundError(CommandError):
    """File not found error."""
    def __init__(self, command: str, path: str):
        super().__init__(command, f"{path}: No such file or directory")


class IsADirectoryError(CommandError):
    """Is a directory error."""
    def __init__(self, command: str, path: str):
        super().__init__(command, f"{path}: Is a directory")


class NotADirectoryError(CommandError):
    """Not a directory error."""
    def __init__(self, command: str, path: str):
        super().__init__(command, f"{path}: Not a directory")


class PermissionError(CommandError):
    """Permission denied error."""
    def __init__(self, command: str, path: str):
        super().__init__(command, f"{path}: Permission denied")


class DirectoryNotEmptyError(CommandError):
    """Directory not empty error."""
    def __init__(self, command: str, path: str):
        super().__init__(command, f"{path}: Directory not empty")


# ─── Cat Command ─────────────────────────────────────────────────────────────

class CatCommand:
    """
    cat - concatenate files and print to stdout.

    Usage: cat [OPTION]... [FILE]...
    """

    def __init__(self) -> None:
        self.name = "cat"

    def execute(
        self,
        files: List[str],
        options: int = CatOptions.NONE,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute cat command."""
        out = output or sys.stdout
        exit_code = 0
        line_number = 0
        prev_blank = False

        if not files:
            # Read from stdin
            self._cat_stream(sys.stdin, out, options, line_number)
            return 0

        for filepath in files:
            if filepath == "-":
                self._cat_stream(sys.stdin, out, options, line_number)
                continue

            try:
                with open(filepath, "r") as f:
                    line_number = self._cat_stream(
                        f, out, options, line_number
                    )
            except FileNotFoundError:
                print(f"cat: {filepath}: No such file or directory", file=sys.stderr)
                exit_code = 1
            except IsADirectoryError:
                print(f"cat: {filepath}: Is a directory", file=sys.stderr)
                exit_code = 1
            except PermissionError:
                print(f"cat: {filepath}: Permission denied", file=sys.stderr)
                exit_code = 1

        return exit_code

    def _cat_stream(
        self,
        input_stream: IO[str],
        output: IO[str],
        options: int,
        start_line: int,
    ) -> int:
        """Cat a single stream."""
        line_number = start_line
        squeeze = bool(options & CatOptions.SQUEEZE_BLANK)
        prev_blank = False

        for line in input_stream:
            is_blank = line.strip() == ""

            if squeeze and is_blank and prev_blank:
                continue
            prev_blank = is_blank

            if options & CatOptions.NUMBER_ALL:
                line_number += 1
                line = f"{line_number:6d}\t{line}"
            elif options & CatOptions.NUMBER_NONBLANK and not is_blank:
                line_number += 1
                line = f"{line_number:6d}\t{line}"

            if options & CatOptions.SHOW_ENDS:
                line = line.rstrip("\n") + "$\n"

            if options & CatOptions.SHOW_TABS:
                line = line.replace("\t", "^I")

            output.write(line)

        return line_number


# ─── Cp Command ──────────────────────────────────────────────────────────────

class CpCommand:
    """
    cp - copy files and directories.

    Usage: cp [OPTION]... SOURCE DEST
           cp [OPTION]... SOURCE... DIRECTORY
    """

    def __init__(self) -> None:
        self.name = "cp"

    def execute(
        self,
        sources: List[str],
        dest: str,
        flags: int = CpFlags.NONE,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute cp command."""
        out = output or sys.stderr

        # Check if dest is a directory
        if os.path.isdir(dest) and not (flags & CpFlags.NO_DEREF and os.path.islink(dest)):
            # Copy each source into directory
            for src in sources:
                result = self._copy_single(src, dest, flags, out)
                if result != 0:
                    return result
            return 0
        elif len(sources) > 1:
            print("cp: target must be a directory", file=sys.stderr)
            return 1
        else:
            return self._copy_single(sources[0], dest, flags, out)

    def _copy_single(
        self,
        src: str,
        dest: str,
        flags: int,
        output: IO[str],
    ) -> int:
        """Copy a single file or directory."""
        if not os.path.exists(src) and not os.path.islink(src):
            print(f"cp: cannot stat '{src}': No such file or directory", file=sys.stderr)
            return 1

        # Determine destination path
        if os.path.isdir(dest):
            dest_path = os.path.join(dest, os.path.basename(src))
        else:
            dest_path = dest

        # Handle symbolic link
        if os.path.islink(src) and (flags & CpFlags.SYMBOLIC):
            link_target = os.readlink(src)
            try:
                os.symlink(link_target, dest_path)
                if flags & CpFlags.VERBOSE:
                    print(f"'{src}' -> '{dest_path}'", output)
                return 0
            except OSError as e:
                print(f"cp: cannot create symbolic link '{dest_path}': {e}", file=sys.stderr)
                return 1

        # Handle hard link
        if flags & CpFlags.LINK:
            try:
                os.link(src, dest_path)
                if flags & CpFlags.VERBOSE:
                    print(f"'{src}' -> '{dest_path}'", output)
                return 0
            except OSError as e:
                print(f"cp: cannot create link '{dest_path}': {e}", file=sys.stderr)
                return 1

        # Handle directory copy
        if os.path.isdir(src):
            if not (flags & CpFlags.RECURSIVE):
                print(f"cp: -r not specified; omitting directory '{src}'", file=sys.stderr)
                return 1
            return self._copy_tree(src, dest_path, flags, output)

        # Handle file copy
        try:
            shutil.copy2(src, dest_path) if (flags & CpFlags.PRESERVE) else shutil.copy(src, dest_path)
            if flags & CpFlags.VERBOSE:
                print(f"'{src}' -> '{dest_path}'", output)
            return 0
        except OSError as e:
            print(f"cp: cannot create regular file '{dest_path}': {e}", file=sys.stderr)
            return 1

    def _copy_tree(
        self,
        src: str,
        dest: str,
        flags: int,
        output: IO[str],
    ) -> int:
        """Recursively copy a directory tree."""
        try:
            if flags & CpFlags.PRESERVE:
                shutil.copytree(src, dest, symlinks=not (flags & CpFlags.NO_DEREF))
            else:
                shutil.copytree(src, dest, symlinks=not (flags & CpFlags.NO_DEREF))
            if flags & CpFlags.VERBOSE:
                print(f"'{src}' -> '{dest}'", output)
            return 0
        except OSError as e:
            print(f"cp: cannot copy directory '{src}': {e}", file=sys.stderr)
            return 1


# ─── Mv Command ──────────────────────────────────────────────────────────────

class MvCommand:
    """
    mv - move/rename files and directories.

    Usage: mv [OPTION]... SOURCE DEST
           mv [OPTION]... SOURCE... DIRECTORY
    """

    def __init__(self) -> None:
        self.name = "mv"

    def execute(
        self,
        sources: List[str],
        dest: str,
        flags: int = MvFlags.NONE,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute mv command."""
        out = output or sys.stderr

        # Check if dest is a directory
        if os.path.isdir(dest) and not (flags & MvFlags.STRIP_TRAILING):
            for src in sources:
                result = self._move_single(src, dest, flags, out)
                if result != 0:
                    return result
            return 0
        elif len(sources) > 1:
            print("mv: target must be a directory", file=sys.stderr)
            return 1
        else:
            return self._move_single(sources[0], dest, flags, out)

    def _move_single(
        self,
        src: str,
        dest: str,
        flags: int,
        output: IO[str],
    ) -> int:
        """Move a single file or directory."""
        if not os.path.exists(src) and not os.path.islink(src):
            print(f"mv: cannot stat '{src}': No such file or directory", file=sys.stderr)
            return 1

        # Determine destination path
        if os.path.isdir(dest) and not (flags & MvFlags.STRIP_TRAILING):
            dest_path = os.path.join(dest, os.path.basename(src))
        else:
            dest_path = dest

        # Check no-clobber
        if flags & MvFlags.NO_DEREF and os.path.exists(dest_path):
            if flags & MvFlags.VERBOSE:
                print(f"mv: not overwriting '{dest_path}'", output)
            return 0

        # Check interactive
        if flags & MvFlags.INTERACTIVE and os.path.exists(dest_path):
            response = input(f"mv: overwrite '{dest_path}'? ")
            if response.lower() not in ("y", "yes"):
                return 0

        # Try os.rename first (atomic on same filesystem)
        try:
            os.rename(src, dest_path)
            if flags & MvFlags.VERBOSE:
                print(f"'{src}' -> '{dest_path}'", output)
            return 0
        except OSError:
            pass

        # Fall back to copy + delete
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dest_path)
                shutil.rmtree(src)
            else:
                shutil.copy2(src, dest_path)
                os.unlink(src)
            if flags & MvFlags.VERBOSE:
                print(f"'{src}' -> '{dest_path}'", output)
            return 0
        except OSError as e:
            print(f"mv: cannot move '{src}' to '{dest_path}': {e}", file=sys.stderr)
            return 1


# ─── Rm Command ──────────────────────────────────────────────────────────────

class RmCommand:
    """
    rm - remove files or directories.

    Usage: rm [OPTION]... FILE...
    """

    def __init__(self) -> None:
        self.name = "rm"

    def execute(
        self,
        paths: List[str],
        flags: int = RmFlags.NONE,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute rm command."""
        out = output or sys.stderr
        exit_code = 0

        for path in paths:
            result = self._remove(path, flags, out)
            if result != 0:
                exit_code = result

        return exit_code

    def _remove(self, path: str, flags: int, output: IO[str]) -> int:
        """Remove a single file or directory."""
        if not os.path.exists(path) and not os.path.islink(path):
            if not (flags & RmFlags.FORCE):
                print(f"rm: cannot remove '{path}': No such file or directory", file=sys.stderr)
                return 1
            return 0

        # Check interactive
        if flags & RmFlags.INTERACTIVE and not (flags & RmFlags.FORCE):
            response = input(f"rm: remove '{path}'? ")
            if response.lower() not in ("y", "yes"):
                return 0

        # Handle symlink
        if os.path.islink(path):
            try:
                os.unlink(path)
                if flags & RmFlags.VERBOSE:
                    print(f"removed '{path}'", output)
                return 0
            except OSError as e:
                print(f"rm: cannot remove '{path}': {e}", file=sys.stderr)
                return 1

        # Handle directory
        if os.path.isdir(path):
            if not (flags & (RmFlags.RECURSIVE | RmFlags.DIR)):
                print(f"rm: cannot remove '{path}': Is a directory", file=sys.stderr)
                return 1

            if flags & RmFlags.DIR:
                try:
                    os.rmdir(path)
                    if flags & RmFlags.VERBOSE:
                        print(f"removed directory '{path}'", output)
                    return 0
                except OSError as e:
                    print(f"rm: cannot remove '{path}': {e}", file=sys.stderr)
                    return 1

            if flags & RmFlags.RECURSIVE:
                try:
                    shutil.rmtree(path)
                    if flags & RmFlags.VERBOSE:
                        print(f"removed '{path}'", output)
                    return 0
                except OSError as e:
                    print(f"rm: cannot remove '{path}': {e}", file=sys.stderr)
                    return 1

        # Handle file
        try:
            os.unlink(path)
            if flags & RmFlags.VERBOSE:
                print(f"removed '{path}'", output)
            return 0
        except OSError as e:
            print(f"rm: cannot remove '{path}': {e}", file=sys.stderr)
            return 1


# ─── Ls Command ──────────────────────────────────────────────────────────────

@dataclass
class LsEntry:
    """Represents an entry in ls output."""
    name: str
    path: str
    is_dir: bool = False
    is_link: bool = False
    is_executable: bool = False
    is_pipe: bool = False
    is_socket: bool = False
    is_block: bool = False
    is_char: bool = False
    size: int = 0
    permissions: int = 0
    nlink: int = 1
    uid: int = 0
    gid: int = 0
    inode: int = 0
    mtime: float = 0.0
    link_target: str = ""

    @property
    def suffix(self) -> str:
        """Get indicator suffix."""
        if self.is_dir:
            return "/"
        if self.is_link:
            return "@"
        if self.is_executable:
            return "*"
        if self.is_pipe:
            return "|"
        if self.is_socket:
            return "="
        return ""


class LsCommand:
    """
    ls - list directory contents.

    Usage: ls [OPTION]... [FILE]...
    """

    def __init__(self) -> None:
        self.name = "ls"

    def execute(
        self,
        paths: List[str],
        flags: int = LsFlags.NONE,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute ls command."""
        out = output or sys.stdout
        exit_code = 0

        if not paths:
            paths = ["."]

        for path in paths:
            result = self._list_path(path, flags, out)
            if result != 0:
                exit_code = result

        return exit_code

    def _list_path(self, path: str, flags: int, output: IO[str]) -> int:
        """List a single path."""
        if not os.path.exists(path) and not os.path.islink(path):
            print(f"ls: cannot access '{path}': No such file or directory", file=sys.stderr)
            return 1

        # If directory and not -d, list contents
        if os.path.isdir(path) and not (flags & LsFlags.DIRECTORY):
            return self._list_directory(path, flags, output)
        else:
            entry = self._get_entry(path)
            self._print_entries([entry], flags, output)
            return 0

    def _list_directory(self, dirpath: str, flags: int, output: IO[str]) -> int:
        """List directory contents."""
        entries: List[LsEntry] = []

        try:
            for item in os.scandir(dirpath):
                name = item.name
                if not (flags & LsFlags.ALL) and name.startswith("."):
                    continue
                entry = self._get_entry(item.path)
                entries.append(entry)
        except PermissionError:
            print(f"ls: cannot open directory '{dirpath}': Permission denied", file=sys.stderr)
            return 1

        # Sort entries
        entries.sort(key=lambda e: e.name.lower())

        if flags & LsFlags.REVERSE:
            entries.reverse()

        if flags & LsFlags.SIZE_SORT:
            entries.sort(key=lambda e: e.size, reverse=True)
        elif flags & LsFlags.TIME_SORT:
            entries.sort(key=lambda e: e.mtime, reverse=True)

        self._print_entries(entries, flags, output)
        return 0

    def _get_entry(self, path: str) -> LsEntry:
        """Get entry information."""
        name = os.path.basename(path)
        entry = LsEntry(name=name, path=path)

        try:
            if os.path.islink(path):
                entry.is_link = True
                entry.link_target = os.readlink(path)
                try:
                    st = os.stat(path)
                except OSError:
                    st = os.lstat(path)
            else:
                st = os.stat(path)

            entry.is_dir = stat.S_ISDIR(st.st_mode)
            entry.is_executable = bool(st.st_mode & stat.S_IXUSR)
            entry.is_pipe = stat.S_ISFIFO(st.st_mode)
            entry.is_socket = stat.S_ISSOCK(st.st_mode)
            entry.is_block = stat.S_ISBLK(st.st_mode)
            entry.is_char = stat.S_ISCHR(st.st_mode)
            entry.size = st.st_size
            entry.permissions = st.st_mode
            entry.nlink = st.st_nlink
            entry.uid = st.st_uid
            entry.gid = st.st_gid
            entry.inode = st.st_ino
            entry.mtime = st.st_mtime
        except OSError:
            pass

        return entry

    def _print_entries(self, entries: List[LsEntry], flags: int, output: IO[str]) -> None:
        """Print entries."""
        if flags & LsFlags.LONG:
            self._print_long(entries, flags, output)
        else:
            self._print_short(entries, flags, output)

    def _print_long(self, entries: List[LsEntry], flags: int, output: IO[str]) -> None:
        """Print in long format."""
        for entry in entries:
            mode_str = self._mode_string(entry.permissions)
            nlink_str = str(entry.nlink)
            uid_str = str(entry.uid)
            gid_str = str(entry.gid)

            if flags & LsFlags.HUMAN:
                size_str = self._human_size(entry.size)
            else:
                size_str = str(entry.size)

            from datetime import datetime
            mtime_str = datetime.fromtimestamp(entry.mtime).strftime("%b %d %H:%M")

            name_str = entry.name
            if flags & LsFlags.CLASSIFY:
                name_str += entry.suffix

            if entry.is_link:
                name_str += f" -> {entry.link_target}"

            if flags & LsFlags.INODE:
                output.write(f"{entry.inode:>8} ")
            if flags & LsFlags.COLOR:
                color = self._get_color(entry)
                reset = LS_COLORS["reset"]
                name_str = f"{color}{name_str}{reset}"

            output.write(
                f"{mode_str} {nlink_str:>3} {uid_str:>4} {gid_str:>4} "
                f"{size_str:>8} {mtime_str} {name_str}\n"
            )

    def _print_short(self, entries: List[LsEntry], flags: int, output: IO[str]) -> None:
        """Print in short format."""
        names = []
        for entry in entries:
            name = entry.name
            if flags & LsFlags.CLASSIFY:
                name += entry.suffix
            if flags & LsFlags.COLOR:
                color = self._get_color(entry)
                reset = LS_COLORS["reset"]
                name = f"{color}{name}{reset}"
            names.append(name)

        output.write("  ".join(names) + "\n")

    def _mode_string(self, mode: int) -> str:
        """Convert mode to ls-style string."""
        result = ["-"] * 10

        if stat.S_ISDIR(mode):
            result[0] = "d"
        elif stat.S_ISLNK(mode):
            result[0] = "l"
        elif stat.S_ISFIFO(mode):
            result[0] = "p"
        elif stat.S_ISSOCK(mode):
            result[0] = "s"
        elif stat.S_ISBLK(mode):
            result[0] = "b"
        elif stat.S_ISCHR(mode):
            result[0] = "c"

        # Owner
        if mode & stat.S_IRUSR:
            result[1] = "r"
        if mode & stat.S_IWUSR:
            result[2] = "w"
        if mode & stat.S_IXUSR:
            result[3] = "x"

        # Group
        if mode & stat.S_IRGRP:
            result[4] = "r"
        if mode & stat.S_IWGRP:
            result[5] = "w"
        if mode & stat.S_IXGRP:
            result[6] = "x"

        # Other
        if mode & stat.S_IROTH:
            result[7] = "r"
        if mode & stat.S_IWOTH:
            result[8] = "w"
        if mode & stat.S_IXOTH:
            result[9] = "x"

        # Setuid/setgid/sticky
        if mode & stat.S_ISUID:
            result[3] = "s" if result[3] == "x" else "S"
        if mode & stat.S_ISGID:
            result[6] = "s" if result[6] == "x" else "S"
        if mode & stat.S_ISVTX:
            result[9] = "t" if result[9] == "x" else "T"

        return "".join(result)

    def _get_color(self, entry: LsEntry) -> str:
        """Get color for entry."""
        if entry.is_dir:
            return LS_COLORS["dir"]
        if entry.is_link:
            return LS_COLORS["link"]
        if entry.is_executable:
            return LS_COLORS["exec"]
        if entry.is_pipe:
            return LS_COLORS["pipe"]
        if entry.is_socket:
            return LS_COLORS["sock"]
        if entry.is_block or entry.is_char:
            return LS_COLORS["block"]
        return ""

    def _human_size(self, size: int) -> str:
        """Convert size to human-readable format."""
        for unit in ("B", "K", "M", "G", "T"):
            if abs(size) < 1024:
                return f"{size:.1f}{unit}" if unit != "B" else f"{size}{unit}"
            size /= 1024
        return f"{size:.1f}P"


# ─── Mkdir Command ───────────────────────────────────────────────────────────

class MkdirCommand:
    """
    mkdir - make directories.

    Usage: mkdir [OPTION]... DIRECTORY...
    """

    def __init__(self) -> None:
        self.name = "mkdir"

    def execute(
        self,
        directories: List[str],
        create_parents: bool = False,
        mode: int = 0o777,
        verbose: bool = False,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute mkdir command."""
        out = output or sys.stderr
        exit_code = 0

        for path in directories:
            try:
                if create_parents:
                    os.makedirs(path, mode=mode, exist_ok=False)
                else:
                    os.mkdir(path, mode=mode)

                if verbose:
                    print(f"mkdir: created directory '{path}'", out)
            except FileExistsError:
                print(f"mkdir: cannot create directory '{path}': File exists", file=sys.stderr)
                exit_code = 1
            except OSError as e:
                print(f"mkdir: cannot create directory '{path}': {e}", file=sys.stderr)
                exit_code = 1

        return exit_code


# ─── Rmdir Command ───────────────────────────────────────────────────────────

class RmdirCommand:
    """
    rmdir - remove empty directories.

    Usage: rmdir [OPTION]... DIRECTORY...
    """

    def __init__(self) -> None:
        self.name = "rmdir"

    def execute(
        self,
        directories: List[str],
        parents: bool = False,
        verbose: bool = False,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute rmdir command."""
        out = output or sys.stderr
        exit_code = 0

        for path in directories:
            try:
                if parents:
                    # Remove parents if empty
                    p = Path(path)
                    while p != p.parent:
                        if p.exists():
                            p.rmdir()
                            if verbose:
                                print(f"rmdir: removed directory '{p}'", out)
                        p = p.parent
                else:
                    os.rmdir(path)
                    if verbose:
                        print(f"rmdir: removed directory '{path}'", out)
            except OSError as e:
                print(f"rmdir: failed to remove '{path}': {e}", file=sys.stderr)
                exit_code = 1

        return exit_code


# ─── Ln Command ──────────────────────────────────────────────────────────────

class LnCommand:
    """
    ln - create links between files.

    Usage: ln [OPTION]... [-T] TARGET LINK_NAME
           ln [OPTION]... TARGET
           ln [OPTION]... TARGET... DIRECTORY
    """

    def __init__(self) -> None:
        self.name = "ln"

    def execute(
        self,
        targets: List[str],
        dest: str,
        symbolic: bool = False,
        force: bool = False,
        verbose: bool = False,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute ln command."""
        out = output or sys.stderr
        exit_code = 0

        if os.path.isdir(dest) and len(targets) > 1:
            for target in targets:
                result = self._link_single(target, dest, symbolic, force, verbose, out)
                if result != 0:
                    exit_code = result
        elif len(targets) == 1:
            result = self._link_single(targets[0], dest, symbolic, force, verbose, out)
            exit_code = result
        else:
            print("ln: missing target", file=sys.stderr)
            return 1

        return exit_code

    def _link_single(
        self,
        target: str,
        dest: str,
        symbolic: bool,
        force: bool,
        verbose: bool,
        output: IO[str],
    ) -> int:
        """Create a single link."""
        if not os.path.exists(target) and not os.path.islink(target):
            print(f"ln: failed to access '{target}': No such file or directory", file=sys.stderr)
            return 1

        # Determine link path
        if os.path.isdir(dest) and not symbolic:
            link_path = os.path.join(dest, os.path.basename(target))
        elif os.path.isdir(dest) and symbolic:
            link_path = os.path.join(dest, os.path.basename(target))
        else:
            link_path = dest

        # Remove existing link if force
        if force and os.path.exists(link_path):
            os.unlink(link_path)

        try:
            if symbolic:
                os.symlink(target, link_path)
            else:
                os.link(target, link_path)
            if verbose:
                print(f"'{link_path}' -> '{target}'", output)
            return 0
        except OSError as e:
            print(f"ln: cannot create link '{link_path}': {e}", file=sys.stderr)
            return 1


# ─── Dd Command ──────────────────────────────────────────────────────────────

class DdCommand:
    """
    dd - convert and copy a file.

    Usage: dd [OPERAND]...
           dd [OPTION]...

    Options:
      if=FILE       read from FILE instead of stdin
      of=FILE       write to FILE instead of stdout
      bs=BYTES      read and write up to BYTES at a time
      count=N       copy only N input blocks
      skip=N        skip N input blocks before reading
      seek=N        skip N output blocks before writing
    """

    def __init__(self) -> None:
        self.name = "dd"

    def execute(
        self,
        if_file: Optional[str] = None,
        of_file: Optional[str] = None,
        bs: int = DEFAULT_BLOCK_SIZE,
        count: Optional[int] = None,
        skip: int = 0,
        seek: int = 0,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute dd command."""
        out = output or sys.stderr

        try:
            # Open input
            if if_file:
                input_stream: BinaryIO = open(if_file, "rb")
            else:
                input_stream = sys.stdin.buffer

            # Open output
            if of_file:
                output_stream: BinaryIO = open(of_file, "wb")
            else:
                output_stream = sys.stdout.buffer

            # Skip input blocks
            if skip > 0:
                input_stream.seek(skip * bs)

            # Seek in output
            if seek > 0:
                output_stream.seek(seek * bs)

            # Copy blocks
            bytes_copied = 0
            blocks_copied = 0

            while True:
                data = input_stream.read(bs)
                if not data:
                    break

                output_stream.write(data)
                bytes_copied += len(data)
                blocks_copied += 1

                if count is not None and blocks_copied >= count:
                    break

            # Print statistics
            print(
                f"{blocks_copied}+{0} records in\n"
                f"{blocks_copied}+{0} records out\n"
                f"{bytes_copied} bytes copied",
                out
            )

            # Close files
            if if_file:
                input_stream.close()
            if of_file:
                output_stream.close()

            return 0

        except OSError as e:
            print(f"dd: {e}", file=sys.stderr)
            return 1


# ─── More Command ────────────────────────────────────────────────────────────

class MoreCommand:
    """
    more - file perusal filter for crt viewing.

    Usage: more [options] file ...
    """

    def __init__(self) -> None:
        self.name = "more"

    def execute(
        self,
        files: List[str],
        lines_per_page: int = 24,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute more command."""
        out = output or sys.stdout
        exit_code = 0

        for filepath in files:
            if filepath == "-":
                self._page_stream(sys.stdin, lines_per_page, out)
                continue

            try:
                with open(filepath, "r") as f:
                    self._page_stream(f, lines_per_page, out)
            except FileNotFoundError:
                print(f"more: {filepath}: No such file or directory", file=sys.stderr)
                exit_code = 1
            except IsADirectoryError:
                print(f"more: {filepath}: Is a directory", file=sys.stderr)
                exit_code = 1
            except PermissionError:
                print(f"more: {filepath}: Permission denied", file=sys.stderr)
                exit_code = 1

        return exit_code

    def _page_stream(self, stream: IO[str], lines_per_page: int, output: IO[str]) -> None:
        """Page through a stream."""
        line_count = 0

        for line in stream:
            output.write(line)
            line_count += 1

            if line_count >= lines_per_page:
                output.write("--More--")
                try:
                    input()
                except EOFError:
                    break
                line_count = 0


# ─── Module Exports ──────────────────────────────────────────────────────────

__all__ = [
    "CatCommand",
    "CpCommand",
    "MvCommand",
    "RmCommand",
    "LsCommand",
    "MkdirCommand",
    "RmdirCommand",
    "LnCommand",
    "DdCommand",
    "MoreCommand",
    "CatOptions",
    "CpFlags",
    "MvFlags",
    "RmFlags",
    "LsFlags",
    "CommandError",
]
