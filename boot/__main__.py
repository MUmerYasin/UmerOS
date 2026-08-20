"""
Umer OS /boot CLI
=================

``python -m boot <command>`` - small command-line front-end for the
``boot`` package, mirroring the style of ``python -m lib``,
``python -m initrd`` and ``python -m root``.

Sub-commands
------------

* ``selftest``              - run every module's self-test
* ``info [path]``           - one-shot /boot summary
* ``audit [path]``          - FHS / TLDP audit
* ``bzimage <vmlinuz>``     - parse a bzImage header
* ``efi <image>``           - parse a PE/COFF (UKI / EFI stub) image
* ``cmdline <preset|str>``  - print a preset kernel command line, or
                              parse + validate a supplied one
* ``grub [path]``           - summarise the GRUB2 menu (delegates to
                              GrubManager)
* ``bls [path]``            - enumerate BLS Type #1 entries under
                              /loader/entries
* ``uki [path]``            - enumerate UKI (Type #2) images under
                              /EFI/Linux
* ``kernels [path]``        - list installed kernels
* ``help``                  - print this help text

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

log = logging.getLogger("UmerOS.Boot.CLI")


USAGE = """\
Umer OS /boot - boot filesystem CLI

Usage:
    python -m boot <command> [args]

Commands:
    selftest                Run the self-test of every boot module.
    info [path]             Print a one-shot /boot summary.
    audit [path]            Run the FHS / TLDP audit and report issues.
    bzimage <path>          Parse a bzImage header.
    efi <path>              Parse a PE/COFF (UKI / EFI stub) image.
    cmdline <preset|str>    Print a preset cmdline, or parse a supplied one.
    grub [path]             Summarise the GRUB2 menu.
    bls [path]              Enumerate BLS Type #1 entries.
    uki [path]              Enumerate UKI (Type #2) images.
    kernels [path]          List installed kernels.
    help                    Print this help text.
"""


# ---------------------------------------------------------------------------
# Self-test runner
# ---------------------------------------------------------------------------

_SELFTEST_MODULES = (
    "boot.kernel_image",
    "boot.boot_params",
    "boot.boot_splash",
    "boot.bootloader",
    "boot.crash_kernel",
    "boot.efi_system",
    "boot.grub_manager",
    "boot.initrd_manager",
    "boot.microcode",
    "boot.systemd_boot",
    "boot.bzimage",
    "boot.efi_stub",
    "boot.cmdline",
    "boot.info",
    "boot.fhs",
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
# info / audit
# ---------------------------------------------------------------------------

def _cmd_info(args: List[str]) -> int:
    from boot.info import boot_summary
    path = args[0] if args else "/boot"
    s = boot_summary(boot_path=path)
    print(s.render_table())
    return 0 if s.exists else 1


def _cmd_audit(args: List[str]) -> int:
    from boot.fhs import FHSBootAuditor
    path = args[0] if args else "/boot"
    auditor = FHSBootAuditor(boot_dir=path)
    report = auditor.audit()
    print(report.render())
    return 0 if report.ok else 1


# ---------------------------------------------------------------------------
# bzimage / efi
# ---------------------------------------------------------------------------

def _cmd_bzimage(args: List[str]) -> int:
    if not args:
        print("bzimage: missing <path>", file=sys.stderr)
        return 2
    from boot.bzimage import parse_bzimage_header
    hdr = parse_bzimage_header(args[0])
    print(json.dumps(hdr.as_dict(), indent=2))
    return 0 if hdr.is_linux or hdr.efi_stub else 1


def _cmd_efi(args: List[str]) -> int:
    if not args:
        print("efi: missing <path>", file=sys.stderr)
        return 2
    from boot.efi_stub import parse_efi_image
    img = parse_efi_image(args[0])
    print(json.dumps(img.as_dict(), indent=2))
    return 0 if img.is_efi_stub else 1


# ---------------------------------------------------------------------------
# cmdline
# ---------------------------------------------------------------------------

def _cmd_cmdline(args: List[str]) -> int:
    from boot.cmdline import (
        PRESETS, parse_cmdline, preset, validate,
    )
    if not args:
        print("available presets:")
        for k in sorted(PRESETS):
            print(f"  {k:<10}  {PRESETS[k]}")
        return 0
    arg = args[0]
    if arg in PRESETS:
        print(preset(arg))
        return 0
    parsed = parse_cmdline(arg)
    print("parsed:", json.dumps(parsed.as_dict(), indent=2))
    issues = validate(arg)
    if issues:
        print("validation issues:")
        for i in issues:
            print(f"  [{i.code}] {i.message}")
        return 1
    return 0


# ---------------------------------------------------------------------------
# grub / bls / uki / kernels
# ---------------------------------------------------------------------------

def _cmd_grub(args: List[str]) -> int:
    from boot.grub_manager import GrubManager
    boot = args[0] if args else "/boot"
    mgr = GrubManager(Path(boot) / "grub")
    cfg = mgr.parse()
    print(f"grub config: {cfg.path or '(generated)'}")
    print(f"  default:  {cfg.default_entry}")
    print(f"  timeout:  {cfg.timeout}s")
    print(f"  entries:  {len(cfg.entries)}")
    for e in cfg.entries:
        print(f"    - {e.title!r}  -> {e.linux or '(no linux)'}")
    return 0


def _cmd_bls(args: List[str]) -> int:
    from boot.systemd_boot import SystemdBootManager, BootEntry
    boot = args[0] if args else "/boot"
    sbm = SystemdBootManager(Path(boot) / "loader")
    entries = sbm.list_entries()
    print(f"BLS Type #1 entries in {boot}/loader/entries:")
    if not entries:
        print("  (none)")
        return 0
    for e in entries:
        print(f"  - {e.path.name}  title={e.title!r}  "
              f"version={e.version!r}  linux={e.linux!r}")
    return 0


def _cmd_uki(args: List[str]) -> int:
    from boot.efi_stub import EfiStubInspector
    boot = args[0] if args else "/boot"
    ins = EfiStubInspector(Path(boot))
    ukis = ins.find_ukis()
    print(f"UKI (BLS Type #2) images under {boot}:")
    if not ukis:
        print("  (none)")
        return 0
    for u in ukis:
        print(f"  - {u.path}")
        print(f"      machine:  0x{u.machine:04x}  "
              f"subsystem:  0x{u.subsystem:04x}")
        print(f"      sections: {', '.join(u.uki_sections) or '(none)'}")
    return 0


def _cmd_kernels(args: List[str]) -> int:
    from boot.kernel_image import KernelImageManager
    boot = args[0] if args else "/boot"
    mgr = KernelImageManager(Path(boot))
    if not mgr.kernels:
        print(f"(no kernels in {boot})")
        return 1
    for v, k in sorted(mgr.kernels.items()):
        marker = "*" if v == mgr.default_version else " "
        print(f"  {marker} {v:<30}  arch={k.architecture.value:<10}  "
              f"comp={k.compression.value:<6}  "
              f"sig={k.signature_type.value:<8}  "
              f"size={k.vmlinuz_size}")
    return 0


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_TABLE = {
    "selftest":  _cmd_selftest,
    "info":      _cmd_info,
    "audit":     _cmd_audit,
    "bzimage":   _cmd_bzimage,
    "efi":       _cmd_efi,
    "cmdline":   _cmd_cmdline,
    "grub":      _cmd_grub,
    "bls":       _cmd_bls,
    "uki":       _cmd_uki,
    "kernels":   _cmd_kernels,
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
