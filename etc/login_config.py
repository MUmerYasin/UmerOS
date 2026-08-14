"""
UmerOS Login/Security Configuration Manager

Manages login.defs, securetty, nologin, lastlog, and login-related configs
for the UmerOS distribution.

Author: UmerOS Development Team
License: GPL-3.0
"""

import os
import shutil
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

# ---------------------------------------------------------------------------
# Path Constants
# ---------------------------------------------------------------------------

LOGIN_DEFS = "/etc/login.defs"
SECURETTY = "/etc/securetty"
NOLOGIN = "/etc/nologin"
LASTLOG = "/var/log/lastlog"
FAILLOG = "/etc/security/faillog"
LOGIN_DEFS_BAK = "/etc/login.defs.old"

# ---------------------------------------------------------------------------
# Default login.defs values 
# ---------------------------------------------------------------------------

LOGIN_DEFS_DEFAULTS: Dict[str, str] = {
    # Password ageing controls
    "PASS_MAX_DAYS": "99999",
    "PASS_MIN_DAYS": "0",
    "PASS_MIN_LEN": "5",
    "PASS_WARN_AGE": "7",
    # UID/GID ranges for regular users
    "UID_MIN": "1000",
    "UID_MAX": "60000",
    "GID_MIN": "1000",
    "GID_MAX": "60000",
    # Home directory creation
    "CREATE_HOME": "yes",
    "DEFAULT_HOME": "no",
    "UMASK": "022",
    # Encryption method
    "ENCRYPT_METHOD": "SHA512",
    "SHA_CRYPT_MIN_ROUNDS": "5000",
    "SHA_CRYPT_MAX_ROUNDS": "5000",
    # Login behaviour
    "LOGIN_RETRIES": "3",
    "LOGIN_TIMEOUT": "60",
    "LOGIN_STRING": "",
    "NOLOGINS_FILE": "/etc/nologin",
    # TTY permissions
    "TTYPERM": "0620",
    "TTYGROUP": "tty",
    # Terminal size
    "TTYTYPE_FILE": "/etc/ttytype",
    # Environment
    "ENV_SUPATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "ENV_PATH": "/usr/local/bin:/usr/bin:/bin",
    "ENV_HZ": "Hertz",
    "ENVIRON_FILE": "/etc/environment",
    # Kerberos (disabled by default)
    "ENV_KRB5CCNAME": "",
    "ENV_TICKET_VARIABLE": "KRB5CCNAME",
    # Su behaviour
    "SU_NAME": "su",
    "SU_WHEEL_ONLY": "no",
    # Utmp/wtmp
    "ENABLE_LASTLOG": "yes",
    "ENABLE_TMPLOG": "yes",
    "LASTLOG_UID_MAX": "60000",
    "LASTLOG_NOLOGINS_MAX": "",
    # Misc
    "HUSHLOGIN_FILE": ".hushlogin",
    "LOG_OK_LOGINS": "yes",
    "LOG_UNKFAIL_ENAB": "no",
    "SYSLOG_SU_ENAB": "yes",
    "SYSLOG_SG_ENAB": "yes",
    "SULOG_FILE": "/var/log/sulog",
    "CONSOLE": "",
    "CONSOLES": "",
    "BFAILDELAY": "10",
    "FAIL_DELAY": "1",
    "CLOSE_SESSIONS": "yes",
    "ONLY_ROOT_ALL_SHELLS": "no",
    "USERDEL_CMD": "",
    "USERGROUPS_ENAB": "no",
    "MD5_CRYPT_ENAB": "no",
    "MD5_CRYPT_ENABLE": "no",
    "CRYPT_MD5_ENABLE": "no",
    "DES_CRYPT_ENAB": "no",
}

# Insecure values for validation
INSECURE_SETTINGS: Dict[str, List[str]] = {
    "PASS_MAX_DAYS": ["99999", "0"],
    "PASS_MIN_DAYS": ["0"],
    "PASS_MIN_LEN": ["5", "4", "3", "2", "1", "0"],
    "UID_MIN": ["0", "1"],
    "GID_MIN": ["0", "1"],
    "ENCRYPT_METHOD": ["DES", "MD5"],
    "CREATE_HOME": ["no"],
    "UMASK": ["000", "002", "022", "027"],
    "PASS_WARN_AGE": ["0"],
    "LOGIN_RETRIES": ["0"],
    "LOGIN_TIMEOUT": ["0"],
}

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LoginConfigError(Exception):
    """Raised when a login configuration operation fails."""


class RootRequiredError(LoginConfigError):
    """Raised when the operation requires root privileges."""


class ConfigParseError(LoginConfigError):
    """Raised when a configuration file cannot be parsed."""


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _ensure_root() -> None:
    """Verify the current process is running as root."""
    if os.geteuid() != 0:
        raise RootRequiredError(
            "This operation requires root privileges. Re-run with sudo."
        )


def _backup_file(path: str) -> Optional[str]:
    """Create a timestamped backup of *path* and return the backup path."""
    if not os.path.isfile(path):
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{path}.{ts}.bak"
    shutil.copy2(path, backup)
    return backup


def _write_file(path: str, content: str, mode: int = 0o644) -> None:
    """Atomically write *content* to *path* (write-then-rename)."""
    tmp = f"{path}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except OSError:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _read_lines(path: str) -> List[str]:
    """Return the lines of *path* as a list, or an empty list when missing."""
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return fh.readlines()


def _write_lines(path: str, lines: List[str]) -> None:
    """Write *lines* (with trailing newlines) to *path*."""
    content = "".join(lines)
    if not content.endswith("\n"):
        content += "\n"
    _write_file(path, content, mode=0o644)


# ---------------------------------------------------------------------------
# Core Manager
# ---------------------------------------------------------------------------


class LoginConfigManager:
    """
    Centralised manager for UmerOS login / security configuration files.

    Parameters
    ----------
    login_defs : str
        Path to ``login.defs`` (default ``/etc/login.defs``).
    securetty : str
        Path to ``securetty`` (default ``/etc/securetty``).
    nologin : str
        Path to ``nologin`` (default ``/etc/nologin``).
    """

    def __init__(
        self,
        login_defs: str = LOGIN_DEFS,
        securetty: str = SECURETTY,
        nologin: str = NOLOGIN,
    ) -> None:
        self.login_defs_path = login_defs
        self.securetty_path = securetty
        self.nologin_path = nologin
        self._defs_cache: Optional[Dict[str, str]] = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_login_defs(self) -> Dict[str, str]:
        """
        Parse the ``login.defs`` file and return a dict of key -> value.

        Lines starting with ``#`` and blank lines are ignored.
        Values may be quoted or unquoted; surrounding quotes are stripped.
        """
        settings: Dict[str, str] = {}
        if not os.path.isfile(self.login_defs_path):
            return dict(LOGIN_DEFS_DEFAULTS)
        try:
            for raw_line in _read_lines(self.login_defs_path):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(None, 1)
                if len(parts) < 2:
                    continue
                key, value = parts
                value = value.strip()
                # Strip surrounding quotes
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                settings[key] = value
        except OSError as exc:
            raise ConfigParseError(
                f"Failed to read {self.login_defs_path}: {exc}"
            )
        self._defs_cache = settings
        return settings

    def _write_login_defs(self, settings: Dict[str, str]) -> None:
        """
        Overwrite ``login.defs`` with the provided *settings* dict.

        Preserves comments that do not correspond to a known key.
        """
        _ensure_root()
        original_lines: List[str] = []
        if os.path.isfile(self.login_defs_path):
            original_lines = _read_lines(self.login_defs_path)

        output: List[str] = []
        written_keys: set = set()

        for raw_line in original_lines:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                output.append(raw_line)
                continue
            parts = line.split(None, 1)
            if len(parts) < 2:
                output.append(raw_line)
                continue
            key = parts[0]
            if key in settings:
                output.append(f"{key}\t\t{settings[key]}\n")
                written_keys.add(key)
            else:
                output.append(raw_line)

        for key in sorted(settings):
            if key not in written_keys:
                output.append(f"{key}\t\t{settings[key]}\n")

        _backup_file(self.login_defs_path)
        _write_file(self.login_defs_path, "".join(output), mode=0o644)
        self._defs_cache = dict(settings)

    # ------------------------------------------------------------------
    # login.defs accessors
    # ------------------------------------------------------------------

    def get_login_defs(self) -> Dict[str, str]:
        """
        Return **all** settings from ``login.defs`` merged with defaults.

        Returns
        -------
        dict[str, str]
            Key -> value mapping of every ``login.defs`` setting.
        """
        defs = dict(LOGIN_DEFS_DEFAULTS)
        if os.path.isfile(self.login_defs_path):
            defs.update(self._parse_login_defs())
        return defs

    def set_login_defs(self, settings: Dict[str, str]) -> Dict[str, Any]:
        """
        Apply multiple *settings* to ``login.defs`` at once.

        Parameters
        ----------
        settings : dict[str, str]
            Key -> value pairs to set.

        Returns
        -------
        dict
            ``{"success": True, "changed": [list of changed keys]}``.
        """
        current = self.get_login_defs()
        changed = [k for k, v in settings.items() if current.get(k) != v]
        merged = {**current, **settings}
        self._write_login_defs(merged)
        return {"success": True, "changed": changed}

    def get_login_def(self, key: str) -> Optional[str]:
        """
        Return a single ``login.defs`` value, or ``None`` if absent.

        Parameters
        ----------
        key : str
            The setting name (e.g. ``PASS_MAX_DAYS``).

        Returns
        -------
        str or None
        """
        defs = self.get_login_defs()
        return defs.get(key)

    def set_login_def(self, key: str, value: str) -> Dict[str, Any]:
        """
        Set a single ``login.defs`` key to *value*.

        Returns
        -------
        dict
            ``{"success": True, "key": ..., "old": ..., "new": ...}``.
        """
        old = self.get_login_def(key)
        defs = self.get_login_defs()
        defs[key] = value
        self._write_login_defs(defs)
        return {"success": True, "key": key, "old": old, "new": value}

    # ------------------------------------------------------------------
    # securetty management
    # ------------------------------------------------------------------

    def get_securetty(self) -> List[str]:
        """
        Return the list of TTYs allowed for root login.

        Returns
        -------
        list[str]
            Sorted, deduplicated list of TTY names.
        """
        if not os.path.isfile(self.securetty_path):
            return []
        ttys: set = set()
        for raw in _read_lines(self.securetty_path):
            tty = raw.strip()
            if tty and not tty.startswith("#"):
                ttys.add(tty)
        return sorted(ttys)

    def set_securetty(self, tty_list: List[str]) -> Dict[str, Any]:
        """
        Replace ``securetty`` with *tty_list*.

        Returns
        -------
        dict
            ``{"success": True, "ttys": [...]}``.
        """
        _ensure_root()
        sorted_ttys = sorted(set(tty for tty in tty_list if tty))
        content = (
            "# /etc/securetty\n"
            "# List of TTYs allowed for root login\n"
            "# Generated by UmerOS LoginConfigManager\n\n"
        )
        content += "\n".join(sorted_ttys) + "\n"
        _backup_file(self.securetty_path)
        _write_file(self.securetty_path, content, mode=0o620)
        return {"success": True, "ttys": sorted_ttys}

    def add_securetty(self, tty: str) -> Dict[str, Any]:
        """
        Add *tty* to ``securetty`` if not already present.

        Returns
        -------
        dict
            ``{"success": True, "added": str, "ttys": [...]}``.
        """
        current = set(self.get_securetty())
        if tty in current:
            return {
                "success": True,
                "added": tty,
                "ttys": sorted(current),
                "message": f"{tty} already present",
            }
        current.add(tty)
        result = self.set_securetty(sorted(current))
        result["added"] = tty
        return result

    def remove_securetty(self, tty: str) -> Dict[str, Any]:
        """
        Remove *tty* from ``securetty``.

        Returns
        -------
        dict
            ``{"success": True, "removed": str, "ttys": [...]}``.
        """
        current = set(self.get_securetty())
        if tty not in current:
            return {
                "success": True,
                "removed": tty,
                "ttys": sorted(current),
                "message": f"{tty} not present",
            }
        current.discard(tty)
        result = self.set_securetty(sorted(current))
        result["removed"] = tty
        return result

    def allow_root_login(self, tty: Optional[str] = None) -> Dict[str, Any]:
        """
        Allow root to log in via *tty* (or all currently listed TTYs).

        When *tty* is ``None`` every TTY in ``/etc/securetty`` is retained
        so root login is broadly permitted.

        Returns
        -------
        dict
            ``{"success": True, ...}``.
        """
        if tty is not None:
            return self.add_securetty(tty)
        current = self.get_securetty()
        if not current:
            common = [
                "tty1", "tty2", "tty3", "tty4", "tty5", "tty6", "console"
            ]
            return self.set_securetty(common)
        return {
            "success": True,
            "ttys": current,
            "message": "Root login already allowed",
        }

    def disallow_root_login(self) -> Dict[str, Any]:
        """
        Deny all direct root logins by writing an empty ``securetty``.

        Returns
        -------
        dict
            ``{"success": True, "ttys": []}``.
        """
        return self.set_securetty([])

    # ------------------------------------------------------------------
    # nologin management
    # ------------------------------------------------------------------

    def get_nologin_message(self) -> str:
        """
        Return the content of the ``/etc/nologin`` message file.

        Returns
        -------
        str
            The message shown to users when nologin is active, or ``""``
            if the file does not exist.
        """
        if not os.path.isfile(self.nologin_path):
            return ""
        with open(self.nologin_path, "r", encoding="utf-8") as fh:
            return fh.read().strip()

    def set_nologin_message(self, message: str) -> Dict[str, Any]:
        """
        Write *message* to ``/etc/nologin`` and activate nologin.

        Returns
        -------
        dict
            ``{"success": True, "message": str}``.
        """
        _ensure_root()
        if os.path.isfile(self.nologin_path):
            _backup_file(self.nologin_path)
        _write_file(self.nologin_path, message + "\n", mode=0o644)
        return {"success": True, "message": message}

    def remove_nologin(self) -> Dict[str, Any]:
        """
        Remove ``/etc/nologin`` to re-enable logins.

        Returns
        -------
        dict
            ``{"success": True}``.
        """
        _ensure_root()
        if os.path.isfile(self.nologin_path):
            _backup_file(self.nologin_path)
            os.remove(self.nologin_path)
        return {"success": True, "message": "Nologin removed"}

    def is_nologin_active(self) -> bool:
        """
        Check whether the nologin file exists (i.e. logins are blocked).

        Returns
        -------
        bool
        """
        return os.path.isfile(self.nologin_path)

    # ------------------------------------------------------------------
    # Range / umask / encryption helpers
    # ------------------------------------------------------------------

    def get_uid_range(self) -> Dict[str, int]:
        """
        Return the UID range for regular users.

        Returns
        -------
        dict
            ``{"uid_min": int, "uid_max": int}``.
        """
        defs = self.get_login_defs()
        return {
            "uid_min": int(defs.get("UID_MIN", 1000)),
            "uid_max": int(defs.get("UID_MAX", 60000)),
        }

    def get_gid_range(self) -> Dict[str, int]:
        """
        Return the GID range for regular groups.

        Returns
        -------
        dict
            ``{"gid_min": int, "gid_max": int}``.
        """
        defs = self.get_login_defs()
        return {
            "gid_min": int(defs.get("GID_MIN", 1000)),
            "gid_max": int(defs.get("GID_MAX", 60000)),
        }

    def get_umask(self) -> str:
        """
        Return the default UMASK value from ``login.defs``.

        Returns
        -------
        str
        """
        return self.get_login_def("UMASK") or "022"

    def set_umask(self, umask: str) -> Dict[str, Any]:
        """
        Set the UMASK value in ``login.defs``.

        Parameters
        ----------
        umask : str
            Octal umask string (e.g. ``"022"``).

        Returns
        -------
        dict
            ``{"success": True, "old": ..., "new": ...}``.
        """
        return self.set_login_def("UMASK", umask.strip())

    def get_encrypt_method(self) -> str:
        """
        Return the current ``ENCRYPT_METHOD`` from ``login.defs``.

        Returns
        -------
        str
        """
        return self.get_login_def("ENCRYPT_METHOD") or "SHA512"

    def set_encrypt_method(self, method: str) -> Dict[str, Any]:
        """
        Set the ``ENCRYPT_METHOD`` in ``login.defs``.

        Parameters
        ----------
        method : str
            One of ``SHA512``, ``SHA256``, ``MD5``, ``DES``, ``BCRYPT``.

        Returns
        -------
        dict
        """
        valid = {"SHA512", "SHA256", "MD5", "DES", "BCRYPT"}
        if method.upper() not in valid:
            raise LoginConfigError(
                f"Invalid method '{method}'. Valid: {', '.join(sorted(valid))}"
            )
        return self.set_login_def("ENCRYPT_METHOD", method.upper())

    # ------------------------------------------------------------------
    # Grouped config helpers
    # ------------------------------------------------------------------

    def get_home_config(self) -> Dict[str, str]:
        """
        Return home-directory related settings.

        Returns
        -------
        dict
            Keys: ``CREATE_HOME``, ``UMASK``, ``DEFAULT_HOME``.
        """
        defs = self.get_login_defs()
        return {
            "CREATE_HOME": defs.get("CREATE_HOME", "yes"),
            "UMASK": defs.get("UMASK", "022"),
            "DEFAULT_HOME": defs.get("DEFAULT_HOME", "no"),
        }

    def get_env_config(self) -> Dict[str, str]:
        """
        Return environment-variable settings from ``login.defs``.

        Returns
        -------
        dict
            Keys: ``ENV_SUPATH``, ``ENV_PATH``, ``ENV_HZ``,
            ``ENVIRON_FILE``, ``ENV_KRB5CCNAME``.
        """
        defs = self.get_login_defs()
        return {
            "ENV_SUPATH": defs.get(
                "ENV_SUPATH",
                "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            ),
            "ENV_PATH": defs.get(
                "ENV_PATH", "/usr/local/bin:/usr/bin:/bin"
            ),
            "ENV_HZ": defs.get("ENV_HZ", "Hertz"),
            "ENVIRON_FILE": defs.get("ENVIRON_FILE", "/etc/environment"),
            "ENV_KRB5CCNAME": defs.get("ENV_KRB5CCNAME", ""),
        }

    def get_timeout_config(self) -> Dict[str, Union[str, int]]:
        """
        Return timeout / retry / TTY-permission settings.

        Returns
        -------
        dict
            Keys: ``LOGIN_TIMEOUT``, ``LOGIN_RETRIES``, ``TTYPERM``.
        """
        defs = self.get_login_defs()
        return {
            "LOGIN_TIMEOUT": int(defs.get("LOGIN_TIMEOUT", 60)),
            "LOGIN_RETRIES": int(defs.get("LOGIN_RETRIES", 3)),
            "TTYPERM": defs.get("TTYPERM", "0620"),
        }

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_config(self) -> Dict[str, Any]:
        """
        Audit the current configuration for known-insecure settings.

        Returns
        -------
        dict
            ``{"valid": bool, "warnings": [...], "details": {...}}``.
        """
        defs = self.get_login_defs()
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        for key, bad_values in INSECURE_SETTINGS.items():
            current = defs.get(key, "")
            if current in bad_values:
                warnings.append(
                    f"{key}={current} is insecure (recommended hardening: "
                    f"see documentation)"
                )
                details[key] = {
                    "current": current,
                    "insecure_values": bad_values,
                    "severity": "warning",
                }

        # Root login in securetty
        ttys = self.get_securetty()
        if ttys:
            warnings.append(
                "Root login is permitted on TTYs: " + ", ".join(ttys)
            )
            details["SECURETTY"] = {
                "current": ttys,
                "severity": "warning",
            }

        # Nologin active
        if self.is_nologin_active():
            msg = self.get_nologin_message()
            warnings.append(f"Nologin is active: {msg!r}")
            details["NOLOGIN"] = {"active": True, "message": msg}

        return {
            "valid": len(warnings) == 0,
            "warnings": warnings,
            "details": details,
            "checked_at": datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------
    # Defaults & standard values
    # ------------------------------------------------------------------

    def get_standard_login_defs(self) -> Dict[str, str]:
        """
        Return the UmerOS-recommended ``login.defs`` values.

        These are hardened defaults suitable for production servers.

        Returns
        -------
        dict[str, str]
            A hardening-oriented default mapping.
        """
        return {
            "PASS_MAX_DAYS": "90",
            "PASS_MIN_DAYS": "7",
            "PASS_MIN_LEN": "12",
            "PASS_WARN_AGE": "14",
            "UID_MIN": "1000",
            "UID_MAX": "60000",
            "GID_MIN": "1000",
            "GID_MAX": "60000",
            "CREATE_HOME": "yes",
            "DEFAULT_HOME": "no",
            "UMASK": "027",
            "ENCRYPT_METHOD": "SHA512",
            "SHA_CRYPT_MIN_ROUNDS": "10000",
            "SHA_CRYPT_MAX_ROUNDS": "10000",
            "LOGIN_RETRIES": "3",
            "LOGIN_TIMEOUT": "60",
            "LOGIN_STRING": "",
            "NOLOGINS_FILE": "/etc/nologin",
            "TTYPERM": "0600",
            "TTYGROUP": "tty",
            "TTYTYPE_FILE": "/etc/ttytype",
            "ENV_SUPATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "ENV_PATH": "/usr/local/bin:/usr/bin:/bin",
            "ENV_HZ": "Hertz",
            "ENVIRON_FILE": "/etc/environment",
            "ENV_KRB5CCNAME": "",
            "ENV_TICKET_VARIABLE": "KRB5CCNAME",
            "SU_NAME": "su",
            "SU_WHEEL_ONLY": "yes",
            "ENABLE_LASTLOG": "yes",
            "ENABLE_TMPLOG": "yes",
            "LASTLOG_UID_MAX": "60000",
            "LASTLOG_NOLOGINS_MAX": "",
            "HUSHLOGIN_FILE": ".hushlogin",
            "LOG_OK_LOGINS": "yes",
            "LOG_UNKFAIL_ENAB": "no",
            "SYSLOG_SU_ENAB": "yes",
            "SYSLOG_SG_ENAB": "yes",
            "SULOG_FILE": "/var/log/sulog",
            "CONSOLE": "",
            "CONSOLES": "",
            "BFAILDELAY": "10",
            "FAIL_DELAY": "1",
            "CLOSE_SESSIONS": "yes",
            "ONLY_ROOT_ALL_SHELLS": "no",
            "USERDEL_CMD": "",
            "USERGROUPS_ENAB": "no",
            "MD5_CRYPT_ENAB": "no",
            "MD5_CRYPT_ENABLE": "no",
            "CRYPT_MD5_ENABLE": "no",
            "DES_CRYPT_ENAB": "no",
        }

    # ------------------------------------------------------------------
    # Export / backup
    # ------------------------------------------------------------------

    def export_status(self) -> Dict[str, Any]:
        """
        Return a complete snapshot of the current login configuration state.

        Includes login.defs values, securetty entries, nologin status,
        and validation results.

        Returns
        -------
        dict
            Comprehensive status dictionary.
        """
        return {
            "login_defs": self.get_login_defs(),
            "securetty": self.get_securetty(),
            "nologin_active": self.is_nologin_active(),
            "nologin_message": self.get_nologin_message(),
            "uid_range": self.get_uid_range(),
            "gid_range": self.get_gid_range(),
            "umask": self.get_umask(),
            "encrypt_method": self.get_encrypt_method(),
            "home_config": self.get_home_config(),
            "env_config": self.get_env_config(),
            "timeout_config": self.get_timeout_config(),
            "validation": self.validate_config(),
            "exported_at": datetime.now().isoformat(),
        }

    def backup_all(self, backup_path: str) -> Dict[str, Any]:
        """
        Create timestamped backups of all managed configuration files.

        Parameters
        ----------
        backup_path : str
            Directory in which to store the backup files.

        Returns
        -------
        dict
            ``{"success": True, "backups": {name: path, ...}}``.
        """
        _ensure_root()
        os.makedirs(backup_path, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backups: Dict[str, Optional[str]] = {}

        sources = {
            "login_defs": self.login_defs_path,
            "securetty": self.securetty_path,
            "nologin": self.nologin_path,
        }

        for name, src in sources.items():
            if os.path.isfile(src):
                dest = os.path.join(backup_path, f"{name}.{ts}.bak")
                shutil.copy2(src, dest)
                backups[name] = dest
            else:
                backups[name] = None

        # Also save a fixed-name copy to LOGIN_DEFS_BAK
        if os.path.isfile(self.login_defs_path):
            shutil.copy2(self.login_defs_path, LOGIN_DEFS_BAK)
            backups["login_defs_canonical"] = LOGIN_DEFS_BAK

        return {"success": True, "backups": backups}

    def restore_login_defs(self, backup_path: str) -> Dict[str, Any]:
        """
        Restore ``login.defs`` from a backup file.

        Parameters
        ----------
        backup_path : str
            Full path to the backup file.

        Returns
        -------
        dict
            ``{"success": True, "restored_from": str}``.
        """
        _ensure_root()
        if not os.path.isfile(backup_path):
            raise LoginConfigError(f"Backup file not found: {backup_path}")
        _backup_file(self.login_defs_path)
        shutil.copy2(backup_path, self.login_defs_path)
        self._defs_cache = None  # invalidate cache
        return {"success": True, "restored_from": backup_path}

    # ------------------------------------------------------------------
    # lastlog / faillog helpers (read-only)
    # ------------------------------------------------------------------

    def get_lastlog_path(self) -> str:
        """Return the configured LASTLOG path."""
        return LASTLOG

    def get_faillog_path(self) -> str:
        """Return the configured FAILLOG path."""
        return FAILLOG

    def lastlog_exists(self) -> bool:
        """Check whether the lastlog file exists."""
        return os.path.isfile(LASTLOG)

    def faillog_exists(self) -> bool:
        """Check whether the faillog file exists."""
        return os.path.isfile(FAILLOG)

    # ------------------------------------------------------------------
    # Utility / summary
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """
        Return a human-readable summary of the current configuration.

        Returns
        -------
        str
            Multi-line text block suitable for display.
        """
        defs = self.get_login_defs()
        ttys = self.get_securetty()
        uid = self.get_uid_range()
        gid = self.get_gid_range()
        timeout = self.get_timeout_config()
        valid = self.validate_config()

        lines = [
            "=== UmerOS Login Configuration Summary ===",
            "",
            f"Password Max Days  : {defs.get('PASS_MAX_DAYS', 'N/A')}",
            f"Password Min Days  : {defs.get('PASS_MIN_DAYS', 'N/A')}",
            f"Password Min Len   : {defs.get('PASS_MIN_LEN', 'N/A')}",
            f"Password Warn Age  : {defs.get('PASS_WARN_AGE', 'N/A')}",
            f"Encrypt Method     : {defs.get('ENCRYPT_METHOD', 'N/A')}",
            f"UMASK              : {defs.get('UMASK', 'N/A')}",
            f"UID Range          : {uid['uid_min']} - {uid['uid_max']}",
            f"GID Range          : {gid['gid_min']} - {gid['gid_max']}",
            f"CREATE_HOME        : {defs.get('CREATE_HOME', 'N/A')}",
            f"LOGIN_TIMEOUT      : {timeout['LOGIN_TIMEOUT']}",
            f"LOGIN_RETRIES      : {timeout['LOGIN_RETRIES']}",
            f"TTYPERM            : {timeout['TTYPERM']}",
            f"Secure TTYs        : {', '.join(ttys) if ttys else '(none)'}",
            f"Nologin Active     : {self.is_nologin_active()}",
            f"Config Valid       : {valid['valid']}",
            "",
        ]

        if valid["warnings"]:
            lines.append("Warnings:")
            for w in valid["warnings"]:
                lines.append(f"  - {w}")
            lines.append("")

        lines.append("=" * 42)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Minimal CLI for quick inspection and validation."""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="UmerOS Login Configuration Manager"
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    sub.add_parser("summary", help="Show configuration summary")
    sub.add_parser("validate", help="Validate current configuration")
    sub.add_parser("export", help="Export full status as JSON")
    sub.add_parser("login-defs", help="Show all login.defs values")
    sub.add_parser("securetty", help="Show securetty entries")
    sub.add_parser("standard", help="Show UmerOS standard defaults")

    args = parser.parse_args()
    mgr = LoginConfigManager()

    if args.command == "summary":
        print(mgr.summary())
    elif args.command == "validate":
        result = mgr.validate_config()
        print(json.dumps(result, indent=2))
    elif args.command == "export":
        print(json.dumps(mgr.export_status(), indent=2, default=str))
    elif args.command == "login-defs":
        print(json.dumps(mgr.get_login_defs(), indent=2))
    elif args.command == "securetty":
        ttys = mgr.get_securetty()
        for tty in ttys:
            print(tty)
    elif args.command == "standard":
        print(json.dumps(mgr.get_standard_login_defs(), indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
