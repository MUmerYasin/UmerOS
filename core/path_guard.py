"""
UmerOS — Shared Path-Traversal Guard  (CWE-22)
==============================================

Canonical, dependency-free guard used by every UmerOS subsystem that builds
filesystem paths from caller-supplied names (``/var``, ``/opt``, ``/srv``,
``/tmp``, the package manager, …).

WHY THIS EXISTS
---------------
Managers routinely join a trusted root with an untrusted name::

    self.root / filename            # arbitrary write inside/outside root
    self.opt_root / provider / name # rmtree -> arbitrary delete
    target_root / service_name      # restore -> arbitrary write

With an unsanitized name this is a classic directory-traversal (CWE-22).
The dangerous cases range from clobbering arbitrary files to **root RCE**
(the ``/etc/cron.d`` write in H303).

THE FIX
-------
``safe_child(root, name)``  — strict single-segment containment.
``safe_join(root, *names)`` — multi-segment containment (allows nested
    names like ``sub/file.txt`` but proves the final path stays inside root).

Both:
  1. Reject obvious escapes up front (absolute paths, separators, ``..``,
     ``.``).
  2. Resolve the candidate with ``Path.resolve()`` and verify it is still
     ``root`` or a descendant of ``root`` — defeating symlink and
     encoded-traversal tricks that a naive string check would miss.

Callers treat ``PathTraversalError`` as a *security refusal* (fail-closed):
the dangerous filesystem operation NEVER happens.

Author: UmerOS Development Team
License: GPL-3.0
"""

from __future__ import annotations

from pathlib import Path


class PathTraversalError(ValueError):
    """Raised when a name would escape its managed root directory.

    This is a *security* refusal, not a generic I/O error: callers should
    log it and return a failure status rather than proceeding.
    """


def _reject_obvious_escape(name: str) -> None:
    """Fail fast on names that cannot be a safe path component."""
    if name is None or name == "":
        raise PathTraversalError("Refusing empty path component")
    if name == ".":
        raise PathTraversalError("Refusing '.' as path component")
    # Reject absolute paths and backslash variants up front.
    if name.startswith("/") or name.startswith("\\"):
        raise PathTraversalError(f"Refusing absolute path component: {name!r}")
    # Reject any path-separator or parent-directory segment.
    for sep in ("/", "\\"):
        if sep in name:
            raise PathTraversalError(
                f"Refusing path separator in component: {name!r}"
            )
    if ".." in name.split("/") or ".." in name.split("\\"):
        raise PathTraversalError(f"Refusing '..' segment in component: {name!r}")


def safe_child(root: "str | Path", name: str) -> Path:
    """Return an absolute, root-contained path for ``root / name``.

    Args:
        root: the manager-owned directory.
        name: caller-supplied child name. Must be a *single* safe segment.

    Returns:
        The resolved :class:`~pathlib.Path`, guaranteed to be ``root`` or a
        descendant of ``root``.

    Raises:
        PathTraversalError: if ``name`` tries to escape ``root``.
    """
    # [FIX CWE-22] Normalize the trusted root once. resolve() follows
    # symlinks so the containment check is against the real on-disk location.
    root_abs = Path(root).resolve()
    _reject_obvious_escape(name)

    # [FIX CWE-22] Build and resolve the candidate, then prove containment.
    candidate = (root_abs / name).resolve()
    if candidate != root_abs and root_abs not in candidate.parents:
        raise PathTraversalError(
            f"Child path escapes managed root {root_abs}: {candidate}"
        )
    return candidate


def safe_join(root: "str | Path", *names: str) -> Path:
    """Join several names under ``root`` and guarantee containment.

    Unlike :func:`safe_child` this allows *nested* names (e.g. a filename of
    ``"sub/file.txt"``): each separator-delimited component is validated and
    the final resolved path must remain inside ``root``.

    Args:
        root: the manager-owned directory.
        *names: caller-supplied path components (each may contain ``/`` or
            ``\\`` separators, which are treated as multiple components).

    Returns:
        The resolved :class:`~pathlib.Path`, guaranteed to be ``root`` or a
        descendant of ``root``.

    Raises:
        PathTraversalError: if any component (or the resulting path) escapes
            ``root``.
    """
    root_abs = Path(root).resolve()
    current = root_abs
    for name in names:
        if name is None:
            raise PathTraversalError("Refusing None path component")
        # [FIX CWE-22] Split on separators so nested names are supported, then
        # validate every component (no "..", no stray separators).
        for part in str(name).replace("\\", "/").split("/"):
            if part in ("", "."):
                continue  # tolerate leading/trailing/duplicate separators
            if part == "..":
                raise PathTraversalError(
                    f"Refusing '..' segment in path component: {name!r}"
                )
            if "/" in part or "\\" in part:
                raise PathTraversalError(
                    f"Refusing separator in path component: {part!r}"
                )
            # [FIX CWE-22] Re-resolve after each component so a crafted name
            # cannot undo prior containment via symlinks.
            current = (current / part).resolve()
    if current != root_abs and root_abs not in current.parents:
        raise PathTraversalError(
            f"Path escapes managed root {root_abs}: {current}"
        )
    return current
