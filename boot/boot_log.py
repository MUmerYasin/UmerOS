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
UmerOS Boot Log Module
=====================
Boot logging and audit trail for the boot process.

Manages:
- Boot event logging (kernel messages, systemd, GRUB)
- Boot time tracking and analytics
- Boot failure detection and reporting
- Persistent audit trail across boots

Reference: https://www.freedesktop.org/software/systemd/man/systemd-journald.service.html
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Boot.Log")


class BootLogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class BootPhase(Enum):
    FIRMWARE = "firmware"
    BOOTLOADER = "bootloader"
    KERNEL = "kernel"
    INITRAMFS = "initramfs"
    INIT = "init"
    USERSPACE = "userspace"
    COMPLETE = "complete"


class BootEventType(Enum):
    BOOT_START = "boot_start"
    BOOT_COMPLETE = "boot_complete"
    BOOT_FAILURE = "boot_failure"
    KERNEL_LOAD = "kernel_load"
    INITRD_LOAD = "initrd_load"
    SERVICE_START = "service_start"
    SERVICE_FAIL = "service_fail"
    GRUB_SELECT = "grub_select"
    MEMTEST = "memtest"
    UPDATE = "update"
    CRASH = "crash"
    FALLBACK = "fallback"


@dataclass
class BootEvent:
    event_type: BootEventType
    phase: BootPhase = BootPhase.FIRMWARE
    timestamp: float = field(default_factory=time.time)
    message: str = ""
    level: BootLogLevel = BootLogLevel.INFO
    details: Optional[Dict[str, str]] = None
    duration_ms: Optional[float] = None

    def as_dict(self) -> dict:
        return {
            "event_type": self.event_type.value,
            "phase": self.phase.value,
            "timestamp": self.timestamp,
            "message": self.message,
            "level": self.level.value,
            "details": self.details,
            "duration_ms": self.duration_ms,
        }


@dataclass
class BootSession:
    boot_id: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    events: List[BootEvent] = field(default_factory=list)
    kernel_version: str = ""
    bootloader: str = ""
    success: bool = True

    @property
    def duration_sec(self) -> Optional[float]:
        if self.end_time is not None:
            return self.end_time - self.start_time
        return None

    def add_event(self, event: BootEvent) -> None:
        self.events.append(event)
        if event.event_type == BootEventType.BOOT_FAILURE:
            self.success = False

    def as_dict(self) -> dict:
        return {
            "boot_id": self.boot_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "event_count": len(self.events),
            "kernel_version": self.kernel_version,
            "bootloader": self.bootloader,
            "success": self.success,
            "duration_sec": self.duration_sec,
        }


@dataclass
class BootStats:
    total_boots: int = 0
    successful_boots: int = 0
    failed_boots: int = 0
    avg_boot_time_sec: float = 0.0
    fastest_boot_sec: float = 0.0
    slowest_boot_sec: float = 0.0
    last_boot: Optional[BootSession] = None

    @property
    def success_rate(self) -> float:
        if self.total_boots == 0:
            return 0.0
        return self.successful_boots / self.total_boots

    def as_dict(self) -> dict:
        return {
            "total_boots": self.total_boots,
            "successful_boots": self.successful_boots,
            "failed_boots": self.failed_boots,
            "success_rate": round(self.success_rate, 4),
            "avg_boot_time_sec": round(self.avg_boot_time_sec, 2),
            "fastest_boot_sec": round(self.fastest_boot_sec, 2),
            "slowest_boot_sec": round(self.slowest_boot_sec, 2),
        }


class BootLogger:
    def __init__(self, log_dir: Optional[Path] = None) -> None:
        self.log_dir = log_dir
        self.sessions: List[BootSession] = []
        self._current: Optional[BootSession] = None

    def start_boot(self, boot_id: str = "", kernel_version: str = "", bootloader: str = "") -> BootSession:
        self._current = BootSession(
            boot_id=boot_id or f"boot-{int(time.time())}",
            kernel_version=kernel_version,
            bootloader=bootloader,
        )
        self._current.add_event(BootEvent(
            event_type=BootEventType.BOOT_START,
            phase=BootPhase.FIRMWARE,
            message="Boot started",
        ))
        return self._current

    def log_event(self, event_type: BootEventType, message: str, phase: BootPhase = BootPhase.FIRMWARE,
                  level: BootLogLevel = BootLogLevel.INFO, details: Optional[Dict[str, str]] = None) -> Optional[BootEvent]:
        if self._current is None:
            self.start_boot()
        event = BootEvent(
            event_type=event_type, phase=phase, message=message,
            level=level, details=details,
        )
        self._current.add_event(event)
        return event

    def end_boot(self, success: bool = True) -> Optional[BootSession]:
        if self._current is None:
            return None
        event_type = BootEventType.BOOT_COMPLETE if success else BootEventType.BOOT_FAILURE
        self._current.add_event(BootEvent(
            event_type=event_type, phase=BootPhase.COMPLETE,
            message="Boot finished" if success else "Boot failed",
            level=BootLogLevel.INFO if success else BootLogLevel.ERROR,
        ))
        self._current.end_time = time.time()
        self._current.success = success
        self.sessions.append(self._current)
        finished = self._current
        self._current = None
        return finished

    def get_stats(self) -> BootStats:
        stats = BootStats()
        stats.total_boots = len(self.sessions)
        durations: List[float] = []
        for s in self.sessions:
            if s.success:
                stats.successful_boots += 1
            else:
                stats.failed_boots += 1
            d = s.duration_sec
            if d is not None:
                durations.append(d)
        if durations:
            stats.avg_boot_time_sec = sum(durations) / len(durations)
            stats.fastest_boot_sec = min(durations)
            stats.slowest_boot_sec = max(durations)
        if self.sessions:
            stats.last_boot = self.sessions[-1]
        return stats

    def save_session(self, session: BootSession) -> Path:
        if self.log_dir is None:
            self.log_dir = Path("/var/log/umeros/boot")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        path = self.log_dir / f"{session.boot_id}.json"
        import json
        path.write_text(json.dumps(session.as_dict(), indent=2), encoding="utf-8")
        return path


class BootAnalyzer:
    def __init__(self, logger: BootLogger) -> None:
        self.logger = logger

    def detect_repeated_failures(self, threshold: int = 3) -> bool:
        recent = self.logger.sessions[-threshold:]
        return len(recent) >= threshold and all(not s.success for s in recent)

    def get_slow_phases(self, threshold_sec: float = 5.0) -> List[str]:
        slow: List[str] = []
        for session in self.logger.sessions:
            for event in session.events:
                if event.duration_ms and event.duration_ms / 1000.0 > threshold_sec:
                    slow.append(f"{session.boot_id}: {event.phase.value} took {event.duration_ms:.0f}ms")
        return slow

    def get_failure_summary(self) -> Dict[str, int]:
        failures: Dict[str, int] = {}
        for session in self.logger.sessions:
            if not session.success:
                for event in session.events:
                    if event.level == BootLogLevel.ERROR:
                        key = event.event_type.value
                        failures[key] = failures.get(key, 0) + 1
        return failures


def _selftest() -> bool:
    logger = BootLogger()

    # Start and end a successful boot
    session = logger.start_boot(boot_id="test-1", kernel_version="6.1.0", bootloader="grub")
    logger.log_event(BootEventType.KERNEL_LOAD, "Kernel loaded", BootPhase.KERNEL)
    logger.log_event(BootEventType.INITRD_LOAD, "Initrd loaded", BootPhase.INITRAMFS)
    ended = logger.end_boot(success=True)
    if ended is None:
        return False
    if not ended.success:
        return False
    if ended.duration_sec is None:
        return False

    # Start and end a failed boot
    logger.start_boot(boot_id="test-2")
    logger.log_event(BootEventType.SERVICE_FAIL, "init failed", level=BootLogLevel.ERROR)
    logger.end_boot(success=False)

    # Stats
    stats = logger.get_stats()
    if stats.total_boots != 2:
        return False
    if stats.successful_boots != 1:
        return False
    if stats.failed_boots != 1:
        return False
    if stats.success_rate != 0.5:
        return False

    # Analyzer
    analyzer = BootAnalyzer(logger)
    if not analyzer.detect_repeated_failures():
        if stats.failed_boots < 3:
            pass
        else:
            return False
    failures = analyzer.get_failure_summary()
    if "boot_failure" not in failures and "service_fail" not in failures:
        return False

    # Event as_dict
    event = BootEvent(event_type=BootEventType.BOOT_START, message="test")
    d = event.as_dict()
    if "event_type" not in d:
        return False

    # Session as_dict
    sd = ended.as_dict()
    if "boot_id" not in sd:
        return False

    # Stats as_dict
    std = stats.as_dict()
    if "total_boots" not in std:
        return False

    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("boot_log selftest:", "OK" if _selftest() else "FAIL")
