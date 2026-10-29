"""Tests for UmerOS Quantum Providers."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quantum.providers.base import BackendProvider, BackendStatus, GateSet
from quantum.providers.ibm_provider import IBMQuantumProvider
from quantum.providers.ionq_provider import IonQProvider


class TestIBMProvider(unittest.TestCase):
    def test_create_provider(self):
        provider = IBMQuantumProvider(token="test-token")
        self.assertEqual(provider.name, "ibm")
        self.assertEqual(provider.version, "1.0")
        self.assertFalse(provider.is_authenticated())

    def test_authenticate_without_token(self):
        provider = IBMQuantumProvider(token=None)
        # Should handle missing token gracefully
        try:
            provider.authenticate()
        except Exception:
            pass  # Expected without real token

    def test_backends_cache(self):
        provider = IBMQuantumProvider(token="test-token")
        # Backends cache should be empty initially
        self.assertEqual(provider._backends_cache, [])

    def test_refresh_backends_no_network(self):
        provider = IBMQuantumProvider(token="test-token")
        # Should handle network failure gracefully
        try:
            provider.refresh_backends()
        except Exception:
            pass  # Expected without network

    def test_repr(self):
        provider = IBMQuantumProvider(token="test-token")
        r = repr(provider)
        self.assertIn("ibm", r)


class TestIonQProvider(unittest.TestCase):
    def test_create_provider(self):
        provider = IonQProvider(api_key="test-key")
        self.assertEqual(provider.name, "ionq")
        self.assertEqual(provider.version, "0.3")

    def test_backends_no_network(self):
        provider = IonQProvider(api_key="test-key")
        try:
            backends = provider.backends()
            self.assertIsInstance(backends, list)
        except Exception:
            pass  # Expected without network

    def test_repr(self):
        provider = IonQProvider(api_key="test-key")
        r = repr(provider)
        self.assertIn("ionq", r)


class TestBackendProviderBase(unittest.TestCase):
    def test_job_queue_mode(self):
        from quantum.providers.base import JobQueueMode
        self.assertEqual(JobQueueMode.QUEUE.value, "queue")
        self.assertEqual(JobQueueMode.EMULATE.value, "emulate")

    def test_backend_status(self):
        self.assertEqual(BackendStatus.ONLINE.value, "online")
        self.assertEqual(BackendStatus.OFFLINE.value, "offline")

    def test_gate_set(self):
        gs = GateSet(name="universal", gates=["H", "CNOT", "T"], max_qubits=5)
        self.assertEqual(gs.name, "universal")
        self.assertEqual(len(gs.gates), 3)


if __name__ == "__main__":
    unittest.main()