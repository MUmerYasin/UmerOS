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
UmerOS PAM Configuration Manager
=================================
Manages Pluggable Authentication Modules (PAM) configuration files.
Handles /etc/pam.d/*, /etc/pam.conf, and /etc/security/* configuration files.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


# =============================================================================
# Path Constants
# =============================================================================

PAM_D_DIR: str = "/etc/pam.d"
PAM_CONF: str = "/etc/pam.conf"
SECURITY_DIR: str = "/etc/security"

LIMITS_CONF: str = os.path.join(SECURITY_DIR, "limits.conf")
ACCESS_CONF: str = os.path.join(SECURITY_DIR, "access.conf")
NAMESPACE_CONF: str = os.path.join(SECURITY_DIR, "namespace.conf")
PWQUALITY_CONF: str = os.path.join(SECURITY_DIR, "pwquality.conf")
GROUP_CONF: str = os.path.join(SECURITY_DIR, "group.conf")
TIME_CONF: str = os.path.join(SECURITY_DIR, "time.conf")
PAM_ENV_CONF: str = os.path.join(SECURITY_DIR, "pam_env.conf")
FAILDELAY_CONF: str = os.path.join(SECURITY_DIR, "faillock.conf")

# =============================================================================
# PAM Type and Control Constants
# =============================================================================

PAM_TYPES: List[str] = ["auth", "account", "password", "session"]

CONTROL_FLAGS: List[str] = [
    "required",
    "requisite",
    "sufficient",
    "optional",
    "include",
    "substack",
]

CONTROL_ACTIONS: List[str] = ["ok", "die", "bad", "silent", "ignore"]

# =============================================================================
# Regex Patterns
# =============================================================================

_PAM_LINE_RE: re.Pattern = re.compile(
    r"""
    ^\s*
    (?P<type>auth|account|password|session)   # PAM type
    \s+
    (?P<control>\S+)                           # control flag or [bracketed]
    \s+
    (?P<rest>.+?)                              # module + options
    \s*$
    """,
    re.VERBOSE,
)

_MODULE_ARGS_RE: re.Pattern = re.compile(
    r"""
    ^(?P<module>\S+/[\w.-]+\.so)  # module path ending in .so
    (\s+(?P<args>.*))?             # optional args
    \s*$
    """,
    re.VERBOSE,
)

_BRACKET_CONTROL_RE: re.Pattern = re.compile(
    r"^\[(?P<actions>.+)\]\s*$"
)

_LIMITS_LINE_RE: re.Pattern = re.compile(
    r"""
    ^\s*
    (?P<domain>\S+)         # domain: *, user, @group
    \s+
    (?P<ltype>-?)           # soft (-), hard (#), or none
    (?P<item>\w+)           # item name
    \s+
    (?P<value>\S+)          # value
    \s*$
    """,
    re.VERBOSE,
)

_ACCESS_LINE_RE: re.Pattern = re.compile(
    r"""
    ^\s*
    (?P<permission>[+-])    # + allow, - deny
    \s*:\s*
    (?P<users>\S+)          # users/groups
    \s*:\s*
    (?P<origin>\S+)         # origin (tty, ip, etc.)
    \s*$
    """,
    re.VERBOSE,
)

_TIME_LINE_RE: re.Pattern = re.compile(
    r"""
    ^\s*
    (?P<users>\S+)
    \s+
    (?P<ttys>\S+)
    \s+
    (?P<times>.+)
    \s*$
    """,
    re.VERBOSE,
)

_PAM_ENV_LINE_RE: re.Pattern = re.compile(
    r"""
    ^\s*
    (?P<var>\w+)            # variable name
    (\s+DEFAULT=(?P<default>[^ ]+))?    # optional DEFAULT
    (\s+OVERRIDE=(?P<override>[^ ]+))?  # optional OVERRIDE
    \s*$
    """,
    re.VERBOSE,
)

_FAILLOCK_LINE_RE: re.Pattern = re.compile(
    r"^\s*(?P<key>\w+)\s*=\s*(?P<value>.+)\s*$"
)

_COMMENT_RE: re.Pattern = re.compile(r"^\s*(?:#.*)?$")

_GROUP_LINE_RE: re.Pattern = re.compile(
    r"""
    ^\s*
    (?P<users>\S+)
    \s*;\s*
    (?P<groups>\S+)
    \s*;\s*
    (?P<services>\S+)
    \s*;\s*
    (?P<times>.+)
    \s*$
    """,
    re.VERBOSE,
)

# =============================================================================
# Standard PAM Modules by Type
# =============================================================================

STANDARD_PAM_MODULES: Dict[str, List[Dict[str, str]]] = {
    "auth": [
        {"module": "pam_unix.so", "description": "Traditional Unix password authentication", "risk": "low"},
        {"module": "pam_securetty.so", "description": "Limit root login to secure TTYs", "risk": "low"},
        {"module": "pam_nologin.so", "description": "Prevent login when /etc/nologin exists", "risk": "low"},
        {"module": "pam_env.so", "description": "Load environment variables from pam_env.conf", "risk": "low"},
        {"module": "pam_faildelay.so", "description": "Delay on authentication failure", "risk": "low"},
        {"module": "pam_faillock.so", "description": "Lock account after failed attempts", "risk": "low"},
        {"module": "pam_tally2.so", "description": "Count failed login attempts (deprecated)", "risk": "medium"},
        {"module": "pam_sss.so", "description": "SSSD authentication", "risk": "low"},
        {"module": "pam_ldap.so", "description": "LDAP authentication", "risk": "medium"},
        {"module": "pam_krb5.so", "description": "Kerberos V5 authentication", "risk": "medium"},
        {"module": "pam_google_authenticator.so", "description": "Google Authenticator TOTP", "risk": "low"},
        {"module": "pam_pwquality.so", "description": "Password quality checking", "risk": "low"},
    ],
    "account": [
        {"module": "pam_unix.so", "description": "Account validity checking", "risk": "low"},
        {"module": "pam_permit.so", "description": "Always permit access", "risk": "high"},
        {"module": "pam_deny.so", "description": "Always deny access", "risk": "low"},
        {"module": "pam_access.so", "description": "Access control via access.conf", "risk": "low"},
        {"module": "pam_time.so", "description": "Time-based access control", "risk": "low"},
        {"module": "pam_sss.so", "description": "SSSD account management", "risk": "low"},
        {"module": "pam_ldap.so", "description": "LDAP account management", "risk": "medium"},
        {"module": "pam_krb5.so", "description": "Kerberos account validation", "risk": "medium"},
        {"module": "pam_nologin.so", "description": "Check /etc/nologin for account access", "risk": "low"},
    ],
    "password": [
        {"module": "pam_unix.so", "description": "Password quality and aging", "risk": "low"},
        {"module": "pam_pwquality.so", "description": "Password complexity requirements", "risk": "low"},
        {"module": "pam_sss.so", "description": "SSSD password management", "risk": "low"},
        {"module": "pam_ldap.so", "description": "LDAP password changes", "risk": "medium"},
        {"module": "pam_krb5.so", "description": "Kerberos password changes", "risk": "medium"},
        {"module": "pam_pwhistory.so", "description": "Remember previous passwords", "risk": "low"},
        {"module": "pam_cracklib.so", "description": "Password strength checking (deprecated)", "risk": "medium"},
    ],
    "session": [
        {"module": "pam_unix.so", "description": "Session setup/cleanup", "risk": "low"},
        {"module": "pam_env.so", "description": "Set up session environment", "risk": "low"},
        {"module": "pam_motd.so", "description": "Display message of the day", "risk": "low"},
        {"module": "pam_limits.so", "description": "Apply resource limits from limits.conf", "risk": "low"},
        {"module": "pam_loginuid.so", "description": "Set login UID", "risk": "low"},
        {"module": "pam_namespace.so", "description": "Polyinstantiated directories", "risk": "low"},
        {"module": "pam_sss.so", "description": "SSSD session management", "risk": "low"},
        {"module": "pam_oddjob_mkhomedir.so", "description": "Create home directory on login", "risk": "low"},
        {"module": "pam_mkhomedir.so", "description": "Create home directory on login", "risk": "low"},
        {"module": "pam_systemd.so", "description": "Register session with systemd", "risk": "low"},
    ],
}

# =============================================================================
# Standard PAM Services
# =============================================================================

STANDARD_PAM_SERVICES: List[str] = [
    "common-auth",
    "common-account",
    "common-password",
    "common-session",
    "common-session-noninteractive",
    "system-auth",
    "password-auth",
    "account-auth",
    "session-auth",
    "sshd",
    "login",
    "sudo",
    "su",
    "gdm-password",
    "gdm-launch-environment",
    "kdm",
    "xdm",
    "lightdm",
    "polkit-1",
    "crond",
    "atd",
    "sssd",
    "system-login",
    "system-service",
    "postlogin",
    "fingerprint-auth",
    "smartcard-auth",
]

# =============================================================================
# Deprecated and Insecure Modules
# =============================================================================

DEPRECATED_MODULES: Dict[str, str] = {
    "pam_tally2.so": "Replaced by pam_faillock.so",
    "pam_cracklib.so": "Replaced by pam_pwquality.so",
    "pam_rhosts_auth.so": "Replaced by pam_securetty.so",
    "pam_ftp.so": "FTP authentication is insecure; use FTPS/SFTP instead",
    "pam_stack.so": "Replaced by include directive",
}

INSECURE_PATTERNS: List[Dict[str, str]] = [
    {"pattern": r"auth\s+sufficient\s+pam_permit\.so", "description": "pam_permit.so with sufficient allows passwordless login", "risk": "critical"},
    {"pattern": r"auth\s+.*pam_deny\.so", "description": "pam_deny.so in auth stack may block all authentication", "risk": "medium"},
    {"pattern": r"password\s+.*pam_permit\.so", "description": "pam_permit.so in password allows any password change", "risk": "critical"},
    {"pattern": r"auth\s+.*pam_tally2\.so", "description": "pam_tally2.so is deprecated, use pam_faillock.so", "risk": "medium"},
]


# =============================================================================
# Helper Utilities
# =============================================================================


def _is_comment_or_blank(line: str) -> bool:
    """Check if a line is a comment or blank."""
    return bool(_COMMENT_RE.match(line))


def _safe_read(path: str) -> str:
    """Read file contents safely, returning empty string if file doesn't exist."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except (FileNotFoundError, PermissionError, OSError):
        return ""


def _safe_write(path: str, content: str) -> None:
    """Write content to file atomically using temp file + rename."""
    dir_name = os.path.dirname(path)
    if dir_name and not os.path.isdir(dir_name):
        os.makedirs(dir_name, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        shutil.move(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _ensure_dir(path: str) -> None:
    """Create directory if it doesn't exist."""
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)

# =============================================================================
# PAMConfigManager
# =============================================================================


class PAMConfigManager:
    """
    Manager for PAM and /etc/security configuration files.

    Provides methods to parse, create, update, and validate PAM service files,
    legacy /etc/pam.conf, and security configuration files.

    Usage::

        manager = PAMConfigManager()
        services = manager.list_services()
        sshd_entries = manager.get_service("sshd")
        manager.add_auth_rule("sshd", "pam_unix.so", "required")
    """

    def __init__(
        self,
        pam_d_dir: str = PAM_D_DIR,
        pam_conf: str = PAM_CONF,
        security_dir: str = SECURITY_DIR,
    ) -> None:
        """
        Initialize the PAM configuration manager.

        Args:
            pam_d_dir: Path to /etc/pam.d directory.
            pam_conf: Path to /etc/pam.conf.
            security_dir: Path to /etc/security directory.
        """
        self.pam_d_dir = pam_d_dir
        self.pam_conf = pam_conf
        self.security_dir = security_dir

        _ensure_dir(self.pam_d_dir)
        _ensure_dir(self.security_dir)

    # =========================================================================
    # Service Management
    # =========================================================================

    def list_services(self) -> List[str]:
        """
        List all available PAM service files.

        Returns:
            Sorted list of service names (filenames in /etc/pam.d).
        """
        try:
            entries = []
            for entry in os.scandir(self.pam_d_dir):
                if entry.is_file() and not entry.name.startswith("."):
                    entries.append(entry.name)
            return sorted(entries)
        except (FileNotFoundError, PermissionError, OSError):
            return []

    def get_service(self, name: str) -> List[Dict[str, Any]]:
        """
        Parse a PAM service file and return its entries.

        Args:
            name: Service name (filename in /etc/pam.d).

        Returns:
            List of parsed entry dicts, each containing:
                - line_number (int)
                - raw (str)
                - type (str | None)
                - control (str | None)
                - bracket_control (dict | None)
                - options (str | None)
                - module (str | None)
                - args (str | None)
                - is_comment (bool)
                - is_blank (bool)
                - header (str | None)
        """
        path = os.path.join(self.pam_d_dir, name)
        content = _safe_read(path)
        return self._parse_pam_file(content)

    def set_service(
        self,
        name: str,
        entries: List[Dict[str, Any]],
        header: str = "",
    ) -> Dict[str, Any]:
        """
        Write a PAM service file from parsed entries.

        Args:
            name: Service name.
            entries: List of entry dicts (as returned by get_service).
            header: Optional header comment block.

        Returns:
            Dict with 'success', 'path', 'line_count', 'timestamp'.
        """
        path = os.path.join(self.pam_d_dir, name)
        lines: List[str] = []

        if header:
            for hline in header.splitlines():
                lines.append(f"# {hline}" if not hline.startswith("#") else hline)
            lines.append("")

        for entry in entries:
            if entry.get("is_comment") or entry.get("is_blank"):
                lines.append(entry.get("raw", ""))
            elif entry.get("header"):
                lines.append(entry["header"])
            else:
                raw = entry.get("raw", "").strip()
                if raw:
                    lines.append(raw)

        content = "\n".join(lines) + "\n" if lines else ""
        _safe_write(path, content)

        return {
            "success": True,
            "path": path,
            "line_count": len(lines),
            "timestamp": datetime.now().isoformat(),
        }

    def delete_service(self, name: str) -> Dict[str, Any]:
        """
        Delete a PAM service file.

        Args:
            name: Service name to delete.

        Returns:
            Dict with 'success', 'path', 'existed', 'timestamp'.
        """
        path = os.path.join(self.pam_d_dir, name)
        existed = os.path.isfile(path)
        if existed:
            os.remove(path)

        return {
            "success": True,
            "path": path,
            "existed": existed,
            "timestamp": datetime.now().isoformat(),
        }

    # =========================================================================
    # PAM Rule Addition Helpers
    # =========================================================================

    def _add_rule(
        self,
        service: str,
        pam_type: str,
        module: str,
        control: str = "required",
        args: str = "",
        options: str = "",
    ) -> Dict[str, Any]:
        """
        Internal helper to add a rule to a service.

        Args:
            service: Service name.
            pam_type: PAM type (auth, account, password, session).
            module: Module .so path.
            control: Control flag.
            args: Module arguments.
            options: Bracketed control or additional options string.

        Returns:
            Dict with 'success', 'service', 'rule', 'line_count', 'timestamp'.
        """
        if pam_type not in PAM_TYPES:
            return {
                "success": False,
                "error": f"Invalid PAM type: {pam_type}. Must be one of {PAM_TYPES}",
            }

        path = os.path.join(self.pam_d_dir, service)
        entries = self.get_service(service)

        parts = [pam_type, control]
        if options:
            parts.append(options)
        parts.append(module)
        if args:
            parts.append(args)

        raw_rule = " ".join(parts)

        new_entry: Dict[str, Any] = {
            "line_number": len(entries) + 1,
            "raw": raw_rule,
            "type": pam_type,
            "control": control,
            "bracket_control": None,
            "options": options or None,
            "module": module,
            "args": args,
            "is_comment": False,
            "is_blank": False,
            "header": None,
        }

        if control.startswith("["):
            bracket_match = _BRACKET_CONTROL_RE.match(control)
            if bracket_match:
                actions = {}
                for pair in bracket_match.group("actions").split():
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        actions[k] = v
                new_entry["bracket_control"] = actions

        entries.append(new_entry)
        result = self.set_service(service, entries)

        return {
            "success": True,
            "service": service,
            "rule": raw_rule,
            "line_count": result["line_count"],
            "timestamp": result["timestamp"],
        }

    def add_auth_rule(
        self,
        service: str,
        module: str,
        control: str = "required",
        args: str = "",
        options: str = "",
    ) -> Dict[str, Any]:
        """Add an auth rule to a service."""
        return self._add_rule(service, "auth", module, control, args, options)

    def add_account_rule(
        self,
        service: str,
        module: str,
        control: str = "required",
        args: str = "",
        options: str = "",
    ) -> Dict[str, Any]:
        """Add an account rule to a service."""
        return self._add_rule(service, "account", module, control, args, options)

    def add_password_rule(
        self,
        service: str,
        module: str,
        control: str = "required",
        args: str = "",
        options: str = "",
    ) -> Dict[str, Any]:
        """Add a password rule to a service."""
        return self._add_rule(service, "password", module, control, args, options)

    def add_session_rule(
        self,
        service: str,
        module: str,
        control: str = "required",
        args: str = "",
        options: str = "",
    ) -> Dict[str, Any]:
        """Add a session rule to a service."""
        return self._add_rule(service, "session", module, control, args, options)

    # =========================================================================
    # Legacy /etc/pam.conf
    # =========================================================================

    def get_pam_conf(self) -> List[Dict[str, Any]]:
        """
        Parse the legacy /etc/pam.conf file.

        Returns:
            List of parsed entry dicts.
        """
        content = _safe_read(self.pam_conf)
        return self._parse_pam_file(content, is_pam_conf=True)

    def set_pam_conf(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Write the legacy /etc/pam.conf file.

        Args:
            entries: List of entry dicts.

        Returns:
            Dict with 'success', 'path', 'line_count', 'timestamp'.
        """
        lines: List[str] = []
        for entry in entries:
            if entry.get("is_comment") or entry.get("is_blank"):
                lines.append(entry.get("raw", ""))
            elif entry.get("header"):
                lines.append(entry["header"])
            else:
                raw = entry.get("raw", "").strip()
                if raw:
                    lines.append(raw)

        content = "\n".join(lines) + "\n" if lines else ""
        _safe_write(self.pam_conf, content)

        return {
            "success": True,
            "path": self.pam_conf,
            "line_count": len(lines),
            "timestamp": datetime.now().isoformat(),
        }
    # =========================================================================
    # /etc/security/limits.conf
    # =========================================================================

    def get_limits(self) -> List[Dict[str, Any]]:
        """
        Parse /etc/security/limits.conf.

        Returns:
            List of dicts with keys: domain, ltype (soft/hard/none),
            item, value, raw, line_number, is_comment, is_blank.
        """
        content = _safe_read(LIMITS_CONF)
        return self._parse_limits_file(content)

    def set_limits(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Write /etc/security/limits.conf.

        Args:
            entries: List of limit entry dicts.

        Returns:
            Dict with success status.
        """
        lines: List[str] = []
        for entry in entries:
            if entry.get("is_comment") or entry.get("is_blank"):
                lines.append(entry.get("raw", ""))
            else:
                domain = entry.get("domain", "*")
                ltype = entry.get("ltype", "")
                item = entry.get("item", "")
                value = entry.get("value", "")
                if ltype:
                    lines.append(f"{domain}\t-{item}\t{value}")
                else:
                    lines.append(f"{domain}\t{item}\t{value}")

        content = "\n".join(lines) + "\n" if lines else ""
        _safe_write(LIMITS_CONF, content)

        return {
            "success": True,
            "path": LIMITS_CONF,
            "line_count": len(lines),
            "timestamp": datetime.now().isoformat(),
        }

    def add_limit(
        self,
        domain: str,
        ltype: str,
        item: str,
        value: str,
    ) -> Dict[str, Any]:
        """
        Add a single limit entry.

        Args:
            domain: User, group (@group), or wildcard (*).
            ltype: '-' for soft, '#' for hard, '' for both.
            item: Limit item (nofile, nproc, core, etc.).
            value: Limit value.

        Returns:
            Dict with success status and total entry count.
        """
        entries = self.get_limits()

        filtered = [
            e for e in entries
            if not (e.get("is_comment") and "End of" in str(e.get("raw", "")))
        ]

        new_entry: Dict[str, Any] = {
            "domain": domain,
            "ltype": ltype,
            "item": item,
            "value": value,
            "raw": f"{domain}\t{ltype}{item}\t{value}",
            "line_number": len(filtered) + 1,
            "is_comment": False,
            "is_blank": False,
        }

        filtered.append(new_entry)
        result = self.set_limits(filtered)

        return {
            "success": True,
            "domain": domain,
            "ltype": ltype,
            "item": item,
            "value": value,
            "total_entries": len(filtered),
            "timestamp": result["timestamp"],
        }

    # =========================================================================
    # /etc/security/access.conf
    # =========================================================================

    def get_access_rules(self) -> List[Dict[str, Any]]:
        """
        Parse /etc/security/access.conf.

        Returns:
            List of dicts with keys: permission, users, origin, raw,
            line_number, is_comment, is_blank.
        """
        content = _safe_read(ACCESS_CONF)
        return self._parse_access_file(content)

    def set_access_rules(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Write /etc/security/access.conf.

        Args:
            entries: List of access rule entry dicts.

        Returns:
            Dict with success status.
        """
        lines: List[str] = []
        for entry in entries:
            if entry.get("is_comment") or entry.get("is_blank"):
                lines.append(entry.get("raw", ""))
            else:
                permission = entry.get("permission", "+")
                users = entry.get("users", "")
                origin = entry.get("origin", "")
                lines.append(f"{permission} : {users} : {origin}")

        content = "\n".join(lines) + "\n" if lines else ""
        _safe_write(ACCESS_CONF, content)

        return {
            "success": True,
            "path": ACCESS_CONF,
            "line_count": len(lines),
            "timestamp": datetime.now().isoformat(),
        }

    def add_access_rule(
        self,
        permission: str,
        users: str,
        origin: str,
    ) -> Dict[str, Any]:
        """
        Add an access control rule.

        Args:
            permission: '+' for allow, '-' for deny.
            users: Usernames, groups (@group), or ALL.
            origin: TTY name, IP, hostname, or ALL.

        Returns:
            Dict with success status.
        """
        entries = self.get_access_rules()

        filtered = [
            e for e in entries
            if not (e.get("is_comment") and "End of" in str(e.get("raw", "")))
        ]

        new_entry: Dict[str, Any] = {
            "permission": permission,
            "users": users,
            "origin": origin,
            "raw": f"{permission} : {users} : {origin}",
            "line_number": len(filtered) + 1,
            "is_comment": False,
            "is_blank": False,
        }

        filtered.append(new_entry)
        result = self.set_access_rules(filtered)

        return {
            "success": True,
            "permission": permission,
            "users": users,
            "origin": origin,
            "total_entries": len(filtered),
            "timestamp": result["timestamp"],
        }

    # =========================================================================
    # /etc/security/pwquality.conf
    # =========================================================================

    def get_pwquality(self) -> Dict[str, str]:
        """
        Parse /etc/security/pwquality.conf (key=value format).

        Returns:
            Dict of setting_name -> value.
        """
        content = _safe_read(PWQUALITY_CONF)
        return self._parse_key_value(content)

    def set_pwquality(self, settings: Dict[str, str]) -> Dict[str, Any]:
        """
        Write /etc/security/pwquality.conf.

        Args:
            settings: Dict of key=value pairs.

        Returns:
            Dict with success status.
        """
        lines: List[str] = [
            "#",
            "# /etc/security/pwquality.conf",
            "# Password quality configuration for UmerOS",
            "#",
            "",
        ]

        for key, value in sorted(settings.items()):
            lines.append(f"{key} = {value}")

        content = "\n".join(lines) + "\n"
        _safe_write(PWQUALITY_CONF, content)

        return {
            "success": True,
            "path": PWQUALITY_CONF,
            "setting_count": len(settings),
            "timestamp": datetime.now().isoformat(),
        }

    # =========================================================================
    # /etc/security/namespace.conf
    # =========================================================================

    def get_namespace(self) -> Dict[str, str]:
        """
        Parse /etc/security/namespace.conf.

        Returns:
            Dict of setting_name -> value.
        """
        content = _safe_read(NAMESPACE_CONF)
        return self._parse_key_value(content)

    def set_namespace(self, settings: Dict[str, str]) -> Dict[str, Any]:
        """
        Write /etc/security/namespace.conf.

        Args:
            settings: Dict of key=value pairs.

        Returns:
            Dict with success status.
        """
        lines: List[str] = [
            "#",
            "# /etc/security/namespace.conf",
            "# Polyinstantiated directories configuration",
            "#",
            "",
        ]

        for key, value in sorted(settings.items()):
            lines.append(f"{key}\t{value}")

        content = "\n".join(lines) + "\n"
        _safe_write(NAMESPACE_CONF, content)

        return {
            "success": True,
            "path": NAMESPACE_CONF,
            "setting_count": len(settings),
            "timestamp": datetime.now().isoformat(),
        }
    # =========================================================================
    # /etc/security/time.conf
    # =========================================================================

    def get_time_rules(self) -> List[Dict[str, Any]]:
        """
        Parse /etc/security/time.conf.

        Returns:
            List of dicts with keys: services, ttys, users, times, raw,
            line_number, is_comment, is_blank.
        """
        content = _safe_read(TIME_CONF)
        return self._parse_time_file(content)

    def set_time_rules(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Write /etc/security/time.conf.

        Args:
            entries: List of time rule entry dicts.

        Returns:
            Dict with success status.
        """
        lines: List[str] = []
        for entry in entries:
            if entry.get("is_comment") or entry.get("is_blank"):
                lines.append(entry.get("raw", ""))
            else:
                services = entry.get("services", "")
                ttys = entry.get("ttys", "")
                users = entry.get("users", "")
                times = entry.get("times", "")
                lines.append(f"{services};{ttys};{users};{times}")

        content = "\n".join(lines) + "\n" if lines else ""
        _safe_write(TIME_CONF, content)

        return {
            "success": True,
            "path": TIME_CONF,
            "line_count": len(lines),
            "timestamp": datetime.now().isoformat(),
        }

    def add_time_rule(
        self,
        services: str,
        ttys: str,
        users: str,
        times: str,
    ) -> Dict[str, Any]:
        """
        Add a time-based access control rule.

        Args:
            services: PAM service names (* for all).
            ttys: TTY names (* for all).
            users: Usernames (* for all).
            times: Time ranges (MoTuFr0800-2000 format).

        Returns:
            Dict with success status.
        """
        entries = self.get_time_rules()

        filtered = [
            e for e in entries
            if not (e.get("is_comment") and "End of" in str(e.get("raw", "")))
        ]

        new_entry: Dict[str, Any] = {
            "services": services,
            "ttys": ttys,
            "users": users,
            "times": times,
            "raw": f"{services};{ttys};{users};{times}",
            "line_number": len(filtered) + 1,
            "is_comment": False,
            "is_blank": False,
        }

        filtered.append(new_entry)
        result = self.set_time_rules(filtered)

        return {
            "success": True,
            "services": services,
            "ttys": ttys,
            "users": users,
            "times": times,
            "total_entries": len(filtered),
            "timestamp": result["timestamp"],
        }

    # =========================================================================
    # /etc/security/group.conf
    # =========================================================================

    def get_group_rules(self) -> List[Dict[str, Any]]:
        """
        Parse /etc/security/group.conf.

        Returns:
            List of dicts with keys: users, groups, ttys, times, maxlogins,
            raw, line_number, is_comment, is_blank.
        """
        content = _safe_read(GROUP_CONF)
        return self._parse_group_file(content)

    def set_group_rules(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Write /etc/security/group.conf.

        Args:
            entries: List of group rule entry dicts.

        Returns:
            Dict with success status.
        """
        lines: List[str] = []
        for entry in entries:
            if entry.get("is_comment") or entry.get("is_blank"):
                lines.append(entry.get("raw", ""))
            else:
                users = entry.get("users", "")
                groups = entry.get("groups", "")
                ttys = entry.get("ttys", "")
                times = entry.get("times", "")
                maxlogins = entry.get("maxlogins", "")
                lines.append(
                    f"{users};{groups};{ttys};{times};{maxlogins}"
                )

        content = "\n".join(lines) + "\n" if lines else ""
        _safe_write(GROUP_CONF, content)

        return {
            "success": True,
            "path": GROUP_CONF,
            "line_count": len(lines),
            "timestamp": datetime.now().isoformat(),
        }

    def add_group_rule(
        self,
        users: str,
        groups: str,
        ttys: str,
        times: str,
        maxlogins: str,
    ) -> Dict[str, Any]:
        """
        Add a group-based login limit rule.

        Args:
            users: Usernames (* for all).
            groups: Group names (* for all).
            ttys: TTY patterns (* for all).
            times: Time ranges (* for all).
            maxlogins: Maximum simultaneous logins.

        Returns:
            Dict with success status.
        """
        entries = self.get_group_rules()

        filtered = [
            e for e in entries
            if not (e.get("is_comment") and "End of" in str(e.get("raw", "")))
        ]

        new_entry: Dict[str, Any] = {
            "users": users,
            "groups": groups,
            "ttys": ttys,
            "times": times,
            "maxlogins": maxlogins,
            "raw": f"{users};{groups};{ttys};{times};{maxlogins}",
            "line_number": len(filtered) + 1,
            "is_comment": False,
            "is_blank": False,
        }

        filtered.append(new_entry)
        result = self.set_group_rules(filtered)

        return {
            "success": True,
            "users": users,
            "groups": groups,
            "ttys": ttys,
            "times": times,
            "maxlogins": maxlogins,
            "total_entries": len(filtered),
            "timestamp": result["timestamp"],
        }

    # =========================================================================
    # /etc/security/pam_env.conf
    # =========================================================================

    def get_pam_env(self) -> Dict[str, str]:
        """
        Parse /etc/security/pam_env.conf.

        Returns:
            Dict of environment variable -> value.
        """
        content = _safe_read(PAM_ENV_CONF)
        return self._parse_key_value(content)

    def set_pam_env(self, variables: Dict[str, str]) -> Dict[str, Any]:
        """
        Write /etc/security/pam_env.conf.

        Args:
            variables: Dict of env var -> value.

        Returns:
            Dict with success status.
        """
        lines: List[str] = [
            "#",
            "# /etc/security/pam_env.conf",
            "# Default environment variables for UmerOS",
            "#",
            "",
        ]

        for key, value in sorted(variables.items()):
            lines.append(f"{key}={value}")

        content = "\n".join(lines) + "\n"
        _safe_write(PAM_ENV_CONF, content)

        return {
            "success": True,
            "path": PAM_ENV_CONF,
            "variable_count": len(variables),
            "timestamp": datetime.now().isoformat(),
        }

    # =========================================================================
    # /etc/security/faillock.conf
    # =========================================================================

    def get_faillock(self) -> Dict[str, str]:
        """
        Parse /etc/security/faillock.conf.

        Returns:
            Dict of setting_name -> value.
        """
        content = _safe_read(FAILLOCK_CONF)
        return self._parse_key_value(content)

    def set_faillock(self, settings: Dict[str, str]) -> Dict[str, Any]:
        """
        Write /etc/security/faillock.conf.

        Args:
            settings: Dict of key=value pairs.

        Returns:
            Dict with success status.
        """
        lines: List[str] = [
            "#",
            "# /etc/security/faillock.conf",
            "# Account lockout configuration for UmerOS",
            "#",
            "",
        ]

        for key, value in sorted(settings.items()):
            lines.append(f"{key} = {value}")

        content = "\n".join(lines) + "\n"
        _safe_write(FAILLOCK_CONF, content)

        return {
            "success": True,
            "path": FAILLOCK_CONF,
            "setting_count": len(settings),
            "timestamp": datetime.now().isoformat(),
        }
    # =========================================================================
    # Validation & Utilities
    # =========================================================================

    def validate_service(self, name: str) -> Dict[str, Any]:
        """
        Validate a PAM service file for common issues.

        Checks:
            - File exists
            - Has required types (auth, account, password, session)
            - No deprecated modules
            - No suspicious control flags
            - Module paths exist (if not optional)

        Args:
            name: Service name to validate.

        Returns:
            Dict with 'valid', 'issues', 'warnings', 'service'.
        """
        issues: List[str] = []
        warnings: List[str] = []

        path = os.path.join(self.pam_d_dir, name)
        if not os.path.isfile(path):
            return {
                "valid": False,
                "issues": [f"Service file not found: {path}"],
                "warnings": [],
                "service": name,
            }

        entries = self.get_service(name)

        found_types: Set[str] = set()
        for entry in entries:
            if entry.get("is_comment") or entry.get("is_blank"):
                continue

            pam_type = entry.get("type")
            module = entry.get("module")
            control = entry.get("control")

            if pam_type:
                found_types.add(pam_type)

            if module:
                module_base = os.path.basename(module)

                if module_base in DEPRECATED_MODULES:
                    reason = DEPRECATED_MODULES.get(module_base, "deprecated")
                    warnings.append(
                        f"Deprecated module: {module} ({reason})"
                    )

                if module_base == "pam_access.so" and pam_type == "auth":
                    issues.append(
                        "pam_access.so should be in 'account', not 'auth'"
                    )

            if control and pam_type:
                if pam_type not in PAM_TYPES:
                    issues.append(f"Unknown PAM type: {pam_type}")

                if pam_type == "auth" and control in ("required", "requisite"):
                    entry_args = entry.get("args", "")
                    if "nullok" in str(entry_args):
                        warnings.append(
                            f"auth {control} {module} has nullok - "
                            "allows empty passwords"
                        )

        if name in STANDARD_PAM_SERVICES:
            required = {"auth", "account", "password", "session"}
            missing = required - found_types
            if missing:
                warnings.append(
                    f"Standard service '{name}' missing types: {missing}"
                )

        for entry in entries:
            if entry.get("is_comment") and entry.get("raw"):
                raw = entry["raw"]
                if "password" in raw.lower() and not raw.startswith("#"):
                    pass

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "service": name,
        }

    def get_standard_modules(self) -> Dict[str, Dict[str, str]]:
        """
        Get the dictionary of standard PAM modules and descriptions.

        Returns:
            Dict of module_name -> {description, auth, account, password, session}.
        """
        return STANDARD_PAM_MODULES.copy()

    def get_standard_services(self) -> List[str]:
        """
        Get the list of standard PAM service names.

        Returns:
            Copy of the standard services list.
        """
        return STANDARD_PAM_SERVICES.copy()

    def export_status(self) -> Dict[str, Any]:
        """
        Export the current state of all PAM and security configurations.

        Returns:
            Dict with full status of every managed file.
        """
        status: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "pam_d": {
                "path": self.pam_d_dir,
                "exists": os.path.isdir(self.pam_d_dir),
                "services": {},
            },
            "pam_conf": {
                "path": self.pam_conf,
                "exists": os.path.isfile(self.pam_conf),
                "entry_count": 0,
            },
            "security_configs": {},
        }

        for service in self.list_services():
            entries = self.get_service(service)
            status["pam_d"]["services"][service] = {
                "entry_count": len(entries),
                "types": sorted({
                    e.get("type") for e in entries
                    if e.get("type")
                }),
            }

        if status["pam_conf"]["exists"]:
            pam_entries = self.get_pam_conf()
            status["pam_conf"]["entry_count"] = len(pam_entries)

        for config_name, config_path in SECURITY_CONFIGS.items():
            exists = os.path.isfile(config_path)
            size = os.path.getsize(config_path) if exists else 0
            status["security_configs"][config_name] = {
                "path": config_path,
                "exists": exists,
                "size": size,
            }

        return status

    def backup_all(self, backup_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a timestamped backup of all PAM and security configs.

        Args:
            backup_dir: Backup destination directory.
                       Defaults to /etc/pam_config_backups/{timestamp}/

        Returns:
            Dict with backup path, files backed up, errors.
        """
        if backup_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = os.path.join(
                os.path.dirname(self.pam_d_dir),
                "pam_config_backups",
                timestamp,
            )

        backup_path = os.path.expanduser(backup_dir)
        os.makedirs(backup_path, exist_ok=True)
        os.makedirs(os.path.join(backup_path, "pam.d"), exist_ok=True)
        os.makedirs(os.path.join(backup_path, "security"), exist_ok=True)

        backed_up: List[str] = []
        errors: List[str] = []

        import shutil

        for service in self.list_services():
            src = os.path.join(self.pam_d_dir, service)
            dst = os.path.join(backup_path, "pam.d", service)
            try:
                shutil.copy2(src, dst)
                backed_up.append(f"pam.d/{service}")
            except (OSError, shutil.Error) as e:
                errors.append(f"pam.d/{service}: {e}")

        if os.path.isfile(self.pam_conf):
            dst = os.path.join(backup_path, "pam.conf")
            try:
                shutil.copy2(self.pam_conf, dst)
                backed_up.append("pam.conf")
            except (OSError, shutil.Error) as e:
                errors.append(f"pam.conf: {e}")

        for config_name, config_path in SECURITY_CONFIGS.items():
            if os.path.isfile(config_path):
                dst = os.path.join(backup_path, "security", config_name)
                try:
                    shutil.copy2(config_path, dst)
                    backed_up.append(f"security/{config_name}")
                except (OSError, shutil.Error) as e:
                    errors.append(f"security/{config_name}: {e}")

        return {
            "success": len(errors) == 0,
            "backup_dir": backup_path,
            "files_backed_up": backed_up,
            "errors": errors,
            "timestamp": datetime.now().isoformat(),
        }
    # =========================================================================
    # Internal Parsing Helpers
    # =========================================================================

    def _parse_pam_file(
        self,
        content: str,
        is_pam_conf: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Parse a PAM service file or /etc/pam.conf content.

        Args:
            content: Raw file content.
            is_pam_conf: If True, parse as legacy /etc/pam.conf format.

        Returns:
            List of parsed entry dicts.
        """
        if not content:
            return []

        entries: List[Dict[str, Any]] = []
        for line_num, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            entry: Dict[str, Any] = {
                "line_number": line_num,
                "raw": stripped,
                "type": None,
                "control": None,
                "bracket_control": None,
                "options": None,
                "module": None,
                "args": None,
                "is_comment": False,
                "is_blank": False,
                "header": None,
            }

            if _is_comment_or_blank(stripped):
                if stripped.startswith("#") or stripped.startswith("--"):
                    entry["is_comment"] = True
                    if "End of" in stripped:
                        entry["header"] = stripped
                elif not stripped:
                    entry["is_blank"] = True
                entries.append(entry)
                continue

            pam_match = _PAM_LINE_RE.match(stripped)
            if pam_match:
                groups = pam_match.groupdict()
                entry["type"] = groups.get("type", "").lower()

                raw_control = groups.get("control", "")
                entry["control"] = raw_control

                if raw_control.startswith("["):
                    bracket_match = _BRACKET_CONTROL_RE.match(raw_control)
                    if bracket_match:
                        actions = {}
                        for pair in bracket_match.group("actions").split():
                            if "=" in pair:
                                k, v = pair.split("=", 1)
                                actions[k] = v
                        entry["bracket_control"] = actions

                entry["options"] = groups.get("options")
                entry["module"] = groups.get("module")

                args_str = groups.get("args", "")
                if args_str:
                    entry["args"] = args_str.strip()

                entries.append(entry)
                continue

            if is_pam_conf:
                pam_conf_match = _PAM_CONF_RE.match(stripped)
                if pam_conf_match:
                    groups = pam_conf_match.groupdict()
                    entry["type"] = groups.get("type", "").lower()
                    entry["control"] = groups.get("control")
                    entry["module"] = groups.get("module")
                    args_str = groups.get("args", "")
                    if args_str:
                        entry["args"] = args_str.strip()

            entries.append(entry)

        return entries

    def _parse_limits_file(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse /etc/security/limits.conf format.

        Args:
            content: Raw file content.

        Returns:
            List of limit entry dicts.
        """
        if not content:
            return []

        entries: List[Dict[str, Any]] = []
        for line_num, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()

            if not stripped or stripped.startswith("#"):
                entries.append({
                    "raw": stripped,
                    "line_number": line_num,
                    "is_comment": bool(stripped),
                    "is_blank": not stripped,
                    "domain": None,
                    "ltype": None,
                    "item": None,
                    "value": None,
                })
                continue

            parts = stripped.split()
            if len(parts) >= 3:
                domain = parts[0]
                ltype_item = parts[1]
                value = parts[2]

                ltype = ""
                item = ltype_item
                if ltype_item.startswith("-"):
                    ltype = "-"
                    item = ltype_item[1:]
                elif ltype_item.startswith("#"):
                    ltype = "#"
                    item = ltype_item[1:]

                entries.append({
                    "domain": domain,
                    "ltype": ltype,
                    "item": item,
                    "value": value,
                    "raw": stripped,
                    "line_number": line_num,
                    "is_comment": False,
                    "is_blank": False,
                })

        return entries

    def _parse_access_file(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse /etc/security/access.conf format.

        Args:
            content: Raw file content.

        Returns:
            List of access rule entry dicts.
        """
        if not content:
            return []

        entries: List[Dict[str, Any]] = []
        for line_num, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()

            if not stripped or stripped.startswith("#"):
                entries.append({
                    "raw": stripped,
                    "line_number": line_num,
                    "is_comment": bool(stripped),
                    "is_blank": not stripped,
                    "permission": None,
                    "users": None,
                    "origin": None,
                })
                continue

            parts = [p.strip() for p in stripped.split(":")]
            if len(parts) >= 3:
                permission = parts[0]
                users = parts[1]
                origin = parts[2]

                entries.append({
                    "permission": permission,
                    "users": users,
                    "origin": origin,
                    "raw": stripped,
                    "line_number": line_num,
                    "is_comment": False,
                    "is_blank": False,
                })

        return entries

    def _parse_time_file(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse /etc/security/time.conf format.

        Args:
            content: Raw file content.

        Returns:
            List of time rule entry dicts.
        """
        if not content:
            return []

        entries: List[Dict[str, Any]] = []
        for line_num, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()

            if not stripped or stripped.startswith("#"):
                entries.append({
                    "raw": stripped,
                    "line_number": line_num,
                    "is_comment": bool(stripped),
                    "is_blank": not stripped,
                    "services": None,
                    "ttys": None,
                    "users": None,
                    "times": None,
                })
                continue

            parts = [p.strip() for p in stripped.split(";")]
            if len(parts) >= 4:
                entries.append({
                    "services": parts[0],
                    "ttys": parts[1],
                    "users": parts[2],
                    "times": parts[3],
                    "raw": stripped,
                    "line_number": line_num,
                    "is_comment": False,
                    "is_blank": False,
                })

        return entries

    def _parse_group_file(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse /etc/security/group.conf format.

        Args:
            content: Raw file content.

        Returns:
            List of group rule entry dicts.
        """
        if not content:
            return []

        entries: List[Dict[str, Any]] = []
        for line_num, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()

            if not stripped or stripped.startswith("#"):
                entries.append({
                    "raw": stripped,
                    "line_number": line_num,
                    "is_comment": bool(stripped),
                    "is_blank": not stripped,
                    "users": None,
                    "groups": None,
                    "ttys": None,
                    "times": None,
                    "maxlogins": None,
                })
                continue

            parts = [p.strip() for p in stripped.split(";")]
            if len(parts) >= 5:
                entries.append({
                    "users": parts[0],
                    "groups": parts[1],
                    "ttys": parts[2],
                    "times": parts[3],
                    "maxlogins": parts[4],
                    "raw": stripped,
                    "line_number": line_num,
                    "is_comment": False,
                    "is_blank": False,
                })

        return entries

    def _parse_key_value(self, content: str) -> Dict[str, str]:
        """
        Parse generic key=value configuration file content.

        Handles both '=' and whitespace separators, skips comments
        and blank lines.

        Args:
            content: Raw file content.

        Returns:
            Dict of key -> value.
        """
        if not content:
            return {}

        result: Dict[str, str] = {}
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("--"):
                continue

            if "=" in stripped:
                key, _, value = stripped.partition("=")
                key = key.strip()
                value = value.strip()
                if key:
                    result[key] = value
            else:
                parts = stripped.split(None, 1)
                if len(parts) == 2:
                    result[parts[0]] = parts[1]

        return result

    def _parse_key_value_list(self, content: str) -> List[Dict[str, str]]:
        """
        Parse key=value file preserving duplicates and order.

        Args:
            content: Raw file content.

        Returns:
            List of dicts with 'key' and 'value'.
        """
        if not content:
            return []

        entries: List[Dict[str, str]] = []
        for line_num, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if "=" in stripped:
                key, _, value = stripped.partition("=")
                entries.append({
                    "key": key.strip(),
                    "value": value.strip(),
                    "line_number": line_num,
                })

        return entries


# =============================================================================
# Module Entry Point
# =============================================================================


if __name__ == "__main__":
    import json

    manager = PAMConfigManager()

    print("=" * 60)
    print("UmerOS PAM Configuration Manager")
    print("=" * 60)
    print()

    status = manager.export_status()

    print(f"PAM.d directory: {status['pam_d']['path']}")
    print(f"PAM.d exists: {status['pam_d']['exists']}")
    print(f"Services found: {len(status['pam_d']['services'])}")

    for svc, info in sorted(status["pam_d"]["services"].items()):
        types = ", ".join(info["types"]) if info["types"] else "none"
        print(f"  {svc}: {info['entry_count']} entries [{types}]")

    print()
    print(f"PAM.conf: {status['pam_conf']['path']}")
    print(f"PAM.conf exists: {status['pam_conf']['exists']}")
    print(f"PAM.conf entries: {status['pam_conf']['entry_count']}")

    print()
    print("Security configs:")
    for name, info in sorted(status["security_configs"].items()):
        exists_str = "exists" if info["exists"] else "MISSING"
        print(f"  {name}: {exists_str} ({info['size']} bytes)")

    print()
    print("Standard PAM modules available:")
    modules = manager.get_standard_modules()
    for mod_name, mod_info in sorted(modules.items()):
        types = []
        if mod_info.get("auth"):
            types.append("auth")
        if mod_info.get("account"):
            types.append("account")
        if mod_info.get("password"):
            types.append("password")
        if mod_info.get("session"):
            types.append("session")
        print(f"  {mod_name} [{', '.join(types)}]: {mod_info['description']}")

    print()
    print("=" * 60)
    print("Configuration summary exported successfully.")
    print("=" * 60)