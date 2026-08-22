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

"""Real-time file system monitoring for active threat detection."""

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set

from .scanner import FileScanner, ScanReport, ScanResult


@dataclass
class MonitorEvent:
    event_type: str  # created, modified, moved
    file_path: str
    timestamp: float
    scan_result: Optional[ScanReport] = None

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "file_path": self.file_path,
            "timestamp": self.timestamp,
            "scan_result": self.scan_result.to_dict() if self.scan_result else None,
        }


class RealtimeMonitor:
    def __init__(self, scanner: FileScanner):
        self.scanner = scanner
        self._watched_dirs: Set[str] = set()
        self._running = False
        self._events: List[MonitorEvent] = []
        self._poll_interval = 2.0
        self._snapshots: Dict[str, Dict[str, float]] = {}
        self._on_threat: Optional[Callable[[MonitorEvent], None]] = None
        self._max_events = 500

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def watched_dirs(self) -> List[str]:
        return sorted(self._watched_dirs)

    def set_threat_callback(self, callback: Callable[[MonitorEvent], None]):
        self._on_threat = callback

    def add_watch(self, dir_path: str) -> bool:
        if os.path.isdir(dir_path):
            self._watched_dirs.add(os.path.abspath(dir_path))
            self._take_snapshot(dir_path)
            return True
        return False

    def remove_watch(self, dir_path: str) -> bool:
        path = os.path.abspath(dir_path)
        if path in self._watched_dirs:
            self._watched_dirs.discard(path)
            self._snapshots.pop(path, None)
            return True
        return False

    def _take_snapshot(self, dir_path: str):
        snapshot = {}
        for root, _, files in os.walk(dir_path):
            for fn in files:
                fp = os.path.join(root, fn)
                try:
                    snapshot[fp] = os.path.getmtime(fp)
                except OSError:
                    pass
        self._snapshots[os.path.abspath(dir_path)] = snapshot

    def _detect_changes(self) -> List[MonitorEvent]:
        events = []
        for watch_dir in list(self._watched_dirs):
            current = {}
            for root, _, files in os.walk(watch_dir):
                for fn in files:
                    fp = os.path.join(root, fn)
                    try:
                        current[fp] = os.path.getmtime(fp)
                    except OSError:
                        pass

            old = self._snapshots.get(watch_dir, {})

            # New or modified files
            for fp, mtime in current.items():
                if fp not in old:
                    events.append(MonitorEvent(
                        event_type="created",
                        file_path=fp,
                        timestamp=time.time(),
                    ))
                elif mtime > old[fp]:
                    events.append(MonitorEvent(
                        event_type="modified",
                        file_path=fp,
                        timestamp=time.time(),
                    ))

            # Deleted files
            for fp in old:
                if fp not in current:
                    events.append(MonitorEvent(
                        event_type="deleted",
                        file_path=fp,
                        timestamp=time.time(),
                    ))

            self._snapshots[watch_dir] = current

        return events

    async def _monitor_loop(self):
        while self._running:
            await asyncio.sleep(self._poll_interval)
            events = self._detect_changes()
            for event in events:
                if event.event_type in ("created", "modified"):
                    scan_report = await asyncio.get_event_loop().run_in_executor(
                        None, self.scanner.scan_file, event.file_path
                    )
                    event.scan_result = scan_report
                    if scan_report.result in (ScanResult.THREAT_FOUND, ScanResult.SUSPICIOUS):
                        self._events.append(event)
                        if len(self._events) > self._max_events:
                            self._events = self._events[-self._max_events:]
                        if self._on_threat:
                            self._on_threat(event)

    async def start(self):
        if self._running:
            return
        self._running = True
        asyncio.create_task(self._monitor_loop())

    def stop(self):
        self._running = False

    def get_events(self, limit: int = 50) -> List[MonitorEvent]:
        return list(reversed(self._events[-limit:]))

    def get_stats(self) -> dict:
        return {
            "running": self._running,
            "watched_dirs": len(self._watched_dirs),
            "total_events": len(self._events),
            "threat_events": sum(
                1 for e in self._events
                if e.scan_result and e.scan_result.result == ScanResult.THREAT_FOUND
            ),
        }
