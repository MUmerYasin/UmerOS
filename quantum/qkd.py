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

Implements the BB84 and E91 quantum key distribution protocols plus the
classical post-processing they need (Cascade error reconciliation and
privacy amplification).

Reconciliation is *not* an oracle: :func:`cascade_reconcile` corrects Bob's
key using **block parities only**, never Alice's individual bit values, so
the QBER measured before reconciliation stays meaningful (a genuine
eavesdropper raises it above :data:`QBER_SECURITY_THRESHOLD` and the
session is rejected).

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import math
import random
import secrets
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

from .circuit import QuantumCircuit, QuantumRegister, ClassicalRegister
from .simulator import StatevectorSimulator
from .backend import LocalBackend
from .qrng import QRNG


#: Maximum tolerable quantum bit error rate.  Above ~11 % an eavesdropper
#: (or channel noise) has leaked so much information that no amount of
#: reconciliation plus privacy amplification yields a secret key, so the
#: session is rejected outright.
QBER_SECURITY_THRESHOLD = 0.11


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
        qber_threshold = QBER_SECURITY_THRESHOLD
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
            is_secure=error_rate < QBER_SECURITY_THRESHOLD,
            basis_matching_rate=sum(matching_bases) / self._num_pairs,
            num_photons=self._num_pairs,
            num_rounds=self._num_pairs,
        )


# ---------------------------------------------------------------------------
# Key Reconciliation (Cascade)
# ---------------------------------------------------------------------------


@dataclass
class ReconciliationResult:
    """Outcome of a Cascade reconciliation run.

    Attributes
    ----------
    alice_key:
        Alice's key.  Reconciliation never modifies it.
    bob_key:
        Bob's key after error correction.
    corrected_bits:
        Number of bits Bob flipped.
    parity_bits_leaked:
        Number of parity bits exchanged over the classical channel.  This is
        what an eavesdropper could learn *about the key* from reconciliation
        itself, so privacy amplification must compress by at least
        :attr:`leak_fraction`.
    passes_used:
        Number of Cascade passes actually executed.
    residual_errors:
        Bits still differing after the last pass.  **Simulator-only
        diagnostic** -- in a real run neither party can compute this (it
        needs the peer's secret); they only observe that the final parity
        checks agree.
    """

    alice_key: List[int]
    bob_key: List[int]
    corrected_bits: int
    parity_bits_leaked: int
    passes_used: int
    residual_errors: int

    @property
    def leak_fraction(self) -> float:
        """Fraction of the key length revealed as parity bits."""
        n = len(self.alice_key)
        return (self.parity_bits_leaked / n) if n else 0.0

    @property
    def is_reconciled(self) -> bool:
        """True when no residual errors remain (simulator diagnostic)."""
        return self.residual_errors == 0


def _xor_block(bits: List[int], positions: List[int]) -> int:
    """Return the XOR (parity) of ``bits`` at ``positions``."""
    acc = 0
    for pos in positions:
        acc ^= bits[pos]
    return acc


def _binary_locate_and_flip(
    alice: List[int],
    bob: List[int],
    block: List[int],
    leak: List[int],
) -> None:
    """Locate one error inside ``block`` by parity binary search, then flip it.

    Only sub-block parities are compared -- Alice's individual bit values are
    never read.  That is what makes this a legitimate reconciliation step
    instead of an oracle that copies Alice's key onto Bob's.
    """
    lo, hi = 0, len(block)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        a_parity = _xor_block(alice, block[lo:mid])
        b_parity = _xor_block(bob, block[lo:mid])
        leak[0] += 1
        if a_parity != b_parity:
            hi = mid
        else:
            lo = mid
    bob[block[lo]] ^= 1


def cascade_reconcile(
    alice_key: List[int],
    bob_key: List[int],
    *,
    block_size: int = 4,
    passes: int = 4,
    seed: Optional[int] = None,
) -> ReconciliationResult:
    """Reconcile two sifted keys with the Cascade protocol.

    Cascade is the classical post-processing step of BB84/E91: Alice and Bob
    exchange **parities only** over the classical channel and use them to
    locate and correct discrepancies in Bob's key.

    Each pass partitions the key into blocks, compares block parities and
    binary-searches any block whose parity differs down to a single bit,
    which Bob then flips.  After the first pass the key is randomly permuted,
    so blocks that held an even number of errors (and were therefore
    parity-invisible) get re-split on the next pass.

    Parameters
    ----------
    alice_key, bob_key:
        Sifted keys of equal length.  Alice's key is never modified.
    block_size:
        Size of the first-pass blocks; doubles on each subsequent pass.
    passes:
        Maximum number of Cascade passes.
    seed:
        Optional seed for the per-pass permutation (testing only).

    Returns
    -------
    ReconciliationResult
        Corrected keys plus the reconciliation statistics.

    Raises
    ------
    ValueError
        If the keys differ in length.
    """
    if len(alice_key) != len(bob_key):
        raise ValueError("Keys must be the same length")

    n = len(alice_key)
    alice = list(alice_key)
    bob = list(bob_key)
    if n == 0:
        return ReconciliationResult([], [], 0, 0, 0, 0)

    rng = random.Random(seed) if seed is not None else secrets.SystemRandom()
    leak = [0]
    corrected = 0
    passes_used = 0

    for pass_index in range(max(1, passes)):
        size = min(n, max(2, block_size * (2 ** pass_index)))
        order = list(range(n))
        if pass_index > 0:
            rng.shuffle(order)

        corrected_this_pass = False
        for start in range(0, n, size):
            block = order[start:start + size]
            if len(block) < 2:
                continue
            leak[0] += 1
            if _xor_block(alice, block) != _xor_block(bob, block):
                _binary_locate_and_flip(alice, bob, block, leak)
                corrected += 1
                corrected_this_pass = True

        passes_used = pass_index + 1
        if not corrected_this_pass:
            break

    residual = sum(1 for a, b in zip(alice, bob) if a != b)
    return ReconciliationResult(
        alice_key=alice,
        bob_key=bob,
        corrected_bits=corrected,
        parity_bits_leaked=leak[0],
        passes_used=passes_used,
        residual_errors=residual,
    )


def key_reconciliation(
    alice_key: List[int],
    bob_key: List[int],
    *,
    block_size: int = 4,
    passes: int = 4,
    seed: Optional[int] = None,
) -> Tuple[List[int], List[int]]:
    """Reconcile Bob's sifted key with Alice's using Cascade.

    Returns ``(alice_key, reconciled_bob_key)``.  Alice's key comes back
    unchanged -- only Bob corrects.  Use :func:`cascade_reconcile` when the
    number of corrected bits or the parity bits leaked are also needed (the
    latter is the input to privacy amplification).

    Raises
    ------
    ValueError
        If the keys differ in length.
    """
    result = cascade_reconcile(
        alice_key, bob_key, block_size=block_size, passes=passes, seed=seed
    )
    return result.alice_key, result.bob_key


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
    "cascade_reconcile",
    "ReconciliationResult",
    "QBER_SECURITY_THRESHOLD",
    "privacy_amplification",
    "run_bb84",
    "run_e91",
]
