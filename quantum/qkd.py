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

"""QKD — Quantum Key Distribution.

Implements the BB84 quantum key distribution protocol and related
quantum cryptography primitives.
"""

from __future__ import annotations

import math
import secrets
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

from .circuit import QuantumCircuit, QuantumRegister, ClassicalRegister
from .simulator import StatevectorSimulator
from .backend import LocalBackend
from .qrng import QRNG


# ---------------------------------------------------------------------------
# Result Types
# ---------------------------------------------------------------------------

@dataclass
class QKDResult:
    """Result of a QKD key exchange."""
    alice_key: List[int]
    bob_key: List[int]
    sifted_key_alice: List[int]
    sifted_key_bob: List[int]
    error_rate: float
    qber: float
    is_secure: bool
    basis_matching_rate: float
    num_photons: int
    num_rounds: int
    eavesdropper_detected: bool = False


@dataclass
class BB84Session:
    """BB84 protocol session data."""
    alice_bits: List[int]
    alice_bases: List[int]
    bob_bases: List[int]
    bob_results: List[int]
    matching_bases: List[bool]
    sifted_bits_alice: List[int]
    sifted_bits_bob: List[int]
    error_rate: float
    secure: bool


# ---------------------------------------------------------------------------
# BB84 Protocol
# ---------------------------------------------------------------------------

class BB84:
    """BB84 Quantum Key Distribution Protocol.

    Implements the full BB84 protocol including:
    - Quantum transmission phase
    - Basis reconciliation
    - Error estimation
    - Eavesdropper detection
    """

    def __init__(self, num_photons: int = 100,
                 backend: Optional[LocalBackend] = None,
                 seed: Optional[int] = None):
        """Initialize BB84 protocol.

        Args:
            num_photons: Number of photons to send
            backend: Optional backend for simulation
            seed: Optional seed for reproducibility
        """
        self._num_photons = num_photons
        self._backend = backend
        self._qrng = QRNG(backend, seed)

    def _generate_random_bits(self, n: int) -> List[int]:
        """Generate n random bits."""
        return [self._qrng.random_bit().value for _ in range(n)]

    def _generate_bases(self, n: int) -> List[int]:
        """Generate n random bases (0=Z, 1=X)."""
        return [self._qrng.random_bit().value for _ in range(n)]

    def _encode_qubits(self, bits: List[int], bases: List[int]) -> QuantumCircuit:
        """Encode bits into quantum states.

        Args:
            bits: Bits to encode
            bases: Encoding bases

        Returns:
            Quantum circuit encoding the bits
        """
        n = len(bits)
        qr = QuantumRegister(n, "q")
        circuit = QuantumCircuit(qr)

        for i in range(n):
            if bits[i] == 1:
                circuit.x(qr[i])
            if bases[i] == 1:  # X basis
                circuit.h(qr[i])

        return circuit

    def _measure_qubits(self, circuit: QuantumCircuit,
                        bases: List[int]) -> Tuple[List[int], QuantumCircuit]:
        """Measure qubits in given bases.

        Args:
            circuit: Quantum circuit to measure
            bases: Measurement bases

        Returns:
            Tuple of (measurement results, measurement circuit)
        """
        n = len(bases)
        qr = QuantumRegister(n, "q")
        cr = ClassicalRegister(n, "c")
        meas_circuit = QuantumCircuit(qr, cr)

        for i in range(n):
            if bases[i] == 1:  # X basis
                meas_circuit.h(qr[i])
            meas_circuit.measure(qr[i], cr[i])

        return meas_circuit

    def run(self) -> QKDResult:
        """Run the full BB84 protocol.

        Returns:
            QKDResult with all protocol data
        """
        n = self._num_photons

        # Step 1: Alice generates random bits and bases
        alice_bits = self._generate_random_bits(n)
        alice_bases = self._generate_bases(n)

        # Step 2: Bob generates random bases
        bob_bases = self._generate_bases(n)

        # Step 3: Alice encodes qubits
        encode_circuit = self._encode_qubits(alice_bits, alice_bases)

        # Step 4: Bob measures qubits
        meas_circuit = self._measure_qubits(encode_circuit, bob_bases)

        # Run measurement
        backend = self._backend or LocalBackend()
        result = backend.run(meas_circuit, shots=1)
        key = list(result.counts.keys())[0]
        bob_results = [int(bit) for bit in key]

        # Step 5: Basis reconciliation
        matching_bases = [alice_bases[i] == bob_bases[i] for i in range(n)]

        sifted_bits_alice = [alice_bits[i] for i in range(n) if matching_bases[i]]
        sifted_bits_bob = [bob_results[i] for i in range(n) if matching_bases[i]]

        # Step 6: Error estimation
        if len(sifted_bits_alice) > 0:
            errors = sum(a != b for a, b in zip(sifted_bits_alice, sifted_bits_bob))
            error_rate = errors / len(sifted_bits_alice)
        else:
            error_rate = 0.0

        # Step 7: Eavesdropper detection
        # QBER threshold for security (simplified)
        qber_threshold = 0.11
        is_secure = error_rate < qber_threshold
        eavesdropper_detected = error_rate >= qber_threshold

        # Calculate basis matching rate
        matching_count = sum(matching_bases)
        basis_matching_rate = matching_count / n

        return QKDResult(
            alice_key=alice_bits,
            bob_key=bob_results,
            sifted_key_alice=sifted_bits_alice,
            sifted_key_bob=sifted_bits_bob,
            error_rate=error_rate,
            qber=error_rate,
            is_secure=is_secure,
            basis_matching_rate=basis_matching_rate,
            num_photons=n,
            num_rounds=n,
            eavesdropper_detected=eavesdropper_detected,
        )

    def single_round(self) -> Tuple[int, int, int, int]:
        """Run a single round of BB84.

        Returns:
            Tuple of (alice_bit, alice_base, bob_base, bob_result)
        """
        # Alice's side
        alice_bit = self._qrng.random_bit().value
        alice_base = self._qrng.random_bit().value

        # Bob's side
        bob_base = self._qrng.random_bit().value

        # Create circuit for this round
        qr = QuantumRegister(1, "q")
        cr = ClassicalRegister(1, "c")
        circuit = QuantumCircuit(qr, cr)

        # Encode
        if alice_bit == 1:
            circuit.x(qr[0])
        if alice_base == 1:
            circuit.h(qr[0])

        # Measure in Bob's basis
        if bob_base == 1:
            circuit.h(qr[0])
        circuit.measure(qr[0], cr[0])

        # Run
        backend = self._backend or LocalBackend()
        result = backend.run(circuit, shots=1)
        key = list(result.counts.keys())[0]
        bob_result = int(key)

        return alice_bit, alice_base, bob_base, bob_result


# ---------------------------------------------------------------------------
# E91 Protocol (Simplified)
# ---------------------------------------------------------------------------

class E91:
    """Simplified E91 quantum key distribution protocol.

    Uses entangled pairs for key distribution.
    """

    def __init__(self, num_pairs: int = 100,
                 backend: Optional[LocalBackend] = None):
        """Initialize E91 protocol.

        Args:
            num_pairs: Number of entangled pairs
            backend: Optional backend
        """
        self._num_pairs = num_pairs
        self._backend = backend
        self._qrng = QRNG(backend)

    def _create_entangled_pair(self) -> QuantumCircuit:
        """Create an entangled Bell pair."""
        qr = QuantumRegister(2, "q")
        circuit = QuantumCircuit(qr)

        circuit.h(qr[0])
        circuit.cx(qr[0], qr[1])

        return circuit

    def run(self) -> QKDResult:
        """Run the E91 protocol.

        Returns:
            QKDResult with protocol data
        """
        alice_bits = []
        alice_bases = []
        bob_bases = []
        bob_results = []

        for _ in range(self._num_pairs):
            # Generate random bases
            alice_bit = self._qrng.random_bit().value
            alice_base = self._qrng.random_bit().value
            bob_base = self._qrng.random_bit().value

            # Create entangled pair
            circuit = self._create_entangled_pair()

            # Alice measures in her base
            qr = QuantumRegister(2, "q")
            cr = ClassicalRegister(2, "c")
            meas_circuit = QuantumCircuit(qr, cr)

            # Rebuild circuit
            meas_circuit.h(qr[0])
            meas_circuit.cx(qr[0], qr[1])

            # Measurement
            if alice_base == 1:
                meas_circuit.h(qr[0])
            meas_circuit.measure(qr[0], cr[0])

            if bob_base == 1:
                meas_circuit.h(qr[1])
            meas_circuit.measure(qr[1], cr[1])

            # Run
            backend = self._backend or LocalBackend()
            result = backend.run(meas_circuit, shots=1)
            key = list(result.counts.keys())[0]

            alice_result = int(key[0])
            bob_result = int(key[1])

            alice_bits.append(alice_bit)
            alice_bases.append(alice_base)
            bob_bases.append(bob_base)
            bob_results.append(bob_result)

        # Basis reconciliation
        matching_bases = [alice_bases[i] == bob_bases[i]
                         for i in range(self._num_pairs)]

        sifted_alice = [alice_bits[i] for i in range(self._num_pairs)
                       if matching_bases[i]]
        sifted_bob = [bob_results[i] for i in range(self._num_pairs)
                     if matching_bases[i]]

        # Error rate
        if sifted_alice:
            errors = sum(a != b for a, b in zip(sifted_alice, sifted_bob))
            error_rate = errors / len(sifted_alice)
        else:
            error_rate = 0.0

        return QKDResult(
            alice_key=alice_bits,
            bob_key=bob_results,
            sifted_key_alice=sifted_alice,
            sifted_key_bob=sifted_bob,
            error_rate=error_rate,
            qber=error_rate,
            is_secure=error_rate < 0.11,
            basis_matching_rate=sum(matching_bases) / self._num_pairs,
            num_photons=self._num_pairs,
            num_rounds=self._num_pairs,
        )


# ---------------------------------------------------------------------------
# Key Reconciliation
# ---------------------------------------------------------------------------

def key_reconciliation(alice_key: List[int], bob_key: List[int]) -> Tuple[List[int], List[int]]:
    """Perform key reconciliation using Cascade-like protocol.

    Args:
        alice_key: Alice's sifted key
        bob_key: Bob's sifted key

    Returns:
        Tuple of (reconciled_alice_key, reconciled_bob_key)
    """
    if len(alice_key) != len(bob_key):
        raise ValueError("Keys must be the same length")

    n = len(alice_key)
    if n == 0:
        return [], []

    # Simple reconciliation: XOR and correct
    reconciled_alice = list(alice_key)
    reconciled_bob = list(bob_key)

    # Find and correct errors
    errors_found = 0
    for i in range(n):
        if reconciled_alice[i] != reconciled_bob[i]:
            # Flip Bob's bit
            reconciled_bob[i] = 1 - reconciled_bob[i]
            errors_found += 1

    return reconciled_alice, reconciled_bob


def privacy_amplification(key: List[int], target_length: int) -> List[int]:
    """Perform privacy amplification using universal hashing.

    Args:
        key: Sifted key to amplify
        target_length: Desired output length

    Returns:
        Amplified key
    """
    if not key:
        return []

    # Use SHA-256 for universal hashing
    key_bytes = bytes(key)
    hash_input = key_bytes
    amplified = []

    while len(amplified) < target_length:
        import hashlib
        h = hashlib.sha256(hash_input).digest()
        for byte in h:
            for i in range(8):
                if len(amplified) < target_length:
                    amplified.append((byte >> i) & 1)
        hash_input = h

    return amplified[:target_length]


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def run_bb84(num_photons: int = 100,
             backend: Optional[LocalBackend] = None) -> QKDResult:
    """Run the BB84 protocol.

    Args:
        num_photons: Number of photons
        backend: Optional backend

    Returns:
        QKDResult
    """
    bb84 = BB84(num_photons, backend)
    return bb84.run()


def run_e91(num_pairs: int = 100,
            backend: Optional[LocalBackend] = None) -> QKDResult:
    """Run the E91 protocol.

    Args:
        num_pairs: Number of entangled pairs
        backend: Optional backend

    Returns:
        QKDResult
    """
    e91 = E91(num_pairs, backend)
    return e91.run()


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

__all__ = [
    "QKDResult",
    "BB84Session",
    "BB84",
    "E91",
    "key_reconciliation",
    "privacy_amplification",
    "run_bb84",
    "run_e91",
]
