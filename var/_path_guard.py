"""
UmerOS /var — Path-Traversal Guard  (fix for H303, CWE-22)
==========================================================

WHY THIS EXISTS
---------------
Every /var manager builds target paths by joining a manager-owned root
(e.g. ``/var/log``) with a caller-supplied name::

    self.log_path / filename          # LogManager.write_log
    self.cron_path / username         # SpoolManager.set_cron_user
    self.local_path / name            # VarDirectoryManager.create_local_directory

With an unsanitized name this is a classic directory-traversal (CWE-22).
The dangerous case is ``set_cron_user("../../etc/cron.d/x", jobs)``: cron
executes ``/etc/cron.d/*`` as root, so a traversal here is a **root RCE**.

THE FIX
-------
``safe_child(root, name)`` guarantees the returned path can *only* live
inside ``root``:

1. Reject obvious escapes up front (absolute paths, path separators,
   ``..`` segments, ``.``).
2. Resolve the candidate with ``Path.resolve()`` and verify it is still
   ``root`` itself or a descendant of ``root`` — this defeats symlink and
   encoded-traversal tricks that a naive string check would miss.

Callers that previously did ``self.root / name`` now call
``safe_child(self.root, name)`` and treat ``PathTraversalError`` as a
refused (fail-closed) operation: the dangerous filesystem write NEVER
happens.

Author: UmerOS Development Team
License: GPL-3.0
"""

from __future__ import annotations

from pathlib import Path


class PathTraversalError(ValueError):
    """Raised when a child name would escape its managed root directory.

    This is a *security* refusal, not a generic I/O error: callers should
    log it and return a failure status rather than proceeding.
    """


def safe_child(root: "str | Path", name: str) -> Path:
    """Return an absolute, root-contained path for ``root / name``.

    Args:
        root: the manager-owned directory (e.g. ``/var/log`` or a temp root
            supplied by tests).
        name: caller-supplied child name. Must be a single, safe segment.

    Returns:
        The resolved :class:`~pathlib.Path`, guaranteed to be ``root`` or a
        descendant of ``root``.

    Raises:
        PathTraversalError: if ``name`` tries to escape ``root`` (absolute
            path, contains a separator, a ``..`` segment, or resolves
            outside ``root``).
    """
    # [FIX H303] Normalize the trusted root once. resolve() follows symlinks
    # so the containment check below is against the *real* on-disk location.
    root_abs = Path(root).resolve()

    if name is None or name == "":
        raise PathTraversalError("Refusing empty child name")
    if name == ".":
        raise PathTraversalError("Refusing '.' as child name")
    # Reject absolute paths and backslash variants up front.
    if name.startswith("/") or name.startswith("\\"):
        raise PathTraversalError(f"Refusing absolute path as child name: {name!r}")
    # Reject any path-separator or parent-directory segment.
    for sep in ("/", "\\"):
        if sep in name:
            raise PathTraversalError(
                f"Refusing path separator in child name: {name!r}"
            )
    if ".." in name.split("/") or ".." in name.split("\\"):
        raise PathTraversalError(f"Refusing '..' segment in child name: {name!r}")

    # [FIX H303] Build and resolve the candidate, then prove containment.
    candidate = (root_abs / name).resolve()
    if candidate != root_abs and root_abs not in candidate.parents:
        raise PathTraversalError(
            f"Child path escapes managed root {root_abs}: {candidate}"
        )
    return candidate
