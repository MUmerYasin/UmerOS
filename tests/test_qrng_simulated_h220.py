"""pin honest labelling of ``quantum/qrng.py`` as a *simulator*.

The row said ``get_random_bytes``/``_extract_entropy`` derive "random" bytes
from a seedable statevector **simulator**, not a hardware QRNG, while security
callers treat the output as quantum randomness.

Drift-recon (session 208) confirmed the premise and found it understated:

* the sampler really is classical — ``quantum/simulator.py`` uses
  ``np.random.choice`` and ``random.random`` (Mersenne Twister), and
  ``quantum/backend.py`` even calls ``np.random.seed(seed)``;
* ``QRNG._seed`` was **stored but never read**, so the documented ``seed``
  parameter silently did nothing (``BB84`` passes a seed straight into it);
* ``QuantumEntropy._pool`` was filled by ``seed()`` but **never read**, so
  seeding the entropy pool was a no-op;
* ``QuantumEntropy._extract_entropy`` called ``circuit.measure(qr, cr)`` with
  ``QuantumRegister`` objects although ``measure`` takes ints, so
  ``get_random_bytes()`` raised ``TypeError`` outright.

Fix: label the module/classes honestly (``IS_HARDWARE_QRNG = False``,
``ENTROPY_SOURCE``, ``QRNG.is_hardware = False``, ``RandomBytes.simulated``),
wire the seed through to the backend, mix the entropy pool with SHA3-256, and
measure each wire individually.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

QUANTUM = Path(__file__).resolve().parent.parent / "quantum"
QRNG_PATH = QUANTUM / "qrng.py"
SIMULATOR_PATH = QUANTUM / "simulator.py"


def _src(path: Path = QRNG_PATH) -> str:
    return path.read_text(encoding="utf-8")


def _qrng():
    import sys

    root = str(QUANTUM.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from quantum import qrng

    return qrng


# ------------------------------------------------------------------ labelling


class TestHonestLabelling:
    """The module must not present itself as a hardware QRNG."""

    def test_no_true_random_claim(self) -> None:
        assert "true random number generation" not in _src(), (
            "module still claims to generate 'true random numbers'"
        )

    def test_docstring_says_simulator(self) -> None:
        doc = ast.get_docstring(ast.parse(_src()))
        assert doc is not None
        lowered = doc.lower()
        assert "simulator" in lowered, "docstring must say it is a simulator"
        assert "not a hardware qrng" in lowered or "not a physical" in lowered, (
            "docstring must explicitly deny being a hardware QRNG"
        )

    def test_is_hardware_flag_false(self) -> None:
        qrng = _qrng()
        assert qrng.IS_HARDWARE_QRNG is False
        assert "IS_HARDWARE_QRNG" in qrng.__all__

    def test_qrng_class_flag(self) -> None:
        qrng = _qrng()
        assert qrng.QRNG.is_hardware is False

    def test_entropy_source_names_prng(self) -> None:
        qrng = _qrng()
        source = qrng.ENTROPY_SOURCE
        assert "ENTROPY_SOURCE" in qrng.__all__
        lowered = source.lower()
        assert "mersenne" in lowered or "prng" in lowered or "numpy.random" in lowered
        assert "not quantum hardware" in lowered

    def test_random_bytes_marked_simulated(self) -> None:
        qrng = _qrng()
        out = qrng.QRNG().random_bytes(2)
        assert out.simulated is True
        assert out.method == "simulator_hadamard", (
            "method label must not claim raw quantum generation"
        )

    def test_no_quantum_hadamard_label_left(self) -> None:
        assert '"quantum_hadamard"' not in _src(), (
            "misleading method label 'quantum_hadamard' still present"
        )

    def test_section1_trailers(self) -> None:
        src = _src()
        assert "Author:  Umer OS Project" in src
        assert "License: GPL-3.0 (GNU General Public License v3)" in src


class TestLabellingMatchesReality:
    """The label is only honest if the sampler really is classical."""

    def test_simulator_samples_with_classical_prng(self) -> None:
        src = _src(SIMULATOR_PATH)
        assert "np.random.choice" in src or "random.random" in src, (
            "simulator must still sample with a classical PRNG"
        )

    def test_backend_seeds_numpy(self) -> None:
        backend = (QUANTUM / "backend.py").read_text(encoding="utf-8")
        assert "np.random.seed(seed)" in backend, (
            "backend reseeding numpy proves the source is deterministic"
        )


# ------------------------------------------------------------------ seed wiring


class TestSeedActuallyWorks:
    """``seed`` used to be stored and ignored."""

    def test_seed_is_read_in_source(self) -> None:
        src = _src()
        assert "self._seed = seed" in src
        # must be consumed somewhere else too
        assert src.count("self._seed") >= 2, (
            "self._seed is assigned but never read"
        )

    def test_same_seed_is_reproducible(self) -> None:
        qrng = _qrng()
        a = qrng.QRNG(seed=42).random_bits(16)
        b = qrng.QRNG(seed=42).random_bits(16)
        assert a == b, "same seed must reproduce the same sequence"

    def test_different_seed_differs(self) -> None:
        qrng = _qrng()
        a = qrng.QRNG(seed=42).random_bits(16)
        c = qrng.QRNG(seed=43).random_bits(16)
        assert a != c

    def test_unseeded_is_not_constant(self) -> None:
        qrng = _qrng()
        bits = qrng.QRNG().random_bits(64)
        assert 0 in bits and 1 in bits, "output looks degenerate"


# ------------------------------------------------------------------ pool wiring


class TestEntropyPoolMixing:
    """``QuantumEntropy.seed()`` used to be a no-op."""

    def test_pool_is_read(self) -> None:
        src = _src()
        assert "self._pool" in src
        assert src.count("self._pool") >= 2, "_pool is filled but never read"

    def test_pool_changes_output(self) -> None:
        qrng = _qrng()
        a = qrng.QuantumEntropy(8)
        a.seed(b"alpha")
        b = qrng.QuantumEntropy(8)
        b.seed(b"beta")
        assert a.get_random_bytes(8) != b.get_random_bytes(8), (
            "different pool contents must yield different bytes"
        )

    def test_unpooled_differs_from_pooled(self) -> None:
        qrng = _qrng()
        pooled = qrng.QuantumEntropy(8)
        pooled.seed(b"alpha")
        plain = qrng.QuantumEntropy(8)
        assert pooled.get_random_bytes(8) != plain.get_random_bytes(8)


# ------------------------------------------------------------------ extract_entropy


class TestExtractEntropyWorks:
    """``get_random_bytes`` used to raise TypeError on ``measure(qr, cr)``."""

    def test_returns_requested_length(self) -> None:
        qrng = _qrng()
        out = qrng.QuantumEntropy(8).get_random_bytes(16)
        assert isinstance(out, bytes)
        assert len(out) == 16

    def test_measures_each_wire(self) -> None:
        src = _src()
        assert "circuit.measure(qr, cr)" not in src, (
            "measure() takes ints, not QuantumRegister objects"
        )
        assert "circuit.measure(q, q)" in src

    def test_various_qubit_counts(self) -> None:
        # Kept <= 8 qubits: the statevector simulator builds a full
        # (2**n, 2**n) gate matrix, so 16 qubits would need 64 GiB.
        qrng = _qrng()
        for n in (1, 4, 8):
            out = qrng.QuantumEntropy(n).get_random_bytes(4)
            assert len(out) == 4


# ------------------------------------------------------------------ helpers


class TestConvenienceFunctions:
    """The module-level helpers must still work."""

    def test_generate_random_bytes(self) -> None:
        qrng = _qrng()
        out = qrng.generate_random_bytes(4)
        assert isinstance(out, bytes) and len(out) == 4

    def test_generate_random_int(self) -> None:
        qrng = _qrng()
        value = qrng.generate_random_int(8)
        assert 0 <= value < 256

    def test_generate_random_string(self) -> None:
        qrng = _qrng()
        s = qrng.generate_random_string(12)
        assert len(s) == 12 and s.isalnum()

    def test_coin_flip_is_bool(self) -> None:
        qrng = _qrng()
        assert isinstance(qrng.generate_random_bit(), bool)
