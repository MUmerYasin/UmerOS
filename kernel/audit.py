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
Umer OS Security Audit Subsystem
================================
Inspired by auditd and audit.c, this subsystem logs security-relevant
events in the kernel (e.g., capability checks, sandbox violations).
"""

import logging
import time
from dataclasses import dataclass
from typing import List, Dict, Optional

log = logging.getLogger("UmerOS.Audit")

@dataclass
class AuditEvent:
    """Represents a single security-auditable event."""
    timestamp: float
    pid: int
    event_type: str
    success: bool
    details: str

class AuditLogger:
    """Manages the creation and storage of audit events."""
    
    def __init__(self, in_memory: bool = True):
        self.events: List[AuditEvent] = []
        self.in_memory = in_memory
        log.info("AuditLogger initialized (in_memory=%s)", in_memory)

    def log_event(self, pid: int, event_type: str, success: bool, details: str = "") -> None:
        """Log a new security event."""
        event = AuditEvent(
            timestamp=time.time(),
            pid=pid,
            event_type=event_type,
            success=success,
            details=details
        )
        self.events.append(event)
        
        status = "SUCCESS" if success else "DENIED"
        log_msg = f"[AUDIT] PID:{pid} TYPE:{event_type} STATUS:{status} DETAILS:'{details}'"
        
        if not success:
            log.warning(log_msg)
        else:
            log.debug(log_msg)

    def get_events_for_pid(self, pid: int) -> List[AuditEvent]:
        """Retrieve all events related to a specific process."""
        return [e for e in self.events if e.pid == pid]

    def get_violations(self) -> List[AuditEvent]:
        """Retrieve all denied access events (violations)."""
        return [e for e in self.events if not e.success]
