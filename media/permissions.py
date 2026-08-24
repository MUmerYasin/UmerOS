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
UmerOS /media - Access Control (Permissions)
==============================================

Manages user/group-based mount permissions following Linux
plugdev/storage group conventions and polkit-style authorization.

    Mounting and unmounting requires super user privileges.  However
    it is often necessary to allow users to use removable media.
    Common approaches: /etc/fstab ``user`` option, sudo, or
    group-based access (plugdev, storage).

Modules
-------
- ``MountPermission`` - per-user authorization model.
- ``MountPermissionManager`` - central permission registry.
- ``GroupPolicy`` - Linux group-based policy (plugdev, storage).

Quick start::

    from media.permissions import MountPermissionManager, GroupPolicy

    mgr = MountPermissionManager()
    mgr.grant("alice", "/media/usb0", owner=True)
    assert mgr.can_mount("alice", "/media/usb0")
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Set

log = logging.getLogger("UmerOS.Media.Permissions")


# ---------------------------------------------------------------------------
#  Permission model
# ---------------------------------------------------------------------------

@unique
class AccessLevel(Enum):
    """Granular access levels for mount operations."""
    NONE = "none"
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    OWNER = "owner"
    ADMIN = "admin"


@dataclass
class MountPermission:
    """Permission entry for a user on a mount point."""
    user: str
    mount_point: str
    access: AccessLevel = AccessLevel.READ_WRITE
    granted_at: float = 0.0
    expires_at: float = 0.0
    granted_by: str = "system"
    groups: Set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.granted_at == 0.0:
            self.granted_at = time.time()

    @property
    def is_expired(self) -> bool:
        if self.expires_at <= 0:
            return False
        return time.time() > self.expires_at

    @property
    def can_read(self) -> bool:
        return self.access in {
            AccessLevel.READ_ONLY, AccessLevel.READ_WRITE,
            AccessLevel.OWNER, AccessLevel.ADMIN,
        }

    @property
    def can_write(self) -> bool:
        return self.access in {
            AccessLevel.READ_WRITE, AccessLevel.OWNER, AccessLevel.ADMIN,
        }

    @property
    def is_owner(self) -> bool:
        return self.access in {AccessLevel.OWNER, AccessLevel.ADMIN}


# ---------------------------------------------------------------------------
#  Linux group-based policy
# ---------------------------------------------------------------------------

# Standard Linux groups that grant mount access
STANDARD_MOUNT_GROUPS: FrozenSet[str] = frozenset({
    "plugdev",      # removable devices
    "storage",      # all block storage
    "disk",         # raw disk access
    "cdrom",        # optical drives
    "floppy",       # floppy drives
    "tape",         # tape drives
    "video",        # video devices
    " optical",     # optical (alternate)
})

# Group -> which media types they cover
GROUP_MEDIA_MAP: Dict[str, FrozenSet[str]] = {
    "plugdev": frozenset({"usb", "sd_card", "mmc", "firewire", "nvme"}),
    "storage": frozenset({"usb", "sd_card", "mmc", "firewire", "nvme",
                          "cdrom", "dvd", "blu_ray", "floppy", "tape"}),
    "disk": frozenset({"usb", "sd_card", "mmc", "firewire", "nvme",
                       "cdrom", "dvd", "blu_ray", "floppy", "tape",
                       "internal"}),
    "cdrom": frozenset({"cdrom", "dvd", "blu_ray"}),
    "floppy": frozenset({"floppy"}),
    "tape": frozenset({"tape"}),
}


@dataclass
class GroupPolicy:
    """Linux group-based access policy.

    Checks whether a user belongs to groups that grant access
    to a given media type.
    """
    user_groups: Set[str] = field(default_factory=set)
    require_primary_group: bool = False

    def can_access_media_type(self, user: str, media_type: str) -> bool:
        """Check if user's groups grant access to *media_type*."""
        for group in self.user_groups:
            allowed = GROUP_MEDIA_MAP.get(group, frozenset())
            if media_type in allowed:
                return True
        return False

    def get_allowed_media_types(self) -> Set[str]:
        """Return all media types accessible by the current groups."""
        result: Set[str] = set()
        for group in self.user_groups:
            result.update(GROUP_MEDIA_MAP.get(group, frozenset()))
        return result

    def add_group(self, group: str) -> None:
        self.user_groups.add(group)

    def remove_group(self, group: str) -> None:
        self.user_groups.discard(group)

    @classmethod
    def for_user(cls, user: str, groups: Optional[Set[str]] = None) -> "GroupPolicy":
        """Create a policy for a user with given groups."""
        return cls(user_groups=groups or set())


# ---------------------------------------------------------------------------
#  Permission Manager
# ---------------------------------------------------------------------------

class MountPermissionManager:
    """Central registry for mount permissions.

    Manages per-user, per-mount-point permissions with expiry support.
    """

    def __init__(self) -> None:
        self._permissions: Dict[str, List[MountPermission]] = {}  # user -> perms
        self._global_admins: Set[str] = {"root"}
        self._mount_owners: Dict[str, str] = {}  # mount_point -> owner

    # -- Grant / Revoke -------------------------------------------------------

    def grant(
        self,
        user: str,
        mount_point: str,
        *,
        access: AccessLevel = AccessLevel.READ_WRITE,
        owner: bool = False,
        expires_in: float = 0.0,
        granted_by: str = "system",
    ) -> MountPermission:
        """Grant a permission entry."""
        if owner:
            access = AccessLevel.OWNER
        perm = MountPermission(
            user=user,
            mount_point=os.path.normpath(mount_point),
            access=access,
            expires_at=time.time() + expires_in if expires_in != 0 else 0.0,
            granted_by=granted_by,
        )
        self._permissions.setdefault(user, []).append(perm)
        if owner:
            self._mount_owners[os.path.normpath(mount_point)] = user
        log.info("Granted %s access to %s for %s", access.value, mount_point, user)
        return perm

    def revoke(self, user: str, mount_point: str) -> bool:
        """Revoke all permissions for *user* on *mount_point*."""
        perms = self._permissions.get(user, [])
        before = len(perms)
        self._permissions[user] = [
            p for p in perms
            if p.mount_point != os.path.normpath(mount_point)
        ]
        mp = os.path.normpath(mount_point)
        if mp in self._mount_owners and self._mount_owners[mp] == user:
            del self._mount_owners[mp]
        return len(self._permissions[user]) < before

    # -- Query ----------------------------------------------------------------

    def can_mount(self, user: str, mount_point: str) -> bool:
        """Check if *user* has any access to *mount_point*."""
        if user in self._global_admins:
            return True
        mp = os.path.normpath(mount_point)
        for perm in self._permissions.get(user, []):
            if perm.mount_point == mp and not perm.is_expired:
                return True
        return False

    def can_write(self, user: str, mount_point: str) -> bool:
        """Check if *user* has write access to *mount_point*."""
        if user in self._global_admins:
            return True
        mp = os.path.normpath(mount_point)
        for perm in self._permissions.get(user, []):
            if perm.mount_point == mp and not perm.is_expired and perm.can_write:
                return True
        return False

    def is_owner(self, user: str, mount_point: str) -> bool:
        """Check if *user* is the owner of *mount_point*."""
        if user in self._global_admins:
            return True
        return self._mount_owners.get(os.path.normpath(mount_point)) == user

    def get_permissions(self, user: str) -> List[MountPermission]:
        """Get all active permissions for *user*."""
        return [
            p for p in self._permissions.get(user, [])
            if not p.is_expired
        ]

    def get_mount_permissions(self, mount_point: str) -> List[MountPermission]:
        """Get all active permissions for a mount point."""
        mp = os.path.normpath(mount_point)
        result = []
        for perms in self._permissions.values():
            for p in perms:
                if p.mount_point == mp and not p.is_expired:
                    result.append(p)
        return result

    # -- Admin ----------------------------------------------------------------

    def add_admin(self, user: str) -> None:
        self._global_admins.add(user)

    def remove_admin(self, user: str) -> None:
        self._global_admins.discard(user)

    @property
    def admins(self) -> Set[str]:
        return set(self._global_admins)

    # -- Cleanup --------------------------------------------------------------

    def cleanup_expired(self) -> int:
        """Remove expired permissions.  Returns count removed."""
        count = 0
        for user in list(self._permissions):
            before = len(self._permissions[user])
            self._permissions[user] = [
                p for p in self._permissions[user] if not p.is_expired
            ]
            count += before - len(self._permissions[user])
            if not self._permissions[user]:
                del self._permissions[user]
        return count

    def clear(self) -> None:
        """Remove all permissions."""
        self._permissions.clear()
        self._mount_owners.clear()
        self._global_admins = {"root"}


# ---------------------------------------------------------------------------
#  fstab-style user/uid mount option helper
# ---------------------------------------------------------------------------

def parse_fstab_uid(options_str: str) -> Optional[int]:
    """Extract ``uid=`` from an fstab options string."""
    for part in options_str.split(","):
        if part.startswith("uid="):
            try:
                return int(part.split("=", 1)[1])
            except (ValueError, IndexError):
                pass
    return None


def effective_user(options_str: str, fallback_uid: int = 0) -> int:
    """Return the effective UID for a mounted filesystem."""
    uid = parse_fstab_uid(options_str)
    return uid if uid is not None else fallback_uid


def _selftest() -> bool:
    """Run self-diagnostics.  Returns True on success."""
    # AccessLevel
    ro = MountPermission("u", "/m", AccessLevel.READ_ONLY)
    assert ro.can_read
    assert not ro.can_write
    rw = MountPermission("u", "/m", AccessLevel.READ_WRITE)
    assert rw.can_read and rw.can_write
    own = MountPermission("u", "/m", AccessLevel.OWNER)
    assert own.is_owner

    # Manager
    mgr = MountPermissionManager()
    mgr.grant("alice", "/media/usb0", owner=True)
    assert mgr.can_mount("alice", "/media/usb0")
    assert mgr.is_owner("alice", "/media/usb0")
    assert not mgr.can_mount("bob", "/media/usb0")
    mgr.grant("bob", "/media/usb0", access=AccessLevel.READ_ONLY)
    assert mgr.can_mount("bob", "/media/usb0")
    assert not mgr.can_write("bob", "/media/usb0")

    # Revoke
    assert mgr.revoke("bob", "/media/usb0")
    assert not mgr.can_mount("bob", "/media/usb0")

    # Admin
    assert mgr.can_mount("root", "/anything")
    mgr.add_admin("charlie")
    assert mgr.can_mount("charlie", "/anything")

    # Expiry
    perm = mgr.grant("dave", "/media/cd0", expires_in=-1)  # already expired
    assert not mgr.can_mount("dave", "/media/cd0")
    removed = mgr.cleanup_expired()
    assert removed >= 1

    # Group policy
    gp = GroupPolicy(user_groups={"plugdev", "cdrom"})
    assert gp.can_access_media_type("user", "usb")
    assert gp.can_access_media_type("user", "cdrom")
    assert not gp.can_access_media_type("user", "tape")
    types = gp.get_allowed_media_types()
    assert "usb" in types
    assert "cdrom" in types

    # fstab helpers
    assert parse_fstab_uid("uid=1000,gid=1000") == 1000
    assert parse_fstab_uid("ro,noatime") is None
    assert effective_user("uid=1001") == 1001
    assert effective_user("ro") == 0

    return True
