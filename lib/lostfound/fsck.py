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
FilesystemChecker (fsck) — Simulates e2fsck's 5-phase consistency check.

Phases (matching e2fsprogs pass ordering):

  Phase 1  — Superblock and inode bitmap consistency.
             * Validate the superblock is sane.
             * Verify every allocated inode has a sane type and size.

  Phase 2  — Directory structure and link-count check.
             * Walk every directory's dirent list.
             * Compare each inode's recorded ``nlinks`` against the number
               of directory entries that reference it.

  Phase 3  — Orphan scan.
             * An inode is an orphan if it is allocated, not corrupted,
               and not referenced by any directory entry (or has nlinks=0).
             * Corrupted inodes are flagged but cannot be recovered.

  Phase 4  — lost+found verification.
             * Ensure the lost+found directory exists (recreate if missing).
             * Warn if it has no preallocated blocks (mklost+found needed).

  Phase 5  — Recovery.
             * Move all discovered orphans into lost+found.

Reference: man 8 fsck, man 8 e2fsck.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .inode import Inode, InodeType
from .orphan import OrphanedInode
from .superblock import FsState, SuperBlock

log = logging.getLogger("UmerOS.fsck")


# --------------------------------------------------------------------------- #
# Structured report
# --------------------------------------------------------------------------- #

@dataclass
class FsckReport:
    """Structured result of a single fsck run.

    Mirrors the kind of summary that ``fsck`` prints to the console at the
    end of a check, but as a typed object.
    """

    # Timing
    started_at:  float = field(default_factory=time.time)
    finished_at: float = 0.0

    # Flags
    forced:                bool = False
    auto_repair:           bool = True
    filesystem_clean:      bool = True
    errors_found:          int  = 0
    errors_fixed:          int  = 0

    # Phase results
    superblock_ok:         bool = True
    inode_bitmap_ok:       bool = True
    link_count_mismatches: int  = 0
    orphan_count:          int  = 0
    corrupted_count:       int  = 0

    # Recovery
    lost_found_existed:    bool = True
    lost_found_recreated:  bool = False
    lost_found_prealloc:   bool = True
    recovered_count:       int  = 0
    recovered_names:       List[str] = field(default_factory=list)

    # Diagnostic lists
    errors:       List[str] = field(default_factory=list)
    warnings:     List[str] = field(default_factory=list)
    orphans:      List[Dict[str, Any]] = field(default_factory=list)
    actions:      List[str] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.finished_at - self.started_at)

    def add_error(self, msg: str, fixed: bool = False) -> None:
        self.errors_found += 1
        self.errors.append(msg)
        self.filesystem_clean = False
        if fixed:
            self.errors_fixed += 1
            self.actions.append(f"FIXED: {msg}")
        else:
            log.error("fsck: %s", msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)
        log.warning("fsck: %s", msg)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "started_at":              self.started_at,
            "finished_at":             self.finished_at,
            "duration_seconds":        round(self.duration_seconds, 6),
            "forced":                  self.forced,
            "auto_repair":             self.auto_repair,
            "filesystem_clean":        self.filesystem_clean,
            "errors_found":            self.errors_found,
            "errors_fixed":            self.errors_fixed,
            "superblock_ok":           self.superblock_ok,
            "inode_bitmap_ok":         self.inode_bitmap_ok,
            "link_count_mismatches":   self.link_count_mismatches,
            "orphan_count":            self.orphan_count,
            "corrupted_count":         self.corrupted_count,
            "lost_found_existed":      self.lost_found_existed,
            "lost_found_recreated":    self.lost_found_recreated,
            "lost_found_prealloc":     self.lost_found_prealloc,
            "recovered_count":         self.recovered_count,
            "recovered_names":         list(self.recovered_names),
            "errors":                  list(self.errors),
            "warnings":                list(self.warnings),
            "orphans":                 list(self.orphans),
            "actions":                 list(self.actions),
        }

    def summary(self) -> str:
        """Return a short human-readable summary line."""
        status = "clean" if self.filesystem_clean else "errors"
        return (
            f"fsck: filesystem {status} "
            f"({self.errors_found} errors, {self.errors_fixed} fixed, "
            f"{self.orphan_count} orphans, {self.recovered_count} recovered "
            f"in {self.duration_seconds:.3f}s)"
        )

    def full_report(self) -> str:
        """Return a multi-line human-readable report."""
        lines = [
            "==== fsck report ====",
            f"  status:           {'CLEAN' if self.filesystem_clean else 'ERRORS'}",
            f"  duration:         {self.duration_seconds:.4f}s",
            f"  errors found:     {self.errors_found}",
            f"  errors fixed:     {self.errors_fixed}",
            f"  superblock ok:    {self.superblock_ok}",
            f"  inode bitmap ok:  {self.inode_bitmap_ok}",
            f"  link mismatches:  {self.link_count_mismatches}",
            f"  orphans found:    {self.orphan_count}",
            f"  corrupted inodes: {self.corrupted_count}",
            f"  lost+found:       "
            f"{'existed' if self.lost_found_existed else 'recreated'}, "
            f"preallocated={self.lost_found_prealloc}",
            f"  recovered:        {self.recovered_count}",
        ]
        if self.recovered_names:
            lines.append("  recovered names:  " + ", ".join(self.recovered_names))
        if self.errors:
            lines.append("  errors:")
            for e in self.errors:
                lines.append(f"    - {e}")
        if self.warnings:
            lines.append("  warnings:")
            for w in self.warnings:
                lines.append(f"    - {w}")
        if self.actions:
            lines.append("  actions taken:")
            for a in self.actions:
                lines.append(f"    - {a}")
        lines.append("=====================")
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# The checker
# --------------------------------------------------------------------------- #

class FilesystemChecker:
    """Simulated ``e2fsck`` / ``fsck``.

    Args:
        partition: The :class:`~lib.lostfound.partition.FilesystemPartition`
                   to check.
        auto_repair: If True (default), automatically fix problems and
                     recover orphans.  If False, only report.
    """

    def __init__(self, partition: Any, auto_repair: bool = True) -> None:
        self.partition = partition
        self.auto_repair: bool = auto_repair

    # ------------------------------------------------------------------ #
    # Public entry point
    # ------------------------------------------------------------------ #

    def check(self, force: bool = False) -> FsckReport:
        """Run a full fsck pass.

        Args:
            force: Run even if the superblock says the FS is clean
                   (equivalent to ``fsck -f``).

        Returns:
            A :class:`FsckReport`.
        """
        report = FsckReport(
            forced=force,
            auto_repair=self.auto_repair,
            started_at=time.time(),
        )

        sb: SuperBlock = self.partition.superblock

        # Decide whether to run at all.
        if not force and not sb.needs_check():
            report.add_warning(
                "filesystem is clean; skipping (use force=True to override)."
            )
            report.finished_at = time.time()
            return report

        log.info("fsck: starting check on %s (force=%s).",
                 getattr(self.partition, "mount_point", "?"), force)

        # --- Phase 1: superblock + inode bitmap ---
        self._phase1_superblock(report)

        # --- Phase 2: directory + link-count check ---
        self._phase2_links(report)

        # --- Phase 3: orphan scan ---
        orphans = self._phase3_orphans(report)

        # --- Phase 4: lost+found verification ---
        self._phase4_lost_found(report)

        # --- Phase 5: recovery ---
        if self.auto_repair and orphans:
            self._phase5_recover(report, orphans)

        # Finalise.
        # The filesystem is clean if: superblock/inode-bitmap are OK, no
        # *unresolved* orphans remain (i.e. every recoverable orphan was
        # recovered), and there are no unfixed errors.
        unresolved_orphans = report.orphan_count - report.recovered_count
        all_resolved = (
            report.superblock_ok
            and unresolved_orphans == 0
            and report.errors_found == report.errors_fixed
        )
        if all_resolved:
            sb.mark_clean()
            report.filesystem_clean = True
            report.actions.append("superblock marked CLEAN")
        else:
            sb.mark_errors(
                f"fsck found unresolved issues "
                f"({unresolved_orphans} unrecovered orphans, "
                f"{report.errors_found - report.errors_fixed} unfixed errors)"
            )
            report.filesystem_clean = False

        report.finished_at = time.time()
        log.info("fsck: %s", report.summary())
        return report

    # ------------------------------------------------------------------ #
    # Phase 1 — superblock + inode bitmap
    # ------------------------------------------------------------------ #

    def _phase1_superblock(self, report: FsckReport) -> None:
        sb = self.partition.superblock
        log.debug("fsck Phase 1: superblock + inode bitmap.")

        # Validate superblock geometry.
        if sb.total_inodes <= 0:
            report.add_error("superblock: total_inodes <= 0")
            report.superblock_ok = False
        if sb.total_blocks <= 0:
            report.add_error("superblock: total_blocks <= 0")
            report.superblock_ok = False
        if sb.free_inodes > sb.total_inodes:
            report.add_error(
                f"superblock: free_inodes ({sb.free_inodes}) > total "
                f"({sb.total_inodes})",
                fixed=self.auto_repair,
            )
            if self.auto_repair:
                sb.free_inodes = sb.total_inodes - self.partition.used_inode_count()
        if sb.free_blocks > sb.total_blocks:
            report.add_error(
                f"superblock: free_blocks ({sb.free_blocks}) > total "
                f"({sb.total_blocks})",
                fixed=self.auto_repair,
            )
            if self.auto_repair:
                sb.free_blocks = sb.total_blocks - self.partition.used_block_count()

        # Validate every allocated inode has a sane type.
        bad = 0
        for ino, inode in self.partition.iter_inodes():
            if not inode.allocated:
                continue
            try:
                _ = InodeType(inode.type) if not isinstance(inode.type, InodeType) else inode.type
            except ValueError:
                report.add_error(
                    f"inode {ino}: invalid type field",
                    fixed=self.auto_repair,
                )
                if self.auto_repair:
                    inode.corrupted = True
                bad += 1
            if inode.size < 0:
                report.add_error(
                    f"inode {ino}: negative size",
                    fixed=self.auto_repair,
                )
                if self.auto_repair:
                    inode.size = 0
                bad += 1

        if bad == 0:
            report.inode_bitmap_ok = True
        else:
            report.inode_bitmap_ok = False

    # ------------------------------------------------------------------ #
    # Phase 2 — directory structure + link counts
    # ------------------------------------------------------------------ #

    def _phase2_links(self, report: FsckReport) -> None:
        log.debug("fsck Phase 2: directory + link counts.")

        # Count how many directory entries reference each inode.
        ref_counts: Dict[int, int] = {}
        for ino, inode in self.partition.iter_inodes():
            if not inode.allocated:
                continue
            if inode.type == InodeType.DIRECTORY:
                for name, target_ino in inode.list_dirents():
                    ref_counts[target_ino] = ref_counts.get(target_ino, 0) + 1

        # Compare against recorded nlinks.
        for ino, inode in self.partition.iter_inodes():
            if not inode.allocated or inode.corrupted:
                continue
            actual = ref_counts.get(ino, 0)
            # Every directory implicitly has 2 links (. and parent entry);
            # every other inode has at least the dirent that names it.
            # We just check for gross mismatches.
            if inode.type == InodeType.DIRECTORY:
                # A directory's real link count = subdirs + 2 (self + parent).
                # In this sim we approximate: at least 1 (its parent's entry).
                expected_min = 1
            else:
                expected_min = 1

            if actual == 0 and inode.nlinks > 0:
                # The inode thinks it is linked but no directory references it.
                # This is the orphan condition — leave for Phase 3.
                continue
            if inode.nlinks < expected_min and actual >= expected_min:
                report.link_count_mismatches += 1
                report.add_error(
                    f"inode {ino}: nlinks ({inode.nlinks}) < references ({actual})",
                    fixed=self.auto_repair,
                )
                if self.auto_repair:
                    inode.nlinks = actual
            elif inode.nlinks != actual and actual > 0:
                # Minor mismatch — record but don't always error.
                report.link_count_mismatches += 1
                if self.auto_repair:
                    inode.nlinks = actual
                    report.actions.append(
                        f"inode {ino}: nlinks corrected {inode.nlinks}->{actual}"
                    )

    # ------------------------------------------------------------------ #
    # Phase 3 — orphan scan
    # ------------------------------------------------------------------ #

    def _phase3_orphans(self, report: FsckReport) -> List[OrphanedInode]:
        log.debug("fsck Phase 3: orphan scan.")

        # Build the set of inodes referenced by *any* directory entry.
        referenced: set = set()
        for ino, inode in self.partition.iter_inodes():
            if inode.type == InodeType.DIRECTORY:
                for name, target_ino in inode.list_dirents():
                    referenced.add(target_ino)

        orphans: List[OrphanedInode] = []
        root_ino = getattr(self.partition, "root_ino", 1)

        for ino, inode in self.partition.iter_inodes():
            if not inode.allocated:
                continue
            if ino == root_ino:
                continue   # the root directory is never an orphan

            if inode.corrupted:
                report.corrupted_count += 1
                report.add_error(
                    f"inode {ino}: corrupted — cannot recover"
                )
                orphans.append(OrphanedInode(inode, OrphanedInode.REASON_CORRUPTED))
                continue

            if ino not in referenced and inode.nlinks == 0:
                reason = OrphanedInode.REASON_NLINKS_ZERO
            elif ino not in referenced:
                reason = OrphanedInode.REASON_NO_DIRENT
            elif inode.deleted and inode.nlinks == 0:
                reason = OrphanedInode.REASON_DELETED_ALLOCATED
            else:
                continue

            report.orphan_count += 1
            o = OrphanedInode(inode, reason)
            orphans.append(o)
            report.orphans.append(o.to_dict())
            report.add_warning(
                f"inode {ino}: orphan ({reason}) — will be recovered"
            )

        return orphans

    # ------------------------------------------------------------------ #
    # Phase 4 — lost+found verification
    # ------------------------------------------------------------------ #

    def _phase4_lost_found(self, report: FsckReport) -> None:
        log.debug("fsck Phase 4: lost+found verification.")
        lf = self.partition.lost_found

        if not lf.exists:
            report.lost_found_existed = False
            report.add_warning(
                "lost+found missing — fsck will recreate it "
                "(without preallocated blocks; run mklost+found)."
            )
            if self.auto_repair:
                lf.recreate_without_prealloc()
                report.lost_found_recreated = True
                report.lost_found_prealloc = False
        else:
            report.lost_found_existed = True
            report.lost_found_prealloc = lf.has_preallocated_blocks
            if not lf.has_preallocated_blocks:
                report.add_warning(
                    "lost+found has no preallocated blocks — "
                    "run mklost+found for robust recovery."
                )

    # ------------------------------------------------------------------ #
    # Phase 5 — recovery
    # ------------------------------------------------------------------ #

    def _phase5_recover(
        self, report: FsckReport, orphans: List[OrphanedInode]
    ) -> None:
        log.debug("fsck Phase 5: recovering %d orphans.", len(orphans))
        lf = self.partition.lost_found

        for o in orphans:
            if not o.is_recoverable:
                report.add_warning(
                    f"inode {o.inode.ino}: skipped (corrupted/unrecoverable)"
                )
                continue
            name = lf.recover(o)
            if name is not None:
                report.recovered_count += 1
                report.recovered_names.append(name)
                report.actions.append(
                    f"inode {o.inode.ino}: linked as {lf.path}/{name}"
                )
            else:
                report.add_error(
                    f"inode {o.inode.ino}: recovery failed"
                )
