"""
Asyncio-based microkernel scheduler prototype with quantum-inspired heuristic.
Each Task is cooperative (an asyncio coroutine). The scheduler runs time-slices
using asyncio.wait_for to bound per-slice runtime.
"""
from dataclasses import dataclass, field
import asyncio
import time
import uuid
from typing import Callable, Dict, Optional, Any

@dataclass
class Task:
    id: str
    coro_factory: Callable[..., Any]  # returns coroutine when called
    priority: int = 0
    created_at: float = field(default_factory=time.time)
    cpu_time: float = 0.0
    last_run: Optional[float] = None
    quantum_state: Dict[str, float] = field(default_factory=dict)
    success_prob: float = 0.5  # predicted by AI Orchestrator (0..1)

class Scheduler:
    def __init__(self, time_slice: float = 0.05):
        self.ready: Dict[str, Task] = {}
        self.loop = asyncio.get_event_loop()
        self.time_slice = time_slice
        self._running = False

    def add_task(self, coro_factory: Callable[..., Any], priority: int = 0, quantum_state=None, success_prob: float = 0.5) -> str:
        t = Task(id=str(uuid.uuid4()), coro_factory=coro_factory, priority=priority,
                 quantum_state=quantum_state or {}, success_prob=success_prob)
        self.ready[t.id] = t
        return t.id

    def _score(self, task: Task) -> float:
        # Avoid division by zero; accumulate fairness via cpu_time
        return (max(0.0001, task.success_prob) * (1.0 + task.priority)) / (1.0 + task.cpu_time)

    async def _run_task_slice(self, task: Task):
        start = time.time()
        coro = task.coro_factory()
        try:
            await asyncio.wait_for(coro, timeout=self.time_slice)
            # Completed normally
            elapsed = time.time() - start
            task.cpu_time += elapsed
            task.last_run = time.time()
            self.ready.pop(task.id, None)
        except asyncio.TimeoutError:
            # Time slice exhausted; update accounting and keep task
            task.cpu_time += self.time_slice
            task.last_run = time.time()
        except Exception as e:
            # In microkernel, escalate to crash manager; here just print and drop
            print(f"[scheduler] Task {task.id} crashed: {e}")
            self.ready.pop(task.id, None)

    async def _scheduler_loop(self):
        while self._running:
            if not self.ready:
                await asyncio.sleep(0.01)
                continue
            # Here we could query an AI Orchestrator to refresh success_prob.
            # For the prototype, we use existing success_prob in Task.
            task = max(self.ready.values(), key=self._score)
            await self._run_task_slice(task)

    def start(self):
        if self._running:
            return
        self._running = True
        self.loop.create_task(self._scheduler_loop())

    def stop(self):
        self._running = False