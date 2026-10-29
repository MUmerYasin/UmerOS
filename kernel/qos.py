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
UmerOS Deterministic Latency QoS Engine ( NEXT Latency Engine).

Classifies tasks into distinct Quality of Service (QoS) classes and dynamically
monitors Flutter UI frame pacing telemetry to throttle background workloads
(quantum simulations, batch processing) whenever the UI render loop drops frames.
"""

from __future__ import annotations

import logging
import time
from enum import IntEnum
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Kernel.QoS")

# Frame deadline threshold (16.6ms for 60 FPS, 8.3ms for 120 FPS)
FRAME_DEADLINE_MS: float = 16.67
THROTTLE_COOLDOWN_SECONDS: float = 2.0


class TaskQoS(IntEnum):
    """Quality of Service tiers for task execution."""

    USER_INTERACTIVE = 100  # Direct pointer/keyboard input, immediate preemption
    USER_INITIATED   = 75   # Window animations, UI drawing, render requests
    UTILITY          = 40   # Asynchronous I/O, network transfers, file saves
    BACKGROUND       = 10   # Quantum simulation, background compilation, indexing


class QoSManager:
    """Manages real-time latency feedback and dynamic background throttling."""

    def __init__(self) -> None:
        self._dropped_frames_count: int = 0
        self._last_dropped_timestamp: float = 0.0
        self._total_frames_reported: int = 0
        self._recent_render_times: List[float] = []

    def record_frame_metric(self, render_time_ms: float, dropped: bool = False) -> bool:
        """Record a frame render duration reported by the UI shell.

        Args:
            render_time_ms: Milliseconds taken by Flutter to render the last frame.
            dropped: Explicit boolean flag indicating whether VSync deadline was missed.

        Returns:
            True if system entered or remains in throttled state.
        """
        self._total_frames_reported += 1
        self._recent_render_times.append(render_time_ms)
        if len(self._recent_render_times) > 60:
            self._recent_render_times.pop(0)

        if dropped or render_time_ms > FRAME_DEADLINE_MS:
            self._dropped_frames_count += 1
            self._last_dropped_timestamp = time.time()
            log.warning(
                "UI Frame Drop detected: %.2f ms (threshold %.2f ms). Throttling background tasks.",
                render_time_ms,
                FRAME_DEADLINE_MS,
            )
            return True
        return self.is_throttled()

    def is_throttled(self) -> bool:
        """Check if background tasks should currently be throttled."""
        if self._last_dropped_timestamp == 0.0:
            return False
        return (time.time() - self._last_dropped_timestamp) < THROTTLE_COOLDOWN_SECONDS

    def get_throttle_factor(self, qos: TaskQoS) -> float:
        """Compute execution multiplier for a given QoS tier under current conditions.

        Returns:
            Multiplier in [0.1, 1.0]. Interactive tasks always get 1.0.
        """
        if not self.is_throttled():
            return 1.0

        if qos >= TaskQoS.USER_INITIATED:
            return 1.0
        elif qos == TaskQoS.UTILITY:
            return 0.5
        else:  # BACKGROUND
            return 0.1

    def stats(self) -> Dict[str, float | int | bool]:
        """Return QoS telemetry metrics summary."""
        avg_render = (
            sum(self._recent_render_times) / len(self._recent_render_times)
            if self._recent_render_times
            else 0.0
        )
        return {
            "total_frames_reported": self._total_frames_reported,
            "dropped_frames_count": self._dropped_frames_count,
            "average_render_time_ms": round(avg_render, 2),
            "is_throttled": self.is_throttled(),
        }

    def reset_metrics(self) -> None:
        """Reset telemetry counters."""
        self._dropped_frames_count = 0
        self._last_dropped_timestamp = 0.0
        self._total_frames_reported = 0
        self._recent_render_times.clear()


# Global default manager
qos_manager = QoSManager()
