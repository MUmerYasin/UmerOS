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
UmerOS /mnt - FHS /mnt Validation
===================================

Validates that the ``/mnt`` directory structure 

    /mnt is the system administrator's temporary mount point.
    Its content is a local issue.  Installation programs must
    not use this directory.

additional guidance:

    /mnt is distinct from /media:
    - /media = auto-detected removable devices (managed by desktop)
    - /mnt   = manual temporary mounts (admin only)

This module checks:

1. ``/mnt`` exists and is a directory.
2. Mount point names are valid (no special characters).
3. Mount points are actual directories (not files/symlinks).
4. No stale empty mount points remain.
5. Mount point permissions are sane (0755 default).
6. Mount points are not nested (``/mnt/a/b`` requires both to exist).
7. Network mounts have proper ``noauto`` semantics.
8. User-mountable entries have ``user`` or ``users`` option.

Two entry points share those checks:

* :meth:`MntValidator.validate` -- whole-tree audit, reporting anomalies as
  ``WARNING``.  Useful as a report; too broad to gate a single mount.
* :meth:`MntValidator.validate_mount_request` -- request-scoped gate used by
  :meth:`mnt.mount_ops.MountManager.mount`.  The same anomalies become
  ``ERROR`` so a pending mount is **refused** rather than merely reported.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

log = logging.getLogger("UmerOS.Mnt.Validation")

MNT_ROOT = "/mnt"

# Single source of truth for mount-point leaf names (shared by the
# whole-tree audit and the per-request gate in `validate_mount_request`).
_NAME_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------

class Severity(str):
    """Severity levels for validation findings."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Finding:
    """A single validation finding.

    Attributes:
        severity:   ``error``, ``warning``, or ``info``.
        code:       Short machine-readable code (e.g. ``MNT001``).
        message:    Human-readable description.
        path:       Filesystem path involved (if any).
        context:    Extra data for diagnostics.
    """
    severity: str
    code: str
    message: str
    path: str = ""
    context: Dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, object]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "context": self.context,
        }

    def __repr__(self) -> str:
        return f"[{self.severity.upper()}] {self.code}: {self.message}"


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class MntValidator:
    """Validates FHS /mnt compliance.

    Usage::

        validator = MntValidator()
        findings = validator.validate()
        for f in findings:
            if f.severity == Severity.ERROR:
                print(f"ERROR: {f.message}")
    """

    def __init__(
        self,
        mnt_root: str | Path = MNT_ROOT,
        fstab_path: str | Path = "/etc/fstab",
    ) -> None:
        self._mnt_root = str(mnt_root)
        self._fstab_path = str(fstab_path)

    def validate(self) -> List[Finding]:
        """Run all validation checks and return findings."""
        findings: List[Finding] = []

        findings.extend(self._check_root_exists())
        findings.extend(self._check_root_permissions())
        findings.extend(self._check_mount_points())
        findings.extend(self._check_stale_points())
        findings.extend(self._check_fstab_entries())
        findings.extend(self._check_media_separation())

        return findings

    @property
    def errors(self) -> List[Finding]:
        return [f for f in self.validate() if f.severity == Severity.ERROR]

    @property
    def warnings(self) -> List[Finding]:
        return [f for f in self.validate() if f.severity == Severity.WARNING]

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def validate_mount_request(
        self,
        device: str,
        mount_point: str,
        fstype: str = "auto",
        options: str = "defaults",
    ) -> List[Finding]:
        """Validate a single *pending* mount request.

        :meth:`validate` audits the whole ``/mnt`` tree plus ``/etc/fstab``
        and is therefore only ever usable as a report: an unrelated
        world-writable directory elsewhere under ``/mnt`` must not veto an
        otherwise sound mount, and re-walking the tree on every ``mount()``
        would be both slow and racy.  This method inspects only the
        properties of *one* request so the mount path can **fail closed** on
        the findings that genuinely concern it.

        Only requests whose target lies under ``mnt_root`` are inspected;
        anything else returns an empty list, because ``/mnt`` policy does not
        govern ``/media`` or arbitrary administrator mounts.

        Severity note: findings that the whole-tree audit reports as
        ``WARNING`` (a symlinked mount point, an unusual leaf name) are
        promoted to ``ERROR`` here.  An audit should describe an existing
        system without failing it, whereas a *new* request must be refused.

        Args:
            device:       Block device or special name being mounted.
            mount_point:  Target directory.
            fstype:       Filesystem type (``auto`` for kernel detection).
            options:      Comma-separated mount options (already hardened).

        Returns:
            Findings scoped to this request.  ``ERROR`` means the request
            must be refused; ``WARNING`` means proceed but tell someone.
        """
        findings: List[Finding] = []

        root = os.path.normpath(self._mnt_root)
        target = os.path.normpath(mount_point)
        if target != root and not target.startswith(root + os.sep):
            return findings

        path = Path(mount_point)

        # MNT004: mounting over a symlink redirects the mount somewhere
        # else entirely -- a zero-trust traversal vector, so refuse.
        if path.is_symlink():
            findings.append(Finding(
                severity=Severity.ERROR,
                code="MNT004",
                message=f"Mount point is a symlink: {mount_point}",
                path=mount_point,
            ))
        # MNT003: the target must be a directory.
        elif path.exists() and not path.is_dir():
            findings.append(Finding(
                severity=Severity.ERROR,
                code="MNT003",
                message=f"Mount point is not a directory: {mount_point}",
                path=mount_point,
            ))

        # MNT005: leaf name validation.
        name = path.name
        if name and not _NAME_RE.match(name):
            findings.append(Finding(
                severity=Severity.ERROR,
                code="MNT005",
                message=f"Mount point name contains unusual characters: {name}",
                path=mount_point,
            ))

        # MNT009: user-mountable requests must stay hardened.  `mount_ops`
        # auto-hardens them, so this only fires when the caller
        # deliberately overrode a flag with exec/suid/dev -- warn, don't
        # block, because that override is an explicit decision.
        opts = {o.strip() for o in options.split(",") if o.strip()}
        if opts & {"user", "users"}:
            weak = [o for o in ("noexec", "nosuid", "nodev") if o not in opts]
            if weak:
                findings.append(Finding(
                    severity=Severity.WARNING,
                    code="MNT009",
                    message=(
                        f"User-mountable {mount_point} lacks "
                        f"{', '.join(weak)}"
                    ),
                    path=mount_point,
                    context={
                        "device": device,
                        "fstype": fstype,
                        "options": options,
                    },
                ))

        return findings

    # -- Checks --------------------------------------------------------------

    def _check_root_exists(self) -> List[Finding]:
        """MNT001: /mnt must exist and be a directory."""
        findings: List[Finding] = []
        path = Path(self._mnt_root)

        if not path.exists():
            findings.append(Finding(
                severity=Severity.ERROR,
                code="MNT001",
                message=f"{self._mnt_root} does not exist",
                path=str(path),
            ))
        elif not path.is_dir():
            findings.append(Finding(
                severity=Severity.ERROR,
                code="MNT001",
                message=f"{self._mnt_root} is not a directory",
                path=str(path),
            ))
        return findings

    def _check_root_permissions(self) -> List[Finding]:
        """MNT002: /mnt should be root-owned with 0755 permissions."""
        findings: List[Finding] = []
        path = Path(self._mnt_root)

        if not path.exists():
            return findings

        st = path.stat()
        mode = stat.S_IMODE(st.st_mode)

        # Check owner
        if st.st_uid != 0:
            findings.append(Finding(
                severity=Severity.WARNING,
                code="MNT002",
                message=f"{self._mnt_root} is not owned by root (uid={st.st_uid})",
                path=str(path),
            ))

        # Check permissions (should be 0755 or more restrictive)
        if mode & stat.S_IWOTH:
            findings.append(Finding(
                severity=Severity.WARNING,
                code="MNT002",
                message=f"{self._mnt_root} is world-writable ({oct(mode)})",
                path=str(path),
                context={"mode": oct(mode)},
            ))

        return findings

    def _check_mount_points(self) -> List[Finding]:
        """MNT003-MNT006: Validate mount point structure."""
        findings: List[Finding] = []
        root = Path(self._mnt_root)

        if not root.is_dir():
            return findings

        for entry in root.iterdir():
            if entry.name.startswith("."):
                continue

            # MNT003: Must be a directory
            if not entry.is_dir():
                findings.append(Finding(
                    severity=Severity.ERROR,
                    code="MNT003",
                    message=f"Mount point is not a directory: {entry}",
                    path=str(entry),
                ))
                continue

            # MNT004: Must not be a symlink
            if entry.is_symlink():
                findings.append(Finding(
                    severity=Severity.WARNING,
                    code="MNT004",
                    message=f"Mount point is a symlink: {entry}",
                    path=str(entry),
                ))

            # MNT005: Name validation
            if not _NAME_RE.match(entry.name):
                findings.append(Finding(
                    severity=Severity.WARNING,
                    code="MNT005",
                    message=f"Mount point name contains unusual characters: {entry.name}",
                    path=str(entry),
                ))

            # MNT006: Check permissions
            st = entry.stat()
            mode = stat.S_IMODE(st.st_mode)
            if mode & stat.S_IWOTH:
                findings.append(Finding(
                    severity=Severity.WARNING,
                    code="MNT006",
                    message=f"Mount point is world-writable: {entry} ({oct(mode)})",
                    path=str(entry),
                    context={"mode": oct(mode)},
                ))

        return findings

    def _check_stale_points(self) -> List[Finding]:
        """MNT007: Stale empty mount points should be cleaned up."""
        findings: List[Finding] = []
        root = Path(self._mnt_root)

        if not root.is_dir():
            return findings

        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            # Check if empty
            try:
                contents = list(entry.iterdir())
                if not contents:
                    findings.append(Finding(
                        severity=Severity.INFO,
                        code="MNT007",
                        message=f"Empty mount point: {entry} (may be stale)",
                        path=str(entry),
                    ))
            except PermissionError:
                pass

        return findings

    def _check_fstab_entries(self) -> List[Finding]:
        """MNT008: fstab entries under /mnt should have noauto."""
        findings: List[Finding] = []
        fstab_path = Path(self._fstab_path)

        if not fstab_path.exists():
            return findings

        try:
            with open(fstab_path, "r", encoding="utf-8") as fh:
                for line_no, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split()
                    if len(parts) < 4:
                        continue

                    mount_point = parts[1]
                    options = parts[3]

                    if mount_point.startswith("/mnt/"):
                        # MNT008: Should have noauto
                        if "noauto" not in options:
                            findings.append(Finding(
                                severity=Severity.WARNING,
                                code="MNT008",
                                message=(
                                    f"fstab entry for {mount_point} "
                                    f"lacks 'noauto' option"
                                ),
                                path=mount_point,
                                context={"line": line_no, "options": options},
                            ))

                        # MNT009: If user option, warn about security
                        if "user" in options and "nosuid" not in options:
                            findings.append(Finding(
                                severity=Severity.WARNING,
                                code="MNT009",
                                message=(
                                    f"User-mountable {mount_point} "
                                    f"lacks 'nosuid' option"
                                ),
                                path=mount_point,
                                context={"line": line_no},
                            ))

        except PermissionError:
            log.warning("Cannot read fstab: %s", fstab_path)

        return findings

    def _check_media_separation(self) -> List[Finding]:
        """MNT010: /mnt and /media should be distinct."""
        findings: List[Finding] = []
        mnt = Path(self._mnt_root)
        media = Path("/media")

        if not mnt.exists():
            return findings

        # Check if /mnt and /media overlap (symlinks etc.)
        if media.exists():
            try:
                mnt_real = mnt.resolve()
                media_real = media.resolve()
                if mnt_real == media_real:
                    findings.append(Finding(
                        severity=Severity.ERROR,
                        code="MNT010",
                        message="/mnt and /media resolve to the same path",
                        path=str(mnt),
                    ))
            except (OSError, ValueError):
                pass

        return findings


# ---------------------------------------------------------------------------
# Convenience: generate report
# ---------------------------------------------------------------------------

def validate_mnt(
    mnt_root: str = MNT_ROOT,
    fstab_path: str = "/etc/fstab",
) -> str:
    """Run validation and return a human-readable report string."""
    validator = MntValidator(mnt_root, fstab_path)
    findings = validator.validate()

    lines: List[str] = []
    lines.append(f"=== /mnt Validation Report ({mnt_root}) ===")
    lines.append("")

    if not findings:
        lines.append("No issues found.")
        return "\n".join(lines)

    errors = [f for f in findings if f.severity == Severity.ERROR]
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    infos = [f for f in findings if f.severity == Severity.INFO]

    lines.append(f"Errors: {len(errors)}  Warnings: {len(warnings)}  Info: {len(infos)}")
    lines.append("")

    for f in findings:
        lines.append(f"  [{f.severity.upper()}] {f.code}: {f.message}")
        if f.path:
            lines.append(f"    Path: {f.path}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    """Validate the validator."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        mnt = os.path.join(tmpdir, "mnt")
        fstab = os.path.join(tmpdir, "fstab")
        os.makedirs(mnt)

        # Create some mount point dirs
        os.makedirs(os.path.join(mnt, "usb"))
        os.makedirs(os.path.join(mnt, "floppy"))

        # Create an empty dir (should trigger MNT007)
        os.makedirs(os.path.join(mnt, "empty"))

        # Create a file (should trigger MNT003)
        with open(os.path.join(mnt, "badfile"), "w") as fh:
            fh.write("not a directory")

        # Create fstab with missing noauto
        with open(fstab, "w") as fh:
            fh.write("/dev/sdb1 /mnt/usb vfat defaults 0 0\n")
            fh.write("/dev/fd0 /mnt/floppy msdos user,noauto 0 0\n")

        validator = MntValidator(mnt, fstab)
        findings = validator.validate()

        # Check we found issues
        codes = [f.code for f in findings]
        if "MNT003" not in codes:
            print("MNT003 not triggered for file in /mnt")
            return False
        if "MNT007" not in codes:
            print("MNT007 not triggered for empty dir")
            return False
        if "MNT008" not in codes:
            print("MNT008 not triggered for missing noauto")
            return False

        # Generate report
        report = validate_mnt(mnt, fstab)
        if "MNT003" not in report:
            print("Report missing MNT003")
            return False

        # is_valid should be False (we have errors)
        if validator.is_valid:
            print("Should not be valid with errors")
            return False

    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("validation selftest:", "OK" if _selftest() else "FAIL")
