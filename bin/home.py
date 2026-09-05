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
UmerOS /bin/home Command
=========================
Shell command for managing user home directories.

Subcommands:
  home create <user>       — Create home directory with skeleton files
  home dotfiles <user>     — Install dotfiles for a user
  home profile <user>      — Show user profile info
  home quota <user>        — Show disk quota for a user
  home backup <user>       — Create a backup of user's home
  home mail <user>         — Show mail status for a user
  home info <user>         — Full home directory info
  home list                — List all user homes

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
import sys
from typing import Any, List, Optional

log = logging.getLogger("UmerOS.home")


class HomeCommand:
    """Manage user home directories and related resources."""

    def execute(self, args: Optional[List[str]] = None,
                stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []

        if not args or args[0] in ("-h", "--help"):
            self._print_help(stdout)
            return 0

        sub = args[0].lower()
        sub_args = args[1:]

        if sub == "create":
            return self._cmd_create(sub_args)
        elif sub == "dotfiles":
            return self._cmd_dotfiles(sub_args)
        elif sub == "profile":
            return self._cmd_profile(sub_args)
        elif sub == "quota":
            return self._cmd_quota(sub_args)
        elif sub == "backup":
            return self._cmd_backup(sub_args)
        elif sub == "mail":
            return self._cmd_mail(sub_args)
        elif sub == "info":
            return self._cmd_info(sub_args)
        elif sub == "list":
            return self._cmd_list()
        else:
            print(f"home: unknown subcommand '{sub}'", file=sys.stderr)
            self._print_help(sys.stderr)
            return 1

    def _print_help(self, out: Any = None) -> None:
        target = out or sys.stdout
        print("Usage: home <subcommand> [args]", file=target)
        print("", file=target)
        print("Subcommands:", file=target)
        print("  create <user>       Create home dir with skeleton files", file=target)
        print("  dotfiles <user>     Install dotfiles for a user", file=target)
        print("  profile <user>      Show user profile", file=target)
        print("  quota <user>        Show disk quota", file=target)
        print("  backup <user>       Backup user home", file=target)
        print("  mail <user>         Show mail status", file=target)
        print("  info <user>         Full home info", file=target)
        print("  list                List all user homes", file=target)

    def _cmd_create(self, args: List[str]) -> int:
        if not args:
            print("home create: missing username", file=sys.stderr)
            return 1
        try:
            from home.home_manager import HomeManager
            hm = HomeManager()
            result = hm.create_home(args[0])
            if result.get("success"):
                print(f"Home created for {args[0]}: {result['data'].get('home_path', '/home/' + args[0])}")
                return 0
            else:
                print(f"home create: {result.get('error', 'failed')}", file=sys.stderr)
                return 1
        except (ImportError, OSError, ValueError) as exc:  # [FIX H8]
            print(f"home create: {exc}", file=sys.stderr)
            return 1

    def _cmd_dotfiles(self, args: List[str]) -> int:
        if not args:
            print("home dotfiles: missing username", file=sys.stderr)
            return 1
        try:
            from home.dotfiles import DotfilesManager
            dm = DotfilesManager()
            files = dm.install_dotfiles(args[0])
            print(f"Installed {len(files)} dotfiles for {args[0]}")
            for f in files:
                print(f"  {f}")
            return 0
        except (ImportError, OSError, ValueError) as exc:  # [FIX H8]
            print(f"home dotfiles: {exc}", file=sys.stderr)
            return 1

    def _cmd_profile(self, args: List[str]) -> int:
        if not args:
            print("home profile: missing username", file=sys.stderr)
            return 1
        try:
            from home.user_profile import UserProfileManager
            pm = UserProfileManager()
            result = pm.get_profile(args[0])
            if result.get("success"):
                data = result["data"]
                print(f"Username:  {data.get('username', 'N/A')}")
                print(f"Full Name: {data.get('full_name', 'N/A')}")
                print(f"Shell:     {data.get('shell', 'N/A')}")
                print(f"Home:      {data.get('home_dir', 'N/A')}")
                print(f"Created:   {data.get('created', 'N/A')}")
                return 0
            else:
                print(f"home profile: {result.get('error', 'not found')}", file=sys.stderr)
                return 1
        except (ImportError, OSError, ValueError) as exc:  # [FIX H8]
            print(f"home profile: {exc}", file=sys.stderr)
            return 1

    def _cmd_quota(self, args: List[str]) -> int:
        if not args:
            print("home quota: missing username", file=sys.stderr)
            return 1
        try:
            from home.home_quota import HomeQuotaManager
            qm = HomeQuotaManager()
            result = qm.get_usage(args[0])
            if result.get("success"):
                data = result["data"]
                used = data.get("used_bytes", 0)
                hard = data.get("hard_limit_bytes", 0)
                soft = data.get("soft_limit_bytes", 0)
                print(f"Quota for {args[0]}:")
                print(f"  Used:      {used} bytes")
                print(f"  Soft limit: {soft} bytes")
                print(f"  Hard limit: {hard} bytes")
                return 0
            else:
                print(f"home quota: {result.get('error', 'not found')}", file=sys.stderr)
                return 1
        except (ImportError, OSError, ValueError) as exc:  # [FIX H8]
            print(f"home quota: {exc}", file=sys.stderr)
            return 1

    def _cmd_backup(self, args: List[str]) -> int:
        if not args:
            print("home backup: missing username", file=sys.stderr)
            return 1
        try:
            from home.home_backup import HomeBackupManager
            bm = HomeBackupManager()
            result = bm.create_backup(args[0])
            if result.get("success"):
                data = result["data"]
                print(f"Backup created for {args[0]}:")
                print(f"  Path: {data.get('backup_path', 'N/A')}")
                print(f"  Size: {data.get('size_bytes', 0)} bytes")
                return 0
            else:
                print(f"home backup: {result.get('error', 'failed')}", file=sys.stderr)
                return 1
        except (ImportError, OSError, ValueError) as exc:  # [FIX H8]
            print(f"home backup: {exc}", file=sys.stderr)
            return 1

    def _cmd_mail(self, args: List[str]) -> int:
        if not args:
            print("home mail: missing username", file=sys.stderr)
            return 1
        try:
            from home.home_mail import HomeMailManager
            mm = HomeMailManager()
            result = mm.get_mailbox(args[0])
            if result.get("success"):
                msgs = result["data"].get("messages", [])
                print(f"Mailbox for {args[0]}: {len(msgs)} message(s)")
                for msg in msgs:
                    print(f"  [{msg.get('from', '?')}] {msg.get('subject', '(no subject)')}")
                return 0
            else:
                print(f"home mail: {result.get('error', 'not found')}", file=sys.stderr)
                return 1
        except (ImportError, OSError, ValueError) as exc:  # [FIX H8]
            print(f"home mail: {exc}", file=sys.stderr)
            return 1

    def _cmd_info(self, args: List[str]) -> int:
        if not args:
            print("home info: missing username", file=sys.stderr)
            return 1
        user = args[0]
        try:
            from home.home_manager import HomeManager
            hm = HomeManager()
            result = hm.get_home_info(user)
            if result.get("success"):
                data = result["data"]
                print(f"Home info for {user}:")
                print(f"  Path:       {data.get('home_path', 'N/A')}")
                print(f"  Exists:     {data.get('exists', False)}")
                print(f"  Size:       {data.get('size_bytes', 0)} bytes")
                print(f"  Dotfiles:   {data.get('dotfiles_count', 0)}")
                return 0
            else:
                print(f"home info: {result.get('error', 'not found')}", file=sys.stderr)
                return 1
        except (ImportError, OSError, ValueError) as exc:  # [FIX H8]
            print(f"home info: {exc}", file=sys.stderr)
            return 1

    def _cmd_list(self) -> int:
        try:
            from home.home_manager import HomeManager
            hm = HomeManager()
            homes = hm.list_homes()
            if homes:
                print("User homes:")
                for h in homes:
                    print(f"  {h}")
                return 0
            else:
                print("No user homes found.")
                return 0
        except (ImportError, OSError, ValueError) as exc:  # [FIX H8]
            print(f"home list: {exc}", file=sys.stderr)
            return 1

    def help(self) -> str:
        return "home — manage user home directories"
