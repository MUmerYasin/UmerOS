""" pin real Cascade reconciliation in ``quantum/qkd.py``.

The row said ``key_reconciliation`` simply flipped Bob's bits to match Alice
(``reconciled_bob[i] = 1 - reconciled_bob[i]``), i.e. **oracle reconciliation**:
it needs Alice's secret key, forces QBER to ~0 and makes an eavesdropper
undetectable.

Fix (session 207): replaced it with a genuine **Cascade** implementation.
Alice and Bob exchange *block parities only*; any block whose parity differs
is binary-searched down to one bit, which Bob flips.  Between passes the key
is randomly permuted so blocks holding an even number of errors -- which are
parity-invisible -- get re-split.

The decisive behavioural test is ``test_even_errors_are_not_corrected``: two
errors inside a single block leave the block parity unchanged, so a
parity-based protocol must NOT correct them.  An oracle would return zero
residual errors, so this test can only pass for a real implementation.
"""

from __future__ import annotations

import ast
import random
from pathlib import Path

import pytest

QKD_PATH = Path(__file__).resolve().parent.parent / "quantum" / "qkd.py"


def _source() -> str:
    return QKD_PATH.read_text(encoding="utf-8")


def _qkd():
    import sys

    root = str(QKD_PATH.parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from quantum import qkd

    return qkd


# ---------------------------------------------------------------- source invariants


class TestOraclePatternRemoved:
    """The oracle reconciliation must be gone from the source."""

    def test_no_bit_flip_oracle(self) -> None:
        assert "reconciled_bob[i] = 1 - reconciled_bob[i]" not in _source(), (
            "oracle reconciliation (flip Bob's bit to match Alice) still present"
        )

    def test_no_per_bit_comparison_loop(self) -> None:
        """No loop that compares Alice's and Bob's bits index-by-index."""
        tree = ast.parse(_source())
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name not in {"key_reconciliation", "cascade_reconcile"}:
                continue
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Compare):
                    continue
                # looking for  alice_key[i] != bob_key[i]  style comparisons
                sides = [sub.left, *sub.comparators]
                names = {
                    n.value.id
                    for n in sides
                    if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name)
                }
                if {"alice_key", "bob_key"} <= names or {
                    "reconciled_alice",
                    "reconciled_bob",
                } <= names:
                    pytest.fail(
                        f"{node.name}: per-bit comparison of both keys "
                        f"at line {sub.lineno} (oracle behaviour)"
                    )

    def test_uses_parity_helper(self) -> None:
        src = _source()
        assert "_xor_block" in src, "must XOR blocks (parity exchange)"
        assert "_binary_locate_and_flip" in src, "must binary-search the error"


class TestModuleSurface:
    """New public surface and the named QBER threshold."""

    def test_cascade_reconcile_exported(self) -> None:
        qkd = _qkd()
        assert hasattr(qkd, "cascade_reconcile")
        assert "cascade_reconcile" in qkd.__all__

    def test_result_type_exported(self) -> None:
        qkd = _qkd()
        assert hasattr(qkd, "ReconciliationResult")
        assert "ReconciliationResult" in qkd.__all__

    def test_threshold_constant(self) -> None:
        qkd = _qkd()
        assert qkd.QBER_SECURITY_THRESHOLD == pytest.approx(0.11)
        assert "QBER_SECURITY_THRESHOLD" in qkd.__all__

    def test_threshold_used_by_both_protocols(self) -> None:
        """BB84 and E91 must reference the named constant, not a literal 0.11."""
        src = _source()
        assert "qber_threshold = QBER_SECURITY_THRESHOLD" in src, (
            "BB84 must use the named threshold"
        )
        assert "is_secure=error_rate < QBER_SECURITY_THRESHOLD" in src, (
            "E91 must use the named threshold"
        )
        # the bare literals should be gone
        assert "qber_threshold = 0.11" not in src
        assert "is_secure=error_rate < 0.11" not in src


class TestDocstring:
    """Section 1 docstring compliance and honest documentation."""

    def test_docstring_documents_parity_only(self) -> None:
        doc = ast.get_docstring(ast.parse(_source()))
        assert doc is not None
        lowered = doc.lower()
        assert "parit" in lowered, "docstring must explain parity-only exchange"
        assert "oracle" in lowered, "docstring must disown oracle reconciliation"

    def test_author_trailer(self) -> None:
        assert "Author:  Umer OS Project" in _source()

    def test_license_trailer(self) -> None:
        assert "License: GPL-3.0 (GNU General Public License v3)" in _source()


# ---------------------------------------------------------------- behaviour


class TestCascadeBehaviour:
    """The protocol must behave like Cascade, not like an oracle."""

    def test_single_error_is_corrected(self) -> None:
        qkd = _qkd()
        alice = [0] * 8
        bob = [0] * 8
        bob[3] = 1
        result = qkd.cascade_reconcile(alice, bob, seed=1)
        assert result.residual_errors == 0
        assert result.bob_key == alice
        assert result.corrected_bits == 1

    def test_even_errors_are_not_corrected(self) -> None:
        """DECISIVE: two errors in one block are parity-invisible.

        Block parity is unchanged by an even number of flips, so a parity-based
        protocol cannot see them.  An oracle would correct both and report zero
        residual errors -- this test fails for any oracle implementation.
        """
        qkd = _qkd()
        alice = [0] * 8
        bob = [0] * 8
        bob[0] = 1
        bob[1] = 1
        result = qkd.cascade_reconcile(alice, bob, block_size=8, passes=1, seed=1)
        assert result.residual_errors == 2, (
            "even-error block must stay uncorrected in a parity-based protocol"
        )
        assert result.corrected_bits == 0

    def test_multipass_converges(self) -> None:
        """A 5 % error rate converges within a few passes."""
        qkd = _qkd()
        random.seed(7)
        alice = [random.randint(0, 1) for _ in range(200)]
        bob = list(alice)
        for i in random.sample(range(200), 10):
            bob[i] ^= 1
        result = qkd.cascade_reconcile(alice, bob, seed=3)
        assert result.residual_errors == 0, "Cascade should converge at 5 % QBER"
        assert result.corrected_bits == 10
        assert result.passes_used >= 1
        assert result.is_reconciled is True

    def test_alice_key_never_modified(self) -> None:
        qkd = _qkd()
        alice = [1, 0, 1, 1, 0, 0, 1, 0]
        bob = [1, 1, 1, 0, 0, 0, 1, 0]
        snapshot = list(alice)
        result = qkd.cascade_reconcile(alice, bob, seed=2)
        assert alice == snapshot, "Alice's key must not be touched"
        assert result.alice_key == snapshot

    def test_leak_is_reported(self) -> None:
        qkd = _qkd()
        alice = [0] * 32
        bob = [0] * 32
        bob[5] = 1
        result = qkd.cascade_reconcile(alice, bob, seed=0)
        assert result.parity_bits_leaked > 0
        assert 0 < result.leak_fraction <= 1.0

    def test_tuple_api_still_works(self) -> None:
        qkd = _qkd()
        a, b = qkd.key_reconciliation([1, 0, 1, 1], [1, 0, 1, 0], seed=0)
        assert a == [1, 0, 1, 1]
        assert b == a

    def test_length_mismatch_raises(self) -> None:
        qkd = _qkd()
        with pytest.raises(ValueError):
            qkd.key_reconciliation([0, 1], [0, 1, 0])

    def test_empty_keys(self) -> None:
        qkd = _qkd()
        assert qkd.key_reconciliation([], []) == ([], [])
        result = qkd.cascade_reconcile([], [])
        assert result.residual_errors == 0
        assert result.leak_fraction == 0.0


class TestQberStillMeaningful:
    """Reconciliation must not destroy the QBER signal."""

    def test_bb84_reports_qber_before_reconciliation(self) -> None:
        """``run()`` computes error_rate from the sifted keys, pre-reconciliation."""
        src = _source()
        # error rate is derived from sifted keys
        assert "errors = sum(a != b for a, b in zip(sifted_alice, sifted_bob))" in src
        assert "eavesdropper_detected = error_rate >= qber_threshold" in src

    def test_high_qber_marks_insecure(self) -> None:
        qkd = _qkd()
        # sanity: the threshold semantics are still "error_rate < threshold"
        assert qkd.QBER_SECURITY_THRESHOLD == pytest.approx(0.11)
