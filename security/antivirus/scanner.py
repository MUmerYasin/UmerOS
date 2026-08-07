"""File and directory scanning engine."""

import asyncio
import hashlib
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

from .heuristics import HeuristicAnalyzer, HeuristicVerdict
from .signatures import Signature, SignatureDatabase, ThreatLevel


class ScanResult(Enum):
    CLEAN = "clean"
    THREAT_FOUND = "threat_found"
    SUSPICIOUS = "suspicious"
    ERROR = "error"


@dataclass
class ScanReport:
    file_path: str
    result: ScanResult
    threat_name: Optional[str] = None
    threat_level: Optional[ThreatLevel] = None
    detection_method: str = ""  # signature, heuristic, or both
    scan_time_ms: float = 0.0
    file_size: int = 0
    md5: str = ""
    sha256: str = ""
    heuristic_score: float = 0.0
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "result": self.result.value,
            "threat_name": self.threat_name,
            "threat_level": self.threat_level.value if self.threat_level else None,
            "detection_method": self.detection_method,
            "scan_time_ms": round(self.scan_time_ms, 2),
            "file_size": self.file_size,
            "md5": self.md5,
            "sha256": self.sha256,
            "heuristic_score": self.heuristic_score,
            "details": self.details,
        }


@dataclass
class ScanStats:
    total_files: int = 0
    clean: int = 0
    threats: int = 0
    suspicious: int = 0
    errors: int = 0
    total_size_bytes: int = 0
    scan_duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_files": self.total_files,
            "clean": self.clean,
            "threats": self.threats,
            "suspicious": self.suspicious,
            "errors": self.errors,
            "total_size_bytes": self.total_size_bytes,
            "scan_duration_ms": round(self.scan_duration_ms, 2),
        }


SCAN_EXTENSIONS = {
    ".exe", ".dll", ".sys", ".drv", ".scr", ".com", ".pif", ".bat", ".cmd",
    ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".ps1", ".psm1",
    ".msi", ".msp", ".mst", ".cpl", ".lnk", ".inf", ".reg",
    ".doc", ".docm", ".xls", ".xlsm", ".ppt", ".pptm",
    ".pdf", ".zip", ".rar", ".7z", ".tar", ".gz",
    ".jar", ".class", ".py", ".rb", ".pl", ".sh",
    ".apk", ".ipa",
}


class FileScanner:
    def __init__(self, db: SignatureDatabase, heuristic: Optional[HeuristicAnalyzer] = None):
        self.db = db
        self.heuristic = heuristic or HeuristicAnalyzer()
        self._scanning = False
        self._cancel = False

    @property
    def is_scanning(self) -> bool:
        return self._scanning

    def cancel_scan(self):
        self._cancel = True

    def scan_file(self, file_path: str) -> ScanReport:
        start = time.perf_counter()
        report = ScanReport(file_path=file_path, result=ScanResult.CLEAN)

        try:
            stat = os.stat(file_path)
            report.file_size = stat.st_size
        except OSError as e:
            report.result = ScanResult.ERROR
            report.details = str(e)
            return report

        # Hash the file
        try:
            report.md5, report.sha256 = self._hash_file(file_path)
        except Exception as e:
            report.result = ScanResult.ERROR
            report.details = f"Hash error: {e}"
            return report

        # Signature lookup
        sig_match = self.db.lookup_hash(report.sha256) or self.db.lookup_hash(report.md5)
        if sig_match:
            report.result = ScanResult.THREAT_FOUND
            report.threat_name = sig_match.name
            report.threat_level = sig_match.threat_level
            report.detection_method = "signature"
            report.scan_time_ms = (time.perf_counter() - start) * 1000
            return report

        # Heuristic analysis
        h_result = self.heuristic.analyze(file_path)
        report.heuristic_score = h_result.score
        if h_result.verdict == HeuristicVerdict.MALICIOUS:
            report.result = ScanResult.THREAT_FOUND
            report.threat_name = f"Heuristic-Malicious-{os.path.basename(file_path)}"
            report.threat_level = ThreatLevel.HIGH
            report.detection_method = "heuristic"
            report.details = "; ".join(h_result.reasons)
        elif h_result.verdict == HeuristicVerdict.SUSPICIOUS:
            report.result = ScanResult.SUSPICIOUS
            report.threat_name = f"Heuristic-Suspicious-{os.path.basename(file_path)}"
            report.threat_level = ThreatLevel.MEDIUM
            report.detection_method = "heuristic"
            report.details = "; ".join(h_result.reasons)

        report.scan_time_ms = (time.perf_counter() - start) * 1000
        return report

    async def scan_directory(
        self,
        dir_path: str,
        on_progress: Optional[Callable[[ScanReport], None]] = None,
    ) -> tuple[List[ScanReport], ScanStats]:
        self._scanning = True
        self._cancel = False
        stats = ScanStats()
        reports = []
        start = time.perf_counter()

        files = []
        for root, _, filenames in os.walk(dir_path):
            for fn in filenames:
                fp = os.path.join(root, fn)
                ext = os.path.splitext(fn)[1].lower()
                if ext in SCAN_EXTENSIONS or not ext:
                    files.append(fp)

        stats.total_files = len(files)

        for fp in files:
            if self._cancel:
                break
            report = await asyncio.get_event_loop().run_in_executor(
                None, self.scan_file, fp
            )
            reports.append(report)
            stats.total_size_bytes += report.file_size

            if report.result == ScanResult.THREAT_FOUND:
                stats.threats += 1
            elif report.result == ScanResult.SUSPICIOUS:
                stats.suspicious += 1
            elif report.result == ScanResult.ERROR:
                stats.errors += 1
            else:
                stats.clean += 1

            if on_progress:
                on_progress(report)

        stats.scan_duration_ms = (time.perf_counter() - start) * 1000
        self._scanning = False
        return reports, stats

    def _hash_file(self, file_path: str) -> tuple[str, str]:
        md5 = hashlib.md5()
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                md5.update(chunk)
                sha256.update(chunk)
        return md5.hexdigest(), sha256.hexdigest()
