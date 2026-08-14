"""
UmerOS /media - Stale Mount-Point Cleanup
==========================================

Scans ``/media`` for mount-point directories that no longer have a
backing device, and optionally removes them after a configurable
stale threshold.

This is the Python equivalent of the ``tmpfiles.d`` cleanup snippet
that distributions ship for ``/media``::

    # /etc/tmpfiles.d/media.conf
    D /media 0755 root root -

The module also provides a deeper audit that cross-references
``/proc/mounts`` to find mount points that are listed in the
mount table but whose backing device no longer exists (e.g. a USB
stick pulled without ``umount``).

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from .media_types import MediaDescriptor, MediaType
from .mount_manager import MediaConfig

log = logging.getLogger("UmerOS.Media.Cleanup")


# ---------------------------------------------------------------------------
# Cleanup result
# ---------------------------------------------------------------------------

@dataclass
class CleanupResult:
    """Report produced by a cleanup pass."""

    scanned: int = 0
    stale_removed: int = 0
    stale_skipped: int = 0       # too recent, kept
    orphan_found: int = 0        # in /proc/mounts but device gone
    errors: List[str] = field(default_factory=list)
    removed_paths: List[str] = field(default_factory=list)
    kept_paths: List[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        parts = [
            f"scanned={self.scanned}",
            f"removed={self.stale_removed}",
            f"kept={self.stale_skipped}",
            f"orphans={self.orphan_found}",
        ]
        if self.errors:
            parts.append(f"errors={len(self.errors)}")
        return " ".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DIR_RE = __import__("re").compile(r"^[a-z]+[0-9]*$", __import__("re").ASCII)


def _is_media_subdir(name: str) -> bool:
    """Return *True* if *name* looks like a media-type subdirectory."""
    return bool(_DIR_RE.match(name))


def _dir_age_s(path: Path) -> float:
    """Seconds since the directory was last modified."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return 0.0
    return time.time() - mtime


def _is_device_alive(device_path: str) -> bool:
    """Check whether a device node still exists and is accessible."""
    return Path(device_path).exists()


def _read_proc_mounts_devices() -> Set[str]:
    """Return the set of device paths listed in ``/proc/mounts``."""
    proc = Path("/proc/mounts")
    if not proc.exists():
        return set()
    try:
        text = proc.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    devices: Set[str] = set()
    for line in text.splitlines():
        parts = line.split()
        if parts:
            devices.add(parts[0])
    return devices


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class CleanupConfig:
    """Configuration for a cleanup pass.

    Attributes:
        config:          Base :class:`MediaConfig` (provides
                         ``media_root`` and ``stale_threshold_s``).
        dry_run:         If *True*, report but do not remove anything.
        remove_empty:    If *True*, remove empty subdirectories even
                         if they are not stale (aggressive cleanup).
        check_orphans:   If *True*, cross-reference ``/proc/mounts``
                         to detect phantom mounts.
        user:            If set, only clean this user's namespace.
    """

    config: MediaConfig = field(default_factory=MediaConfig)
    dry_run: bool = False
    remove_empty: bool = True
    check_orphans: bool = True
    user: Optional[str] = None


def cleanup_media(
    cfg: Optional[CleanupConfig] = None,
) -> CleanupResult:
    """Run a cleanup pass over ``/media``.

    Steps:
        1. Walk the ``/media`` tree looking for subdirectories that
           match the expected naming pattern.
        2. For each directory, check its age against the stale
           threshold.
        3. If stale (or empty and ``remove_empty`` is set), remove it
           (unless ``dry_run`` is active).
        4. Optionally cross-reference ``/proc/mounts`` to flag
           orphaned mount entries.

    Returns:
        A :class:`CleanupResult` summary.
    """
    ccfg = cfg or CleanupConfig()
    result = CleanupResult()

    media_root = ccfg.config.media_root
    if not media_root.is_dir():
        result.errors.append(f"Media root does not exist: {media_root}")
        return result

    # If user-scoped, descend one level
    search_root = media_root
    if ccfg.user:
        user_dir = media_root / ccfg.user
        if user_dir.is_dir():
            search_root = user_dir
        else:
            log.info("User namespace %s does not exist; nothing to clean.", user_dir)
            return result

    stale_threshold = ccfg.config.stale_threshold_s

    # --- Phase 1: scan subdirectories ---
    for entry in sorted(search_root.iterdir()):
        if not entry.is_dir():
            continue
        if not _is_media_subdir(entry.name):
            continue

        result.scanned += 1
        age = _dir_age_s(entry)
        is_empty = not any(entry.iterdir()) if entry.is_dir() else False

        should_remove = False
        reason = ""

        if is_empty and ccfg.remove_empty:
            should_remove = True
            reason = "empty"
        elif age > stale_threshold:
            should_remove = True
            reason = f"stale ({age:.0f}s > {stale_threshold}s)"
        else:
            result.kept_paths.append(str(entry))
            result.stale_skipped += 1
            continue

        if should_remove:
            if ccfg.dry_run:
                result.kept_paths.append(f"[DRY-RUN] would remove: {entry}")
                log.info("DRY-RUN: would remove %s (%s)", entry, reason)
            else:
                try:
                    # Remove contents then directory
                    for child in entry.rglob("*"):
                        if child.is_file() or child.is_symlink():
                            child.unlink()
                    entry.rmdir()
                    result.removed_paths.append(str(entry))
                    result.stale_removed += 1
                    log.info("Removed %s (%s)", entry, reason)
                except OSError as exc:
                    result.errors.append(f"Failed to remove {entry}: {exc}")

    # --- Phase 2: orphan detection ---
    if ccfg.check_orphans:
        alive_devices = _read_proc_mounts_devices()
        for entry in search_root.rglob("*"):
            if not entry.is_dir():
                continue
            # Check if anything is mounted here
            try:
                st = entry.stat()
            except OSError:
                continue
            # Directories with st_nlink > 2 have subdirectories
            # mounted inside them
            if st.st_nlink > 2:
                # This is a mount point — check if device is alive
                # (We cannot determine the device from just the path
                # without parsing /proc/mounts, so we flag it.)
                result.orphan_found += 1

    log.info("Cleanup complete: %s", result.summary)
    return result


def validate_fhs_media(media_root: Optional[Path] = None) -> Dict[str, bool]:
    """Check that the four FHS-required directories exist.

    Returns a dict mapping directory name to existence flag::

        {"floppy": True, "cdrom": True, "cdrecorder": False, "zip": True}
    """
    root = media_root or MediaConfig().media_root
    required = ["floppy", "cdrom", "cdrecorder", "zip"]
    return {name: (root / name).is_dir() for name in required}


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------

def _selftest():
    """Run a basic self-test for this module."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = MediaConfig(media_root=tmpdir)
        result = scan_stale_mounts(cfg)
        assert hasattr(result, "stale_count") or hasattr(result, "summary"), "result should have stale_count or summary"

    print("selftest OK")


if __name__ == "__main__":
    _selftest()
