"""
UmerOS /home Package — Home Directory Management
Manages user home directories, dotfiles, profiles, SSH, mail, and backups.

FHS 3.0 /home specification:
  ~user    = Home directory of the user.
  /home/$USER/   Each user has a subdirectory in /home.
  /etc/skel  Skeleton directory for new home directories.
  Dotfiles  Hidden config files in user's home.
  ~/.local/  User-local executables, data, state.

Managers:
  HomeManager        — Core home directory CRUD, XDG dirs, disk usage
  DotfilesManager    — Default dotfile templates, install/remove
  UserProfileManager — Per-user environment variables, PATH, aliases
  HomeMailManager    — Maildir delivery, /var/spool/mail
  HomeDirsManager    — XDG user dirs, hidden config dirs
  HomeLocalManager   — ~/.local/ hierarchy (share, bin, lib, state)
  HomeSSHManager     — SSH key pairs, authorized_keys, known_hosts, config
  HomeQuotaManager   — Disk quota tracking per user
  HomeBackupManager  — Home directory backup/restore (tar.gz)

Integration:
  etc/passwd_group.py  — User UID/GID, primary groups
  etc/skeleton.py      — Skeleton files for new homes
  etc/adduser_config.py — DHOME="/home"
  kernel/umer_kernel.py — Pre-creates /home/umer at boot
"""

from .home_manager import HomeManager
from .dotfiles import DotfilesManager
from .user_profile import UserProfileManager
from .home_mail import HomeMailManager
from .home_dirs import HomeDirsManager
from .home_local import HomeLocalManager
from .home_ssh import HomeSSHManager
from .home_quota import HomeQuotaManager
from .home_backup import HomeBackupManager

__all__ = [
    "HomeManager",
    "DotfilesManager",
    "UserProfileManager",
    "HomeMailManager",
    "HomeDirsManager",
    "HomeLocalManager",
    "HomeSSHManager",
    "HomeQuotaManager",
    "HomeBackupManager",
]
