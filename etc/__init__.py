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

from etc.config_manager import ConfigManager, get_config_manager
from etc.passwd_group import PasswdGroupManager
from etc.network_config import NetworkConfigManager
from etc.shell_config import ShellConfigManager
from etc.critical_files import CriticalFilesManager

__all__ = [
    "ConfigManager",
    "get_config_manager",
    "PasswdGroupManager",
    "NetworkConfigManager",
    "ShellConfigManager",
    "CriticalFilesManager",
]
