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
UmerOS /sbin Path & Mount-Option Policy
=======================================
Validation shared by the privileged ``/sbin`` commands that accept or build
filesystem paths: ``mount``, ``umount``, ``mknod``, ``losetup``, ``chroot``
and ``pivot_root``.

Why this module exists (H234)
-----------------------------
Those commands are **simulated** -- they mutate in-memory tables
(``_MOUNT_TABLE``, ``_DEVICE_NODES``, ``_LOOP_DEVICES``) and print, rather than
issuing a real ``mount(2)`` / ``mknod(2)`` / ``chroot(2)``.  That is honest
today, but it means every argument they accept has been *stored unvalidated*.
The moment the simulation is wired to real syscalls, that stored text becomes a
real path: ``mknod ../../etc/cron.d/root c 1 1`` would plant a device node
outside ``/dev``, and ``mount -o rw,suid /dev/sdb1 /mnt/usb`` would honour a
setuid binary on removable media.

So the policy is applied **now**, while it is still cheap: the commands reject
an unsafe argument today, and the check is already in the path when the syscall
lands.

Two rules
---------
1. **Paths must be absolute, NUL-free, backslash-free and free of ``..``.**
   A privileged path is resolved against ``/``, so a relative or traversing
   value is a caller error, not something to normalise away silently.
2. **New mounts are hardened** with ``nosuid,nodev,noexec`` unless the caller
   explicitly asked for the opposite (``suid``/``dev``/``exec``).  This mirrors
   ``mnt/mount_ops.py::harden_user_options`` and ``_HARDEN_PAIRS`` -- the same
   flags, deliberately, so the simulated ``/sbin/mount`` and the real ``mnt/``
   mount engine cannot drift apart.  ``HARDEN_PAIRS`` below is asserted equal to
   ``mnt.mount_ops._HARDEN_PAIRS`` by the test suite rather than imported, so
   ``sbin/`` does not drag the whole ``mnt`` subsystem in at import time.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import posixpath
import re
from typing import List, Optional, Tuple

#: (hardening flag, explicit opt-out) pairs, kept identical to
#: ``mnt.mount_ops._HARDEN_PAIRS``.
HARDEN_PAIRS: Tuple[Tuple[str, str], ...] = (
    ("noexec", "exec"),
    ("nosuid", "suid"),
    ("nodev", "dev"),
)

#: Device nodes may only be created here.
DEV_PREFIX = "/dev"

#: Loop devices live under this prefix and are named ``loop<N>``.
LOOP_PREFIX = "/dev/loop"

_LOOP_NAME_RE = re.compile(r"^/dev/loop\d+\Z")

#: Characters that must never appear in a path handed to a privileged command.
_FORBIDDEN_CHARS = ("\x00", "\n", "\r")


class UnsafePathError(ValueError):
    """Raised when a caller-supplied path is unfit for a privileged operation.

    A security refusal, not an I/O error: the caller reports it and returns a
    non-zero status; the operation never happens.
    """


def normalise(path: Optional[str], what: str = "path") -> str:
    """Return a normalised absolute POSIX path, or raise :class:`UnsafePathError`.

    Args:
        path: the caller-supplied path.
        what: a short noun used in the error message (``"mount point"``, …).

    Raises:
        UnsafePathError: if ``path`` is empty, non-string, contains a NUL or
            newline, is not absolute, contains a backslash, or has a ``..``
            segment.
    """
    if not isinstance(path, str) or not path.strip():
        raise UnsafePathError(f"{what}: empty or non-string path")
    for bad in _FORBIDDEN_CHARS:
        if bad in path:
            raise UnsafePathError(f"{what}: control character in {path!r}")
    if "\\" in path:
        raise UnsafePathError(f"{what}: backslash in POSIX path {path!r}")
    if not path.startswith("/"):
        raise UnsafePathError(f"{what}: must be an absolute path, got {path!r}")
    if ".." in path.split("/"):
        raise UnsafePathError(f"{what}: '..' segment in {path!r}")

    norm = posixpath.normpath(path)
    if not norm.startswith("/"):
        # normpath can only do this for a relative input, already rejected.
        raise UnsafePathError(f"{what}: does not normalise to an absolute path")
    return norm


def require_under(path: Optional[str], prefix: str, what: str = "path") -> str:
    """Return ``path`` normalised, proving it lies at or beneath ``prefix``."""
    norm = normalise(path, what=what)
    root = normalise(prefix, what="prefix")
    if norm == root or norm.startswith(root.rstrip("/") + "/"):
        return norm
    raise UnsafePathError(f"{what}: {path!r} is outside {root}")


def validate_source(spec: Optional[str], what: str = "device") -> str:
    """Validate a mount *source*, which need not be a path.

    ``mount`` accepts both real device paths (``/dev/sdb1``) and pseudo
    filesystem names (``proc``, ``sysfs``, ``tmpfs``, ``nfs-server:/export``),
    so an absolute-path requirement would be wrong here.  What is never
    acceptable is an empty value, a control character, or a ``..`` segment.
    """
    if not isinstance(spec, str) or not spec.strip():
        raise UnsafePathError(f"{what}: empty or non-string source")
    for bad in _FORBIDDEN_CHARS:
        if bad in spec:
            raise UnsafePathError(f"{what}: control character in {spec!r}")
    if ".." in spec.replace("\\", "/").split("/"):
        raise UnsafePathError(f"{what}: '..' segment in {spec!r}")
    return spec


def require_loop_device(path: Optional[str], what: str = "loop device") -> str:
    """Return ``path`` if it names a loop device (``/dev/loop<N>``)."""
    norm = normalise(path, what=what)
    if not _LOOP_NAME_RE.match(norm):
        raise UnsafePathError(f"{what}: {path!r} is not a /dev/loop<N> device")
    return norm


def harden_mount_options(options: Optional[str]) -> Tuple[str, List[str]]:
    """Append ``noexec,nosuid,nodev`` unless the caller opted out explicitly.

    Returns:
        ``(hardened_options, flags_added)``.  ``flags_added`` is empty when the
        caller had already chosen each flag (or its opposite), so a caller can
        tell whether anything changed without re-parsing the string.

    A caller that writes ``exec``/``suid``/``dev`` is making a deliberate,
    privileged decision -- the same convention ``mnt/mount_ops`` documents --
    so that choice is preserved rather than silently overridden.
    """
    parts = [p.strip() for p in (options or "").split(",") if p.strip()]
    names = {p.lower() for p in parts}
    added: List[str] = []
    for hard, soft in HARDEN_PAIRS:
        if hard not in names and soft not in names:
            parts.append(hard)
            names.add(hard)
            added.append(hard)
    return ",".join(parts), added
