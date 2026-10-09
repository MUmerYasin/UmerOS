"""
UmerOS /var — Path-Traversal Guard  (fix for H303, CWE-22)
==========================================================

SHIM over the canonical guard in ``core.path_guard``.

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
inside ``root``; ``safe_join(root, *names)`` extends that guarantee to
nested (multi-segment) names. Both:

1. Reject obvious escapes up front (absolute paths, path separators,
   ``..`` segments, ``.``).
2. Resolve the candidate with ``Path.resolve()`` and verify it is still
   ``root`` itself or a descendant of ``root`` — this defeats symlink and
   encoded-traversal tricks that a naive string check would miss.

This module re-exports the *canonical* implementations from
``core.path_guard`` so there is exactly one guarded code path for the
whole OS (previously this file was a full copy, which let the two
guards drift apart). Callers treat ``PathTraversalError`` as a refused
(fail-closed) operation: the dangerous filesystem write NEVER happens.

Author: UmerOS Development Team
License: GPL-3.0
"""

from __future__ import annotations

import os
import sys

# [FIX] Re-export the canonical guard: one implementation, no drift.
try:
    from core.path_guard import (  # noqa: F401
        PathTraversalError,
        safe_child,
        safe_join,
    )
except Exception:  # pragma: no cover - standalone fallback
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.path_guard import (  # noqa: F401
        PathTraversalError,
        safe_child,
        safe_join,
    )

__all__ = ["PathTraversalError", "safe_child", "safe_join"]
