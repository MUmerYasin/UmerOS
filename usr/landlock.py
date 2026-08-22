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
UmerOS Landlock Module
=======================
Kernel Landlock unprivileged access control.
Implements filesystem path rules and port network rules.

Reference: docs.kernel.org/userspace-api/landlock.html
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ============================================================================
# Constants
# ============================================================================

SUCCESS: int = 0
ERROR: int = 1
EINVAL: int = 22
EPERM: int = 13
ENOENT: int = 2
EACCES: int = 13


class LandlockABI(IntEnum):
    """Landlock ABI versions."""
    LANDLOCK_ABI_VERSION_1: int = 1
    LANDLOCK_ABI_VERSION_2: int = 2
    LANDLOCK_ABI_VERSION_3: int = 3


class LandlockRight(IntEnum):
    """Landlock access rights."""
    LANDLOCK_ACCESS_FS_EXECUTE: int = 1 << 0
    LANDLOCK_ACCESS_FS_WRITE_FILE: int = 1 << 1
    LANDLOCK_ACCESS_FS_READ_FILE: int = 1 << 2
    LANDLOCK_ACCESS_FS_READ_DIR: int = 1 << 3
    LANDLOCK_ACCESS_FS_REMOVE_DIR: int = 1 << 4
    LANDLOCK_ACCESS_FS_REMOVE_FILE: int = 1 << 5
    LANDLOCK_ACCESS_FS_MAKE_CHAR: int = 1 << 6
    LANDLOCK_ACCESS_FS_MAKE_DIR: int = 1 << 7
    LANDLOCK_ACCESS_FS_MAKE_REG: int = 1 << 8
    LANDLOCK_ACCESS_FS_MAKE_SOCK: int = 1 << 9
    LANDLOCK_ACCESS_FS_MAKE_FIFO: int = 1 << 10
    LANDLOCK_ACCESS_FS_MAKE_BLOCK: int = 1 << 11
    LANDLOCK_ACCESS_FS_MAKE_SYM: int = 1 << 12
    LANDLOCK_ACCESS_FS_REFER: int = 1 << 13
    LANDLOCK_ACCESS_FS_TRUNCATE: int = 1 << 14
    LANDLOCK_ACCESS_NET_BIND_TCP: int = 1 << 16
    LANDLOCK_ACCESS_NET_CONNECT_TCP: int = 1 << 17
    LANDLOCK_ACCESS_FS_IOCTL_DEV: int = 1 << 18


class LandlockRuleType(IntEnum):
    """Landlock rule types."""
    LANDLOCK_RULE_PATH_BENEATH: int = 1
    LANDLOCK_RULE_NET_PORT: int = 2
    LANDLOCK_RULE_HANDLED_ACCESS: int = 3


class LandlockAttrType(IntEnum):
    """Landlock attribute types."""
    LANDLOCK_ATTR_ABSTRACT_UNIX_SOCKET_PATH: int = 1
    LANDLOCK_ATTR_PORT: int = 2


# ============================================================================
# Landlock Data Structures
# ============================================================================

@dataclass
class LandlockPathBeneathAttr:
    """Path beneath attribute."""
    allowed_access: int = 0
    parent_fd: int = -1


@dataclass
class LandlockNetPortAttr:
    """Net port attribute."""
    allowed_access: int = 0
    port: int = 0


@dataclass
class LandlockPathRule:
    """Filesystem path rule."""
    rule_id: int
    path: str
    parent_fd: int
    allowed_access: int
    inherited: bool = False


@dataclass
class LandlockNetRule:
    """Network port rule."""
    rule_id: int
    port: int
    allowed_access: int
    inherited: bool = False


@dataclass
class LandlockRuleset:
    """Landlock ruleset."""
    ruleset_id: int
    num_path_beneath: int = 0
    num_net_port: int = 0
    path_rules: List[LandlockPathRule] = field(default_factory=list)
    net_rules: List[LandlockNetRule] = field(default_factory=list)
    handled_access_fs: int = 0
    handled_access_net: int = 0
    compat_version: int = 1
    created_by: int = 0
    attached_to: List[int] = field(default_factory=list)


# ============================================================================
# Landlock Manager
# ============================================================================

class LandlockManager:
    """Landlock access control manager."""

    def __init__(self) -> None:
        self._rulesets: Dict[int, LandlockRuleset] = {}
        self._next_ruleset_id: int = 1
        self._next_rule_id: int = 1
        self._abi_version: int = LandlockABI.LANDLOCK_ABI_VERSION_3
        self._proc_rulesets: Dict[int, List[int]] = {}

    def get_abi_version(self) -> int:
        return self._abi_version

    def create_ruleset(self, attr: Dict[str, int], flags: int = 0) -> int:
        rsid = self._next_ruleset_id
        self._next_ruleset_id += 1
        ruleset = LandlockRuleset(
            ruleset_id=rsid,
            num_path_beneath=attr.get("num_path_beneath", 0),
            num_net_port=attr.get("num_net_port", 0),
            handled_access_fs=attr.get("handled_access_fs", 0),
            handled_access_net=attr.get("handled_access_net", 0),
            compat_version=attr.get("compat_version", 1),
        )
        self._rulesets[rsid] = ruleset
        return rsid

    def add_rule_path_beneath(self, ruleset_id: int, path: str, parent_fd: int, allowed_access: int) -> int:
        if ruleset_id not in self._rulesets:
            return -EINVAL
        rule_id = self._next_rule_id
        self._next_rule_id += 1
        rule = LandlockPathRule(
            rule_id=rule_id,
            path=path,
            parent_fd=parent_fd,
            allowed_access=allowed_access,
        )
        self._rulesets[ruleset_id].path_rules.append(rule)
        return SUCCESS

    def add_rule_net_port(self, ruleset_id: int, port: int, allowed_access: int) -> int:
        if ruleset_id not in self._rulesets:
            return -EINVAL
        rule_id = self._next_rule_id
        self._next_rule_id += 1
        rule = LandlockNetRule(
            rule_id=rule_id,
            port=port,
            allowed_access=allowed_access,
        )
        self._rulesets[ruleset_id].net_rules.append(rule)
        return SUCCESS

    def restrict_self(self, ruleset_id: int, pid: int) -> int:
        if ruleset_id not in self._rulesets:
            return -EINVAL
        ruleset = self._rulesets[ruleset_id]
        if pid not in ruleset.attached_to:
            ruleset.attached_to.append(pid)
        if pid not in self._proc_rulesets:
            self._proc_rulesets[pid] = []
        if ruleset_id not in self._proc_rulesets[pid]:
            self._proc_rulesets[pid].append(ruleset_id)
        return SUCCESS

    def check_access(self, pid: int, path: str, access: int) -> bool:
        rulesets = self._proc_rulesets.get(pid, [])
        for rsid in rulesets:
            rs = self._rulesets.get(rsid)
            if not rs:
                continue
            for rule in rs.path_rules:
                if path.startswith(rule.path) or rule.path == "/":
                    if rule.allowed_access & access:
                        return True
        return False

    def check_net_access(self, pid: int, port: int, access: int) -> bool:
        rulesets = self._proc_rulesets.get(pid, [])
        for rsid in rulesets:
            rs = self._rulesets.get(rsid)
            if not rs:
                continue
            for rule in rs.net_rules:
                if rule.port == port or rule.port == 0:
                    if rule.allowed_access & access:
                        return True
        return False

    def get_rulesets(self, pid: int) -> List[LandlockRuleset]:
        rsids = self._proc_rulesets.get(pid, [])
        return [self._rulesets[rsid] for rsid in rsids if rsid in self._rulesets]

    def remove_ruleset(self, ruleset_id: int) -> int:
        self._rulesets.pop(ruleset_id, None)
        return SUCCESS


# ============================================================================
# Global Instance
# ============================================================================

_global_landlock: Optional[LandlockManager] = None


def get_landlock_manager() -> LandlockManager:
    global _global_landlock
    if _global_landlock is None:
        _global_landlock = LandlockManager()
    return _global_landlock


def landlock_create_ruleset(attr: Dict[str, int], flags: int = 0) -> int:
    return get_landlock_manager().create_ruleset(attr, flags)


def landlock_add_rule(ruleset_id: int, rule_type: int, rule_attr: Dict[str, Any], flags: int = 0) -> int:
    if rule_type == LandlockRuleType.LANDLOCK_RULE_PATH_BENEATH:
        return get_landlock_manager().add_rule_path_beneath(
            ruleset_id,
            rule_attr.get("path", "/"),
            rule_attr.get("parent_fd", -1),
            rule_attr.get("allowed_access", 0),
        )
    elif rule_type == LandlockRuleType.LANDLOCK_RULE_NET_PORT:
        return get_landlock_manager().add_rule_net_port(
            ruleset_id,
            rule_attr.get("port", 0),
            rule_attr.get("allowed_access", 0),
        )
    return -EINVAL


def landlock_restrict_self(ruleset_id: int, pid: int) -> int:
    return get_landlock_manager().restrict_self(ruleset_id, pid)
