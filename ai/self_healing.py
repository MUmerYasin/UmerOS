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

"""AI self-healing service  [TODAY] (monitoring) / [FUTURE] (auto-patch).

[H12 GATE] Design mandate: any path that *executes* generated patches must be
capability-scoped, sandbox-executed, audit-logged and rollback-tested. The
current service deliberately does NOT execute anything: ``mitigate`` only
records an audited, capability-gated restart decision.
"""
from __future__ import annotations

import logging
import time
from typing import Dict, List

try:
    from core.capability_gate import gate
    from core.capability_gate import CAP_SYS_ADMIN
except Exception:  # pragma: no cover - standalone fallback
    import os as _os
    import sys as _sys
    _proj = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if _proj not in _sys.path:
        _sys.path.insert(0, _proj)
    from core.capability_gate import gate, CAP_SYS_ADMIN

log = logging.getLogger("UmerOS.AI.SelfHealing")


class SelfHealingService:
    """Crash monitor with audited, capability-gated restart decisions."""

    def __init__(self) -> None:
        self.crashed_pids: set = set()
        self.audit_log: List[Dict[str, object]] = []
        log.info("SelfHealingService initialised (no auto-exec).")

    def _audit(self, action: str, pid: int, outcome: str) -> None:
        entry = {"ts": time.time(), "action": action,
                 "pid": pid, "outcome": outcome}
        self.audit_log.append(entry)
        log.info("audit: %s", entry)

    def detect_anomaly(self, pid: int, status: str) -> bool:
        """Record a crash anomaly for *pid*."""
        if status == "CRASHED":
            log.warning("Anomaly detected: PID %d crashed.", pid)
            self.crashed_pids.add(pid)
            self._audit("detect", pid, "crashed")
            return True
        return False

    def mitigate(self, pid: int) -> bool:
        """Decide a mitigation for *pid*.

        [FIX H21/H12] Requires the SYS_ADMIN capability (fail-closed when a
        manager is wired / strict mode), writes an audit record BEFORE and
        AFTER, and never executes generated code. The actual process restart
        is delegated to the supervisor; this service only authorises it.
        """
        if pid not in self.crashed_pids:
            return False
        gate.require(CAP_SYS_ADMIN)  # [FIX H21] privileged recovery op
        self._audit("mitigate-authorised", pid, "restart handed to supervisor")
        self.crashed_pids.discard(pid)
        self._audit("mitigate-complete", pid, "ok")
        return True