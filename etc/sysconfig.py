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
UmerOS /etc/sysconfig and /etc/default manager.

Handles Red Hat style /etc/sysconfig/* and Debian style /etc/default/*
configuration files. Provides parsing, reading, writing, backup, and
template generation for system defaults.

Usage:
    from sysconfig import SysconfigManager

    mgr = SysconfigManager()
    locale = mgr.get_i18n()
    mgr.set_sysconfig_value("network", "NETWORKING", "yes")
"""

from __future__ import annotations

import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

SYSCONFIG_DIR: str = "/etc/sysconfig"
DEFAULT_DIR: str = "/etc/default"
NETWORK_SCRIPTS: str = "/etc/sysconfig/network-scripts"
I18N: str = "/etc/sysconfig/i18n"
KEYBOARD: str = "/etc/sysconfig/keyboard"
CLOCK: str = "/etc/sysconfig/clock"
LANGUAGES: str = "/etc/default/locale"

# Standard key/value templates shipped with a fresh Red Hat / Debian install.
# Keys are file basenames, values are dicts of default key/value pairs.
_STANDARD_SYSCONFIG: Dict[str, Dict[str, str]] = {
    "network": {
        "NETWORKING": "yes",
        "NETWORKING_IPV6": "no",
        "HOSTNAME": "localhost.localdomain",
        "GATEWAY": "",
        "GATEWAYDEV": "",
        "NTPSERVERS": "",
        "NTPSPOOL": "yes",
    },
    "network-scripts": {
        "_description": "Directory under /etc/sysconfig for ifcfg-* files",
    },
    "i18n": {
        "SYSFONT": "lat2u-16",
        "SYSFONTACM": "iso01",
        "KEYTABLE": "us",
        "FONT": "",
        "FONT_MAP": "",
        "FONT_UNIMAP": "",
    },
    "keyboard": {
        "KEYBOARDTYPE": "pc",
        "KEYMAP": "us",
    },
    "clock": {
        "ZONE": "UTC",
        "ARC": "false",
        "SRMHZ": "",
        "NTPSERVERS": "",
        "SYNC_HWCLOCK": "no",
    },
    "init": {
        "DEFAULT_RUNLEVEL": "3",
    },
    "sshd": {
        "SSHD_USE_STRONG_RNG": "",
    },
    "iptables-config": {
        "IPTABLES_MODULES": "",
        "IPTABLES_SAVE_ON_STOP": "no",
        "IPTABLES_SAVE_ON_RESTART": "no",
        "IPTABLES_OPTIONS_NUMERIC": "yes",
    },
    "authconfig": {
        "PASSWDALGORITHM": "sha512",
        "PASSWDSALT_LEN": "16",
    },
}

_STANDARD_DEFAULT: Dict[str, Dict[str, str]] = {
    "locale": {
        "LANG": "en_US.UTF-8",
        "LANGUAGE": "en_US:en",
        "LC_ALL": "",
        "LC_CTYPE": "",
        "LC_NUMERIC": "",
        "LC_TIME": "",
        "LC_COLLATE": "",
        "LC_MONETARY": "",
        "LC_MESSAGES": "",
        "LC_PAPER": "",
        "LC_NAME": "",
        "LC_ADDRESS": "",
        "LC_TELEPHONE": "",
        "LC_MEASUREMENT": "",
        "LC_IDENTIFICATION": "",
    },
    "grub": {
        "GRUB_DEFAULT": "saved",
        "GRUB_TIMEOUT": "5",
        "GRUB_DISTRIBUTOR": "",
        "GRUB_CMDLINE_LINUX": "crashkernel=auto rhgb quiet",
        "GRUB_CMDLINE_LINUX_DEFAULT": "",
    },
    "dpkg": {
        "DPKG_OPT": "",
    },
    "sshd": {
        "SSHD_USE_STRONG_RNG": "",
    },
    "rcS": {
        "SINGLE": "",
        "RESOLV_CONF": "",
    },
    "ucf": {
        "OLD_DEFAULT_BACKUP_METHOD": "",
    },
    "update-notifier-common": {
        "DUPFRINT_ACTIVE": "0",
    },
    "anacron": {
        "ANACRON_RUN-parts": "/etc/cron.weekly",
    },
    "rsyslog": {
        "RSYSLOG_MODULE": "imuxsock",
    },
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SysconfigError(Exception):
    """Raised when a sysconfig operation fails."""


class SysconfigFileNotFoundError(SysconfigError):
    """Raised when the requested config file does not exist."""


class SysconfigWriteError(SysconfigError):
    """Raised when writing a config file fails."""


class SysconfigParseError(SysconfigError):
    """Raised when a config file cannot be parsed."""


# ---------------------------------------------------------------------------
# Helpers (module level)
# ---------------------------------------------------------------------------

def _is_valid_filename(name: str) -> bool:
    """Return True if *name* is a safe bare filename (no slashes, dots, spaces)."""
    if not name or "/" in name or "\\" in name:
        return False
    if name.startswith(".") or " " in name:
        return False
    # Only allow ASCII alphanumerics, hyphens, underscores
    return bool(re.match(r"^[A-Za-z0-9_\-]+$", name))


def _now_iso() -> str:
    """ISO 8601 timestamp for log/metadata."""
    return datetime.now().isoformat(timespec="seconds")


def _backup_item(src: Path, dest_dir: Path) -> Optional[str]:
    """Copy a single file into *dest_dir*, preserving the original basename."""
    if not src.is_file():
        return None
    dest = dest_dir / src.name
    try:
        shutil.copy2(str(src), str(dest))
        return str(dest)
    except OSError as exc:
        raise SysconfigWriteError(
            f"Backup failed for {src}: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# SysconfigManager
# ---------------------------------------------------------------------------

class SysconfigManager:
    """Manager for /etc/sysconfig (Red Hat) and /etc/default (Debian) files.

    Parameters
    ----------
    sysconfig_dir : str, optional
        Root of Red Hat style configs.  Defaults to ``/etc/sysconfig``.
    default_dir : str, optional
        Root of Debian style configs.  Defaults to ``/etc/default``.

    Examples
    --------
    >>> m = SysconfigManager()
    >>> m.get_i18n()
    {'SYSFONT': 'lat2u-16', ...}
    """

    def __init__(
        self,
        sysconfig_dir: str = SYSCONFIG_DIR,
        default_dir: str = DEFAULT_DIR,
    ) -> None:
        self.sysconfig_dir = Path(sysconfig_dir)
        self.default_dir = Path(default_dir)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_dir(self, path: Path) -> None:
        """Create *path* and all parents if they don't exist."""
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise SysconfigWriteError(
                f"Cannot create directory {path}: {exc}"
            ) from exc

    @staticmethod
    def _parse_key_value(filepath: Path) -> Dict[str, str]:
        """Parse a shell‑style KEY=value file.

        Recognises:
        - ``KEY=VALUE``
        - ``export KEY=VALUE``
        - ``KEY="VALUE"``
        - ``KEY='VALUE'``
        - ``KEY=VALUE # inline comment``
        - Blank lines and lines beginning with ``#`` (pure comments).

        Returns a dict mapping every key to its **unquoted** string value.
        """
        result: Dict[str, str] = {}
        if not filepath.is_file():
            return result

        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise SysconfigParseError(
                f"Cannot read {filepath}: {exc}"
            ) from exc

        for raw_line in text.splitlines():
            line = raw_line.strip()
            # skip blank / comment lines
            if not line or line.startswith("#"):
                continue

            # strip leading 'export '
            m_export = re.match(r"^export\s+", line)
            if m_export:
                line = line[m_export.end():]

            # KEY = VALUE …
            m_kv = re.match(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<val>.*)", line)
            if not m_kv:
                continue

            key = m_kv.group("key")
            val = m_kv.group("val").rstrip().rstrip("#").rstrip()

            # strip matching quotes
            if len(val) >= 2:
                if (val[0] == '"' and val[-1] == '"') or (
                    val[0] == "'" and val[-1] == "'"
                ):
                    val = val[1:-1]

            result[key] = val

        return result

    @staticmethod
    def _write_key_value(filepath: Path, settings: Dict[str, str], *,
                          header: Optional[str] = None) -> None:
        """Write a dict as ``KEY=VALUE`` lines, creating dirs as needed.

        An optional *header* comment block is prepended.
        """
        lines: List[str] = []
        if header:
            lines.append(f"# {header}")
            lines.append(f"# Generated by UmerOS SysconfigManager — {_now_iso()}")
            lines.append("")

        for key, value in settings.items():
            # value may itself contain spaces/quotes; wrap in double quotes
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key}="{escaped}"')

        lines.append("")  # trailing newline

        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text("\n".join(lines), encoding="utf-8")
        except OSError as exc:
            raise SysconfigWriteError(
                f"Cannot write {filepath}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Generic sysconfig accessors
    # ------------------------------------------------------------------

    def list_sysconfig(self) -> Dict[str, Dict[str, str]]:
        """Return every file in /etc/sysconfig as ``{name: {k: v, ...}}``.

        Non‑regular files (directories, symlinks to dirs, etc.) are skipped.
        """
        result: Dict[str, Dict[str, str]] = {}
        if not self.sysconfig_dir.is_dir():
            return result

        for item in sorted(self.sysconfig_dir.iterdir()):
            if item.is_file() and not item.is_symlink():
                result[item.name] = self._parse_key_value(item)

        return result

    def get_sysconfig(self, name: str) -> Dict[str, str]:
        """Return key/value pairs for ``/etc/sysconfig/<name>``.

        Raises :class:`SysconfigFileNotFoundError` if the file does not exist.
        """
        if not _is_valid_filename(name):
            raise SysconfigError(f"Invalid sysconfig name: {name!r}")

        target = self.sysconfig_dir / name
        if not target.is_file():
            raise SysconfigFileNotFoundError(
                f"Sysconfig file not found: {target}"
            )
        return self._parse_key_value(target)

    def set_sysconfig(self, name: str, settings: Dict[str, str]) -> Dict[str, Any]:
        """Write *settings* to ``/etc/sysconfig/<name>``.

        If the file exists its values are **replaced** entirely (not merged).
        Returns a status dict with the file path and list of keys written.
        """
        if not _is_valid_filename(name):
            raise SysconfigError(f"Invalid sysconfig name: {name!r}")

        target = self.sysconfig_dir / name
        self._ensure_dir(target.parent)

        header = f"UmerOS sysconfig — {name}"
        self._write_key_value(target, settings, header=header)

        return {
            "status": "success",
            "file": str(target),
            "keys_written": sorted(settings.keys()),
            "timestamp": _now_iso(),
        }

    def get_sysconfig_value(self, name: str, key: str) -> Optional[str]:
        """Return a single value from ``/etc/sysconfig/<name>`` or *None*."""
        try:
            cfg = self.get_sysconfig(name)
        except SysconfigFileNotFoundError:
            return None
        return cfg.get(key)

    def set_sysconfig_value(self, name: str, key: str, value: str) -> Dict[str, Any]:
        """Set a single key in ``/etc/sysconfig/<name>``.

        If the file does not exist it is created.  If it exists, existing keys
        that are *not* in the write are preserved (merge semantics).
        """
        if not _is_valid_filename(name):
            raise SysconfigError(f"Invalid sysconfig name: {name!r}")

        target = self.sysconfig_dir / name

        current: Dict[str, str] = {}
        if target.is_file():
            current = self._parse_key_value(target)

        current[key] = value
        self._ensure_dir(target.parent)

        header = f"UmerOS sysconfig — {name} (updated {key})"
        self._write_key_value(target, current, header=header)

        return {
            "status": "success",
            "file": str(target),
            "key": key,
            "value": value,
            "total_keys": len(current),
            "timestamp": _now_iso(),
        }

    def remove_sysconfig_value(self, name: str, key: str) -> Dict[str, Any]:
        """Remove a key from ``/etc/sysconfig/<name>``.

        Raises :class:`SysconfigFileNotFoundError` if the file is missing.
        Returns a status dict.
        """
        target = self.sysconfig_dir / name
        if not target.is_file():
            raise SysconfigFileNotFoundError(
                f"Sysconfig file not found: {target}"
            )

        current = self._parse_key_value(target)
        if key not in current:
            raise SysconfigError(
                f"Key {key!r} not found in {target}"
            )

        removed_val = current.pop(key)
        header = f"UmerOS sysconfig — {name} (removed {key})"
        self._write_key_value(target, current, header=header)

        return {
            "status": "success",
            "file": str(target),
            "key": key,
            "removed_value": removed_val,
            "remaining_keys": sorted(current.keys()),
            "timestamp": _now_iso(),
        }

    # ------------------------------------------------------------------
    # Generic default accessors
    # ------------------------------------------------------------------

    def list_defaults(self) -> Dict[str, Dict[str, str]]:
        """Return every file in /etc/default as ``{name: {k: v, ...}}``."""
        result: Dict[str, Dict[str, str]] = {}
        if not self.default_dir.is_dir():
            return result

        for item in sorted(self.default_dir.iterdir()):
            if item.is_file() and not item.is_symlink():
                result[item.name] = self._parse_key_value(item)

        return result

    def get_default(self, name: str) -> Dict[str, str]:
        """Return key/value pairs for ``/etc/default/<name>``.

        Raises :class:`SysconfigFileNotFoundError` if the file is missing.
        """
        if not _is_valid_filename(name):
            raise SysconfigError(f"Invalid default name: {name!r}")

        target = self.default_dir / name
        if not target.is_file():
            raise SysconfigFileNotFoundError(
                f"Default file not found: {target}"
            )
        return self._parse_key_value(target)

    def set_default(self, name: str, settings: Dict[str, str]) -> Dict[str, Any]:
        """Write *settings* to ``/etc/default/<name>`` (full replace).

        Returns a status dict.
        """
        if not _is_valid_filename(name):
            raise SysconfigError(f"Invalid default name: {name!r}")

        target = self.default_dir / name
        self._ensure_dir(target.parent)

        header = f"UmerOS default — {name}"
        self._write_key_value(target, settings, header=header)

        return {
            "status": "success",
            "file": str(target),
            "keys_written": sorted(settings.keys()),
            "timestamp": _now_iso(),
        }

    def get_default_value(self, name: str, key: str) -> Optional[str]:
        """Return a single value from ``/etc/default/<name>`` or *None*."""
        try:
            cfg = self.get_default(name)
        except SysconfigFileNotFoundError:
            return None
        return cfg.get(key)

    def set_default_value(self, name: str, key: str, value: str) -> Dict[str, Any]:
        """Set a single key in ``/etc/default/<name>`` (merge semantics)."""
        if not _is_valid_filename(name):
            raise SysconfigError(f"Invalid default name: {name!r}")

        target = self.default_dir / name

        current: Dict[str, str] = {}
        if target.is_file():
            current = self._parse_key_value(target)

        current[key] = value
        self._ensure_dir(target.parent)

        header = f"UmerOS default — {name} (updated {key})"
        self._write_key_value(target, current, header=header)

        return {
            "status": "success",
            "file": str(target),
            "key": key,
            "value": value,
            "total_keys": len(current),
            "timestamp": _now_iso(),
        }

    def remove_default_value(self, name: str, key: str) -> Dict[str, Any]:
        """Remove a key from ``/etc/default/<name>``."""
        target = self.default_dir / name
        if not target.is_file():
            raise SysconfigFileNotFoundError(
                f"Default file not found: {target}"
            )

        current = self._parse_key_value(target)
        if key not in current:
            raise SysconfigError(
                f"Key {key!r} not found in {target}"
            )

        removed_val = current.pop(key)
        header = f"UmerOS default — {name} (removed {key})"
        self._write_key_value(target, current, header=header)

        return {
            "status": "success",
            "file": str(target),
            "key": key,
            "removed_value": removed_val,
            "remaining_keys": sorted(current.keys()),
            "timestamp": _now_iso(),
        }

    # ------------------------------------------------------------------
    # Network scripts
    # ------------------------------------------------------------------

    def get_network_scripts(self) -> List[str]:
        """Return basenames of all files under /etc/sysconfig/network-scripts.

        Files are returned in sorted order.  Only regular files are listed;
        subdirectories and symlinks are excluded.
        """
        net_dir = Path(NETWORK_SCRIPTS)
        if not net_dir.is_dir():
            return []

        return sorted(
            entry.name
            for entry in net_dir.iterdir()
            if entry.is_file() and not entry.is_symlink()
        )

    def get_ifcfg(self, interface: str) -> Dict[str, str]:
        """Return parsed key/value pairs for ``ifcfg-<interface>``.

        Raises :class:`SysconfigFileNotFoundError` if the file does not exist.
        """
        if not _is_valid_filename(f"ifcfg-{interface}"):
            raise SysconfigError(f"Invalid interface name: {interface!r}")

        target = Path(NETWORK_SCRIPTS) / f"ifcfg-{interface}"
        if not target.is_file():
            raise SysconfigFileNotFoundError(
                f"Interface config not found: {target}"
            )
        return self._parse_key_value(target)

    def set_ifcfg(self, interface: str, settings: Dict[str, str]) -> Dict[str, Any]:
        """Write key/value pairs to ``ifcfg-<interface>``.

        If the file exists it is replaced entirely (not merged).
        Returns a status dict.
        """
        if not _is_valid_filename(f"ifcfg-{interface}"):
            raise SysconfigError(f"Invalid interface name: {interface!r}")

        target = Path(NETWORK_SCRIPTS) / f"ifcfg-{interface}"
        self._ensure_dir(target.parent)

        header = f"UmerOS network-scripts — ifcfg-{interface}"
        self._write_key_value(target, settings, header=header)

        return {
            "status": "success",
            "file": str(target),
            "interface": interface,
            "keys_written": sorted(settings.keys()),
            "timestamp": _now_iso(),
        }

    # ------------------------------------------------------------------
    # Convenience: specific well‑known files
    # ------------------------------------------------------------------

    def get_i18n(self) -> Dict[str, str]:
        """Return contents of /etc/sysconfig/i18n."""
        target = Path(I18N)
        if not target.is_file():
            return dict(_STANDARD_SYSCONFIG.get("i18n", {}))
        return self._parse_key_value(target)

    def set_i18n(self, settings: Dict[str, str]) -> Dict[str, Any]:
        """Write settings to /etc/sysconfig/i18n."""
        target = Path(I18N)
        self._ensure_dir(target.parent)

        header = "UmerOS sysconfig — i18n"
        self._write_key_value(target, settings, header=header)

        return {
            "status": "success",
            "file": str(target),
            "keys_written": sorted(settings.keys()),
            "timestamp": _now_iso(),
        }

    def get_keyboard(self) -> Dict[str, str]:
        """Return contents of /etc/sysconfig/keyboard."""
        target = Path(KEYBOARD)
        if not target.is_file():
            return dict(_STANDARD_SYSCONFIG.get("keyboard", {}))
        return self._parse_key_value(target)

    def set_keyboard(self, settings: Dict[str, str]) -> Dict[str, Any]:
        """Write settings to /etc/sysconfig/keyboard."""
        target = Path(KEYBOARD)
        self._ensure_dir(target.parent)

        header = "UmerOS sysconfig — keyboard"
        self._write_key_value(target, settings, header=header)

        return {
            "status": "success",
            "file": str(target),
            "keys_written": sorted(settings.keys()),
            "timestamp": _now_iso(),
        }

    def get_clock(self) -> Dict[str, str]:
        """Return contents of /etc/sysconfig/clock."""
        target = Path(CLOCK)
        if not target.is_file():
            return dict(_STANDARD_SYSCONFIG.get("clock", {}))
        return self._parse_key_value(target)

    def set_clock(self, settings: Dict[str, str]) -> Dict[str, Any]:
        """Write settings to /etc/sysconfig/clock."""
        target = Path(CLOCK)
        self._ensure_dir(target.parent)

        header = "UmerOS sysconfig — clock"
        self._write_key_value(target, settings, header=header)

        return {
            "status": "success",
            "file": str(target),
            "keys_written": sorted(settings.keys()),
            "timestamp": _now_iso(),
        }

    # ------------------------------------------------------------------
    # Cross‑source combined lookup
    # ------------------------------------------------------------------

    def get_service_config(self, service: str) -> Dict[str, str]:
        """Return a merged dict of sysconfig + default for *service*.

        If a key appears in both sources, the **sysconfig** value wins.
        Missing files are silently skipped.
        """
        merged: Dict[str, str] = {}

        # try /etc/default/<service>
        try:
            merged.update(self.get_default(service))
        except SysconfigFileNotFoundError:
            pass

        # try /etc/sysconfig/<service> — overrides default values
        try:
            merged.update(self.get_sysconfig(service))
        except SysconfigFileNotFoundError:
            pass

        return merged

    # ------------------------------------------------------------------
    # Standard templates
    # ------------------------------------------------------------------

    def get_standard_sysconfig(self) -> Dict[str, Dict[str, str]]:
        """Return a copy of the built‑in standard sysconfig templates.

        The dict maps filename → {key: default_value, ...}.  These are the
        defaults that ``UmerOS`` would ship with a fresh install.
        """
        import copy
        return copy.deepcopy(_STANDARD_SYSCONFIG)

    def get_standard_default(self) -> Dict[str, Dict[str, str]]:
        """Return a copy of the built‑in standard /etc/default templates."""
        import copy
        return copy.deepcopy(_STANDARD_DEFAULT)

    # ------------------------------------------------------------------
    # Status / reporting
    # ------------------------------------------------------------------

    def export_status(self) -> Dict[str, Any]:
        """Return a snapshot of every managed config file.

        The returned dict has three top‑level keys:
        - ``sysconfig`` — dict of sysconfig files
        - ``defaults`` — dict of default files
        - ``metadata`` — timestamp, directory paths, file counts
        """
        sc = self.list_sysconfig()
        dl = self.list_defaults()

        # collect files that exist for the well‑known paths
        well_known: Dict[str, Dict[str, str]] = {}
        for label, filepath in [
            ("i18n", I18N),
            ("keyboard", KEYBOARD),
            ("clock", CLOCK),
            ("locale", LANGUAGES),
        ]:
            p = Path(filepath)
            if p.is_file():
                well_known[label] = self._parse_key_value(p)

        return {
            "sysconfig": sc,
            "defaults": dl,
            "well_known": well_known,
            "metadata": {
                "timestamp": _now_iso(),
                "sysconfig_dir": str(self.sysconfig_dir),
                "default_dir": str(self.default_dir),
                "network_scripts": NETWORK_SCRIPTS,
                "sysconfig_file_count": len(sc),
                "defaults_file_count": len(dl),
                "well_known_file_count": len(well_known),
            },
        }

    # ------------------------------------------------------------------
    # Backup / restore helpers
    # ------------------------------------------------------------------

    def backup_all(self, backup_path: str) -> Dict[str, Any]:
        """Copy every managed file into *backup_path*.

        Layout inside *backup_path*::

            backup_path/
                sysconfig/          ← copies of /etc/sysconfig/*
                default/            ← copies of /etc/default/*
                network_scripts/    ← copies of /etc/sysconfig/network-scripts/*

        Returns a status dict listing all backed‑up files and any errors.
        """
        backup_root = Path(backup_path)
        self._ensure_dir(backup_root)

        sc_dest = backup_root / "sysconfig"
        dl_dest = backup_root / "default"
        ns_dest = backup_root / "network_scripts"
        self._ensure_dir(sc_dest)
        self._ensure_dir(dl_dest)
        self._ensure_dir(ns_dest)

        backed_up: List[str] = []
        errors: List[str] = []

        # 1. /etc/sysconfig/*
        if self.sysconfig_dir.is_dir():
            for item in self.sysconfig_dir.iterdir():
                if item.is_file() and not item.is_symlink():
                    try:
                        result = _backup_item(item, sc_dest)
                        if result:
                            backed_up.append(result)
                    except SysconfigWriteError as exc:
                        errors.append(str(exc))

        # 2. /etc/default/*
        if self.default_dir.is_dir():
            for item in self.default_dir.iterdir():
                if item.is_file() and not item.is_symlink():
                    try:
                        result = _backup_item(item, dl_dest)
                        if result:
                            backed_up.append(result)
                    except SysconfigWriteError as exc:
                        errors.append(str(exc))

        # 3. /etc/sysconfig/network-scripts/*
        net_dir = Path(NETWORK_SCRIPTS)
        if net_dir.is_dir():
            for item in net_dir.iterdir():
                if item.is_file() and not item.is_symlink():
                    try:
                        result = _backup_item(item, ns_dest)
                        if result:
                            backed_up.append(result)
                    except SysconfigWriteError as exc:
                        errors.append(str(exc))

        return {
            "status": "success" if not errors else "partial",
            "backup_path": str(backup_root),
            "files_backed_up": len(backed_up),
            "backed_up_files": sorted(backed_up),
            "errors": errors,
            "timestamp": _now_iso(),
        }

    # ------------------------------------------------------------------
    # Restore helpers
    # ------------------------------------------------------------------

    def restore_from_backup(self, backup_path: str) -> Dict[str, Any]:
        """Restore files from a backup created by :meth:`backup_all`.

        Expects the same directory layout that ``backup_all`` produces.
        Only files that are present in the backup are overwritten; existing
        files that are *not* in the backup are left untouched.

        Returns a status dict.
        """
        backup_root = Path(backup_path)
        if not backup_root.is_dir():
            raise SysconfigError(
                f"Backup path does not exist: {backup_root}"
            )

        restored: List[str] = []
        errors: List[str] = []

        mapping: List[Tuple[Path, Path]] = [
            (backup_root / "sysconfig", self.sysconfig_dir),
            (backup_root / "default", self.default_dir),
            (backup_root / "network_scripts", Path(NETWORK_SCRIPTS)),
        ]

        for src_dir, dst_dir in mapping:
            if not src_dir.is_dir():
                continue
            self._ensure_dir(dst_dir)

            for item in src_dir.iterdir():
                if item.is_file():
                    dst = dst_dir / item.name
                    try:
                        shutil.copy2(str(item), str(dst))
                        restored.append(str(dst))
                    except OSError as exc:
                        errors.append(f"{item} → {dst}: {exc}")

        return {
            "status": "success" if not errors else "partial",
            "files_restored": len(restored),
            "restored_files": sorted(restored),
            "errors": errors,
            "timestamp": _now_iso(),
        }

    # ------------------------------------------------------------------
    # Diff / comparison
    # ------------------------------------------------------------------

    def diff_with_standard(self) -> Dict[str, Dict[str, Any]]:
        """Compare the current live files against the standard templates.

        Returns a dict keyed by filename.  Each entry contains:
        - ``current`` — live values (or None if missing)
        - ``standard`` — template values
        - ``missing`` — keys present in template but absent in live
        - ``extra`` — keys present in live but absent in template
        """
        sc_template = self.get_standard_sysconfig()
        dl_template = self.get_standard_default()
        live_sc = self.list_sysconfig()
        live_dl = self.list_defaults()

        diff_result: Dict[str, Dict[str, Any]] = {}

        all_names = set(sc_template.keys()) | set(live_sc.keys())
        for name in sorted(all_names):
            live = live_sc.get(name, {})
            tmpl = sc_template.get(name, {})
            missing = [k for k in tmpl if k not in live]
            extra = [k for k in live if k not in tmpl]
            diff_result[f"sysconfig/{name}"] = {
                "current": live or None,
                "standard": tmpl,
                "missing_keys": missing,
                "extra_keys": extra,
                "match": not missing and not extra and live == tmpl,
            }

        all_names = set(dl_template.keys()) | set(live_dl.keys())
        for name in sorted(all_names):
            live = live_dl.get(name, {})
            tmpl = dl_template.get(name, {})
            missing = [k for k in tmpl if k not in live]
            extra = [k for k in live if k not in tmpl]
            diff_result[f"default/{name}"] = {
                "current": live or None,
                "standard": tmpl,
                "missing_keys": missing,
                "extra_keys": extra,
                "match": not missing and not extra and live == tmpl,
            }

        return diff_result

    # ------------------------------------------------------------------
    # Apply standard templates (create missing files)
    # ------------------------------------------------------------------

    def apply_standard_sysconfig(self) -> Dict[str, Any]:
        """Create any missing standard sysconfig files from templates.

        Existing files are **not** modified.  Returns a status dict listing
        which files were created and which were skipped.
        """
        created: List[str] = []
        skipped: List[str] = []

        for name, defaults in _STANDARD_SYSCONFIG.items():
            if name == "network-scripts":
                continue  # not a config file
            target = self.sysconfig_dir / name
            if target.is_file():
                skipped.append(name)
                continue
            self._ensure_dir(target.parent)
            header = f"UmerOS standard sysconfig — {name}"
            self._write_key_value(target, defaults, header=header)
            created.append(name)

        return {
            "status": "success",
            "created": created,
            "skipped": skipped,
            "timestamp": _now_iso(),
        }

    def apply_standard_default(self) -> Dict[str, Any]:
        """Create any missing standard default files from templates.

        Existing files are **not** modified.
        """
        created: List[str] = []
        skipped: List[str] = []

        for name, defaults in _STANDARD_DEFAULT.items():
            target = self.default_dir / name
            if target.is_file():
                skipped.append(name)
                continue
            self._ensure_dir(target.parent)
            header = f"UmerOS standard default — {name}"
            self._write_key_value(target, defaults, header=header)
            created.append(name)

        return {
            "status": "success",
            "created": created,
            "skipped": skipped,
            "timestamp": _now_iso(),
        }

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def validate_sysconfig(self, name: str) -> Dict[str, Any]:
        """Validate ``/etc/sysconfig/<name>`` for common issues.

        Checks performed:
        - File exists
        - All values are non‑empty strings (warns on empty)
        - No duplicate keys (last‑write‑wins means earlier values silently lost)
        - Key names conform to ``[A-Za-z_][A-Za-z0-9_]*``

        Returns a dict with ``valid`` (bool), ``warnings`` (list), and
        ``errors`` (list).
        """
        warnings: List[str] = []
        errors: List[str] = []
        target = self.sysconfig_dir / name

        if not target.is_file():
            errors.append(f"File not found: {target}")
            return {"valid": False, "warnings": warnings, "errors": errors}

        # raw parse to check for issues
        text = target.read_text(encoding="utf-8", errors="replace")
        seen_keys: Dict[str, int] = {}
        for lineno, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            m_export = re.match(r"^export\s+", line)
            if m_export:
                line = line[m_export.end():]

            m_kv = re.match(r"^(?P<key>[A-Za-z_]\w*)\s*=\s*(?P<val>.*)", line)
            if not m_kv:
                warnings.append(f"Line {lineno}: not a valid KEY=VALUE line")
                continue

            key = m_kv.group("key")
            val = m_kv.group("val").strip()

            # check for duplicate
            seen_keys[key] = seen_keys.get(key, 0) + 1

            # check empty value
            if not val:
                warnings.append(
                    f"Line {lineno}: key {key!r} has an empty value"
                )

        # report duplicates
        for key, count in seen_keys.items():
            if count > 1:
                warnings.append(
                    f"Key {key!r} appears {count} times (last value wins)"
                )

        return {
            "valid": len(errors) == 0,
            "warnings": warnings,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # repr / str
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"SysconfigManager(sysconfig_dir={self.sysconfig_dir!r}, "
            f"default_dir={self.default_dir!r})"
        )

    def __str__(self) -> str:
        sc_count = len(self.list_sysconfig())
        dl_count = len(self.list_defaults())
        return (
            f"SysconfigManager: {sc_count} sysconfig files, "
            f"{dl_count} default files"
        )


# ---------------------------------------------------------------------------
# Module‑level convenience functions (standalone usage)
# ---------------------------------------------------------------------------

_default_manager: Optional[SysconfigManager] = None


def _get_default_manager() -> SysconfigManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = SysconfigManager()
    return _default_manager


def list_sysconfig() -> Dict[str, Dict[str, str]]:
    """Shortcut — see :meth:`SysconfigManager.list_sysconfig`."""
    return _get_default_manager().list_sysconfig()


def list_defaults() -> Dict[str, Dict[str, str]]:
    """Shortcut — see :meth:`SysconfigManager.list_defaults`."""
    return _get_default_manager().list_defaults()


def get_sysconfig(name: str) -> Dict[str, str]:
    """Shortcut — see :meth:`SysconfigManager.get_sysconfig`."""
    return _get_default_manager().get_sysconfig(name)


def set_sysconfig(name: str, settings: Dict[str, str]) -> Dict[str, Any]:
    """Shortcut — see :meth:`SysconfigManager.set_sysconfig`."""
    return _get_default_manager().set_sysconfig(name, settings)


def get_sysconfig_value(name: str, key: str) -> Optional[str]:
    """Shortcut — see :meth:`SysconfigManager.get_sysconfig_value`."""
    return _get_default_manager().get_sysconfig_value(name, key)


def set_sysconfig_value(name: str, key: str, value: str) -> Dict[str, Any]:
    """Shortcut — see :meth:`SysconfigManager.set_sysconfig_value`."""
    return _get_default_manager().set_sysconfig_value(name, key, value)


def remove_sysconfig_value(name: str, key: str) -> Dict[str, Any]:
    """Shortcut — see :meth:`SysconfigManager.remove_sysconfig_value`."""
    return _get_default_manager().remove_sysconfig_value(name, key)


def get_default(name: str) -> Dict[str, str]:
    """Shortcut — see :meth:`SysconfigManager.get_default`."""
    return _get_default_manager().get_default(name)


def set_default(name: str, settings: Dict[str, str]) -> Dict[str, Any]:
    """Shortcut — see :meth:`SysconfigManager.set_default`."""
    return _get_default_manager().set_default(name, settings)


def get_default_value(name: str, key: str) -> Optional[str]:
    """Shortcut — see :meth:`SysconfigManager.get_default_value`."""
    return _get_default_manager().get_default_value(name, key)


def set_default_value(name: str, key: str, value: str) -> Dict[str, Any]:
    """Shortcut — see :meth:`SysconfigManager.set_default_value`."""
    return _get_default_manager().set_default_value(name, key, value)


def remove_default_value(name: str, key: str) -> Dict[str, Any]:
    """Shortcut — see :meth:`SysconfigManager.remove_default_value`."""
    return _get_default_manager().remove_default_value(name, key)


def get_network_scripts() -> List[str]:
    """Shortcut — see :meth:`SysconfigManager.get_network_scripts`."""
    return _get_default_manager().get_network_scripts()


def get_ifcfg(interface: str) -> Dict[str, str]:
    """Shortcut — see :meth:`SysconfigManager.get_ifcfg`."""
    return _get_default_manager().get_ifcfg(interface)


def set_ifcfg(interface: str, settings: Dict[str, str]) -> Dict[str, Any]:
    """Shortcut — see :meth:`SysconfigManager.set_ifcfg`."""
    return _get_default_manager().set_ifcfg(interface, settings)


def get_i18n() -> Dict[str, str]:
    """Shortcut — see :meth:`SysconfigManager.get_i18n`."""
    return _get_default_manager().get_i18n()


def set_i18n(settings: Dict[str, str]) -> Dict[str, Any]:
    """Shortcut — see :meth:`SysconfigManager.set_i18n`."""
    return _get_default_manager().set_i18n(settings)


def get_keyboard() -> Dict[str, str]:
    """Shortcut — see :meth:`SysconfigManager.get_keyboard`."""
    return _get_default_manager().get_keyboard()


def set_keyboard(settings: Dict[str, str]) -> Dict[str, Any]:
    """Shortcut — see :meth:`SysconfigManager.set_keyboard`."""
    return _get_default_manager().set_keyboard(settings)


def get_clock() -> Dict[str, str]:
    """Shortcut — see :meth:`SysconfigManager.get_clock`."""
    return _get_default_manager().get_clock()


def set_clock(settings: Dict[str, str]) -> Dict[str, Any]:
    """Shortcut — see :meth:`SysconfigManager.set_clock`."""
    return _get_default_manager().set_clock(settings)


def get_service_config(service: str) -> Dict[str, str]:
    """Shortcut — see :meth:`SysconfigManager.get_service_config`."""
    return _get_default_manager().get_service_config(service)


def export_status() -> Dict[str, Any]:
    """Shortcut — see :meth:`SysconfigManager.export_status`."""
    return _get_default_manager().export_status()


def backup_all(backup_path: str) -> Dict[str, Any]:
    """Shortcut — see :meth:`SysconfigManager.backup_all`."""
    return _get_default_manager().backup_all(backup_path)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Minimal CLI for quick sysconfig / default inspection."""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="UmerOS /etc/sysconfig & /etc/default manager",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    sub.add_parser("list", help="List all sysconfig and default files")
    sub.add_parser("i18n", help="Show i18n config")
    sub.add_parser("keyboard", help="Show keyboard config")
    sub.add_parser("clock", help="Show clock config")
    sub.add_parser("locale", help="Show locale config")
    sub.add_parser("status", help="Full status report")
    sub.add_parser("validate", help="Validate all sysconfig files")
    sub.add_parser("diff", help="Diff against standard templates")
    sub.add_parser("apply-templates", help="Create missing standard files")

    p_show = sub.add_parser("show", help="Show a specific config file")
    p_show.add_argument("name", help="File basename (e.g. sshd)")
    p_show.add_argument(
        "--src", choices=["sysconfig", "default"], default="sysconfig",
        help="Source directory",
    )

    p_val = sub.add_parser("validate-one", help="Validate a single sysconfig file")
    p_val.add_argument("name", help="File basename")

    p_backup = sub.add_parser("backup", help="Backup all config files")
    p_backup.add_argument("path", help="Destination directory")

    args = parser.parse_args()

    mgr = SysconfigManager()

    if args.command is None:
        parser.print_help()
        return

    if args.command == "list":
        print("=== /etc/sysconfig ===")
        for name, kv in mgr.list_sysconfig().items():
            print(f"  {name}: {len(kv)} keys")
        print(f"\n=== /etc/default ===")
        for name, kv in mgr.list_defaults().items():
            print(f"  {name}: {len(kv)} keys")

    elif args.command == "i18n":
        print(json.dumps(mgr.get_i18n(), indent=2))

    elif args.command == "keyboard":
        print(json.dumps(mgr.get_keyboard(), indent=2))

    elif args.command == "clock":
        print(json.dumps(mgr.get_clock(), indent=2))

    elif args.command == "locale":
        try:
            print(json.dumps(mgr.get_default("locale"), indent=2))
        except SysconfigFileNotFoundError:
            print("File /etc/default/locale not found")

    elif args.command == "status":
        status = mgr.export_status()
        print(json.dumps(status, indent=2))

    elif args.command == "validate":
        for name in mgr.list_sysconfig():
            result = mgr.validate_sysconfig(name)
            flag = "OK" if result["valid"] else "FAIL"
            print(f"  [{flag}] {name}: "
                  f"{len(result['warnings'])} warnings, "
                  f"{len(result['errors'])} errors")

    elif args.command == "validate-one":
        result = mgr.validate_sysconfig(args.name)
        print(json.dumps(result, indent=2))

    elif args.command == "diff":
        diff = mgr.diff_with_standard()
        for path, info in diff.items():
            match_flag = "MATCH" if info["match"] else "DIFF"
            print(f"  [{match_flag}] {path}")
            if info["missing_keys"]:
                print(f"    missing: {info['missing_keys']}")
            if info["extra_keys"]:
                print(f"    extra:   {info['extra_keys']}")

    elif args.command == "apply-templates":
        r1 = mgr.apply_standard_sysconfig()
        r2 = mgr.apply_standard_default()
        print("Sysconfig:", json.dumps(r1, indent=2))
        print("Default:", json.dumps(r2, indent=2))

    elif args.command == "show":
        try:
            if args.src == "sysconfig":
                kv = mgr.get_sysconfig(args.name)
            else:
                kv = mgr.get_default(args.name)
            print(json.dumps(kv, indent=2))
        except SysconfigFileNotFoundError as exc:
            print(f"Error: {exc}")
            raise SystemExit(1) from exc

    elif args.command == "backup":
        result = mgr.backup_all(args.path)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
