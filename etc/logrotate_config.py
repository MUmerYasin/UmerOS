"""
UmerOS /etc Log Rotation Configuration
========================================
Manages log rotation configuration and policies.

FHS 3.0 entries:
  /etc/logrotate.conf        — Log rotation main configuration
  /etc/logrotate.d/          — Log rotation per-package configurations
  /etc/logrotate.conf.d/     — Additional log rotation configurations

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Etc.LogrotateConfig")


@dataclass
class LogrotateEntry:
    """Represents a log rotation configuration entry."""
    log_path: str
    options: Dict[str, str] = field(default_factory=dict)
    postrotate: str = ""
    prerotate: str = ""
    comments: List[str] = field(default_factory=list)


class LogrotateConfigManager:
    """
    Manages log rotation configuration.

    Handles /etc/logrotate.conf and /etc/logrotate.d/.
    """

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.logrotate_d_path = self.etc_path / "logrotate.d"
        self.logrotate_conf_d_path = self.etc_path / "logrotate.conf.d"

    def initialize(self) -> bool:
        """Create all log rotation configuration files with defaults."""
        try:
            self._create_logrotate_conf()
            self._create_logrotate_d_files()
            self._create_logrotate_conf_d()
            log.info("Initialized log rotation configuration files")
            return True
        except Exception as e:
            log.error("Failed to initialize logrotate config: %s", e)
            return False

    # ── /etc/logrotate.conf ──────────────────────────────────────────────

    def _create_logrotate_conf(self) -> None:
        """Create /etc/logrotate.conf (main log rotation configuration)."""
        filepath = self.etc_path / "logrotate.conf"
        if filepath.exists():
            return
        content = """# /etc/logrotate.conf - Log rotation main configuration
# UmerOS Log Rotation Configuration
# See logrotate(8) for details.

# Default settings
daily
rotate 7
create
compress
delaycompress
missingok
notifempty

# Include per-package configurations
include /etc/logrotate.d

# Include additional configurations
include /etc/logrotate.conf.d

# System log rotation
/var/log/syslog {
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    postrotate
        /usr/bin/systemctl reload rsyslog > /dev/null 2>&1 || true
    endscript
}

/var/log/auth.log {
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    postrotate
        /usr/bin/systemctl reload rsyslog > /dev/null 2>&1 || true
    endscript
}

/var/log/kern.log {
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    postrotate
        /usr/bin/systemctl reload rsyslog > /dev/null 2>&1 || true
    endscript
}

/var/log/dmesg {
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    postrotate
        /usr/bin/systemctl reload rsyslog > /dev/null 2>&1 || true
    endscript
}

# Application logs
/var/log/*.log {
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root adm
}

# Temporary files
/tmp/* {
    daily
    rotate 0
    missingok
    notifempty
}
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/logrotate.conf")

    # ── /etc/logrotate.d/ ────────────────────────────────────────────────

    def _create_logrotate_d_files(self) -> None:
        """Create /etc/logrotate.d/ directory with common configurations."""
        self.logrotate_d_path.mkdir(parents=True, exist_ok=True)

        configs = {
            "apt": """# /etc/logrotate.d/apt - APT log rotation
/var/log/apt/term.log {
    rotate 12
    monthly
    compress
    missingok
    notifempty
}

/var/log/apt/history.log {
    rotate 12
    monthly
    compress
    missingok
    notifempty
}
""",
            "dpkg": """# /etc/logrotate.d/dpkg - DPKG log rotation
/var/log/dpkg.log {
    monthly
    rotate 4
    compress
    missingok
    notifempty
}

/var/log/dpkg.log.*.gz {
    monthly
    rotate 4
    compress
    missingok
    notifempty
}
""",
            "cron": """# /etc/logrotate.d/cron - Cron log rotation
/var/log/cron {
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    postrotate
        /usr/bin/systemctl reload rsyslog > /dev/null 2>&1 || true
    endscript
}
""",
            "maillog": """# /etc/logrotate.d/maillog - Mail log rotation
/var/log/maillog {
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    postrotate
        /usr/bin/systemctl reload rsyslog > /dev/null 2>&1 || true
    endscript
}
""",
            "sshd": """# /etc/logrotate.d/sshd - SSH log rotation
/var/log/auth.log {
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    postrotate
        /usr/bin/systemctl reload rsyslog > /dev/null 2>&1 || true
    endscript
}
""",
        }

        for filename, content in configs.items():
            filepath = self.logrotate_d_path / filename
            if not filepath.exists():
                filepath.write_text(content, encoding="utf-8")
                log.debug("Created /etc/logrotate.d/%s", filename)

    # ── /etc/logrotate.conf.d/ ───────────────────────────────────────────

    def _create_logrotate_conf_d(self) -> None:
        """Create /etc/logrotate.conf.d/ directory with base configuration."""
        self.logrotate_conf_d_path.mkdir(parents=True, exist_ok=True)
        base = self.logrotate_conf_d_path / "base.conf"
        if not base.exists():
            content = """# /etc/logrotate.conf.d/base.conf
# Base log rotation settings
# These settings apply to all logs unless overridden

# Default rotation settings
daily
rotate 7
create
compress
delaycompress
missingok
notifempty
"""
            base.write_text(content, encoding="utf-8")
            log.debug("Created /etc/logrotate.conf.d/base.conf")

    # ── Utility Methods ──────────────────────────────────────────────────

    def parse_logrotate_conf(self) -> List[LogrotateEntry]:
        """Parse /etc/logrotate.conf into a list of entries."""
        filepath = self.etc_path / "logrotate.conf"
        if not filepath.exists():
            return []
        entries = []
        current_entry = None
        in_block = False
        block_content = []
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "{" in line and "}" not in line:
                # Start of a block
                log_path = line.split("{")[0].strip()
                current_entry = LogrotateEntry(log_path=log_path)
                in_block = True
                block_content = []
            elif "}" in line:
                # End of a block
                if current_entry:
                    entries.append(current_entry)
                    current_entry = None
                in_block = False
            elif in_block:
                block_content.append(line)
            elif not in_block:
                # Global directive
                parts = line.split()
                if len(parts) >= 2:
                    entries.append(LogrotateEntry(
                        log_path="global",
                        options={parts[0]: " ".join(parts[1:])}
                    ))
        return entries

    def list_logrotate_d_configs(self) -> List[str]:
        """List configurations in /etc/logrotate.d/."""
        if not self.logrotate_d_path.exists():
            return []
        return [f.name for f in self.logrotate_d_path.iterdir() if f.is_file()]

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of log rotation configuration."""
        return {
            "logrotate_conf_exists": (self.etc_path / "logrotate.conf").exists(),
            "logrotate_d_exists": self.logrotate_d_path.exists(),
            "logrotate_d_configs": self.list_logrotate_d_configs(),
            "logrotate_conf_d_exists": self.logrotate_conf_d_path.exists(),
        }
