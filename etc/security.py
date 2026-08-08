"""
UmerOS /etc Security Configuration
====================================
Manages security-related configuration files.

FHS 3.0 entries:
  /etc/security/                  — Security configuration directory
  /etc/security/access.conf       — Login access control
  /etc/security/limits.conf       — Resource limits
  /etc/security/namespace.conf    — Namespace configuration
  /etc/security/pam_env.conf      — PAM environment variables
  /etc/security/sepermit.conf     — SELinux context mapping
  /etc/security/time.conf         — Time-based access control

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger("UmerOS.Etc.SecurityConfig")


class SecurityConfigManager:
    """Manages /etc/security/ configuration files."""

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.security_path = self.etc_path / "security"

    def initialize(self) -> bool:
        try:
            self.security_path.mkdir(parents=True, exist_ok=True)
            self._create_access_conf()
            self._create_limits_conf()
            self._create_namespace_conf()
            self._create_pam_env_conf()
            self._create_time_conf()
            self._create_sepermit_conf()
            log.info("Initialized /etc/security/")
            return True
        except Exception as e:
            log.error("Failed to initialize security config: %s", e)
            return False

    def _create_access_conf(self) -> None:
        fp = self.security_path / "access.conf"
        if fp.exists():
            return
        fp.write_text(
            "# /etc/security/access.conf - Login access control tables\n"
            "# UmerOS Access Control Configuration\n"
            "# See access.conf(5) for details.\n\n"
            "# Format: permission : users : origins\n\n"
            "# Allow root only from console\n"
            "+ : root : LOCAL\n\n"
            "# Allow all users locally\n"
            "+ : ALL : LOCAL\n\n"
            "# Deny remote root login\n"
            "- : root : ALL\n\n"
            "# Allow users in group 'wheel' to su\n"
            "+ : wheel : ALL\n\n"
            "# Default: deny all\n"
            "- : ALL : ALL\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/security/access.conf")

    def _create_limits_conf(self) -> None:
        fp = self.security_path / "limits.conf"
        if fp.exists():
            return
        fp.write_text(
            "# /etc/security/limits.conf - Resource limits\n"
            "# UmerOS Limits Configuration\n"
            "# See limits.conf(5) for details.\n\n"
            "# Format: <domain> <type> <item> <value>\n\n"
            "# Default limits for all users\n"
            "*    soft    core      0\n"
            "*    hard    core      0\n"
            "*    soft    nofile    1024\n"
            "*    hard    nofile    65536\n"
            "*    soft    nproc     1024\n"
            "*    hard    nproc     65536\n\n"
            "# limits.d/ directory\n"
            "# Additional limits can be added in /etc/security/limits.d/\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/security/limits.conf")

    def _create_namespace_conf(self) -> None:
        fp = self.security_path / "namespace.conf"
        if fp.exists():
            return
        fp.write_text(
            "# /etc/security/namespace.conf - Namespace configuration\n"
            "# UmerOS Namespace Configuration\n\n"
            "# Uncomment to enable mount namespace\n"
            "# mount_prefix /mnt/user\n\n"
            "# Uncomment to enable polyinstanced /tmp\n"
            "# /tmp       tmpfs   mode=0755,gid=0,seclabel\n\n"
            "# Uncomment to enable polyinstanced /var/tmp\n"
            "# /var/tmp   tmpfs   mode=0755,gid=0,seclabel\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/security/namespace.conf")

    def _create_pam_env_conf(self) -> None:
        fp = self.security_path / "pam_env.conf"
        if fp.exists():
            return
        fp.write_text(
            "# /etc/security/pam_env.conf - PAM environment variables\n"
            "# UmerOS PAM Environment Configuration\n"
            "# See pam_env.conf(5) for details.\n\n"
            "# Format: VARIABLE  DEFAULT=[value]  OVERRIDE=[value]\n\n"
            "# Set default editor\n"
            "EDITOR DEFAULT=vi\n\n"
            "# Set default pager\n"
            "PAGER DEFAULT=less\n\n"
            "# Set locale\n"
            "LANG DEFAULT=en_US.UTF-8\n\n"
            "# Set PATH\n"
            "PATH DEFAULT=/usr/local/bin:/usr/bin:/bin\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/security/pam_env.conf")

    def _create_time_conf(self) -> None:
        fp = self.security_path / "time.conf"
        if fp.exists():
            return
        fp.write_text(
            "# /etc/security/time.conf - Time-based access control\n"
            "# UmerOS Time Access Configuration\n"
            "# See time.conf(5) for details.\n\n"
            "# Format: services;users;times\n\n"
            "# Allow all users full access\n"
            "*;*;Al0000-2400\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/security/time.conf")

    def _create_sepermit_conf(self) -> None:
        fp = self.security_path / "sepermit.conf"
        if fp.exists():
            return
        fp.write_text(
            "# /etc/security/sepermit.conf - SELinux context mapping\n"
            "# UmerOS SEPermit Configuration\n\n"
            "# Format: user : [group[,group,...]] : [secontext]\n\n"
            "# Permissive users\n"
            "# user1 : user1 : user_u\n",
            encoding="utf-8",
        )
        log.debug("Created /etc/security/sepermit.conf")

    def get_summary(self) -> Dict[str, Any]:
        return {
            "security_path_exists": self.security_path.exists(),
            "access_conf_exists": (self.security_path / "access.conf").exists(),
            "limits_conf_exists": (self.security_path / "limits.conf").exists(),
            "namespace_conf_exists": (self.security_path / "namespace.conf").exists(),
            "pam_env_conf_exists": (self.security_path / "pam_env.conf").exists(),
            "time_conf_exists": (self.security_path / "time.conf").exists(),
            "sepermit_conf_exists": (self.security_path / "sepermit.conf").exists(),
        }
