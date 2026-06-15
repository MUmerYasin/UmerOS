"""
Umer AI Assistant and Self-Healing Module
- Lightweight rule-based AI with predictive resource allocation.
- Self-healing: catches exceptions in wrapped functions and attempts recovery.
"""

import threading
import time
import random
from collections import deque

class PredictiveResourceManager:
    """Predicts resource usage based on simple history."""
    def __init__(self):
        self.history = deque(maxlen=10)  # store recent load percentages
        self.current_load = 0.0

    def record_load(self, cpu_percent):
        self.history.append(cpu_percent)
        self.current_load = cpu_percent

    def predict_next(self):
        """Naive prediction: average of last few readings + trend."""
        if not self.history:
            return 0.0
        avg = sum(self.history) / len(self.history)
        if len(self.history) >= 2:
            trend = self.history[-1] - self.history[0]
            avg += trend * 0.1
        return max(0.0, min(100.0, avg))

    def preallocate(self):
        """Based on prediction, suggest resource allocation."""
        predicted = self.predict_next()
        if predicted > 80:
            return "Allocate extra RAM and throttle background tasks."
        elif predicted > 50:
            return "Normal allocation with caching."
        else:
            return "Minimal resource allocation, conserve energy."

class AIAssistant:
    """
    Local AI assistant that understands natural-language-ish commands.
    Uses pattern matching (no actual LLM for zero-dependency demo).
    """
    def __init__(self):
        self.resource_manager = PredictiveResourceManager()
        self.commands = {
            "hello": "Hello! How can I assist you with Umer OS?",
            "status": self.get_system_status,
            "optimize": self.optimize_system,
            "help": "Available commands: hello, status, optimize, help",
        }
        # Simulate CPU load readings in background
        self._load_thread = threading.Thread(target=self._simulate_load, daemon=True)
        self._load_thread.start()

    def _simulate_load(self):
        while True:
            load = random.uniform(10, 90)
            self.resource_manager.record_load(load)
            time.sleep(5)

    def get_system_status(self):
        pred = self.resource_manager.predict_next()
        rec = self.resource_manager.preallocate()
        return f"Predicted load: {pred:.1f}%. Recommendation: {rec}"

    def optimize_system(self):
        # AI optimization: trigger quantum scheduler
        return "Initiating quantum-inspired resource optimization..."

    def process_command(self, text):
        text = text.lower().strip()
        if text in self.commands:
            cmd = self.commands[text]
            if callable(cmd):
                return cmd()
            else:
                return cmd
        else:
            # Simple self-learning: add to known commands
            self.commands[text] = f"Command '{text}' noted. Not yet implemented."
            return f"I don't understand '{text}'. Type 'help' for options."

class SelfHealing:
    """Decorator/utility that catches exceptions and restarts functions."""
    @staticmethod
    def run_with_recovery(func, max_retries=3, *args, **kwargs):
        attempts = 0
        while attempts < max_retries:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                attempts += 1
                print(f"[SelfHealing] Error in {func.__name__}: {e}. Retry {attempts}/{max_retries}")
                time.sleep(1)
        print(f"[SelfHealing] Failed after {max_retries} retries. Rolling back.")
        # Could attempt to restore a previous state here
        raise RuntimeError("Self-healing exhausted.")

if __name__ == "__main__":
    ai = AIAssistant()
    print(ai.process_command("status"))
    print(ai.process_command("hello"))