"""
Umer OS Capability Manager  [TODAY - zero-trust]
=================================================
Implements a capability-based permission system for the Umer OS microkernel.

Design:
  - No PID has any capability by default.
  - Capabilities are named strings (e.g. "fs.read", "net.send").
  - ``register(pid)``  — declare a PID; creates an empty grant set.
  - ``grant(pid, cap)`` — add a capability.
  - ``revoke(pid, cap)`` — remove a capability.
  - ``query(pid, cap)`` → bool  — non-raising boolean test.
  - ``check(pid, cap)`` → raises PermissionError if not granted.
  - ``registered_pids()`` → sorted list of known PIDs.

SYSTEM_PID = 0 is reserved for the kernel itself.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import threading
from typing import Dict, FrozenSet, List, Set

log = logging.getLogger("UmerOS.CapabilityManager")

# Well-known capability name constants
CAP_FS_READ       = "fs.read"
CAP_FS_WRITE      = "fs.write"
CAP_FS_ADMIN      = "fs.admin"
CAP_NET_SEND      = "net.send"
CAP_NET_RECV      = "net.recv"
CAP_NET_ADMIN     = "net.admin"
CAP_GPU_RENDER    = "gpu.render"
CAP_GPU_COMPUTE   = "gpu.compute"
CAP_QUANTUM_SIM   = "quantum.simulate"
CAP_QUANTUM_HW    = "quantum.hardware"   # FUTURE: real QPU access
CAP_AI_INFERENCE  = "ai.inference"
CAP_AI_TRAIN      = "ai.train"           # requires user consent
CAP_PROC_SPAWN    = "proc.spawn"
CAP_PROC_KILL     = "proc.kill"
CAP_DEVICE_USB    = "device.usb"
CAP_IPC_BROADCAST = "ipc.broadcast"
CAP_INSTALL       = "install"            # admin-only

# Reserved kernel PID
SYSTEM_PID: int = 0


class CapabilityManager:
    """Zero-trust capability grant/revoke/check system.

    Thread-safe via a single ``threading.Lock``.
    """

    def __init__(self) -> None:
        # PID → mutable set of granted capability strings
        self._grants: Dict[int, Set[str]] = {}
        self._lock:   threading.Lock = threading.Lock()
        # The kernel (SYSTEM_PID=0) starts with all capabilities
        self._grants[SYSTEM_PID] = {
            CAP_FS_READ, CAP_FS_WRITE, CAP_FS_ADMIN,
            CAP_NET_SEND, CAP_NET_RECV, CAP_NET_ADMIN,
            CAP_GPU_RENDER, CAP_GPU_COMPUTE,
            CAP_QUANTUM_SIM,
            CAP_AI_INFERENCE, CAP_AI_TRAIN,
            CAP_PROC_SPAWN, CAP_PROC_KILL,
            CAP_DEVICE_USB, CAP_IPC_BROADCAST, CAP_INSTALL,
        }
        log.info("CapabilityManager initialised (zero-trust; SYSTEM_PID=0 is omnipotent).")

    # ── Registration ─────────────────────────────────────────────────────────

    def register(self, pid: int) -> None:
        """Register a PID so it appears in ``registered_pids()`` with no capabilities.

        Idempotent — re-registering an existing PID is a no-op.

        Args:
            pid: Process ID to register.
        """
        with self._lock:
            if pid not in self._grants:
                self._grants[pid] = set()
        log.debug("PID %d registered (no capabilities).", pid)

    def registered_pids(self) -> List[int]:
        """Return a sorted list of all known PIDs.

        Returns:
            List of integer PIDs in ascending order.
        """
        with self._lock:
            return sorted(self._grants.keys())

    # ── Grant / Revoke ────────────────────────────────────────────────────────

    def grant(self, pid: int, capability: str) -> None:
        """Grant a capability to a process.  Registers the PID if unknown.

        Args:
            pid:        Target process ID.
            capability: Named capability string.
        """
        with self._lock:
            if pid not in self._grants:
                self._grants[pid] = set()
            self._grants[pid].add(capability)
        log.info("Capability '%s' granted to PID %d.", capability, pid)

    def grant_many(self, pid: int, capabilities: List[str]) -> None:
        """Grant multiple capabilities to a process in one call.

        Args:
            pid:          Target process ID.
            capabilities: Iterable of capability strings.
        """
        with self._lock:
            if pid not in self._grants:
                self._grants[pid] = set()
            self._grants[pid].update(capabilities)
        log.info("Capabilities %s granted to PID %d.", capabilities, pid)

    def revoke(self, pid: int, capability: str) -> bool:
        """Revoke a single capability from a process.

        Args:
            pid:        Target process ID.
            capability: Capability to revoke.

        Returns:
            True if the capability was present and removed, False otherwise.
        """
        with self._lock:
            caps = self._grants.get(pid, set())
            had = capability in caps
            caps.discard(capability)
        if had:
            log.info("Capability '%s' revoked from PID %d.", capability, pid)
        return had

    def revoke_all(self, pid: int) -> int:
        """Revoke all capabilities from a process (e.g. on process exit).

        Args:
            pid: Process ID.

        Returns:
            Number of capabilities that were revoked.
        """
        with self._lock:
            caps = self._grants.pop(pid, set())
        n = len(caps)
        if n:
            log.info("All %d capability/capabilities revoked from PID %d.", n, pid)
        return n

    # ── Query / Check ────────────────────────────────────────────────────────

    def query(self, pid: int, capability: str) -> bool:
        """Test whether a process holds a capability — returns bool, never raises.

        Args:
            pid:        Process ID (unknown PIDs return False).
            capability: Capability string to test.

        Returns:
            True if granted, False otherwise.
        """
        with self._lock:
            return capability in self._grants.get(pid, set())

    def check(self, pid: int, capability: str) -> bool:
        """Assert that pid holds capability; raise PermissionError if not.

        This is the *enforcement* variant.  Use ``query()`` when you only
        want a boolean answer without raising.

        Args:
            pid:        Process ID.
            capability: Required capability.

        Returns:
            True if the capability is held.

        Raises:
            PermissionError: If the capability is not granted.
        """
        with self._lock:
            granted = capability in self._grants.get(pid, set())
        if not granted:
            log.warning("DENIED: PID %d requested '%s'.", pid, capability)
            raise PermissionError(
                f"PID {pid} does not hold capability '{capability}'."
            )
        return True

    def list_capabilities(self, pid: int) -> FrozenSet[str]:
        """Return the frozen set of capabilities held by a process.

        Args:
            pid: Process ID.

        Returns:
            FrozenSet of capability strings (empty if PID unknown).
        """
        with self._lock:
            return frozenset(self._grants.get(pid, set()))
