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
Umer OS /root CLI
=================
``python -m root <command>`` - small command-line front-end for the
``root`` package, mirroring the style of ``python -m lib`` and
``python -m initrd``.

Sub-commands
------------

* ``selftest``           - run every module's self-test
* ``info [path]``        - one-shot /root summary
* ``audit [path]``       - run the FHS / TLDP audit
* ``safety [path]``      - run the safety auditor only
* ``ensure [path]``      - create the home, set perms, drop dotfiles
* ``forward <addr>``     - set /root/.forward
* ``dotfiles [path]``    - list + materialise the standard dotfiles
* ``passwd [path]``      - inspect /etc/passwd root entry
* ``help``               - print this help text

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

log = logging.getLogger("UmerOS.Root.CLI")


USAGE = """\
Umer OS /root - system administrator home CLI

Usage:
    python -m root <command> [args]

Commands:
    selftest                Run the self-test of every root module.
    info [path]             Print a one-shot /root summary.
    audit [path]            Run the FHS / TLDP audit and report issues.
    safety [path]           Run the safety auditor only.
    ensure [path]           Create the home, set perms, drop dotfiles.
    forward <addr>          Set /root/.forward to the given address.
    dotfiles [path]         List + materialise the standard dotfiles.
    passwd [path]           Show the canonical /etc/passwd root entry.
    help                    Print this help text.
"""


# ---------------------------------------------------------------------------
# Self-test runner
# ---------------------------------------------------------------------------

_SELFTEST_MODULES = (
    "root.home",
    "root.dotfiles",
    "root.shell",
    "root.mail",
    "root.safety",
    "root.passwd",
    "root.fhs",
)


def _cmd_selftest(_args: List[str]) -> int:
    import importlib
    results: List[tuple[str, bool, str]] = []
    for mod_name in _SELFTEST_MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except Exception as exc:  # noqa: BLE001
            results.append((mod_name, False, f"import failed: {exc}"))
            continue
        selftest = getattr(mod, "_selftest", None)
        if selftest is None:
            results.append((mod_name, True, "no _selftest() defined"))
            continue
        try:
            ok = bool(selftest())
        except Exception as exc:  # noqa: BLE001
            results.append((mod_name, False, f"raised: {exc}"))
            continue
        results.append((mod_name, ok, "OK" if ok else "FAIL"))
    width = max(len(name) for name, _, _ in results)
    for name, ok, note in results:
        marker = "OK" if ok else "FAIL"
        print(f"  {name:<{width}}  [{marker}]  {note}")
    failures = [name for name, ok, _ in results if not ok]
    return 0 if not failures else 1


# ---------------------------------------------------------------------------
# info / audit / safety
# ---------------------------------------------------------------------------

def _cmd_info(args: List[str]) -> int:
    from root.home import RootHomeManager
    home = args[0] if args else None
    mgr = RootHomeManager(default_path=home or "/root")
    info = mgr.audit(path=home)
    print(mgr.render_table(info))
    return 0 if not info.issues else 1


def _cmd_audit(args: List[str]) -> int:
    from root.fhs import FHSRootAuditor
    home = args[0] if args else "/root"
    auditor = FHSRootAuditor(home=home)
    print(auditor.audit().render())
    print(auditor.safety_audit().render())
    return 0 if auditor.audit().ok else 1


def _cmd_safety(args: List[str]) -> int:
    from root.safety import RootSafetyAuditor
    home = args[0] if args else "/root"
    auditor = RootSafetyAuditor(home=home)
    report = auditor.audit()
    print(report.render())
    return 1 if report.has_blocking() else 0


# ---------------------------------------------------------------------------
# ensure / forward / dotfiles
# ---------------------------------------------------------------------------

def _cmd_ensure(args: List[str]) -> int:
    from root.dotfiles import RootDotfilesManager
    from root.home import RootHomeManager
    home = args[0] if args else None
    hm = RootHomeManager(default_path=home or "/root")
    info = hm.ensure(path=home)
    print(hm.render_table(info))
    dm = RootDotfilesManager(home=info.path)
    report = dm.ensure_all(force=False)
    print(json.dumps(report.as_dict(), indent=2))
    return 0


def _cmd_forward(args: List[str]) -> int:
    if not args:
        print("forward: missing <address>", file=sys.stderr)
        return 2
    from root.mail import RootMailForwarder
    fm = RootMailForwarder(home="/root")
    report = fm.ensure(address=args[0], comment="set by python -m root forward")
    print(fm.render(report))
    return 0 if report.exists and not report.issues else 1


def _cmd_dotfiles(args: List[str]) -> int:
    from root.dotfiles import RootDotfilesManager
    home = args[0] if args else "/root"
    mgr = RootDotfilesManager(home=home)
    if not Path(home).is_dir():
        print(f"dotfiles: {home} is not a directory", file=sys.stderr)
        return 2
    report = mgr.ensure_all(force=False)
    present = mgr.list_present()
    missing = mgr.list_missing()
    print(f"  present: {', '.join(present) or '(none)'}")
    print(f"  missing: {', '.join(missing) or '(none)'}")
    print()
    print(json.dumps(report.as_dict(), indent=2))
    return 0


def _cmd_passwd(_args: List[str]) -> int:
    from root.passwd import CanonicalRootBuilder, PasswdManager
    mgr = PasswdManager()
    canonical = CanonicalRootBuilder().build()
    existing = mgr.find_root()
    if existing is None:
        print("  (no /etc/passwd entry for uid 0 found)")
        print()
    else:
        print(f"  current: {existing.as_line()}")
        print(f"  proposed: {canonical.as_line()}")
        if existing.home != canonical.home or existing.shell != canonical.shell:
            print("  (canonical differs - run as part of an installer to upsert)")
        else:
            print("  (matches canonical)")
    return 0


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_TABLE = {
    "selftest":  _cmd_selftest,
    "info":      _cmd_info,
    "audit":     _cmd_audit,
    "safety":    _cmd_safety,
    "ensure":    _cmd_ensure,
    "forward":   _cmd_forward,
    "dotfiles":  _cmd_dotfiles,
    "passwd":    _cmd_passwd,
}


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("help", "-h", "--help"):
        print(USAGE)
        return 0
    cmd, rest = args[0], args[1:]
    if cmd not in _TABLE:
        print(f"unknown command: {cmd}\n\n{USAGE}", file=sys.stderr)
        return 2
    return _TABLE[cmd](rest)


if __name__ == "__main__":
    sys.exit(main())
