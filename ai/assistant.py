import os
from typing import Dict


class AIAssistant:
    def __init__(self):
        self.memory: Dict[str, str] = {}
        self.permissions = {"train_local": False}

    def predict_task_success(self, task) -> float:
        base = 0.6
        if task.priority > 1.0:
            base += 0.1
        if task.name in self.memory:
            base += 0.1
        return min(0.99, base)

    def respond(self, prompt: str) -> str:
        prompt = prompt.lower().strip()
        if "status" in prompt:
            return "Umer AI assistant is online."
        if "hello" in prompt:
            return "Hello. Umer OS is ready."
        return f"Received: {prompt}"

    def remember(self, key: str, value: str):
        if self.permissions["train_local"]:
            self.memory[key] = value