"""
Umer OS Initrd CLI
==================
``python -m initrd ...`` - small command-line front-end for the
initrd package.

Sub-commands
------------

* ``selftest``                - run every module's self-test
* ``build <out>``             - build a default initramfs image
* ``inspect <image>``         - print the entries of a cpio image
* ``run <image>``             - boot the runtime over an image
* ``scenarios``               - list the built-in scenarios
* ``archivers``               - list the registered archivers
* ``plan <kernel-version>``   - show the build plan for a kernel version

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

from initrd.archivers import detect_archiver, list_archivers
from initrd.builder import BuildRequest, InitrdBuilder, OutputFormat
from initrd.cpio import unpack_archive
from initrd.linuxrc import BootContext, run
from initrd.scenarios import ScenarioId, list_scenarios

log = logging.getLogger("UmerOS.Initrd.CLI")


USAGE = """\
Umer OS initrd - pure-Python initramfs toolkit

Usage:
    python -m initrd <command> [args]

Commands:
    selftest                  Run the self-test of every module.
    build <out> [scenario]    Build a default initramfs image.
    inspect <image>           Print the entries of a cpio image.
    run <image>               Run the /init runtime over an image.
    scenarios                 List the built-in scenarios.
    archivers                 List the registered archivers.
    plan <kernel-version>     Show the build plan for a kernel.
    help                      Print this help text.
"""


def _cmd_selftest(_args: List[str]) -> int:
    results: List[tuple[str, bool]] = []
    for mod in ("initrd.archivers", "initrd.cpio", "initrd.vfs_ops",
                "initrd.ramdisk", "initrd.hooks", "initrd.phase_machine",
                "initrd.pivot_root", "initrd.module_resolver",
                "initrd.scenarios", "initrd.ai_helper", "initrd.builder",
                "initrd.linuxrc"):
        try:
            mod_obj = __import__(mod, fromlist=["_selftest"])
            ok = bool(mod_obj._selftest())  # noqa: SLF001
        except Exception as exc:  # noqa: BLE001
            ok = False
            log.error("%s selftest failed: %s", mod, exc)
        results.append((mod, ok))
    width = max(len(name) for name, _ in results)
    for name, ok in results:
        marker = "OK" if ok else "FAIL"
        print(f"  {name:<{width}}  [{marker}]")
    return 0 if all(ok for _, ok in results) else 1


def _cmd_build(args: List[str]) -> int:
    if not args:
        print("build: missing <out> path", file=sys.stderr)
        return 2
    out = args[0]
    scenario_id = args[1] if len(args) > 1 else "normal"
    try:
        scenario = ScenarioId(scenario_id)
    except ValueError:
        print(f"build: unknown scenario {scenario_id!r}", file=sys.stderr)
        return 2
    request = BuildRequest(
        kernel_version="cli-default",
        scenario=scenario,
        output_format=OutputFormat.CPIO_GZ,
        output_path=out,
    )
    builder = InitrdBuilder()
    result = builder.build(request)
    print(json.dumps(result.as_dict(), indent=2))
    return 0


def _cmd_inspect(args: List[str]) -> int:
    if not args:
        print("inspect: missing <image> path", file=sys.stderr)
        return 2
    path = Path(args[0])
    blob = path.read_bytes()
    archiver = detect_archiver(blob)
    if archiver.extension:
        print(f"# detected {archiver.__name__}; decompressing ...")
        blob = archiver.decompress(blob)
    entries = unpack_archive(blob)
    print(f"# {len(entries)} entries:")
    for entry in entries[:200]:
        kind = "d" if entry.is_dir() else ("l" if entry.is_symlink() else "f")
        size = len(entry.data) if entry.is_regular() else 0
        target = f" -> {entry.target}" if entry.is_symlink() else ""
        print(f"  {kind} {oct(entry.mode)} {size:>10}  {entry.name}{target}")
    if len(entries) > 200:
        print(f"  ... and {len(entries) - 200} more")
    return 0


def _cmd_run(args: List[str]) -> int:
    if not args:
        print("run: missing <image> path", file=sys.stderr)
        return 2
    path = Path(args[0])
    blob = path.read_bytes()
    archiver = detect_archiver(blob)
    if archiver.extension:
        blob = archiver.decompress(blob)
    request = BuildRequest(kernel_version="cli-run", scenario=ScenarioId.NORMAL)
    ctx = BootContext.from_request(request, blob=blob)
    return run(ctx)


def _cmd_scenarios(_args: List[str]) -> int:
    for sid in list_scenarios():
        from initrd.scenarios import get_scenario
        s = get_scenario(sid)
        print(f"  {sid.value:<12}  {s.title}")
    return 0


def _cmd_archivers(_args: List[str]) -> int:
    for name in list_archivers():
        print(f"  {name}")
    return 0


def _cmd_plan(args: List[str]) -> int:
    if not args:
        print("plan: missing <kernel-version>", file=sys.stderr)
        return 2
    kv = args[0]
    request = BuildRequest(kernel_version=kv)
    print(json.dumps(request.to_dict(), indent=2))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("help", "-h", "--help"):
        print(USAGE)
        return 0
    cmd, rest = args[0], args[1:]
    table = {
        "selftest":  _cmd_selftest,
        "build":     _cmd_build,
        "inspect":   _cmd_inspect,
        "run":       _cmd_run,
        "scenarios": _cmd_scenarios,
        "archivers": _cmd_archivers,
        "plan":      _cmd_plan,
    }
    if cmd not in table:
        print(f"unknown command: {cmd}\n\n{USAGE}", file=sys.stderr)
        return 2
    return table[cmd](rest)


if __name__ == "__main__":
    sys.exit(main())
