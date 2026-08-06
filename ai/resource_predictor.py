"""
Umer OS Resource Predictor
==========================
Statistical resource prediction with EWMA, trend analysis, and spike detection.

Replaces naive random-based prediction with proper time-series analysis.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import collections
import math
import time
from typing import Any, Deque, Dict, List, Optional, Tuple


class ResourcePredictor:
    """Statistical resource predictor using EWMA and linear trend analysis.

    Maintains per-PID history and provides:
      - Spike detection via z-score analysis (not random).
      - Next-load prediction using EWMA + trend extrapolation.
      - Resource preallocation recommendations based on predicted load.
      - Memory pressure detection and workload classification.
    """

    # Spike detection thresholds
    SPIKE_Z_THRESHOLD = 2.0       # z-score above this = spike
    SPIKE_MIN_SAMPLES = 5         # minimum samples before spike detection

    # Workload classification
    LOAD_LOW = 30.0
    LOAD_MEDIUM = 60.0
    LOAD_HIGH = 80.0

    def __init__(self, window: int = 30, alpha: float = 0.3) -> None:
        """Initialise the resource predictor.

        Args:
            window: Maximum number of historical samples to retain.
            alpha:  EWMA smoothing factor (0 < alpha <= 1).
        """
        self._window = window
        self._alpha = alpha

        # Per-PID CPU history (% scale 0-100)
        self._cpu_history: Dict[int, Deque[float]] = {}
        # Per-PID memory history (MB)
        self._mem_history: Dict[int, Deque[float]] = {}
        # Global CPU history (aggregated)
        self._global_cpu: Deque[float] = collections.deque(maxlen=window * 10)

        # Spike log: list of (timestamp, pid, value, z_score)
        self._spike_log: List[Tuple[float, int, float, float]] = []

        # Per-PID trend slopes (recomputed on each update)
        self._cpu_trends: Dict[int, float] = {}
        self._mem_trends: Dict[int, float] = {}

    # ── Data ingestion ────────────────────────────────────────────────────────

    def log_usage(self, pid: int, memory_mb: float, cpu_percent: float) -> None:
        """Record a resource usage sample for a process.

        Args:
            pid:         Process ID.
            memory_mb:   Current memory usage in MB.
            cpu_percent: CPU usage as percentage [0, 100].
        """
        cpu_clamped = max(0.0, min(100.0, cpu_percent))
        mem_clamped = max(0.0, memory_mb)

        cpu_dq = self._cpu_history.setdefault(
            pid, collections.deque(maxlen=self._window)
        )
        mem_dq = self._mem_history.setdefault(
            pid, collections.deque(maxlen=self._window)
        )

        cpu_dq.append(cpu_clamped)
        mem_dq.append(mem_clamped)
        self._global_cpu.append(cpu_clamped)

        # Update trend slopes
        if len(cpu_dq) >= 3:
            self._cpu_trends[pid] = self._linear_trend(cpu_dq)
        if len(mem_dq) >= 3:
            self._mem_trends[pid] = self._linear_trend(mem_dq)

    # ── Statistical helpers ───────────────────────────────────────────────────

    def _ewma(self, samples: Deque[float], default: float = 0.0) -> float:
        """Compute exponentially-weighted moving average."""
        if not samples:
            return default
        result = float(samples[0])
        for v in list(samples)[1:]:
            result = self._alpha * float(v) + (1 - self._alpha) * result
        return result

    def _stddev(self, samples: Deque[float]) -> float:
        """Compute sample standard deviation."""
        if len(samples) < 2:
            return 0.0
        vals = [float(v) for v in samples]
        mean = sum(vals) / len(vals)
        variance = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
        return math.sqrt(variance)

    def _linear_trend(self, samples: Deque[float]) -> float:
        """Compute linear trend slope via least-squares regression.

        Returns:
            Slope per sample (positive = increasing, negative = decreasing).
        """
        n = len(samples)
        if n < 3:
            return 0.0
        vals = [float(v) for v in samples]
        x_mean = (n - 1) / 2.0
        y_mean = sum(vals) / n
        num = sum((i - x_mean) * (vals[i] - y_mean) for i in range(n))
        den = sum((i - x_mean) ** 2 for i in range(n))
        return num / den if den != 0 else 0.0

    def _z_score(self, value: float, samples: Deque[float]) -> float:
        """Compute z-score of value against the sample distribution."""
        if len(samples) < self.SPIKE_MIN_SAMPLES:
            return 0.0
        vals = [float(v) for v in samples]
        mean = sum(vals) / len(vals)
        sd = self._stddev(samples)
        if sd < 1e-9:
            return 0.0
        return (value - mean) / sd

    # ── Spike detection ───────────────────────────────────────────────────────

    def predict_spike(self, pid: int) -> bool:
        """Detect if the latest CPU reading is a statistical spike.

        Uses z-score analysis instead of random probability.

        Args:
            pid: Process ID to check.

        Returns:
            True if a spike is detected (latest value > z_threshold above mean).
        """
        hist = self._cpu_history.get(pid)
        if not hist or len(hist) < self.SPIKE_MIN_SAMPLES:
            return False

        latest = hist[-1]
        z = self._z_score(latest, hist)

        if z > self.SPIKE_Z_THRESHOLD:
            self._spike_log.append((time.time(), pid, latest, z))
            return True
        return False

    def detect_memory_pressure(self, pid: int, threshold_mb: float = 512.0) -> bool:
        """Detect if a process is experiencing memory pressure.

        A process is under memory pressure if:
          - Current usage exceeds threshold, AND
          - Memory trend is increasing (positive slope).

        Args:
            pid:           Process ID.
            threshold_mb:  Memory threshold in MB.

        Returns:
            True if memory pressure is detected.
        """
        hist = self._mem_history.get(pid)
        if not hist or not len(hist):
            return False

        current = hist[-1]
        trend = self._mem_trends.get(pid, 0.0)
        return current > threshold_mb and trend > 0.5

    def get_spike_log(self) -> List[Dict[str, Any]]:
        """Return the spike detection log."""
        return [
            {"ts": ts, "pid": pid, "value": val, "z_score": z}
            for ts, pid, val, z in self._spike_log
        ]

    # ── Prediction ────────────────────────────────────────────────────────────

    def predict_next_load(self) -> float:
        """Predict next global CPU load using EWMA + trend extrapolation.

        Combines the exponentially-weighted moving average with the linear
        trend to produce a more accurate forecast.

        Returns:
            Predicted CPU load percentage [0.0, 100.0].
        """
        if not self._global_cpu:
            return 0.0

        base = self._ewma(self._global_cpu, 0.0)
        trend = self._linear_trend(self._global_cpu)

        # Extrapolate one step ahead, dampened by alpha
        predicted = base + trend * self._alpha
        return max(0.0, min(100.0, predicted))

    def predict_pid_load(self, pid: int) -> float:
        """Predict next CPU load for a specific process.

        Args:
            pid: Process ID.

        Returns:
            Predicted CPU load percentage [0.0, 100.0].
        """
        hist = self._cpu_history.get(pid)
        if not hist or not len(hist):
            return 0.0
        base = self._ewma(hist, 0.0)
        trend = self._cpu_trends.get(pid, 0.0)
        predicted = base + trend * self._alpha
        return max(0.0, min(100.0, predicted))

    def predict_pid_memory(self, pid: int) -> float:
        """Predict next memory usage for a specific process.

        Args:
            pid: Process ID.

        Returns:
            Predicted memory in MB.
        """
        hist = self._mem_history.get(pid)
        if not hist or not len(hist):
            return 0.0
        base = self._ewma(hist, 0.0)
        trend = self._mem_trends.get(pid, 0.0)
        predicted = base + trend * self._alpha
        return max(0.0, predicted)

    def get_prediction_confidence(self, pid: int) -> float:
        """Return confidence in predictions for a PID [0.0, 1.0].

        Based on: sample count, volatility, and trend stability.
        """
        hist = self._cpu_history.get(pid)
        if not hist:
            return 0.0

        # More samples = more confidence
        sample_score = min(1.0, len(hist) / self._window)

        # Lower volatility = more confidence
        sd = self._stddev(hist)
        vol_score = max(0.0, 1.0 - sd / 50.0)  # normalize by 50% range

        # Stable trend = more confidence
        trend = abs(self._cpu_trends.get(pid, 0.0))
        trend_score = max(0.0, 1.0 - trend / 5.0)

        return round(0.4 * sample_score + 0.3 * vol_score + 0.3 * trend_score, 4)

    def get_workload_class(self, pid: int) -> str:
        """Classify the workload type for a process.

        Returns one of: "idle", "low", "medium", "high", "erratic".
        """
        hist = self._cpu_history.get(pid)
        if not hist or not len(hist):
            return "idle"

        avg = self._ewma(hist, 0.0)
        sd = self._stddev(hist)

        # High volatility = erratic
        if sd > 25.0:
            return "erratic"

        if avg < self.LOAD_LOW:
            return "low"
        elif avg < self.LOAD_MEDIUM:
            return "medium"
        else:
            return "high"

    # ── Resource recommendations ──────────────────────────────────────────────

    def preallocate_recommendation(self) -> str:
        """Generate a resource allocation recommendation based on predicted load.

        Uses EWMA + trend analysis instead of naive averaging.

        Returns:
            Human-readable recommendation string.
        """
        predicted = self.predict_next_load()
        trend = self._linear_trend(self._global_cpu) if self._global_cpu else 0.0

        if predicted > self.LOAD_HIGH:
            msg = "ALERT: High load predicted ({:.0f}%)".format(predicted)
            if trend > 1.0:
                msg += " — load INCREASING, consider immediate scaling."
            else:
                msg += " — allocate extra RAM and throttle background tasks."
            return msg
        elif predicted > self.LOAD_MEDIUM:
            msg = "Moderate load predicted ({:.0f}%)".format(predicted)
            if trend > 0.5:
                msg += " — trend rising, enable caching and prepare for scale."
            else:
                msg += " — normal allocation with caching."
            return msg
        elif predicted > self.LOAD_LOW:
            return "Low load predicted ({:.0f}%). Normal allocation.".format(predicted)
        else:
            return "Minimal load predicted ({:.0f}%). Conserve energy, enter low-power mode.".format(predicted)

    def get_system_summary(self) -> Dict[str, Any]:
        """Return a summary of the resource prediction state."""
        all_pids = set(self._cpu_history.keys()) | set(self._mem_history.keys())
        classes = {}
        for pid in all_pids:
            cls = self.get_workload_class(pid)
            classes[cls] = classes.get(cls, 0) + 1

        return {
            "tracked_pids": len(all_pids),
            "global_cpu_avg": round(self._ewma(self._global_cpu, 0.0), 2),
            "global_cpu_trend": round(self._linear_trend(self._global_cpu), 4) if self._global_cpu else 0.0,
            "predicted_next_load": round(self.predict_next_load(), 2),
            "workload_distribution": classes,
            "total_spikes_detected": len(self._spike_log),
            "recommendation": self.preallocate_recommendation(),
        }
