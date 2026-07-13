"""
Umer OS Hybrid Quantum Kernel  [TODAY - Python simulation]
==========================================================
The minimal microkernel core that orchestrates all Umer OS subsystems.

Responsibilities (kernel-space only):
  - Spawn and track processes (``spawn_process``).
  - Coordinate the scheduler, memory manager, IPC bus, and capability manager.
  - Provide a ``tick()`` / ``init()`` / ``shutdown()`` lifecycle.
  - Inject the AI resource manager into the scheduler once it is available.
  - Expose ``uptime()`` for health monitoring.

Everything else (drivers, FS, network, UI, AI, quantum) runs as user-space
services that interact with the kernel via the IPCBus.

TODO: QPU integration — QuantumAPIGateway will be wired here when QPU
hardware is detected at boot.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from kernel.capability_manager import CapabilityManager, SYSTEM_PID, CAP_PROC_SPAWN
from kernel.ipc_bus import IPCBus
from kernel.memory_manager import MemoryManager
from kernel.scheduler import HybridScheduler, NullAIManager, Task, TaskState

log = logging.getLogger("UmerOS.Kernel")

# Default total simulated memory: 1 GiB
_DEFAULT_RAM = 1 * 1024 * 1024 * 1024


class UmerKernel:
    """The Umer Hybrid Quantum Kernel.

    Instantiate with default arguments for normal operation.
    Pass smaller ``total_memory_bytes`` for tests.

    Args:
        total_memory_bytes: Simulated RAM size in bytes (default 1 GiB).
        quantum_simulator:  Optional SuperpositionSchedulerAdapter injected
                            into the scheduler for quantum-inspired scoring.
    """

    def __init__(
        self,
        total_memory_bytes: int = _DEFAULT_RAM,
        quantum_simulator: Any = None,
    ) -> None:
        self._boot_time: float = time.monotonic()

        # Core subsystems
        self.scheduler: HybridScheduler  = HybridScheduler(quantum_simulator)
        self.memory:    MemoryManager    = MemoryManager(total_memory_bytes)
        self.ipc:       IPCBus           = IPCBus()
        self.caps:      CapabilityManager = CapabilityManager()

        # AI manager starts as NullAIManager; replaced via inject_ai_manager()
        self._ai_manager: Any = NullAIManager()

        # Process registry: pid → metadata dict
        self._processes: Dict[int, dict] = {}
        self._next_pid:  int = 1  # 0 is SYSTEM_PID (kernel itself)

        # Running flag
        self._running: bool = False

        log.info(
            "UmerKernel created — RAM=%d MiB, quantum_sim=%s",
            total_memory_bytes // (1024 * 1024),
            type(quantum_simulator).__name__ if quantum_simulator else "None",
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def init(self) -> None:
        """Start all kernel subsystems.

        Call once after construction.  Safe to call multiple times (idempotent).
        """
        if self._running:
            log.warning("init() called on already-running kernel — ignored.")
            return

        self.ipc.start()
        self.ipc.register(SYSTEM_PID)
        self.caps.grant_many(SYSTEM_PID, [])  # SYSTEM_PID already has all caps from __init__

        await self.scheduler.start(ai_manager=self._ai_manager)
        self._running = True
        log.info("UmerKernel initialised and running.")

    async def shutdown(self) -> None:
        """Gracefully stop all kernel subsystems."""
        if not self._running:
            return
        self._running = False
        await self.scheduler.stop()
        log.info("UmerKernel shut down cleanly.")

    async def main_loop(self, ticks: int = 0) -> None:
        """Run the kernel main loop.

        Args:
            ticks: Number of ticks to run (0 = run forever until shutdown).
        """
        if not self._running:
            await self.init()
        i = 0
        while self._running and (ticks == 0 or i < ticks):
            await asyncio.sleep(0.01)
            i += 1

    # ── Process management ────────────────────────────────────────────────────

    def spawn_process(
        self,
        name: str,
        priority: float = 0.5,
        capabilities: Optional[List[str]] = None,
        coroutine: Any = None,
    ) -> int:
        """Spawn a new process and register it with all subsystems.

        Args:
            name:         Human-readable process name.
            priority:     Scheduling priority in [0.0, 1.0].
            capabilities: List of capability strings to grant initially.
            coroutine:    Optional async callable for the scheduler to run.

        Returns:
            The new process's PID.
        """
        pid = self._next_pid
        self._next_pid += 1

        # Register with capability manager
        self.caps.register(pid)
        if capabilities:
            self.caps.grant_many(pid, capabilities)

        # Register with IPC bus
        self.ipc.register(pid)

        # Record metadata
        self._processes[pid] = {
            "name":      name,
            "priority":  priority,
            "born_at":   time.monotonic(),
            "state":     TaskState.READY,
        }

        log.info("Spawned process '%s' as PID %d (priority=%.2f).", name, pid, priority)
        return pid

    def kill_process(self, pid: int) -> bool:
        """Terminate a process and release its resources.

        Args:
            pid: Process ID to terminate.

        Returns:
            True if the process existed and was removed, False otherwise.
        """
        if pid not in self._processes:
            return False
        self.caps.revoke_all(pid)
        self.ipc.unregister(pid)
        self._processes.pop(pid, None)
        log.info("Process PID %d terminated.", pid)
        return True

    def list_processes(self) -> List[dict]:
        """Return a snapshot list of all running processes.

        Returns:
            List of process metadata dicts, each containing pid, name,
            priority, state, and age_seconds fields.
        """
        now = time.monotonic()
        result = []
        for pid, meta in self._processes.items():
            result.append({
                "pid":         pid,
                "name":        meta["name"],
                "priority":    meta["priority"],
                "state":       meta["state"],
                "age_seconds": round(now - meta["born_at"], 3),
            })
        return result

    # ── AI integration ────────────────────────────────────────────────────────

    def inject_ai_manager(self, ai_manager: Any) -> None:
        """Replace the NullAIManager with the real AIResourceManager.

        Called by the boot sequence once the AI subsystem is loaded.

        Args:
            ai_manager: Object implementing ``predict_task_success(task) -> float``.
        """
        self._ai_manager = ai_manager
        self.scheduler.set_ai_manager(ai_manager)
        log.info("AI manager injected: %s", type(ai_manager).__name__)

    # ── Health / monitoring ───────────────────────────────────────────────────

    def uptime(self) -> float:
        """Return seconds since the kernel was constructed.

        Returns:
            Float seconds.
        """
        return time.monotonic() - self._boot_time

    def status(self) -> dict:
        """Return a health snapshot of the kernel.

        Returns:
            Dict with uptime, process count, memory stats, and scheduler stats.
        """
        mem = self.memory.stats()
        return {
            "uptime_seconds": round(self.uptime(), 3),
            "process_count":  len(self._processes),
            "scheduler_tasks": len(self.scheduler),
            "memory":         mem,
            "running":        self._running,
        }
