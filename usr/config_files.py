"""
UmerOS Configuration Files Manager
===================================
Configuration file management under /usr/etc.

The /usr/etc directory holds system-wide default configuration files
that serve as fallbacks or templates. This module provides parsing,
validation, and management of configuration files in various formats:
  - /usr/etc/sysctl.conf    : Kernel parameter defaults
  - /usr/etc/fstab          : Filesystem table defaults
  - /usr/etc/profile        : Shell profile defaults
  - /usr/etc/bashrc         : Bash configuration defaults
  - /usr/etc/resolv.conf    : DNS resolver defaults
  - /usr/etc/hosts          : Host file defaults
  - /usr/etc/sudoers        : Sudo configuration defaults
"""

from __future__ import annotations

import os
import re
import json
import stat
from dataclasses import dataclass, field
from enum import IntEnum
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)


# ============================================================================
# Constants
# ============================================================================

DEFAULT_CONFIG_ROOT: str = "/usr/etc"

CONFIG_FILE_PATTERNS: Dict[str, str] = {
    "sysctl": "sysctl.conf",
    "fstab": "fstab",
    "profile": "profile",
    "bashrc": "bashrc",
    "resolv": "resolv.conf",
    "hosts": "hosts",
    "sudoers": "sudoers",
}

CONFIG_PERMISSIONS: int = 0o644
SENSITIVE_PERMISSIONS: int = 0o640


# ============================================================================
# Enums
# ============================================================================

class ConfigFormat(IntEnum):
    """Supported configuration file formats."""
    KEY_VALUE = 0
    INI = 1
    SYSCTL = 2
    SHELL_EXPORT = 3
    JSON = 4
    YAML = 5
    TOML = 6
    CUSTOM = 7


class ConfigStatus(IntEnum):
    """Status of a configuration file."""
    UNKNOWN = 0
    UNLOADED = 1
    LOADED = 2
    VALID = 3
    INVALID = 4
    OVERRIDDEN = 5
    DEFAULT = 6
    MODIFIED = 7


class SecurityLevel(IntEnum):
    """Security sensitivity levels for config files."""
    PUBLIC = 0
    INTERNAL = 1
    PRIVATE = 2
    SENSITIVE = 3


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class ConfigEntry:
    """A single configuration entry (key-value pair)."""
    key: str = ""
    value: str = ""
    line_number: int = 0
    is_commented: bool = False
    source_file: str = ""
    section: str = ""

    def uncommented_value(self) -> str:
        """Get the value with leading '#' removed."""
        return self.value.lstrip("#").strip()

    def is_active(self) -> bool:
        """Check if this entry is active (not commented out)."""
        return not self.is_commented and self.value.strip() != ""


@dataclass
class ConfigSection:
    """A section within an INI-style config file."""
    name: str = ""
    entries: List[ConfigEntry] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0

    def get_entry(self, key: str) -> Optional[ConfigEntry]:
        """Get an entry by key."""
        for entry in self.entries:
            if entry.key == key:
                return entry
        return None

    def get_value(self, key: str) -> Optional[str]:
        """Get value for a key."""
        entry = self.get_entry(key)
        return entry.value if entry else None


@dataclass
class ConfigFile:
    """Represents a configuration file."""
    name: str = ""
    path: str = ""
    format: ConfigFormat = ConfigFormat.KEY_VALUE
    status: ConfigStatus = ConfigStatus.UNKNOWN
    security_level: SecurityLevel = SecurityLevel.PUBLIC
    entries: List[ConfigEntry] = field(default_factory=list)
    sections: List[ConfigSection] = field(default_factory=list)
    raw_content: str = ""
    size_bytes: int = 0
    modified_at: float = 0.0
    file_mode: int = 0

    def get_value(self, key: str, section: str = "") -> Optional[str]:
        """Get a configuration value by key."""
        for entry in self.entries:
            if entry.key == key:
                if section and entry.section != section:
                    continue
                if entry.is_active():
                    return entry.value
        return None

    def set_value(self, key: str, value: str, section: str = "") -> None:
        """Set a configuration value."""
        for entry in self.entries:
            if entry.key == key and entry.section == section:
                entry.value = value
                entry.is_commented = False
                self.status = ConfigStatus.MODIFIED
                return
        self.entries.append(ConfigEntry(
            key=key,
            value=value,
            section=section,
        ))
        self.status = ConfigStatus.MODIFIED

    def get_all_keys(self, section: str = "") -> List[str]:
        """Get all keys, optionally filtered by section."""
        keys: List[str] = []
        for entry in self.entries:
            if section and entry.section != section:
                continue
            if entry.is_active():
                keys.append(entry.key)
        return keys

    def get_entries(self, section: str = "") -> List[ConfigEntry]:
        """Get all entries, optionally filtered by section."""
        if section:
            return [e for e in self.entries if e.section == section]
        return list(self.entries)

    def remove_entry(self, key: str, section: str = "") -> bool:
        """Remove an entry by key."""
        for i, entry in enumerate(self.entries):
            if entry.key == key and entry.section == section:
                self.entries.pop(i)
                self.status = ConfigStatus.MODIFIED
                return True
        return False

    def entry_count(self) -> int:
        """Count active entries."""
        return sum(1 for e in self.entries if e.is_active())


# ============================================================================
# Configuration File Parser
# ============================================================================

class ConfigParser:
    """Parser for various configuration file formats."""

    RE_KEY_VALUE = re.compile(
        r"^\s*#?\s*(\S+?)\s*=\s*(.*?)\s*$"
    )
    RE_SYSCTL = re.compile(
        r"^\s*#?\s*([\w.]+)\s*=\s*(.*)"
    )
    RE_INI_SECTION = re.compile(
        r"^\s*\[(\w+)\]\s*$"
    )
    RE_INI_ENTRY = re.compile(
        r"^\s*#?\s*(\S+?)\s*=\s*(.*?)\s*$"
    )
    RE_SHELL_EXPORT = re.compile(
        r"^\s*(?:export\s+)?(\w+?)=(.*)"
    )
    RE_COMMENT = re.compile(
        r"^\s*[#;]"
    )
    RE_HOSTS_LINE = re.compile(
        r"^\s*([\d.:a-fA-F]+)\s+(.*)"
    )
    RE_SUDOERS_ENTRY = re.compile(
        r"^\s*(\S+)\s+(.*)"
    )

    def detect_format(self, filepath: str) -> ConfigFormat:
        """Detect configuration file format from path."""
        basename = os.path.basename(filepath).lower()
        ext = os.path.splitext(basename)[1].lower()
        if ext == ".json":
            return ConfigFormat.JSON
        if ext in (".yaml", ".yml"):
            return ConfigFormat.YAML
        if ext == ".toml":
            return ConfigFormat.TOML
        if "sysctl" in basename:
            return ConfigFormat.SYSCTL
        if "sudoers" in basename:
            return ConfigFormat.KEY_VALUE
        if basename in ("profile", "bashrc", "zshrc", "bash_profile"):
            return ConfigFormat.SHELL_EXPORT
        if basename == "resolv.conf":
            return ConfigFormat.KEY_VALUE
        if basename == "hosts":
            return ConfigFormat.KEY_VALUE
        if basename == "fstab":
            return ConfigFormat.KEY_VALUE
        return ConfigFormat.KEY_VALUE

    def parse(self, filepath: str) -> Optional[ConfigFile]:
        """Parse a configuration file."""
        config_format = self.detect_format(filepath)
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except (OSError, IOError):
            return None

        config = ConfigFile(
            name=os.path.basename(filepath),
            path=filepath,
            format=config_format,
            raw_content=content,
        )

        try:
            st = os.stat(filepath)
            config.size_bytes = st.st_size
            config.modified_at = st.st_mtime
            config.file_mode = st.st_mode
        except OSError:
            pass

        if config_format == ConfigFormat.JSON:
            config.entries = self._parse_json(content, filepath)
        elif config_format == ConfigFormat.SYSCTL:
            config.entries = self._parse_sysctl(content, filepath)
        elif config_format == ConfigFormat.SHELL_EXPORT:
            config.entries = self._parse_shell(content, filepath)
        else:
            config.entries = self._parse_key_value(content, filepath)

        config.status = ConfigStatus.LOADED
        return config

    def _parse_json(self, content: str, source: str) -> List[ConfigEntry]:
        """Parse JSON configuration."""
        entries: List[ConfigEntry] = []
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                entries = self._flatten_dict(data, source)
        except json.JSONDecodeError:
            pass
        return entries

    def _flatten_dict(
        self, data: Dict[str, Any], source: str, prefix: str = ""
    ) -> List[ConfigEntry]:
        """Flatten a nested dict into entries."""
        entries: List[ConfigEntry] = []
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                entries.extend(
                    self._flatten_dict(value, source, full_key)
                )
            else:
                entries.append(ConfigEntry(
                    key=full_key,
                    value=str(value),
                    source_file=source,
                ))
        return entries

    def _parse_sysctl(self, content: str, source: str) -> List[ConfigEntry]:
        """Parse sysctl-style configuration."""
        entries: List[ConfigEntry] = []
        for i, line in enumerate(content.split("\n"), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = self.RE_SYSCTL.match(line)
            if m:
                entries.append(ConfigEntry(
                    key=m.group(1),
                    value=m.group(2).strip(),
                    line_number=i,
                    source_file=source,
                ))
        return entries

    def _parse_shell(self, content: str, source: str) -> List[ConfigEntry]:
        """Parse shell-style (export) configuration."""
        entries: List[ConfigEntry] = []
        for i, line in enumerate(content.split("\n"), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = self.RE_SHELL_EXPORT.match(line)
            if m:
                entries.append(ConfigEntry(
                    key=m.group(1),
                    value=m.group(2).strip().strip('"').strip("'"),
                    line_number=i,
                    source_file=source,
                ))
        return entries

    def _parse_key_value(self, content: str, source: str) -> List[ConfigEntry]:
        """Parse generic key=value configuration."""
        entries: List[ConfigEntry] = []
        current_section = ""
        for i, line in enumerate(content.split("\n"), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith(";"):
                if stripped.startswith("#"):
                    continue
                continue
            m = self.RE_INI_SECTION.match(stripped)
            if m:
                current_section = m.group(1)
                continue
            m = self.RE_KEY_VALUE.match(stripped)
            if m:
                entries.append(ConfigEntry(
                    key=m.group(1),
                    value=m.group(2),
                    line_number=i,
                    source_file=source,
                    section=current_section,
                    is_commented=stripped.startswith("#"),
                ))
        return entries

    def parse_string(self, content: str, fmt: ConfigFormat = ConfigFormat.KEY_VALUE) -> ConfigFile:
        """Parse configuration from a string."""
        config = ConfigFile(
            format=fmt,
            raw_content=content,
        )
        if fmt == ConfigFormat.JSON:
            config.entries = self._parse_json(content, "<string>")
        elif fmt == ConfigFormat.SYSCTL:
            config.entries = self._parse_sysctl(content, "<string>")
        elif fmt == ConfigFormat.SHELL_EXPORT:
            config.entries = self._parse_shell(content, "<string>")
        else:
            config.entries = self._parse_key_value(content, "<string>")
        config.status = ConfigStatus.LOADED
        return config


# ============================================================================
# Configuration File Manager
# ============================================================================

class ConfigFilesManager:
    """
    Manages configuration files under /usr/etc.

    Provides loading, validation, and management of system-wide
    default configuration files.
    """

    def __init__(self, config_root: str = DEFAULT_CONFIG_ROOT) -> None:
        self._config_root = config_root
        self._configs: Dict[str, ConfigFile] = {}
        self._parser = ConfigParser()
        self._overrides: Dict[str, str] = {}

    @property
    def config_root(self) -> str:
        """Get the config root directory."""
        return self._config_root

    # -- Loading --

    def load_config(self, relative_path: str) -> Optional[ConfigFile]:
        """Load a configuration file by relative path."""
        full_path = os.path.join(self._config_root, relative_path)
        config = self._parser.parse(full_path)
        if config:
            self._configs[full_path] = config
        return config

    def load_all(self) -> int:
        """Load all known configuration files."""
        count = 0
        for name in CONFIG_FILE_PATTERNS.values():
            if self.load_config(name):
                count += 1
        return count

    def scan_directory(self, subpath: str = "") -> int:
        """Scan a directory for configuration files."""
        dirpath = os.path.join(self._config_root, subpath)
        if not os.path.isdir(dirpath):
            return 0
        count = 0
        try:
            for entry in os.scandir(dirpath):
                if entry.is_file():
                    config = self._parser.parse(entry.path)
                    if config:
                        self._configs[entry.path] = config
                        count += 1
        except (OSError, PermissionError):
            pass
        return count

    # -- Access --

    def get_config(self, path: str) -> Optional[ConfigFile]:
        """Get a loaded configuration by full path."""
        return self._configs.get(path)

    def find_config(self, name: str) -> List[ConfigFile]:
        """Find configurations by filename."""
        results: List[ConfigFile] = []
        for config in self._configs.values():
            if config.name == name:
                results.append(config)
        return results

    def list_configs(self) -> List[ConfigFile]:
        """List all loaded configurations."""
        return list(self._configs.values())

    def get_value(self, path: str, key: str) -> Optional[str]:
        """Get a value from a loaded configuration."""
        config = self._configs.get(path)
        if config is None:
            return None
        return config.get_value(key)

    # -- Modification --

    def set_value(self, path: str, key: str, value: str) -> bool:
        """Set a value in a loaded configuration."""
        config = self._configs.get(path)
        if config is None:
            return False
        config.set_value(key, value)
        self._overrides[f"{path}:{key}"] = value
        return True

    def save_config(self, path: str) -> bool:
        """Save a configuration file to disk."""
        config = self._configs.get(path)
        if config is None:
            return False
        lines: List[str] = []
        current_section = ""
        for entry in config.entries:
            if entry.section and entry.section != current_section:
                current_section = entry.section
                lines.append(f"[{current_section}]")
            if entry.is_commented:
                lines.append(f"# {entry.key} = {entry.value}")
            else:
                lines.append(f"{entry.key} = {entry.value}")
        content = "\n".join(lines) + "\n"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            config.raw_content = content
            config.status = ConfigStatus.VALID
            return True
        except (OSError, IOError):
            return False

    # -- Validation --

    def validate_config(self, path: str) -> Tuple[bool, List[str]]:
        """Validate a configuration file."""
        config = self._configs.get(path)
        if config is None:
            return False, ["Configuration not loaded"]
        errors: List[str] = []
        keys_seen: Set[str] = set()
        for entry in config.entries:
            if not entry.key:
                errors.append(f"Line {entry.line_number}: Empty key")
                continue
            full_key = f"{entry.section}:{entry.key}"
            if full_key in keys_seen:
                errors.append(
                    f"Line {entry.line_number}: Duplicate key '{entry.key}'"
                )
            keys_seen.add(full_key)
            if not entry.value and entry.is_active():
                errors.append(
                    f"Line {entry.line_number}: Empty value for '{entry.key}'"
                )
        config.status = ConfigStatus.VALID if not errors else ConfigStatus.INVALID
        return len(errors) == 0, errors

    def check_permissions(self, path: str) -> Tuple[bool, List[str]]:
        """Check file permissions for security."""
        warnings: List[str] = []
        config = self._configs.get(path)
        if config is None:
            return False, ["Configuration not loaded"]
        try:
            st = os.stat(path)
            mode = st.st_mode
            if mode & stat.S_IROTH and mode & stat.S_IWOTH:
                warnings.append("File is world-readable and world-writable")
            if mode & stat.S_IWGRP:
                warnings.append("File is group-writable")
            basename = os.path.basename(path)
            if basename == "sudoers" and mode & stat.S_IROTH:
                warnings.append("Sudoers file should not be world-readable")
        except OSError:
            pass
        return len(warnings) == 0, warnings

    # -- Utility --

    def config_count(self) -> int:
        """Get total number of loaded configurations."""
        return len(self._configs)

    def get_override_count(self) -> int:
        """Get number of overridden values."""
        return len(self._overrides)

    def clear(self) -> None:
        """Clear all loaded configurations."""
        self._configs.clear()
        self._overrides.clear()


# ============================================================================
# Global Singleton
# ============================================================================

_global_config_files: Optional[ConfigFilesManager] = None


def get_global_config_files() -> ConfigFilesManager:
    """Get or create the global ConfigFilesManager instance."""
    global _global_config_files
    if _global_config_files is None:
        _global_config_files = ConfigFilesManager()
    return _global_config_files
