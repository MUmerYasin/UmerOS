#!/usr/bin/env python3
"""
UmerOS Login Banner and Message Manager.

Manages /etc/issue, /etc/issue.net, /etc/motd, /etc/ssh/banner,
and related files for system login messages and post-login banners.
"""

import os
import re
import glob
import shutil
import socket
import platform
import subprocess
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
ISSUE: str = "/etc/issue"
ISSUE_NET: str = "/etc/issue.net"
MOTD: str = "/etc/motd"
SSH_BANNER: str = "/etc/ssh/banner"
PAM_MOTD: str = "/etc/pam.d/motd"
PROFILE_MOTD: str = "/etc/profile.d/motd.sh"

# ---------------------------------------------------------------------------
# Escape‑sequence catalogue (getty / agetty compatible)
# ---------------------------------------------------------------------------
ISSUE_ESCAPE_SEQUENCES: Dict[str, str] = {
    "\\l": "Current TTY name",
    "\\m": "Machine architecture (e.g. x86_64)",
    "\\n": "Hostname",
    "\\o": "Domain name",
    "\\r": "OS release (e.g. 1.0-generic)",
    "\\s": "OS name ",
    "\\t": "Current time (24‑hour clock)",
    "\\d": "Current date",
    "\\u": "Current logged‑in usernames",
    "\\U": "Number of logged‑in users",
    "\\v": "OS version string",
}


# ---------------------------------------------------------------------------
# Helper: safe file I/O with root‑aware error handling
# ---------------------------------------------------------------------------

def _read_file(path: str) -> str:
    """Read *path* and return its contents, raising ``FileNotFoundError``
    when the file does not exist and ``PermissionError`` on access issues."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {path}")
    except PermissionError:
        raise PermissionError(
            f"Permission denied reading {path}. Are you running as root?"
        )


def _write_file(path: str, content: str) -> None:
    """Atomically write *content* to *path*.

    A temporary file is written first then moved into place so readers
    never see a half‑written file.  Parent directories are created if
    they are missing.
    """
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)

    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(content)
        shutil.copystat(path, tmp) if os.path.exists(path) else None
        os.replace(tmp, path)
    except PermissionError:
        raise PermissionError(
            f"Permission denied writing {path}. Are you running as root?"
        )
    except Exception:
        # Clean up partial write
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _backup_file(path: str, backup_dir: str) -> Optional[str]:
    """Copy *path* into *backup_dir* and return the destination path."""
    if not os.path.exists(path):
        return None
    os.makedirs(backup_dir, exist_ok=True)
    dest = os.path.join(backup_dir, os.path.basename(path) + ".bak")
    shutil.copy2(path, dest)
    return dest


# ---------------------------------------------------------------------------
# Main manager class
# ---------------------------------------------------------------------------

class IssueMotdManager:
    """High‑level API for reading, writing and previewing login
    banners and message‑of‑the‑day files.

    Parameters
    ----------
    issue : str
        Path to the pre‑login issue file (default ``/etc/issue``).
    issue_net : str
        Path to the network pre‑login banner (default ``/etc/issue.net``).
    motd : str
        Path to the post‑login MOTD file (default ``/etc/motd``).
    ssh_banner : str
        Path to the SSH banner file (default ``/etc/ssh/banner``).
    """

    def __init__(
        self,
        issue: str = ISSUE,
        issue_net: str = ISSUE_NET,
        motd: str = MOTD,
        ssh_banner: str = SSH_BANNER,
    ) -> None:
        self.issue = issue
        self.issue_net = issue_net
        self.motd = motd
        self.ssh_banner = ssh_banner

    # ------------------------------------------------------------------
    # Escape‑sequence replacement engine
    # ------------------------------------------------------------------

    @staticmethod
    def _replace_escape_sequences(text: str) -> str:
        """Replace ``\\x`` getty escape sequences in *text* with live
        system values.

        Recognised codes are documented in :data:`ISSUE_ESCAPE_SEQUENCES`.
        """
        hostname = socket.gethostname()
        domain = ""
        try:
            domain = socket.getfqdn().replace(hostname, "").strip(".")
        except Exception:
            pass

        replacements: Dict[str, str] = {
            "\\l": _safe_tty_name(),
            "\\m": platform.machine(),
            "\\n": hostname,
            "\\o": domain,
            "\\r": platform.release(),
            "\\s": platform.system(),
            "\\t": datetime.datetime.now().strftime("%H:%M:%S"),
            "\\d": datetime.datetime.now().strftime("%a %b %d %Y"),
            "\\u": _current_users(),
            "\\U": str(_user_count()),
            "\\v": platform.version(),
        }

        result = text
        for code, value in replacements.items():
            # Use a literal‑string replacement so backslashes in the
            # replacement value are not re‑interpreted.
            result = result.replace(code, value)
        return result

    # ------------------------------------------------------------------
    # /etc/issue — pre‑login local banner
    # ------------------------------------------------------------------

    def get_issue(self) -> str:
        """Return the raw contents of ``/etc/issue``."""
        return _read_file(self.issue)

    def set_issue(self, text: str) -> Dict[str, Any]:
        """Write *text* to ``/etc/issue`` and return a status dict."""
        try:
            _write_file(self.issue, text)
            return {"success": True, "file": self.issue, "message": "Issue updated."}
        except Exception as exc:
            return {"success": False, "file": self.issue, "error": str(exc)}

    # ------------------------------------------------------------------
    # /etc/issue.net — pre‑login network banner (SSH, telnet)
    # ------------------------------------------------------------------

    def get_issue_net(self) -> str:
        """Return the raw contents of ``/etc/issue.net``."""
        return _read_file(self.issue_net)

    def set_issue_net(self, text: str) -> Dict[str, Any]:
        """Write *text* to ``/etc/issue.net`` and return a status dict."""
        try:
            _write_file(self.issue_net, text)
            return {"success": True, "file": self.issue_net, "message": "Issue.net updated."}
        except Exception as exc:
            return {"success": False, "file": self.issue_net, "error": str(exc)}

    # ------------------------------------------------------------------
    # /etc/motd — post‑login MOTD
    # ------------------------------------------------------------------

    def get_motd(self) -> str:
        """Return the raw contents of ``/etc/motd``."""
        return _read_file(self.motd)

    def set_motd(self, text: str) -> Dict[str, Any]:
        """Write *text* to ``/etc/motd`` and return a status dict."""
        try:
            _write_file(self.motd, text)
            return {"success": True, "file": self.motd, "message": "MOTD updated."}
        except Exception as exc:
            return {"success": False, "file": self.motd, "error": str(exc)}

    # ------------------------------------------------------------------
    # /etc/ssh/banner — SSH pre‑auth banner
    # ------------------------------------------------------------------

    def get_ssh_banner(self) -> str:
        """Return the raw contents of the SSH banner file."""
        return _read_file(self.ssh_banner)

    def set_ssh_banner(self, text: str) -> Dict[str, Any]:
        """Write *text* to the SSH banner file and return a status dict."""
        try:
            _write_file(self.ssh_banner, text)
            return {
                "success": True,
                "file": self.ssh_banner,
                "message": "SSH banner updated.",
            }
        except Exception as exc:
            return {"success": False, "file": self.ssh_banner, "error": str(exc)}

    # ------------------------------------------------------------------
    # PAM MOTD configuration
    # ------------------------------------------------------------------

    def get_pam_motd_config(self) -> List[str]:
        """Return each line of ``/etc/pam.d/motd`` as a list element."""
        try:
            content = _read_file(PAM_MOTD)
            return content.splitlines()
        except FileNotFoundError:
            return []

    def set_pam_motd_config(self, entries: List[str]) -> Dict[str, Any]:
        """Replace ``/etc/pam.d/motd`` with *entries* (one per line)."""
        content = "\n".join(entries) + "\n"
        try:
            _write_file(PAM_MOTD, content)
            return {
                "success": True,
                "file": PAM_MOTD,
                "message": "PAM MOTD config updated.",
            }
        except Exception as exc:
            return {"success": False, "file": PAM_MOTD, "error": str(exc)}

    # ------------------------------------------------------------------
    # /etc/profile.d/motd.sh — profile‑script MOTD
    # ------------------------------------------------------------------

    def get_profile_motd(self) -> str:
        """Return the raw contents of ``/etc/profile.d/motd.sh``."""
        return _read_file(PROFILE_MOTD)

    def set_profile_motd(self, script: str) -> Dict[str, Any]:
        """Write *script* to ``/etc/profile.d/motd.sh`` and return a
        status dict.
        """
        try:
            _write_file(PROFILE_MOTD, script)
            os.chmod(PROFILE_MOTD, 0o644)
            return {
                "success": True,
                "file": PROFILE_MOTD,
                "message": "Profile MOTD script updated.",
            }
        except Exception as exc:
            return {"success": False, "file": PROFILE_MOTD, "error": str(exc)}

    # ------------------------------------------------------------------
    # /etc/profile.d/ — MOTD script management
    # ------------------------------------------------------------------

    def list_motd_scripts(self) -> List[str]:
        """Return sorted basenames of every ``*.sh`` file under
        ``/etc/profile.d/``.
        """
        pattern = os.path.join("/etc/profile.d", "*.sh")
        scripts = glob.glob(pattern)
        return sorted(os.path.basename(s) for s in scripts)

    def add_motd_script(self, name: str, script: str) -> Dict[str, Any]:
        """Create ``/etc/profile.d/<name>`` with *script* contents."""
        dest = os.path.join("/etc/profile.d", name)
        try:
            _write_file(dest, script)
            os.chmod(dest, 0o644)
            return {
                "success": True,
                "file": dest,
                "message": f"Script '{name}' added.",
            }
        except Exception as exc:
            return {"success": False, "file": dest, "error": str(exc)}

    def remove_motd_script(self, name: str) -> Dict[str, Any]:
        """Remove ``/etc/profile.d/<name>`` if it exists."""
        target = os.path.join("/etc/profile.d", name)
        try:
            if os.path.exists(target):
                os.remove(target)
                return {
                    "success": True,
                    "file": target,
                    "message": f"Script '{name}' removed.",
                }
            return {
                "success": False,
                "file": target,
                "error": f"Script '{name}' not found.",
            }
        except Exception as exc:
            return {"success": False, "file": target, "error": str(exc)}

    # ------------------------------------------------------------------
    # Rendering and previewing
    # ------------------------------------------------------------------

    def render_issue(self, escape_sequences: bool = True) -> str:
        """Read ``/etc/issue`` and optionally replace escape sequences
        with live system values.

        Parameters
        ----------
        escape_sequences : bool
            When *True* (default) all ``\\x`` codes are expanded.
        """
        raw = self.get_issue()
        if escape_sequences:
            return self._replace_escape_sequences(raw)
        return raw

    def preview_issue(self, text: str) -> str:
        """Show what *text* would look like after escape‑sequence
        replacement — does **not** touch any files on disk.
        """
        return self._replace_escape_sequences(text)

    # ------------------------------------------------------------------
    # Information helpers
    # ------------------------------------------------------------------

    def get_issue_info(self) -> Dict[str, Any]:
        """Parse the current ``/etc/issue`` and return metadata about
        which escape sequences it contains.
        """
        raw = self.get_issue()
        found_codes: List[Dict[str, str]] = []
        for code, description in ISSUE_ESCAPE_SEQUENCES.items():
            # Escape the backslash for regex matching
            escaped = re.escape(code)
            if re.search(escaped, raw):
                found_codes.append({"code": code, "description": description})

        return {
            "file": self.issue,
            "raw_content": raw,
            "rendered": self._replace_escape_sequences(raw),
            "escape_sequences_found": found_codes,
            "available_escape_sequences": ISSUE_ESCAPE_SEQUENCES,
        }

    # ------------------------------------------------------------------
    # Standard templates
    # ------------------------------------------------------------------

    def get_standard_issue(self) -> str:
        """Return a standard Ubuntu/Debian ``/etc/issue`` template."""
        return (
            r"Ubuntu 24.04 LTS \n \l"
            "\n\n"
            "Welcome to UmerOS.\n\n"
        )

    def get_standard_issue_net(self) -> str:
        """Return a standard ``/etc/issue.net`` template for network
        banners.
        """
        return (
            "Welcome to UmerOS.\n"
            "Unauthorized access is prohibited.\n"
        )

    def get_standard_motd() -> str:
        """Return a standard ``/etc/motd`` template."""
        return (
            "\n"
            "  ███╗   ███╗██╗███╗   ███╗ █████╗ ██████╗  ██████╗ ███████╗██████╗ \n"
            "  ████╗ ████║██║████╗ ████║██╔══██╗██╔══██╗██╔═══██╗██╔════╝██╔══██╗\n"
            "  ██╔████╔██║██║██╔████╔██║███████║██████╔╝██║   ██║█████╗  ██████╔╝\n"
            "  ██║╚██╔╝██║██║██║╚██╔╝██║██╔══██║██╔══██╗██║   ██║██╔══╝  ██╔══██╗\n"
            "  ██║ ╚═╝ ██║██║██║ ╚═╝ ██║██║  ██║██║  ██║╚██████╔╝███████╗██║  ██║\n"
            "  ╚═╝     ╚═╝╚═╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝\n"
            "\n"
            "  UmerOS — Secure. Minimal. Yours.\n\n"
            "  System information as of {date}\n\n"
            "    {uptime}\n\n"
            "  Last login: {last_login}\n\n"
        )

    def get_ssh_banner_motd(self) -> str:
        """Return a standard SSH banner / MOTD combination."""
        return (
            "********************************************************************\n"
            "*  UmerOS Secure Shell — Authorized access only.                   *\n"
            "*  All sessions are monitored and logged.                          *\n"
            "********************************************************************\n\n"
        )

    # ------------------------------------------------------------------
    # Status and backup
    # ------------------------------------------------------------------

    def export_status(self) -> Dict[str, Any]:
        """Return a comprehensive snapshot of every managed file's
        current state.
        """
        status: Dict[str, Any] = {
            "files": {},
            "profile_scripts": self.list_motd_scripts(),
            "pam_motd_config": self.get_pam_motd_config(),
        }

        for name, path in [
            ("issue", self.issue),
            ("issue_net", self.issue_net),
            ("motd", self.motd),
            ("ssh_banner", self.ssh_banner),
            ("profile_motd", PROFILE_MOTD),
        ]:
            entry: Dict[str, Any] = {"path": path, "exists": os.path.exists(path)}
            if entry["exists"]:
                try:
                    content = _read_file(path)
                    entry["size_bytes"] = os.path.getsize(path)
                    entry["preview"] = content[:500]
                    if name == "issue":
                        entry["rendered"] = self._replace_escape_sequences(content)
                except Exception as exc:
                    entry["read_error"] = str(exc)
            status["files"][name] = entry

        return status

    def backup_all(self, backup_path: str) -> Dict[str, Any]:
        """Copy every managed file into *backup_path* and return a
        manifest of what was backed up.
        """
        os.makedirs(backup_path, exist_ok=True)
        backed_up: List[str] = []
        errors: List[str] = []

        targets = [
            self.issue,
            self.issue_net,
            self.motd,
            self.ssh_banner,
            PAM_MOTD,
            PROFILE_MOTD,
        ]

        # Also back up any profile.d scripts
        pattern = os.path.join("/etc/profile.d", "*.sh")
        targets.extend(glob.glob(pattern))

        for path in targets:
            try:
                result = _backup_file(path, backup_path)
                if result:
                    backed_up.append(result)
            except Exception as exc:
                errors.append(f"{path}: {exc}")

        return {
            "backup_path": backup_path,
            "files_backed_up": backed_up,
            "errors": errors,
            "success": len(errors) == 0,
        }


# ---------------------------------------------------------------------------
# Module‑level helpers used by _replace_escape_sequences
# ---------------------------------------------------------------------------

def _safe_tty_name() -> str:
    """Return the short TTY name (e.g. ``tty1``) or ``unknown``."""
    try:
        tty = os.ttyname(0)
        if tty:
            return os.path.basename(tty)
    except Exception:
        pass
    return "unknown"


def _current_users() -> str:
    """Return a comma‑separated string of currently logged‑in users."""
    try:
        output = subprocess.check_output(
            ["who"], stderr=subprocess.DEVNULL, text=True
        )
        names = sorted(set(line.split()[0] for line in output.splitlines() if line))
        return ", ".join(names) if names else "none"
    except Exception:
        return "unknown"


def _user_count() -> int:
    """Return the number of currently logged‑in users."""
    try:
        output = subprocess.check_output(
            ["who"], stderr=subprocess.DEVNULL, text=True
        )
        return len([line for line in output.splitlines() if line])
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Convenience: fill in dynamic fields in the standard MOTD template
# ---------------------------------------------------------------------------

def _format_standard_motd() -> str:
    """Return the standard MOTD with dynamic fields filled in."""
    motd_template = IssueMotdManager.get_standard_motd()
    now = datetime.datetime.now()

    try:
        uptime_raw = subprocess.check_output(
            ["uptime", "-p"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        uptime_raw = "uptime unavailable"

    try:
        last_login_raw = subprocess.check_output(
            ["last", "-1", "-w", "who"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        last_login_raw = "unknown"

    return motd_template.format(
        date=now.strftime("%a %b %d %H:%M:%S %Z %Y"),
        uptime=uptime_raw,
        last_login=last_login_raw,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _cli() -> None:
    """Minimal CLI for quick banner management from the terminal."""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        description="UmerOS Login Banner & MOTD Manager",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # -- status --
    sub.add_parser("status", help="Show current state of all managed files")

    # -- get ---
    get_p = sub.add_parser("get", help="Read a managed file")
    get_p.add_argument(
        "file",
        choices=["issue", "issue.net", "motd", "ssh", "pam", "profile"],
        help="Which file to read",
    )

    # -- set ---
    set_p = sub.add_parser("set", help="Write content to a managed file")
    set_p.add_argument(
        "file",
        choices=["issue", "issue.net", "motd", "ssh", "pam", "profile"],
    )
    set_p.add_argument("text", help="Content to write (or @filename to read from file)")

    # -- render --
    render_p = sub.add_parser("render", help="Render /etc/issue with escape sequences")
    render_p.add_argument("--raw", action="store_true", help="Show raw text")

    # -- preview --
    preview_p = sub.add_parser("preview", help="Preview text with escape sequences")
    preview_p.add_argument("text", help="Text containing \\x escape codes")

    # -- info --
    sub.add_parser("info", help="Show escape‑sequence metadata for /etc/issue")

    # -- backup --
    backup_p = sub.add_parser("backup", help="Back up all managed files")
    backup_p.add_argument("path", help="Directory to write backups into")

    # -- escape-codes --
    sub.add_parser("escape-codes", help="List available escape sequences")

    # -- templates --
    sub.add_parser("templates", help="Print standard templates")

    # -- scripts --
    scripts_p = sub.add_parser("scripts", help="Manage /etc/profile.d/*.sh")
    scripts_sub = scripts_p.add_subparsers(dest="scripts_cmd")
    scripts_sub.add_parser("list", help="List profile.d scripts")
    add_sp = scripts_sub.add_parser("add", help="Add a script")
    add_sp.add_argument("name", help="Script filename")
    add_sp.add_argument("content", help="Script body (or @filename)")
    rm_sp = scripts_sub.add_parser("remove", help="Remove a script")
    rm_sp.add_argument("name", help="Script filename")

    args = parser.parse_args()
    manager = IssueMotdManager()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    def _read_arg_or_file(value: str) -> str:
        if value.startswith("@"):
            with open(value[1:], "r", encoding="utf-8") as fh:
                return fh.read()
        return value

    if args.command == "status":
        print(json.dumps(manager.export_status(), indent=2))

    elif args.command == "get":
        dispatch = {
            "issue": manager.get_issue,
            "issue.net": manager.get_issue_net,
            "motd": manager.get_motd,
            "ssh": manager.get_ssh_banner,
            "pam": lambda: "\n".join(manager.get_pam_motd_config()),
            "profile": manager.get_profile_motd,
        }
        print(dispatch[args.file]())

    elif args.command == "set":
        content = _read_arg_or_file(args.text)
        dispatch = {
            "issue": manager.set_issue,
            "issue.net": manager.set_issue_net,
            "motd": manager.set_motd,
            "ssh": manager.set_ssh_banner,
            "pam": lambda c: manager.set_pam_motd_config(c.splitlines()),
            "profile": manager.set_profile_motd,
        }
        result = dispatch[args.file](content)
        print(json.dumps(result, indent=2))

    elif args.command == "render":
        if args.raw:
            print(manager.get_issue())
        else:
            print(manager.render_issue())

    elif args.command == "preview":
        print(manager.preview_issue(args.text))

    elif args.command == "info":
        print(json.dumps(manager.get_issue_info(), indent=2))

    elif args.command == "backup":
        print(json.dumps(manager.backup_all(args.path), indent=2))

    elif args.command == "escape-codes":
        print("Available escape sequences for /etc/issue:\n")
        for code, desc in ISSUE_ESCAPE_SEQUENCES.items():
            print(f"  {code:4s}  {desc}")

    elif args.command == "templates":
        print("=== Standard /etc/issue ===")
        print(manager.get_standard_issue())
        print("=== Standard /etc/issue.net ===")
        print(manager.get_standard_issue_net())
        print("=== Standard /etc/motd ===")
        print(_format_standard_motd())
        print("=== Standard SSH Banner ===")
        print(manager.get_ssh_banner_motd())

    elif args.command == "scripts":
        if args.scripts_cmd == "list" or args.scripts_cmd is None:
            for s in manager.list_motd_scripts():
                print(s)
        elif args.scripts_cmd == "add":
            body = _read_arg_or_file(args.content)
            print(json.dumps(manager.add_motd_script(args.name, body), indent=2))
        elif args.scripts_cmd == "remove":
            print(json.dumps(manager.remove_motd_script(args.name), indent=2))


if __name__ == "__main__":
    _cli()
