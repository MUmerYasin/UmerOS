"""Tests for UmerOS Star Shield DSLM and Scoped Tokens."""
import sys
import unittest
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from security.star_shield.dslm import DeviceSecurityLevel, DataSensitivity, DSLMAuthority
from security.star_shield.scoped_token import ScopedToken, ScopedTokenGate


class TestDSLM(unittest.TestCase):
    def test_local_attestation(self):
        auth = DSLMAuthority("node1", DeviceSecurityLevel.SL3)
        att = auth.attest_local()
        self.assertEqual(att.node_id, "node1")
        self.assertEqual(att.security_level, DeviceSecurityLevel.SL3)
        self.assertTrue(att.verified)

    def test_peer_registration(self):
        auth = DSLMAuthority("node1")
        auth.register_peer("node2", DeviceSecurityLevel.SL4)
        self.assertEqual(auth.get_peer_sl("node2"), DeviceSecurityLevel.SL4)
        self.assertEqual(auth.peer_count, 1)

    def test_data_routing_allowed(self):
        auth = DSLMAuthority("node1", DeviceSecurityLevel.SL4)
        auth.register_peer("node2", DeviceSecurityLevel.SL4)
        # S3 data to SL4 device should be allowed
        self.assertTrue(auth.can_route_data(DataSensitivity.S3_CONFIDENTIAL, "node2"))

    def test_data_routing_denied(self):
        auth = DSLMAuthority("node1", DeviceSecurityLevel.SL4)
        auth.register_peer("node2", DeviceSecurityLevel.SL2)
        # S3 data to SL2 device should be denied
        self.assertFalse(auth.can_route_data(DataSensitivity.S3_CONFIDENTIAL, "node2"))
        self.assertEqual(len(auth.audit_log()), 1)

    def test_unknown_peer_treated_as_sl1(self):
        auth = DSLMAuthority("node1", DeviceSecurityLevel.SL4)
        # S2 data to unknown node (SL1) should be denied
        self.assertFalse(auth.can_route_data(DataSensitivity.S2_INTERNAL, "unknown_node"))

    def test_s1_always_allowed(self):
        auth = DSLMAuthority("node1", DeviceSecurityLevel.SL4)
        auth.register_peer("node2", DeviceSecurityLevel.SL1)
        self.assertTrue(auth.can_route_data(DataSensitivity.S1_PUBLIC, "node2"))


class TestScopedToken(unittest.TestCase):
    def test_issue_and_validate(self):
        gate = ScopedTokenGate(default_ttl=60.0)
        token = gate.issue("/tmp/test.txt", "file", "node1")
        self.assertTrue(gate.validate(token))
        self.assertFalse(token.is_expired)

    def test_expired_token_invalid(self):
        gate = ScopedTokenGate(default_ttl=0.01)
        token = gate.issue("/tmp/test.txt", "file", "node1", ttl=0.01)
        import time
        time.sleep(0.02)
        self.assertTrue(token.is_expired)
        self.assertFalse(gate.validate(token))

    def test_revoke(self):
        gate = ScopedTokenGate()
        token = gate.issue("/tmp/test.txt", "file", "node1")
        self.assertTrue(gate.revoke(token.token_id))
        self.assertFalse(gate.validate(token))

    def test_cleanup_expired(self):
        gate = ScopedTokenGate()
        gate.issue("/tmp/a.txt", "file", "node1", ttl=0.01)
        import time
        time.sleep(0.02)
        removed = gate.cleanup_expired()
        self.assertEqual(removed, 1)
        self.assertEqual(gate.active_count, 0)

    def test_tampered_token_invalid(self):
        gate = ScopedTokenGate()
        token = gate.issue("/tmp/test.txt", "file", "node1")
        token.resource = "/tmp/secret.txt"  # tamper
        self.assertFalse(gate.validate(token))

    def test_serialization(self):
        gate = ScopedTokenGate()
        token = gate.issue("/tmp/test.txt", "file", "node1")
        d = token.to_dict()
        restored = ScopedToken.from_dict(d)
        self.assertEqual(restored.token_id, token.token_id)
        self.assertEqual(restored.resource, token.resource)


if __name__ == "__main__":
    unittest.main()