"""Tests for Umer OS AI Subsystems."""
from __future__ import annotations

import collections
import unittest

from ai.umer_ai import (
    NullAIResourceManager,
    AIResourceManager,
    LocalAIAssistant,
    SelfHealingEngine,
    AIFirewall,
    AIGovernance,
)
from kernel.scheduler import Task


class TestNullAIResourceManager(unittest.TestCase):

    def setUp(self):
        self.ai = NullAIResourceManager()

    def test_predict_task_success_neutral(self):
        t = Task(pid=1, name="t", priority=0.5)
        self.assertAlmostEqual(self.ai.predict_task_success(t), 0.5)

    def test_predict_cpu_neutral(self):
        self.assertAlmostEqual(self.ai.predict_cpu_usage(1), 0.5)

    def test_predict_ram_positive(self):
        self.assertGreater(self.ai.predict_ram_usage(1), 0)

    def test_rebalance_does_not_raise(self):
        self.ai.rebalance_resources()  # must not raise


class TestAIResourceManager(unittest.TestCase):

    def setUp(self):
        self.arm = AIResourceManager(window=10, alpha=0.5)

    def test_predict_cpu_no_history_returns_default(self):
        result = self.arm.predict_cpu_usage(pid=99)
        self.assertAlmostEqual(result, 0.5)

    def test_predict_ram_no_history_returns_default(self):
        result = self.arm.predict_ram_usage(pid=99)
        self.assertEqual(result, 4 * 1024 * 1024)

    def test_record_and_predict_cpu(self):
        for _ in range(5):
            self.arm.record_cpu(pid=1, usage=0.9)
        result = self.arm.predict_cpu_usage(pid=1)
        self.assertGreater(result, 0.5)

    def test_record_and_predict_ram(self):
        for _ in range(5):
            self.arm.record_ram(pid=2, bytes_used=16 * 1024 * 1024)
        result = self.arm.predict_ram_usage(pid=2)
        self.assertGreater(result, 4 * 1024 * 1024)

    def test_predict_cpu_clamped_to_valid_range(self):
        for _ in range(5):
            self.arm.record_cpu(1, 1.0)
        self.assertLessEqual(self.arm.predict_cpu_usage(1), 1.0)
        self.assertGreaterEqual(self.arm.predict_cpu_usage(1), 0.0)

    def test_predict_task_success_range(self):
        t = Task(pid=3, name="worker", priority=0.8)
        score = self.arm.predict_task_success(t)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_crash_reduces_success_score(self):
        t = Task(pid=4, name="flaky", priority=0.8)
        score_before = self.arm.predict_task_success(t)
        for _ in range(5):
            self.arm.record_crash(pid=4)
        score_after = self.arm.predict_task_success(t)
        self.assertLess(score_after, score_before)

    def test_rebalance_does_not_raise(self):
        self.arm.record_cpu(5, 0.95)
        self.arm.rebalance_resources()  # must not raise

    def test_ewma_converges(self):
        """EWMA should converge towards the recorded values."""
        # Record many 0.8 samples
        for _ in range(20):
            self.arm.record_cpu(10, 0.8)
        result = self.arm.predict_cpu_usage(10)
        self.assertGreater(result, 0.5)

    def test_window_limits_history(self):
        arm = AIResourceManager(window=3)
        for v in [0.1, 0.1, 0.1, 0.9, 0.9, 0.9]:
            arm.record_cpu(1, v)
        # Last 3 samples are 0.9 — prediction should be higher than 0.5
        self.assertGreater(arm.predict_cpu_usage(1), 0.5)


class TestLocalAIAssistant(unittest.TestCase):

    def setUp(self):
        self.ai = LocalAIAssistant()

    def test_status_command(self):
        reply = self.ai.ask("status")
        self.assertIn("operational", reply.lower())

    def test_optimize_command(self):
        reply = self.ai.ask("optimize resources now")
        self.assertIn("optimis", reply.lower())

    def test_help_command(self):
        reply = self.ai.ask("help")
        self.assertIn("command", reply.lower())

    def test_quantum_command(self):
        reply = self.ai.ask("quantum status")
        self.assertIsInstance(reply, str)
        self.assertGreater(len(reply), 0)

    def test_unknown_command_fallback(self):
        reply = self.ai.ask("xyzzy plugh")
        self.assertTrue(
            "recognis" in reply.lower() or "didn't" in reply.lower()
                         or "assistant" in reply.lower(),
            f"Unexpected fallback reply: {reply!r}",
        )

    def test_index_files_returns_count(self):
        import os, tempfile
        with tempfile.TemporaryDirectory() as d:
            # Create dummy files
            for name in ("a.txt", "b.md", "c.py"):
                with open(os.path.join(d, name), "w") as f:
                    f.write("umer os test file quantum ai")
            count = self.ai.index_files(d)
        self.assertEqual(count, 3)

    def test_search_files_after_index(self):
        import os, tempfile
        with tempfile.TemporaryDirectory() as d:
            fpath = os.path.join(d, "quantum.txt")
            with open(fpath, "w") as f:
                f.write("quantum computing superposition")
            self.ai.index_files(d)
            results = self.ai.search_files("quantum")
        self.assertTrue(any("quantum" in r for r in results))

    def test_search_no_results_when_not_indexed(self):
        fresh = LocalAIAssistant()
        results = fresh.search_files("missing")
        self.assertEqual(results, [])

    def test_summarise_returns_string(self):
        summary = self.ai.summarise_system_state()
        self.assertIsInstance(summary, str)
        self.assertGreater(len(summary), 0)


class TestSelfHealingEngine(unittest.TestCase):

    def setUp(self):
        self.arm = AIResourceManager()
        self.healer = SelfHealingEngine(self.arm)

    def test_watch_registers_pid(self):
        self.healer.watch(pid=1, name="test_svc")
        self.assertIn(1, self.healer._watchers)

    def test_on_crash_records_crash(self):
        self.healer.watch(1, "svc")
        self.healer.on_crash(1, ValueError("simulated crash"))
        self.assertEqual(self.arm._crashes.get(1, 0), 1)

    def test_on_crash_calls_callback(self):
        called = []
        self.healer.watch(2, "svc", recovery=lambda pid, exc: called.append(pid))
        self.healer.on_crash(2, RuntimeError("oops"))
        self.assertIn(2, called)

    def test_generate_patch_memory_error(self):
        patch = self.healer.generate_patch("MemoryError: out of memory")
        self.assertIn("compact", patch)

    def test_generate_patch_permission_error(self):
        patch = self.healer.generate_patch("PermissionError: access denied")
        self.assertIn("capability", patch.lower())

    def test_generate_patch_timeout(self):
        patch = self.healer.generate_patch("TimeoutError: timed out")
        self.assertIn("sleep", patch.lower())

    def test_generate_patch_generic(self):
        patch = self.healer.generate_patch("SomeError: unknown")
        self.assertIn("PATCH", patch)

    def test_rollback_no_patches_returns_false(self):
        self.healer.watch(9, "svc")
        self.assertFalse(self.healer.rollback(9))

    def test_rollback_after_crash_returns_true(self):
        self.healer.watch(10, "svc")
        self.healer.on_crash(10, Exception("crash"))
        self.assertTrue(self.healer.rollback(10))


class TestAIFirewall(unittest.TestCase):

    def setUp(self):
        self.fw = AIFirewall(threshold=0.75)

    def test_score_zero_for_empty_trace(self):
        self.fw.profile_process(1)
        score = self.fw.score_anomaly(1, [])
        self.assertAlmostEqual(score, 0.0)

    def test_benign_trace_low_score(self):
        self.fw.profile_process(1)
        score = self.fw.score_anomaly(1, ["read", "write", "stat", "open"])
        self.assertLess(score, 0.5)

    def test_suspicious_trace_high_score(self):
        self.fw.profile_process(2)
        suspicious = ["ptrace", "setuid", "execve", "mmap_anon", "bind"]
        score = self.fw.score_anomaly(2, suspicious)
        self.assertGreater(score, 0.5)

    def test_score_in_valid_range(self):
        self.fw.profile_process(3)
        trace = ["read", "ptrace", "write"]
        score = self.fw.score_anomaly(3, trace)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_quarantine_marks_process(self):
        self.fw.quarantine(pid=5, reason="test")
        self.assertTrue(self.fw.is_quarantined(5))

    def test_unquarantined_pid_is_not_quarantined(self):
        self.assertFalse(self.fw.is_quarantined(999))

    def test_alert_is_logged(self):
        self.fw.alert(pid=6, reason="test_alert")
        log = self.fw.get_alert_log()
        self.assertTrue(any(e["pid"] == 6 for e in log))

    def test_check_and_act_quarantines_above_threshold(self):
        self.fw.profile_process(7)
        bad = ["ptrace", "setuid", "execve", "mmap_anon", "bind",
               "socket_raw", "write_proc_mem"]
        self.fw.check_and_act(7, bad)
        self.assertTrue(self.fw.is_quarantined(7))

    def test_check_and_act_no_quarantine_for_benign(self):
        self.fw.profile_process(8)
        good = ["read", "write", "stat"]
        self.fw.check_and_act(8, good)
        self.assertFalse(self.fw.is_quarantined(8))


class TestAIGovernance(unittest.TestCase):

    def setUp(self):
        self.gov = AIGovernance()

    def test_default_consent_is_false(self):
        self.assertFalse(self.gov.check_consent("on_device_training"))

    def test_grant_and_check_consent(self):
        self.gov.grant_consent("telemetry")
        self.assertTrue(self.gov.check_consent("telemetry"))

    def test_revoke_consent(self):
        self.gov.grant_consent("telemetry")
        self.gov.revoke_consent("telemetry")
        self.assertFalse(self.gov.check_consent("telemetry"))

    def test_clear_all_resets_all_consents(self):
        self.gov.grant_consent("feature_a")
        self.gov.grant_consent("feature_b")
        self.gov.clear_all()
        self.assertFalse(self.gov.check_consent("feature_a"))
        self.assertFalse(self.gov.check_consent("feature_b"))

    def test_consent_report(self):
        self.gov.grant_consent("x")
        report = self.gov.consent_report()
        self.assertIn("x", report)
        self.assertTrue(report["x"])

    def test_multiple_features_independent(self):
        self.gov.grant_consent("a")
        self.assertFalse(self.gov.check_consent("b"))
        self.assertTrue(self.gov.check_consent("a"))


if __name__ == "__main__":
    unittest.main()
