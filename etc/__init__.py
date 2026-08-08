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

# FHS-mandated system config modules
from etc.adduser_config import AdduserConfigManager
from etc.mail_aliases import MailAliasesManager
from etc.nfs_exports import NFSExportsManager
from etc.login_environment import LoginEnvironmentManager
from etc.cron_allow import CronAccessManager
from etc.networks import NetworksManager
from etc.cups_config import CUPSConfigManager
from etc.conf_d import ConfDManager
from etc.ssl_config import SSLConfigManager
from etc.dpkg_config import DpkgConfigManager
from etc.kernel_config import KernelConfigManager
from etc.hotplug_config import HotplugConfigManager
from etc.manpath_config import ManpathConfigManager
from etc.updatedb_config import UpdatedbConfigManager
from etc.usb_config import USBConfigManager
from etc.x11_extra import X11ExtraManager
from etc.kde_config import KDEConfigManager

# Networking configuration
from etc.hosts_access import HostsAccessManager
from etc.inet_services import InetServicesManager
from etc.dhcp_config import DHCPConfigManager

# Shell and user environment
from etc.shell_profile import ShellProfileManager
from etc.csh_zsh_config import CshZshConfigManager

# System logging and maintenance
from etc.logrotate_config import LogrotateConfigManager
from etc.syslog_config import SyslogConfigManager
from etc.hardware_config import HardwareConfigManager

# MIME and package management
from etc.mime_config import MimeConfigManager
from etc.apt_config import AptConfigManager

# File sharing and mail
from etc.samba_config import SambaConfigManager
from etc.mail_config import MailConfigManager

# Core system modules
from etc.skeleton import SkeletonManager
from etc.security import SecurityConfigManager
from etc.environment import EnvironmentManager

# Service/daemon configuration
from etc.cron_d import CronDManager
from etc.init_scripts import InitScriptsManager
from etc.dbus_config import DBusConfigManager

# Hardware/storage configuration
from etc.lvm_config import LVMConfigManager
from etc.fonts_config import FontsConfigManager
from etc.ssl_dirs import SSLDirsManager

# Network/security configuration
from etc.network_manager import NetworkManagerConfigManager
from etc.wpa_supplicant import WPASupplicantManager

# Desktop/system configuration
from etc.xdg_config import XDGConfigManager
from etc.gss_config import GSSConfigManager
from etc.openvpn_config import OpenVPNConfigManager

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
    # FHS-mandated system config
    "AdduserConfigManager",
    "MailAliasesManager",
    "NFSExportsManager",
    "LoginEnvironmentManager",
    "CronAccessManager",
    "NetworksManager",
    "CUPSConfigManager",
    "ConfDManager",
    "SSLConfigManager",
    "DpkgConfigManager",
    "KernelConfigManager",
    "HotplugConfigManager",
    "ManpathConfigManager",
    "UpdatedbConfigManager",
    "USBConfigManager",
    "X11ExtraManager",
    "KDEConfigManager",
    # Networking configuration
    "HostsAccessManager",
    "InetServicesManager",
    "DHCPConfigManager",
    # Shell and user environment
    "ShellProfileManager",
    "CshZshConfigManager",
    # System logging and maintenance
    "LogrotateConfigManager",
    "SyslogConfigManager",
    "HardwareConfigManager",
    # MIME and package management
    "MimeConfigManager",
    "AptConfigManager",
    # File sharing and mail
    "SambaConfigManager",
    "MailConfigManager",
    # Core system modules
    "SkeletonManager",
    "SecurityConfigManager",
    "EnvironmentManager",
    # Service/daemon configuration
    "CronDManager",
    "InitScriptsManager",
    "DBusConfigManager",
    # Hardware/storage configuration
    "LVMConfigManager",
    "FontsConfigManager",
    "SSLDirsManager",
    # Network/security configuration
    "NetworkManagerConfigManager",
    "WPASupplicantManager",
    # Desktop/system configuration
    "XDGConfigManager",
    "GSSConfigManager",
    "OpenVPNConfigManager",
]
