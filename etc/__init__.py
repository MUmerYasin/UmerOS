"""
Umer OS /etc hierarchy — System configuration modules.

FHS 3.0 /etc requirements:
- System configuration files
- passwd, group, shadow (user accounts)
- hosts, resolv.conf (network)
- fstab (filesystem mounts)
- profile, bashrc (shell config)
- hostname, timezone
- System service configuration

Author:  Umer OS Project
Licence: Apache 2.0
"""

# Original modules
from etc.config_manager import ConfigManager, get_config_manager
from etc.passwd_group import PasswdGroupManager
from etc.network_config import NetworkConfigManager
from etc.shell_config import ShellConfigManager
from etc.critical_files import CriticalFilesManager

# New Linux /etc modules
from etc.alternatives import AlternativesManager
from etc.cron_schedule import CronScheduleManager
from etc.pam_config import PAMConfigManager
from etc.locale_timezone import LocaleTimezoneManager
from etc.hostname_manager import HostnameManager
from etc.fstab_manager import FstabManager
from etc.module_config import ModuleConfigManager
from etc.sysconfig import SysconfigManager
from etc.udev_rules import UdevRulesManager
from etc.tmpfiles import TmpfilesManager
from etc.login_config import LoginConfigManager
from etc.issue_motd import IssueMotdManager

__all__ = [
    # Original
    "ConfigManager",
    "get_config_manager",
    "PasswdGroupManager",
    "NetworkConfigManager",
    "ShellConfigManager",
    "CriticalFilesManager",
    # New
    "AlternativesManager",
    "CronScheduleManager",
    "PAMConfigManager",
    "LocaleTimezoneManager",
    "HostnameManager",
    "FstabManager",
    "ModuleConfigManager",
    "SysconfigManager",
    "UdevRulesManager",
    "TmpfilesManager",
    "LoginConfigManager",
    "IssueMotdManager",
]
