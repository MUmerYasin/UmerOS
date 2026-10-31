# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""H248 - the behavioural monitor must stop claiming AI and start enforcing.

The row was: ``security/security.py`` ``AIBehavioralMonitor`` is a 4-entry
hardcoded rule set labelled "AI-driven", whose ``_trigger_quarantine`` only
calls ``log.critical`` (no isolation), and whose rules flag ordinary behaviour.

So these tests pin four things:

* the label is honest - heuristic rules, no model;
* quarantine has an effect a caller can observe - capabilities are actually
  revoked through the sandbox, so ``check_permission`` starts denying;
* the quarantine is sticky - an innocuous action after it is still refused;
* the named false positive is tuned - a game writing under a system path warns
  and only quarantines on repetition, while impossible combinations still
  quarantine on the first hit.
"""
from __future__ import annotations

import pathlib
import unittest
from unittest import mock

import security.security as secmod
from security.sandbox import SecuritySandbox
from security.security import AIBehavioralMonitor

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent


class _Clock:
    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start

    def monotonic(self) -> float:
        return self.now

    def time(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _sandbox(pid: int = 7, name: str = "calculator", caps=("read", "write")):
    sandbox = SecuritySandbox()
    sandbox.register_process(pid, name)
    for cap in caps:
        sandbox.grant_permission(pid, cap)
    return sandbox


# ---------------------------------------------------------------------------
# The label is honest
# ---------------------------------------------------------------------------

class TestTheLabelIsHonest(unittest.TestCase):

    def test_the_class_docstring_does_not_claim_a_model(self):
        doc = (AIBehavioralMonitor.__doc__ or "").lower()
        self.assertIn("heuristic", doc)
        self.assertIn("not", doc)
        self.assertNotIn("ai-driven", doc)

    def test_the_module_docstring_drops_the_ai_framing(self):
        doc = secmod.__doc__ or ""
        self.assertNotIn("AI Behavioral Monitoring", doc)
        self.assertIn("heuristic behavioural monitoring", doc)

    def test_the_gui_no_longer_sells_it_as_anomaly_detection(self):
        gui = (PROJECT_ROOT / "ui" / "umeros_gui.py").read_text(encoding="utf-8")
        self.assertNotIn("AIBehavioralMonitor — anomaly detection", gui)
        self.assertIn("AIBehavioralMonitor — heuristic anomaly rules", gui)

    def test_the_source_keeps_no_ai_driven_docstring_on_the_live_class(self):
        """Scan the live class region only.

        ``inspect.getsource`` is unusable here: everything after this class is
        commented out, and ``tokenize`` skips comment tokens, so no DEDENT
        arrives and the "class source" runs to EOF - straight through the dead
        code that still says "AI-driven".
        """
        text = (PROJECT_ROOT / "security" / "security.py").read_text(encoding="utf-8")
        start = text.index("\nclass AIBehavioralMonitor:") + 1
        end = text.index("\n# --------------------------", start)
        region = text[start:end]
        self.assertNotIn("AI-driven", region)
        self.assertNotIn("AI SECURITY", region)
        self.assertIn("heuristic", region.lower())


# ---------------------------------------------------------------------------
# Quarantine actually does something
# ---------------------------------------------------------------------------

class TestQuarantineIsReal(unittest.TestCase):

    def test_a_block_hit_revokes_the_process_capabilities(self):
        sandbox = _sandbox(7, "calculator", ("read", "write", "network"))
        monitor = AIBehavioralMonitor(sandbox=sandbox)
        self.assertTrue(sandbox.check_permission(7, "write"))

        self.assertFalse(
            monitor.analyze_action(7, "calculator", "load", "kernel_module_load")
        )

        self.assertEqual(
            sandbox.processes[7].permissions, set(), "capabilities must be revoked"
        )
        self.assertFalse(sandbox.check_permission(7, "write"))
        self.assertFalse(sandbox.check_permission(7, "network"))

    def test_the_record_says_capabilities_were_revoked(self):
        sandbox = _sandbox(7, "calculator", ("read", "write"))
        monitor = AIBehavioralMonitor(sandbox=sandbox)
        monitor.analyze_action(7, "calculator", "load", "kernel_module_load")
        reason = monitor.quarantine_reason(7) or ""
        self.assertIn("revoked 2 capability", reason)

    def test_without_a_sandbox_the_record_says_nothing_was_revoked(self):
        """Honesty: a monitor with no sandbox must not imply it isolated anything."""
        monitor = AIBehavioralMonitor()
        self.assertFalse(
            monitor.analyze_action(9, "calculator", "load", "kernel_module_load")
        )
        self.assertTrue(monitor.is_quarantined(9))
        self.assertIn("NOT revoked", monitor.quarantine_reason(9) or "")

    def test_a_pid_the_sandbox_never_saw_is_reported_as_such(self):
        sandbox = _sandbox(7, "calculator")
        monitor = AIBehavioralMonitor(sandbox=sandbox)
        monitor.analyze_action(999, "calculator", "load", "kernel_module_load")
        self.assertIn("not registered", monitor.quarantine_reason(999) or "")

    def test_quarantine_is_sticky(self):
        monitor = AIBehavioralMonitor(sandbox=_sandbox())
        self.assertFalse(
            monitor.analyze_action(7, "calculator", "load", "kernel_module_load")
        )
        self.assertFalse(
            monitor.analyze_action(7, "calculator", "read", "notes.txt"),
            "an innocuous action after quarantine must still be refused",
        )

    def test_quarantine_is_per_pid(self):
        monitor = AIBehavioralMonitor(sandbox=None)
        monitor.analyze_action(1, "calculator", "load", "kernel_module_load")
        self.assertTrue(monitor.is_quarantined(1))
        self.assertFalse(monitor.is_quarantined(2))
        self.assertTrue(monitor.analyze_action(2, "calculator", "read", "notes.txt"))

    def test_quarantined_pids_is_sorted_and_complete(self):
        monitor = AIBehavioralMonitor()
        for pid in (30, 10, 20):
            monitor.quarantine(pid, "test")
        self.assertEqual(monitor.quarantined_pids, (10, 20, 30))

    def test_quarantine_is_idempotent(self):
        sandbox = _sandbox(7, "calculator", ("read", "write"))
        monitor = AIBehavioralMonitor(sandbox=sandbox)
        monitor.quarantine(7, "first reason")
        monitor.quarantine(7, "second reason")
        self.assertIn("first reason", monitor.quarantine_reason(7) or "")
        self.assertNotIn("second reason", monitor.quarantine_reason(7) or "")
        self.assertEqual(sandbox.processes[7].permissions, set())


class TestRelease(unittest.TestCase):

    def test_release_restores_the_revoked_capabilities(self):
        sandbox = _sandbox(7, "calculator", ("read", "write"))
        monitor = AIBehavioralMonitor(sandbox=sandbox)
        monitor.analyze_action(7, "calculator", "load", "kernel_module_load")
        self.assertEqual(sandbox.processes[7].permissions, set())

        self.assertTrue(monitor.release(7))
        self.assertFalse(monitor.is_quarantined(7))
        self.assertEqual(sandbox.processes[7].permissions, {"read", "write"})
        self.assertTrue(sandbox.check_permission(7, "write"))

    def test_after_release_the_process_is_evaluated_normally(self):
        monitor = AIBehavioralMonitor(sandbox=_sandbox())
        monitor.quarantine(7, "manual")
        self.assertFalse(monitor.analyze_action(7, "calculator", "read", "notes.txt"))
        monitor.release(7)
        self.assertTrue(monitor.analyze_action(7, "calculator", "read", "notes.txt"))

    def test_release_of_a_pid_that_was_never_quarantined_returns_false(self):
        monitor = AIBehavioralMonitor()
        self.assertFalse(monitor.release(42))

    def test_release_without_a_sandbox_does_not_raise(self):
        monitor = AIBehavioralMonitor()
        monitor.quarantine(5, "manual")
        self.assertTrue(monitor.release(5))


# ---------------------------------------------------------------------------
# The false positive the row names
# ---------------------------------------------------------------------------

class TestFalsePositiveIsTuned(unittest.TestCase):

    def test_a_game_writing_system_files_is_not_a_block_rule(self):
        monitor = AIBehavioralMonitor()
        self.assertNotIn(
            ("game", "filesystem_write_system"),
            monitor.suspicious_patterns,
            "the row's named false positive must no longer be an unconditional block",
        )

    def test_a_game_may_write_a_few_times_before_quarantine(self):
        monitor = AIBehavioralMonitor(strike_threshold=3)
        verdicts = [
            monitor.analyze_action(11, "game", "write", "filesystem_write_system")
            for _ in range(3)
        ]
        self.assertEqual(verdicts, [True, True, False], "third strike quarantines")
        self.assertTrue(monitor.is_quarantined(11))

    def test_an_impossible_combination_still_blocks_on_the_first_hit(self):
        monitor = AIBehavioralMonitor(strike_threshold=99)
        self.assertFalse(
            monitor.analyze_action(7, "calculator", "load", "kernel_module_load"),
            "the strike threshold must not weaken a BLOCK rule",
        )
        self.assertTrue(monitor.is_quarantined(7))

    def test_clean_actions_do_not_reset_strikes(self):
        """Otherwise an attacker interleaves innocuous calls and never trips it."""
        monitor = AIBehavioralMonitor(strike_threshold=3)
        allowed = []
        for _ in range(3):
            allowed.append(
                monitor.analyze_action(11, "game", "write", "filesystem_write_system")
            )
            monitor.analyze_action(11, "game", "read", "save.dat")
        self.assertEqual(allowed, [True, True, False])

    def test_strikes_decay_after_the_window(self):
        clock = _Clock()
        with mock.patch.object(secmod, "time", clock):
            monitor = AIBehavioralMonitor(strike_threshold=3, strike_window=60.0)
            self.assertTrue(
                monitor.analyze_action(11, "game", "write", "filesystem_write_system")
            )
            self.assertTrue(
                monitor.analyze_action(11, "game", "write", "filesystem_write_system")
            )
            clock.advance(61.0)
            self.assertTrue(
                monitor.analyze_action(11, "game", "write", "filesystem_write_system"),
                "a stale strike must be forgotten, not accumulate forever",
            )
            self.assertFalse(monitor.is_quarantined(11))

    def test_an_ordinary_program_is_never_flagged(self):
        monitor = AIBehavioralMonitor()
        for _ in range(20):
            self.assertTrue(monitor.analyze_action(7, "text_editor", "read", "notes.txt"))
            self.assertTrue(monitor.analyze_action(7, "media_player", "read", "song.mp3"))
        self.assertFalse(monitor.is_quarantined(7))


# ---------------------------------------------------------------------------
# Rule table
# ---------------------------------------------------------------------------

class TestRuleTable(unittest.TestCase):

    def test_suspicious_patterns_exposes_only_block_rules(self):
        monitor = AIBehavioralMonitor()
        self.assertIn(("calculator", "kernel_module_load"), monitor.suspicious_patterns)
        self.assertIn(("text_editor", "network_access"), monitor.suspicious_patterns)
        self.assertNotIn(
            ("game", "filesystem_write_system"), monitor.suspicious_patterns
        )

    def test_add_rule_can_promote_and_demote(self):
        monitor = AIBehavioralMonitor()
        monitor.add_rule("notepad", "network_access")
        self.assertFalse(
            monitor.analyze_action(7, "notepad", "network_access", "sock")
        )

        monitor2 = AIBehavioralMonitor(strike_threshold=2)
        monitor2.add_rule("notepad", "network_access", severity=monitor2.WARN)
        self.assertTrue(monitor2.analyze_action(7, "notepad", "network_access", "sock"))

    def test_add_rule_rejects_an_unknown_severity(self):
        monitor = AIBehavioralMonitor()
        with self.assertRaises(ValueError):
            monitor.add_rule("x", "y", severity="catastrophic")

    def test_a_custom_table_replaces_the_defaults(self):
        monitor = AIBehavioralMonitor(rules={("mine", "secret_cap"): "block"})
        self.assertFalse(monitor.analyze_action(1, "mine", "secret_cap", ""))
        self.assertTrue(monitor.analyze_action(2, "calculator", "load", "kernel_module_load"))

    def test_process_names_are_matched_case_insensitively(self):
        monitor = AIBehavioralMonitor()
        self.assertFalse(
            monitor.analyze_action(7, "Calculator", "load", "kernel_module_load")
        )

    def test_the_resource_identifier_is_matched_as_a_capability_name(self):
        """Documented behaviour: action and resource are capability identifiers."""
        monitor = AIBehavioralMonitor()
        self.assertFalse(
            monitor.analyze_action(7, "calculator", "open", "kernel_module_load")
        )


if __name__ == "__main__":
    unittest.main()
