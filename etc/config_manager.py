"""
Umer OS Configuration Manager
=============================
Manages system configuration files for /etc.

FHS 3.0 /etc requirements:
- Essential for system operation
- Configuration files must be in /etc (not /usr/etc or /var/etc)
- Static configuration files (not variable data)
- System-wide configuration

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import configparser
import json
import logging
import os
import re
import shutil
import stat
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

log = logging.getLogger("UmerOS.Etc.Config")


# ── Enums ─────────────────────────────────────────────────────────────────

class ConfigType(Enum):
    """Configuration file types."""
    INI = "ini"                  # INI format (key=value)
    JSON = "json"                # JSON format
    YAML = "yaml"                # YAML format
    TOML = "toml"                # TOML format
    SHELL = "shell"              # Shell variables (KEY=VALUE)
    TEXT = "text"                # Plain text
    BINARY = "binary"            # Binary configuration


class ConfigStatus(Enum):
    """Configuration file status."""
    VALID = "valid"
    INVALID = "invalid"
    MISSING = "missing"
    READONLY = "readonly"
    MODIFIED = "modified"
    BACKUP = "backup"


class ConfigPermission(Enum):
    """Configuration file permission levels."""
    ROOT_ONLY = 0o600           # Read/write root only
    ROOT_READ = 0o644           # Read all, write root
    GROUP_READ = 0o664          # Read/write root/group, read all
    WORLD_READ = 0o666          # Read/write all
    EXECUTABLE = 0o755          # Executable (scripts)


# ── Data Classes ──────────────────────────────────────────────────────────

@dataclass
class ConfigFile:
    """Represents a configuration file in /etc."""
    name: str
    path: str
    config_type: ConfigType
    status: ConfigStatus = ConfigStatus.VALID
    permissions: int = 0o644
    owner: str = "root"
    group: str = "root"
    size_bytes: int = 0
    timestamp: float = 0.0
    description: str = ""
    backup_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize derived fields."""
        if os.path.isfile(self.path):
            self.size_bytes = os.path.getsize(self.path)
            self.timestamp = os.path.getmtime(self.path)


@dataclass
class ConfigSection:
    """Represents a section in an INI-style configuration."""
    name: str
    options: Dict[str, str] = field(default_factory=dict)
    comments: List[str] = field(default_factory=list)


@dataclass
class UserEntry:
    """Represents an entry in /etc/passwd."""
    username: str
    password: str = "x"         # 'x' means shadow password
    uid: int = 0
    gid: int = 0
    gecos: str = ""             # Full name and other info
    home_dir: str = "/home/username"
    shell: str = "/bin/bash"


@dataclass
class GroupEntry:
    """Represents an entry in /etc/group."""
    group_name: str
    password: str = "x"
    gid: int = 0
    members: List[str] = field(default_factory=list)


@dataclass
class HostEntry:
    """Represents an entry in /etc/hosts."""
    ip_address: str
    hostname: str
    aliases: List[str] = field(default_factory=list)


# ── Configuration Manager ─────────────────────────────────────────────────

class ConfigManager:
    """
    Manager for /etc configuration files.

    Responsibilities:
    - Track configuration files
    - Parse/write INI, JSON, Shell config files
    - Manage user/group files (passwd, group)
    - Manage network configuration (hosts, resolv.conf)
    - Backup and restore configuration
    - FHS compliance checking
    """

    # Essential /etc files
    ESSENTIAL_FILES = [
        "passwd",
        "group",
        "shadow",
        "gshadow",
        "hosts",
        "resolv.conf",
        "hostname",
        "timezone",
        "fstab",
        "mtab",
        "profile",
        "shells",
        " shells",
        "os-release",
        "machine-id",
        "host.conf",
        "nsswitch.conf",
        "sudoers",
    ]

    def __init__(self, etc_path: str = "/etc"):
        """
        Initialize configuration manager.

        Args:
            etc_path: Path to /etc directory
        """
        self.etc_path = Path(etc_path)
        self.config_files: Dict[str, ConfigFile] = {}
        self.user_entries: List[UserEntry] = []
        self.group_entries: List[GroupEntry] = []
        self.host_entries: List[HostEntry] = []
        self._initialized = False

        log.info("ConfigManager initialized for path: %s", etc_path)

    def initialize(self) -> bool:
        """
        Initialize the manager and scan for existing configuration files.

        Returns:
            True if initialization successful
        """
        try:
            # Ensure /etc directory exists
            self.etc_path.mkdir(parents=True, exist_ok=True)

            # Create essential files if they don't exist
            self._create_essential_files()

            # Scan for existing configuration files
            self._scan_config_files()

            self._initialized = True
            log.info("ConfigManager initialization complete. Found %d config files.", len(self.config_files))
            return True

        except Exception as exc:
            log.error("ConfigManager initialization failed: %s", exc)
            return False

    def _create_essential_files(self) -> None:
        """Create essential /etc files if they don't exist."""
        essential_files = {
            "passwd": self._create_default_passwd,
            "group": self._create_default_group,
            "hosts": self._create_default_hosts,
            "hostname": self._create_default_hostname,
            "timezone": self._create_default_timezone,
            "os-release": self._create_default_os_release,
            "machine-id": self._create_default_machine_id,
            "shells": self._create_default_shells,
            "fstab": self._create_default_fstab,
            "resolv.conf": self._create_default_resolv_conf,
            "profile": self._create_default_profile,
        }

        for filename, creator in essential_files.items():
            filepath = self.etc_path / filename
            if not filepath.exists():
                creator(filepath)
                log.debug("Created essential /etc file: %s", filename)

    def _create_default_passwd(self, filepath: Path) -> None:
        """Create default /etc/passwd file."""
        content = """# /etc/passwd - User account information
# Format: username:password:uid:gid:gecos:home_dir:shell
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
bin:x:2:2:bin:/bin:/usr/sbin/nologin
sys:x:3:3:sys:/dev:/usr/sbin/nologin
sync:x:4:65534:sync:/bin:/bin/sync
games:x:5:60:games:/usr/games:/usr/sbin/nologin
man:x:6:12:man:/var/cache/man:/usr/sbin/nologin
lp:x:7:7:lp:/var/spool/lpd:/usr/sbin/nologin
mail:x:8:8:mail:/var/mail:/usr/sbin/nologin
news:x:9:9:news:/var/spool/news:/usr/sbin/nologin
uucp:x:10:10:uucp:/var/spool/uucp:/usr/sbin/nologin
proxy:x:13:13:proxy:/bin:/usr/sbin/nologin
www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin
backup:x:34:34:backup:/var/backups:/usr/sbin/nologin
list:x:38:38:Mailing List Manager:/var/list:/usr/sbin/nologin
irc:x:39:39:ircd:/var/run/ircd:/usr/sbin/nologin
gnats:x:41:41:Gnats Bug-Reporting System (admin):/var/lib/gnats:/usr/sbin/nologin
nobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin
systemd-network:x:100:102::/run/systemd:/usr/sbin/nologin
systemd-resolve:x:101:103::/run/systemd:/usr/sbin/nologin
systemd-timesync:x:102:104::/run/systemd:/usr/sbin/nologin
messagebus:x:103:106::/run/dbus:/usr/sbin/nologin
syslog:x:104:108::/home/syslog:/usr/sbin/nologin
_apt:x:105:65534::/nonexistent:/usr/sbin/nologin
tss:x:106:111:TPM software stack,,,:/var/lib/tpm:/bin/false
uuidd:x:107:112::/run/uuidd:/usr/sbin/nologin
tcpdump:x:108:113::/nonexistent:/usr/sbin/nologin
usbmux:x:109:46:usbmuxd,,,:/var/lib/usbmuxd:/usr/sbin/nologin
rtkit:x:110:117:RealtimeKit,,,:/proc:/bin/false
dnsmasq:x:111:65534:dnsmasq,,,:/var/lib/misc:/usr/sbin/nologin
colord:x:112:118:colord colour management,,,:/var/lib/colord:/bin/false
speech-dispatcher:bin:x:113:29:Speech Dispatcher,,,:/run/speech-dispatcher:/usr/sbin/nologin
avahi-autoipd:x:114:119:Avahi autoipd,,,:/var/lib/avahi-autoipd:/usr/sbin/nologin
avahi:x:115:120:Avahi mDNS/DNS-SD daemon,,,:/var/run/avahi-daemon:/usr/sbin/nologin
cups-pk-helper:x:116:121:CUPS-PK-Helper,,,:/org/cups/cups_pk_helper:/usr/sbin/nologin
sshd:x:117:65534::/run/sshd:/usr/sbin/nologin
pulse:x:118:122:PulseAudio daemon,,,:/var/run/pulse:/usr/sbin/nologin
statd:x:119:65534::/var/lib/nfs:/usr/sbin/nologin
gdm:x:120:124:Gnome Display Manager:/var/lib/gdm3:/bin/false
tcpdump:x:108:113::/nonexistent:/usr/sbin/nologin
umer:x:1000:1000:Umer OS User:/home/umer:/bin/bash
"""
        filepath.write_text(content, encoding="utf-8")

    def _create_default_group(self, filepath: Path) -> None:
        """Create default /etc/group file."""
        content = """# /etc/group - Group information
# Format: group_name:password:gid:members
root:x:0:
daemon:x:1:
bin:x:2:
sys:x:3:
adm:x:4:syslog,umer
tty:x:5:
disk:x:6:
lp:x:7:
mail:x:8:
news:x:9:
uucp:x:10:
proxy:x:13:
www-data:x:33:
backup:x:34:
list:x:38:
irc:x:39:
gnats:x:41:
nogroup:x:65534:
systemd-network:x:100:
systemd-resolve:x:101:
systemd-timesync:x:102:
messagebus:x:106:
syslog:x:108:
_tss:x:111:
usbmux:x:46:
rtkit:x:117:
dnsmasq:x:113:
colord:x:118:
speech-dispatcher:x:29:
avahi-autoipd:x:119:
avahi:x:120:
cups-pk-helper:x:121:
sshd:x:117:
pulse:x:122:
stap-devpc:x:123:
gdm:x:124:
umer:x:1000:
"""
        filepath.write_text(content, encoding="utf-8")

    def _create_default_hosts(self, filepath: Path) -> None:
        """Create default /etc/hosts file."""
        content = """# /etc/hosts - Host name database
# Format: IP_ADDRESS canonical_name [aliases...]
127.0.0.1       localhost
127.0.1.1       umeros

# IPv6
::1             localhost ip6-localhost ip6-loopback
ff02::1         ip6-allnodes
ff02::2         ip6-allrouters
"""
        filepath.write_text(content, encoding="utf-8")

    def _create_default_hostname(self, filepath: Path) -> None:
        """Create default /etc/hostname file."""
        filepath.write_text("umeros", encoding="utf-8")

    def _create_default_timezone(self, filepath: Path) -> None:
        """Create default /etc/timezone file."""
        filepath.write_text("UTC", encoding="utf-8")

    def _create_default_os_release(self, filepath: Path) -> None:
        """Create default /etc/os-release file."""
        content = """# /etc/os-release - OS identification
NAME="UmerOS"
VERSION="1.0.0"
ID=umeros
ID_LIKE=debian
VERSION_ID="1.0.0"
PRETTY_NAME="UmerOS 1.0.0"
HOME_URL="https://umeros.org"
BUG_REPORT_URL="https://bugs.umeros.org"
"""
        filepath.write_text(content, encoding="utf-8")

    def _create_default_machine_id(self, filepath: Path) -> None:
        """Create default /etc/machine-id file."""
        # Generate a random machine ID
        import uuid
        machine_id = uuid.uuid4().hex
        filepath.write_text(machine_id + "\n", encoding="utf-8")

    def _create_default_shells(self, filepath: Path) -> None:
        """Create default /etc/shells file."""
        content = """# /etc/shells - Valid login shells
/bin/sh
/bin/bash
/bin/rbash
/bin/dash
/bin/zsh
"""
        filepath.write_text(content, encoding="utf-8")

    def _create_default_fstab(self, filepath: Path) -> None:
        """Create default /etc/fstab file."""
        content = """# /etc/fstab - Static file system information
# <file system> <mount point> <type> <options> <dump> <pass>
# / was on /dev/sda1 during installation
/dev/sda1               /               ext4    errors=remount-ro 0       1
# /boot was on /dev/sda2 during installation
/dev/sda2               /boot           ext4    defaults        0       2
# swap was on /dev/sda3 during installation
/dev/sda3               none            swap    sw              0       0
"""
        filepath.write_text(content, encoding="utf-8")

    def _create_default_resolv_conf(self, filepath: Path) -> None:
        """Create default /etc/resolv.conf file."""
        content = """# /etc/resolv.conf - DNS resolver configuration
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
search .
"""
        filepath.write_text(content, encoding="utf-8")

    def _create_default_profile(self, filepath: Path) -> None:
        """Create default /etc/profile file."""
        content = """# /etc/profile - System-wide environment and startup programs
# ~/.profile: executed by the command interpreter for login shells.

# set PATH so it includes user's private bin if it exists
if [ -d "$HOME/bin" ] ; then
    PATH="$HOME/bin:$PATH"
fi

# set PATH so it includes user's private bin if it exists
if [ -d "$HOME/.local/bin" ] ; then
    PATH="$HOME/.local/bin:$PATH"
fi

# Enable color support of ls and also add handy aliases
if [ -x /usr/bin/dircolors ]; then
    test -r ~/.dircolors && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"
    alias ls='ls --color=auto'
    #alias dir='dir --color=auto'
    #alias vdir='vdir --color=auto'
    alias grep='grep --color=auto'
    alias fgrep='fgrep --color=auto'
    alias egrep='egrep --color=auto'
fi
"""
        filepath.write_text(content, encoding="utf-8")

    def _scan_config_files(self) -> None:
        """Scan /etc for existing configuration files."""
        for config_file in self.etc_path.iterdir():
            if config_file.is_file():
                self._register_existing_config(config_file)

    def _register_existing_config(self, config_path: Path) -> None:
        """Register an existing configuration file."""
        name = config_path.name

        # Determine config type from extension
        config_type = self._detect_config_type(name)

        config_file = ConfigFile(
            name=name,
            path=str(config_path),
            config_type=config_type,
            status=ConfigStatus.VALID,
        )

        self.config_files[name] = config_file

    def _detect_config_type(self, filename: str) -> ConfigType:
        """Detect configuration type from filename."""
        ext_map = {
            ".json": ConfigType.JSON,
            ".yaml": ConfigType.YAML,
            ".yml": ConfigType.YAML,
            ".toml": ConfigType.TOML,
            ".ini": ConfigType.INI,
            ".conf": ConfigType.INI,
            ".cfg": ConfigType.INI,
        }

        for ext, config_type in ext_map.items():
            if filename.endswith(ext):
                return config_type

        # Check for shell config files
        shell_files = ["profile", "bashrc", "bash_profile", "bash_logout", "zshrc", "zprofile"]
        if filename in shell_files or filename.startswith("."):
            return ConfigType.SHELL

        return ConfigType.TEXT

    # ── File Management ───────────────────────────────────────────────────

    def get_config_file(self, name: str) -> Optional[ConfigFile]:
        """Get a configuration file by name."""
        return self.config_files.get(name)

    def list_config_files(self) -> List[ConfigFile]:
        """List all configuration files."""
        return list(self.config_files.values())

    def read_file(self, name: str) -> Optional[str]:
        """
        Read content of a configuration file.

        Args:
            name: Configuration file name

        Returns:
            File content or None if not found
        """
        config = self.config_files.get(name)
        if not config or not os.path.isfile(config.path):
            return None

        try:
            with open(config.path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as exc:
            log.error("Failed to read config file %s: %s", name, exc)
            return None

    def write_file(
        self,
        name: str,
        content: str,
        backup: bool = True,
    ) -> bool:
        """
        Write content to a configuration file.

        Args:
            name: Configuration file name
            content: Content to write
            backup: Whether to backup before writing

        Returns:
            True if write successful
        """
        config = self.config_files.get(name)
        if not config:
            log.error("Config file not found: %s", name)
            return False

        try:
            # Create backup if requested
            if backup and os.path.isfile(config.path):
                backup_path = config.path + ".backup"
                shutil.copy2(config.path, backup_path)
                config.backup_path = backup_path
                log.debug("Created backup: %s", backup_path)

            # Write the file
            with open(config.path, "w", encoding="utf-8") as f:
                f.write(content)

            # Update metadata
            config.size_bytes = os.path.getsize(config.path)
            config.timestamp = os.path.getmtime(config.path)
            config.status = ConfigStatus.MODIFIED

            log.info("Wrote config file: %s", name)
            return True

        except Exception as exc:
            log.error("Failed to write config file %s: %s", name, exc)
            return False

    # ── INI File Handling ─────────────────────────────────────────────────

    def read_ini(self, name: str) -> Optional[configparser.ConfigParser]:
        """
        Read an INI-style configuration file.

        Args:
            name: Configuration file name

        Returns:
            ConfigParser object or None
        """
        config = self.config_files.get(name)
        if not config or not os.path.isfile(config.path):
            return None

        try:
            parser = configparser.ConfigParser()
            parser.read(config.path, encoding="utf-8")
            return parser
        except Exception as exc:
            log.error("Failed to read INI file %s: %s", name, exc)
            return None

    def write_ini(
        self,
        name: str,
        sections: Dict[str, Dict[str, str]],
        backup: bool = True,
    ) -> bool:
        """
        Write an INI-style configuration file.

        Args:
            name: Configuration file name
            sections: Dictionary of sections with their options
            backup: Whether to backup before writing

        Returns:
            True if write successful
        """
        config = self.config_files.get(name)
        if not config:
            log.error("Config file not found: %s", name)
            return False

        try:
            parser = configparser.ConfigParser()
            for section, options in sections.items():
                parser[section] = options

            # Create backup if requested
            if backup and os.path.isfile(config.path):
                backup_path = config.path + ".backup"
                shutil.copy2(config.path, backup_path)
                config.backup_path = backup_path

            # Write the file
            with open(config.path, "w", encoding="utf-8") as f:
                parser.write(f)

            # Update metadata
            config.size_bytes = os.path.getsize(config.path)
            config.timestamp = os.path.getmtime(config.path)
            config.status = ConfigStatus.MODIFIED

            log.info("Wrote INI file: %s", name)
            return True

        except Exception as exc:
            log.error("Failed to write INI file %s: %s", name, exc)
            return False

    # ── JSON File Handling ────────────────────────────────────────────────

    def read_json(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Read a JSON configuration file.

        Args:
            name: Configuration file name

        Returns:
            JSON data or None
        """
        config = self.config_files.get(name)
        if not config or not os.path.isfile(config.path):
            return None

        try:
            with open(config.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            log.error("Failed to read JSON file %s: %s", name, exc)
            return None

    def write_json(
        self,
        name: str,
        data: Dict[str, Any],
        backup: bool = True,
        indent: int = 4,
    ) -> bool:
        """
        Write a JSON configuration file.

        Args:
            name: Configuration file name
            data: JSON data to write
            backup: Whether to backup before writing
            indent: JSON indentation level

        Returns:
            True if write successful
        """
        config = self.config_files.get(name)
        if not config:
            log.error("Config file not found: %s", name)
            return False

        try:
            # Create backup if requested
            if backup and os.path.isfile(config.path):
                backup_path = config.path + ".backup"
                shutil.copy2(config.path, backup_path)
                config.backup_path = backup_path

            # Write the file
            with open(config.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)

            # Update metadata
            config.size_bytes = os.path.getsize(config.path)
            config.timestamp = os.path.getmtime(config.path)
            config.status = ConfigStatus.MODIFIED

            log.info("Wrote JSON file: %s", name)
            return True

        except Exception as exc:
            log.error("Failed to write JSON file %s: %s", name, exc)
            return False

    # ── Shell Config Handling ─────────────────────────────────────────────

    def read_shell_config(self, name: str) -> Dict[str, str]:
        """
        Read a shell configuration file (KEY=VALUE format).

        Args:
            name: Configuration file name

        Returns:
            Dictionary of key-value pairs
        """
        content = self.read_file(name)
        if not content:
            return {}

        config = {}
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                config[key] = value

        return config

    # ── User/Group Management ─────────────────────────────────────────────

    def parse_passwd(self) -> List[UserEntry]:
        """
        Parse /etc/passwd file.

        Returns:
            List of UserEntry objects
        """
        content = self.read_file("passwd")
        if not content:
            return []

        self.user_entries = []
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split(":")
                if len(parts) >= 7:
                    try:
                        uid = int(parts[2])
                        gid = int(parts[3])
                    except ValueError:
                        continue
                    entry = UserEntry(
                        username=parts[0],
                        password=parts[1],
                        uid=uid,
                        gid=gid,
                        gecos=parts[4],
                        home_dir=parts[5],
                        shell=parts[6],
                    )
                    self.user_entries.append(entry)

        return self.user_entries

    def parse_group(self) -> List[GroupEntry]:
        """
        Parse /etc/group file.

        Returns:
            List of GroupEntry objects
        """
        content = self.read_file("group")
        if not content:
            return []

        self.group_entries = []
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split(":")
                if len(parts) >= 4:
                    try:
                        gid = int(parts[2])
                    except ValueError:
                        gid = -1
                    members = [m for m in parts[3].split(",") if m] if parts[3] else []
                    entry = GroupEntry(
                        group_name=parts[0],
                        password=parts[1],
                        gid=gid,
                        members=members,
                    )
                    self.group_entries.append(entry)

        return self.group_entries

    # ── Network Configuration ─────────────────────────────────────────────

    def parse_hosts(self) -> List[HostEntry]:
        """
        Parse /etc/hosts file.

        Returns:
            List of HostEntry objects
        """
        content = self.read_file("hosts")
        if not content:
            return []

        self.host_entries = []
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split()
                if len(parts) >= 2:
                    entry = HostEntry(
                        ip_address=parts[0],
                        hostname=parts[1],
                        aliases=parts[2:] if len(parts) > 2 else [],
                    )
                    self.host_entries.append(entry)

        return self.host_entries

    def get_nameservers(self) -> List[str]:
        """
        Get nameservers from /etc/resolv.conf.

        Returns:
            List of nameserver IP addresses
        """
        content = self.read_file("resolv.conf")
        if not content:
            return []

        nameservers = []
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("nameserver"):
                parts = line.split()
                if len(parts) >= 2:
                    nameservers.append(parts[1])

        return nameservers

    # ── Backup and Restore ────────────────────────────────────────────────

    def backup_config(self, name: str) -> Optional[str]:
        """
        Create a backup of a configuration file.

        Args:
            name: Configuration file name

        Returns:
            Backup file path or None
        """
        config = self.config_files.get(name)
        if not config or not os.path.isfile(config.path):
            return None

        try:
            timestamp = int(time.time())
            backup_path = f"{config.path}.backup.{timestamp}"
            shutil.copy2(config.path, backup_path)
            config.backup_path = backup_path

            log.info("Created backup: %s", backup_path)
            return backup_path

        except Exception as exc:
            log.error("Failed to backup config file %s: %s", name, exc)
            return None

    def restore_config(self, name: str, backup_path: str) -> bool:
        """
        Restore a configuration file from backup.

        Args:
            name: Configuration file name
            backup_path: Path to backup file

        Returns:
            True if restore successful
        """
        config = self.config_files.get(name)
        if not config:
            return False

        if not os.path.isfile(backup_path):
            log.error("Backup file not found: %s", backup_path)
            return False

        try:
            shutil.copy2(backup_path, config.path)
            config.size_bytes = os.path.getsize(config.path)
            config.timestamp = os.path.getmtime(config.path)
            config.status = ConfigStatus.VALID

            log.info("Restored config file %s from %s", name, backup_path)
            return True

        except Exception as exc:
            log.error("Failed to restore config file %s: %s", name, exc)
            return False

    # ── FHS Compliance ────────────────────────────────────────────────────

    def check_fhs_compliance(self) -> Dict[str, Any]:
        """
        Check FHS compliance for /etc.

        Returns:
            Dictionary with compliance results
        """
        results = {
            "compliant": True,
            "issues": [],
            "warnings": [],
            "missing_essential": [],
        }

        # Check for essential files
        for essential in self.ESSENTIAL_FILES:
            if essential not in self.config_files:
                results["missing_essential"].append(essential)
                results["warnings"].append(f"Missing essential /etc file: {essential}")

        # Check for files that shouldn't be in /etc
        for name in self.config_files:
            if name.endswith((".py", ".pyc", ".so", ".o")):
                results["issues"].append(f"Binary file in /etc: {name}")
                results["compliant"] = False

        return results

    # ── Utilities ─────────────────────────────────────────────────────────

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all configuration files."""
        return {
            "total_files": len(self.config_files),
            "files_by_type": {
                config_type.value: len([
                    f for f in self.config_files.values()
                    if f.config_type == config_type
                ])
                for config_type in ConfigType
            },
            "total_user_entries": len(self.user_entries),
            "total_group_entries": len(self.group_entries),
            "total_host_entries": len(self.host_entries),
        }


# ── Singleton ─────────────────────────────────────────────────────────────

_config_manager_instance: Optional[ConfigManager] = None


def get_config_manager(etc_path: str = "/etc") -> ConfigManager:
    """
    Get or create the singleton ConfigManager instance.

    Args:
        etc_path: Path to /etc directory

    Returns:
        ConfigManager instance
    """
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = ConfigManager(etc_path)
        _config_manager_instance.initialize()
    return _config_manager_instance


def reset_config_manager() -> None:
    """Reset the singleton ConfigManager instance."""
    global _config_manager_instance
    _config_manager_instance = None
