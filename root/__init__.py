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
Umer OS /root
=============

 /root page focuses on three things:

* ``/root`` is the system administrator's home directory.
* It is **not** under ``/home`` because ``/home`` is often on a
  separate partition and would be inaccessible when only ``/`` is
  mounted.
* If root's home cannot be located, it must default to ``/``.
* Subdirectories for mail and other applications should not appear
  in ``/root``.
* Mail for admin roles (``root``, ``postmaster``, ``webmaster``)
  should be forwarded to an appropriate user.

This package covers those rules, plus a small set of operational
best practices the TLDP page only hints at.

Sub-modules
-----------

* :mod:`root.home`     - resolution, audit, bootstrap of root's home
* :mod:`root.dotfiles` - ``.bashrc``, ``.profile``, ``.bash_logout``, ``.vimrc`` ...
* :mod:`root.shell`    - root-friendly environment (``PATH``, ``PS1``, ``LD_LIBRARY_PATH``)
* :mod:`root.mail`     - ``~/.forward`` management and admin role table
* :mod:`root.safety`   - safety auditor (PATH, LD_*, .ssh, history, user-state)
* :mod:`root.passwd`   - /etc/passwd integration + canonical root row
* :mod:`root.fhs`      - FHS / TLDP audit + bootstrap

Quick start
-----------

::

    from root.home import RootHomeManager
    from root.dotfiles import RootDotfilesManager
    from root.mail import RootMailForwarder
    from root.fhs import FHSRootAuditor

    info = RootHomeManager().audit()
    print(info)

    RootDotfilesManager(home="/root").ensure_all(force=True)
    RootMailForwarder(home="/root").ensure("admin@example.com")

    audit = FHSRootAuditor().audit()
    if not audit.ok:
        for issue in audit.issues:
            print(issue)

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

__version__ = "2.0.0"

from root.dotfiles import (
    DEFAULT_TEMPLATES,
    DotfileResult,
    DotfilesReport,
    RootDotfilesManager,
)
from root.fhs import FHSIssue, FHSIssueSeverity, FHSReport, FHSRootAuditor
from root.home import (
    DEFAULT_ROOT_HOME,
    DISCOURAGED_SUBDIRS,
    ROOT_HOME_MODE,
    ROOT_UID,
    RootHomeInfo,
    RootHomeManager,
    RootHomeResolver,
    find_root_passwd_entry,
)
from root.mail import (
    ADMIN_ROLES,
    FORWARD_FILENAME,
    ForwardEntry,
    ForwardParser,
    ForwardReport,
    RootMailForwarder,
)
from root.passwd import CanonicalRootBuilder, PasswdEntry, PasswdManager
from root.safety import (
    SafetyFinding,
    SafetyReport,
    SafetySeverity,
    RootSafetyAuditor,
)
from root.shell import (
    DANGEROUS_VARS,
    DEFAULT_PATH,
    DEFAULT_SHELL,
    HARDENED_DEFAULTS,
    RootShellEnvironmentBuilder,
    ShellEnvironment,
)


__all__ = [
    # home
    "DEFAULT_ROOT_HOME", "DISCOURAGED_SUBDIRS", "ROOT_HOME_MODE", "ROOT_UID",
    "RootHomeInfo", "RootHomeManager", "RootHomeResolver",
    "find_root_passwd_entry",
    # dotfiles
    "DEFAULT_TEMPLATES", "DotfileResult", "DotfilesReport", "RootDotfilesManager",
    # shell
    "DANGEROUS_VARS", "DEFAULT_PATH", "DEFAULT_SHELL", "HARDENED_DEFAULTS",
    "RootShellEnvironmentBuilder", "ShellEnvironment",
    # mail
    "ADMIN_ROLES", "FORWARD_FILENAME", "ForwardEntry", "ForwardParser",
    "ForwardReport", "RootMailForwarder",
    # safety
    "SafetyFinding", "SafetyReport", "SafetySeverity", "RootSafetyAuditor",
    # passwd
    "CanonicalRootBuilder", "PasswdEntry", "PasswdManager",
    # fhs
    "FHSIssue", "FHSIssueSeverity", "FHSReport", "FHSRootAuditor",
]
