"""
Umer OS Kernel Taint Tracking  [TODAY]
==========================================
Integrity state bitmask inspired by Linux kernel/panic.c taint_flags.

    Linux reference: kernel/panic.c — taint_flags[] is a 20-bit bitmask
    recording categories of "badness": proprietary module loaded, bad page,
    machine check, unsigned module, etc.  Flags only increase — they are
    never cleared.  panic() messages include the taint string for forensic
    value.

Design:
    - Named taint flags (enum-like strings stored as bit positions).
    - ``taint.add(TAINT_OOM_KILL)`` — ORs the bit, never clears it.
    - ``taint.summary()`` returns a compact label string (e.g. "U B").
    - Included in every ``kernel.status()`` and panic report.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
from typing import FrozenSet, List, Optional

log = logging.getLogger("UmerOS.Taint")

# ── Taint Flag Definitions ──────────────────────────────────────────────────────
# Flags are monotonically increasing bit positions.  Never reuse a removed bit.

TAINT_PROPRIETARY:  str = "TAINT_PROPRIETARY"   # Proprietary module loaded
TAINT_UNSIGNED_MODULE: str = "TAINT_UNSIGNED_MODULE" # Unsigned/unverified module
TAINT_BAD_PAGE:       str = "TAINT_BAD_PAGE"       # Bad memory page detected
TAINT_OOM_KILL:      str = "TAINT_OOM_KILL"      # Out-of-memory kill occurred
TAINT_CRYPTO_FAIL:   str = "TAINT_CRYPTO_FAIL"   # Cryptographic verification failed
TAINT_SANDBOX_VIOLATION: str = "TAINT_SANDBOX_VIOLATION"  # Sandbox was breached
TAINT_IPC_TAMPER:    str = "TAINT_IPC_TAMPER"     # IPC message tampering detected
TAINT_HUNG_TASK:     str = "TAINT_HUNG_TASK"      # A task was killed by watchdog

# Internal mapping: flag name → bit position
_FLAGS: List[str] = [
    TAINT_PROPRIETARY,
    TAINT_UNSIGNED_MODULE,
    TAINT_BAD_PAGE,
    TAINT_OOM_KILL,
    TAINT_CRYPTO_FAIL,
    TAINT_SANDBOX_VIOLATION,
    TAINT_IPC_TAMPER,
    TAINT_HUNG_TASK,
]

_FLAG_INDEX: dict = {name: 1 << i for i, name in enumerate(_FLAGS)}
_FLAG_LABEL: dict = {1 << i: _FLAGS[i][6:] for i, name in enumerate(_FLAGS)}


# ── Taint Tracker ───────────────────────────────────────────────────────────────

class KernelTaint:
    """Monotonic bitmask tracking kernel integrity events.

    Inspired by Linux ``kernel/panic.c``: once a taint bit is set it is
    **never** cleared.  This gives post-mortem forensic value — the taint
    string tells you every category of degradation the system has
    experienced during its lifetime.

    Usage::

        taint = KernelTaint()
        taint.add(TAINT_OOM_KILL)
        taint.add(TAINT_CRYPTO_FAIL)
        print(taint.summary())          # "O C"
        print(taint.is_tainted())       # True
        print(taint.has(TAINT_OOM_KILL))  # True
    """

    def __init__(self) -> None:
        self._mask: int = 0  # bitmask — only ever OR'd, never AND'd

    # ── Mutations (monotonic — no clear) ──────────────────────────────────────

    def add(self, flag: str) -> None:
        """Set a taint flag (idempotent — safe to call multiple times).

        Args:
            flag: One of the TAINT_* constants.

        Raises:
            ValueError: If the flag name is unknown.
        """
        if flag not in _FLAG_INDEX:
            raise ValueError(f"Unknown taint flag: {flag!r}")
        bit = _FLAG_INDEX[flag]
        if not (self._mask & bit):
            self._mask |= bit
            log.warning("Kernel taint added: %s", flag)

    # ── Queries ─────────────────────────────────────────────────────────────────

    def has(self, flag: str) -> bool:
        """Check whether a specific taint flag is set.

        Returns:
            True if the flag is set.
        """
        if flag not in _FLAG_INDEX:
            return False
        return bool(self._mask & _FLAG_INDEX[flag])

    def is_tainted(self) -> bool:
        """Return True if any taint flag is set.

        Returns:
            True if the kernel has been tainted.
        """
        return self._mask != 0

    @property
    def mask(self) -> int:
        """Return the raw bitmask (for serialization / status)."""
        return self._mask

    def flags(self) -> FrozenSet[str]:
        """Return the set of all currently-set taint flag names.

        Returns:
            FrozenSet of TAINT_* strings.
        """
        return frozenset(
            name for name, bit in _FLAG_INDEX.items() if self._mask & bit
        )

    def summary(self) -> str:
        """Return a compact taint string like ``"U C O"``.

        Uses short labels (the part after ``TAINT_``).  Returns an empty
        string if the kernel is clean.

        Returns:
            Compact label string.
        """
        if not self.is_tainted():
            return ""
        parts = []
        for bit_pos in range(len(_FLAGS)):
            if self._mask & (1 << bit_pos):
                parts.append(_FLAG_LABEL[1 << bit_pos])
        return " ".join(parts)

    def __repr__(self) -> str:
        if self.is_tainted():
            return f"KernelTaint({self.summary()!r})"
        return "KernelTaint(clean)"
