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
UmerOS Helper Programs Manager (/usr/libexec)
==============================================
Helper programs and executables used by system utilities.

Reference: Filesystem Hierarchy - /usr/libexec
  /usr/libexec contains helper programs that are not meant to be
  executed directly by users or scripts. They are called by other
  programs and provide supporting functionality.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ─── Constants ───────────────────────────────────────────────────────────────

LIBEXEC_PATHS = [
    "/usr/libexec",
    "/usr/libexec/openssh",
    "/usr/libexec/ipsec",
    "/usr/libexec/udev",
    "/usr/libexec/initscripts",
    "/usr/libexec/sudo",
]

LIBEXEC_CATEGORIES = {
    "OPENSSH": "OpenSSH helper programs",
    "UDEV": "Udev event handlers",
    "SUDO": "Sudo helper utilities",
    "NETWORK": "Network configuration helpers",
    "SYSTEM": "System initialization helpers",
    "CRON": "Cron-related helpers",
    "PACKAGE": "Package management helpers",
    "SECURITY": "Security-related helpers",
}


# ─── Enums ───────────────────────────────────────────────────────────────────

class LibexecCategory(IntEnum):
    """Helper program categories."""
    OPENSSH = 1
    UDEV = 2
    SUDO = 3
    NETWORK = 4
    SYSTEM = 5
    CRON = 6
    PACKAGE = 7
    SECURITY = 8
    UNKNOWN = 99


class LibexecStatus(IntEnum):
    """Helper program status."""
    ACTIVE = 1
    DEPRECATED = 2
    REMOVED = 3
    BROKEN = 4


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class LibexecBinary:
    """Represents a helper program in /usr/libexec."""
    name: str
    path: str
    category: LibexecCategory = LibexecCategory.UNKNOWN
    status: LibexecStatus = LibexecStatus.ACTIVE
    description: str = ""
    version: str = ""
    size: int = 0
    parent_package: str = ""
    required_by: List[str] = field(default_factory=list)
    permissions: str = "755"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "category": self.category.name,
            "status": self.status.name,
            "description": self.description,
            "version": self.version,
            "size": self.size,
            "parent_package": self.parent_package,
            "required_by": self.required_by,
            "permissions": self.permissions,
        }


@dataclass
class LibexecModule:
    """A loadable module for helper programs."""
    name: str
    path: str
    module_type: str = "shared"
    description: str = ""
    version: str = ""
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "module_type": self.module_type,
            "description": self.description,
            "version": self.version,
            "dependencies": self.dependencies,
        }


# ─── Global State ────────────────────────────────────────────────────────────

_global_libexec_manager: Optional["LibexecManager"] = None


# ─── Main Manager Class ─────────────────────────────────────────────────────

class LibexecManager:
    """Manages /usr/libexec - helper programs."""

    def __init__(self) -> None:
        self._binaries: Dict[str, LibexecBinary] = {}
        self._modules: Dict[str, LibexecModule] = {}
        self._custom_paths: List[str] = []
        self._initialize_default_binaries()
        self._initialize_default_modules()

    def _initialize_default_binaries(self) -> None:
        """Initialize with common libexec binaries."""
        default_bins = [
            ("ssh-keysign", "/usr/libexec/openssh/ssh-keysign", LibexecCategory.OPENSSH, "SSH key signing helper"),
            ("ssh-pkcs11-helper", "/usr/libexec/openssh/ssh-pkcs11-helper", LibexecCategory.OPENSSH, "PKCS#11 helper"),
            ("sftp-server", "/usr/libexec/openssh/sftp-server", LibexecCategory.OPENSSH, "SFTP server program"),
            ("sshd", "/usr/libexec/openssh/sshd", LibexecCategory.OPENSSH, "OpenSSH daemon"),
            ("udevd", "/usr/libexec/udev/udevd", LibexecCategory.UDEV, "Udev event daemon"),
            ("udevadm", "/usr/libexec/udev/udevadm", LibexecCategory.UDEV, "Udev administration tool"),
            ("systemd-*", "/usr/libexec/systemd/", LibexecCategory.SYSTEM, "Systemd helper programs"),
            ("sudo", "/usr/libexec/sudo/sudo", LibexecCategory.SUDO, "Sudo helper"),
            ("sudoedit", "/usr/libexec/sudo/sudoedit", LibexecCategory.SUDO, "Sudo edit helper"),
            ("pkexec", "/usr/libexec/polkit-1/pkexec", LibexecCategory.SECURITY, "PolicyKit execute as other user"),
            ("polkitd", "/usr/libexec/polkit-1/polkitd", LibexecCategory.SECURITY, "PolicyKit daemon"),
            ("colord", "/usr/libexec/colord/colord", LibexecCategory.SYSTEM, "Color management daemon"),
            ("geoclue", "/usr/libexec/geoclue-2.0/geoclue", LibexecCategory.SYSTEM, "Geolocation service"),
            ("rtkit-daemon", "/usr/libexec/rtkit/rtkit-daemon", LibexecCategory.SYSTEM, "RealtimeKit scheduling policy"),
            ("ibus-*", "/usr/libexec/ibus/", LibexecCategory.SYSTEM, "IBus input method helpers"),
            ("gdm-*", "/usr/libexec/gdm/", LibexecCategory.SYSTEM, "GDM helpers"),
            ("NetworkManager", "/usr/libexec/NetworkManager/", LibexecCategory.NETWORK, "NetworkManager helpers"),
            ("dhclient", "/usr/libexec/dhclient", LibexecCategory.NETWORK, "DHCP client helper"),
            ("ipsec", "/usr/libexec/ipsec/ipsec", LibexecCategory.NETWORK, "IPsec management"),
            ("charon", "/usr/libexec/ipsec/charon", LibexecCategory.NETWORK, "IKEv2 daemon"),
            ("pluto", "/usr/libexec/ipsec/pluto", LibexecCategory.NETWORK, "IKE daemon"),
            ("cron", "/usr/libexec/cron/cron", LibexecCategory.CRON, "Cron daemon helper"),
            ("at", "/usr/libexec/at/at", LibexecCategory.CRON, "At scheduler helper"),
            ("rpm", "/usr/libexec/rpm/rpm", LibexecCategory.PACKAGE, "RPM helper"),
            ("dpkg", "/usr/libexec/dpkg/dpkg", LibexecCategory.PACKAGE, "DPkg helper"),
            ("apt-*", "/usr/libexec/apt/", LibexecCategory.PACKAGE, "APT helpers"),
        ]
        for name, path, cat, desc in default_bins:
            self._binaries[name] = LibexecBinary(
                name=name, path=path, category=cat, description=desc
            )

    def _initialize_default_modules(self) -> None:
        """Initialize default modules."""
        default_modules = [
            ("gtk-3.0", "/usr/libexec/gtk-3.0", "shared", "GTK 3 modules"),
            ("gdk-pixbuf-2.0", "/usr/libexec/gdk-pixbuf-2.0", "shared", "GDK Pixbuf loaders"),
            ("pango", "/usr/libexec/pango", "shared", "Pango modules"),
            ("glib-2.0", "/usr/libexec/glib-2.0", "shared", "GLib modules"),
            ("dconf", "/usr/libexec/dconf", "shared", "DConf helpers"),
            ("gsettings", "/usr/libexec/gsettings", "shared", "GSettings helpers"),
            ("gio", "/usr/libexec/gio", "shared", "GIO modules"),
            ("polkit-1", "/usr/libexec/polkit-1", "shared", "PolicyKit modules"),
            ("colord", "/usr/libexec/colord", "shared", "Color management modules"),
            ("packagekit", "/usr/libexec/packagekit", "shared", "PackageKit helpers"),
        ]
        for name, path, mod_type, desc in default_modules:
            self._modules[name] = LibexecModule(
                name=name, path=path, module_type=mod_type, description=desc
            )

    def add_custom_path(self, path: str) -> None:
        """Add a custom libexec search path."""
        if path not in self._custom_paths:
            self._custom_paths.append(path)

    def get_search_paths(self) -> List[str]:
        """Get all libexec search paths."""
        return LIBEXEC_PATHS + self._custom_paths

    def register_binary(self, binary: LibexecBinary) -> None:
        """Register a new helper binary."""
        self._binaries[binary.name] = binary

    def get_binary(self, name: str) -> Optional[LibexecBinary]:
        """Get a binary by name."""
        return self._binaries.get(name)

    def list_binaries(self, category: Optional[LibexecCategory] = None) -> List[LibexecBinary]:
        """List all binaries, optionally filtered by category."""
        bins = list(self._binaries.values())
        if category is not None:
            bins = [b for b in bins if b.category == category]
        return sorted(bins, key=lambda b: b.name)

    def search_binaries(self, query: str) -> List[LibexecBinary]:
        """Search binaries by name or description."""
        query_lower = query.lower()
        results = []
        for binary in self._binaries.values():
            if (query_lower in binary.name.lower() or
                query_lower in binary.description.lower()):
                results.append(binary)
        return results

    def register_module(self, module: LibexecModule) -> None:
        """Register a new module."""
        self._modules[module.name] = module

    def get_module(self, name: str) -> Optional[LibexecModule]:
        """Get a module by name."""
        return self._modules.get(name)

    def list_modules(self) -> List[LibexecModule]:
        """List all modules."""
        return sorted(self._modules.values(), key=lambda m: m.name)

    def get_statistics(self) -> Dict[str, Any]:
        """Get libexec statistics."""
        by_category: Dict[str, int] = {}
        for binary in self._binaries.values():
            cat_name = binary.category.name
            by_category[cat_name] = by_category.get(cat_name, 0) + 1
        return {
            "total_binaries": len(self._binaries),
            "total_modules": len(self._modules),
            "by_category": by_category,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize manager to dictionary."""
        return {
            "search_paths": self.get_search_paths(),
            "binaries": {k: v.to_dict() for k, v in self._binaries.items()},
            "modules": {k: v.to_dict() for k, v in self._modules.items()},
            "statistics": self.get_statistics(),
        }


# ─── Singleton Getter ────────────────────────────────────────────────────────

def get_global_libexec_manager() -> LibexecManager:
    """Get or create the global LibexecManager instance."""
    global _global_libexec_manager
    if _global_libexec_manager is None:
        _global_libexec_manager = LibexecManager()
    return _global_libexec_manager


def initialize() -> LibexecManager:
    """Initialize and return the global LibexecManager."""
    return get_global_libexec_manager()


def refresh() -> LibexecManager:
    """Refresh the global LibexecManager."""
    global _global_libexec_manager
    _global_libexec_manager = LibexecManager()
    return _global_libexec_manager
