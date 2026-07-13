"""
Umer OS Hybrid Scheduler  [TODAY - quantum-inspired classical simulation]
=========================================================================
Implements the AI + quantum-inspired task scheduling algorithm.

Selection heuristic (superposition-inspired):
    score = quantum_state["superposition"] * priority / (cpu_time + EPSILON)

    "superposition" is a success-probability in [0,1] predicted by the
    AIResourceManager.  Higher scores win the next CPU slot.

EXPERIMENTAL: When a QPU becomes available the QuantumCircuitSimulator in
quantum/quantum_sim.py will replace the placeholder probability.
TODO: QPU integration hook at _select_next()

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

log = logging.getLogger("UmerOS.Scheduler")

EPSILON = 0.001       # prevents division-by-zero in score formula
TICK_INTERVAL = 0.01  # scheduler tick every 10 ms
MAX_TASKS = 1024      # hard cap on simultaneous tasks


# ---------------------------------------------------------------------------
# Task state constants
# ---------------------------------------------------------------------------

class TaskState:
    """String constants for Task.state — importable enum-style class.

    Using plain strings (not enum.Enum) keeps Task a simple dataclass while
    still providing named constants that tests and callers can import.
    """

    READY   = "READY"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    DONE    = "DONE"


# ---------------------------------------------------------------------------
# Task dataclass
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """A schedulable unit of work within Umer OS.

    Attributes:
        pid:           Unique process identifier (positive integer).
        name:          Human-readable process/service name.
        priority:      Static priority hint in [0.0, 1.0]; higher = more important.
        state:         Lifecycle state; one of TaskState.{READY, RUNNING, BLOCKED, DONE}.
        cpu_time:      Accumulated CPU seconds consumed so far.
        quantum_state: AI/quantum metadata dict.
                       Key ``"superposition"`` (float, 0-1): predicted success probability.
        coroutine:     Optional async callable executed when the task is dispatched.
    """

    pid:           int
    name:          str
    priority:      float = 0.5
    state:         str   = TaskState.READY
    cpu_time:      float = 0.0
    quantum_state: Dict  = field(default_factory=lambda: {"superposition": 0.5})
    coroutine:     Optional[Callable] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Validate fields after construction.

        Raises:
            ValueError: If priority is outside [0.0, 1.0].
        """
        if not (0.0 <= self.priority <= 1.0):
            raise ValueError(
                f"Task.priority must be in [0.0, 1.0]; got {self.priority!r}."
            )

    @property
    def schedule_score(self) -> float:
        """Compute the quantum-inspired scheduling score (higher = preferred).

        Returns:
            superposition_probability * priority / (cpu_time + EPSILON)
        """
        sup = float(self.quantum_state.get("superposition", 0.5))
        return (sup * self.priority) / (self.cpu_time + EPSILON)


# ---------------------------------------------------------------------------
# NullAIManager
# ---------------------------------------------------------------------------

class NullAIManager:
    """Fallback AI manager used before the real AIResourceManager is injected.

    Returns a fixed neutral probability (0.5) for all tasks so the scheduler
    works correctly from first boot even without the AI subsystem loaded.
    """

    def predict_task_success(self, task: Task) -> float:
        """Return a neutral 0.5 for every task (round-robin behaviour).

        Args:
            task: The task being evaluated.

        Returns:
            0.5 — equal probability for all tasks.
        """
        return 0.5


# ---------------------------------------------------------------------------
# HybridScheduler
# ---------------------------------------------------------------------------

class HybridScheduler:
    """AI + quantum-inspired cooperative task scheduler.

    Maintains a dictionary of Tasks keyed by PID.  Each asyncio tick the
    scheduler picks the task with the highest ``schedule_score`` among those
    in READY state, transitions it to RUNNING, invokes its coroutine (if any),
    then returns it to READY.

    Thread-safety: All mutations are guarded by ``asyncio.Lock``.

    Args:
        quantum_simulator: Optional SuperpositionSchedulerAdapter.
            When supplied, its ``evaluate_task_paths()`` refines task scores.
    """

    def __init__(self, quantum_simulator=None) -> None:
        self._tasks:       Dict[int, Task]      = {}
        self._lock:        asyncio.Lock         = asyncio.Lock()
        self._ai                                = NullAIManager()
        self._running:     bool                 = False
        self._loop_task:   Optional[asyncio.Task] = None
        self._quantum_sim                       = quantum_simulator
        log.info("HybridScheduler initialised.")

    # ── AI manager injection ─────────────────────────────────────────────────

    def set_ai_manager(self, ai_manager) -> None:
        """Inject the AI resource manager for task success prediction.

        Args:
            ai_manager: Object with ``predict_task_success(task) -> float``.
        """
        self._ai = ai_manager
        log.debug("AI manager injected into HybridScheduler: %s",
                  type(ai_manager).__name__)

    # ── Task management ──────────────────────────────────────────────────────

    async def add_task(self, task: Task) -> None:
        """Enqueue a task and initialise its quantum_state from the AI manager.

        Args:
            task: Task to schedule.

        Raises:
            ValueError: If MAX_TASKS would be exceeded.
        """
        async with self._lock:
            if len(self._tasks) >= MAX_TASKS:
                raise ValueError(
                    f"Task limit ({MAX_TASKS}) reached; cannot add PID {task.pid}."
                )
            try:
                score = float(self._ai.predict_task_success(task))
                task.quantum_state["superposition"] = max(0.0, min(1.0, score))
            except Exception as exc:  # noqa: BLE001
                log.warning("AI predict_task_success failed for PID %d: %s",
                            task.pid, exc)
                task.quantum_state["superposition"] = task.priority
            self._tasks[task.pid] = task
        log.debug("Task added: PID %d (%s) score=%.3f",
                  task.pid, task.name, task.quantum_state["superposition"])

    async def remove_task(self, pid: int) -> Optional[Task]:
        """Remove and return a task by PID.

        Args:
            pid: Process ID to remove.

        Returns:
            The removed Task, or None if not found.
        """
        async with self._lock:
            return self._tasks.pop(pid, None)

    async def get_task(self, pid: int) -> Optional[Task]:
        """Look up a task by PID without removing it.

        Args:
            pid: Process ID.

        Returns:
            The Task, or None if not found.
        """
        async with self._lock:
            return self._tasks.get(pid)

    async def list_tasks(self) -> List[Task]:
        """Return a snapshot list of all current tasks.

        Returns:
            List of Task objects (copy, safe to iterate outside the lock).
        """
        async with self._lock:
            return list(self._tasks.values())

    def __len__(self) -> int:
        """Return the number of currently registered tasks.

        Returns:
            Integer task count (all states).
        """
        return len(self._tasks)

    # ── Core selection ───────────────────────────────────────────────────────

    async def _select_next(self) -> Optional[Task]:
        """Pick the highest-scored READY task (quantum-inspired selection).

        If a quantum simulator is attached, its ``evaluate_task_paths()``
        refines the scores before selection.

        Returns:
            Highest-scored READY Task, or None if no READY tasks exist.
        """
        async with self._lock:
            ready = [t for t in self._tasks.values() if t.state == TaskState.READY]

        if not ready:
            return None

        # Optional quantum-inspired score refinement
        if self._quantum_sim is not None:
            try:
                refinements = self._quantum_sim.evaluate_task_paths(ready)
                for task in ready:
                    if task.pid in refinements:
                        task.quantum_state["superposition"] = refinements[task.pid]
            except Exception as exc:  # noqa: BLE001
                log.debug("Quantum refinement skipped: %s", exc)

        return max(ready, key=lambda t: t.schedule_score)

    async def _execute_task(self, task: Task) -> None:
        """Transition a task to RUNNING, run its coroutine, restore READY.

        Args:
            task: Task to execute.
        """
        task.state = TaskState.RUNNING
        start = time.perf_counter()
        try:
            if task.coroutine is not None:
                await task.coroutine(task)
            else:
                await asyncio.sleep(0)  # yield control
        except asyncio.CancelledError:
            task.state = TaskState.DONE
            return
        except Exception as exc:  # noqa: BLE001
            log.error("Task PID %d raised %s: %s", task.pid, type(exc).__name__, exc)
            task.state = TaskState.BLOCKED
        else:
            task.state = TaskState.READY
        finally:
            task.cpu_time += time.perf_counter() - start

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self, ai_manager=None) -> None:
        """Start the background scheduling loop.

        Args:
            ai_manager: Optional AI manager to inject before starting.
        """
        if ai_manager is not None:
            self.set_ai_manager(ai_manager)
        self._running = True
        self._loop_task = asyncio.create_task(self._scheduler_loop())
        log.info("HybridScheduler started.")

    async def stop(self) -> None:
        """Stop the scheduler and cancel the background loop task."""
        self._running = False
        if self._loop_task is not None and not self._loop_task.done():
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        log.info("HybridScheduler stopped.")

    async def _scheduler_loop(self) -> None:
        """Main loop: select → execute → sleep for TICK_INTERVAL."""
        while self._running:
            try:
                task = await self._select_next()
                if task is not None:
                    await self._execute_task(task)
                else:
                    await asyncio.sleep(TICK_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                log.error("Scheduler loop error: %s", exc)
                await asyncio.sleep(TICK_INTERVAL)

    async def tick(self) -> Optional[Task]:
        """Single-step: select and return the next READY task (non-executing).

        Useful for tests and external dispatchers that manage execution themselves.

        Returns:
            Highest-scored READY Task, or None.
        """
        return await self._select_next()

    # ── Statistics ───────────────────────────────────────────────────────────

    async def stats(self) -> dict:
        """Return scheduler health statistics.

        Returns:
            Dict with total task count, state breakdown, and average score.
        """
        async with self._lock:
            tasks = list(self._tasks.values())
        by_state: Dict[str, int] = {}
        for t in tasks:
            by_state[t.state] = by_state.get(t.state, 0) + 1
        avg = sum(t.schedule_score for t in tasks) / len(tasks) if tasks else 0.0
        return {
            "total_tasks":    len(tasks),
            "by_state":       by_state,
            "average_score":  round(avg, 4),
        }
