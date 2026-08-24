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
tmpfiles.d Configuration Manager for UmerOS
============================================
Manages tmpfiles.d(5) configuration files that control automatic
creation, cleaning, and mode-setting of temporary files and directories.

Covers /etc/tmpfiles.d, /usr/lib/tmpfiles.d, and /run/tmpfiles.d
per the systemd-tmpfiles specification.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import fnmatch
import os
import re
import stat
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TMPFILES_DIRS = [
    "/etc/tmpfiles.d",
    "/usr/lib/tmpfiles.d",
    "/run/tmpfiles.d",
    "/usr/local/lib/tmpfiles.d",
]

_LINE_RE = re.compile(
    r"^\s*(?P<type>[a-zA-ZqQpPdDcCbBxXTeEfFHhLzZvwarR])\s+"
    r"(?P<path>\S+)"
    r"(?:\s+(?P<mode>[0-9]+))?"
    r"(?:\s+(?P<user>\S+))?"
    r"(?:\s+(?P<group>\S+))?"
    r"(?:\s+(?P<age>\S+))?"
    r"(?:\s+(?P<argument>\S+))?"
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class TmpfilesType(Enum):
    """tmpfiles.d directive types."""
    f = auto()   # Create a file
    f_ = auto()  # Create or truncate
    w = auto()   # Write to file (append or create)
    d = auto()   # Create a directory
    D = auto()   # Create or empty directory
    e = auto()   # Adjust directory mode/owner (like d but don't create)
    v = auto()   # Create subvolume
    q = auto()   # Create subvolume + chattr +q
    Q = auto()   # Adjust subvolume
    p = auto()   # Create a named pipe (FIFO)
    p_ = auto()  # Create or remove named pipe
    L = auto()   # Create a symlink
    L_ = auto()  # Create or remove symlink
    c = auto()   # Create a character device
    c_ = auto()  # Create or remove character device
    b = auto()   # Create a block device
    b_ = auto()  # Create or remove block device
    C = auto()   # Copy files (recursive)
    x = auto()   # Exclude a path from cleanup
    X = auto()   # Exclude from cleanup (recursively)
    z = auto()   # Adjust file mode/owner
    Z = auto()   # Recursively set SELinux contexts
    s = auto()   # Create a socket file
    r = auto()   # Remove a file or directory
    R = auto()   # Recursively remove
    h = auto()   # Set file/directory attributes
    H = auto()   # Recursively set attributes
    a = auto()   # Set POSIX ACLs
    A = auto()   # Recursively set POSIX ACLs
    IGNORE = auto()  # Comment or blank line


@dataclass
class TmpfilesEntry:
    """A single parsed tmpfiles.d directive."""
    line_number: int
    source_file: str
    entry_type: str
    path: str
    mode: Optional[int] = None
    user: str = ""
    group: str = ""
    age: str = ""
    argument: str = ""
    is_exclusion: bool = False

    @property
    def mode_octal(self) -> str:
        if self.mode is not None:
            return oct(self.mode)
        return "default"

    @property
    def full_path(self) -> str:
        return os.path.expandvars(self.path)


@dataclass
class TmpfilesConfig:
    """A complete tmpfiles.d configuration file."""
    path: str
    filename: str
    entries: list[TmpfilesEntry]
    parse_errors: list[str] = field(default_factory=list)

    @property
    def create_entries(self) -> list[TmpfilesEntry]:
        return [e for e in self.entries if e.entry_type in ("f", "f_", "d", "D", "v", "q", "p", "L", "c", "b", "C") and not e.is_exclusion]

    @property
    def exclusion_entries(self) -> list[TmpfilesEntry]:
        return [e for e in self.entries if e.is_exclusion]

    @property
    def cleanup_entries(self) -> list[TmpfilesEntry]:
        return [e for e in self.entries if e.entry_type in ("r", "R")]

    @property
    def adjustment_entries(self) -> list[TmpfilesEntry]:
        return [e for e in self.entries if e.entry_type in ("z", "Z", "h", "H", "a", "A", "e")]


@dataclass
class CleanupResult:
    """Result of a tmpfiles cleanup operation."""
    scanned: int = 0
    cleaned: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    freed_bytes: int = 0

    @property
    def freed_human(self) -> str:
        if self.freed_bytes < 1024:
            return f"{self.freed_bytes} B"
        elif self.freed_bytes < 1024 * 1024:
            return f"{self.freed_bytes / 1024:.1f} KB"
        elif self.freed_bytes < 1024 * 1024 * 1024:
            return f"{self.freed_bytes / (1024 * 1024):.1f} MB"
        return f"{self.freed_bytes / (1024 * 1024 * 1024):.1f} GB"


@dataclass
class AgeSpec:
    """Parsed age specification for cleanup rules."""
    days: int = 0
    seconds: int = 0
    use_max: bool = False
    use_min: bool = False
    exclude: bool = False

    @classmethod
    def parse(cls, spec: str) -> AgeSpec:
        """Parse an age specification like '10d', '5w', '3m', '+3d', '-5d'."""
        if not spec or spec == "-":
            return cls()

        result = cls()
        s = spec

        if s.startswith("+"):
            result.use_min = True
            s = s[1:]
        elif s.startswith("-"):
            result.use_max = True
            s = s[1:]

        if s.endswith("d"):
            result.days = int(s[:-1]) if s[:-1].isdigit() else 0
        elif s.endswith("w"):
            result.days = int(s[:-1]) * 7 if s[:-1].isdigit() else 0
        elif s.endswith("m"):
            result.days = int(s[:-1]) * 30 if s[:-1].isdigit() else 0
        elif s.endswith("y"):
            result.days = int(s[:-1]) * 365 if s[:-1].isdigit() else 0
        elif s.isdigit():
            result.seconds = int(s)

        return result

    @property
    def cutoff_timestamp(self) -> float:
        """Timestamp before which files should be cleaned."""
        return time.time() - (self.days * 86400 + self.seconds)


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class TmpfilesManager:
    """
    Manages tmpfiles.d(5) configuration for automatic file lifecycle.

    Parses /etc/tmpfiles.d/*.conf, /usr/lib/tmpfiles.d/*.conf, and
    /run/tmpfiles.d/*.conf to determine which files/directories to
    create, clean, or adjust.

    Usage::

        tmpfiles = TmpfilesManager()
        configs = tmpfiles.load_all()
        result = tmpfiles.simulate_cleanup("/tmp")
    """

    def __init__(self, config_dirs: Optional[list[str]] = None) -> None:
        self._config_dirs = config_dirs or _TMPFILES_DIRS

    def load_all(self) -> list[TmpfilesConfig]:
        """Load and parse all tmpfiles.d configuration files."""
        configs: list[TmpfilesConfig] = []
        for config_dir in self._config_dirs:
            if not os.path.isdir(config_dir):
                continue
            for fname in sorted(os.listdir(config_dir)):
                if fname.endswith(".conf"):
                    fpath = os.path.join(config_dir, fname)
                    config = self.parse_file(fpath)
                    if config:
                        configs.append(config)
        return configs

    def parse_file(self, path: str) -> Optional[TmpfilesConfig]:
        """Parse a single tmpfiles.d configuration file."""
        try:
            with open(path, "r") as f:
                lines = f.readlines()
        except (OSError, UnicodeDecodeError):
            return None

        entries: list[TmpfilesEntry] = []
        errors: list[str] = []

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            match = _LINE_RE.match(stripped)
            if not match:
                errors.append(f"Line {i}: parse error: {stripped}")
                continue

            entry_type = match.group("type")
            path_val = match.group("path")
            mode_str = match.group("mode")
            user = match.group("user") or ""
            group = match.group("group") or ""
            age = match.group("age") or ""
            argument = match.group("argument") or ""

            # Handle exclusions (x/X prefix)
            is_exclusion = entry_type in ("x", "X")
            if is_exclusion:
                entry_type_char = entry_type
            else:
                entry_type_char = entry_type

            mode = int(mode_str, 8) if mode_str else None

            entries.append(TmpfilesEntry(
                line_number=i,
                source_file=path,
                entry_type=entry_type_char,
                path=path_val,
                mode=mode,
                user=user,
                group=group,
                age=age,
                argument=argument,
                is_exclusion=is_exclusion,
            ))

        return TmpfilesConfig(
            path=path,
            filename=os.path.basename(path),
            entries=entries,
            parse_errors=errors,
        )

    def simulate_cleanup(
        self,
        target_dir: str,
        configs: Optional[list[TmpfilesConfig]] = None,
    ) -> CleanupResult:
        """
        Simulate cleanup of a directory based on tmpfiles.d rules.

        Does not actually delete files — returns what would be cleaned.
        """
        if configs is None:
            configs = self.load_all()

        result = CleanupResult()
        target = os.path.expanduser(target_dir)

        if not os.path.isdir(target):
            return result

        # Collect all exclusion patterns
        exclusions: list[str] = []
        for config in configs:
            for entry in config.exclusion_entries:
                exclusions.append(entry.path)

        # Collect age-based cleanup rules
        age_rules: list[Tuple[str, AgeSpec]] = []
        for config in configs:
            for entry in config.create_entries:
                if entry.age and entry.age != "-":
                    age_spec = AgeSpec.parse(entry.age)
                    if age_spec.days > 0 or age_spec.seconds > 0:
                        age_rules.append((entry.path, age_spec))

        # Walk the target directory
        for root, dirs, files in os.walk(target):
            for fname in files + dirs:
                fpath = os.path.join(root, fname)
                result.scanned += 1

                # Check exclusions
                excluded = False
                for exc_pattern in exclusions:
                    if fnmatch.fnmatch(fpath, exc_pattern):
                        excluded = True
                        break
                if excluded:
                    result.skipped += 1
                    continue

                # Check age rules
                try:
                    mtime = os.path.getmtime(fpath)
                    for pattern, age_spec in age_rules:
                        if fnmatch.fnmatch(fpath, pattern):
                            if mtime < age_spec.cutoff_timestamp:
                                result.cleaned += 1
                                try:
                                    size = os.path.getsize(fpath) if os.path.isfile(fpath) else 0
                                    result.freed_bytes += size
                                except OSError:
                                    pass
                                break
                    else:
                        result.skipped += 1
                except OSError:
                    result.errors.append(f"Cannot stat: {fpath}")
                    result.skipped += 1

        return result

    def get_all_paths(self, configs: Optional[list[TmpfilesConfig]] = None) -> list[str]:
        """Get all paths that would be created/managed by tmpfiles.d rules."""
        if configs is None:
            configs = self.load_all()

        paths: list[str] = []
        for config in configs:
            for entry in config.create_entries:
                paths.append(entry.full_path)
        return sorted(set(paths))

    def find_config_for_path(self, path: str) -> list[TmpfilesEntry]:
        """Find all tmpfiles.d entries that apply to a given path."""
        configs = self.load_all()
        entries: list[TmpfilesEntry] = []

        for config in configs:
            for entry in config.entries:
                pattern = entry.path
                if fnmatch.fnmatch(path, pattern) or path.startswith(entry.path):
                    entries.append(entry)
        return entries

    def get_summary(self) -> dict[str, object]:
        """Get a summary of all tmpfiles.d configurations."""
        configs = self.load_all()
        total_entries = sum(len(c.entries) for c in configs)
        total_errors = sum(len(c.parse_errors) for c in configs)

        by_type: dict[str, int] = {}
        for config in configs:
            for entry in config.entries:
                by_type[entry.entry_type] = by_type.get(entry.entry_type, 0) + 1

        return {
            "config_files": len(configs),
            "total_entries": total_entries,
            "total_errors": total_errors,
            "entries_by_type": by_type,
            "config_dirs": [d for d in self._config_dirs if os.path.isdir(d)],
        }


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------

def _selftest():
    """Run a basic self-test for this module."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = TmpfilesManager(config_dirs=[tmpdir])
        summary = mgr.get_summary()
        assert "total_entries" in summary, "summary should have total_entries"

    print("selftest OK")
    return True


if __name__ == "__main__":
    _selftest()
