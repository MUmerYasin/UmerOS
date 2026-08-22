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

#!/usr/bin/env python3
"""
UmerOS tmpfiles.d Manager
=========================
Manages /etc/tmpfiles.d/*, /usr/lib/tmpfiles.d/*, /run/tmpfiles.d/*
for creating and cleaning up temporary files, runtime directories, and state directories.

Implements systemd-tmpfiles style configuration parsing and management.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

TMPFILES_D: str = "/etc/tmpfiles.d"
USR_LIB_TMPFILES: str = "/usr/lib/tmpfiles.d"
RUN_TMPFILES: str = "/run/tmpfiles.d"


# ---------------------------------------------------------------------------
# Type code mapping
# ---------------------------------------------------------------------------

TYPES: Dict[str, str] = {
    "d": "directory",
    "D": "directory, cleaned on cleanup",
    "f": "file",
    "F": "file, truncated on creation",
    "L": "symlink",
    "c": "character device",
    "b": "block device",
    "p": "named pipe (FIFO)",
    "x": "exclude path from cleanup",
    "w": "restore extended attributes",
    "z": "adjust file/directory permissions and ownership",
    "t": "set extended attributes",
}


# ---------------------------------------------------------------------------
# Common tmpfiles patterns (systemd-tmpfiles)
# ---------------------------------------------------------------------------

COMMON_TMPFILES_PATTERNS: Dict[str, List[Dict[str, str]]] = {
    "runtime-dirs": [
        {"type": "d", "path": "/run", "mode": "0755", "user": "root", "group": "root", "age": "-", "argument": ""},
        {"type": "d", "path": "/run/lock", "mode": "1777", "user": "root", "group": "root", "age": "-", "argument": ""},
        {"type": "d", "path": "/run/user", "mode": "0755", "user": "root", "group": "root", "age": "10d", "argument": ""},
        {"type": "d", "path": "/run/shutdown", "mode": "0755", "user": "root", "group": "root", "age": "-", "argument": ""},
    ],
    "temporary-dirs": [
        {"type": "d", "path": "/tmp", "mode": "1777", "user": "root", "group": "root", "age": "10d", "argument": ""},
        {"type": "d", "path": "/var/tmp", "mode": "1777", "user": "root", "group": "root", "age": "30d", "argument": ""},
    ],
    "state-dirs": [
        {"type": "d", "path": "/var/lib", "mode": "0755", "user": "root", "group": "root", "age": "-", "argument": ""},
        {"type": "d", "path": "/var/cache", "mode": "0755", "user": "root", "group": "root", "age": "-", "argument": ""},
        {"type": "d", "path": "/var/spool", "mode": "0755", "user": "root", "group": "root", "age": "-", "argument": ""},
        {"type": "d", "path": "/var/log", "mode": "0755", "user": "root", "group": "root", "age": "-", "argument": ""},
    ],
    "log-dirs": [
        {"type": "d", "path": "/var/log/journal", "mode": "0755", "user": "root", "group": "systemd-journal", "age": "-", "argument": ""},
        {"type": "d", "path": "/var/log/journal/remote", "mode": "0755", "user": "root", "group": "systemd-journal", "age": "-", "argument": ""},
    ],
    "pid-cache-dirs": [
        {"type": "d", "path": "/run/systemd", "mode": "0755", "user": "root", "group": "root", "age": "-", "argument": ""},
        {"type": "d", "path": "/run/systemd/seats", "mode": "0755", "user": "root", "group": "root", "age": "-", "argument": ""},
        {"type": "d", "path": "/run/systemd/sessions", "mode": "0755", "user": "root", "group": "root", "age": "-", "argument": ""},
        {"type": "d", "path": "/run/systemd/units", "mode": "0755", "user": "root", "group": "root", "age": "-", "argument": ""},
    ],
    "device-nodes": [
        {"type": "c", "path": "/dev/null", "mode": "0666", "user": "root", "group": "root", "age": "-", "argument": "1:3"},
        {"type": "c", "path": "/dev/zero", "mode": "0666", "user": "root", "group": "root", "age": "-", "argument": "1:5"},
        {"type": "c", "path": "/dev/full", "mode": "0666", "user": "root", "group": "root", "age": "-", "argument": "1:7"},
        {"type": "c", "path": "/dev/random", "mode": "0666", "user": "root", "group": "root", "age": "-", "argument": "1:8"},
        {"type": "c", "path": "/dev/urandom", "mode": "0666", "user": "root", "group": "root", "age": "-", "argument": "1:9"},
    ],
    "symlinks": [
        {"type": "L", "path": "/dev/core", "mode": "-", "user": "root", "group": "root", "age": "-", "argument": "/proc/kcore"},
        {"type": "L", "path": "/dev/fd", "mode": "-", "user": "root", "group": "root", "age": "-", "argument": "/proc/self/fd"},
        {"type": "L", "path": "/dev/stdin", "mode": "-", "user": "root", "group": "root", "age": "-", "argument": "/proc/self/fd/0"},
        {"type": "L", "path": "/dev/stdout", "mode": "-", "user": "root", "group": "root", "age": "-", "argument": "/proc/self/fd/1"},
        {"type": "L", "path": "/dev/stderr", "mode": "-", "user": "root", "group": "root", "age": "-", "argument": "/proc/self/fd/2"},
    ],
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TmpfilesError(Exception):
    """Base exception for tmpfiles operations."""


class ConfigNotFoundError(TmpfilesError):
    """Raised when a named configuration file cannot be found."""


class InvalidEntryError(TmpfilesError):
    """Raised when an entry fails validation."""


class EntryNotFoundError(TmpfilesError):
    """Raised when the requested entry index does not exist."""


class PathError(TmpfilesError):
    """Raised for path-related errors."""


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _ensure_dir(path: str) -> None:
    """Create *path* (and parents) if it does not already exist."""
    os.makedirs(path, exist_ok=True)


def _parse_mode(mode_str: str) -> int:
    """Convert an octal mode string (e.g. ``'0755'``) to an integer."""
    try:
        return int(mode_str, 8)
    except (ValueError, TypeError):
        return 0o755


def _format_mode(mode_int: int) -> str:
    """Format an integer mode back to an octal string like ``'0755'``."""
    return oct(mode_int)[2:].zfill(4)


def _is_valid_type_char(ch: str) -> bool:
    """Return True if *ch* is a recognised tmpfiles type code."""
    return ch in TYPES


def _age_to_seconds(age_str: str) -> Optional[int]:
    """Convert a systemd-style age string to seconds.

    Supported suffixes:
        s – seconds (default)
        m – minutes
        h – hours
        d – days
        w – weeks
        months – months  (30 days each)
        years – years    (365 days each)

    A value of ``'-'`` means *no age-based cleanup* and returns ``None``.
    """
    if age_str == "-" or age_str == "":
        return None

    match = re.match(r"^(\d+)(s|m|h|d|w|months?|years?)?$", age_str)
    if not match:
        return None

    value = int(match.group(1))
    unit = match.group(2) or "s"

    multipliers: Dict[str, int] = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
        "w": 604800,
        "month": 2_592_000,
        "months": 2_592_000,
        "year": 31_536_000,
        "years": 31_536_000,
    }

    return value * multipliers.get(unit, 1)


# ---------------------------------------------------------------------------
# Main manager class
# ---------------------------------------------------------------------------


class TmpfilesManager:
    """Manage systemd-tmpfiles.d style configuration files.

    Parameters
    ----------
    tmpfiles_d:
        Path to the system ``/etc/tmpfiles.d`` directory.
    usr_lib_tmpfiles:
        Path to the vendor ``/usr/lib/tmpfiles.d`` directory.
    run_tmpfiles:
        Path to the runtime ``/run/tmpfiles.d`` directory.
    """

    # ------------------------------------------------------------------ init

    def __init__(
        self,
        tmpfiles_d: str = TMPFILES_D,
        usr_lib_tmpfiles: str = USR_LIB_TMPFILES,
        run_tmpfiles: str = RUN_TMPFILES,
    ) -> None:
        self.tmpfiles_d = tmpfiles_d
        self.usr_lib_tmpfiles = usr_lib_tmpfiles
        self.run_tmpfiles = run_tmpfiles

        # In-memory config store:  name -> list of entry dicts
        self._configs: Dict[str, List[Dict[str, Any]]] = {}

        # Ensure the primary directories exist on disk
        for d in (self.tmpfiles_d, self.usr_lib_tmpfiles, self.run_tmpfiles):
            _ensure_dir(d)

        # Load every .conf we find
        self._load_all_configs()

    # ------------------------------------------------------------- internal

    def _load_all_configs(self) -> None:
        """Scan every search directory and load ``*.conf`` files."""
        for search_dir in (self.tmpfiles_d, self.usr_lib_tmpfiles, self.run_tmpfiles):
            if not os.path.isdir(search_dir):
                continue
            for fname in sorted(os.listdir(search_dir)):
                if fname.endswith(".conf"):
                    full = os.path.join(search_dir, fname)
                    name = fname[:-5]  # strip '.conf'
                    if name not in self._configs:
                        self._configs[name] = self._parse_file(full)

    def _find_config_path(self, name: str) -> Optional[str]:
        """Return the first on-disk path for *name*, checking search dirs in
        priority order.  Returns ``None`` if not found."""
        for search_dir in (self.tmpfiles_d, self.usr_lib_tmpfiles, self.run_tmpfiles):
            candidate = os.path.join(search_dir, f"{name}.conf")
            if os.path.isfile(candidate):
                return candidate
        return None

    def _parse_file(self, filepath: str) -> List[Dict[str, Any]]:
        """Parse a single tmpfiles.d config file and return a list of entries."""
        entries: List[Dict[str, Any]] = []
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
                for lineno, raw_line in enumerate(fh, start=1):
                    entry = self._parse_tmpfiles_line(raw_line, lineno=lineno)
                    if entry is not None:
                        entries.append(entry)
        except OSError:
            pass
        return entries

    # --------------------------------------------------- line parsing/format

    @staticmethod
    def _parse_tmpfiles_line(
        line: str,
        lineno: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """Parse a single tmpfiles.d configuration line.

        Returns ``None`` for blank / comment lines.  Returns a dict with
        keys ``type``, ``path``, ``mode``, ``user``, ``group``, ``age``,
        ``argument``, ``comment``, ``lineno`` for valid lines.
        """
        stripped = line.strip()

        # Blank line or comment
        if not stripped or stripped.startswith("#") or stripped.startswith(";"):
            return None

        parts = stripped.split(None, 7)
        if len(parts) < 6:
            # Malformed – store anyway so validators can flag it
            return {
                "type": parts[0] if len(parts) >= 1 else "",
                "path": parts[1] if len(parts) >= 2 else "",
                "mode": parts[2] if len(parts) >= 3 else "0755",
                "user": parts[3] if len(parts) >= 4 else "root",
                "group": parts[4] if len(parts) >= 5 else "root",
                "age": parts[5] if len(parts) >= 6 else "-",
                "argument": " ".join(parts[6:]) if len(parts) >= 7 else "",
                "comment": "",
                "lineno": lineno,
                "_valid": False,
            }

        type_char = parts[0]
        path = parts[1]
        mode = parts[2]
        user = parts[3]
        group = parts[4]
        age = parts[5]
        argument = " ".join(parts[6:]) if len(parts) >= 7 else ""

        return {
            "type": type_char,
            "path": path,
            "mode": mode,
            "user": user,
            "group": group,
            "age": age,
            "argument": argument,
            "comment": "",
            "lineno": lineno,
            "_valid": True,
        }

    @staticmethod
    def _format_tmpfiles_line(entry: Dict[str, Any]) -> str:
        """Format an entry dict back to a tmpfiles.d config line."""
        parts = [
            entry.get("type", ""),
            entry.get("path", ""),
            entry.get("mode", "0755"),
            entry.get("user", "root"),
            entry.get("group", "root"),
            entry.get("age", "-"),
        ]
        argument = entry.get("argument", "")
        if argument:
            parts.append(argument)
        return " ".join(parts)

    # ------------------------------------------------------ public API: list

    def list_config_files(self) -> List[str]:
        """Return a sorted list of config names (without ``.conf`` suffix)
        found across all search directories.  Duplicates are reported once."""
        names: set[str] = set()
        for search_dir in (self.tmpfiles_d, self.usr_lib_tmpfiles, self.run_tmpfiles):
            if not os.path.isdir(search_dir):
                continue
            for fname in os.listdir(search_dir):
                if fname.endswith(".conf"):
                    names.add(fname[:-5])
        return sorted(names)

    # ---------------------------------------------------- public API: get/set

    def get_config(self, name: str) -> List[Dict[str, Any]]:
        """Return the list of entries for config *name*.

        Raises
        ------
        ConfigNotFoundError
            If *name* does not exist in any search directory.
        """
        if name not in self._configs:
            # Try reloading from disk
            path = self._find_config_path(name)
            if path is None:
                raise ConfigNotFoundError(
                    f"Configuration '{name}' not found in any tmpfiles.d directory"
                )
            self._configs[name] = self._parse_file(path)
        return list(self._configs[name])

    def set_config(self, name: str, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Replace the entire configuration *name* with *entries*.

        Returns a result dict with ``success``, ``name``, ``entry_count``.
        """
        if not entries:
            return {
                "success": False,
                "name": name,
                "entry_count": 0,
                "error": "entries list must not be empty",
            }

        for idx, entry in enumerate(entries):
            if "type" not in entry or "path" not in entry:
                return {
                    "success": False,
                    "name": name,
                    "entry_count": len(entries),
                    "error": f"Entry at index {idx} is missing required 'type' or 'path' fields",
                }

        self._configs[name] = list(entries)
        self._write_config_to_disk(name)

        return {
            "success": True,
            "name": name,
            "entry_count": len(entries),
            "path": self._find_config_path(name) or os.path.join(self.tmpfiles_d, f"{name}.conf"),
        }

    # --------------------------------------------------- public API: CRUD

    def add_entry(
        self,
        name: str,
        type_char: str,
        path: str,
        mode: str = "0755",
        user: str = "root",
        group: str = "root",
        age: str = "-",
        argument: str = "",
        comment: str = "",
        position: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Append (or insert at *position*) a new entry to config *name*.

        Returns a result dict with ``success``, ``name``, ``entry_index``,
        ``entry``.
        """
        if not _is_valid_type_char(type_char):
            return {
                "success": False,
                "name": name,
                "error": f"Invalid type character '{type_char}'. Valid types: {', '.join(sorted(TYPES))}",
            }

        if not path:
            return {
                "success": False,
                "name": name,
                "error": "Path must not be empty",
            }

        # Ensure config exists in memory (create if needed)
        if name not in self._configs:
            self._configs[name] = []

        entry: Dict[str, Any] = {
            "type": type_char,
            "path": path,
            "mode": mode,
            "user": user,
            "group": group,
            "age": age,
            "argument": argument,
            "comment": comment,
            "lineno": 0,
            "_valid": True,
        }

        entries = self._configs[name]
        if position is None or position >= len(entries):
            entries.append(entry)
            idx = len(entries) - 1
        else:
            position = max(0, position)
            entries.insert(position, entry)
            idx = position

        self._write_config_to_disk(name)

        return {
            "success": True,
            "name": name,
            "entry_index": idx,
            "entry": entry,
            "total_entries": len(entries),
        }

    def remove_entry(self, name: str, entry_index: int) -> Dict[str, Any]:
        """Remove the entry at *entry_index* from config *name*.

        Returns a result dict with ``success``, ``name``, ``removed``.
        """
        if name not in self._configs:
            path = self._find_config_path(name)
            if path is None:
                return {
                    "success": False,
                    "name": name,
                    "error": f"Configuration '{name}' not found",
                }
            self._configs[name] = self._parse_file(path)

        entries = self._configs[name]
        if entry_index < 0 or entry_index >= len(entries):
            return {
                "success": False,
                "name": name,
                "error": f"Entry index {entry_index} out of range (0..{len(entries) - 1})",
            }

        removed = entries.pop(entry_index)
        self._write_config_to_disk(name)

        return {
            "success": True,
            "name": name,
            "removed": removed,
            "remaining_entries": len(entries),
        }

    def get_entry(self, name: str, entry_index: int) -> Dict[str, Any]:
        """Return the single entry at *entry_index* from config *name*.

        Raises
        ------
        ConfigNotFoundError
        EntryNotFoundError
        """
        if name not in self._configs:
            path = self._find_config_path(name)
            if path is None:
                raise ConfigNotFoundError(
                    f"Configuration '{name}' not found"
                )
            self._configs[name] = self._parse_file(path)

        entries = self._configs[name]
        if entry_index < 0 or entry_index >= len(entries):
            raise EntryNotFoundError(
                f"Entry index {entry_index} out of range for config '{name}' "
                f"(valid: 0..{len(entries) - 1})"
            )

        return dict(entries[entry_index])

    # ------------------------------------------------- public API: queries

    def list_all_entries(self) -> List[Dict[str, Any]]:
        """Merge entries from **every** known configuration and return them
        as a single flat list.

        Each entry includes an extra ``_config`` key with the source config
        name.
        """
        merged: List[Dict[str, Any]] = []
        for name in sorted(self._configs.keys()):
            for entry in self._configs[name]:
                enriched = dict(entry)
                enriched["_config"] = name
                merged.append(enriched)
        return merged

    def get_entries_by_type(self, type_char: str) -> List[Dict[str, Any]]:
        """Return all entries whose ``type`` field equals *type_char*."""
        if not _is_valid_type_char(type_char):
            return []
        return [
            dict(e) | {"_config": name}
            for name, entries in self._configs.items()
            for e in entries
            if e.get("type") == type_char
        ]

    def get_entries_by_path(self, path: str) -> List[Dict[str, Any]]:
        """Return all entries whose ``path`` field equals *path*."""
        normalised = os.path.normpath(path)
        return [
            dict(e) | {"_config": name}
            for name, entries in self._configs.items()
            for e in entries
            if os.path.normpath(e.get("path", "")) == normalised
        ]

    # ------------------------------------------------ public API: validate

    def validate_config(self, name: str) -> Dict[str, Any]:
        """Validate every entry in the named configuration.

        Returns a dict with ``success``, ``name``, ``errors``, ``warnings``,
        ``valid_entries``, ``total_entries``.
        """
        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        try:
            entries = self.get_config(name)
        except ConfigNotFoundError as exc:
            return {
                "success": False,
                "name": name,
                "errors": [{"message": str(exc)}],
                "warnings": [],
                "valid_entries": 0,
                "total_entries": 0,
            }

        for idx, entry in enumerate(entries):
            entry_errors: List[str] = []

            # Check type character
            type_char = entry.get("type", "")
            if not type_char:
                entry_errors.append("Missing or empty type character")
            elif not _is_valid_type_char(type_char):
                entry_errors.append(
                    f"Invalid type character '{type_char}'. "
                    f"Valid: {', '.join(sorted(TYPES))}"
                )

            # Check path
            path = entry.get("path", "")
            if not path:
                entry_errors.append("Missing or empty path")
            elif not path.startswith("/"):
                entry_errors.append(f"Path '{path}' is not absolute (must start with /)")

            # Check mode
            mode_str = entry.get("mode", "")
            if mode_str and mode_str != "-":
                try:
                    mode_int = int(mode_str, 8)
                    if mode_int < 0 or mode_int > 0o7777:
                        entry_errors.append(f"Mode '{mode_str}' is out of range")
                except ValueError:
                    entry_errors.append(f"Mode '{mode_str}' is not a valid octal number")

            # Check age
            age_str = entry.get("age", "-")
            if age_str != "-" and age_str != "":
                if _age_to_seconds(age_str) is None:
                    entry_errors.append(f"Age '{age_str}' has an unrecognised format")

            # Warn about non-root user/group for certain types
            if type_char in ("d", "D", "f", "F", "p"):
                if entry.get("user", "root") != "root":
                    warnings.append({
                        "index": idx,
                        "message": (
                            f"Non-root user '{entry.get('user')}' on {type_char} entry "
                            f"at '{path}'"
                        ),
                    })

            if entry_errors:
                errors.append({
                    "index": idx,
                    "path": path,
                    "errors": entry_errors,
                })

        return {
            "success": len(errors) == 0,
            "name": name,
            "errors": errors,
            "warnings": warnings,
            "valid_entries": len(entries) - len(errors),
            "total_entries": len(entries),
        }

    # ------------------------------------------- public API: create / clean

    def create_entries(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Simulate (or actually perform) the creation of files and directories.

        If *name* is ``None`` entries from **all** configs are processed.

        Returns a dict with ``success``, ``created``, ``skipped``, ``errors``.
        """
        created: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        if name is not None:
            try:
                entries = self.get_config(name)
                source_map = {name: entries}
            except ConfigNotFoundError as exc:
                return {
                    "success": False,
                    "created": [],
                    "skipped": [],
                    "errors": [{"error": str(exc)}],
                }
        else:
            source_map = dict(self._configs)

        for cfg_name, entries in source_map.items():
            for idx, entry in enumerate(entries):
                type_char = entry.get("type", "")
                path_str = entry.get("path", "")
                mode_str = entry.get("mode", "0755")

                if type_char in ("x", "w", "z", "t"):
                    # These types are informational / cleanup hints, not creation types
                    skipped.append({
                        "config": cfg_name,
                        "index": idx,
                        "type": type_char,
                        "path": path_str,
                        "reason": f"Type '{type_char}' ({TYPES.get(type_char, 'unknown')}) is not a creation type",
                    })
                    continue

                if not path_str:
                    errors.append({
                        "config": cfg_name,
                        "index": idx,
                        "error": "Empty path",
                    })
                    continue

                try:
                    if type_char == "d" or type_char == "D":
                        os.makedirs(path_str, exist_ok=True)
                        os.chmod(path_str, _parse_mode(mode_str))
                        created.append({
                            "config": cfg_name,
                            "index": idx,
                            "type": type_char,
                            "path": path_str,
                            "action": "directory_created",
                        })

                    elif type_char == "f" or type_char == "F":
                        parent = os.path.dirname(path_str)
                        if parent:
                            os.makedirs(parent, exist_ok=True)
                        if type_char == "F":
                            # Truncated write
                            with open(path_str, "w", encoding="utf-8") as fh:
                                fh.write("")
                        else:
                            # Create only if absent
                            if not os.path.exists(path_str):
                                with open(path_str, "a", encoding="utf-8") as fh:
                                    pass
                        os.chmod(path_str, _parse_mode(mode_str))
                        created.append({
                            "config": cfg_name,
                            "index": idx,
                            "type": type_char,
                            "path": path_str,
                            "action": "file_created",
                        })

                    elif type_char == "L":
                        argument = entry.get("argument", "")
                        if not argument:
                            errors.append({
                                "config": cfg_name,
                                "index": idx,
                                "error": "Symlink requires a non-empty argument (target)",
                            })
                            continue
                        parent = os.path.dirname(path_str)
                        if parent:
                            os.makedirs(parent, exist_ok=True)
                        if os.path.islink(path_str):
                            os.remove(path_str)
                        os.symlink(argument, path_str)
                        created.append({
                            "config": cfg_name,
                            "index": idx,
                            "type": type_char,
                            "path": path_str,
                            "target": argument,
                            "action": "symlink_created",
                        })

                    elif type_char == "p":
                        parent = os.path.dirname(path_str)
                        if parent:
                            os.makedirs(parent, exist_ok=True)
                        if not os.path.exists(path_str):
                            os.mkfifo(path_str)
                        os.chmod(path_str, _parse_mode(mode_str))
                        created.append({
                            "config": cfg_name,
                            "index": idx,
                            "type": type_char,
                            "path": path_str,
                            "action": "fifo_created",
                        })

                    elif type_char in ("c", "b"):
                        # Character / block devices require mknod privileges;
                        # record intent only in simulation mode.
                        created.append({
                            "config": cfg_name,
                            "index": idx,
                            "type": type_char,
                            "path": path_str,
                            "argument": entry.get("argument", ""),
                            "action": "device_node_recorded",
                            "note": "Device node creation requires root / mknod",
                        })

                    else:
                        skipped.append({
                            "config": cfg_name,
                            "index": idx,
                            "type": type_char,
                            "path": path_str,
                            "reason": f"Unhandled creation type '{type_char}'",
                        })

                except OSError as exc:
                    errors.append({
                        "config": cfg_name,
                        "index": idx,
                        "path": path_str,
                        "type": type_char,
                        "error": str(exc),
                    })

        return {
            "success": len(errors) == 0,
            "created": created,
            "skipped": skipped,
            "errors": errors,
        }

    def clean_entries(
        self,
        name: Optional[str] = None,
        age: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Simulate (or actually perform) the age-based cleanup.

        Parameters
        ----------
        name:
            If given only entries from this config are processed.
        age:
            Override the age threshold (e.g. ``'5d'``).  If ``None`` each
            entry's own ``age`` field is used.

        Returns a dict with ``success``, ``cleaned``, ``skipped``, ``errors``.
        """
        cleaned: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        if name is not None:
            try:
                entries = self.get_config(name)
                source_map = {name: entries}
            except ConfigNotFoundError as exc:
                return {
                    "success": False,
                    "cleaned": [],
                    "skipped": [],
                    "errors": [{"error": str(exc)}],
                }
        else:
            source_map = dict(self._configs)

        threshold_seconds = _age_to_seconds(age) if age else None

        for cfg_name, entries in source_map.items():
            for idx, entry in enumerate(entries):
                type_char = entry.get("type", "")
                path_str = entry.get("path", "")

                # Only D and d with age != '-' can be cleaned
                if type_char not in ("d", "D", "f", "F"):
                    skipped.append({
                        "config": cfg_name,
                        "index": idx,
                        "type": type_char,
                        "path": path_str,
                        "reason": f"Type '{type_char}' is not cleaned by age",
                    })
                    continue

                effective_age = age or entry.get("age", "-")
                age_secs = threshold_seconds or _age_to_seconds(effective_age)
                if age_secs is None:
                    skipped.append({
                        "config": cfg_name,
                        "index": idx,
                        "type": type_char,
                        "path": path_str,
                        "reason": "Age is '-' (no cleanup)",
                    })
                    continue

                if not os.path.exists(path_str):
                    skipped.append({
                        "config": cfg_name,
                        "index": idx,
                        "type": type_char,
                        "path": path_str,
                        "reason": "Path does not exist",
                    })
                    continue

                try:
                    mtime = os.path.getmtime(path_str)
                    age_now = time.time() - mtime
                    if age_now > age_secs:
                        if type_char == "D" and os.path.isdir(path_str):
                            shutil.rmtree(path_str)
                            cleaned.append({
                                "config": cfg_name,
                                "index": idx,
                                "type": type_char,
                                "path": path_str,
                                "age_seconds": int(age_now),
                                "action": "directory_removed",
                            })
                        elif type_char == "d" and os.path.isdir(path_str):
                            # Type 'd' only cleans *contents*, not the directory itself
                            for child in os.listdir(path_str):
                                child_path = os.path.join(path_str, child)
                                if os.path.isdir(child_path) and not os.path.islink(child_path):
                                    shutil.rmtree(child_path)
                                elif os.path.isfile(child_path) or os.path.islink(child_path):
                                    os.remove(child_path)
                            cleaned.append({
                                "config": cfg_name,
                                "index": idx,
                                "type": type_char,
                                "path": path_str,
                                "age_seconds": int(age_now),
                                "action": "directory_contents_cleaned",
                            })
                        elif type_char in ("f", "F") and os.path.isfile(path_str):
                            os.remove(path_str)
                            cleaned.append({
                                "config": cfg_name,
                                "index": idx,
                                "type": type_char,
                                "path": path_str,
                                "age_seconds": int(age_now),
                                "action": "file_removed",
                            })
                    else:
                        skipped.append({
                            "config": cfg_name,
                            "index": idx,
                            "type": type_char,
                            "path": path_str,
                            "age_seconds": int(age_now),
                            "threshold_seconds": age_secs,
                            "reason": "Not old enough for cleanup",
                        })
                except OSError as exc:
                    errors.append({
                        "config": cfg_name,
                        "index": idx,
                        "path": path_str,
                        "error": str(exc),
                    })

        return {
            "success": len(errors) == 0,
            "cleaned": cleaned,
            "skipped": skipped,
            "errors": errors,
        }

    # ------------------------------------------------ public API: standards

    def get_standard_configs(self) -> Dict[str, List[Dict[str, Any]]]:
        """Return the built-in standard tmpfiles patterns.

        Keys are logical group names (``'runtime-dirs'``, ``'temporary-dirs'``,
        etc.) and values are lists of entry dicts ready for use with
        :meth:`add_entry` or :meth:`set_config`.
        """
        return dict(COMMON_TMPFILES_PATTERNS)

    # ------------------------------------------------ public API: backup

    def backup_all(self, backup_path: str) -> Dict[str, Any]:
        """Copy every ``*.conf`` file from all search directories into
        *backup_path*, preserving filenames with a directory prefix.

        Returns a dict with ``success``, ``backed_up``, ``errors``.
        """
        _ensure_dir(backup_path)
        backed_up: List[str] = []
        errors: List[str] = []

        dir_labels = {
            self.tmpfiles_d: "etc_tmpfiles_d",
            self.usr_lib_tmpfiles: "usr_lib_tmpfiles",
            self.run_tmpfiles: "run_tmpfiles",
        }

        for search_dir, label in dir_labels.items():
            if not os.path.isdir(search_dir):
                continue
            dest_dir = os.path.join(backup_path, label)
            _ensure_dir(dest_dir)
            for fname in os.listdir(search_dir):
                if fname.endswith(".conf"):
                    src = os.path.join(search_dir, fname)
                    dst = os.path.join(dest_dir, fname)
                    try:
                        shutil.copy2(src, dst)
                        backed_up.append(f"{label}/{fname}")
                    except OSError as exc:
                        errors.append(f"{label}/{fname}: {exc}")

        return {
            "success": len(errors) == 0,
            "backup_path": backup_path,
            "backed_up": backed_up,
            "errors": errors,
        }

    # ------------------------------------------------- disk persistence

    def _write_config_to_disk(self, name: str) -> None:
        """Serialise the in-memory config *name* back to ``/etc/tmpfiles.d``."""
        dest_dir = self.tmpfiles_d
        _ensure_dir(dest_dir)
        filepath = os.path.join(dest_dir, f"{name}.conf")

        lines: List[str] = []
        lines.append(f"# Written by UmerOS tmpfiles manager – {datetime.now().isoformat()}")
        lines.append(f"# Config: {name}")
        lines.append("")

        for entry in self._configs.get(name, []):
            comment = entry.get("comment", "")
            if comment:
                lines.append(f"# {comment}")
            lines.append(self._format_tmpfiles_line(entry))

        lines.append("")

        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Standalone helper: pretty-print a config
# ---------------------------------------------------------------------------


def print_config(manager: TmpfilesManager, name: str) -> None:
    """Pretty-print the contents of a named configuration to stdout."""
    try:
        entries = manager.get_config(name)
    except ConfigNotFoundError as exc:
        print(f"ERROR: {exc}")
        return

    print(f"--- /etc/tmpfiles.d/{name}.conf ({len(entries)} entries) ---")
    for idx, entry in enumerate(entries):
        type_char = entry.get("type", "?")
        desc = TYPES.get(type_char, "unknown")
        line = manager._format_tmpfiles_line(entry)
        print(f"  [{idx:3d}] ({type_char} {desc:30s}) {line}")
    print()


# ---------------------------------------------------------------------------
# CLI / Demo
# ---------------------------------------------------------------------------


def _cli_demo() -> None:
    """Quick demonstration of the TmpfilesManager API."""
    print("=" * 72)
    print("UmerOS tmpfiles.d Manager – Demo")
    print("=" * 72)

    mgr = TmpfilesManager()

    # Show available types
    print("\nAvailable tmpfiles type codes:")
    for code, desc in sorted(TYPES.items()):
        print(f"  {code}  – {desc}")

    # Show standard configs
    print("\nStandard tmpfiles patterns:")
    for group, entries in mgr.get_standard_configs().items():
        print(f"  {group}: {len(entries)} entries")

    # Populate a demo config
    demo_name = "umeros-default"
    print(f"\nSetting up demo config '{demo_name}'…")

    mgr.set_config(demo_name, [
        {"type": "d", "path": "/run/umeros", "mode": "0755", "user": "root", "group": "root", "age": "-", "argument": ""},
        {"type": "d", "path": "/run/umeros/pids", "mode": "0755", "user": "root", "group": "root", "age": "1d", "argument": ""},
        {"type": "f", "path": "/run/umeros/lock", "mode": "0644", "user": "root", "group": "root", "age": "-", "argument": ""},
        {"type": "L", "path": "/run/umeros/current", "mode": "-", "user": "root", "group": "root", "age": "-", "argument": "/run/umeros/lock"},
        {"type": "d", "path": "/var/lib/umeros", "mode": "0700", "user": "umeros", "group": "umeros", "age": "-", "argument": ""},
    ])

    # List configs
    print(f"\nAll config files: {mgr.list_config_files()}")

    # Print config
    print_config(mgr, demo_name)

    # Add an entry
    print("Adding an entry…")
    result = mgr.add_entry(
        demo_name,
        type_char="p",
        path="/run/umeros/control",
        mode="0600",
        user="root",
        group="root",
    )
    print(f"  add_entry result: success={result['success']}, index={result.get('entry_index')}")

    # Validate
    print(f"\nValidating '{demo_name}'…")
    validation = mgr.validate_config(demo_name)
    print(f"  valid={validation['success']}, errors={len(validation['errors'])}, warnings={len(validation['warnings'])}")

    # Query by type
    dirs = mgr.get_entries_by_type("d")
    print(f"\nAll directory entries ({len(dirs)}):")
    for e in dirs:
        print(f"  [{e.get('_config', '?')}] {e.get('path')}")

    # Query by path
    path_entries = mgr.get_entries_by_path("/run/umeros")
    print(f"\nEntries matching /run/umeros ({len(path_entries)}):")
    for e in path_entries:
        print(f"  {e.get('type')} {e.get('path')}")

    # Remove an entry
    print("\nRemoving entry at index 1…")
    rm_result = mgr.remove_entry(demo_name, 1)
    print(f"  removed: {rm_result.get('removed', {}).get('path')}")

    # Print updated config
    print_config(mgr, demo_name)

    # Backup
    import tempfile
    backup_dir = tempfile.mkdtemp(prefix="umeros-tmpfiles-backup-")
    print(f"\nBacking up to {backup_dir}…")
    backup_result = mgr.backup_all(backup_dir)
    print(f"  backed up: {backup_result['backed_up']}")
    shutil.rmtree(backup_dir, ignore_errors=True)

    print("\n" + "=" * 72)
    print("Demo complete.")
    print("=" * 72)


if __name__ == "__main__":
    _cli_demo()
