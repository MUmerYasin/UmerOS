"""[FIX H18/H21/H12] consent-gated online AI + capability-gated self-healing."""
from __future__ import annotations
import sys, unittest
from pathlib import Path
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

class TestConsentWiring(unittest.TestCase):
    """[FIX H18] every online provider call passes the consent gate."""
    def test_assistant_service_fails_closed(self):
        import ai.assistant_service as svc
        self.assertTrue(hasattr(svc, "governance"))
        src = Path(svc.__file__).read_text(encoding="utf-8")
        self.assertIn("check_consent", src)
        self.assertIn("raise", src.split("_check_consent_or_raise")[1][:400])

class TestSelfHealingGate(unittest.TestCase):
    """[FIX H21/H12] mitigate is capability-gated + audited, never execs."""
    def test_strict_mode_requires_cap(self):
        import core.capability_gate as cg
        from ai.self_healing import SelfHealingService
        prev = cg.gate.strict
        try:
            s = SelfHealingService()
            s.detect_anomaly(7, "CRASHED")
            cg.gate.set_strict(True)
            with self.assertRaises(PermissionError):
                s.mitigate(7)
        finally:
            cg.gate.set_strict(prev)

    def test_audited_and_no_exec(self):
        import core.capability_gate as cg
        from ai.self_healing import SelfHealingService
        prev = cg.gate.strict
        try:
            s = SelfHealingService()
            s.detect_anomaly(9, "CRASHED")
            cg.gate.set_strict(False)
            self.assertTrue(s.mitigate(9))
            actions = [e["action"] for e in s.audit_log]
            self.assertIn("mitigate-authorised", actions)
            src = Path("ai/self_healing.py").read_text(encoding="utf-8")
            for banned in ("exec(", "eval(", "__import__"):
                self.assertNotIn(banned, src)
        finally:
            cg.gate.set_strict(prev)

if __name__ == "__main__":
    unittest.main()
