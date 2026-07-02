from collections import deque
import random
import threading

class Task:
    def __init__(self, pid, name, priority):
        self.pid = pid
        self.name = name
        self.priority = priority
        self._in_queue = True

class HybridScheduler:
    """Thread-safe hybrid scheduler with quantum-inspired priority weighting."""
    
    def __init__(self):
        self._task_queue = deque()
        self._current_pid = 1000
        self._lock = threading.Lock()
        self._task_map = {}  # pid -> Task for O(1) lookup

    def add_task(self, name, priority=1):
        """Add a new task to the scheduler. Thread-safe."""
        with self._lock:
            task = Task(self._current_pid, name, priority)
            self._task_queue.append(task)
            self._task_map[task.pid] = task
            self._current_pid += 1
            return task.pid

    def get_next_task(self):
        """Get next task using quantum-inspired weighted selection. Thread-safe."""
        with self._lock:
            if not self._task_queue:
                return None
            
            # Build list of valid tasks with their weights
            valid_tasks = []
            weights = []
            for task in self._task_queue:
                if task._in_queue:
                    valid_tasks.append(task)
                    weights.append(task.priority)
            
            if not valid_tasks:
                return None
            
            # Weighted random selection (quantum-inspired)
            task = random.choices(valid_tasks, weights=weights, k=1)[0]
            task._in_queue = False
            self._task_queue.remove(task)
            return task
    
    def requeue_task(self, task):
        """Return a task to the queue (e.g., after time-slice expiration)."""
        with self._lock:
            if task.pid in self._task_map and not task._in_queue:
                task._in_queue = True
                self._task_queue.append(task)
    
    def remove_task(self, pid):
        """Remove a task from the scheduler."""
        with self._lock:
            if pid in self._task_map:
                self._task_map[pid]._in_queue = False
                del self._task_map[pid]
