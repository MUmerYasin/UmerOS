import random
from collections import deque

class ResourcePredictor:
    def __init__(self):
        # In a real scenario, this would load a scikit-learn or PyTorch model
        # For now, we simulate predictive heuristics
        self.history = []
        
        # Deepseek Merged: moving average tracker
        self.load_history = deque(maxlen=10)

    def log_usage(self, pid, memory_mb, cpu_percent):
        self.history.append({'pid': pid, 'mem': memory_mb, 'cpu': cpu_percent})
        self.load_history.append(cpu_percent)

    def predict_spike(self, pid):
        # Simulated AI prediction: 20% chance to predict a memory spike
        prediction = random.random() < 0.2
        if prediction:
            print(f"[AI Predictor] WARNING: High probability of memory spike detected for PID {pid}")
        return prediction

    # --- Deepseek Merged Code Below ---
    def predict_next_load(self) -> float:
        """Naive prediction: average of last few readings + trend."""
        if not self.load_history:
            return 0.0
        avg = sum(self.load_history) / len(self.load_history)
        if len(self.load_history) >= 2:
            trend = self.load_history[-1] - self.load_history[0]
            avg += trend * 0.1
        return max(0.0, min(100.0, avg))

    def preallocate_recommendation(self) -> str:
        """Based on prediction, suggest resource allocation."""
        predicted = self.predict_next_load()
        if predicted > 80:
            return "Allocate extra RAM and throttle background tasks."
        elif predicted > 50:
            return "Normal allocation with caching."
        else:
            return "Minimal resource allocation, conserve energy."
