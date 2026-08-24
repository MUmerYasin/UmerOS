"""
UmerOS Capability Gate  [zero-trust bridge]
==========================================
Single wiring point for the *cap-gate* remediation cluster (H227, H233, H267,
H273, H281, H283, H296, H304).  Privileged operations in /srv, /tmp, /var, /usr,
/root and /sbin call ``gate.require(CAP_...)`` before performing the privileged
action.  This is the bridge between those modules and the kernel's real
``CapabilityManager`` (``kernel.capability_manager``).

Why a bridge instead of importing CapabilityManager directly?
  * The privileged modules are library-style (no running kernel / PID context),
    so a process-global gate instance is the natural integration seam.
  * The kernel boots a real ``CapabilityManager``; it calls ``gate.wire(cm)`` once
    and every privileged call is then enforced fail-closed (no capability -> the
    manager raises ``PermissionError``).

Fail-closed vs. usable (important design choice):
  * When a CapabilityManager IS wired  -> enforce against it (truly fail-closed).
  * When NO manager is wired (standalone scripts, CLI tools, unit tests) the gate
    defaults to *permissive* but logs a warning, so existing workflows do not
    break.  Hardened deployments (or tests proving the fail-closed path) can call
    ``gate.set_strict(True)`` to deny outright when no trust source is present.

Author: UmerOS Project
License: GPL-3.0
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Optional

log = logging.getLogger("UmerOS.CapabilityGate")

# ── Capability name constants ───────────────────────────────────────────────
# Re-declared locally so the gate can be imported from anywhere without a hard
# dependency on kernel.capability_manager (which is import-safe, but we keep a
# copy to avoid import cycles and to document the cap taxonomy in one place).
CAP_FS_READ = "fs.read"
CAP_FS_WRITE = "fs.write"
CAP_FS_ADMIN = "fs.admin"
CAP_FS_PERMS = "fs.perms"          # chmod / permission changes (H273, H283)
CAP_NET_SEND = "net.send"
CAP_NET_ADMIN = "net.admin"
CAP_INSTALL = "install"
CAP_BACKUP = "srv.backup"          # backup/restore destructive ops (H267)
CAP_REAPER = "tmp.reap"            # tmp reaper destructive delete (H281)
CAP_SYS_ADMIN = "sys.admin"        # generic privileged admin (H227, H233, H296, H304)
CAP_HOME_ADMIN = "home.admin"      # privileged /home mutations: create/remove/restore (H83, H85)


class CapabilityGate:
    """Process-global zero-trust capability gate.

    Thread-safe via a single ``threading.Lock``.
    """

    def __init__(self) -> None:
        self._manager: Any = None
        self._strict: bool = False
        self._lock: threading.Lock = threading.Lock()

    # ── Wiring ───────────────────────────────────────────────────────────────

    def wire(self, manager: Any) -> None:
        """Attach the kernel's CapabilityManager (or any object exposing
        ``query(pid, cap)``).  Once wired, every ``require`` is enforced against
        it (fail-closed)."""
        with self._lock:
            self._manager = manager
        log.info("CapabilityGate wired to %r.", type(manager).__name__)

    def unwire(self) -> None:
        with self._lock:
            self._manager = None

    def set_strict(self, value: bool) -> None:
        """When True, deny privileged ops if no manager is wired (fail-closed)."""
        with self._lock:
            self._strict = value

    @property
    def strict(self) -> bool:
        with self._lock:
            return self._strict

    @property
    def enforcing(self) -> bool:
        """True when the zero-trust posture is active.

        A posture is active when a real ``CapabilityManager`` is wired (fail-
        closed enforcement) OR strict mode is enabled. Callers use this to scale
        defense-in-depth controls (e.g. SSRF destination filtering) with the same
        trust level the capability gate applies to privileged operations.
        """
        with self._lock:
            return self._manager is not None or self._strict

    # ── Query / enforcement ──────────────────────────────────────────────────

    def query(self, cap: str, pid: Optional[int] = None) -> bool:
        """Boolean test for a capability (never raises)."""
        pid = os.getpid() if pid is None else pid
        with self._lock:
            mgr = self._manager
        if mgr is not None:
            try:
                return bool(mgr.query(pid, cap))
            except Exception:
                return False
        return not self._strict  # permissive when no trust source + non-strict

    def require(self, cap: str, pid: Optional[int] = None) -> None:
        """Assert the current process holds ``cap``; raise PermissionError otherwise.

        Args:
            cap: Required capability string.
            pid: Optional explicit PID (defaults to the current process).

        Raises:
            PermissionError: If the capability is not held (and a trust source
                is wired, or strict mode is on with no trust source).
        """
        pid = os.getpid() if pid is None else pid
        with self._lock:
            mgr = self._manager
            strict = self._strict
        if mgr is not None:
            try:
                if not mgr.query(pid, cap):
                    log.warning("DENIED: pid %s lacks capability '%s'.", pid, cap)
                    raise PermissionError(
                        f"Capability '{cap}' not held by pid {pid}."
                    )
            except PermissionError:
                raise
            except Exception as exc:  # pragma: no cover - defensive
                raise PermissionError(
                    f"Capability check failed for '{cap}': {exc}"
                ) from exc
            return
        if strict:
            raise PermissionError(
                f"Capability '{cap}' required but no trust source is wired "
                f"(strict mode)."
            )
        log.warning(
            "PERMISSIVE: capability '%s' required by pid %s but no "
            "CapabilityManager is wired; allowing (set strict mode to deny).",
            cap, pid,
        )


# Process-global gate instance — the integration seam for the whole cluster.
gate = CapabilityGate()
