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
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

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
        """Write an entry to a log file."""
        log_file = self.log_path / filename
        timestamp = datetime.now().strftime("%b %d %H:%M:%S")
        entry = f"{timestamp} {facility}[{os.getpid()}]: {message}"
        try:
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
        log_file = self.log_path / filename
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

    def parse_log_entry(self, line: str) -> Optional[LogEntry]:
        """Parse a syslog-format line."""
        # Format: "MMM DD HH:MM:SS facility[pid]: message"
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
        log_file = self.log_path / filename
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

    def compress_old_logs(self) -> List[str]:
        """Compress old rotated log files."""
        compressed = []
        for log_file in self.log_path.glob("*.log"):
            if log_file.name == "syslog" or log_file.name == "auth.log":
                continue
            if "." in log_file.name:
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
        log_file = self.log_path / filename
        if not log_file.exists():
            return {"exists": False}
        lines = self.read_log(filename, lines=10000)
        return {
            "exists": True,
            "total_lines": len(lines),
            "file_size": log_file.stat().st_size,
            "last_modified": datetime.fromtimestamp(log_file.stat().st_mtime).isoformat(),
        }

    def search_logs(self, filename: str, pattern: str, max_results: int = 100) -> List[str]:
        """Search for pattern in a log file."""
        results = []
        log_file = self.log_path / filename
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
