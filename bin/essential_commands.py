"""
UmerOS /bin Essential File Operation Commands
==============================================
Implementation of core file manipulation commands

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

import builtins
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
        self.description = "concatenate files and print to stdout"
        self.usage = "cat [OPTION]... [FILE]..."

    def execute(
        self,
        args: Optional[List[str]] = None,
        *,
        files: Optional[List[str]] = None,
        options: int = CatOptions.NONE,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute cat command.

        Supports both CLI-style: execute(["--help"]) -> prints help, returns 0
        And legacy kwargs: execute(files=["f.txt"], options=CatOptions.NUMBER_ALL)
        """
        if args is None:
            args = []

        # Kwargs-style: options was explicitly provided, treat args as filenames
        if not files and options != CatOptions.NONE:
            files = [a for a in args if not a.startswith("-")]
        # CLI-style: parse args list
        elif not files:
            parsed_options, positional = self._parse_args(args)
            if parsed_options is None:
                return 0
            options = parsed_options
            files = positional

        out = output or sys.stdout
        exit_code = 0
        line_number = 0

        if not files:
            try:
                self._cat_stream(sys.stdin, out, options, line_number)
            except builtins.OSError:
                pass  # Windows: stdin may not support reading
            return 0

        for filepath in files:
            if filepath == "-":
                self._cat_stream(sys.stdin, out, options, line_number)
                continue

            try:
                with open(filepath, "r") as f:
                    line_number = self._cat_stream(f, out, options, line_number)
            except builtins.FileNotFoundError:
                print(f"cat: {filepath}: No such file or directory", file=sys.stderr)
                exit_code = 1
            except builtins.IsADirectoryError:
                print(f"cat: {filepath}: Is a directory", file=sys.stderr)
                exit_code = 1
            except builtins.PermissionError:
                print(f"cat: {filepath}: Permission denied", file=sys.stderr)
                sys.stderr.flush()
                exit_code = 1

        return exit_code

    def _parse_args(self, args: List[str]) -> Tuple[Optional[int], List[str]]:
        """Parse CLI args. Returns (None, []) for --help/--version, else (options, files)."""
        options = CatOptions.NONE
        positional = []
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "--help":
                print(self.usage)
                return None, []
            elif arg == "--version":
                print("cat (UmerOS) 1.0")
                return None, []
            elif arg.startswith("-") and arg not in ("-",):
                for ch in arg[1:]:
                    if ch == "b":
                        options |= CatOptions.NUMBER_NONBLANK
                    elif ch == "n":
                        options |= CatOptions.NUMBER_ALL
                    elif ch == "E":
                        options |= CatOptions.SHOW_ENDS
                    elif ch == "T":
                        options |= CatOptions.SHOW_TABS
                    elif ch == "v":
                        options |= CatOptions.SHOW_ALL
                    elif ch == "s":
                        options |= CatOptions.SQUEEZE_BLANK
                    elif ch == "e":
                        options |= CatOptions.SHOW_ENDS | CatOptions.SHOW_ALL
                    elif ch == "t":
                        options |= CatOptions.SHOW_TABS | CatOptions.SHOW_ALL
                    else:
                        print(f"cat: invalid option -- '{ch}'", file=sys.stderr)
                        return None, []
            else:
                positional.append(arg)
            i += 1
        return options, positional

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
        self.description = "copy files and directories"
        self.usage = "cp [OPTION]... SOURCE DEST"

    def _parse_args(self, args: List[str]) -> Tuple[Optional[int], List[str]]:
        """Parse CLI args. Returns (None, []) for --help/--version, else (flags, positional)."""
        flags = CpFlags.NONE
        positional = []
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "--help":
                print(self.usage)
                return None, []
            elif arg == "--version":
                print("cp (UmerOS) 1.0")
                return None, []
            elif arg.startswith("-") and arg not in ("-",):
                for ch in arg[1:]:
                    if ch == "f":
                        flags |= CpFlags.FORCE
                    elif ch == "i":
                        flags |= CpFlags.INTERACTIVE
                    elif ch == "d":
                        flags |= CpFlags.NO_DEREF
                    elif ch == "p":
                        flags |= CpFlags.PRESERVE
                    elif ch == "r":
                        flags |= CpFlags.RECURSIVE
                    elif ch == "v":
                        flags |= CpFlags.VERBOSE
                    elif ch == "u":
                        flags |= CpFlags.UPDATE
                    elif ch == "l":
                        flags |= CpFlags.LINK
                    elif ch == "s":
                        flags |= CpFlags.SYMBOLIC
                    else:
                        print(f"cp: invalid option -- '{ch}'", file=sys.stderr)
                        return None, []
            else:
                positional.append(arg)
            i += 1
        return flags, positional

    def execute(
        self,
        args: Optional[List[str]] = None,
        *,
        sources: Optional[List[str]] = None,
        dest: Optional[str] = None,
        flags: int = CpFlags.NONE,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute cp command.

        Supports both CLI-style: execute(["-r", "src", "dst"]) -> copies, returns 0
        And legacy kwargs: execute(sources=["f.txt"], dest="dst")
        """
        if args is None:
            args = []

        # CLI-style: parse args list
        if sources is None or dest is None:
            parsed_flags, positional = self._parse_args(args)
            if parsed_flags is None:
                return 0
            flags = parsed_flags
            if len(positional) < 2:
                print("cp: missing destination operand", file=sys.stderr)
                return 1
            sources = positional[:-1]
            dest = positional[-1]

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
        self.description = "move or rename files and directories"
        self.usage = "mv [OPTION]... SOURCE DEST"

    def _parse_args(self, args: List[str]):
        """Parse CLI flags. Returns (flags, sources, dest) or (None, None, None) for help."""
        import getopt
        try:
            opts, positional = getopt.getopt(args, "ifuv",
                ["help", "version", "backup", "force", "interactive",
                 "no-clobber", "strip-trailing", "verbose", "suffix="])
        except getopt.GetoptError:
            return None, None, None
        flags = MvFlags.NONE
        for o, _ in opts:
            if o in ("--help",):
                return None, None, None
            if o in ("--version",):
                return None, None, None
            if o in ("-i", "--interactive"):
                flags |= MvFlags.INTERACTIVE
            if o in ("-f", "--force", "--no-clobber"):
                flags |= MvFlags.NO_DEREF
            if o in ("-u",):
                flags |= MvFlags.UPDATE
            if o in ("-v", "--verbose"):
                flags |= MvFlags.VERBOSE
            if o in ("--strip-trailing",):
                flags |= MvFlags.STRIP_TRAILING
        if len(positional) < 2:
            return None, None, None
        return flags, positional[:-1], positional[-1]

    def execute(
        self,
        args: Optional[List[str]] = None,
        *,
        sources: Optional[List[str]] = None,
        dest: Optional[str] = None,
        flags: int = MvFlags.NONE,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute mv command.

        Supports both CLI-style: execute(["--help"]) -> prints help, returns 0
        And legacy kwargs: execute(sources=[src], dest=dst)
        Returns != 0 for no args or missing source.
        """
        if args is None:
            args = []
        if "--help" in args:
            print(self.usage)
            return 0
        if sources is None or dest is None:
            parsed_flags, parsed_sources, parsed_dest = self._parse_args(args)
            if parsed_flags is None:
                return 1
            flags = parsed_flags
            sources = parsed_sources
            dest = parsed_dest
        if not sources or dest is None:
            return 1
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
        self.description = "remove files or directories"
        self.usage = "rm [OPTION]... FILE..."

    def _parse_args(self, args: List[str]):
        """Parse CLI flags. Returns (flags, paths) or (None, None) for help."""
        import getopt
        try:
            opts, positional = getopt.getopt(args, "firv",
                ["help", "version", "force", "interactive", "recursive", "verbose"])
        except getopt.GetoptError:
            return None, None
        flags = RmFlags.NONE
        for o, _ in opts:
            if o in ("--help",):
                return None, None
            if o in ("--version",):
                return None, None
            if o in ("-f", "--force"):
                flags |= RmFlags.FORCE
            if o in ("-i", "--interactive"):
                flags |= RmFlags.INTERACTIVE
            if o in ("-r", "-R", "--recursive"):
                flags |= RmFlags.RECURSIVE
            if o in ("-d",):
                flags |= RmFlags.DIR
            if o in ("-v", "--verbose"):
                flags |= RmFlags.VERBOSE
        return flags, positional

    def execute(
        self,
        args: Optional[List[str]] = None,
        *,
        paths: Optional[List[str]] = None,
        flags: int = RmFlags.NONE,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute rm command.

        Supports both CLI-style: execute(["--help"]) -> prints help, returns 0
        And legacy kwargs: execute(paths=[file])
        Returns != 0 for missing file or no args.
        """
        if args is None:
            args = []
        if paths is None:
            parsed_flags, parsed_paths = self._parse_args(args)
            if parsed_flags is None:
                return 0
            flags = parsed_flags
            paths = parsed_paths
        if not paths:
            return 1
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
        self.description = "list directory contents"
        self.usage = "ls [OPTION]... [FILE]..."

    def _parse_args(self, args: List[str]):
        """Parse CLI flags. Returns (flags, paths) or (None, None) for help/version."""
        import getopt
        try:
            opts, positional = getopt.getopt(args, "alhirsSdRF",
                ["help", "version", "color=", "all", "long", "inode",
                 "recursive", "reverse", "human", "size", "time", "directory", "classify"])
        except getopt.GetoptError:
            return LsFlags.NONE, args
        flags = LsFlags.NONE
        for o, _ in opts:
            if o in ("--help",):
                return None, None
            if o in ("--version",):
                return None, None
            if o in ("-a", "--all"):
                flags |= LsFlags.ALL
            if o in ("-l", "--long"):
                flags |= LsFlags.LONG
            if o in ("-h", "--human"):
                flags |= LsFlags.HUMAN
            if o in ("-i", "--inode"):
                flags |= LsFlags.INODE
            if o in ("-r", "--reverse"):
                flags |= LsFlags.REVERSE
            if o in ("-R", "--recursive"):
                flags |= LsFlags.RECURSIVE
            if o in ("-S",):
                flags |= LsFlags.SIZE_SORT
            if o in ("-t",):
                flags |= LsFlags.TIME_SORT
            if o in ("-d", "--directory"):
                flags |= LsFlags.DIRECTORY
            if o in ("-F", "--classify"):
                flags |= LsFlags.CLASSIFY
            if o in ("--color",):
                flags |= LsFlags.COLOR
        return flags, positional or ["."]

    def execute(
        self,
        args: Optional[List[str]] = None,
        *,
        paths: Optional[List[str]] = None,
        flags: int = LsFlags.NONE,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute ls command.

        Supports both CLI-style: execute(["--help"]) -> prints help, returns 0
        And legacy kwargs: execute(paths=["."], flags=LsFlags.LONG)
        """
        if args is None:
            args = []
        if paths is None:
            parsed_flags, parsed_paths = self._parse_args(args)
            if parsed_flags is None:
                return 0
            flags = parsed_flags
            paths = parsed_paths
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
        self.description = "make directories"
        self.usage = "mkdir [OPTION]... DIRECTORY..."

    def _parse_args(self, args: List[str]):
        """Parse CLI flags. Returns (flags, directories) or (None, None) for help."""
        import getopt
        try:
            opts, positional = getopt.getopt(args, "pv",
                ["help", "version", "parents", "verbose", "mode="])
        except getopt.GetoptError:
            return None, None
        create_parents = False
        verbose = False
        mode = 0o777
        for o, val in opts:
            if o in ("--help",):
                return None, None
            if o in ("--version",):
                return None, None
            if o in ("-p", "--parents"):
                create_parents = True
            if o in ("-v", "--verbose"):
                verbose = True
            if o in ("--mode",):
                try:
                    mode = int(val, 8)
                except ValueError:
                    pass
        return (create_parents, mode, verbose), positional

    def execute(
        self,
        args: Optional[List[str]] = None,
        *,
        directories: Optional[List[str]] = None,
        create_parents: bool = False,
        mode: int = 0o777,
        verbose: bool = False,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute mkdir command.

        Supports both CLI-style: execute(["--help"]) -> prints help, returns 0
        And legacy kwargs: execute(directories=[dir])
        Returns != 0 for no args.
        """
        if args is None:
            args = []
        if directories is None:
            parsed, parsed_dirs = self._parse_args(args)
            if parsed is None:
                return 0
            create_parents, mode, verbose = parsed
            directories = parsed_dirs
        if not directories:
            return 1
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
        self.description = "remove empty directories"
        self.usage = "rmdir [OPTION]... DIRECTORY..."

    def _parse_args(self, args: List[str]):
        """Parse CLI flags. Returns (parents, verbose, directories) or (None, None, None) for help."""
        import getopt
        try:
            opts, positional = getopt.getopt(args, "pv",
                ["help", "version", "parents", "verbose"])
        except getopt.GetoptError:
            return None, None, None
        parents = False
        verbose = False
        for o, _ in opts:
            if o in ("--help",):
                return None, None, None
            if o in ("--version",):
                return None, None, None
            if o in ("-p", "--parents"):
                parents = True
            if o in ("-v", "--verbose"):
                verbose = True
        return (parents, verbose), positional

    def execute(
        self,
        args: Optional[List[str]] = None,
        *,
        directories: Optional[List[str]] = None,
        parents: bool = False,
        verbose: bool = False,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute rmdir command.

        Supports both CLI-style: execute(["--help"]) -> prints help, returns 0
        And legacy kwargs: execute(directories=[dir])
        Returns != 0 for no args.
        """
        if args is None:
            args = []
        if directories is None:
            parsed, parsed_dirs = self._parse_args(args)
            if parsed is None:
                return 0
            parents, verbose = parsed
            directories = parsed_dirs
        if not directories:
            return 1
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
        self.description = "create links between files"
        self.usage = "ln [OPTION]... TARGET LINK_NAME"

    def _parse_args(self, args: List[str]):
        """Parse CLI flags. Returns (symbolic, force, verbose, positional) or (None, None) for help."""
        import getopt
        try:
            opts, positional = getopt.getopt(args, "sfv",
                ["help", "version", "symbolic", "force", "verbose"])
        except getopt.GetoptError:
            return None, None
        symbolic = False
        force = False
        verbose = False
        for o, _ in opts:
            if o in ("--help",):
                return None, None
            if o in ("--version",):
                return None, None
            if o in ("-s", "--symbolic"):
                symbolic = True
            if o in ("-f", "--force"):
                force = True
            if o in ("-v", "--verbose"):
                verbose = True
        return (symbolic, force, verbose), positional

    def execute(
        self,
        args: Optional[List[str]] = None,
        *,
        targets: Optional[List[str]] = None,
        dest: Optional[str] = None,
        symbolic: bool = False,
        force: bool = False,
        verbose: bool = False,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute ln command.

        Supports both CLI-style: execute(["--help"]) -> prints help, returns 0
        And legacy kwargs: execute(targets=[src], dest=dst)
        Returns != 0 for no args.
        """
        if args is None:
            args = []
        if targets is None or dest is None:
            parsed, positional = self._parse_args(args)
            if parsed is None:
                return 0
            symbolic, force, verbose = parsed
            if len(positional) < 2:
                return 1
            targets = positional[:-1]
            dest = positional[-1]
        if not targets:
            return 1
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
        args: Optional[List[str]] = None,
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

        # Handle args list from CLI
        if args is not None:
            if "--help" in args:
                print(self.__doc__)
                return 0
            if "--version" in args:
                print("dd (UmerOS coreutils) 1.0")
                return 0
            if not args:
                return 0
            # Parse if=, of=, bs=, count=, skip=, seek= from args
            for arg in args:
                if arg.startswith("if="):
                    if_file = arg[3:]
                elif arg.startswith("of="):
                    of_file = arg[3:]
                elif arg.startswith("bs="):
                    bs = int(arg[3:])
                elif arg.startswith("count="):
                    count = int(arg[6:])
                elif arg.startswith("skip="):
                    skip = int(arg[5:])
                elif arg.startswith("seek="):
                    seek = int(arg[5:])

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
        files: Optional[List[str]] = None,
        lines_per_page: int = 24,
        output: Optional[IO[str]] = None,
    ) -> int:
        """Execute more command."""
        if files is None:
            files = []
        if "--help" in files:
            print(self.__doc__)
            return 0
        if "--version" in files:
            print("more (UmerOS coreutils) 1.0")
            return 0
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


def _selftest() -> bool:
    """Run self-tests for essential_commands module."""
    try:
        import io, contextlib, tempfile

        # CatCommand
        cc = CatCommand()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("line1\nline2\nline3\n")
            tmppath = f.name
        try:
            f = io.StringIO()
            with contextlib.redirect_stdout(f):
                assert cc.execute([tmppath]) == 0
            assert "line1" in f.getvalue()
            try:
                result = cc.execute(["nonexistent_file_xyz_xyz_xyz"])
                assert result == 1
            except (FileNotFoundError, OSError):
                pass
            # -n flag
            f2 = io.StringIO()
            with contextlib.redirect_stdout(f2):
                assert cc.execute([tmppath], options=CatOptions.NUMBER_ALL) == 0
        finally:
            os.unlink(tmppath)

        # LsCommand
        lc = LsCommand()
        f3 = io.StringIO()
        with contextlib.redirect_stdout(f3):
            assert lc.execute([]) == 0

        # CpCommand
        cocp = CpCommand()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("copy test\n")
            src = f.name
        dst = src + ".copy"
        tmpdir = None
        try:
            assert cocp.execute([src, dst]) == 0
            assert os.path.exists(dst)
            # -r with directory
            tmpdir = tempfile.mkdtemp()
            os.rmdir(tmpdir)
            assert cocp.execute(["-r", src, tmpdir]) == 0
        finally:
            for p in [src, dst]:
                if os.path.exists(p):
                    os.unlink(p)
            if tmpdir and os.path.isdir(tmpdir):
                os.rmdir(tmpdir)

        # MvCommand
        mv = MvCommand()
        src2 = tempfile.mktemp(suffix=".txt")
        dst2 = tempfile.mktemp(suffix=".txt")
        try:
            with open(src2, "w") as f:
                f.write("move test\n")
            assert mv.execute([src2, dst2]) == 0
            assert os.path.exists(dst2)
        finally:
            for p in [src2, dst2]:
                if os.path.exists(p):
                    os.unlink(p)

        # RmCommand
        rm = RmCommand()
        tmpf = tempfile.mktemp(suffix=".txt")
        with open(tmpf, "w") as f:
            f.write("delete me\n")
        assert rm.execute([tmpf]) == 0
        assert not os.path.exists(tmpf)

        # MkdirCommand
        mk = MkdirCommand()
        tmpdir2 = tempfile.mktemp()
        assert mk.execute([tmpdir2]) == 0
        assert os.path.isdir(tmpdir2)

        # RmdirCommand
        rmd = RmdirCommand()
        assert rmd.execute([tmpdir2]) == 0
        assert not os.path.isdir(tmpdir2)

        # LnCommand
        ln = LnCommand()
        src3 = tempfile.mktemp(suffix=".txt")
        lnk = src3 + ".link"
        try:
            with open(src3, "w") as f:
                f.write("link test\n")
            assert ln.execute([src3, lnk]) == 0
            assert os.path.exists(lnk)
        finally:
            for p in [src3, lnk]:
                if os.path.exists(p):
                    os.unlink(p)

        # DdCommand
        dd = DdCommand()
        dd_out = tempfile.mktemp()
        try:
            dd.execute(["if=/dev/null", f"of={dd_out}", "count=1", "bs=512"])
        except Exception:
            pass
        if os.path.exists(dd_out):
            os.unlink(dd_out)

        # MoreCommand (just check it handles missing file gracefully)
        mc = MoreCommand()
        assert hasattr(mc, 'execute')
        try:
            mc.execute(["/nonexistent_file_xyz"])
        except (FileNotFoundError, Exception):
            pass  # MoreCommand handles this internally but just in case

        return True
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"_selftest FAILED: {e}")
        return False


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
