"""Main antivirus engine orchestrating all components."""

import asyncio
import os
from typing import Callable, List, Optional

from .heuristics import HeuristicAnalyzer
from .quarantine import QuarantineManager
from .realtime import RealtimeMonitor
from .scanner import FileScanner, ScanReport, ScanResult, ScanStats
from .signatures import SignatureDatabase, ThreatLevel


class AntivirusEngine:
    """Unified antivirus engine combining signatures, heuristics, quarantine, and real-time monitoring."""

    def __init__(self, db_path: Optional[str] = None, quarantine_dir: Optional[str] = None):
        self.db = SignatureDatabase(db_path)
        self.heuristic = HeuristicAnalyzer()
        self.scanner = FileScanner(self.db, self.heuristic)
        self.quarantine = QuarantineManager(quarantine_dir)
        self.realtime = RealtimeMonitor(self.scanner)
        self._threat_callback: Optional[Callable] = None

    def set_threat_callback(self, callback: Callable):
        self._threat_callback = callback
        self.realtime.set_threat_callback(self._on_threat_detected)

    def _on_threat_detected(self, event):
        if self._threat_callback:
            self._threat_callback(event)

    def scan_file(self, file_path: str) -> ScanReport:
        return self.scanner.scan_file(file_path)

    async def scan_directory(
        self,
        dir_path: str,
        on_progress: Optional[Callable[[ScanReport], None]] = None,
    ) -> tuple[List[ScanReport], ScanStats]:
        return await self.scanner.scan_directory(dir_path, on_progress)

    def quarantine_threat(self, report: ScanReport):
        if report.result == ScanResult.THREAT_FOUND:
            return self.quarantine.quarantine_file(
                file_path=report.file_path,
                threat_name=report.threat_name or "Unknown",
                threat_level=report.threat_level.value if report.threat_level else "medium",
                detection_method=report.detection_method,
                md5=report.md5,
                sha256=report.sha256,
            )
        return None

    def restore_quarantined(self, entry_id: str) -> bool:
        return self.quarantine.restore_file(entry_id)

    def delete_quarantined(self, entry_id: str) -> bool:
        return self.quarantine.delete_quarantined(entry_id)

    def add_watch(self, dir_path: str) -> bool:
        return self.realtime.add_watch(dir_path)

    def remove_watch(self, dir_path: str) -> bool:
        return self.realtime.remove_watch(dir_path)

    async def start_realtime(self):
        await self.realtime.start()

    def stop_realtime(self):
        self.realtime.stop()

    def cancel_scan(self):
        self.scanner.cancel_scan()

    def get_dashboard(self) -> dict:
        sig_stats = self.db.get_stats()
        quarantine_stats = self.quarantine.get_stats()
        realtime_stats = self.realtime.get_stats()
        return {
            "engine_status": "active",
            "signatures": sig_stats,
            "quarantine": quarantine_stats,
            "realtime": realtime_stats,
            "realtime_running": self.realtime.is_running,
            "scanning": self.scanner.is_scanning,
        }

    def get_quarantine_list(self) -> list:
        return [e.to_dict() for e in self.quarantine.list_entries()]

    def get_realtime_events(self, limit: int = 50) -> list:
        return [e.to_dict() for e in self.realtime.get_events(limit)]

    def get_watched_dirs(self) -> list:
        return self.realtime.watched_dirs
