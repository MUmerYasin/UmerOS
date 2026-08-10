"""
UmerOS udev Rules Engine
Based on Greg Kroah-Hartman's udev paper (OLS 2003)

Rules format:
    KERNEL=="name", SUBSYSTEM=="subsystem", ACTION=="add|remove", \
    ENV{key}=="value", \
    NAME="devname", SYMLINK="link", OWNER="user", GROUP="group", MODE="0666"
"""

from __future__ import annotations

import re
import stat
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from .device_manager import DeviceManager, DeviceNode, DeviceType  # noqa: F401


class UdevAction(Enum):
    """Device hotplug actions."""
    ADD = "add"
    REMOVE = "remove"
    CHANGE = "change"
    MOVE = "move"
    ONLINE = "online"
    OFFLINE = "offline"


@dataclass
class UdevEvent:
    """Event emitted by kernel when device state changes."""
    subsystem: str
    kernel: str
    action: UdevAction
    devpath: str = ""
    devname: str = ""
    major: int = 0
    minor: int = 0
    env: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.devpath:
            self.devpath = f"/sys/class/{self.subsystem}/{self.kernel}"


@dataclass
class UdevRuleMatch:
    """A single match criterion for a udev rule."""
    key: str  # KERNEL, SUBSYSTEM, ACTION, ENV{}, ATTR{}, etc.
    value: str  # Pattern to match (supports ==, !=, =~, !~)
    operator: str = "=="  # ==, !=, =~, !~


@dataclass
class UdevRuleAction:
    """A single action to perform when rule matches."""
    key: str  # NAME, SYMLINK, OWNER, GROUP, MODE, RUN, etc.
    value: str  # Value to set


@dataclass
class UdevRule:
    """A complete udev rule with matches and actions."""
    matches: list[UdevRuleMatch] = field(default_factory=list)
    actions: list[UdevRuleAction] = field(default_factory=list)
    priority: int = 0  # Lower = higher priority
    raw_line: str = ""

    def matches_event(self, event: UdevEvent) -> bool:
        """Check if this rule matches the given event."""
        for match in self.matches:
            if not self._check_match(match, event):
                return False
        return True

    def _check_match(self, match: UdevRuleMatch, event: UdevEvent) -> bool:
        """Check a single match criterion against an event."""
        value = self._get_event_value(match.key, event)

        if match.operator == "==":
            return self._pattern_match(value, match.value)
        elif match.operator == "!=":
            return not self._pattern_match(value, match.value)
        elif match.operator == "=~":
            return bool(re.match(match.value, value))
        elif match.operator == "!~":
            return not bool(re.match(match.value, value))
        return False

    def _get_event_value(self, key: str, event: UdevEvent) -> str:
        """Extract value from event based on key."""
        key = key.upper()

        if key == "KERNEL":
            return event.kernel
        elif key == "SUBSYSTEM":
            return event.subsystem
        elif key == "ACTION":
            return event.action.value
        elif key == "DEVPATH":
            return event.devpath
        elif key == "DEVNAME":
            return event.devname
        elif key == "MAJOR":
            return str(event.major)
        elif key == "MINOR":
            return str(event.minor)
        elif key.startswith("ENV{") and key.endswith("}"):
            env_key = key[4:-1]
            return event.env.get(env_key, "")
        elif key.startswith("ATTR{") and key.endswith("}"):
            # Would read from sysfs - return empty for now
            return ""
        return ""

    def _pattern_match(self, value: str, pattern: str) -> bool:
        """Match value against pattern with wildcard support (*, ?)."""
        # Convert glob pattern to regex
        regex = re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".")
        return bool(re.fullmatch(regex, value))

    def apply_actions(
        self,
        event: UdevEvent,
        device_manager: DeviceManager
    ) -> DeviceNode | None:
        """Apply rule actions to create/modify device node."""
        name = None
        symlinks: list[str] = []
        owner = "root"
        group = "root"
        mode = 0o666

        for action in self.actions:
            action_key = action.key.upper()

            if action_key == "NAME":
                name = self._substitute_placeholders(action.value, event)
            elif action_key == "SYMLINK":
                symlinks.append(self._substitute_placeholders(action.value, event))
            elif action_key == "OWNER":
                owner = action.value
            elif action_key == "GROUP":
                group = action.value
            elif action_key == "MODE":
                try:
                    mode = int(action.value, 8)  # Parse octal
                except ValueError:
                    mode = 0o666

        if not name:
            name = event.kernel

        # Determine device type based on subsystem
        device_type = self._infer_device_type(event)

        # Create the device node
        devnode = DeviceNode(
            name=name,
            dev_type=device_type,
            major=event.major,
            minor=event.minor,
            mode=mode,
            uid=0,
            gid=0,
        )

        # Add symlinks
        for link in symlinks:
            link_path = Path(f"/dev/{link}")
            devnode.symlink_to(link_path)

        device_manager.create(devnode)
        return devnode

    def _infer_device_type(self, event: UdevEvent) -> DeviceType:
        """Infer device type from subsystem/kernel name."""
        subsystem = event.subsystem.lower()
        kernel = event.kernel.lower()

        if subsystem == "block" or kernel.startswith(("sd", "hd", "vd", "nvme")):
            return DeviceType.BLOCK
        elif subsystem == "tty" or kernel.startswith(("tty", "pts")):
            return DeviceType.CHAR
        elif subsystem == "input" or kernel.startswith(("input", "mouse")):
            return DeviceType.CHAR
        elif subsystem == "net" or kernel.startswith(("eth", "wlan")):
            return DeviceType.CHAR  # Network devices are char in Linux
        else:
            return DeviceType.CHAR

    def _substitute_placeholders(self, value: str, event: UdevEvent) -> str:
        """Replace %k, %n, %p, %E{key}, etc. with event values."""
        import re
        result = value

        # Simple substitutions
        result = result.replace("%k", event.kernel)
        result = result.replace("%n", str(event.minor))
        result = result.replace("%p", event.devpath)
        result = result.replace("%S", event.env.get("ID_SERIAL_SHORT", ""))
        result = result.replace("%b", event.env.get("ID_PATH", ""))
        result = result.replace("%d", f"{event.major}:{event.minor}")
        result = result.replace("%m", str(event.major))

        # Handle %E{key} syntax - substitute env variable
        def replace_env(match):
            key = match.group(1)
            return event.env.get(key, "")

        result = re.sub(r'%E\{([^}]+)\}', replace_env, result)

        # Handle %{key} syntax as shorthand for %E{key}
        result = re.sub(r'%\{([^}]+)\}', replace_env, result)

        return result


class UdevRulesEngine:
    """
    udev rules engine that processes device events.

    Based on Greg Kroah-Hartman's udev paper (OLS 2003):
    - Rules are loaded from /etc/udev/rules.d/ and /lib/udev/rules.d/
    - Rules are processed in lexical order
    - First matching rule wins (for NAME/SYMLINK)
    - Later rules can add additional symlinks
    """

    def __init__(self, device_manager: DeviceManager):
        self.device_manager = device_manager
        self.rules: list[UdevRule] = []
        self._load_default_rules()

    def _load_default_rules(self):
        """Load default UmerOS rules."""
        # Block device rules
        self.add_rule(UdevRule(
            matches=[
                UdevRuleMatch("SUBSYSTEM", "block"),
                UdevRuleMatch("ACTION", "add"),
            ],
            actions=[
                UdevRuleAction("NAME", "disk/by-id/%E{ID_SERIAL}-%k"),
                UdevRuleAction("MODE", "0660"),
                UdevRuleAction("GROUP", "disk"),
            ],
            priority=100,
        ))

        # TTY rules
        self.add_rule(UdevRule(
            matches=[
                UdevRuleMatch("SUBSYSTEM", "tty"),
                UdevRuleMatch("ACTION", "add"),
            ],
            actions=[
                UdevRuleAction("NAME", "tty/%k"),
                UdevRuleAction("MODE", "0620"),
                UdevRuleAction("GROUP", "dialout"),
            ],
            priority=100,
        ))

        # Input device rules
        self.add_rule(UdevRule(
            matches=[
                UdevRuleMatch("SUBSYSTEM", "input"),
                UdevRuleMatch("ACTION", "add"),
            ],
            actions=[
                UdevRuleAction("NAME", "input/%k"),
                UdevRuleAction("MODE", "0660"),
                UdevRuleAction("GROUP", "input"),
            ],
            priority=100,
        ))

    def add_rule(self, rule: UdevRule):
        """Add a rule to the ruleset."""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority)

    def remove_rule(self, rule: UdevRule):
        """Remove a rule from the ruleset."""
        if rule in self.rules:
            self.rules.remove(rule)

    def load_rules_file(self, path: Path):
        """Load rules from a udev rules file."""
        if not path.exists():
            return

        with open(path, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                rule = self._parse_rule_line(line)
                if rule:
                    rule.raw_line = f"{path}:{line_num}: {line}"
                    self.rules.append(rule)

        self.rules.sort(key=lambda r: r.priority)

    def _parse_rule_line(self, line: str) -> UdevRule | None:
        """Parse a single udev rule line."""
        # Simple parser - handles basic patterns
        matches = []
        actions = []

        # Split by comma or whitespace
        tokens = re.split(r'[,\s]+', line)

        i = 0
        while i < len(tokens):
            token = tokens[i]

            if "==" in token or "!=" in token or "=~" in token or "!~" in token:
                # This is a match
                match = self._parse_match(token)
                if match:
                    matches.append(match)
            elif "=" in token and not token.startswith(("ENV", "ATTR")):
                # This is an action
                action = self._parse_action(token)
                if action:
                    actions.append(action)
            i += 1

        if matches or actions:
            return UdevRule(matches=matches, actions=actions)
        return None

    def _parse_match(self, token: str) -> UdevRuleMatch | None:
        """Parse a match token like KERNEL=="sda*" or SUBSYSTEM=="block"."""
        for op in ["==", "!=", "=~", "!~"]:
            if op in token:
                key, value = token.split(op, 1)
                value = value.strip('"').strip("'")
                return UdevRuleMatch(key=key.strip(), value=value, operator=op)
        return None

    def _parse_action(self, token: str) -> UdevRuleAction | None:
        """Parse an action token like NAME="sda" or MODE="0666"."""
        if "=" in token:
            key, value = token.split("=", 1)
            value = value.strip('"').strip("'")
            return UdevRuleAction(key=key.strip(), value=value)
        return None

    def process_event(self, event: UdevEvent) -> list[DeviceNode]:
        """Process a device event through all rules."""
        results = []

        for rule in self.rules:
            if rule.matches_event(event):
                devnode = rule.apply_actions(event, self.device_manager)
                if devnode:
                    results.append(devnode)

        return results

    def simulate_hotplug(
        self,
        subsystem: str,
        kernel: str,
        action: UdevAction = UdevAction.ADD,
        major: int = 0,
        minor: int = 0,
        env: dict[str, str] | None = None,
    ) -> list[DeviceNode]:
        """Simulate a device hotplug event."""
        event = UdevEvent(
            subsystem=subsystem,
            kernel=kernel,
            action=action,
            major=major,
            minor=minor,
            env=env or {},
        )
        return self.process_event(event)

    def get_rules_summary(self) -> dict[str, Any]:
        """Get summary of loaded rules."""
        return {
            "total_rules": len(self.rules),
            "rules": [
                {
                    "priority": r.priority,
                    "matches": len(r.matches),
                    "actions": len(r.actions),
                    "raw": r.raw_line[:80] if r.raw_line else "default",
                }
                for r in self.rules[:10]  # First 10 rules
            ],
        }
