"""
UmerOS /etc Syslog Configuration
==================================
Manages system logging configuration.

FHS 3.0 entries:
  /etc/syslog.conf       — Syslog daemon configuration
  /etc/syslog.d/         — Syslog configuration directory
  /etc/rsyslog.conf      — Rsyslog configuration
  /etc/rsyslog.d/        — Rsyslog configuration directory

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Etc.SyslogConfig")


@dataclass
class SyslogRule:
    """Represents a syslog configuration rule."""
    facility: str
    priority: str
    action: str
    comments: List[str] = field(default_factory=list)


class SyslogConfigManager:
    """
    Manages system logging configuration.

    Handles /etc/syslog.conf, /etc/syslog.d/, /etc/rsyslog.conf,
    and /etc/rsyslog.d/.
    """

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.syslog_d_path = self.etc_path / "syslog.d"
        self.rsyslog_d_path = self.etc_path / "rsyslog.d"

    def initialize(self) -> bool:
        """Create all syslog configuration files with defaults."""
        try:
            self._create_syslog_conf()
            self._create_syslog_d()
            self._create_rsyslog_conf()
            self._create_rsyslog_d()
            log.info("Initialized syslog configuration files")
            return True
        except Exception as e:
            log.error("Failed to initialize syslog config: %s", e)
            return False

    # ── /etc/syslog.conf ─────────────────────────────────────────────────

    def _create_syslog_conf(self) -> None:
        """Create /etc/syslog.conf (syslog daemon configuration)."""
        filepath = self.etc_path / "syslog.conf"
        if filepath.exists():
            return
        content = """# /etc/syslog.conf - Syslog daemon configuration
# UmerOS Syslog Configuration
# See syslog.conf(5) for details.

# Log all kernel messages to /var/log/kern.log
kern.*                         /var/log/kern.log

# Log anything (except mail) of level info or higher
*.info;mail.none;authpriv.none;cron.none    /var/log/messages

# Log authentication messages
authpriv.*                     /var/log/auth.log

# Log cron messages
cron.*                         /var/log/cron.log

# Log mail messages
mail.*                         /var/log/mail.log

# Log emergency messages to all users
*.emerg                        *

# Log news errors
news.crit                      /var/log/news/news.crit
news.err                       /var/log/news/news.err
news.notice                    /var/log/news/news.notice

# Include additional configurations
$IncludeConfig /etc/syslog.d/*.conf
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/syslog.conf")

    # ── /etc/syslog.d/ ───────────────────────────────────────────────────

    def _create_syslog_d(self) -> None:
        """Create /etc/syslog.d/ directory with common configurations."""
        self.syslog_d_path.mkdir(parents=True, exist_ok=True)
        base = self.syslog_d_path / "base.conf"
        if not base.exists():
            content = """# /etc/syslog.d/base.conf
# Base syslog configuration

# Default logging
*.info;mail.none;authpriv.none;cron.none    /var/log/messages

# Authentication
authpriv.*                     /var/log/auth.log

# Cron
cron.*                         /var/log/cron.log

# Mail
mail.*                         /var/log/mail.log
"""
            base.write_text(content, encoding="utf-8")
            log.debug("Created /etc/syslog.d/base.conf")

    # ── /etc/rsyslog.conf ────────────────────────────────────────────────

    def _create_rsyslog_conf(self) -> None:
        """Create /etc/rsyslog.conf (Rsyslog configuration)."""
        filepath = self.etc_path / "rsyslog.conf"
        if filepath.exists():
            return
        content = """# /etc/rsyslog.conf - Rsyslog configuration
# UmerOS Rsyslog Configuration
# See rsyslog.conf(5) for details.

# Module loading
$ModLoad imuxsock
$ModLoad imklog

# Template for file logging
$ActionFileDefaultTemplate RSYSLOG_TraditionalFileFormat

# Log all kernel messages to /var/log/kern.log
kern.*                         /var/log/kern.log

# Log anything (except mail) of level info or higher
*.info;mail.none;authpriv.none;cron.none    /var/log/messages

# Log authentication messages
authpriv.*                     /var/log/auth.log

# Log cron messages
cron.*                         /var/log/cron.log

# Log mail messages
mail.*                         /var/log/mail.log

# Log emergency messages to all users
*.emerg                        :omusrmsg:*

# Log news errors
news.crit                      /var/log/news/news.crit
news.err                       /var/log/news/news.err
news.notice                    /var/log/news/news.notice

# Include additional configurations
$IncludeConfig /etc/rsyslog.d/*.conf

# Remote logging (uncomment to enable)
#*.* @@remote-host:514
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/rsyslog.conf")

    # ── /etc/rsyslog.d/ ──────────────────────────────────────────────────

    def _create_rsyslog_d(self) -> None:
        """Create /etc/rsyslog.d/ directory with common configurations."""
        self.rsyslog_d_path.mkdir(parents=True, exist_ok=True)
        base = self.rsyslog_d_path / "base.conf"
        if not base.exists():
            content = """# /etc/rsyslog.d/base.conf
# Base rsyslog configuration

# Default logging
*.info;mail.none;authpriv.none;cron.none    /var/log/messages

# Authentication
authpriv.*                     /var/log/auth.log

# Cron
cron.*                         /var/log/cron.log

# Mail
mail.*                         /var/log/mail.log

# Local messages
local0.*                       /var/log/local0.log
local1.*                       /var/log/local1.log
local2.*                       /var/log/local2.log
local3.*                       /var/log/local3.log
local4.*                       /var/log/local4.log
local5.*                       /var/log/local5.log
local6.*                       /var/log/local6.log
local7.*                       /var/log/local7.log
"""
            base.write_text(content, encoding="utf-8")
            log.debug("Created /etc/rsyslog.d/base.conf")

    # ── Utility Methods ──────────────────────────────────────────────────

    def parse_syslog_conf(self) -> List[SyslogRule]:
        """Parse /etc/syslog.conf into a list of rules."""
        filepath = self.etc_path / "syslog.conf"
        if not filepath.exists():
            return []
        rules = []
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("$"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                rules.append(SyslogRule(
                    facility=parts[0],
                    priority=parts[1] if len(parts) > 1 else "*",
                    action=" ".join(parts[2:]) if len(parts) > 2 else parts[-1],
                ))
        return rules

    def parse_rsyslog_conf(self) -> List[SyslogRule]:
        """Parse /etc/rsyslog.conf into a list of rules."""
        filepath = self.etc_path / "rsyslog.conf"
        if not filepath.exists():
            return []
        rules = []
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("$"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                rules.append(SyslogRule(
                    facility=parts[0],
                    priority=parts[1] if len(parts) > 1 else "*",
                    action=" ".join(parts[2:]) if len(parts) > 2 else parts[-1],
                ))
        return rules

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of syslog configuration."""
        return {
            "syslog_conf_exists": (self.etc_path / "syslog.conf").exists(),
            "syslog_d_exists": self.syslog_d_path.exists(),
            "rsyslog_conf_exists": (self.etc_path / "rsyslog.conf").exists(),
            "rsyslog_d_exists": self.rsyslog_d_path.exists(),
        }
