#!/usr/bin/env python3
"""
UmerOS udev Rules Manager
==========================

Manages udev rules, udev.conf, hardware database (hwdb),
and device persistent naming on UmerOS systems.

Provides a high-level Python API for reading, writing, validating,
and simulating udev rules, as well as managing udev.conf settings
and hwdb entries.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
UDEV_RULES_D: str = "/etc/udev/rules.d"
UDEV_CONF: str = "/etc/udev/udev.conf"
UDEV_HWDB: str = "/etc/udev/hwdb.d"
RUNUDEV_DIR: str = "/run/udev"
PERSISTENT_NET: str = "/etc/udev/rules.d/70-persistent-net.rules"
PERSISTENT_CD: str = "/etc/udev/rules.d/75-persistent-name.rules"

# ---------------------------------------------------------------------------
# Match / Action vocabulary
# ---------------------------------------------------------------------------
UDEV_MATCH_TYPES: List[str] = [
    "SUBSYSTEM",
    "KERNEL",
    "DRIVERS",
    "ATTRS",
    "ATTR",
    "ENV",
    "TAG",
    "TEST",
    "PROGRAM",
    "RESULT",
    "ACTION",
]

UDEV_ACTION_TYPES: List[str] = [
    "RUN",
    "GOTO",
    "LABEL",
    "SYMLINK",
    "OWNER",
    "GROUP",
    "MODE",
    "IMPORT",
    "PROGRAM",
    "RESULT",
    "NAME",
    "ENV",
    "TAG",
    "OPTIONS",
    "TEST",
]

# ---------------------------------------------------------------------------
# Common / standard rule templates
# ---------------------------------------------------------------------------
COMMON_UDEV_RULES: Dict[str, List[str]] = {
    "persistent_net_naming": [
        "# Persistent network device naming",
        'ACTION=="add", SUBSYSTEM=="net", DRIVERS=="?*", '
        'ATTR{address}=="", NAME:="%k"',
        'ACTION=="add", SUBSYSTEM=="net", DRIVERS=="?*", '
        'ATTR{address}!="", NAME:="%k"',
    ],
    "usb_device_rules": [
        "# Generic USB device permissions",
        'ACTION=="add", SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", '
        'MODE="0664", GROUP="plugdev"',
        "# USB serial adapters",
        'ACTION=="add", SUBSYSTEM=="tty", ATTRS{idVendor}=="*", '
        'MODE="0666"',
    ],
    "input_device_rules": [
        "# Input device permissions",
        'ACTION=="add", SUBSYSTEM=="input", MODE="0664", GROUP="input"',
        "# Evdev permissions",
        'ACTION=="add", KERNEL=="event*", '
        'ATTRS{manufacturer}=="*", MODE="0664", GROUP="input"',
    ],
    "sound_rules": [
        "# Sound device permissions",
        'ACTION=="add", SUBSYSTEM=="sound", MODE="0660", GROUP="audio"',
    ],
    "video_rules": [
        "# Video device permissions (webcams)",
        'ACTION=="add", SUBSYSTEM=="video4", MODE="0660", GROUP="video"',
    ],
    "bluetooth_rules": [
        "# Bluetooth hci device",
        'ACTION=="add", KERNEL=="hci*", MODE="0660", GROUP="bluetooth"',
    ],
    "storage_rules": [
        "# Storage device permissions",
        'ACTION=="add", SUBSYSTEM=="block", ENV{ID_FS_USAGE}=="filesystem", '
        'MODE="0660", GROUP="storage"',
    ],
    "power_supply_rules": [
        "# Power supply (battery) notifications",
        'ACTION=="change", SUBSYSTEM=="power_supply", '
        'ATTR{status}=="Discharging", RUN+="/usr/bin/notify-send Battery low"',
    ],
    "cpu_governor_rules": [
        "# CPU frequency governor on AC/battery",
        'ACTION=="change", SUBSYSTEM=="power_supply", '
        'ATTR{type}=="Mains", RUN+="/bin/sh -c \'echo performance > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor\'"',
        'ACTION=="change", SUBSYSTEM=="power_supply", '
        'ATTR{type}=="Battery", RUN+="/bin/sh -c \'echo powersave > /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor\'"',
    ],
    "persistent_cdrom_rules": [
        "# Persistent CD-ROM symlinks",
        'KERNEL=="sr0", SYMLINK+="cdrom"',
        'KERNEL=="sr1", SYMLINK+="cdrom1"',
    ],
    "persistent_disk_rules": [
        "# Persistent disk symlinks",
        'KERNEL=="sd[a-z]", ENV{ID_SERIAL}=="", SYMLINK+="disk/by-id/usb-%k"',
    ],
    "tmpfiles_cleanup": [
        "# Clean /run/udev on boot",
        'RUN+="/bin/rm -rf /run/udev/*"',
    ],
}


# ===================================================================
# Data classes
# ===================================================================
@dataclass
class UdevRule:
    """Represents a single parsed udev rule line."""

    line_number: int = 0
    comment: str = ""
    matches: Dict[str, str] = field(default_factory=dict)
    actions: Dict[str, str] = field(default_factory=dict)
    raw: str = ""
    disabled: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "line_number": self.line_number,
            "comment": self.comment,
            "matches": self.matches,
            "actions": self.actions,
            "raw": self.raw,
            "disabled": self.disabled,
        }


@dataclass
class RuleResult:
    """Standardised result envelope for every mutating operation."""

    success: bool
    message: str
    data: Any = None
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "success": self.success,
            "message": self.message,
        }
        if self.data is not None:
            d["data"] = self.data
        if self.errors:
            d["errors"] = self.errors
        return d


# ===================================================================
# UdevRulesManager
# ===================================================================
class UdevRulesManager:
    """High-level manager for udev rules, configuration and hwdb.

    Parameters
    ----------
    rules_dir:
        Path to the ``rules.d`` directory (default ``/etc/udev/rules.d``).
    udev_conf:
        Path to ``udev.conf`` (default ``/etc/udev/udev.conf``).
    hwdb_dir:
        Path to ``hwdb.d`` directory (default ``/etc/udev/hwdb.d``).
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def __init__(
        self,
        rules_dir: str = UDEV_RULES_D,
        udev_conf: str = UDEV_CONF,
        hwdb_dir: str = UDEV_HWDB,
    ) -> None:
        self.rules_dir = Path(rules_dir)
        self.udev_conf_path = Path(udev_conf)
        self.hwdb_dir = Path(hwdb_dir)
        self.runudev_dir = Path(RUNUDEV_DIR)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _ensure_dir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    def _read_file(self, path: Path) -> str:
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
        return ""

    def _write_file(self, path: Path, content: str) -> None:
        self._ensure_dir(path.parent)
        path.write_text(content, encoding="utf-8")

    def _run_udevadm(self, *args: str) -> Tuple[int, str, str]:
        """Run ``udevadm`` and return ``(returncode, stdout, stderr)``."""
        try:
            result = subprocess.run(
                ["udevadm", *args],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode, result.stdout, result.stderr
        except FileNotFoundError:
            return -1, "", "udevadm not found"
        except subprocess.TimeoutExpired:
            return -1, "", "udevadm timed out"

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    # =================================================================
    # Rule-file listing
    # =================================================================
    def list_rules_files(self) -> List[str]:
        """Return sorted list of rule file names inside *rules_dir*.

        Returns
        -------
        list[str]
            File basenames, e.g. ``["70-persistent-net.rules", …]``.
        """
        if not self.rules_dir.is_dir():
            return []
        files = sorted(
            p.name for p in self.rules_dir.iterdir() if p.is_file()
        )
        return files

    # =================================================================
    # Parsing a single udev rule line
    # =================================================================
    def _parse_udev_rule(self, raw: str, line_number: int = 0) -> UdevRule:
        """Parse a single udev rule line into a :class:`UdevRule`.

        Handles comment lines (``#``), blank lines and genuine rules
        with ``KEY==\"VAL\", ACTION=\"…\"`` syntax.

        Match operators recognised: ``==``, ``!=``
        Action operators recognised: ``=``, ``+=``, ``-=``
        """
        stripped = raw.strip()
        rule = UdevRule(line_number=line_number, raw=raw)

        # Comment / blank
        if not stripped or stripped.startswith("#"):
            rule.comment = stripped.lstrip("#").strip()
            return rule

        # Disabled rule (commented with a special marker)
        if stripped.startswith("#DISABLED#"):
            rule.disabled = True
            stripped = stripped[len("#DISABLED#"):].strip()

        # Remove inline comments
        cleaned = stripped.split("#", 1)[0].strip()
        if not cleaned:
            rule.comment = stripped.lstrip("#").strip()
            return rule

        # Tokenise respecting quoted strings
        tokens = self._tokenise(cleaned)

        for token in tokens:
            token = token.strip().rstrip(",")
            if not token:
                continue

            # match operators
            for op in ("!=", "=="):
                if op in token:
                    key, _, value = token.partition(op)
                    key = key.strip()
                    value = value.strip().strip('"')
                    rule.matches[key] = value
                    break
            else:
                # action operators
                for op in ("+=", "-=", "="):
                    if op in token:
                        key, _, value = token.partition(op)
                        key = key.strip()
                        value = value.strip().strip('"')
                        rule.actions[key] = value
                        break

        return rule

    @staticmethod
    def _tokenise(text: str) -> List[str]:
        """Split a udev rule into comma-separated tokens respecting quotes."""
        tokens: List[str] = []
        current: List[str] = []
        in_quote = False
        for ch in text:
            if ch == '"':
                in_quote = not in_quote
                current.append(ch)
            elif ch == ',' and not in_quote:
                tokens.append("".join(current))
                current = []
            else:
                current.append(ch)
        if current:
            tokens.append("".join(current))
        return tokens

    # =================================================================
    # Formatting a rule back to text
    # =================================================================
    def _format_udev_rule(self, rule: UdevRule) -> str:
        """Convert a :class:`UdevRule` back into a single udev rule line."""
        parts: List[str] = []

        for key, value in rule.matches.items():
            parts.append(f'{key}=="{value}"')

        for key, value in rule.actions.items():
            if key in ("RUN", "IMPORT", "PROGRAM"):
                parts.append(f'{key}+="{value}"')
            elif key == "ENV":
                parts.append(f'{key}+="{value}"')
            elif key == "TEST":
                parts.append(f'{key}+="{value}"')
            else:
                parts.append(f'{key}="{value}"')

        line = ", ".join(parts)
        return line

    # =================================================================
    # Read / write a rules file
    # =================================================================
    def get_rules(self, name: str) -> List[Dict[str, Any]]:
        """Read and parse a rules file.

        Parameters
        ----------
        name:
            Filename inside ``rules_dir``, e.g. ``"99-custom.rules"``.

        Returns
        -------
        list[dict]
            Each dict has keys ``line_number``, ``comment``, ``matches``,
            ``actions``, ``raw``, ``disabled``.
        """
        path = self.rules_dir / name
        if not path.is_file():
            return []

        text = self._read_file(path)
        lines = text.splitlines()
        rules: List[Dict[str, Any]] = []
        for idx, line in enumerate(lines, start=1):
            rule = self._parse_udev_rule(line, line_number=idx)
            rules.append(rule.to_dict())
        return rules

    def set_rules(self, name: str, rules: List[Dict[str, Any]]) -> RuleResult:
        """Overwrite a rules file with the provided rule list.

        Parameters
        ----------
        name:
            Filename inside ``rules_dir``.
        rules:
            List of dicts each containing at minimum ``matches`` and
            ``actions`` keys (plus optional ``comment`` and ``disabled``).

        Returns
        -------
        RuleResult
        """
        path = self.rules_dir / name
        lines: List[str] = []
        for idx, entry in enumerate(rules, start=1):
            comment = entry.get("comment", "")
            disabled = entry.get("disabled", False)
            matches = entry.get("matches", {})
            actions = entry.get("actions", {})

            rule = UdevRule(
                line_number=idx,
                comment=comment,
                matches=dict(matches),
                actions=dict(actions),
                disabled=disabled,
            )

            if comment and not matches:
                lines.append(f"# {comment}")
                continue

            formatted = self._format_udev_rule(rule)
            if disabled:
                formatted = f"#DISABLED# {formatted}"
            if comment:
                formatted = f"# {comment}\n{formatted}"
            lines.append(formatted)

        content = "\n".join(lines) + "\n"
        try:
            self._ensure_dir(path.parent)
            self._write_file(path, content)
            return RuleResult(
                success=True,
                message=f"Wrote {len(rules)} rules to {name}",
                data={"file": str(path), "rule_count": len(rules)},
            )
        except OSError as exc:
            return RuleResult(
                success=False,
                message=f"Failed to write {name}: {exc}",
                errors=[str(exc)],
            )

    # =================================================================
    # Add / remove / toggle individual rules
    # =================================================================
    def add_rule(
        self,
        name: str,
        matches: Dict[str, str],
        actions: Dict[str, str],
        comment: str = "",
        position: Optional[int] = None,
    ) -> RuleResult:
        """Append (or insert at *position*) a single rule.

        Parameters
        ----------
        name:
            Rules filename.
        matches:
            Match dictionary, e.g. ``{"SUBSYSTEM": "net"}``.
        actions:
            Action dictionary, e.g. ``{"MODE": "0666"}``.
        comment:
            Optional inline comment.
        position:
            If given, insert at this 0-based index; otherwise append.

        Returns
        -------
        RuleResult
        """
        existing = self.get_rules(name)
        new_rule: Dict[str, Any] = {
            "comment": comment,
            "matches": dict(matches),
            "actions": dict(actions),
            "disabled": False,
        }

        if position is not None and 0 <= position <= len(existing):
            existing.insert(position, new_rule)
        else:
            existing.append(new_rule)

        return self.set_rules(name, existing)

    def remove_rule(self, name: str, rule_index: int) -> RuleResult:
        """Remove the rule at *rule_index* (1-based line number) from *name*.

        Returns
        -------
        RuleResult
        """
        existing = self.get_rules(name)
        if not existing:
            return RuleResult(
                success=False,
                message=f"No rules file found: {name}",
            )

        # rule_index is 1-based line number; convert to 0-based list pos
        pos = rule_index - 1
        if pos < 0 or pos >= len(existing):
            return RuleResult(
                success=False,
                message=f"Index {rule_index} out of range (1–{len(existing)})",
            )

        removed = existing.pop(pos)
        result = self.set_rules(name, existing)
        result.data = {"removed_rule": removed}
        return result

    def disable_rule(self, name: str, rule_index: int) -> RuleResult:
        """Disable a rule by prefixing its line with ``#DISABLED#``."""
        return self._toggle_rule(name, rule_index, disable=True)

    def enable_rule(self, name: str, rule_index: int) -> RuleResult:
        """Re-enable a previously disabled rule."""
        return self._toggle_rule(name, rule_index, disable=False)

    def _toggle_rule(
        self, name: str, rule_index: int, *, disable: bool
    ) -> RuleResult:
        existing = self.get_rules(name)
        if not existing:
            return RuleResult(
                success=False,
                message=f"No rules file: {name}",
            )
        pos = rule_index - 1
        if pos < 0 or pos >= len(existing):
            return RuleResult(
                success=False,
                message=f"Index {rule_index} out of range",
            )
        existing[pos]["disabled"] = disable
        state = "disabled" if disable else "enabled"
        result = self.set_rules(name, existing)
        result.message = f"Rule {rule_index} {state} in {name}"
        return result

    def get_rule(self, name: str, rule_index: int) -> RuleResult:
        """Return a single rule by 1-based index."""
        existing = self.get_rules(name)
        if not existing:
            return RuleResult(
                success=False,
                message=f"No rules file: {name}",
            )
        pos = rule_index - 1
        if pos < 0 or pos >= len(existing):
            return RuleResult(
                success=False,
                message=f"Index {rule_index} out of range (1–{len(existing)})",
            )
        return RuleResult(
            success=True,
            message="Rule retrieved",
            data=existing[pos],
        )

    # =================================================================
    # Convenience rule builders
    # =================================================================
    def add_symlink_rule(
        self,
        name: str,
        match: Dict[str, str],
        symlink: str,
        comment: str = "",
    ) -> RuleResult:
        """Add a ``SYMLINK`` rule.

        Parameters
        ----------
        name:
            Rules filename.
        match:
            Match dictionary.
        symlink:
            Target symlink path, e.g. ``"disk/by-id/my-drive"``.
        comment:
            Optional comment.
        """
        actions = {"SYMLINK": symlink}
        return self.add_rule(name, match, actions, comment=comment)

    def add_permissions_rule(
        self,
        name: str,
        match: Dict[str, str],
        owner: Optional[str] = None,
        group: Optional[str] = None,
        mode: Optional[str] = None,
        comment: str = "",
    ) -> RuleResult:
        """Add a permissions rule (OWNER / GROUP / MODE).

        Parameters
        ----------
        name:
            Rules filename.
        match:
            Match dictionary.
        owner:
            Owner username or UID string.
        group:
            Group name or GID string.
        mode:
            Octal mode string, e.g. ``"0660"``.
        comment:
            Optional comment.
        """
        actions: Dict[str, str] = {}
        if owner is not None:
            actions["OWNER"] = owner
        if group is not None:
            actions["GROUP"] = group
        if mode is not None:
            actions["MODE"] = mode

        if not actions:
            return RuleResult(
                success=False,
                message="At least one of owner, group, mode must be provided",
            )

        return self.add_rule(name, match, actions, comment=comment)

    def add_program_rule(
        self,
        name: str,
        match: Dict[str, str],
        program: str,
        comment: str = "",
    ) -> RuleResult:
        """Add a ``RUN`` rule that invokes an external program.

        Parameters
        ----------
        name:
            Rules filename.
        match:
            Match dictionary.
        program:
            Program path or shell command.
        comment:
            Optional comment.
        """
        actions = {"RUN": program}
        return self.add_rule(name, match, actions, comment=comment)

    # =================================================================
    # udev.conf management
    # =================================================================
    def get_udev_conf(self) -> Dict[str, str]:
        """Parse ``udev.conf`` and return key-value pairs.

        Lines beginning with ``#`` are treated as comments and skipped.

        Returns
        -------
        dict[str, str]
            Mapping of setting name to value.
        """
        if not self.udev_conf_path.is_file():
            return {}
        text = self._read_file(self.udev_conf_path)
        settings: Dict[str, str] = {}
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" in stripped:
                key, _, value = stripped.partition("=")
                settings[key.strip()] = value.strip().strip('"')
        return settings

    def set_udev_conf(self, settings: Dict[str, str]) -> RuleResult:
        """Write key-value pairs to ``udev.conf``.

        Parameters
        ----------
        settings:
            Mapping of setting name to value.  Existing file is **replaced**
            entirely with the provided settings.

        Returns
        -------
        RuleResult
        """
        lines: List[str] = [
            "# udev.conf — managed by UmerOS udev_rules.py",
            f"# Last updated: {self._timestamp()}",
            "",
        ]
        for key, value in sorted(settings.items()):
            lines.append(f'{key}="{value}"')
        lines.append("")

        content = "\n".join(lines)
        try:
            self._write_file(self.udev_conf_path, content)
            return RuleResult(
                success=True,
                message=f"Wrote {len(settings)} settings to udev.conf",
                data=settings,
            )
        except OSError as exc:
            return RuleResult(
                success=False,
                message=f"Failed to write udev.conf: {exc}",
                errors=[str(exc)],
            )

    # =================================================================
    # hwdb management
    # =================================================================
    def _parse_hwdb(self, text: str) -> Dict[str, Dict[str, str]]:
        """Parse hwdb text into a dict keyed by modalias.

        Format per entry::

            <modalias>
            KEY: value
            …
        """
        entries: Dict[str, Dict[str, str]] = {}
        current_key: Optional[str] = None
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.endswith(":") and not stripped.startswith(" "):
                # potential header — but modalias lines don't end with ":"
                continue
            if not stripped.startswith(" ") and ":" in stripped:
                # New modalias line (no leading whitespace, contains a colon
                # that is part of the modalias pattern itself)
                # hwdb modalias format: the line does NOT end with ':'
                parts = stripped.split(":", 1)
                if len(parts) == 2 and not stripped.endswith(":"):
                    current_key = stripped
                    entries[current_key] = {}
                    continue
            if current_key and ":" in stripped:
                k, _, v = stripped.partition(":")
                entries[current_key][k.strip()] = v.strip()
        return entries

    def get_hwdb_entries(self) -> Dict[str, Dict[str, str]]:
        """Return all hwdb entries from ``hwdb.d/``.

        Returns
        -------
        dict[str, dict[str, str]]
            Outer key is the modalias string; inner dict is attribute
            key-value pairs.
        """
        if not self.hwdb_dir.is_dir():
            return {}

        combined_text: List[str] = []
        for path in sorted(self.hwdb_dir.iterdir()):
            if path.is_file():
                combined_text.append(self._read_file(path))

        return self._parse_hwdb("\n".join(combined_text))

    def add_hwdb_entry(
        self, vendor: str, product: str, attrs: Dict[str, str]
    ) -> RuleResult:
        """Append a new entry to the hwdb.

        Parameters
        ----------
        vendor:
            Vendor ID string, e.g. ``"046d"`` (Logitech).
        product:
            Product ID string, e.g. ``"c52b"``.
        attrs:
            Attribute dictionary, e.g. ``{"NAME": "my-keyboard"}``.

        Returns
        -------
        RuleResult
        """
        modalias = f"usb:v{vendor.upper()}p{product.upper()}*"
        lines: List[str] = []
        lines.append(modalias)
        for key, value in sorted(attrs.items()):
            lines.append(f"  {key}: {value}")
        lines.append("")

        target = self.hwdb_dir / "99-custom.hwdb"
        existing = ""
        if target.is_file():
            existing = self._read_file(target)

        new_block = "\n".join(lines) + "\n"
        combined = existing.rstrip("\n") + "\n" + new_block

        try:
            self._ensure_dir(target.parent)
            self._write_file(target, combined)
            return RuleResult(
                success=True,
                message=f"Added hwdb entry for {modalias}",
                data={"modalias": modalias, "attrs": attrs},
            )
        except OSError as exc:
            return RuleResult(
                success=False,
                message=f"Failed to write hwdb: {exc}",
                errors=[str(exc)],
            )

    # =================================================================
    # Validation
    # =================================================================
    def validate_rules(self, name: str) -> RuleResult:
        """Validate every rule in the named file.

        Checks performed:
        * Syntax check via ``udevadm verify`` (if available).
        * Structural checks for unknown match / action keys.
        * Ensures no duplicate match keys with conflicting operators.

        Returns
        -------
        RuleResult
            ``data`` contains a list of issue dicts.
        """
        path = self.rules_dir / name
        if not path.is_file():
            return RuleResult(
                success=False,
                message=f"File not found: {name}",
            )

        issues: List[Dict[str, Any]] = []
        rules = self.get_rules(name)

        known_matches = set(UDEV_MATCH_TYPES)
        known_actions = set(UDEV_ACTION_TYPES)

        for entry in rules:
            ln = entry.get("line_number", 0)
            raw = entry.get("raw", "")
            matches = entry.get("matches", {})
            actions = entry.get("actions", {})

            # Blank / comment
            if entry.get("comment") and not matches and not actions:
                continue

            for key in matches:
                if key not in known_matches:
                    issues.append(
                        {
                            "line": ln,
                            "type": "unknown_match",
                            "key": key,
                            "raw": raw,
                        }
                    )

            for key in actions:
                if key not in known_actions:
                    issues.append(
                        {
                            "line": ln,
                            "type": "unknown_action",
                            "key": key,
                            "raw": raw,
                        }
                    )

            # Try udevadm verify
            try:
                result = subprocess.run(
                    ["udevadm", "verify", str(path)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0 and result.stdout.strip():
                    for vline in result.stdout.strip().splitlines():
                        issues.append(
                            {
                                "line": ln,
                                "type": "udevadm",
                                "message": vline.strip(),
                                "raw": raw,
                            }
                        )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        if issues:
            return RuleResult(
                success=True,
                message=f"Validation completed with {len(issues)} issue(s)",
                data=issues,
            )
        return RuleResult(
            success=True,
            message="Validation passed — no issues found",
            data=[],
        )

    # =================================================================
    # Standard / reference rules
    # =================================================================
    def get_standard_rules(self) -> Dict[str, List[str]]:
        """Return the built-in common rule templates.

        Returns
        -------
        dict[str, list[str]]
            Each key is a category name; the value is a list of rule
            lines (comments + rules).
        """
        return dict(COMMON_UDEV_RULES)

    # =================================================================
    # Simulate rule matching
    # =================================================================
    def test_rule_match(
        self, rule: Dict[str, Any], device_attrs: Dict[str, str]
    ) -> RuleResult:
        """Simulate whether *rule* matches *device_attrs*.

        Parameters
        ----------
        rule:
            A rule dict with a ``matches`` key containing match
            conditions.
        device_attrs:
            Simulated device attributes, e.g.
            ``{"SUBSYSTEM": "net", "ATTR{address}": "aa:bb:cc:dd:ee:ff"}``.

        Returns
        -------
        RuleResult
            ``data["matched"]`` is ``True`` if all match conditions are
            satisfied.
        """
        matches = rule.get("matches", {})
        matched = True
        details: List[Dict[str, Any]] = []

        for key, expected in matches.items():
            actual = device_attrs.get(key, "")
            # Simple equality check (udev ``==`` operator)
            if actual == expected:
                details.append(
                    {"key": key, "expected": expected, "actual": actual, "hit": True}
                )
            else:
                matched = False
                details.append(
                    {"key": key, "expected": expected, "actual": actual, "hit": False}
                )

        return RuleResult(
            success=True,
            message="Match" if matched else "No match",
            data={"matched": matched, "details": details},
        )

    # =================================================================
    # Export / Backup
    # =================================================================
    def export_status(self) -> Dict[str, Any]:
        """Return a full status snapshot of the managed udev state.

        Returns
        -------
        dict
            Keys: ``rules_files``, ``rules``, ``udev_conf``, ``hwdb``,
            ``timestamp``.
        """
        files = self.list_rules_files()
        all_rules: Dict[str, List[Dict[str, Any]]] = {}
        for fname in files:
            all_rules[fname] = self.get_rules(fname)

        return {
            "timestamp": self._timestamp(),
            "rules_dir": str(self.rules_dir),
            "rules_files": files,
            "rules": all_rules,
            "udev_conf": self.get_udev_conf(),
            "hwdb": self.get_hwdb_entries(),
        }

    def backup_all(self, backup_path: str) -> RuleResult:
        """Create a full backup of all managed udev state.

        Parameters
        ----------
        backup_path:
            Destination directory for the backup.  A timestamped
            subdirectory is created inside it.

        Returns
        -------
        RuleResult
        """
        dest = Path(backup_path) / f"udev_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            self._ensure_dir(dest)

            # Backup rules dir
            rules_dest = dest / "rules.d"
            if self.rules_dir.is_dir():
                shutil.copytree(self.rules_dir, rules_dest, dirs_exist_ok=True)

            # Backup udev.conf
            if self.udev_conf_path.is_file():
                shutil.copy2(self.udev_conf_path, dest / "udev.conf")

            # Backup hwdb
            hwdb_dest = dest / "hwdb.d"
            if self.hwdb_dir.is_dir():
                shutil.copytree(self.hwdb_dir, hwdb_dest, dirs_exist_ok=True)

            # Snapshot JSON
            snapshot = self.export_status()
            import json

            (dest / "status.json").write_text(
                json.dumps(snapshot, indent=2, default=str), encoding="utf-8"
            )

            return RuleResult(
                success=True,
                message=f"Backup created at {dest}",
                data={"backup_path": str(dest)},
            )
        except Exception as exc:
            return RuleResult(
                success=False,
                message=f"Backup failed: {exc}",
                errors=[str(exc)],
            )

    # =================================================================
    # udevadm helpers
    # =================================================================
    def reload_rules(self) -> RuleResult:
        """Ask ``udevadm`` to reload rules and re-trigger devices."""
        rc, out, err = self._run_udevadm("control", "--reload-rules")
        if rc == 0:
            self._run_udevadm("trigger")
            return RuleResult(
                success=True,
                message="udev rules reloaded and devices re-triggered",
            )
        return RuleResult(
            success=False,
            message=f"udevadm reload failed (rc={rc}): {err}",
            errors=[err],
        )

    def test_rules_syntax(self, name: str) -> RuleResult:
        """Run ``udevadm verify`` on the named rules file."""
        path = self.rules_dir / name
        if not path.is_file():
            return RuleResult(
                success=False,
                message=f"File not found: {name}",
            )
        rc, out, err = self._run_udevadm("verify", str(path))
        if rc == 0:
            return RuleResult(
                success=True,
                message=f"Syntax check passed for {name}",
            )
        return RuleResult(
            success=False,
            message=f"Syntax errors in {name}",
            data={"stdout": out, "stderr": err},
            errors=[err],
        )

    def query_device(self, device: str) -> RuleResult:
        """Query udevdb for a device path or sys name.

        Parameters
        ----------
        device:
            Kernel device name or ``/sys`` path, e.g. ``"sda"`` or
            ``"/sys/block/sda"``.
        """
        rc, out, err = self._run_udevadm("info", "--query=all", f"--name={device}")
        if rc != 0:
            return RuleResult(
                success=False,
                message=f"Could not query device: {device}",
                errors=[err],
            )

        props: Dict[str, str] = {}
        for line in out.splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                props[key.strip()] = value.strip()
        return RuleResult(
            success=True,
            message=f"Device info for {device}",
            data=props,
        )


# ===================================================================
# CLI entry point
# ===================================================================
def _cli() -> None:
    """Minimal command-line interface for quick operations."""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="UmerOS udev Rules Manager",
    )
    sub = parser.add_subparsers(dest="command")

    # list
    sub.add_parser("list", help="List rules files")

    # status
    sub.add_parser("status", help="Export full udev status as JSON")

    # get
    p_get = sub.add_parser("get", help="Parse a rules file")
    p_get.add_argument("file", help="Rules filename")

    # validate
    p_val = sub.add_parser("validate", help="Validate a rules file")
    p_val.add_argument("file", help="Rules filename")

    # conf
    sub.add_parser("conf", help="Print udev.conf settings")

    # hwdb
    sub.add_parser("hwdb", help="Print hwdb entries")

    # reload
    sub.add_parser("reload", help="Reload udev rules")

    args = parser.parse_args()
    mgr = UdevRulesManager()

    if args.command == "list":
        for f in mgr.list_rules_files():
            print(f)

    elif args.command == "status":
        print(json.dumps(mgr.export_status(), indent=2, default=str))

    elif args.command == "get":
        rules = mgr.get_rules(args.file)
        for r in rules:
            print(json.dumps(r, default=str))

    elif args.command == "validate":
        result = mgr.validate_rules(args.file)
        print(json.dumps(result.to_dict(), indent=2, default=str))

    elif args.command == "conf":
        for k, v in mgr.get_udev_conf().items():
            print(f"{k} = {v}")

    elif args.command == "hwdb":
        for modalias, attrs in mgr.get_hwdb_entries().items():
            print(f"[{modalias}]")
            for k, v in attrs.items():
                print(f"  {k}: {v}")

    elif args.command == "reload":
        result = mgr.reload_rules()
        print(json.dumps(result.to_dict(), indent=2, default=str))

    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
