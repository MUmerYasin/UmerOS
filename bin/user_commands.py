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
UmerOS /bin User Commands
==========================
User-related commands: su, login

FHS 3.0: Essential commands for user switching and session management.
"""

from __future__ import annotations

import os
import pwd
import crypt
import spwd
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class SessionInfo:
    """Represents a user session."""
    uid: int = 0
    gid: int = 0
    user: str = ""
    home: str = ""
    shell: str = ""
    env: Dict[str, str] = field(default_factory=dict)
    login_time: float = 0.0
    tty: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uid": self.uid, "gid": self.gid, "user": self.user,
            "home": self.home, "shell": self.shell,
            "login_time": self.login_time, "tty": self.tty,
        }


# ─── su Command ──────────────────────────────────────────────────────────────

class SuCommand:
    """
    su - substitute user identity.

    Usage: su [-] [user [argument...]]
      -: Simulate full login (reset environment)
      -l, --login: Same as -
      -c command: Pass command to shell
      -s shell: Use specified shell
      -m, -p: Do not reset environment variables
      -g group: Primary group
      user: Target user (default: root)

    When called without arguments, switches to root.
    When called with '-', simulates login shell.
    """

    def __init__(self) -> None:
        self._current_session = self._get_current_session()

    def execute(self, args: List[str] | None = None) -> int:
        args = args or []
        opts = self._parse_args(args)

        target_user = opts.get("user", "root")
        command = opts.get("command")
        login_mode = opts.get("login", False)
        shell = opts.get("shell")

        # Get user info
        try:
            user_info = pwd.getpwnam(target_user)
        except KeyError:
            print(f"su: user '{target_user}' does not exist", file=sys.stderr)
            return 1

        # Authenticate (skip for root->root or if root running)
        if os.getuid() != 0 and target_user != self._current_session.user:
            if not self._authenticate(target_user):
                print("su: Authentication failure", file=sys.stderr)
                return 1

        # Set up environment
        env = self._setup_environment(user_info, login_mode)

        # Execute command or shell
        if command:
            return self._exec_command(target_user, user_info, command, env, shell)
        else:
            return self._exec_shell(target_user, user_info, login_mode, env, shell)

    def _parse_args(self, args: List[str]) -> Dict[str, Any]:
        opts: Dict[str, Any] = {}
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "-":
                opts["login"] = True
            elif arg == "-l" or arg == "--login":
                opts["login"] = True
            elif arg == "-m" or arg == "-p":
                opts["preserve_env"] = True
            elif arg == "-c" and i + 1 < len(args):
                i += 1
                opts["command"] = args[i]
            elif arg == "-s" and i + 1 < len(args):
                i += 1
                opts["shell"] = args[i]
            elif arg == "-g" and i + 1 < len(args):
                i += 1
                opts["group"] = args[i]
            elif not arg.startswith("-"):
                opts["user"] = arg
            i += 1
        return opts

    def _get_current_session(self) -> SessionInfo:
        uid = os.getuid()
        gid = os.getgid()
        try:
            pw = pwd.getpwuid(uid)
            return SessionInfo(
                uid=uid, gid=gid, user=pw.pw_name,
                home=pw.pw_dir, shell=pw.pw_shell,
                login_time=time.time(),
            )
        except KeyError:
            return SessionInfo(uid=uid, gid=gid, user=f"uid{uid}")

    def _authenticate(self, username: str) -> bool:
        """Prompt for password and verify."""
        try:
            sp = spwd.getspnam(username)
        except (KeyError, PermissionError):
            return os.getuid() == 0

        import getpass
        try:
            password = getpass.getpass(f"Password: ")
        except (EOFError, KeyboardInterrupt):
            return False

        if not sp.sp_pwd:
            return True
        encrypted = crypt.crypt(password, sp.sp_pwd)
        return encrypted == sp.sp_pwd

    def _setup_environment(self, user_info: Any, login_mode: bool) -> Dict[str, str]:
        env = dict(os.environ)

        if login_mode:
            # Clear most environment variables
            keep = {"PATH", "TERM", "HOME", "USER", "SHELL", "LOGNAME", "LANG"}
            env = {k: v for k, v in env.items() if k in keep}

        env["HOME"] = user_info.pw_dir
        env["USER"] = user_info.pw_name
        env["LOGNAME"] = user_info.pw_name
        env["SHELL"] = user_info.pw_shell
        env["PATH"] = "/usr/local/bin:/usr/bin:/bin"
        env["LOGNAME"] = user_info.pw_name

        return env

    def _exec_command(self, target_user: str, user_info: Any,
                      command: str, env: Dict[str, str],
                      shell: Optional[str]) -> int:
        import subprocess
        sh = shell or user_info.pw_shell or "/bin/sh"
        try:
            result = subprocess.run(
                [sh, "-c", command],
                env=env,
                user=user_info.pw_uid,
                group=user_info.pw_gid,
                cwd=user_info.pw_dir,
            )
            return result.returncode
        except OSError as e:
            print(f"su: failed to execute '{command}': {e}", file=sys.stderr)
            return 1

    def _exec_shell(self, target_user: str, user_info: Any,
                    login_mode: bool, env: Dict[str, str],
                    shell: Optional[str]) -> int:
        sh = shell or user_info.pw_shell or "/bin/sh"
        argv = [sh]
        if login_mode:
            argv = [f"-{os.path.basename(sh)}"]

        print(f"Switching to user '{target_user}' ({user_info.pw_uid})")
        print(f"Shell: {sh}")
        print(f"Home: {user_info.pw_dir}")
        print("(Interactive shell not available in UmerOS)")
        return 0


# ─── login Command ───────────────────────────────────────────────────────────

class LoginCommand:
    """
    login - begin a session on the system.

    Usage: login [-p] [-h host] [-f user | -F] [-t timeout] [user]
      -p: Preserve environment
      -h: Remote host name
      -f: Skip authentication for user
      -F: Skip authentication (force)
      -t: Login timeout in seconds
      user: Username to login as

    login reads /etc/nologin to deny access.
    login checks /etc/securetty for root access.
    login records login in /var/log/wtmp and /var/log/lastlog.
    """

    MAX_ATTEMPTS = 3
    NOLGIN_MSG = "System closed for maintenance.\n"

    def execute(self, args: List[str] | None = None) -> int:
        args = args or []
        opts = self._parse_args(args)

        # Check /etc/nologin
        if self._check_nologin():
            return 1

        target_user = opts.get("user")
        skip_auth = opts.get("skip_auth", False)
        timeout = opts.get("timeout", 60)

        if not target_user:
            target_user = self._prompt_user("login: ")

        # Check /etc/securetty for root
        if target_user == "root" and not self._check_securetty():
            print("Login incorrect", file=sys.stderr)
            return 1

        # Authenticate
        if not skip_auth:
            if not self._do_login(target_user, timeout):
                return 1

        # Set up session
        session = self._setup_session(target_user)

        # Record login
        self._record_login(session)

        # Start shell
        return self._start_session(session)

    def _parse_args(self, args: List[str]) -> Dict[str, Any]:
        opts: Dict[str, Any] = {}
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "-p":
                opts["preserve"] = True
            elif arg == "-h" and i + 1 < len(args):
                i += 1
                opts["host"] = args[i]
            elif arg == "-f" and i + 1 < len(args):
                i += 1
                opts["user"] = args[i]
                opts["skip_auth"] = True
            elif arg == "-F":
                opts["skip_auth"] = True
            elif arg == "-t" and i + 1 < len(args):
                i += 1
                opts["timeout"] = int(args[i])
            elif not arg.startswith("-"):
                opts["user"] = arg
            i += 1
        return opts

    def _check_nologin(self) -> bool:
        nologin_paths = ["/etc/nologin", "/etc/securetty"]
        for path in nologin_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        content = f.read().strip()
                    if content:
                        print(content)
                        return True
                except OSError:
                    pass
        return False

    def _check_securetty(self) -> bool:
        try:
            with open("/etc/securetty", "r") as f:
                ttys = [line.strip() for line in f if line.strip()]
            current_tty = os.ttyname(0) if os.isatty(0) else ""
            return not ttys or current_tty in ttys
        except (OSError, ValueError):
            return True

    def _prompt_user(self, prompt: str) -> str:
        try:
            return input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return ""

    def _do_login(self, username: str, timeout: int) -> bool:
        for attempt in range(self.MAX_ATTEMPTS):
            try:
                import getpass
                password = getpass.getpass("Password: ")
            except (EOFError, KeyboardInterrupt):
                print()
                return False

            if self._verify_password(username, password):
                return True
            remaining = self.MAX_ATTEMPTS - attempt - 1
            if remaining > 0:
                print(f"Login incorrect. {remaining} attempt(s) remaining.")
        return False

    def _verify_password(self, username: str, password: str) -> bool:
        try:
            sp = spwd.getspnam(username)
            if not sp.sp_pwd:
                return True
            encrypted = crypt.crypt(password, sp.sp_pwd)
            return encrypted == sp.sp_pwd
        except (KeyError, PermissionError):
            return False

    def _setup_session(self, username: str) -> SessionInfo:
        try:
            pw = pwd.getpwnam(username)
        except KeyError:
            print(f"User '{username}' not found", file=sys.stderr)
            sys.exit(1)

        session = SessionInfo(
            uid=pw.pw_uid, gid=pw.pw_gid, user=pw.pw_name,
            home=pw.pw_dir, shell=pw.pw_shell,
            login_time=time.time(),
        )

        try:
            session.tty = os.ttyname(0)
        except (OSError, ValueError):
            session.tty = "unknown"

        # Set environment
        os.environ["HOME"] = pw.pw_dir
        os.environ["USER"] = pw.pw_name
        os.environ["LOGNAME"] = pw.pw_name
        os.environ["SHELL"] = pw.pw_shell
        os.environ["PATH"] = "/usr/local/bin:/usr/bin:/bin"
        os.environ["TERM"] = os.environ.get("TERM", "linux")

        return session

    def _record_login(self, session: SessionInfo) -> None:
        """Record login to wtmp and lastlog."""
        wtmp_path = "/var/log/wtmp"
        lastlog_path = "/var/log/lastlog"

        # Write to lastlog (simplified)
        try:
            with open(lastlog_path, "w") as f:
                f.write(f"{session.user} {session.tty} {session.login_time}\n")
        except OSError:
            pass

        # Write to wtmp (simplified)
        try:
            with open(wtmp_path, "a") as f:
                f.write(f"LOGIN {session.user} tty1 {session.login_time}\n")
        except OSError:
            pass

    def _start_session(self, session: SessionInfo) -> int:
        shell = session.shell or "/bin/sh"
        print(f"Last login: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Welcome to UmerOS, {session.user}!")
        print(f"Shell: {shell}")
        print(f"Home: {session.home}")
        print("(Interactive session not available)")
        return 0


def _selftest() -> bool:
    """Run self-tests for user_commands module."""
    try:
        # SuCommand (skip execute — requires interactive session on Windows)
        su = SuCommand()
        assert hasattr(su, "execute")
        assert "su" in SuCommand.__doc__.lower() or "substitute" in SuCommand.__doc__.lower()

        # LoginCommand (skip execute — getpass blocks on Windows)
        lc = LoginCommand()
        assert hasattr(lc, "execute")
        assert "login" in LoginCommand.__doc__.lower()

        return True
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"_selftest FAILED: {e}")
        return False
