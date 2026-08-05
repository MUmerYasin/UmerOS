"""
UmerOS /etc Critical Configuration Files
==========================================
Manages additional critical configuration files required by FHS 3.0.

FHS 3.0 required files:
  /etc/inittab     — Init configuration
  /etc/crontab     — System-wide crontab
  /etc/sudoers     — Sudo configuration
  /etc/issue       — Pre-login banner
  /etc/motd        — Post-login message
  /etc/nsswitch.conf — Name service switch
  /etc/ld.so.conf  — Dynamic linker configuration
  /etc/exports     — NFS exports
  /etc/mtab        — Mounted filesystems (symlink)
  /etc/sysctl.conf — Kernel parameters

FHS 3.0 directories:
  /etc/network/    — Network interface configuration
  /etc/default/    — Default configurations
  /etc/skel/       — User home directory skeleton
  /etc/X11/        — X Window System configuration
  /etc/cron.d/     — Cron drop-in directory

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Etc.CriticalFiles")


@dataclass
class SysctlEntry:
    """Represents a sysctl parameter."""
    key: str
    value: str
    description: str = ""
    is_default: bool = True


@dataclass
class CronEntry:
    """Represents a crontab entry."""
    minute: str = "*"
    hour: str = "*"
    day_of_month: str = "*"
    month: str = "*"
    day_of_week: str = "*"
    command: str = ""
    user: str = "root"
    comment: str = ""


class CriticalFilesManager:
    """
    Manages critical /etc configuration files required by FHS 3.0.

    Handles init, cron, sudo, login banners, system config, and directories.
    """

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.skel_path = self.etc_path / "skel"
        self.network_path = self.etc_path / "network"
        self.default_path = self.etc_path / "default"
        self.x11_path = self.etc_path / "X11"
        self.cron_d_path = self.etc_path / "cron.d"

    def initialize(self) -> bool:
        """Create all missing critical files and directories."""
        try:
            self._create_inittab()
            self._create_crontab()
            self._create_sudoers()
            self._create_issue()
            self._create_motd()
            self._create_nsswitch_conf()
            self._create_ld_so_conf()
            self._create_exports()
            self._create_sysctl_conf()
            self._create_mtab_link()
            self._create_directories()
            self._create_skel_files()
            self._create_cron_d()
            log.info("Initialized all critical /etc files")
            return True
        except Exception as e:
            log.error("Failed to initialize critical files: %s", e)
            return False

    # ── /etc/inittab ────────────────────────────────────────────────────

    def _create_inittab(self) -> None:
        """Create /etc/inittab (System V init configuration)."""
        filepath = self.etc_path / "inittab"
        if filepath.exists():
            return
        content = """# /etc/inittab - System V Initialization Configuration
# UmerOS uses systemd as the default init system
# This file is provided for compatibility purposes

# Default runlevel
id:5:initdefault:

# System initialization
si::sysinit:/etc/init.d/rcS

# Terminal runlevels
1:2345:respawn:/sbin/getty 38400 tty1
2:2345:respawn:/sbin/getty 38400 tty2
3:2345:respawn:/sbin/getty 38400 tty3

# X Display Manager (commented out, use systemd)
#7:235:respawn:/usr/sbin/gdm

# Ctrl-Alt-Delete handling
ca::ctrlaltdel:/sbin/shutdown -r now

# Shutdown/reboot handling
l0:0:wait:/etc/init.d/rc 0
l1:1:wait:/etc/init.d/rc 1
l2:2:wait:/etc/init.d/rc 2
l3:3:wait:/etc/init.d/rc 3
l4:4:wait:/etc/init.d/rc 4
l5:5:wait:/etc/init.d/rc 5
l6:6:wait:/etc/init.d/rc 6

# UPS monitoring (if applicable)
#pf::powerfail:/etc/init.d/powerfail start
#pr:12345:powerokwait:/etc/init.d/powerok stop
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/inittab")

    # ── /etc/crontab ────────────────────────────────────────────────────

    def _create_crontab(self) -> None:
        """Create /etc/crontab (system-wide crontab)."""
        filepath = self.etc_path / "crontab"
        if filepath.exists():
            return
        content = """# /etc/crontab - System-wide crontab
# UmerOS System Crontab
# Format: minute hour day_of_week month day_of_week user command

SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# System maintenance
0 0 * * * root test -x /usr/sbin/run-crons && /usr/sbin/run-crons

# Log rotation
0 * * * * root /usr/sbin/logrotate /etc/logrotate.conf

# Temp file cleanup (daily)
0 3 * * * root find /tmp -type f -atime +10 -delete 2>/dev/null

# Database maintenance (example)
#30 2 * * 0 root /usr/local/bin/db_maintenance.sh

# Backup (daily at 2am)
#0 2 * * * root /usr/local/bin/backup.sh

# Security scan (weekly)
#0 4 * * 0 root /usr/local/bin/security_scan.sh
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/crontab")

    # ── /etc/sudoers ────────────────────────────────────────────────────

    def _create_sudoers(self) -> None:
        """Create /etc/sudoers (sudo configuration)."""
        filepath = self.etc_path / "sudoers"
        if filepath.exists():
            return
        content = """# /etc/sudoers - Sudo configuration
# UmerOS Sudo Configuration
# MUST be edited with 'visudo'

# Defaults
Defaults        env_reset
Defaults        mail_badpass
Defaults        secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Host specification
# Host_Alias     FILESERVERS = fs1, fs2
# Host_Alias     MAILSERVERS = smtp, imap

# User specification
# User specification: user host=(runas) commands

# Root can run anything
root    ALL=(ALL:ALL) ALL

# Members of the admin group can run anything
%admin ALL=(ALL) ALL

# Allow members of group sudo to run any command
%sudo  ALL=(ALL:ALL) ALL

# Read drop-in files from /etc/sudoers.d
@includedir /etc/sudoers.d

# UmerOS default user
umer    ALL=(ALL) NOPASSWD: ALL
"""
        filepath.write_text(content, encoding="utf-8")
        try:
            os.chmod(str(filepath), 0o440)
        except Exception:
            pass
        log.debug("Created /etc/sudoers")

    # ── /etc/issue ──────────────────────────────────────────────────────

    def _create_issue(self) -> None:
        """Create /etc/issue (pre-login banner)."""
        filepath = self.etc_path / "issue"
        if filepath.exists():
            return
        content = r"""
    __  __  _____  _____  ____  ___  _   _  ____  ___
   |  \/  ||  __ \|  __ \/ ___||  _ \| \ | |/ ___|/ _ \
   | |\/| || |  | | |  | \___ \| |_) |  \| | |  _| | | |
   | |  | || |__| | |__| |___) |  _ <| |\  | |_| | |_| |
   |_|  |_||_____/|_____/|____/|_| \_\_| \_|\____|\___/

                   UmerOS v1.0.0
                  Welcome to UmerOS

  Type 'login' to begin, or 'help' for available commands.

"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/issue")

    # ── /etc/motd ───────────────────────────────────────────────────────

    def _create_motd(self) -> None:
        """Create /etc/motd (message of the day)."""
        filepath = self.etc_path / "motd"
        if filepath.exists():
            return
        content = """
  ╔══════════════════════════════════════════════════╗
  ║           Welcome to UmerOS v1.0.0               ║
  ║                                                  ║
  ║  System:  UmerOS Virtual Operating System         ║
  ║  Kernel:  UmerOS 1.0.0 (Python)                  ║
  ║  Arch:    x86_64                                  ║
  ║                                                  ║
  ║  For help: type 'help'                           ║
  ║  To login: type 'login'                           ║
  ╚══════════════════════════════════════════════════╝

  System information:
    * Running processes: check with 'ps'
    * Disk usage: check with 'df'
    * Network: check with 'ip' or 'ifconfig'

  Last login: """ + time.strftime("%a %b %d %H:%M:%S %Y") + """

"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/motd")

    # ── /etc/nsswitch.conf ──────────────────────────────────────────────

    def _create_nsswitch_conf(self) -> None:
        """Create /etc/nsswitch.conf (name service switch)."""
        filepath = self.etc_path / "nsswitch.conf"
        if filepath.exists():
            return
        content = """# /etc/nsswitch.conf - Name Service Switch configuration
#
# UmerOS Name Service Switch Configuration
#

# Name resolution
hosts:          files dns
networks:       files dns

# Password and group files
passwd:         files
shadow:         files
group:          files

# Glibc NSS
gshadow:        files

# Service names
services:       files [notfound=return]

# Protocols
protocols:      files

# RPC
rpc:            files

# Ethernet
ethers:         files

# Netmasks
netmasks:       files

# Public key
publickey:      files

# Automount
automount:      files

# Sudoers
sudoers:        files

# SSH known hosts
known_hosts:    files
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/nsswitch.conf")

    # ── /etc/ld.so.conf ─────────────────────────────────────────────────

    def _create_ld_so_conf(self) -> None:
        """Create /etc/ld.so.conf (dynamic linker configuration)."""
        filepath = self.etc_path / "ld.so.conf"
        if filepath.exists():
            return
        content = """# /etc/ld.so.conf - Dynamic linker configuration
# UmerOS Dynamic Linker Configuration

# Include libraries from /lib and /usr/lib
include /etc/ld.so.conf.d/*.conf

# Standard library paths
/lib/x86_64-linux-gnu
/usr/lib/x86_64-linux-gnu
/lib
/usr/lib
/usr/local/lib

# Local library paths
/usr/local/lib/x86_64-linux-gnu

# Custom library paths (uncomment as needed)
#/opt/lib
#/usr/share/lib
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/ld.so.conf")

        # Also create ld.so.conf.d directory
        ld_conf_d = self.etc_path / "ld.so.conf.d"
        ld_conf_d.mkdir(parents=True, exist_ok=True)
        log.debug("Created /etc/ld.so.conf.d")

    # ── /etc/exports ────────────────────────────────────────────────────

    def _create_exports(self) -> None:
        """Create /etc/exports (NFS exports)."""
        filepath = self.etc_path / "exports"
        if filepath.exists():
            return
        content = """# /etc/exports - NFS server exports
# UmerOS NFS Export Configuration
# Format: directory host(options)
# Example:
# /shared   192.168.1.0/24(rw,sync,no_subtree_check,no_root_squash)
# /home     *.example.com(rw,sync,no_subtree_check)

# No exports by default for security
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/exports")

    # ── /etc/sysctl.conf ────────────────────────────────────────────────

    def _create_sysctl_conf(self) -> None:
        """Create /etc/sysctl.conf (kernel parameters)."""
        filepath = self.etc_path / "sysctl.conf"
        if filepath.exists():
            return
        content = """# /etc/sysctl.conf - Kernel parameters configuration
# UmerOS Sysctl Configuration
# See sysctl.conf(5) for details.

# Uncomment to disable SysRq key
#kernel.sysrq = 0

# Uncomment to set hostname
#kernel.hostname = umeros

# Controls IP packet forwarding
net.ipv4.ip_forward = 0

# Controls source route verification
net.ipv4.conf.default.rp_filter = 1

# Controls ICMP echo requests
net.ipv4.icmp_echo_ignore_broadcasts = 1

# Controls TCP SYN cookies
net.ipv4.tcp_syncookies = 1

# Controls the maximum number of shared memory segments
kernel.shmmax = 68719476736
kernel.shmall = 4294967296

# Controls the default maximum size of a message queue
kernel.msgmnb = 65536

# Controls the default max size of a message
kernel.msgmax = 65536

# Controls the maximum number of open file descriptors
fs.file-max = 2097152

# Controls the default maximum number of threads
kernel.threads-max = 196605

# Virtual memory tuning
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5

# Network buffer tuning
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/sysctl.conf")

    # ── /etc/mtab ───────────────────────────────────────────────────────

    def _create_mtab_link(self) -> None:
        """Create /etc/mtab symlink to /proc/mounts."""
        filepath = self.etc_path / "mtab"
        if filepath.exists() or filepath.is_symlink():
            return
        try:
            filepath.symlink_to("/proc/mounts")
            log.debug("Created /etc/mtab -> /proc/mounts symlink")
        except Exception as e:
            # If symlink fails, create a regular file
            content = """# /etc/mtab - Mounted filesystems
# This file is normally a symlink to /proc/mounts
# Created as fallback for UmerOS

rootfs / rootfs rw 0 0
proc /proc proc rw,nosuid,nodev,noexec,relatime 0 0
sysfs /sys sysfs rw,nosuid,nodev,noexec,relatime 0 0
tmpfs /tmp tmpfs rw,nosuid,nodev,relatime,size=1024000k 0 0
"""
            filepath.write_text(content, encoding="utf-8")
            log.debug("Created /etc/mtab (fallback file)")

    # ── Directory Creation ──────────────────────────────────────────────

    def _create_directories(self) -> None:
        """Create required /etc subdirectories."""
        directories = [
            self.etc_path / "network" / "interfaces.d",
            self.etc_path / "default",
            self.etc_path / "skel",
            self.etc_path / "skel" / ".config",
            self.etc_path / "skel" / ".local",
            self.etc_path / "skel" / ".local" / "share",
            self.etc_path / "X11",
            self.etc_path / "X11" / "Xsession.d",
            self.etc_path / "X11" / "xorg.conf.d",
            self.etc_path / "cron.d",
            self.etc_path / "sudoers.d",
            self.etc_path / "ld.so.conf.d",
            self.etc_path / "logrotate.d",
            self.etc_path / "apt",
            self.etc_path / "dpkg",
            self.etc_path / "profile.d",
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        log.debug("Created required /etc subdirectories")

    # ── /etc/skel Files ─────────────────────────────────────────────────

    def _create_skel_files(self) -> None:
        """Create skeleton files in /etc/skel for new users."""
        # .profile
        profile = self.skel_path / ".profile"
        if not profile.exists():
            content = """# ~/.profile: executed by the command interpreter for login shells.
# This file is not read by bash(1), if ~/.bash_profile or ~/.bash_login
# exists.
# see /usr/share/doc/bash/examples/startup-files for examples.

# if running bash
if [ -n "$BASH_VERSION" ]; then
    # include .bashrc if it exists
    if [ -f "$HOME/.bashrc" ]; then
        . "$HOME/.bashrc"
    fi
fi

# set PATH so it includes user's private bin if it exists
if [ -d "$HOME/bin" ] ; then
    PATH="$HOME/bin:$PATH"
fi

# set PATH so it includes user's private bin if it exists
if [ -d "$HOME/.local/bin" ] ; then
    PATH="$HOME/.local/bin:$PATH"
fi
"""
            profile.write_text(content, encoding="utf-8")

        # .bashrc
        bashrc = self.skel_path / ".bashrc"
        if not bashrc.exists():
            content = r"""# ~/.bashrc: executed by bash(1) for non-login shells.

# If not running interactively, don't do anything
[ -z "$PS1" ] && return

# don't put duplicate lines in the history
HISTCONTROL=ignoreboth

# append to the history file, don't overwrite it
shopt -s histappend

# for setting history length see HISTSIZE and HISTFILESIZE in bash(1)
HISTSIZE=1000
HISTFILESIZE=2000

# check the window size after each command and, if necessary,
# update the values of LINES and COLUMNS.
shopt -s checkwinsize

# make less more friendly for non-text input files
[ -x /usr/bin/lesspipe ] && eval "$(SHELL=/bin/sh lesspipe)"

# set variable identifying the chroot you work in
if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi

# set a fancy prompt (non-color, unless we know we "need" color)
case "$TERM" in
    xterm-color) color_prompt=yes;;
esac

# uncomment for a colored prompt, if the terminal supports it
force_color_prompt=yes

if [ -n "$force_color_prompt" ]; then
    if [ -x /usr/bin/tput setaf 1 ]; then
        color_prompt=yes
    else
        color_prompt=
    fi
fi

if [ "$color_prompt" = yes ]; then
    PS1='${debian_chroot:+($debian_chroot)}\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '
else
    PS1='${debian_chroot:+($debian_chroot)}\u@\h:\w\$ '
fi
unset color_prompt force_color_prompt

# enable color support of ls and also add handy aliases
if [ -x /usr/bin/dircolors ]; then
    test -r ~/.dircolors && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"
    alias ls='ls --color=auto'
    alias grep='grep --color=auto'
    alias fgrep='fgrep --color=auto'
    alias egrep='egrep --color=auto'
fi

# some more ls aliases
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'

# Alias definitions.
# You may want to put all your additions into a separate file like
# ~/.bash_aliases, instead of adding them here directly.
if [ -f ~/.bash_aliases ]; then
    . ~/.bash_aliases
fi
"""
            bashrc.write_text(content, encoding="utf-8")

    # ── /etc/cron.d ─────────────────────────────────────────────────────

    def _create_cron_d(self) -> None:
        """Create /etc/cron.d directory with example files."""
        # Example: /etc/cron.d/sysstat
        sysstat = self.cron_d_path / "sysstat"
        if not sysstat.exists():
            content = """# /etc/cron.d/sysstat - System statistics collection
# Collect system statistics every 10 minutes

# Activity reports
5 * * * * root /usr/lib/sysstat/sa1 1 1

# Daily summary
53 23 * * * root /usr/lib/sysstat/sa2 -A
"""
            sysstat.write_text(content, encoding="utf-8")
            try:
                os.chmod(str(sysstat), 0o644)
            except Exception:
                pass

    # ── Utility Methods ─────────────────────────────────────────────────

    def read_issue(self) -> str:
        """Read /etc/issue content."""
        filepath = self.etc_path / "issue"
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        return ""

    def read_motd(self) -> str:
        """Read /etc/motd content."""
        filepath = self.etc_path / "motd"
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        return ""

    def read_sysctl_conf(self) -> Dict[str, str]:
        """Parse /etc/sysctl.conf into a dictionary."""
        filepath = self.etc_path / "sysctl.conf"
        if not filepath.exists():
            return {}
        config = {}
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                config[key.strip()] = value.strip()
        return config

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of critical /etc files."""
        return {
            "inittab_exists": (self.etc_path / "inittab").exists(),
            "crontab_exists": (self.etc_path / "crontab").exists(),
            "sudoers_exists": (self.etc_path / "sudoers").exists(),
            "issue_exists": (self.etc_path / "issue").exists(),
            "motd_exists": (self.etc_path / "motd").exists(),
            "nsswitch_conf_exists": (self.etc_path / "nsswitch.conf").exists(),
            "ld_so_conf_exists": (self.etc_path / "ld.so.conf").exists(),
            "exports_exists": (self.etc_path / "exports").exists(),
            "mtab_exists": (self.etc_path / "mtab").exists(),
            "sysctl_conf_exists": (self.etc_path / "sysctl.conf").exists(),
            "directories": {
                "network": self.network_path.exists(),
                "default": self.default_path.exists(),
                "skel": self.skel_path.exists(),
                "X11": self.x11_path.exists(),
                "cron.d": self.cron_d_path.exists(),
                "sudoers.d": (self.etc_path / "sudoers.d").exists(),
                "ld.so.conf.d": (self.etc_path / "ld.so.conf.d").exists(),
                "profile.d": (self.etc_path / "profile.d").exists(),
            },
        }
