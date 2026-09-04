# UmerOS /etc — System configuration managers
# ===========================================
# GPL-3.0 — see LICENSE and README for details.
#
# /etc: system configuration files (passwd, group, shadow,
# fstab, profile, hostname, …) plus per-service config managers.
"""
UmerOS /etc — System configuration managers.
"""

from __future__ import annotations

import logging
from typing import List

__version__ = "1.0.0"
__all__: list[str] = []

log = logging.getLogger("UmerOS.Etc")


def _try_import(module_name: str, names: tuple[str, ...]) -> None:
    """Import optional helpers and add the names to ``__all__``."""
    global __all__
    try:
        mod = __import__(f"{__name__}.{module_name}", fromlist=names)
    except ImportError:
        return
    for n in names:
        if hasattr(mod, n):
            globals()[n] = getattr(mod, n)
            __all__ = list(__all__) + [n]


for _mod, _names in (
    # Original
    ("config_manager", ("ConfigManager", "get_config_manager")),
    ("passwd_group", ("PasswdGroupManager",)),
    ("network_config", ("NetworkConfigManager",)),
    ("shell_config", ("ShellConfigManager",)),
    ("critical_files", ("CriticalFilesManager",)),
    # New
    ("alternatives", ("AlternativesManager",)),
    ("cron_schedule", ("CronScheduleManager",)),
    ("pam_config", ("PAMConfigManager",)),
    ("locale_timezone", ("LocaleTimezoneManager",)),
    ("hostname_manager", ("HostnameManager",)),
    ("fstab_manager", ("FstabManager",)),
    ("module_config", ("ModuleConfigManager",)),
    ("sysconfig", ("SysconfigManager",)),
    ("udev_rules", ("UdevRulesManager",)),
    ("tmpfiles", ("TmpfilesManager",)),
    ("login_config", ("LoginConfigManager",)),
    ("issue_motd", ("IssueMotdManager",)),
    # FHS-mandated system config
    ("adduser_config", ("AdduserConfigManager",)),
    ("mail_aliases", ("MailAliasesManager",)),
    ("nfs_exports", ("NFSExportsManager",)),
    ("login_environment", ("LoginEnvironmentManager",)),
    ("cron_allow", ("CronAccessManager",)),
    ("networks", ("NetworksManager",)),
    ("cups_config", ("CUPSConfigManager",)),
    ("conf_d", ("ConfDManager",)),
    ("ssl_config", ("SSLConfigManager",)),
    ("dpkg_config", ("DpkgConfigManager",)),
    ("kernel_config", ("KernelConfigManager",)),
    ("hotplug_config", ("HotplugConfigManager",)),
    ("manpath_config", ("ManpathConfigManager",)),
    ("updatedb_config", ("UpdatedbConfigManager",)),
    ("usb_config", ("USBConfigManager",)),
    ("x11_extra", ("X11ExtraManager",)),
    ("kde_config", ("KDEConfigManager",)),
    # Networking configuration
    ("hosts_access", ("HostsAccessManager",)),
    ("inet_services", ("InetServicesManager",)),
    ("dhcp_config", ("DHCPConfigManager",)),
    # Shell and user environment
    ("shell_profile", ("ShellProfileManager",)),
    ("csh_zsh_config", ("CshZshConfigManager",)),
    # System logging and maintenance
    ("logrotate_config", ("LogrotateConfigManager",)),
    ("syslog_config", ("SyslogConfigManager",)),
    ("hardware_config", ("HardwareConfigManager",)),
    # MIME and package management
    ("mime_config", ("MimeConfigManager",)),
    ("apt_config", ("AptConfigManager",)),
    # File sharing and mail
    ("samba_config", ("SambaConfigManager",)),
    ("mail_config", ("MailConfigManager",)),
    # Core system modules
    ("skeleton", ("SkeletonManager",)),
    ("security", ("SecurityConfigManager",)),
    ("environment", ("EnvironmentManager",)),
    # Service/daemon configuration
    ("cron_d", ("CronDManager",)),
    ("init_scripts", ("InitScriptsManager",)),
    ("dbus_config", ("DBusConfigManager",)),
    # Hardware/storage configuration
    ("lvm_config", ("LVMConfigManager",)),
    ("fonts_config", ("FontsConfigManager",)),
    ("ssl_dirs", ("SSLDirsManager",)),
    # Network/security configuration
    ("network_manager", ("NetworkManagerConfigManager",)),
    ("wpa_supplicant", ("WPASupplicantManager",)),
    # Desktop/system configuration
    ("xdg_config", ("XDGConfigManager",)),
    ("gss_config", ("GSSConfigManager",)),
    ("openvpn_config", ("OpenVPNConfigManager",)),
    # Kernel/time configuration
    ("modprobe_d", ("ModprobeDManager",)),
    ("sysctl_d", ("SysctlDManager",)),
    ("chrony_config", ("ChronyConfigManager",)),
    # Network/PPP/scanner configuration
    ("ppp_config", ("PPPConfigManager",)),
    ("sane_config", ("SANEConfigManager",)),
    ("modules_load", ("ModulesLoadManager",)),
    # FHS batch 12 - shell/os/security/misc
    ("shells", ("ShellsManager",)),
    ("os_release", ("OSReleaseManager",)),
    ("inputrc_config", ("InputRCManager",)),
    ("securetty", ("SecureTTYManager",)),
    ("host_conf", ("HostConfManager",)),
    ("gai_conf", ("GAIConfManager",)),
    ("vconsole_config", ("VConsoleManager",)),
    ("profile_d", ("ProfileDManager",)),
    ("binfmt_d", ("BinFmtManager",)),
    ("default_config", ("DefaultConfigManager",)),
    ("e2fsck_config", ("E2fsckConfigManager",)),
    ("sudoers", ("SudoersManager",)),
    ("init_system", ("InitSystemManager",)),
    ("hosts", ("HostsManager",)),
):
    _try_import(_mod, _names)


def _selftest() -> bool:
    """Verify the public surface is intact."""
    import importlib
    import sys

    pkg = importlib.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        print(f"etc selftest FAIL: missing {missing}", file=sys.stderr)
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
