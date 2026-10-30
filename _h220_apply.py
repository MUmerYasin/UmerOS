"""applier -- make quantum/qrng.py honest about being a simulator.

Assert-first: every anchor must appear exactly once.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

TARGET = Path("quantum/qrng.py")
src = TARGET.read_text(encoding="utf-8")
original = src


def sub(old: str, new: str, label: str) -> None:
    global src
    count = src.count(old)
    if count != 1:
        print(f"ABORT [{label}]: expected 1 occurrence, found {count}")
        sys.exit(1)
    src = src.replace(old, new, 1)


# ------------------------------------------------------------------ 1. module docstring
sub(
    '''"""QRNG — Quantum Random Number Generator.

Implements true random number generation using quantum circuits.
"""''',
    '''"""QRNG — *simulated* quantum random number generation.

**This is a simulator, not a hardware QRNG.**  Every "quantum" draw comes from
sampling a statevector simulation, and that sampling is performed with
``numpy.random.choice`` / ``random.random`` — classical Mersenne Twister PRNG
output (see ``quantum/simulator.py`` and ``quantum/backend.py``, which even
calls ``np.random.seed()``).  The output is therefore **seedable and
deterministic** and must never be used as a cryptographic entropy source for
real key material.

:data:`IS_HARDWARE_QRNG` is ``False`` and :data:`ENTROPY_SOURCE` names the
actual source, so callers can assert on provenance instead of trusting the
class names.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""''',
    "module docstring",
)

# ------------------------------------------------------------------ 2. provenance constants
sub(
    "from .backend import LocalBackend\n\n\n",
    "from .backend import LocalBackend\n\n\n"
    "#: This module drives a classical PRNG through a quantum *simulator*; it is\n"
    "#: not a physical quantum random number generator.\n"
    "IS_HARDWARE_QRNG = False\n\n"
    "#: Human-readable description of where the bytes actually come from.\n"
    'ENTROPY_SOURCE = (\n'
    '    "numpy.random.choice / random.random (Mersenne Twister) over a "\n'
    '    "statevector-simulator measurement distribution -- NOT quantum hardware"\n'
    ")\n\n\n",
    "provenance constants",
)

# ------------------------------------------------------------------ 3. RandomBytes
sub(
    '''@dataclass
class RandomBytes:
    """Random byte sequence."""
    data: bytes
    num_bits: int
    method: str
''',
    '''@dataclass
class RandomBytes:
    """Random byte sequence.

    ``simulated`` is always ``True`` today: the bytes come from a classical
    PRNG driving a quantum *simulator* (see the module docstring), not from a
    hardware quantum measurement.
    """
    data: bytes
    num_bits: int
    method: str
    simulated: bool = True
''',
    "RandomBytes",
)

# ------------------------------------------------------------------ 4. method label
sub(
    '            method="quantum_hadamard"\n',
    '            method="simulator_hadamard"\n',
    "method label",
)

# ------------------------------------------------------------------ 5. QRNG docstring
sub(
    '''class QRNG:
    """Quantum Random Number Generator.

    Uses quantum circuits to generate true random numbers
    based on quantum mechanical principles.
    """
''',
    '''class QRNG:
    """Simulator-backed random number generator.

    Circuits run on a statevector simulator, so the measured distribution is
    sampled with a classical PRNG.  The output is **not** true quantum
    randomness and **not** cryptographically secure — see the module
    docstring.  ``seed`` makes the sequence reproducible, which is precisely
    why this is unsuitable as an entropy source.
    """

    #: Always ``False``: this class never talks to quantum hardware.
    is_hardware: bool = False
''',
    "QRNG docstring",
)

# ------------------------------------------------------------------ 6. seed pass-through
sub(
    '''    def _run_circuit(self, circuit: QuantumCircuit) -> dict:
        """Run a circuit and return measurement results."""
        backend = self._backend or LocalBackend()
        result = backend.run(circuit, shots=1)
        return result.counts
''',
    '''    def _run_circuit(self, circuit: QuantumCircuit) -> dict:
        """Run a circuit and return measurement results.

        When a ``seed`` was supplied it is passed through to the backend,
        offset by the draw counter so successive samples differ while the
        whole sequence stays reproducible.  That reproducibility is exactly
        why this generator must not be treated as a hardware entropy source.

        Before this change ``self._seed`` was stored but never read, so the
        documented ``seed`` parameter silently did nothing.
        """
        backend = self._backend or LocalBackend()
        seed = None if self._seed is None else self._seed + self._count
        result = backend.run(circuit, shots=1, seed=seed)
        return result.counts
''',
    "seed pass-through",
)

# ------------------------------------------------------------------ 7. QuantumEntropy docstring
sub(
    '''class QuantumEntropy:
    """Quantum entropy source for cryptographic applications.

    Uses quantum circuits to extract high-quality randomness
    suitable for cryptographic key generation.
    """
''',
    '''class QuantumEntropy:
    """Entropy *simulator* — not suitable for real key material.

    Draws from the same simulator-backed :class:`QRNG` pipeline, so the output
    is classical PRNG randomness presented as quantum measurement.  Classical
    entropy supplied through :meth:`seed` is mixed in with SHA3-256 so that
    seeding actually contributes.
    """
''',
    "QuantumEntropy docstring",
)

# ------------------------------------------------------------------ 8. reuse seeded runner
sub(
    '''        backend = self._backend or LocalBackend()
        result = backend.run(circuit, shots=1)
        key = list(result.counts.keys())[0]
''',
    '''        counts = self._qrng._run_circuit(circuit)
        key = list(counts.keys())[0]
''',
    "extract_entropy backend call",
)

# ------------------------------------------------------------------ 9. mix the pool
sub(
    '''        result = bytearray()

        # Mix quantum entropy
        while len(result) < num_bytes:
            quantum_entropy = self._extract_entropy()
            for b in quantum_entropy:
                if len(result) < num_bytes:
                    result.append(b)

        return bytes(result)
''',
    '''        result = bytearray()

        while len(result) < num_bytes:
            result.extend(self._extract_entropy())

        simulated = bytes(result[:num_bytes])
        if not self._pool:
            return simulated

        # Mix the caller-supplied classical entropy in with SHA3-256.  Before
        # this change ``seed()`` filled ``_pool`` but nothing ever read it, so
        # seeding silently did nothing.
        material = bytes(self._pool) + simulated
        digest = hashlib.sha3_256(material).digest()
        mixed = bytearray()
        while len(mixed) < num_bytes:
            mixed.extend(digest)
            digest = hashlib.sha3_256(digest + material).digest()
        return bytes(mixed[:num_bytes])
''',
    "pool mixing",
)

# ------------------------------------------------------------------ 10. __all__
sub(
    '    "RandomBit",\n    "RandomBytes",\n',
    '    "IS_HARDWARE_QRNG",\n    "ENTROPY_SOURCE",\n    "RandomBit",\n    "RandomBytes",\n',
    "__all__",
)

# ------------------------------------------------------------------ verify
ast.parse(src)
assert "true random number generation" not in src
assert src != original

TARGET.write_text(src, encoding="utf-8")
print("OK: quantum/qrng.py relabelled as a simulator.")
