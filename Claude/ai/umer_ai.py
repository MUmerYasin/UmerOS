"""
Umer OS AI Orchestration Engine  [TODAY / EXPERIMENTAL]
=======================================================
Provides four AI subsystems that the Umer OS kernel integrates:

TODAY:
  NullAIResourceManager — zero-dependency stub for boot.
  AIResourceManager     — LSTM-inspired heuristic predictor [TODAY-heuristic].
  LocalAIAssistant      — simple keyword/rules assistant stub [TODAY-stub].
  SelfHealingEngine     — exception pattern monitor [EXPERIMENTAL].
  AIFirewall            — anomaly scoring [TODAY-heuristic].

EXPERIMENTAL:
  Full ONNX Runtime model loading for LSTM inference.

FUTURE:
  llama-cpp-python LLM, on-device training, QPU-accelerated inference.

Privacy guarantee: NO user data leaves the device by default.
All AI training is opt-in only (see ``AIGovernance``).

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import collections
import logging
import math
import time
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

log = logging.getLogger("UmerOS.AI")


# ---------------------------------------------------------------------------
# Null (bootstrap) AI resource manager
# ---------------------------------------------------------------------------

class NullAIResourceManager:
    """Minimal AI manager used before the full AIResourceManager is loaded.

    Returns fixed neutral values so the kernel and scheduler work correctly
    from first boot without requiring ML libraries.
    """

    def predict_task_success(self, task) -> float:
        """Return neutral 0.5 for any task."""
        return 0.5

    def predict_cpu_usage(self, pid: int, window: int = 10) -> float:
        """Return a neutral 50% CPU estimate."""
        return 0.5

    def predict_ram_usage(self, pid: int) -> int:
        """Return 4 MiB estimate."""
        return 4 * 1024 * 1024

    def rebalance_resources(self) -> None:
        """No-op stub."""


# ---------------------------------------------------------------------------
# AI Resource Manager
# ---------------------------------------------------------------------------

class AIResourceManager:
    """Heuristic-based resource predictor (LSTM-inspired, no ML framework).

    Maintains a rolling window of per-PID CPU and RAM samples.
    Prediction uses an exponentially-weighted moving average (EWMA) —
    a classic signal-processing technique that approximates an LSTM's
    short-term memory without requiring PyTorch/ONNX at runtime.

    EXPERIMENTAL: When onnxruntime is installed, a real LSTM model can be
    loaded via ``load_onnx_model(path)`` to replace the EWMA predictor.

    Args:
        window: Number of historical samples to retain per PID.
        alpha:  EWMA smoothing factor (0 < alpha ≤ 1).
    """

    def __init__(self, window: int = 20, alpha: float = 0.3) -> None:
        self._window = window
        self._alpha  = alpha
        # cpu_history[pid] = deque of float fractions [0,1]
        self._cpu_hist: Dict[int, Deque[float]] = {}
        # ram_history[pid] = deque of int bytes
        self._ram_hist: Dict[int, Deque[int]]   = {}
        # crash_count[pid] = int
        self._crashes:  Dict[int, int]           = collections.defaultdict(int)
        self._onnx_model = None  # EXPERIMENTAL: loaded via load_onnx_model()
        log.info("AIResourceManager initialised (EWMA predictor, window=%d).", window)

    # ── Data ingestion ────────────────────────────────────────────────────────

    def record_cpu(self, pid: int, usage: float) -> None:
        """Record a CPU usage sample for a process.

        Args:
            pid:   Process ID.
            usage: CPU fraction [0.0, 1.0].
        """
        dq = self._cpu_hist.setdefault(pid, collections.deque(maxlen=self._window))
        dq.append(max(0.0, min(1.0, usage)))

    def record_ram(self, pid: int, bytes_used: int) -> None:
        """Record a RAM usage sample for a process.

        Args:
            pid:        Process ID.
            bytes_used: Current RSS in bytes.
        """
        dq = self._ram_hist.setdefault(pid, collections.deque(maxlen=self._window))
        dq.append(max(0, bytes_used))

    def record_crash(self, pid: int) -> None:
        """Increment the crash counter for a process.

        Args:
            pid: Process ID.
        """
        self._crashes[pid] += 1
        log.warning("AIResourceManager: crash recorded for PID %d (total=%d).",
                    pid, self._crashes[pid])

    # ── EWMA helper ───────────────────────────────────────────────────────────

    def _ewma(self, samples: Deque, default: float) -> float:
        """Compute exponentially-weighted moving average.

        Args:
            samples: Deque of numeric values (oldest first).
            default: Return value when samples is empty.

        Returns:
            EWMA float.
        """
        if not samples:
            return default
        result = float(samples[0])
        for v in list(samples)[1:]:
            result = self._alpha * float(v) + (1 - self._alpha) * result
        return result

    # ── Predictions ───────────────────────────────────────────────────────────

    def predict_cpu_usage(self, pid: int, window: int = 10) -> float:
        """Predict next-tick CPU usage for a process.

        Args:
            pid:    Process ID.
            window: Ignored (kept for API compatibility; uses self._window).

        Returns:
            Predicted CPU fraction in [0.0, 1.0].
        """
        hist = self._cpu_hist.get(pid)
        return round(self._ewma(hist, 0.5), 4) if hist else 0.5

    def predict_ram_usage(self, pid: int) -> int:
        """Predict next-tick RAM usage for a process.

        Args:
            pid: Process ID.

        Returns:
            Predicted bytes (integer).
        """
        hist = self._ram_hist.get(pid)
        return int(self._ewma(hist, 4 * 1024 * 1024)) if hist else 4 * 1024 * 1024

    def predict_task_success(self, task) -> float:
        """Predict scheduling success probability for a task.

        Combines:
          - Historical crash rate: fewer crashes → higher score.
          - EWMA CPU: lower predicted load → easier to schedule soon.
          - Task priority: direct contribution.

        Args:
            task: Object with ``.pid`` and ``.priority`` attributes.

        Returns:
            Success probability in [0.0, 1.0].
        """
        crashes   = self._crashes.get(task.pid, 0)
        crash_pen = 1.0 / (1.0 + crashes)        # 1.0 for no crashes
        cpu_load  = self.predict_cpu_usage(task.pid)
        cpu_score = 1.0 - cpu_load               # low load → high score

        score = 0.5 * crash_pen + 0.3 * cpu_score + 0.2 * float(task.priority)
        return round(max(0.0, min(1.0, score)), 4)

    def rebalance_resources(self) -> None:
        """Analyse all PIDs and log rebalancing recommendations.

        In a full implementation this would send IPC messages to processes
        suggesting they shed load, release caches, or yield CPU.

        TODAY: Logs warnings for high-CPU or high-crash processes.
        """
        for pid, hist in self._cpu_hist.items():
            avg = self._ewma(hist, 0.0)
            if avg > 0.85:
                log.warning("Rebalance: PID %d avg CPU %.0f%% — consider throttling.",
                            pid, avg * 100)
        for pid, count in self._crashes.items():
            if count >= 3:
                log.error("Rebalance: PID %d crashed %d times — quarantine recommended.",
                          pid, count)

    # ── EXPERIMENTAL: ONNX model loading ─────────────────────────────────────

    def load_onnx_model(self, model_path: str) -> bool:
        """Load an ONNX Runtime LSTM model to replace the EWMA predictor.

        EXPERIMENTAL: Requires ``onnxruntime`` installed.

        Args:
            model_path: Path to an .onnx model file.

        Returns:
            True if loaded successfully, False otherwise.
        """
        try:
            import onnxruntime as ort  # type: ignore
            self._onnx_model = ort.InferenceSession(model_path)
            log.info("ONNX model loaded from '%s'.", model_path)
            return True
        except Exception as exc:
            log.error("Failed to load ONNX model: %s", exc)
            return False


# ---------------------------------------------------------------------------
# Local AI Assistant
# ---------------------------------------------------------------------------

class LocalAIAssistant:
    """Rule-based local AI assistant stub.

    TODAY: Keyword-matching with canned responses.
    EXPERIMENTAL: Semantic search over indexed files.
    FUTURE: Full on-device LLM via llama-cpp-python.

    Privacy: All responses generated locally; no network calls.
    """

    _RULES: List[Tuple[str, str]] = [
        ("optimize",    "Running resource optimiser — rebalancing CPU and RAM allocation."),
        ("status",      "System is operational. All kernel subsystems nominal."),
        ("help",        "Available commands: status, optimize, search <query>, uptime, shutdown."),
        ("uptime",      "Kernel uptime available via UmerKernel.uptime()."),
        ("shutdown",    "Call UmerKernel.shutdown() to safely stop all services."),
        ("quantum",     "Quantum simulation layer active. Real QPU integration: FUTURE."),
        ("security",    "Zero-trust security active. All IPC messages are HMAC-signed."),
        ("memory",      "Memory manager reports usage via UmerKernel.status()['memory']."),
        ("search",      "File indexer not yet loaded. Call index_files(directory) first."),
    ]

    def __init__(self) -> None:
        self._file_index: Dict[str, str] = {}  # path → content snippet
        log.info("LocalAIAssistant initialised (rule-based stub).")

    def ask(self, prompt: str) -> str:
        """Respond to a natural-language prompt using keyword matching.

        Args:
            prompt: User's question or command string.

        Returns:
            Assistant's response string.
        """
        lower = prompt.lower().strip()
        for keyword, response in self._RULES:
            if keyword in lower:
                return response
        return (
            "I'm Umer OS Assistant. I didn't recognise that command. "
            "Try 'help' for a list of available commands."
        )

    def index_files(self, directory: str) -> int:
        """Index text files in a directory for keyword search.

        Args:
            directory: Filesystem path to index.

        Returns:
            Number of files indexed.
        """
        import os
        count = 0
        try:
            for root, _, files in os.walk(directory):
                for fname in files:
                    if fname.endswith((".txt", ".md", ".py", ".json")):
                        path = os.path.join(root, fname)
                        try:
                            with open(path, encoding="utf-8", errors="ignore") as fh:
                                content = fh.read(2048)  # index first 2 KiB
                            self._file_index[path] = content
                            count += 1
                        except OSError:
                            pass
        except OSError as exc:
            log.error("index_files: %s", exc)
        log.info("Indexed %d file(s) from '%s'.", count, directory)
        return count

    def search_files(self, query: str) -> List[str]:
        """Search the file index for files containing the query string.

        Args:
            query: Search term (case-insensitive).

        Returns:
            List of matching file paths (up to 10 results).
        """
        q = query.lower()
        results = [
            path for path, content in self._file_index.items()
            if q in content.lower()
        ]
        return results[:10]

    def summarise_system_state(self) -> str:
        """Return a human-readable system state summary."""
        return (
            "Umer OS is running. "
            f"File index: {len(self._file_index)} entries. "
            "AI backend: rule-based stub (FUTURE: on-device LLM)."
        )


# ---------------------------------------------------------------------------
# Self-Healing Engine
# ---------------------------------------------------------------------------

class SelfHealingEngine:
    """Monitors processes for crashes and attempts automated recovery.

    TODAY: Logs crashes and invokes registered recovery callbacks.
    EXPERIMENTAL: Patch generation via local LLM analysis.
    FUTURE: Real-time code rewriting with verification.

    Args:
        ai_resource_manager: AIResourceManager to record crashes in.
    """

    def __init__(self, ai_resource_manager: Optional[AIResourceManager] = None) -> None:
        self._arm = ai_resource_manager or AIResourceManager()
        self._watchers:  Dict[int, str] = {}   # pid → process name
        self._callbacks: Dict[int, Callable]  = {}  # pid → recovery callable
        self._patches:   Dict[int, List[str]] = {}  # pid → patch history
        log.info("SelfHealingEngine initialised.")

    def watch(self, pid: int, name: str = "", recovery: Optional[Callable] = None) -> None:
        """Register a process for crash monitoring.

        Args:
            pid:      Process ID to watch.
            name:     Human-readable process name (for log messages).
            recovery: Optional callable to invoke on crash: ``recovery(pid, exc)``.
        """
        self._watchers[pid] = name or f"pid-{pid}"
        if recovery:
            self._callbacks[pid] = recovery
        log.debug("SelfHealingEngine watching PID %d ('%s').", pid, self._watchers[pid])

    def on_crash(self, pid: int, exception: Exception) -> None:
        """Handle a process crash.

        Records the crash, attempts recovery, and generates a patch stub.

        Args:
            pid:       Crashed process ID.
            exception: The exception that caused the crash.
        """
        name = self._watchers.get(pid, f"pid-{pid}")
        log.error("CRASH: PID %d ('%s') — %s: %s",
                  pid, name, type(exception).__name__, exception)
        self._arm.record_crash(pid)

        # Invoke registered recovery callback
        cb = self._callbacks.get(pid)
        if cb:
            try:
                cb(pid, exception)
                log.info("Recovery callback for PID %d executed.", pid)
            except Exception as cb_exc:  # noqa: BLE001
                log.error("Recovery callback for PID %d failed: %s", pid, cb_exc)

        # Generate and log a patch stub
        patch = self.generate_patch(str(exception))
        self._patches.setdefault(pid, []).append(patch)
        log.info("Patch stub generated for PID %d (total patches: %d).",
                 pid, len(self._patches[pid]))

    def generate_patch(self, traceback_str: str) -> str:
        """Generate a recovery patch stub based on the exception text.

        TODAY: Rule-based pattern matching to create a Python snippet.
        FUTURE: On-device LLM generates and verifies actual fix.

        Args:
            traceback_str: Exception string / traceback.

        Returns:
            Python code string (patch stub).
        """
        if "MemoryError" in traceback_str:
            return "# PATCH: trigger compact() and retry allocation\ntry:\n    memory_manager.compact()\nexcept Exception:\n    pass\n"
        if "PermissionError" in traceback_str:
            return "# PATCH: re-request missing capability before retry\n# capability_manager.grant(pid, required_cap)\n"
        if "TimeoutError" in traceback_str:
            return "# PATCH: increase timeout or retry with backoff\nimport time; time.sleep(1)\n"
        return f"# PATCH stub for: {traceback_str[:80]}\n# TODO: FUTURE — LLM-generated fix\npass\n"

    def rollback(self, pid: int) -> bool:
        """Roll back the last applied patch for a process.

        TODAY: Removes patch from history log only (no live code modification).
        FUTURE: Reverts hot-patched bytecode.

        Args:
            pid: Process ID.

        Returns:
            True if a patch was rolled back, False if no patches exist.
        """
        patches = self._patches.get(pid, [])
        if not patches:
            log.warning("Rollback requested for PID %d but no patches recorded.", pid)
            return False
        removed = patches.pop()
        log.info("Rolled back patch for PID %d: %s", pid, removed[:40])
        return True


# ---------------------------------------------------------------------------
# AI Firewall
# ---------------------------------------------------------------------------

class AIFirewall:
    """Behavioural anomaly detector for process and network activity.

    TODAY: Heuristic scoring using deviation from baseline.
    EXPERIMENTAL: Isolation Forest classifier via scikit-learn.

    Scores range from 0.0 (normal) to 1.0 (critical threat).
    Processes scoring above threshold are quarantined.

    Args:
        threshold: Anomaly score above which a process is quarantined.
        baseline_window: Number of samples to establish the normal baseline.
    """

    THREAT_THRESHOLD = 0.75

    def __init__(
        self,
        threshold: float = THREAT_THRESHOLD,
        baseline_window: int = 30,
    ) -> None:
        self._threshold = threshold
        self._baseline_window = baseline_window
        self._profiles: Dict[int, Deque[float]] = {}
        self._quarantined: Dict[int, str] = {}
        self._alert_log: List[dict] = []
        log.info("AIFirewall initialised (threshold=%.2f).", threshold)

    def profile_process(self, pid: int) -> None:
        """Initialise a normal-behaviour profile for a process.

        Args:
            pid: Process ID.
        """
        if pid not in self._profiles:
            self._profiles[pid] = collections.deque(maxlen=self._baseline_window)
            log.debug("AIFirewall: started profiling PID %d.", pid)

    def score_anomaly(self, pid: int, syscall_trace: List[str]) -> float:
        """Compute an anomaly score for a process's recent syscall pattern.

        Heuristic: counts "suspicious" syscall names (e.g. mmap, ptrace,
        socket with high frequency) and normalises by trace length.

        Args:
            pid:          Process ID.
            syscall_trace: List of recent syscall name strings.

        Returns:
            Float score in [0.0, 1.0].  0.0 = benign, 1.0 = critical threat.
        """
        if not syscall_trace:
            return 0.0

        SUSPICIOUS = {"ptrace", "mmap_anon", "setuid", "execve", "connect",
                      "bind", "socket_raw", "write_proc_mem"}
        hits = sum(1 for s in syscall_trace if s in SUSPICIOUS)
        score = hits / len(syscall_trace)

        # Track in rolling window for trend analysis
        dq = self._profiles.setdefault(pid, collections.deque(maxlen=self._baseline_window))
        dq.append(score)

        # Trend: if recent mean > historical mean, boost score
        if len(dq) >= 5:
            recent  = sum(list(dq)[-5:]) / 5
            overall = sum(dq) / len(dq)
            if recent > overall * 1.5:
                score = min(1.0, score * 1.25)

        return round(score, 4)

    def quarantine(self, pid: int, reason: str = "anomaly_threshold") -> None:
        """Quarantine a process (mark as unsafe; prevent further scheduling).

        Args:
            pid:    Process ID to quarantine.
            reason: Human-readable quarantine reason.
        """
        self._quarantined[pid] = reason
        log.error("QUARANTINE: PID %d — reason: %s", pid, reason)

    def is_quarantined(self, pid: int) -> bool:
        """Return True if the process is currently quarantined."""
        return pid in self._quarantined

    def alert(self, pid: int, reason: str) -> None:
        """Record and log a security alert without quarantining.

        Args:
            pid:    Process ID.
            reason: Alert description.
        """
        entry = {"pid": pid, "reason": reason, "ts": time.time()}
        self._alert_log.append(entry)
        log.warning("ALERT: PID %d — %s", pid, reason)

    def check_and_act(self, pid: int, syscall_trace: List[str]) -> float:
        """Score, alert, and auto-quarantine if threshold exceeded.

        Args:
            pid:          Process ID.
            syscall_trace: Recent syscall list.

        Returns:
            Anomaly score (also quarantines the process if score > threshold).
        """
        score = self.score_anomaly(pid, syscall_trace)
        if score >= self._threshold:
            self.quarantine(pid, reason=f"score={score:.2f}")
        elif score >= self._threshold * 0.6:
            self.alert(pid, f"elevated anomaly score {score:.2f}")
        return score

    def get_alert_log(self) -> List[dict]:
        """Return the complete alert log.

        Returns:
            List of alert dicts with pid, reason, and ts keys.
        """
        return list(self._alert_log)


# ---------------------------------------------------------------------------
# AI Governance
# ---------------------------------------------------------------------------

class AIGovernance:
    """Tracks user consent for AI data collection and enforces privacy policy.

    Every AI feature that touches personal data must call ``check_consent()``
    before proceeding.  No data collection happens without an explicit grant.

    Stored locally in memory only; persisted externally by the caller.
    """

    def __init__(self) -> None:
        self._consents: Dict[str, bool] = {}
        log.info("AIGovernance initialised (all consents default to False).")

    def grant_consent(self, feature: str) -> None:
        """User grants consent for an AI feature.

        Args:
            feature: Feature identifier (e.g. "on_device_training", "telemetry").
        """
        self._consents[feature] = True
        log.info("Consent GRANTED for feature '%s'.", feature)

    def revoke_consent(self, feature: str) -> None:
        """User revokes consent for an AI feature.

        Args:
            feature: Feature identifier.
        """
        self._consents[feature] = False
        log.info("Consent REVOKED for feature '%s'.", feature)

    def check_consent(self, feature: str) -> bool:
        """Check whether the user has consented to a feature.

        Args:
            feature: Feature identifier.

        Returns:
            True if consented, False otherwise.
        """
        return self._consents.get(feature, False)

    def clear_all(self) -> None:
        """Revoke all consents and clear any learned preferences."""
        self._consents.clear()
        log.info("All AI consents cleared (user requested erasure).")

    def consent_report(self) -> Dict[str, bool]:
        """Return the current consent state for all features."""
        return dict(self._consents)
