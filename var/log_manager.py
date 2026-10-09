"""
UmerOS /var Log Management
============================
Manages system logs in /var/log.

FHS 3.0:
  /var/log/       — Log files
  /var/log/syslog — System log
  /var/log/auth.log — Authentication log
  /var/log/dmesg  — Kernel ring buffer log

Author:  Umer OS Project
License: GPL-3.0
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# [FIX H303] Guard against directory-traversal / arbitrary-append (CWE-22).
from ._path_guard import safe_child, PathTraversalError

# [FIX H304] Gate privileged /var/log filesystem mutation behind the zero-trust
# capability bridge. Writing log entries, rotating, and compressing old logs are
# privileged operations that must require the `fs.admin` capability when a
# CapabilityManager is wired (fail-closed); when no manager is wired the gate
# stays permissive (warning) so existing flows keep working.
try:
    from core.capability_gate import gate, CAP_FS_ADMIN
except Exception:  # pragma: no cover - standalone fallback
    import sys
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.capability_gate import gate, CAP_FS_ADMIN

log = logging.getLogger("UmerOS.Var.LogManager")


@dataclass
class LogEntry:
    """Represents a log entry."""
    timestamp: str
    facility: str
    severity: str
    message: str
    source: Optional[str] = None


class LogManager:
    """
    Manages log files in /var/log.

    Handles syslog, auth.log, dmesg, and general log management.
    """

    LOG_LEVELS = {
        "emerg": 0, "alert": 1, "crit": 2, "err": 3,
        "warning": 4, "notice": 5, "info": 6, "debug": 7,
    }

    def __init__(self, var_path: str = "/var"):
        self.var_path = Path(var_path)
        self.log_path = self.var_path / "log"

    # ── Log Writing ────────────────────────────────────────────────────

    def write_log(self, filename: str, message: str, level: str = "info",
                  facility: str = "user") -> bool:
        """Write an entry to a log file.

        SECURITY (H303): ``filename`` is now contained to /var/log. Previously
        ``write_log("../../etc/cron.d/x", payload)`` allowed arbitrary file
        append outside the log directory. The guard refuses such attempts.
        """
        # [FIX H304] privileged FHS append -> requires fs.admin when wired.
        gate.require(CAP_FS_ADMIN)
        try:
            # [FIX H303] contain the caller-supplied filename inside /var/log.
            log_file = safe_child(self.log_path, filename)
        except PathTraversalError as e:
            log.error("Refused path-traversal in write_log: %s", e)
            return False
        timestamp = datetime.now().strftime("%b %d %H:%M:%S")
        # [FIX] The ``level`` argument was accepted but never
        # persisted, so entries could not be filtered by severity.
        level = self._normalize_level(level)
        entry = f"{timestamp} {facility}[{os.getpid()}] {level}: {message}"
        try:
            # Ensure the log directory exists (robustness: write_log must not
            # fail merely because /var/log was not pre-created).
            self.log_path.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(entry + "\n")
            return True
        except Exception as e:
            log.error("Failed to write log: %s", e)
            return False

    def write_syslog(self, message: str, level: str = "info",
                     facility: str = "user") -> bool:
        """Write to /var/log/syslog."""
        return self.write_log("syslog", message, level, facility)

    def write_auth_log(self, message: str, level: str = "info") -> bool:
        """Write to /var/log/auth.log."""
        return self.write_log("auth.log", message, level, "auth")

    # ── Log Reading ────────────────────────────────────────────────────

    def read_log(self, filename: str, lines: int = 100) -> List[str]:
        """Read the last N lines from a log file."""
        try:
            # [FIX H303] contain the caller-supplied filename inside /var/log.
            log_file = safe_child(self.log_path, filename)
        except PathTraversalError as e:
            log.error("Refused path-traversal in read_log: %s", e)
            return []
        if not log_file.exists():
            return []
        try:
            content = log_file.read_text(encoding="utf-8")
            all_lines = content.splitlines()
            return all_lines[-lines:]
        except Exception as e:
            log.error("Failed to read log: %s", e)
            return []

    def read_syslog(self, lines: int = 100) -> List[str]:
        """Read from /var/log/syslog."""
        return self.read_log("syslog", lines)

    # Format written by ``write_log``:
    #   "MMM DD HH:MM:SS facility[pid] level: message"
    _LOG_LINE_RE = re.compile(
        r"^(?P<ts>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
        r"(?P<facility>[^\s\[]+)\[(?P<pid>\d+)\]\s+"
        r"(?P<level>[A-Za-z]+):\s(?P<message>.*)$"
    )

    @classmethod
    def _normalize_level(cls, level: str) -> str:
        """Map a level name onto the canonical syslog level names."""
        if not level:
            return "info"
        low = str(level).lower()
        return low if low in cls.LOG_LEVELS else "info"

    def parse_log_entry(self, line: str) -> Optional[LogEntry]:
        """Parse a line written by ``write_log`` (round-trips level)."""
        match = self._LOG_LINE_RE.match(line.strip())
        if match:
            return LogEntry(
                timestamp=match.group("ts"),
                facility=match.group("facility"),
                severity=match.group("level").lower(),
                message=match.group("message"),
            )
        # Fallback: tolerate the legacy "facility[pid]: message" layout.
        parts = line.split(":", 1)
        if len(parts) != 2:
            return None
        timestamp_part = parts[0].strip()
        message_part = parts[1].strip()
        # Try to extract facility from message
        facility = "user"
        severity = "info"
        if "[" in message_part:
            fac_sev = message_part.split("[")[0]
            if "." in fac_sev:
                facility, severity = fac_sev.split(".", 1)
            else:
                facility = fac_sev
        return LogEntry(
            timestamp=timestamp_part,
            facility=facility,
            severity=severity,
            message=message_part,
        )

    # ── Log Rotation ───────────────────────────────────────────────────

    def rotate_log(self, filename: str, max_size: int = 10 * 1024 * 1024) -> bool:
        """Rotate a log file if it exceeds max_size."""
        # [FIX H304] privileged FHS rename -> requires fs.admin when wired.
        gate.require(CAP_FS_ADMIN)
        try:
            # [FIX H303] contain the caller-supplied filename inside /var/log.
            log_file = safe_child(self.log_path, filename)
        except PathTraversalError as e:
            log.error("Refused path-traversal in rotate_log: %s", e)
            return False
        if not log_file.exists():
            return False
        if log_file.stat().st_size < max_size:
            return True
        rotated = log_file.with_suffix(f".{int(time.time())}.log")
        try:
            log_file.rename(rotated)
            log_file.touch()
            log.info("Rotated %s to %s", filename, rotated.name)
            return True
        except Exception as e:
            log.error("Failed to rotate log: %s", e)
            return False

    # Rotated logs are named "<stem>.<unix-ts>.log" by ``rotate_log``.
    _ROTATED_RE = re.compile(r"\.\d+\.log$")

    def compress_old_logs(self) -> List[str]:
        """Compress old rotated log files (never the active log)."""
        # [FIX H304] privileged FHS delete -> requires fs.admin when wired.
        gate.require(CAP_FS_ADMIN)
        compressed = []
        for log_file in self.log_path.glob("*.log"):
            if log_file.name == "syslog" or log_file.name == "auth.log":
                continue
            # [FIX] The previous ``"." in name`` check matched every
            # "*.log" file — including the *active* log — so
            # "compressing old logs" deleted the live log file.
            # Only rotate-stamped files are old enough to compress.
            if not self._ROTATED_RE.search(log_file.name):
                continue
                try:
                    import gzip
                    with open(log_file, "rb") as f_in:
                        with gzip.open(str(log_file) + ".gz", "wb") as f_out:
                            f_out.write(f_in.read())
                    log_file.unlink()
                    compressed.append(log_file.name)
                except Exception as e:
                    log.error("Failed to compress %s: %s", log_file.name, e)
        return compressed

    # ── Log Analysis ───────────────────────────────────────────────────

    def get_log_stats(self, filename: str) -> Dict:
        """Get statistics for a log file."""
        try:
            # [FIX H303] contain the caller-supplied filename inside /var/log.
            log_file = safe_child(self.log_path, filename)
        except PathTraversalError as e:
            log.error("Refused path-traversal in get_log_stats: %s", e)
            return {"exists": False}
        if not log_file.exists():
            return {"exists": False}
        # [FIX] Count lines directly: read_log(..., lines=10000) capped
        # total_lines at 10000 for logs larger than the read window.
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                total_lines = sum(1 for _ in f)
        except Exception as e:
            log.error("Failed to count lines in %s: %s", filename, e)
            total_lines = 0
        return {
            "exists": True,
            "total_lines": total_lines,
            "file_size": log_file.stat().st_size,
            "last_modified": datetime.fromtimestamp(log_file.stat().st_mtime).isoformat(),
        }

    def search_logs(self, filename: str, pattern: str, max_results: int = 100) -> List[str]:
        """Search for pattern in a log file."""
        results = []
        try:
            # [FIX H303] contain the caller-supplied filename inside /var/log.
            log_file = safe_child(self.log_path, filename)
        except PathTraversalError as e:
            log.error("Refused path-traversal in search_logs: %s", e)
            return []
        if not log_file.exists():
            return []
        for line in log_file.read_text(encoding="utf-8").splitlines():
            if pattern.lower() in line.lower():
                results.append(line)
                if len(results) >= max_results:
                    break
        return results

    def get_summary(self) -> Dict:
        """Get summary of /var/log contents."""
        log_files = []
        if self.log_path.exists():
            for f in self.log_path.iterdir():
                if f.is_file():
                    log_files.append(f.name)
        return {
            "log_directory": str(self.log_path),
            "total_log_files": len(log_files),
            "log_files": log_files,
        }
