from collections import deque
import random
import asyncio

class Task:
    def __init__(self, pid, name, priority):
        self.pid = pid
        self.name = name
        self.priority = priority

class HybridScheduler:
    def __init__(self):
        self.task_queue = deque()
        self.current_pid = 1000

    def add_task(self, name, priority=1):
        task = Task(self.current_pid, name, priority)
        self.task_queue.append(task)
        self.current_pid += 1
        return task.pid

    def get_next_task(self):
        if not self.task_queue:
            return None
        # Simulating Quantum Superposition Priority:
        # Instead of completely fair scheduling, we apply a randomized probability
        # amplitude to select tasks (simulating quantum states collapse)
        weights = [t.priority for t in self.task_queue]
        task = random.choices(self.task_queue, weights=weights, k=1)[0]
        self.task_queue.remove(task)
        return task