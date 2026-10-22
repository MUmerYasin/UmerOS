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
UmerOS /opt/installers CLI
==========================

``python -m opt.installers <command>`` - small command-line front-end for
the pre-built package installers, mirroring ``python -m opt``.

Sub-commands
------------

* ``selftest``   - run every installer's ``_selftest()``
* ``help``       - print this help text

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import sys
from typing import List, Optional

USAGE = """\
Umer OS /opt/installers - pre-built package installers CLI

Usage:
    python -m opt.installers <command> [args]

Commands:
    selftest                Run the self-test of every installer module.
    help                    Print this help text.
"""

# Installer modules whose _selftest() the CLI runs (H192).
_SELFTEST_MODULES = (
    "opt.installers.sample_app",
    "opt.installers.web_server",
    "opt.installers.database",
    "opt.installers.development",
)


def _cmd_selftest(_args: List[str]) -> int:
    """Run every listed installer's _selftest() and report status."""
    import importlib

    results: List[tuple] = []
    for mod_name in _SELFTEST_MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except Exception as exc:  # noqa: BLE001
            results.append((mod_name, False, f"import failed: {exc}"))
            continue
        selftest = getattr(mod, "_selftest", None)
        if selftest is None:
            results.append((mod_name, False, "no _selftest() defined"))
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
    if failures:
        print(f"opt.installers selftest FAIL: {failures}", file=sys.stderr)
        return 1
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("help", "-h", "--help"):
        print(USAGE)
        return 0
    if args[0] == "selftest":
        return _cmd_selftest(args[1:])
    print(f"unknown command: {args[0]}\n\n{USAGE}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
