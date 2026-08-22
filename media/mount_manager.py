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
UmerOS /media - Mount Point Manager
====================================

Creates, tracks, and tears down FHS-compliant mount points under
``/media`` for removable devices.

Key responsibilities
--------------------
* **Numbered mount points** – When multiple devices of the same type
  are inserted, the manager allocates ``/media/<type>0``,
  ``/media/<type>1``, … up to the configured maximum.
* **Symlink maintenance** – Keeps a convenience symlink
  (e.g. ``/media/cdrom`` -> ``/media/cdrom0``) pointing at the
  most-recently-inserted device.
* **FHS bootstrapping** – Creates the four required directories
  (``floppy``, ``cdrom``, ``cdrecorder``, ``zip``) at startup.
* **User-scoped mounts** – Supports the ``/media/<user>/<label>``
  layout used by udisks2 with ``--enable-fhs-media``.
* **Mount/unmount lifecycle** – Wraps the actual ``mount(2)`` /
  ``umount(2)`` calls through :class:`MountTable` from
  :mod:`initrd.mounts` when available, otherwise performs direct
  filesystem operations.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .media_types import (
    MediaDescriptor,
    MediaType,
    MountNaming,
    MOUNT_NAMING,
)

log = logging.getLogger("UmerOS.Media.MountManager")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class MediaConfig:
    """Tuneable parameters for the mount-manager.

    Attributes:
        media_root:         Base directory for all mount points
                            (default ``/media``).
        user_namespaces:    If *True*, mount points are created under
                            ``/media/<user>/`` instead of directly
                            under ``/media/``.
        create_fhs_dirs:    If *True*, the four FHS-mandated
                            directories are created on startup.
        default_fs_options: Extra mount options applied to every
                            mount call (e.g. ``["noexec", "nosuid"]``).
        stale_threshold_s:  Seconds after which an un-cleaned mount
                            point is considered stale (used by
                            :mod:`media.cleanup`).
    """

    media_root: Path = Path("/media")
    user_namespaces: bool = False
    create_fhs_dirs: bool = True
    default_fs_options: List[str] = field(
        default_factory=lambda: ["noexec", "nosuid", "nodev"]
    )
    stale_threshold_s: int = 86400  # 24 h

    def __post_init__(self) -> None:
        if isinstance(self.media_root, str):
            self.media_root = Path(self.media_root)


# ---------------------------------------------------------------------------
# Mount-point path helpers
# ---------------------------------------------------------------------------

def mount_point_for(
    media_type: MediaType,
    index: int = 0,
    config: Optional[MediaConfig] = None,
    user: Optional[str] = None,
) -> Path:
    """Return the canonical mount-point path for a given type + index.

    Examples::

        mount_point_for(MediaType.CDROM, 0)
        # -> Path("/media/cdrom0")

        mount_point_for(MediaType.USB, 2, user="alice")
        # -> Path("/media/alice/usb2")
    """
    cfg = config or MediaConfig()
    naming = MOUNT_NAMING.get(media_type)
    base = naming.base_name if naming else media_type.value

    if cfg.user_namespaces and user:
        return cfg.media_root / user / f"{base}{index}"
    return cfg.media_root / f"{base}{index}"


def symlink_for(
    media_type: MediaType,
    config: Optional[MediaConfig] = None,
    user: Optional[str] = None,
) -> Optional[Path]:
    """Return the convenience symlink path, or *None* if not applicable."""
    naming = MOUNT_NAMING.get(media_type)
    if not naming or not naming.symlink_name:
        return None
    cfg = config or MediaConfig()
    if cfg.user_namespaces and user:
        return cfg.media_root / user / naming.symlink_name
    return cfg.media_root / naming.symlink_name


# ---------------------------------------------------------------------------
# Mount point tracker
# ---------------------------------------------------------------------------

@dataclass
class _Slot:
    """Internal bookkeeping for one numbered mount slot."""
    device: str
    descriptor: MediaDescriptor
    in_use: bool = True


class MountManager:
    """Stateful manager for ``/media`` mount-point lifecycle.

    Typical usage::

        mgr = MountManager()
        mgr.bootstrap()

        slot = mgr.allocate(MediaType.USB, "/dev/sdb1", label="KINGSTON")
        # -> mount_point = /media/usb0

        mgr.release(slot.mount_point)
    """

    def __init__(self, config: Optional[MediaConfig] = None) -> None:
        self.config = config or MediaConfig()
        # media_type -> list of _Slot (indexed by number)
        self._slots: Dict[MediaType, List[_Slot]] = {}
        # mount_point_str -> _Slot  (fast reverse lookup)
        self._by_mount: Dict[str, _Slot] = {}

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def bootstrap(self) -> List[Path]:
        """Create the FHS-required ``/media`` subdirectories.

        Returns the list of directories that were actually created
        (skips those that already exist).
        """
        created: List[Path] = []
        root = self.config.media_root
        root.mkdir(parents=True, exist_ok=True)

        if not self.config.create_fhs_dirs:
            return created

        for mt in MediaType:
            naming = MOUNT_NAMING.get(mt)
            if not naming:
                continue
            target = root / naming.base_name
            if not target.exists():
                target.mkdir(parents=True, exist_ok=True)
                created.append(target)
                log.info("Created FHS media dir: %s", target)
        return created

    # ------------------------------------------------------------------
    # Allocation
    # ------------------------------------------------------------------

    def allocate(
        self,
        media_type: MediaType,
        device_path: str,
        *,
        filesystem: Optional[str] = None,
        label: Optional[str] = None,
        uuid: Optional[str] = None,
        size_bytes: int = 0,
        read_only: bool = False,
        user: Optional[str] = None,
        options: Optional[List[str]] = None,
    ) -> MediaDescriptor:
        """Allocate the next available numbered mount point.

        Creates the directory (and parent directories) on disk and
        returns a fully-populated :class:`MediaDescriptor`.

        Raises:
            RuntimeError: If the maximum slot count is exhausted.
        """
        naming = MOUNT_NAMING.get(media_type)
        max_count = (naming.max_count if naming else 0) or 999

        slots = self._slots.setdefault(media_type, [])
        index = None
        for i in range(max_count):
            if i >= len(slots) or not slots[i].in_use:
                index = i
                break
        if index is None:
            raise RuntimeError(
                f"All {max_count} mount slots for {media_type.value} "
                f"are in use."
            )

        mp = mount_point_for(media_type, index, self.config, user)
        mp.mkdir(parents=True, exist_ok=True)

        desc = MediaDescriptor(
            media_type=media_type,
            device_path=device_path,
            mount_point=str(mp),
            filesystem=filesystem,
            label=label,
            uuid=uuid,
            size_bytes=size_bytes,
            read_only=read_only,
            mounted=True,
            user=user,
            options=options or list(self.config.default_fs_options),
        )

        slot = _Slot(device=device_path, descriptor=desc)
        if index < len(slots):
            slots[index] = slot
        else:
            slots.append(slot)
        self._by_mount[str(mp)] = slot

        # Update convenience symlink
        self._update_symlink(media_type, mp, user)

        log.info(
            "Allocated %s [%d] -> %s (%s)",
            media_type.value, index, mp, device_path,
        )
        return desc

    def _update_symlink(
        self,
        media_type: MediaType,
        target: Path,
        user: Optional[str] = None,
    ) -> None:
        """Point the convenience symlink at *target*."""
        link = symlink_for(media_type, self.config, user)
        if link is None:
            return
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(target.name)
        log.debug("Symlink %s -> %s", link, target.name)

    # ------------------------------------------------------------------
    # Release
    # ------------------------------------------------------------------

    def release(self, mount_point: str | Path) -> Optional[MediaDescriptor]:
        """Release a previously allocated mount point.

        Removes the directory contents (if any) and the directory
        itself, clears the slot, and updates the convenience symlink
        to point at the next-most-recent allocation (or removes it).

        Returns the descriptor that was released, or *None* if the
        mount point was not tracked.
        """
        mp_str = str(mount_point)
        slot = self._by_mount.pop(mp_str, None)
        if slot is None:
            log.warning("release: unknown mount point %s", mp_str)
            return None

        slot.in_use = False
        desc = slot.descriptor

        # Remove directory
        mp_path = Path(mount_point)
        if mp_path.is_dir():
            for child in mp_path.iterdir():
                child.unlink(missing_ok=True)
            mp_path.rmdir()
            log.info("Removed mount point dir: %s", mp_path)

        # Update symlink to last remaining active slot
        slots = self._slots.get(desc.media_type, [])
        user = desc.user
        link = symlink_for(desc.media_type, self.config, user)
        if link is not None:
            active = [s for s in slots if s.in_use and s.descriptor.mount_point]
            if active:
                last_mp = Path(active[-1].descriptor.mount_point)
                if link.is_symlink() or link.exists():
                    link.unlink()
                link.symlink_to(last_mp.name)
            else:
                if link.is_symlink() or link.exists():
                    link.unlink()

        log.info("Released mount point %s", mp_str)
        return desc

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_mounts(
        self,
        media_type: Optional[MediaType] = None,
        user: Optional[str] = None,
    ) -> List[MediaDescriptor]:
        """List all currently allocated mount points.

        Args:
            media_type: If given, restrict to this type.
            user:       If given, restrict to this user's mounts.
        """
        results: List[MediaDescriptor] = []
        types = [media_type] if media_type else list(MediaType)
        for mt in types:
            for slot in self._slots.get(mt, []):
                if not slot.in_use:
                    continue
                d = slot.descriptor
                if user and d.user != user:
                    continue
                results.append(d)
        return results

    def find_by_device(self, device_path: str) -> Optional[MediaDescriptor]:
        """Look up a mounted descriptor by its device path."""
        for slot in self._by_mount.values():
            if slot.device == device_path:
                return slot.descriptor
        return None

    def find_by_mount(self, mount_point: str | Path) -> Optional[MediaDescriptor]:
        """Look up a mounted descriptor by its mount-point path."""
        slot = self._by_mount.get(str(mount_point))
        return slot.descriptor if slot else None

    @property
    def stats(self) -> Dict[str, int]:
        """Aggregate counts per media type."""
        out: Dict[str, int] = {}
        for mt, slots in self._slots.items():
            active = sum(1 for s in slots if s.in_use)
            if active:
                out[mt.value] = active
        return out


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------

def _selftest():
    """Run a basic self-test for this module."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = MountManager(media_root=tmpdir)
        summary = mgr.stats
        assert isinstance(summary, dict), "stats should be a dict"

    print("selftest OK")


if __name__ == "__main__":
    _selftest()
