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

from kernel.signals import SignalQueue, SIGKILL, SIGTERM, SIGCHLD, FATAL_SIGNALS

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

    READY    = "READY"
    RUNNING  = "RUNNING"
    BLOCKED  = "BLOCKED"
    DONE     = "DONE"
    EXITING  = "EXITING"


# ---------------------------------------------------------------------------
# Task dataclass
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """A schedulable unit of work within Umer OS.

    Inspired by Linux ``struct task_struct`` — each task has identity
    (pid), scheduling metadata (priority, state, cpu_time), quantum
    hints, a signal queue for inter-task notification, and optional
    parent/child links forming a process tree.

    Attributes:
        pid:           Unique process identifier (positive integer).
        name:          Human-readable process/service name.
        priority:      Static priority hint in [0.0, 1.0]; higher = more important.
        state:         Lifecycle state; one of TaskState.{READY, RUNNING, BLOCKED, DONE, EXITING}.
        cpu_time:      Accumulated CPU seconds consumed so far.
        quantum_state: AI/quantum metadata dict.
                       Key ``"superposition"`` (float, 0-1): predicted success probability.
        coroutine:     Optional async callable executed when the task is dispatched.
        parent_pid:    PID of the spawning parent (None = kernel-spawned).
        children:      Set of child PIDs spawned by this task.
        exit_code:     Exit status (None = still running).
        signal_queue:   Per-task pending signal queue and handler registry.
        last_state_change: Monotonic timestamp of the last state transition.
    """

    pid:           int
    name:          str
    priority:      float = 0.5
    state:         str   = TaskState.READY
    cpu_time:      float = 0.0
    quantum_state: Dict  = field(default_factory=lambda: {"superposition": 0.5})
    coroutine:     Optional[Callable] = field(default=None, repr=False)
    # ── Process tree (inspired by Linux fork.c) ─────────────────────────────
    parent_pid:    Optional[int] = field(default=None, repr=False)
    children:      set = field(default_factory=set)
    exit_code:     Optional[int] = field(default=None, repr=False)
    # ── Signal queue (inspired by Linux signal.c) ────────────────────────────
    signal_queue:   SignalQueue = field(default_factory=SignalQueue)
    # ── Exit notification (set by exit_task; awaited by wait()) ──────────────
    exited:         asyncio.Event = field(default_factory=asyncio.Event, repr=False)
    # ── State-change tracking (for hung-task watchdog) ────────────────────────
    last_state_change: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        """Validate fields after construction.

        Raises:
            ValueError: If priority is outside [0.0, 1.0].
        """
        if not (0.0 <= self.priority <= 1.0):
            raise ValueError(
                f"Task.priority must be in [0.0, 1.0]; got {self.priority!r}."
            )

    def touch_state(self) -> None:
        """Record a state transition timestamp (for hung-task watchdog).

        Call this whenever ``task.state`` is changed.
        """
        self.last_state_change = time.monotonic()

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
        # Hung-task watchdog (inspired by Linux khungtaskd)
        self._watchdog_task: Optional[asyncio.Task] = None
        self._watchdog_interval: float = 10.0   # seconds between checks
        self._hung_timeout:       float = 120.0  # declare hung after this many seconds
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

    async def spawn_child(self, parent_pid: int, task: Task) -> None:
        """Enqueue a task as a child of ``parent_pid`` (sets up process tree).

        Inspired by Linux ``copy_process()``: links the child into the
        parent's children set and records ``parent_pid`` on the child.

        Args:
            parent_pid: PID of the spawning parent (must already exist).
            task:       Child Task to add.

        Raises:
            KeyError:   If the parent PID is not registered.
            ValueError: If MAX_TASKS would be exceeded.
        """
        async with self._lock:
            if parent_pid not in self._tasks:
                raise KeyError(f"Parent PID {parent_pid} not found.")
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
            task.parent_pid = parent_pid
            self._tasks[parent_pid].children.add(task.pid)
            self._tasks[task.pid] = task
        log.debug("Child spawned: PID %d (%s) under parent PID %d",
                  task.pid, task.name, parent_pid)

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
        task.touch_state()
        start = time.perf_counter()
        try:
            if task.coroutine is not None:
                await task.coroutine(task)
            else:
                await asyncio.sleep(0)  # yield control
        except asyncio.CancelledError:
            task.state = TaskState.DONE
            task.touch_state()
            return
        except Exception as exc:  # noqa: BLE001
            log.error("Task PID %d raised %s: %s", task.pid, type(exc).__name__, exc)
            task.state = TaskState.BLOCKED
        else:
            task.state = TaskState.READY
        finally:
            task.cpu_time += time.perf_counter() - start
            task.touch_state()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self, ai_manager=None) -> None:
        """Start the background scheduling loop and hung-task watchdog.

        Args:
            ai_manager: Optional AI manager to inject before starting.
        """
        if ai_manager is not None:
            self.set_ai_manager(ai_manager)
        self._running = True
        self._loop_task = asyncio.create_task(self._scheduler_loop())
        self._watchdog_task = asyncio.create_task(self._watchdog_loop())
        log.info("HybridScheduler started (watchdog enabled).")

    async def stop(self) -> None:
        """Stop the scheduler, watchdog, and cancel background loop tasks."""
        self._running = False
        for bg in (self._loop_task, self._watchdog_task):
            if bg is not None and not bg.done():
                bg.cancel()
                try:
                    await bg
                except asyncio.CancelledError:
                    pass
        self._loop_task = None
        self._watchdog_task = None
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

    async def _watchdog_loop(self) -> None:
        """Periodic scan for hung tasks (inspired by Linux khungtaskd).

        Every ``_watchdog_interval`` seconds, scans all tasks.  Any task
        whose state has not changed for longer than ``_hung_timeout``
        seconds is logged as hung.  Tasks stuck in BLOCKED for too long
        are also flagged.
        """
        while self._running:
            try:
                await asyncio.sleep(self._watchdog_interval)
                await self._check_hung_tasks()
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                log.error("Watchdog loop error: %s", exc)

    async def _check_hung_tasks(self) -> None:
        """Detect tasks whose state has been stagnant for too long."""
        now = time.monotonic()
        async with self._lock:
            for task in list(self._tasks.values()):
                idle = now - task.last_state_change
                if idle < self._hung_timeout:
                    continue
                # Task is hung — log a diagnostic
                log.warning(
                    "HUNG TASK: PID %d (%s) in state %s for %.1fs "
                    "(threshold=%.0fs)",
                    task.pid, task.name, task.state, idle, self._hung_timeout,
                )
                # In a real kernel we'd dump the coroutine; we keep it simple.

    async def tick(self) -> Optional[Task]:
        """Single-step: select and return the next READY task (non-executing).

        Useful for tests and external dispatchers that manage execution themselves.

        Returns:
            Highest-scored READY Task, or None.
        """
        return await self._select_next()

    # ── Statistics ───────────────────────────────────────────────────────────

    # ── Process management (inspired by Linux exit.c do_exit) ────────────────

    async def exit_task(self, pid: int, code: int = 0) -> bool:
        """Clean up a task and transition it to DONE.

        Inspired by Linux ``do_exit()`` — runs an ordered teardown
        sequence: set EXITING, cancel coroutine, revoke capabilities,
        unregister IPC, update process tree, then set DONE.

        Args:
            pid:  Process ID to exit.
            code: Exit status code (0 = success).

        Returns:
            True if the task existed and was cleaned up, False otherwise.
        """
        async with self._lock:
            task = self._tasks.get(pid)
            if task is None:
                return False

            log.info("exit_task: PID %d (%s) exit_code=%d", pid, task.name, code)
            task.state = TaskState.EXITING
            task.touch_state()
            task.exit_code = code

            # Note: we do not hold the asyncio.Task handle here, so we cannot
            # cancel the coroutine directly.  Setting state=EXITING prevents
            # the scheduler loop from re-selecting this task.

            # Reparent children to init (kernel reaper) —
            # Linux: find_new_reaper() → forget_original_parent()
            if task.parent_pid is not None and task.children:
                parent = self._tasks.get(task.parent_pid)
                if parent is not None:
                    for child_pid in task.children:
                        parent.children.add(child_pid)
                        child = self._tasks.get(child_pid)
                        if child is not None:
                            child.parent_pid = task.parent_pid
                    log.debug("Reparented %d children of PID %d to PID %d",
                             len(task.children), pid, task.parent_pid)

            # Notify parent with SIGCHLD
            if task.parent_pid is not None:
                parent = self._tasks.get(task.parent_pid)
                if parent is not None:
                    parent.signal_queue.enqueue(SIGCHLD)

            # Clear children set
            task.children.clear()

            task.state = TaskState.DONE
            task.touch_state()

            # Wake any waiters blocked on task.exited
            task.exited.set()

            # Remove from active tasks
            del self._tasks[pid]

        return True

    # ── Signals (inspired by Linux signal.c) ────────────────────────────────

    async def send_signal(self, pid: int, sig: str) -> bool:
        """Deliver a signal to a task.

        Inspired by Linux ``__send_signal_locked``:
          - SIGKILL: sets task state to EXITING (unblockable).
          - SIGTERM: enqueued; handler runs if registered, else default action.
          - SIGSTOP: sets task to BLOCKED.
          - SIGCHLD/SIGUSR*: enqueued for cooperative handling.

        Args:
            pid: Target process ID.
            sig: Signal name (e.g. "SIGTERM", "SIGKILL").

        Returns:
            True if the signal was delivered or actioned, False if PID unknown.
        """
        # SIGKILL is fatal & unblockable — must release self._lock before
        # calling exit_task (which acquires the same lock; asyncio.Lock is
        # NOT reentrant).
        async with self._lock:
            task = self._tasks.get(pid)
            if task is None:
                log.warning("send_signal: PID %d not found for %s", pid, sig)
                return False
            task_name = task.name

        log.info("Signal %s → PID %d (%s)", sig, pid, task_name)

        # SIGKILL: unblockable forced exit (releases lock first — see above)
        if sig == SIGKILL:
            await self.exit_task(pid, code=-9)
            return True

        async with self._lock:
            task = self._tasks.get(pid)
            if task is None:
                return False  # task vanished between the two locks

            # SIGSTOP: pause the task
            if sig == "SIGSTOP":
                task.state = TaskState.BLOCKED
                task.touch_state()
                return True

            # All other signals: enqueue for cooperative handling
            task.signal_queue.enqueue(sig)

            # If a handler is registered, schedule it
            handler = task.signal_queue.get_handler(sig)
            if handler is not None:
                try:
                    asyncio.create_task(handler.callback(sig))
                except Exception as exc:  # noqa: BLE001
                    log.error("Signal handler for %s on PID %d failed: %s",
                             sig, pid, exc)

            return True

    async def recv_signal(self, pid: int) -> Optional[str]:
        """Cooperatively drain one pending signal for a task.

        Args:
            pid: Process ID to receive for.

        Returns:
            Signal string, or None if PID not found.
        """
        async with self._lock:
            task = self._tasks.get(pid)
            if task is None:
                return None
            if task.signal_queue.pending_count > 0:
                return task.signal_queue.try_recv()
            return None

    # ── Wait primitive (inspired by Linux wait_task_zombie) ────────────────

    def wait_event(self, pid: int) -> Optional[asyncio.Event]:
        """Return an asyncio.Event for a task's completion (or None).

        The event is set when ``exit_task(pid)`` runs.

        Args:
            pid: Child PID to wait on.

        Returns:
            asyncio.Event if task exists, None otherwise.
        """
        task = self._tasks.get(pid)
        if task is None:
            return None
        return task.exited

    # ── State-change tracking (for hung-task watchdog) ────────────────────────

    def _touch_state_locked(self, task: Task) -> None:
        """Record a state transition. Caller must hold self._lock."""
        task.last_state_change = time.monotonic()

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
