"""
UmerOS /bin Permission Management Commands
=============================================
Implementation of permission and ownership management commands per FHS 3.0.

Commands implemented:
  chmod  - Change file mode bits
  chown  - Change file owner and group
  chgrp  - Change group ownership
"""

from __future__ import annotations

import os
import re
import stat
import sys
from dataclasses import dataclass
from enum import IntEnum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


# ─── Enums ───────────────────────────────────────────────────────────────────

class ChmodMode(IntEnum):
    """Chmod operation modes."""
    SYMBOLIC = 0
    OCTAL = 1


class WhoFlag(IntEnum):
    """Symbolic mode who flags."""
    USER = 0
    GROUP = 1
    OTHER = 2
    ALL = 3


class PermChange(IntEnum):
    """Permission change operations."""
    ADD = 0
    REMOVE = 1
    SET = 2


# ─── Exceptions ──────────────────────────────────────────────────────────────

class ChmodError(Exception):
    """Base exception for chmod errors."""
    def __init__(self, message: str, exit_code: int = 1):
        self.message = message
        self.exit_code = exit_code
        super().__init__(f"chmod: {message}")


class ChownError(Exception):
    """Base exception for chown errors."""
    def __init__(self, message: str, exit_code: int = 1):
        self.message = message
        self.exit_code = exit_code
        super().__init__(f"chown: {message}")


class ChgrpError(Exception):
    """Base exception for chgrp errors."""
    def __init__(self, message: str, exit_code: int = 1):
        self.message = message
        self.exit_code = exit_code
        super().__init__(f"chgrp: {message}")


# ─── Symbolic Mode Parser ───────────────────────────────────────────────────

@dataclass
class SymbolicPermission:
    """Represents a symbolic permission change."""
    who: WhoFlag
    op: PermChange
    perms: str  # e.g., "rwx", "rx", "w"

    def __str__(self) -> str:
        who_chars = ["u", "g", "o", "a"]
        op_chars = ["+", "-", "="]
        return f"{who_chars[self.who]}{op_chars[self.op]}{self.perms}"


class SymbolicModeParser:
    """
    Parse symbolic mode strings like u+x, g-w, a=r, etc.
    """

    # Permission letter to bit mapping
    PERM_BITS = {
        "r": stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH,
        "w": stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH,
        "x": stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH,
    }

    WHO_BITS = {
        "u": stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR,
        "g": stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP,
        "o": stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH,
    }

    @classmethod
    def parse(cls, mode_str: str, current_mode: int) -> int:
        """Parse symbolic mode and apply to current mode."""
        # Handle comma-separated clauses
        clauses = mode_str.split(",")
        new_mode = current_mode

        for clause in clauses:
            new_mode = cls._apply_clause(clause.strip(), new_mode)

        return new_mode & 0o7777  # Preserve setuid/setgid/sticky bits

    @classmethod
    def _apply_clause(cls, clause: str, current_mode: int) -> int:
        """Apply a single symbolic clause."""
        # Parse who, op, perms
        match = re.match(r"([ugoa]*)([+-=])([rwxXst]*)", clause)
        if not match:
            raise ChmodError(f"invalid mode: '{clause}'")

        who_str, op_str, perms_str = match.groups()

        # Determine who
        if not who_str:
            who = WhoFlag.ALL
        elif who_str == "a":
            who = WhoFlag.ALL
        elif who_str == "u":
            who = WhoFlag.USER
        elif who_str == "g":
            who = WhoFlag.GROUP
        elif who_str == "o":
            who = WhoFlag.OTHER
        else:
            raise ChmodError(f"invalid who: '{who_str}'")

        # Determine operation
        if op_str == "+":
            op = PermChange.ADD
        elif op_str == "-":
            op = PermChange.REMOVE
        elif op_str == "=":
            op = PermChange.SET
        else:
            raise ChmodError(f"invalid operation: '{op_str}'")

        # Build permission bits
        perm_bits = 0
        for p in perms_str:
            if p in ("r", "w", "x"):
                perm_bits |= cls._get_perm_bit(p, who)
            elif p == "X":
                # Execute only if file is directory or already executable
                if stat.S_ISDIR(current_mode) or (current_mode & stat.S_IXUSR):
                    perm_bits |= cls._get_perm_bit("x", who)
            elif p == "s":
                # Setuid/setgid
                if who in (WhoFlag.USER, WhoFlag.ALL):
                    perm_bits |= stat.S_ISUID
                if who in (WhoFlag.GROUP, WhoFlag.ALL):
                    perm_bits |= stat.S_ISGID
            elif p == "t":
                # Sticky bit
                perm_bits |= stat.S_ISVTX
            else:
                raise ChmodError(f"invalid permission: '{p}'")

        # Apply operation
        if op == PermChange.ADD:
            return current_mode | perm_bits
        elif op == PermChange.REMOVE:
            return current_mode & ~perm_bits
        elif op == PermChange.SET:
            # Clear the who bits first, then set
            who_mask = cls.WHO_BITS.get("u", 0)  # Will be overridden
            if who == WhoFlag.USER:
                who_mask = stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
            elif who == WhoFlag.GROUP:
                who_mask = stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP
            elif who == WhoFlag.OTHER:
                who_mask = stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH
            else:  # ALL
                who_mask = (stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |
                           stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP |
                           stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH)

            return (current_mode & ~who_mask) | perm_bits

        return current_mode

    @classmethod
    def _get_perm_bit(cls, perm: str, who: WhoFlag) -> int:
        """Get permission bit for specific who."""
        if perm not in cls.PERM_BITS:
            return 0

        base = cls.PERM_BITS[perm]
        if who == WhoFlag.USER:
            return base >> 6  # Shift to user position
        elif who == WhoFlag.GROUP:
            return (base >> 3) & 0o111  # Shift to group position
        elif who == WhoFlag.OTHER:
            return base & 0o111  # Other position
        else:  # ALL
            return base  # All positions

    @classmethod
    def parse_octal(cls, mode_str: str, current_mode: int) -> int:
        """Parse octal mode like 755, 644, etc."""
        try:
            # Handle 3-digit (no setuid/setgid/sticky)
            if len(mode_str) == 3:
                mode = int(mode_str, 8)
                return mode | (current_mode & ~0o777)
            # Handle 4-digit (with setuid/setgid/sticky)
            elif len(mode_str) == 4:
                return int(mode_str, 8)
            else:
                raise ChmodError(f"invalid mode: '{mode_str}'")
        except ValueError:
            raise ChmodError(f"invalid mode: '{mode_str}'")


# ─── Chmod Command ──────────────────────────────────────────────────────────

class ChmodCommand:
    """
    chmod - change file mode bits.

    Usage: chmod [OPTION]... MODE FILE...
           chmod [OPTION]... OCTAL-MODE FILE...
           chmod [OPTION]... --reference=RFILE FILE...

    Options:
      -c, --changes          like verbose but report only when a change is made
      -f, --silent, --quiet  suppress most error messages
      -v, --verbose          output a diagnostic for every file processed
      -R, --recursive        change files and directories recursively
      --preserve-root        fail silently while operating on the root '/' directory
      --no-preserve-root     do not treat '/' specially
      --reference=RFILE      use RFILE's mode instead of MODE values
    """

    def __init__(self) -> None:
        self.name = "chmod"

    def execute(
        self,
        mode: str,
        files: List[str],
        recursive: bool = False,
        verbose: bool = False,
        silent: bool = False,
        reference_file: Optional[str] = None,
        output: Optional[sys.stdout.__class__] = None,
    ) -> int:
        """Execute chmod command."""
        out = output or sys.stderr
        exit_code = 0

        if reference_file:
            return self._chmod_reference(files, reference_file, recursive, verbose, out)

        for filepath in files:
            result = self._chmod_single(filepath, mode, recursive, verbose, silent, out)
            if result != 0:
                exit_code = result

        return exit_code

    def _chmod_single(
        self,
        path: str,
        mode: str,
        recursive: bool,
        verbose: bool,
        silent: bool,
        output: Any,
    ) -> int:
        """Change mode on a single file."""
        if not os.path.exists(path) and not os.path.islink(path):
            if not silent:
                print(f"chmod: cannot access '{path}': No such file or directory", file=sys.stderr)
            return 1

        try:
            current_mode = os.stat(path).st_mode

            # Parse mode
            if re.match(r"^[0-7]{3,4}$", mode):
                new_mode = SymbolicModeParser.parse_octal(mode, current_mode)
            else:
                new_mode = SymbolicModeParser.parse(mode, current_mode)

            # Preserve setuid/setgid/sticky from current mode if not explicitly set
            preserved_bits = current_mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX)
            if not mode.endswith(("s", "t")):
                new_mode |= preserved_bits

            os.chmod(path, new_mode)

            if verbose:
                print(f"changed '{path}' from {oct(current_mode)[-3:]} to {oct(new_mode)[-3:]}", output)

            # Handle recursive directory traversal
            if recursive and os.path.isdir(path) and not os.path.islink(path):
                for root, dirs, files in os.walk(path):
                    for d in dirs:
                        dir_path = os.path.join(root, d)
                        try:
                            os.chmod(dir_path, new_mode)
                            if verbose:
                                print(f"changed '{dir_path}' to {oct(new_mode)[-3:]}", output)
                        except OSError as e:
                            if not silent:
                                print(f"chmod: cannot access '{dir_path}': {e}", file=sys.stderr)
                    for f in files:
                        file_path = os.path.join(root, f)
                        try:
                            os.chmod(file_path, new_mode)
                            if verbose:
                                print(f"changed '{file_path}' to {oct(new_mode)[-3:]}", output)
                        except OSError as e:
                            if not silent:
                                print(f"chmod: cannot access '{file_path}': {e}", file=sys.stderr)

            return 0

        except OSError as e:
            if not silent:
                print(f"chmod: changing permissions of '{path}': {e}", file=sys.stderr)
            return 1

    def _chmod_reference(
        self,
        files: List[str],
        reference_file: str,
        recursive: bool,
        verbose: bool,
        output: Any,
    ) -> int:
        """Use reference file's mode."""
        try:
            ref_stat = os.stat(reference_file)
            ref_mode = ref_stat.st_mode & 0o7777
            mode_str = oct(ref_mode)[-3:]
            exit_code = 0

            for filepath in files:
                result = self._chmod_single(filepath, mode_str, recursive, verbose, False, output)
                if result != 0:
                    exit_code = result

            return exit_code

        except OSError as e:
            print(f"chmod: cannot stat '{reference_file}': {e}", file=sys.stderr)
            return 1

    def get_supported_modes(self) -> List[str]:
        """Get list of supported mode formats."""
        return [
            "octal: 755, 644, 777, etc.",
            "symbolic: u+x, g-w, a=r, o+rx, etc.",
            "combined: u+x,g-w, etc.",
        ]


# ─── Chown Command ──────────────────────────────────────────────────────────

@dataclass
class UserSpec:
    """Parsed user specification."""
    user: Optional[str] = None
    group: Optional[str] = None
    has_colon: bool = False

    @classmethod
    def parse(cls, spec: str) -> "UserSpec":
        """Parse user:group specification."""
        if ":" in spec:
            parts = spec.split(":", 1)
            return cls(user=parts[0] or None, group=parts[1] or None, has_colon=True)
        return cls(user=spec, group=None, has_colon=False)


class ChownCommand:
    """
    chown - change file owner and group.

    Usage: chown [OPTION]... OWNER[:GROUP] FILE...
           chown [OPTION]... --reference=RFILE FILE...

    Options:
      -c, --changes          like verbose but report only when a change is made
      -f, --silent, --quiet  suppress most error messages
      -v, --verbose          output a diagnostic for every file processed
      -R, --recursive        change files and directories recursively
      -H                     dereference command-line symlinks
      -L                     dereference every symbolic link
      -P                     do not dereference any symbolic links (default)
      --from=CURRENT_OWNER[:CURRENT_GROUP]
                             change the owner and/or group of each file only if
                             its current owner and/or group match those specified
      --reference=RFILE      use RFILE's owner and group instead of values
      --no-preserve-root     do not treat '/' specially
      --preserve-root        fail silently while operating on the root '/' directory
    """

    def __init__(self) -> None:
        self.name = "chown"

    def execute(
        self,
        owner_spec: str,
        files: List[str],
        recursive: bool = False,
        verbose: bool = False,
        silent: bool = False,
        dereference: bool = False,
        from_owner: Optional[str] = None,
        reference_file: Optional[str] = None,
        output: Optional[sys.stdout.__class__] = None,
    ) -> int:
        """Execute chown command."""
        out = output or sys.stderr
        exit_code = 0

        if reference_file:
            return self._chown_reference(files, reference_file, recursive, verbose, out)

        user_spec = UserSpec.parse(owner_spec)

        for filepath in files:
            result = self._chown_single(
                filepath, user_spec, recursive, verbose, silent, dereference, from_owner, out
            )
            if result != 0:
                exit_code = result

        return exit_code

    def _chown_single(
        self,
        path: str,
        user_spec: UserSpec,
        recursive: bool,
        verbose: bool,
        silent: bool,
        dereference: bool,
        from_owner: Optional[str],
        output: Any,
    ) -> int:
        """Change owner on a single file."""
        if not os.path.exists(path) and not os.path.islink(path):
            if not silent:
                print(f"chown: cannot access '{path}': No such file or directory", file=sys.stderr)
            return 1

        try:
            # Get current ownership
            if dereference:
                st = os.stat(path)
            else:
                st = os.lstat(path)

            current_uid = st.st_uid
            current_gid = st.st_gid

            # Check --from constraint
            if from_owner:
                from_spec = UserSpec.parse(from_owner)
                if from_spec.user is not None:
                    # Check if current owner matches
                    try:
                        import pwd
                        current_user = pwd.getpwuid(current_uid).pw_name
                    except (ImportError, KeyError):
                        current_user = str(current_uid)

                    if from_spec.user != current_user:
                        return 0  # Skip, doesn't match

            # Resolve new uid/gid
            new_uid = self._resolve_uid(user_spec.user, current_uid)
            new_gid = self._resolve_gid(user_spec.group, current_gid, user_spec.has_colon)

            # Only change if something actually changed
            if new_uid == current_uid and new_gid == current_gid:
                return 0

            # Perform the change
            os.chown(path, new_uid, new_gid)

            if verbose:
                owner_str = user_spec.user or str(new_uid)
                group_str = user_spec.group or str(new_gid)
                print(f"changed ownership of '{path}' to {owner_str}:{group_str}", output)

            # Handle recursive directory traversal
            if recursive and os.path.isdir(path) and not os.path.islink(path):
                for root, dirs, files in os.walk(path):
                    for d in dirs:
                        dir_path = os.path.join(root, d)
                        try:
                            os.chown(dir_path, new_uid, new_gid)
                            if verbose:
                                print(f"changed ownership of '{dir_path}'", output)
                        except OSError as e:
                            if not silent:
                                print(f"chown: cannot access '{dir_path}': {e}", file=sys.stderr)
                    for f in files:
                        file_path = os.path.join(root, f)
                        try:
                            os.chown(file_path, new_uid, new_gid)
                            if verbose:
                                print(f"changed ownership of '{file_path}'", output)
                        except OSError as e:
                            if not silent:
                                print(f"chown: cannot access '{file_path}': {e}", file=sys.stderr)

            return 0

        except OSError as e:
            if not silent:
                print(f"chown: changing ownership of '{path}': {e}", file=sys.stderr)
            return 1

    def _chown_reference(
        self,
        files: List[str],
        reference_file: str,
        recursive: bool,
        verbose: bool,
        output: Any,
    ) -> int:
        """Use reference file's ownership."""
        try:
            ref_stat = os.stat(reference_file)
            ref_uid = ref_stat.st_uid
            ref_gid = ref_stat.st_gid

            exit_code = 0
            for filepath in files:
                try:
                    os.chown(filepath, ref_uid, ref_gid)
                    if verbose:
                        print(f"changed ownership of '{filepath}' to {ref_uid}:{ref_gid}", output)
                except OSError as e:
                    print(f"chown: cannot access '{filepath}': {e}", file=sys.stderr)
                    exit_code = 1

            return exit_code

        except OSError as e:
            print(f"chown: cannot stat '{reference_file}': {e}", file=sys.stderr)
            return 1

    def _resolve_uid(self, user: Optional[str], default: int) -> int:
        """Resolve user name to UID."""
        if user is None:
            return default

        # Check if it's already a number
        try:
            return int(user)
        except ValueError:
            pass

        # Try to look up by name
        try:
            import pwd
            return pwd.getpwnam(user).pw_uid
        except (ImportError, KeyError):
            pass

        # Try UmerOS user database
        try:
            from umeros.fs.users import UserDatabase
            db = UserDatabase()
            user_info = db.get_user(user)
            if user_info:
                return user_info.uid
        except (ImportError, Exception):
            pass

        raise ChownError(f"invalid user: '{user}'")

    def _resolve_gid(self, group: Optional[str], default: int, explicit_colon: bool) -> int:
        """Resolve group name to GID."""
        if group is None and not explicit_colon:
            return default
        if group is None:
            return default

        # Check if it's already a number
        try:
            return int(group)
        except ValueError:
            pass

        # Try to look up by name
        try:
            import grp
            return grp.getgrnam(group).gr_gid
        except (ImportError, KeyError):
            pass

        # Try UmerOS group database
        try:
            from umeros.fs.users import GroupDatabase
            db = GroupDatabase()
            group_info = db.get_group(group)
            if group_info:
                return group_info.gid
        except (ImportError, Exception):
            pass

        raise ChownError(f"invalid group: '{group}'")


# ─── Chgrp Command ──────────────────────────────────────────────────────────

class ChgrpCommand:
    """
    chgrp - change group ownership.

    Usage: chgrp [OPTION]... GROUP FILE...
           chgrp [OPTION]... --reference=RFILE FILE...

    Options:
      -c, --changes          like verbose but report only when a change is made
      -f, --silent, --quiet  suppress most error messages
      -v, --verbose          output a diagnostic for every file processed
      -R, --recursive        change files and directories recursively
      -H                     dereference command-line symlinks
      -L                     dereference every symbolic link
      -P                     do not dereference any symbolic links (default)
      --from=CURRENT_GROUP   change the group of each file only if its current
                             group matches the specified one
      --reference=RFILE      use RFILE's group instead of GROUP values
      --no-preserve-root     do not treat '/' specially
      --preserve-root        fail silently while operating on the root '/' directory
    """

    def __init__(self) -> None:
        self.name = "chgrp"

    def execute(
        self,
        group: str,
        files: List[str],
        recursive: bool = False,
        verbose: bool = False,
        silent: bool = False,
        dereference: bool = False,
        from_group: Optional[str] = None,
        reference_file: Optional[str] = None,
        output: Optional[sys.stdout.__class__] = None,
    ) -> int:
        """Execute chgrp command."""
        out = output or sys.stderr
        exit_code = 0

        if reference_file:
            return self._chgrp_reference(files, reference_file, recursive, verbose, out)

        for filepath in files:
            result = self._chgrp_single(
                filepath, group, recursive, verbose, silent, dereference, from_group, out
            )
            if result != 0:
                exit_code = result

        return exit_code

    def _chgrp_single(
        self,
        path: str,
        group: str,
        recursive: bool,
        verbose: bool,
        silent: bool,
        dereference: bool,
        from_group: Optional[str],
        output: Any,
    ) -> int:
        """Change group on a single file."""
        if not os.path.exists(path) and not os.path.islink(path):
            if not silent:
                print(f"chgrp: cannot access '{path}': No such file or directory", file=sys.stderr)
            return 1

        try:
            # Get current group
            if dereference:
                st = os.stat(path)
            else:
                st = os.lstat(path)

            current_gid = st.st_gid

            # Check --from constraint
            if from_group:
                try:
                    import grp
                    current_group_name = grp.getgrgid(current_gid).gr_name
                except (ImportError, KeyError):
                    current_group_name = str(current_gid)

                if from_group != current_group_name:
                    return 0  # Skip, doesn't match

            # Resolve new gid
            new_gid = self._resolve_gid(group)

            # Only change if actually different
            if new_gid == current_gid:
                return 0

            # Perform the change
            os.chown(path, -1, new_gid)  # -1 means don't change uid

            if verbose:
                print(f"changed group of '{path}' to {group}", output)

            # Handle recursive directory traversal
            if recursive and os.path.isdir(path) and not os.path.islink(path):
                for root, dirs, files in os.walk(path):
                    for d in dirs:
                        dir_path = os.path.join(root, d)
                        try:
                            os.chown(dir_path, -1, new_gid)
                            if verbose:
                                print(f"changed group of '{dir_path}' to {group}", output)
                        except OSError as e:
                            if not silent:
                                print(f"chgrp: cannot access '{dir_path}': {e}", file=sys.stderr)
                    for f in files:
                        file_path = os.path.join(root, f)
                        try:
                            os.chown(file_path, -1, new_gid)
                            if verbose:
                                print(f"changed group of '{file_path}' to {group}", output)
                        except OSError as e:
                            if not silent:
                                print(f"chgrp: cannot access '{file_path}': {e}", file=sys.stderr)

            return 0

        except OSError as e:
            if not silent:
                print(f"chgrp: changing group of '{path}': {e}", file=sys.stderr)
            return 1

    def _chgrp_reference(
        self,
        files: List[str],
        reference_file: str,
        recursive: bool,
        verbose: bool,
        output: Any,
    ) -> int:
        """Use reference file's group."""
        try:
            ref_stat = os.stat(reference_file)
            ref_gid = ref_stat.st_gid

            exit_code = 0
            for filepath in files:
                try:
                    os.chown(filepath, -1, ref_gid)
                    if verbose:
                        print(f"changed group of '{filepath}' to {ref_gid}", output)
                except OSError as e:
                    print(f"chgrp: cannot access '{filepath}': {e}", file=sys.stderr)
                    exit_code = 1

            return exit_code

        except OSError as e:
            print(f"chgrp: cannot stat '{reference_file}': {e}", file=sys.stderr)
            return 1

    def _resolve_gid(self, group: str) -> int:
        """Resolve group name to GID."""
        # Check if it's already a number
        try:
            return int(group)
        except ValueError:
            pass

        # Try to look up by name
        try:
            import grp
            return grp.getgrnam(group).gr_gid
        except (ImportError, KeyError):
            pass

        # Try UmerOS group database
        try:
            from umeros.fs.users import GroupDatabase
            db = GroupDatabase()
            group_info = db.get_group(group)
            if group_info:
                return group_info.gid
        except (ImportError, Exception):
            pass

        raise ChgrpError(f"invalid group: '{group}'")


# ─── Utility Functions ──────────────────────────────────────────────────────

def format_mode(mode: int) -> str:
    """Format mode as ls-style string."""
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


def format_octal(mode: int) -> str:
    """Format mode as octal string."""
    return oct(mode & 0o7777)


def validate_mode(mode_str: str) -> bool:
    """Validate a mode string."""
    # Check octal
    if re.match(r"^[0-7]{3,4}$", mode_str):
        return True

    # Check symbolic
    if re.match(r"^[ugoa]*[+-=][rwxXst]*([,][ugoa]*[+-=][rwxXst]*)*$", mode_str):
        return True

    return False


# ─── Module Exports ──────────────────────────────────────────────────────────

__all__ = [
    "ChmodCommand",
    "ChownCommand",
    "ChgrpCommand",
    "SymbolicModeParser",
    "UserSpec",
    "ChmodError",
    "ChownError",
    "ChgrpError",
    "WhoFlag",
    "PermChange",
    "format_mode",
    "format_octal",
    "validate_mode",
]
