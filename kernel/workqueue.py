"""
Umer OS Workqueue Subsystem
===========================
Inspired by Linux's workqueue.c, this subsystem handles deferred execution
of functions that don't need their own full Task/PID context, or for background
kernel maintenance jobs.
"""

import asyncio
import logging
from typing import Callable, Coroutine, Any, List

log = logging.getLogger("UmerOS.WorkQueue")

class WorkItem:
    """Represents a piece of deferred work."""
    def __init__(self, func: Callable[..., Coroutine], name: str = "unnamed_work"):
        self.func = func
        self.name = name

class WorkQueue:
    """Manages execution of background work items using asyncio tasks."""
    
    def __init__(self):
        self.queue: asyncio.Queue[WorkItem] = asyncio.Queue()
        self.workers: List[asyncio.Task] = []
        self._running = False
        log.info("WorkQueue subsystem initialized")

    def schedule_work(self, func: Callable[..., Coroutine], name: str = "deferred_work") -> None:
        """Schedule an async function to be executed by a worker."""
        item = WorkItem(func, name)
        self.queue.put_nowait(item)
        log.debug("Scheduled work item: %s", name)

    def start_workers(self, num_workers: int = 2) -> None:
        """Start the background worker tasks."""
        if self._running:
            return
            
        self._running = True
        for i in range(num_workers):
            task = asyncio.create_task(self._worker_loop(i))
            self.workers.append(task)
        log.info("Started %d workqueue background workers", num_workers)

    async def stop_workers(self) -> None:
        """Stop all background workers gracefully."""
        self._running = False
        for worker in self.workers:
            worker.cancel()
            
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)
            self.workers.clear()
        log.info("WorkQueue stopped")

    async def _worker_loop(self, worker_id: int) -> None:
        """The main loop for a single worker."""
        while self._running:
            try:
                # Wait for work with a timeout to allow graceful shutdown
                item = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
                
            try:
                log.debug("Worker %d executing '%s'", worker_id, item.name)
                await item.func()
                log.debug("Worker %d completed '%s'", worker_id, item.name)
            except Exception as e:
                log.error("WorkItem '%s' failed in worker %d: %s", item.name, worker_id, e)
            finally:
                self.queue.task_done()
