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
UmerOS User Profile Manager
Per-user shell profile and environment variable management.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import json
import os
import re
import logging

# [FIX H84] Fail-closed path-traversal containment (CWE-22): every caller-supplied
# name (username / message id / subdir / filename) is validated as a single safe
# path segment -- or a contained multi-segment join -- before any home path is built.
try:
    from core.path_guard import PathTraversalError, safe_child, safe_join
except Exception:  # pragma: no cover - standalone fallback
    import os as _os
    import sys as _sys
    _proj = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if _proj not in _sys.path:
        _sys.path.insert(0, _proj)
    from core.path_guard import PathTraversalError, safe_child, safe_join

# [FIX H86] Shell-injection guard: `.profile` / `.bashrc` are *sourced* by the
# login shell, so any user-controlled text interpolated into them is code
# execution in the user's context. Identifiers (env keys, alias names) are
# validated against the POSIX name grammar; every value / command is emitted as
# a single-quoted shell literal so no metacharacter can break out.
log = logging.getLogger("UmerOS.Home.UserProfile")

_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ALIAS_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _shell_quote(text: str) -> str:
    """Return ``text`` as a POSIX single-quoted shell literal.

    The only byte that cannot appear inside single quotes is ``'`` itself, so
    the canonical ``'\''`` idiom closes/reopens the quote around it. The result
    is inert: no expansion, command substitution, or newline breakout.
    """
    return "'" + str(text).replace("'", "'\\''") + "'"


@dataclass
class UserProfile:
    """User-specific environment and profile data."""
    username: str
    uid: int = 1000
    gid: int = 1000
    home: str = ""
    shell: str = "/bin/bash"
    env_vars: Dict[str, str] = field(default_factory=dict)
    path_dirs: List[str] = field(default_factory=list)
    aliases: Dict[str, str] = field(default_factory=dict)
    groups: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.home:
            self.home = f"/home/{self.username}"


class UserProfileManager:
    """Manages per-user profiles and environment."""

    DEFAULT_ENV = {
        "HOME": "",
        "USER": "",
        "LOGNAME": "",
        "SHELL": "/bin/bash",
        "LANG": "en_US.UTF-8",
        "TERM": "xterm-256color",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "XDG_DATA_HOME": "~/.local/share",
        "XDG_CONFIG_HOME": "~/.config",
        "XDG_STATE_HOME": "~/.local/state",
        "XDG_CACHE_HOME": "~/.cache",
    }

    def __init__(self, home_path: str = "/home", etc_path: str = "/etc"):
        self.home_path = Path(home_path)
        self.etc_path = Path(etc_path)
        self.profiles: Dict[str, UserProfile] = {}

    def create_profile(self, username: str, uid: int = 1000,
                       gid: int = 1000, shell: str = "/bin/bash") -> UserProfile:
        """Create a new user profile."""
        home = str(safe_child(self.home_path, username))
        profile = UserProfile(
            username=username,
            uid=uid,
            gid=gid,
            home=home,
            shell=shell,
            env_vars={
                **self.DEFAULT_ENV,
                "HOME": home,
                "USER": username,
                "LOGNAME": username,
                "SHELL": shell,
                "PATH": f"{home}/.local/bin:{home}/bin:/usr/local/bin:/usr/bin:/bin",
            },
            path_dirs=[
                f"{home}/.local/bin",
                f"{home}/bin",
                "/usr/local/bin",
                "/usr/bin",
                "/bin",
            ],
            aliases={
                "ls": "ls --color=auto",
                "ll": "ls -la",
                "la": "ls -A",
                "l": "ls -CF",
                "rm": "rm -i",
                "cp": "cp -i",
                "mv": "mv -i",
            },
            groups=[username, "users"],
        )
        self.profiles[username] = profile
        self._write_profile_files(profile)
        return profile

    def get_profile(self, username: str) -> Optional[UserProfile]:
        """Get a user's profile."""
        return self.profiles.get(username)

    def set_env(self, username: str, key: str, value: str) -> bool:
        """Set an environment variable for a user."""
        profile = self.profiles.get(username)
        if not profile:
            return False
        # [FIX H86] env keys are emitted unquoted as `export KEY=...`;
        # reject anything that is not a valid shell identifier.
        if not _ENV_KEY_RE.match(key or ""):
            raise ValueError(f"Invalid environment variable name: {key!r}")
        profile.env_vars[key] = value
        self._write_profile_files(profile)
        return True

    def get_env(self, username: str, key: str) -> Optional[str]:
        """Get an environment variable for a user."""
        profile = self.profiles.get(username)
        if not profile:
            return None
        return profile.env_vars.get(key)

    def add_path(self, username: str, directory: str) -> bool:
        """Add a directory to a user's PATH."""
        profile = self.profiles.get(username)
        if not profile:
            return False
        if directory not in profile.path_dirs:
            profile.path_dirs.append(directory)
            profile.env_vars["PATH"] = ":".join(profile.path_dirs)
            self._write_profile_files(profile)
        return True

    def add_alias(self, username: str, name: str, command: str) -> bool:
        """Add an alias for a user."""
        profile = self.profiles.get(username)
        if not profile:
            return False
        # [FIX H86] alias names are emitted unquoted as `alias NAME=...`;
        # reject anything that is not a valid shell identifier.
        if not _ALIAS_NAME_RE.match(name or ""):
            raise ValueError(f"Invalid alias name: {name!r}")
        profile.aliases[name] = command
        self._write_profile_files(profile)
        return True

    def remove_alias(self, username: str, name: str) -> bool:
        """Remove an alias for a user."""
        profile = self.profiles.get(username)
        if not profile:
            return False
        if name in profile.aliases:
            del profile.aliases[name]
            self._write_profile_files(profile)
            return True
        return False

    def _write_profile_files(self, profile: UserProfile) -> None:
        """Write profile files to user's home directory."""
        user_home = Path(profile.home)
        user_home.mkdir(parents=True, exist_ok=True)

        # Write .profile
        profile_content = self._generate_profile(profile)
        (user_home / ".profile").write_text(profile_content, encoding='utf-8')

        # Write .bashrc
        bashrc_content = self._generate_bashrc(profile)
        (user_home / ".bashrc").write_text(bashrc_content, encoding='utf-8')

    def _generate_profile(self, profile: UserProfile) -> str:
        """Generate .profile content."""
        lines = ["# ~/.profile: login shell initialization\n"]
        lines.append("umask 022\n")

        for key, value in profile.env_vars.items():
            # [FIX H86] never interpolate raw text: validate the identifier and
            # single-quote the value so it cannot break out of the assignment.
            if not _ENV_KEY_RE.match(key or ""):
                log.warning("Skipping invalid env var name %r for %s", key, profile.username)
                continue
            lines.append(f"export {key}={_shell_quote(value)}")

        lines.append(f"\nexport PATH={_shell_quote(':'.join(profile.path_dirs))}")
        return "\n".join(lines) + "\n"

    def _generate_bashrc(self, profile: UserProfile) -> str:
        """Generate .bashrc content."""
        lines = ["# ~/.bashrc: non-login shell initialization\n"]
        lines.append("[[ $- != *i* ]] && return\n")
        lines.append("HISTSIZE=1000")
        lines.append("HISTFILESIZE=2000")
        lines.append("shopt -s histappend checkwinsize\n")

        for name, cmd in profile.aliases.items():
            # [FIX H86] validate the alias name, single-quote the command body.
            if not _ALIAS_NAME_RE.match(name or ""):
                log.warning("Skipping invalid alias name %r for %s", name, profile.username)
                continue
            lines.append(f"alias {name}={_shell_quote(cmd)}")

        return "\n".join(lines) + "\n"

    def load_from_passwd(self, passwd_path: str = "/etc/passwd") -> None:
        """Load profiles from /etc/passwd."""
        path = Path(passwd_path)
        if not path.exists():
            return
        for line in path.read_text().splitlines():
            if line.startswith('#') or ':' not in line:
                continue
            parts = line.split(':')
            if len(parts) >= 7:
                username = parts[0]
                uid = int(parts[2]) if parts[2].isdigit() else 1000
                gid = int(parts[3]) if parts[3].isdigit() else 1000
                home = parts[5]
                shell = parts[6]
                if not username.startswith(('!', '+')):
                    self.create_profile(username, uid, gid, shell)

    def export_profile(self, username: str) -> Dict:
        """Export a user's profile as dict."""
        profile = self.profiles.get(username)
        if not profile:
            return {}
        return {
            "username": profile.username,
            "uid": profile.uid,
            "gid": profile.gid,
            "home": profile.home,
            "shell": profile.shell,
            "env_vars": profile.env_vars,
            "path_dirs": profile.path_dirs,
            "aliases": profile.aliases,
            "groups": profile.groups,
        }
