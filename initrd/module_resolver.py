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
Umer OS Initrd Module Resolver
==============================
Decides which kernel modules must be loaded into the initrd so the
real root filesystem can be mounted.

The reference describes three resolution strategies for
``/linuxrc``::

    2) /linuxrc determines what is needed to (1) mount the "real" root
       FS (i.e. device type, device drivers, file system) and (2) the
       distribution media (e.g. CD-ROM, network, tape, ...). This can
       be done by asking the user, by auto-probing, or by using a
       hybrid approach.

This module implements all three:

* :meth:`ModuleResolver.from_user_config` - read a list from a file or
  a CLI argument (the "asking the user" case).
* :meth:`ModuleResolver.autoprobe` - inspect the live kernel log and
  the host's ``/sys`` and ``/proc`` to guess what is needed.
* :meth:`ModuleResolver.hybrid` - start from autoprobe, then let the
  user add/remove entries before committing.

The actual module database is a simple Python dict so the project
doesn't need a C compiler to regenerate ``modules.dep`` every time
the kernel changes.  Real production setups would read from
``/lib/modules/$(uname -r)/modules.dep``.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set

log = logging.getLogger("UmerOS.Initrd.ModuleResolver")


# ---------------------------------------------------------------------------
# Reasons
# ---------------------------------------------------------------------------

class ModuleReason(str, Enum):
    """Why a particular module was added to the list."""

    USER_REQUEST   = "user_request"
    AUTOPROBE      = "autoprobe"
    DEPENDENCY     = "dependency"
    FILESYSTEM     = "filesystem"
    STORAGE        = "storage"
    NETWORK        = "network"
    CRYPTO         = "crypto"
    SCENARIO       = "scenario"


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@dataclass
class ModuleSpec:
    """A single kernel module to load into the initrd."""

    name: str
    reason: ModuleReason = ModuleReason.USER_REQUEST
    parameters: Dict[str, str] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    source: str = ""

    def as_dict(self) -> dict:
        return {
            "name":         self.name,
            "reason":       self.reason.value,
            "parameters":   dict(self.parameters),
            "dependencies": list(self.dependencies),
            "source":       self.source,
        }


# ---------------------------------------------------------------------------
# Default database
# ---------------------------------------------------------------------------

# A pragmatic subset of the modules.alias graph.  This is the
# bare minimum needed to make UmerOS boot in a real VM.
DEFAULT_MODULE_DB: Dict[str, ModuleSpec] = {
    # Filesystems
    "ext4":      ModuleSpec("ext4",      ModuleReason.FILESYSTEM, source="default"),
    "btrfs":     ModuleSpec("btrfs",     ModuleReason.FILESYSTEM, source="default"),
    "xfs":       ModuleSpec("xfs",       ModuleReason.FILESYSTEM, source="default"),
    "vfat":      ModuleSpec("vfat",      ModuleReason.FILESYSTEM, source="default"),
    "ntfs":      ModuleSpec("ntfs",      ModuleReason.FILESYSTEM, source="default"),
    "f2fs":      ModuleSpec("f2fs",      ModuleReason.FILESYSTEM, source="default"),
    "overlay":   ModuleSpec("overlay",   ModuleReason.FILESYSTEM, source="default"),
    "squashfs":  ModuleSpec("squashfs",  ModuleReason.FILESYSTEM, source="default"),
    # Storage / block
    "ahci":      ModuleSpec("ahci",      ModuleReason.STORAGE, source="default"),
    "nvme":      ModuleSpec("nvme",      ModuleReason.STORAGE, source="default"),
    "virtio_blk":ModuleSpec("virtio_blk",ModuleReason.STORAGE, source="default"),
    "sd_mod":    ModuleSpec("sd_mod",    ModuleReason.STORAGE, source="default"),
    "ata_piix":  ModuleSpec("ata_piix",  ModuleReason.STORAGE, source="default"),
    # Crypto / dm
    "dm_mod":    ModuleSpec("dm_mod",    ModuleReason.CRYPTO, source="default"),
    "dm_crypt":  ModuleSpec("dm_crypt",  ModuleReason.CRYPTO, source="default"),
    "aes":       ModuleSpec("aes",       ModuleReason.CRYPTO, source="default"),
    "sha256":    ModuleSpec("sha256",    ModuleReason.CRYPTO, source="default"),
    # Network
    "e1000":     ModuleSpec("e1000",     ModuleReason.NETWORK, source="default"),
    "virtio_net":ModuleSpec("virtio_net",ModuleReason.NETWORK, source="default"),
    "r8169":     ModuleSpec("r8169",     ModuleReason.NETWORK, source="default"),
    # Keyboard / display
    "usbhid":    ModuleSpec("usbhid",    ModuleReason.USER_REQUEST, source="default"),
    "atkbd":     ModuleSpec("atkbd",     ModuleReason.USER_REQUEST, source="default"),
    "i915":      ModuleSpec("i915",      ModuleReason.USER_REQUEST, source="default"),
}


# Aliases used by autoprobe.
_ALIASES: Dict[str, List[str]] = {
    "ext4":      ["ext4"],
    "btrfs":     ["btrfs"],
    "xfs":       ["xfs"],
    "vfat":      ["vfat", "fat", "msdos"],
    "ntfs":      ["ntfs", "ntfs3"],
    "f2fs":      ["f2fs"],
    "overlay":   ["overlay"],
    "squashfs":  ["squashfs"],
    "ahci":      ["ahci", "ata_generic"],
    "nvme":      ["nvme", "nvme_core"],
    "virtio_blk":["virtio_blk"],
    "sd_mod":    ["sd_mod", "sdhci"],
    "ata_piix":  ["ata_piix", "ata_generic"],
    "dm_mod":    ["dm_mod", "dm-thin-pool", "dm-mirror"],
    "dm_crypt":  ["dm_crypt"],
    "aes":       ["aes", "aes_x86_64"],
    "sha256":    ["sha256", "sha256_generic"],
    "e1000":     ["e1000", "e1000e", "igb"],
    "virtio_net":["virtio_net"],
    "r8169":     ["r8169"],
}


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------

class ModuleResolver:
    """Decide which modules to load into the initrd."""

    def __init__(self, db: Optional[Dict[str, ModuleSpec]] = None) -> None:
        self.db: Dict[str, ModuleSpec] = dict(db or DEFAULT_MODULE_DB)
        self.selected: Dict[str, ModuleSpec] = {}

    # -- user input --------------------------------------------------------

    def from_user_config(self, names: List[str]) -> List[ModuleSpec]:
        """Use the explicit list provided by the user (the "ask" path)."""
        out: List[ModuleSpec] = []
        for name in names:
            spec = self._lookup(name)
            if spec is None:
                log.warning("user requested unknown module: %s", name)
                continue
            spec = ModuleSpec(
                name=spec.name,
                reason=ModuleReason.USER_REQUEST,
                parameters=dict(spec.parameters),
                dependencies=list(spec.dependencies),
                source="user",
            )
            self.selected[spec.name] = spec
            out.append(spec)
        log.info("resolver: %d modules added from user config", len(out))
        return out

    # -- autoprobe ---------------------------------------------------------

    def autoprobe(self, host_root: str = "/") -> List[ModuleSpec]:
        """Look at ``host_root``'s ``/proc`` and ``/sys`` to guess modules.

        This is the "auto-probing" path.  In
        UmerOS we can't actually read a real ``/proc`` so the function
        uses lightweight heuristics on file presence:

        * If ``/sys/firmware/efi`` exists we are on UEFI - no extra
          modules required, but we record the fact.
        * If a ``modules.dep`` file is present we scan it for the
          modules that match our aliases.
        * If nothing matches we return the empty list (caller decides
          whether to fall back to a default).
        """
        out: List[ModuleSpec] = []
        seen: Set[str] = set()

        # 1. /sys hints
        sys_root = Path(host_root) / "sys"
        if (sys_root / "firmware" / "efi").exists():
            log.debug("autoprobe: UEFI firmware detected")
        if (sys_root / "block").exists():
            # Block devices present - we need a storage module.
            for blk in (sys_root / "block").iterdir():
                if blk.name in seen:
                    continue
                seen.add(blk.name)
                if blk.name.startswith("nvme"):
                    self._add_if_known("nvme", ModuleReason.AUTOPROBE, out)
                elif blk.name.startswith("sd") or blk.name.startswith("vd"):
                    self._add_if_known("sd_mod", ModuleReason.AUTOPROBE, out)
                    self._add_if_known("virtio_blk", ModuleReason.AUTOPROBE, out)

        # 2. modules.dep scan
        modules_dep = Path(host_root) / "lib" / "modules"
        if modules_dep.exists():
            for dep_file in modules_dep.rglob("modules.dep"):
                try:
                    text = dep_file.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for line in text.splitlines():
                    head = line.split(":", 1)[0].strip()
                    base = os.path.basename(head).replace(".ko", "").replace(".ko.xz", "")
                    for canonical, aliases in _ALIASES.items():
                        if base in aliases or base == canonical:
                            self._add_if_known(canonical, ModuleReason.AUTOPROBE, out)

        # 3. /proc/version for arch hints
        proc_version = Path(host_root) / "proc" / "version"
        if proc_version.exists():
            try:
                text = proc_version.read_text(encoding="utf-8", errors="replace").lower()
                if "x86_64" in text or "amd64" in text:
                    self._add_if_known("aes", ModuleReason.AUTOPROBE, out)
            except OSError:
                pass

        # Deduplicate while preserving order.
        unique: List[ModuleSpec] = []
        seen_names: Set[str] = set()
        for spec in out:
            if spec.name in seen_names:
                continue
            seen_names.add(spec.name)
            unique.append(spec)
            self.selected[spec.name] = spec
        log.info("resolver: autoprobe selected %d modules", len(unique))
        return unique

    # -- hybrid -----------------------------------------------------------

    def hybrid(self, host_root: str = "/",
               extras: Optional[List[str]] = None) -> List[ModuleSpec]:
        """Combine autoprobe with the user's additional requests."""
        base = self.autoprobe(host_root)
        if extras:
            self.from_user_config(extras)
        return base + [s for s in self.selected.values() if s.reason == ModuleReason.USER_REQUEST]

    # -- introspection ----------------------------------------------------

    def list_selected(self) -> List[ModuleSpec]:
        return list(self.selected.values())

    def export(self) -> List[dict]:
        return [s.as_dict() for s in self.selected.values()]

    def to_json(self) -> str:
        return json.dumps(self.export(), indent=2)

    # -- internals --------------------------------------------------------

    def _lookup(self, name: str) -> Optional[ModuleSpec]:
        if name in self.db:
            return self.db[name]
        for canonical, aliases in _ALIASES.items():
            if name in aliases:
                return self.db.get(canonical)
        return None

    def _add_if_known(self, name: str, reason: ModuleReason,
                      out: List[ModuleSpec]) -> None:
        spec = self._lookup(name)
        if spec is None:
            return
        out.append(ModuleSpec(
            name=spec.name,
            reason=reason,
            parameters=dict(spec.parameters),
            dependencies=list(spec.dependencies),
            source="autoprobe",
        ))


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def detect_rootfstype(probe_path: str) -> Optional[str]:
    """Best-effort root FS type detection from a ``blkid``-like string."""
    if not probe_path:
        return None
    text = probe_path.lower()
    for fs in ("btrfs", "xfs", "ext4", "ext3", "ext2", "vfat", "ntfs", "f2fs", "overlay"):
        if fs in text:
            return fs
    return None


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    r = ModuleResolver()
    r.from_user_config(["ext4", "ahci", "unknown_module"])
    if "ext4" not in r.selected or "ahci" not in r.selected:
        return False
    if "unknown_module" in r.selected:
        return False
    r2 = ModuleResolver()
    r2.from_user_config(["ext4", "dm_crypt", "ahci"])
    seen_reasons = {s.reason for s in r2.list_selected()}
    return ModuleReason.USER_REQUEST in seen_reasons


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("module_resolver selftest:", "OK" if _selftest() else "FAIL")
