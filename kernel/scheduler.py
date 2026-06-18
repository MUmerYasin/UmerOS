"""
Asyncio-based microkernel scheduler prototype with quantum-inspired heuristic.
Each Task is cooperative (an asyncio coroutine). The scheduler runs time-slices
using asyncio.wait_for to bound per-slice runtime.
"""
from dataclasses import dataclass, field
import asyncio
import time
import uuid
from typing import Callable, Dict, Optional, Any, Dict, Optional



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
    pid: int = 0
    name: str = ""
    priority: float
    state: str = "READY"
    cpu_time: float = 0.0
    quantum_state: Dict = field(default_factory=lambda: {"superposition": 0.0})

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



class HybridScheduler:
    def __init__(self):
        self.tasks: Dict[int, Task] = {}
        self.lock = asyncio.Lock()
        self.ai = None
        self.running = False

    async def start(self, ai_manager):
        self.ai = ai_manager
        self.running = True
        asyncio.create_task(self._scheduler_loop())

    async def add_task(self, task: Task):
        async with self.lock:
            self.tasks[task.pid] = task
            task.quantum_state["superposition"] = self.ai.predict_task_success(task)
        async def _scheduler_loop(self):
        while self.running:
            async with self.lock:
                ready = [t for t in self.tasks.values() if t.state == "READY"]
                if not ready:
                    pass
                else:
                    ready.sort(
                        key=lambda t: t.quantum_state["superposition"] / (t.cpu_time + 0.1),
                        reverse=True,
                    )
                    selected = ready[0]
                    selected.state = "RUNNING"
                    await self._execute_task(selected)
                    selected.state = "READY"
            await asyncio.sleep(0.01)

    async def _execute_task(self, task: Task):
        start = time.perf_counter()
        await asyncio.sleep(0.05)
        task.cpu_time += time.perf_counter() - start

    async def stop(self):
        self.running = False