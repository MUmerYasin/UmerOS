import random

class ResourcePredictor:
    def __init__(self):
        # In a real scenario, this would load a scikit-learn or PyTorch model
        # For now, we simulate predictive heuristics
        self.history = []

    def log_usage(self, pid, memory_mb, cpu_percent):
        self.history.append({'pid': pid, 'mem': memory_mb, 'cpu': cpu_percent})

    def predict_spike(self, pid):
        # Simulated AI prediction: 20% chance to predict a memory spike
        prediction = random.random() < 0.2
        if prediction:
            print(f"[AI Predictor] WARNING: High probability of memory spike detected for PID {pid}")
        return prediction
