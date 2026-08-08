"""
UmerOS User Profile Manager
Per-user shell profile and environment variable management.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import json
import os


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
        home = str(self.home_path / username)
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
            lines.append(f'export {key}="{value}"')

        lines.append(f'\nexport PATH="{":".join(profile.path_dirs)}"')
        return "\n".join(lines) + "\n"

    def _generate_bashrc(self, profile: UserProfile) -> str:
        """Generate .bashrc content."""
        lines = ["# ~/.bashrc: non-login shell initialization\n"]
        lines.append("[[ $- != *i* ]] && return\n")
        lines.append("HISTSIZE=1000")
        lines.append("HISTFILESIZE=2000")
        lines.append("shopt -s histappend checkwinsize\n")

        for name, cmd in profile.aliases.items():
            lines.append(f"alias {name}='{cmd}'")

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
