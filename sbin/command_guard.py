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
UmerOS /sbin Command Guard
==========================
Zero-trust execution guard shared by every ``/sbin`` command class.

Why this module exists (H233)
-----------------------------
``SbinManager.execute()`` already called ``gate.require(CAP_SYS_ADMIN)`` before
dispatching a command, but that gate sat on the **manager façade only**.  Every
command class is a plain ``SbinCommand`` subclass with a public ``execute()``,
so ``HaltCommand().execute()`` — or any import of ``sbin.boot`` — reached the
privileged code path with no capability check at all.  Nothing in the package
was audited either: ``sbin/`` had no audit log whatsoever.

Rather than editing all 45 command classes, each module's ``SbinCommand`` base
declares ``__init_subclass__ = install_guard``.  Python calls that hook once per
subclass at class-creation time, so **every** command's ``execute()`` is wrapped
with the gate and the audit record the moment its class is defined — whichever
entry point a caller uses.  A new command cannot forget to opt in.

Capability policy
-----------------
Every command requires ``sys.admin`` by default, matching the pre-existing
behaviour of ``SbinManager.execute()``.  A genuinely read-only command may opt
out by declaring ``capability = None`` on its class; that is an explicit,
reviewable decision rather than an omission.

Auditing
--------
Each invocation emits one ``AUDIT START`` and one ``AUDIT END`` record (or
``AUDIT DENY`` / ``AUDIT ERROR``) on the ``UmerOS.Sbin.Audit`` logger.  The
argument vector is summarised and bounded — never logged verbatim — so a long or
secret-bearing argument list cannot bloat or leak into the log.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import functools
import logging
import os
import sys
from typing import Any, Callable, List, Optional

# Reuse the process-global zero-trust bridge so a single `wire()` call in the
# kernel covers /sbin along with the rest of the cap-gate cluster.
try:
    from core.capability_gate import gate, CAP_SYS_ADMIN
except Exception:  # pragma: no cover - standalone script fallback
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.capability_gate import gate, CAP_SYS_ADMIN

log = logging.getLogger("UmerOS.Sbin.Audit")

#: Capability required by a command that does not declare its own.
CAPABILITY = CAP_SYS_ADMIN

#: How many argv entries an audit record may quote.
MAX_ARGV_LOGGED = 8

#: Longest single argument quoted in an audit record.
MAX_ARG_CHARS = 64


def argv_summary(args: Optional[List[str]]) -> str:
    """Return a bounded, single-line summary of a command's argument vector.

    Never returns the raw list: a caller may pass arbitrarily many arguments, or
    one enormous one, and the audit log must stay readable and leak-free.  The
    total argument *count* is always reported even when the values are elided.
    """
    if not args:
        return "(none)"
    shown: List[str] = []
    for arg in args[:MAX_ARGV_LOGGED]:
        text = str(arg)
        if len(text) > MAX_ARG_CHARS:
            text = text[: MAX_ARG_CHARS - 3] + "..."
        shown.append(text)
    extra = len(args) - len(shown)
    body = " ".join(shown)
    return f"{body} (+{extra} more)" if extra > 0 else body


def audit(event: str, name: str, **fields: Any) -> None:
    """Emit one structured audit record for a ``/sbin`` command lifecycle event."""
    detail = "".join(f" {key}={value!r}" for key, value in fields.items())
    log.info("AUDIT %s %s%s", event, name, detail)


def _guarded_execute(func: Callable[..., int]) -> Callable[..., int]:
    """Wrap a command's ``execute`` with the capability gate and audit trail."""

    @functools.wraps(func)
    def wrapper(self: Any, args: Optional[List[str]] = None) -> int:
        cls = type(self)
        name = getattr(cls, "name", "") or cls.__name__
        cap = getattr(cls, "capability", CAPABILITY)
        summary = argv_summary(args)

        if cap:
            if gate.enforcing:
                try:
                    gate.require(cap)
                except PermissionError:
                    log.warning(
                        "AUDIT DENY %s: capability %r not held (argv: %s)",
                        name, cap, summary,
                    )
                    raise
            else:
                # No trust source is wired and strict mode is off, so
                # `gate.require` would *allow* after logging a warning.
                # Skipping it is behaviourally identical, and it stops a
                # `_selftest` loop from emitting one warning per command
                # (63 lines for a single maintenance.py run) that buries
                # the output it is supposed to accompany.  The warning is
                # still raised by `SbinManager.execute`, the documented
                # entry point, and the audit record below always fires.
                log.debug(
                    "%s: capability %r not enforced (no trust source wired)",
                    name, cap,
                )

        audit("START", name, capability=cap or "-", argv=summary)
        try:
            code = func(self, args)
        except Exception:
            log.warning("AUDIT ERROR %s: execute() raised", name, exc_info=True)
            raise
        audit("END", name, exit=code)
        return code

    wrapper.__sbin_guarded__ = True  # type: ignore[attr-defined]
    return wrapper


def install_guard(cls: type, **kwargs: Any) -> None:
    """``__init_subclass__`` hook: gate + audit every command subclass.

    Assigned to each module's ``SbinCommand`` base as
    ``__init_subclass__ = install_guard``.  Python converts it to a classmethod
    and calls it once per subclass at definition time, so the wrapper is in place
    before any caller can reach ``execute()``.

    The hook is idempotent: a class whose ``execute`` is already wrapped (for
    example via a second base class) is left alone.
    """
    raw = cls.__dict__.get("execute")
    if raw is not None and not getattr(raw, "__sbin_guarded__", False):
        cls.execute = _guarded_execute(raw)  # type: ignore[assignment]
