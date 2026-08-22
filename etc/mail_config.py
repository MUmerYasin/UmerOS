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
UmerOS /etc Mail Configuration
================================
Manages mail system configuration files.

FHS 3.0 entries:
  /etc/mail.rc          — Mail user agent configuration
  /etc/mailname         — System mail name
  /etc/postfix/         — Postfix MTA configuration directory
  /etc/postfix/main.cf  — Postfix main configuration
  /etc/postfix/master.cf — Postfix master configuration
  /etc/aliases          — Mail aliases
  /etc/aliases.db       — Compiled mail aliases database

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Etc.MailConfig")


@dataclass
class MailAlias:
    """Represents a mail alias."""
    name: str
    target: str
    comments: List[str] = field(default_factory=list)


class MailConfigManager:
    """
    Manages mail system configuration.

    Handles /etc/mail.rc, /etc/mailname, /etc/postfix/,
    and /etc/aliases.
    """

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.postfix_path = self.etc_path / "postfix"

    def initialize(self) -> bool:
        """Create all mail configuration files with defaults."""
        try:
            self._create_mail_rc()
            self._create_mailname()
            self._create_aliases()
            self._create_postfix()
            log.info("Initialized mail configuration files")
            return True
        except Exception as e:
            log.error("Failed to initialize mail config: %s", e)
            return False

    # ── /etc/mail.rc ─────────────────────────────────────────────────────

    def _create_mail_rc(self) -> None:
        """Create /etc/mail.rc (Mail user agent configuration)."""
        filepath = self.etc_path / "mail.rc"
        if filepath.exists():
            return
        content = """# /etc/mail.rc - Mail user agent configuration
# UmerOS Mail Configuration
# See mail(1) for details.

# Default editor
set EDITOR=vi

# Set output character set
set characterset=UTF-8

# Set terminal type
set TERM=xterm

# Reply-to address
#set replyto=user@example.com

# Set mail header format
set header

# Set bell on
set bell

# Ignore some messages
set ignore="Received: by: Return-Path:"

# Set mailbox location
set MBOX=/var/mail/$LOGNAME

# Set record file
set RECORD=~/mail/dead.letter

# Set saved message folder
set SENT=~/mail/sent

# Set message folder
set MBOX=~/mail/mbox
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/mail.rc")

    # ── /etc/mailname ────────────────────────────────────────────────────

    def _create_mailname(self) -> None:
        """Create /etc/mailname (system mail name)."""
        filepath = self.etc_path / "mailname"
        if filepath.exists():
            return
        filepath.write_text("localhost\n", encoding="utf-8")
        log.debug("Created /etc/mailname")

    # ── /etc/aliases ─────────────────────────────────────────────────────

    def _create_aliases(self) -> None:
        """Create /etc/aliases (mail aliases)."""
        filepath = self.etc_path / "aliases"
        if filepath.exists():
            return
        content = """# /etc/aliases - Mail aliases
# UmerOS Mail Aliases Configuration
# See aliases(5) for details.
#
# Format:
#   name: recipient1, recipient2, ...
#
# After modifying, run: newaliases

# System aliases
mailer-daemon: postmaster
postmaster: root
nobody: root
hostmaster: root
usenet: root
news: root
webmaster: root
www: root
ftp: root
abuse: root
noc: root
security: root

# User aliases
#user1: realuser1
#user2: realuser2

# Mailing lists
#listname: member1, member2, member3

# Forward to file
#spam: /dev/null
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/aliases")

    # ── /etc/postfix/ ────────────────────────────────────────────────────

    def _create_postfix(self) -> None:
        """Create /etc/postfix/ directory with main configuration files."""
        self.postfix_path.mkdir(parents=True, exist_ok=True)
        self._create_postfix_main_cf()
        self._create_postfix_master_cf()

    def _create_postfix_main_cf(self) -> None:
        """Create /etc/postfix/main.cf (Postfix main configuration)."""
        filepath = self.postfix_path / "main.cf"
        if filepath.exists():
            return
        content = """# /etc/postfix/main.cf - Postfix main configuration
# UmerOS Postfix Configuration
# See postconf(5) for details.

# General
smtpd_banner = $myhostname ESMTP $mail_name
biff = no
append_dot_mydomain = no
readme_directory = no

# Hostname
myhostname = localhost
mydomain = localhost
myorigin = $myhostname
mydestination = $myhostname, localhost.$mydomain, localhost
mynetworks = 127.0.0.0/8 [::ffff:127.0.0.0]/104 [::1]/128

# Mail storage
home_mailbox = Maildir/
mailbox_command =

# Relay
relayhost =
relay_domains =

# Security
smtpd_recipient_restrictions = permit_mynetworks, reject_unauth_destination
smtpd_relay_restrictions = permit_mynetworks, permit_sasl_authenticated, reject_unauth_destination

# TLS
#smtpd_tls_cert_file = /etc/ssl/certs/ssl-cert-snakeoil.pem
#smtpd_tls_key_file = /etc/ssl/private/ssl-cert-snakeoil.key
#smtpd_use_tls = yes
#smtpd_tls_auth_only = yes

# SASL
#smtpd_sasl_auth_enable = yes
#smtpd_sasl_security_options = noanonymous
#smtpd_sasl_tls_security_options = noanonymous

# Timeouts
smtp_helo_timeout = 60s
smtp_mail_timeout = 60s
smtp_rcpt_timeout = 60s

# Size
message_size_limit = 10485760
mailbox_size_limit = 0

# Deferred
maximal_queue_lifetime = 1d
bounce_queue_lifetime = 1d
maximal_backoff_time = 4000s
minimal_backoff_time = 300s
queue_run_delay = 300s

# Virtual
virtual_alias_domains =
virtual_alias_maps = proxy:hash:/etc/aliases
virtual_mailbox_domains = proxy:hash:/etc/postfix/vdomains
virtual_mailbox_maps = proxy:hash:/etc/postfix/vmailbox
virtual_mailbox_base = /var/vmail
virtual_uid_maps = static:5000
virtual_gid_maps = static:5000
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/postfix/main.cf")

    def _create_postfix_master_cf(self) -> None:
        """Create /etc/postfix/master.cf (Postfix master configuration)."""
        filepath = self.postfix_path / "master.cf"
        if filepath.exists():
            return
        content = """# /etc/postfix/master.cf - Postfix master configuration
# UmerOS Postfix Master Configuration
# See master(5) for details.
#
# service type private unpriv  chroot  wakeup  maxproc command + args

# Inbound SMTP
smtp      inet  n       -       y       -       -       smtpd

# Submission (uncomment to enable)
#submission inet n       -       y       -       -       smtpd
#  -o syslog_name=postfix/submission
#  -o smtpd_tls_security_level=encrypt
#  -o smtpd_sasl_auth_enable=yes

# SMTPS (uncomment to enable)
#smtps     inet  n       -       y       -       -       smtpd
#  -o syslog_name=postfix/smtps
#  -o smtpd_tls_wrappermode=yes
#  -o smtpd_sasl_auth_enable=yes

# Pickup service
pickup    unix  n       -       y       60      1       pickup

# Cleanup service
cleanup   unix  n       -       y       -       0       cleanup

# Queue manager
qmgr      unix  n       -       n       300     1       qmgr

# Bounce service
bounce    unix  -       -       y       -       0       bounce

# Deferred queue
defer     unix  -       -       y       -       0       bounce

# Trace service
trace     unix  -       -       y       -       0       bounce

# Verify service
verify    unix  -       -       y       -       1       verify

# Sendmail
sendmail  unix  -       n       y       -       -       flags=Ru user=mail argv=/usr/sbin/sendmail -oi -f ${sender} ${recipient}

# SMTP client
smtp      unix  -       -       y       -       -       smtp
  -o smtp_connect_timeout=30

# Relay
relay     unix  -       -       y       -       -       smtp
  -o smtp_connect_timeout=30
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/postfix/master.cf")

    # ── Utility Methods ──────────────────────────────────────────────────

    def parse_aliases(self) -> List[MailAlias]:
        """Parse /etc/aliases into a list of aliases."""
        filepath = self.etc_path / "aliases"
        if not filepath.exists():
            return []
        aliases = []
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                name, target = line.split(":", 1)
                aliases.append(MailAlias(
                    name=name.strip(),
                    target=target.strip(),
                ))
        return aliases

    def parse_mailname(self) -> str:
        """Parse /etc/mailname and return the mail name."""
        filepath = self.etc_path / "mailname"
        if not filepath.exists():
            return "localhost"
        return filepath.read_text(encoding="utf-8").strip()

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of mail configuration."""
        return {
            "mail_rc_exists": (self.etc_path / "mail.rc").exists(),
            "mailname_exists": (self.etc_path / "mailname").exists(),
            "aliases_exists": (self.etc_path / "aliases").exists(),
            "postfix_exists": self.postfix_path.exists(),
            "main_cf_exists": (self.postfix_path / "main.cf").exists(),
            "master_cf_exists": (self.postfix_path / "master.cf").exists(),
        }
