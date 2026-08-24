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
Umer OS /lib CLI
================
``python -m lib <command>`` - small command-line front-end for the
``lib`` package, mirroring the style of ``python -m initrd`` and
``python -m quantum``.

Sub-commands
------------

* ``selftest``           - run every lib module's self-test
* ``info``               - one-shot /lib summary (the headline numbers)
* ``audit``              - run the FHS audit and print a coloured report
* ``ldd <path>``         - trace shared library deps of an ELF binary
* ``ldconfig``           - rebuild /etc/ld.so.cache (binary format)
* ``depmod``             - regenerate /lib/modules/<ver>/modules.dep
* ``modprobe <name>``    - load a kernel module (or ``-r`` to remove)
* ``lsmod``              - list currently loaded modules
* ``cpplink``            - ensure /lib/cpp references the C preprocessor
* ``list``               - list essential libraries
* ``help``               - print this help text

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

log = logging.getLogger("UmerOS.Lib.CLI")


USAGE = """\
Umer OS /lib - shared-library + kernel-module CLI

Usage:
    python -m lib <command> [args]

Commands:
    selftest                Run the self-test of every lib module.
    info [path]             Print a one-shot summary of /lib.
    audit [path]            Run the FHS audit and report issues.
    ldd <elf>               Trace shared library dependencies of an ELF file.
    ldconfig [path]         Rebuild /etc/ld.so.cache from /etc/ld.so.conf.
    depmod [ver]            Regenerate modules.dep for the given kernel.
    modprobe <name> [-r]    Load (or remove with -r) a kernel module.
    lsmod                   List currently loaded kernel modules.
    cpplink                 Ensure /lib/cpp references /usr/bin/cpp.
    list                    List all essential libraries.
    help                    Print this help text.
"""


# ---------------------------------------------------------------------------
# Self-test runner
# ---------------------------------------------------------------------------

_SELFTEST_MODULES = (
    "lib.elf_parser",
    "lib.essential_libs",
    "lib.library_manager",
    "lib.dynamic_linker",
    "lib.kernel_modules",
    "lib.ldd",
    "lib.fhs",
    "lib.arch",
    "lib.multiarch",
    "lib.iptables_libs",
    "lib.kbd",
    "lib.security",
    "lib.oss",
    "lib.firmware",
    "lib.usr_lib",
    "lib.usr_include",
    "lib.var_lib",
    "lib.ssl_libs",
    "lib.iconv",
    "lib.tmpfiles",
    "lib.libinfo",
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
    if failures:
        print(f"\n  {len(failures)} of {len(results)} modules failed.")
    else:
        print(f"\n  {len(results)} modules passed.")
    return 0 if not failures else 1


# ---------------------------------------------------------------------------
# info / audit
# ---------------------------------------------------------------------------

def _cmd_info(args: List[str]) -> int:
    from lib.libinfo import lib_summary
    lib_path = args[0] if args else "/lib"
    info = lib_summary(lib_path=lib_path)
    print(info.render_table())
    return 0 if not info.issues else 1


def _cmd_audit(args: List[str]) -> int:
    from lib.fhs import LibHierarchyManager
    root = args[0] if args else "/"
    mgr = LibHierarchyManager(root=root)
    report = mgr.audit()
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.ok else 1


# ---------------------------------------------------------------------------
# ldd
# ---------------------------------------------------------------------------

def _cmd_ldd(args: List[str]) -> int:
    if not args:
        print("ldd: missing <elf-path>", file=sys.stderr)
        return 2
    from lib.ldd import Ldd
    ldd = Ldd()
    tree = ldd.trace(args[0])
    print(ldd.format_tree(tree))
    if tree.missing:
        print(f"ldd: {tree.missing_count} unresolved dependencies", file=sys.stderr)
        return 1
    return 0


# ---------------------------------------------------------------------------
# ldconfig
# ---------------------------------------------------------------------------

def _cmd_ldconfig(_args: List[str]) -> int:
    from lib.dynamic_linker import DynamicLinkerManager
    mgr = DynamicLinkerManager()
    result = mgr.ldconfig()
    print(json.dumps(result, indent=2))
    return 0


# ---------------------------------------------------------------------------
# depmod
# ---------------------------------------------------------------------------

def _cmd_depmod(args: List[str]) -> int:
    from lib.kernel_modules import DEFAULT_KERNEL_VERSION, KernelModuleManager
    kernel_version = args[0] if args else DEFAULT_KERNEL_VERSION
    mgr = KernelModuleManager(kernel_version=kernel_version)
    try:
        out = mgr.depmod()
    except TypeError:
        # depmod takes no args in some revisions.
        out = mgr.depmod()
    if isinstance(out, str):
        print(out)
    elif isinstance(out, list):
        for line in out:
            print(line)
    else:
        print(f"depmod: wrote {out} dep entries for {kernel_version}")
    return 0


# ---------------------------------------------------------------------------
# modprobe / lsmod
# ---------------------------------------------------------------------------

def _cmd_modprobe(args: List[str]) -> int:
    if not args:
        print("modprobe: missing <module-name>", file=sys.stderr)
        return 2
    from lib.kernel_modules import KernelModuleManager
    name = args[0]
    remove = "-r" in args
    mgr = KernelModuleManager()
    if remove:
        result = mgr.rmmod(name)
        print(f"rmmod: {name} -> {result.value}")
        return 0 if result.value == "ok" else 1
    # modprobe returns an int (count loaded) or ModuleLoadResult
    res = mgr.modprobe(name)
    if hasattr(res, "value"):
        print(f"modprobe: {name} -> {res.value}")
        return 0 if res.value == "ok" else 1
    print(f"modprobe: {name} -> {res}")
    return 0


def _cmd_lsmod(_args: List[str]) -> int:
    from lib.kernel_modules import KernelModuleManager
    mgr = KernelModuleManager()
    for mod in mgr.list_loaded_modules() if hasattr(mgr, "list_loaded_modules") else []:
        size = getattr(mod, "size", 0)
        refs = len(getattr(mod, "dependencies", []))
        print(f"{mod.name:30} {size:>8}  {refs} deps")
    return 0


# ---------------------------------------------------------------------------
# cpplink
# ---------------------------------------------------------------------------

def _cmd_cpplink(_args: List[str]) -> int:
    from lib.fhs import LibHierarchyManager
    mgr = LibHierarchyManager()
    try:
        path = mgr.ensure_cpp_reference(prefer_symlink=True)
    except TypeError:
        # Some revisions take no keyword.
        path = mgr.ensure_cpp_reference()
    print(f"/lib/cpp -> {path}")
    return 0


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

def _cmd_list(_args: List[str]) -> int:
    from lib.essential_libs import EssentialLibraryManager
    mgr = EssentialLibraryManager()
    for lib in mgr.list_libraries():
        link = f" -> {lib.symlink_target}" if lib.symlink_target else ""
        print(f"  {lib.path}  ({lib.size_bytes:>10} B){link}")
    print(f"\n  {mgr.get_summary()['total_entries']} essential libraries registered.")
    return 0


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_TABLE = {
    "selftest":  _cmd_selftest,
    "info":      _cmd_info,
    "audit":     _cmd_audit,
    "ldd":       _cmd_ldd,
    "ldconfig":  _cmd_ldconfig,
    "depmod":    _cmd_depmod,
    "modprobe":  _cmd_modprobe,
    "lsmod":     _cmd_lsmod,
    "cpplink":   _cmd_cpplink,
    "list":      _cmd_list,
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
