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

"""
Umer OS Initrd Phase Machine
============================
State machine that drives the eight boot phases
``/initrd`` reference.

The eight phases, as quoted from the reference::

    1) the boot loader loads the kernel and the initial RAM disk
    2) the kernel converts initrd into a "normal" RAM disk and
       frees the memory used by initrd
    3) initrd is mounted read-write as root
    4) /linuxrc is executed (this can be any valid executable,
       including shell scripts; it is run with uid 0 and can do
       basically everything init can do)
    5) linuxrc mounts the "real" root file system
    6) linuxrc places the root file system at the root directory
       using the pivot_root system call
    7) the usual boot sequence (e.g. invocation of /sbin/init) is
       performed on the root file system
    8) the initrd file system is removed

Each phase is modelled by a :class:`BootPhase` enum value plus a
:class:`PhaseOutcome` enum value that the runner records.  A failure
in any phase transitions to the :attr:`BootPhase.FAILED` state and
stops further transitions, but the report remains available for the
recovery scenario to inspect.

The machine itself knows nothing about *how* each phase is performed
- that's the :mod:`initrd.linuxrc` job.  The machine just enforces
ordering and emits audit events.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

log = logging.getLogger("UmerOS.Initrd.PhaseMachine")


# ---------------------------------------------------------------------------
# Phase enum
# ---------------------------------------------------------------------------

class BootPhase(str, Enum):
    """The eight phases from the /initrd reference, plus start/end."""

    START                = "start"
    PHASE_1_LOAD         = "phase_1_load"
    PHASE_2_CONVERT      = "phase_2_convert"
    PHASE_3_MOUNT_ROOT   = "phase_3_mount_root"
    PHASE_4_LINUXRC      = "phase_4_linuxrc"
    PHASE_5_MOUNT_REAL   = "phase_5_mount_real"
    PHASE_6_PIVOT_ROOT   = "phase_6_pivot_root"
    PHASE_7_EXEC_INIT    = "phase_7_exec_init"
    PHASE_8_TEARDOWN     = "phase_8_teardown"
    COMPLETED            = "completed"
    FAILED               = "failed"

    @property
    def index(self) -> int:
        order = [
            BootPhase.START,
            BootPhase.PHASE_1_LOAD,
            BootPhase.PHASE_2_CONVERT,
            BootPhase.PHASE_3_MOUNT_ROOT,
            BootPhase.PHASE_4_LINUXRC,
            BootPhase.PHASE_5_MOUNT_REAL,
            BootPhase.PHASE_6_PIVOT_ROOT,
            BootPhase.PHASE_7_EXEC_INIT,
            BootPhase.PHASE_8_TEARDOWN,
            BootPhase.COMPLETED,
        ]
        try:
            return order.index(self)
        except ValueError:
            return -1


class PhaseOutcome(str, Enum):
    """Result of one phase execution."""

    PENDING   = "pending"
    RUNNING   = "running"
    SUCCEEDED = "succeeded"
    SKIPPED   = "skipped"
    FAILED    = "failed"


# ---------------------------------------------------------------------------
# Allowed transitions
# ---------------------------------------------------------------------------

# Forward edges of the state machine.  Anything not listed is forbidden.
_ALLOWED: Dict[BootPhase, List[BootPhase]] = {
    BootPhase.START:              [BootPhase.PHASE_1_LOAD, BootPhase.FAILED],
    BootPhase.PHASE_1_LOAD:       [BootPhase.PHASE_2_CONVERT, BootPhase.FAILED],
    BootPhase.PHASE_2_CONVERT:    [BootPhase.PHASE_3_MOUNT_ROOT, BootPhase.FAILED],
    BootPhase.PHASE_3_MOUNT_ROOT: [BootPhase.PHASE_4_LINUXRC, BootPhase.FAILED],
    BootPhase.PHASE_4_LINUXRC:    [BootPhase.PHASE_5_MOUNT_REAL, BootPhase.FAILED],
    BootPhase.PHASE_5_MOUNT_REAL: [BootPhase.PHASE_6_PIVOT_ROOT, BootPhase.FAILED],
    BootPhase.PHASE_6_PIVOT_ROOT: [BootPhase.PHASE_7_EXEC_INIT, BootPhase.FAILED],
    BootPhase.PHASE_7_EXEC_INIT:  [BootPhase.PHASE_8_TEARDOWN, BootPhase.FAILED],
    BootPhase.PHASE_8_TEARDOWN:   [BootPhase.COMPLETED, BootPhase.FAILED],
    BootPhase.COMPLETED:          [],
    BootPhase.FAILED:             [],
}


# ---------------------------------------------------------------------------
# Phase record
# ---------------------------------------------------------------------------

@dataclass
class PhaseRecord:
    """Audit row for a single phase execution."""

    phase: BootPhase
    outcome: PhaseOutcome = PhaseOutcome.PENDING
    started_at: float = 0.0
    finished_at: float = 0.0
    duration: float = 0.0
    error: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "phase":       self.phase.value,
            "outcome":     self.outcome.value,
            "started_at":  self.started_at,
            "finished_at": self.finished_at,
            "duration":    self.duration,
            "error":       self.error,
            "notes":       list(self.notes),
        }


# ---------------------------------------------------------------------------
# Machine
# ---------------------------------------------------------------------------

class PhaseMachine:
    """Drives the boot through the eight phases in order."""

    def __init__(self) -> None:
        self.phase: BootPhase = BootPhase.START
        self.history: List[PhaseRecord] = []
        self.context: Dict[str, object] = {}

    # -- transitions ------------------------------------------------------

    def can_transition(self, next_phase: BootPhase) -> bool:
        return next_phase in _ALLOWED.get(self.phase, [])

    def transition(self, next_phase: BootPhase) -> None:
        if not self.can_transition(next_phase):
            raise RuntimeError(
                f"phase transition {self.phase.value} -> {next_phase.value} not allowed"
            )
        log.debug("phase: %s -> %s", self.phase.value, next_phase.value)
        self.phase = next_phase

    # -- execution scaffolding -------------------------------------------

    def begin_phase(self, phase: Optional[BootPhase] = None) -> PhaseRecord:
        """Mark ``phase`` (defaults to the next phase) as running."""
        target = phase or self._next_phase()
        if target is not None and target != self.phase:
            self.transition(target)
        rec = PhaseRecord(phase=self.phase, outcome=PhaseOutcome.RUNNING,
                          started_at=time.time())
        self.history.append(rec)
        return rec

    def finish_phase(self, rec: PhaseRecord, *,
                     outcome: PhaseOutcome = PhaseOutcome.SUCCEEDED,
                     error: Optional[str] = None,
                     note: Optional[str] = None) -> None:
        rec.finished_at = time.time()
        rec.duration = rec.finished_at - rec.started_at
        rec.outcome = outcome
        rec.error = error
        if note:
            rec.notes.append(note)
        if outcome == PhaseOutcome.FAILED:
            self.transition(BootPhase.FAILED)
        elif outcome == PhaseOutcome.SUCCEEDED:
            nxt = self._next_phase()
            if nxt is not None and nxt is not BootPhase.FAILED:
                self.transition(nxt)

    def skip_phase(self, reason: str) -> PhaseRecord:
        rec = self.begin_phase()
        self.finish_phase(rec, outcome=PhaseOutcome.SKIPPED, note=reason)
        return rec

    # -- introspection ----------------------------------------------------

    def report(self) -> List[dict]:
        """Return one dict per phase ever entered."""
        return [r.as_dict() for r in self.history]

    def summary(self) -> dict:
        """Compact view suitable for logs."""
        return {
            "current_phase":   self.phase.value,
            "phases_completed": sum(
                1 for r in self.history if r.outcome == PhaseOutcome.SUCCEEDED
            ),
            "phases_failed":   sum(
                1 for r in self.history if r.outcome == PhaseOutcome.FAILED
            ),
            "phases_skipped":  sum(
                1 for r in self.history if r.outcome == PhaseOutcome.SKIPPED
            ),
        }

    # -- internals --------------------------------------------------------

    def _next_phase(self) -> Optional[BootPhase]:
        order = [
            BootPhase.START,
            BootPhase.PHASE_1_LOAD,
            BootPhase.PHASE_2_CONVERT,
            BootPhase.PHASE_3_MOUNT_ROOT,
            BootPhase.PHASE_4_LINUXRC,
            BootPhase.PHASE_5_MOUNT_REAL,
            BootPhase.PHASE_6_PIVOT_ROOT,
            BootPhase.PHASE_7_EXEC_INIT,
            BootPhase.PHASE_8_TEARDOWN,
            BootPhase.COMPLETED,
        ]
        try:
            idx = order.index(self.phase)
        except ValueError:
            return None
        if idx + 1 < len(order):
            return order[idx + 1]
        return None


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    pm = PhaseMachine()
    rec = pm.begin_phase()
    pm.finish_phase(rec)
    if pm.phase != BootPhase.PHASE_2_CONVERT:
        return False
    try:
        pm.transition(BootPhase.PHASE_5_MOUNT_REAL)
    except RuntimeError:
        pass
    else:
        return False
    rec = pm.begin_phase()
    pm.finish_phase(rec)
    # After finishing PHASE_3_MOUNT_ROOT the machine advances to
    # PHASE_4_LINUXRC.
    if pm.phase != BootPhase.PHASE_4_LINUXRC:
        return False
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("phase_machine selftest:", "OK" if _selftest() else "FAIL")
