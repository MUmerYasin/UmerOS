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
Umer OS Initrd /linuxrc (a.k.a. /init)
======================================
The PID 1 program that runs *inside* the initrd.  Maps one-to-one to
the eight phases of the ``/initrd`` reference.

This module is the orchestrator: it owns the :class:`PhaseMachine`,
the :class:`HookManager`, the active :class:`RamDisk`, the
:class:`ModuleResolver`, the :class:`AIHelper`, and a
:class:`ScenarioRunner`.  The actual work in each phase is delegated
to a private :func:`_phase_*` coroutine, but the public surface is
just :func:`run`.

Usage from a script that lives *inside* the initrd::

    #!/usr/bin/env python3
    from initrd.linuxrc import run
    run()

Usage from the host (for tests and demos)::

    from initrd.linuxrc import run, BootContext
    ctx = BootContext.from_request(req, blob=cpio_bytes)
    run(ctx)

The :class:`BootContext` carries everything :func:`run` needs; the
top-level :func:`run()` is a thin wrapper that builds a default
context when called from ``init`` (no arguments available).

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Optional

from initrd.ai_helper import AIHelper
from initrd.builder import BuildRequest
from initrd.cpio import CpioEntry, newc_dir, newc_file, newc_symlink
from initrd.hooks import HookAbort, HookManager, HookPoint
from initrd.module_resolver import ModuleResolver, ModuleSpec
from initrd.mounts import (
    ChrootContext, FilesystemType, MountFlag, MountTable, InitrdMountRecord,
    chroot_into, chroot_undo, mount, mount_dev, mount_proc, mount_sys,
    populate_dev, resolve_in_chroot, unmount,
)
from initrd.phase_machine import BootPhase, PhaseMachine, PhaseOutcome
from initrd.pivot_root import pivot_ramdisk_to
from initrd.ramdisk import RamDisk
from initrd.scenarios import (
    InitrdScenario, ScenarioId, ScenarioRunner, get_scenario,
)
from initrd.signals import InitSignal, PID1SignalHandler
from initrd.vfs_ops import VfsRoot

# [FIX H92] Zero-trust capability gate for the most privileged boot op
# (acquiring uid 0).  Falls back to a permissive stub if the shared gate
# module is unavailable so the import is never a boot blocker.
try:
    from core.capability_gate import CAP_SYS_ADMIN, gate
except Exception:  # pragma: no cover - import safety net
    class _GateFallback:
        """Permissive stand-in when the real gate is not importable."""

        def require(self, *args, **kwargs) -> None:  # always allow
            return None

    gate = _GateFallback()
    CAP_SYS_ADMIN = "sys.admin"

log = logging.getLogger("UmerOS.Initrd.Linuxrc")


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

@dataclass
class BootContext:
    """Everything :func:`run` needs to complete the eight phases."""

    request: BuildRequest
    ramdisk: RamDisk
    resolver: ModuleResolver = field(default_factory=ModuleResolver)
    ai: AIHelper = field(default_factory=AIHelper)
    hooks: HookManager = field(default_factory=HookManager)
    real_root: VfsRoot = field(default_factory=VfsRoot)
    extra_modules: List[str] = field(default_factory=list)
    extra_cpio: bytes = b""
    host_root: str = "/"
    log_path: str = "/var/log/umeros_initrd.log"
    interactive: bool = False
    #: The mount table the runtime uses to record every mount.
    mount_table: MountTable = field(default_factory=MountTable)
    #: PID 1 signal handler (auto-installed when env allows it).
    signal_handler: PID1SignalHandler = field(default_factory=PID1SignalHandler)
    #: Active chroot context, if any.
    chroot_ctx: Optional[ChrootContext] = None
    #: Effective uid at boot - the spec says /linuxrc runs as uid 0.
    effective_uid: int = 0
    #: Optional path to a "saved initrd image" produced on teardown.
    save_image_path: Optional[str] = None

    # -- factories --------------------------------------------------------

    @classmethod
    def from_request(
        cls,
        request: BuildRequest,
        blob: bytes = b"",
        host_root: str = "/",
    ) -> "BootContext":
        """Build a context from a :class:`BuildRequest` + a cpio blob."""
        ramdisk = RamDisk(
            name=f"initrd-{request.kernel_version}",
            mount_point="/",
        )
        ramdisk.load(blob)
        ctx = cls(
            request=request,
            ramdisk=ramdisk,
            host_root=host_root,
            interactive=request.scenario in (ScenarioId.INSTALL,
                                            ScenarioId.RECOVERY,
                                            ScenarioId.RESCUE),
        )
        ctx.mount_table = ramdisk.mount_table
        # Register default reap + signal handlers.
        ctx.signal_handler.on_reap(lambda pid: True)
        ctx.signal_handler.on(InitSignal.SIGUSR1, lambda pid: log.info("config reload"))
        return ctx

    @classmethod
    def default_demo(cls) -> "BootContext":
        """Default context used by :func:`run` when called with no args."""
        from initrd.cpio import pack_archive
        entries: List[CpioEntry] = [
            newc_dir("bin"),
            newc_dir("etc"),
            newc_file("init", b"#!/bin/sh\necho hi\n", mode=0o755),
            newc_file("etc/hostname", b"umer-os\n"),
            newc_symlink("bin/sh", "bin/busybox"),
        ]
        blob = pack_archive(entries)
        req = BuildRequest(
            kernel_version="demo",
            scenario=ScenarioId.NORMAL,
        )
        return cls.from_request(req, blob=blob, host_root=os.getcwd())


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def run(context: Optional[BootContext] = None) -> int:
    """Run the full eight-phase boot.  Returns the process exit code."""
    ctx = context or BootContext.default_demo()
    try:
        asyncio.run(_run_async(ctx))
    except HookAbort as abort:
        log.error("boot aborted by hook: %s", abort)
        return 2
    except Exception as exc:  # noqa: BLE001
        log.exception("boot failed: %s", exc)
        return 1
    if ctx.hooks._aborted:  # noqa: SLF001 - intentional
        return 2
    return 0


async def _run_async(ctx: BootContext) -> None:
    """Coroutine form of :func:`run`."""
    log.info("===== Umer OS /init starting =====")
    log.info("kernel=%s scenario=%s",
             ctx.request.kernel_version, ctx.request.scenario.value)
    log.info("AI helper enabled: %s", ctx.ai.enabled)
    # : /linuxrc is run with uid 0.  We try the real setuid
    # first (no-op when already root, harmless when not) and fall
    # back to recording the intended uid for the report.
    ctx.effective_uid = _drop_to_root()

    # Try to install real signal handlers (only works as PID 1).
    if ctx.signal_handler.install():
        log.info("signal handler installed for host signals")

    scenario = get_scenario(ctx.request.scenario)
    scenario_runner = ScenarioRunner(scenario)
    machine = PhaseMachine()

    # Apply scenario-level configuration BEFORE we start the machine
    # so the module list and extra files are available during phase 5.
    scenario_runner.apply_modules(ctx.resolver)
    ctx.extra_modules.extend(scenario.extra_modules)

    # -- Phase 1: bootloader loads the kernel + initial RAM disk ---------
    rec = machine.begin_phase(BootPhase.PHASE_1_LOAD)
    await ctx.hooks.run_async(HookPoint.PRE_LOAD, {"ctx": ctx})
    # The kernel has already done the heavy lifting by the time /init
    # runs - we just acknowledge it.
    await asyncio.sleep(0)  # yield to event loop
    machine.finish_phase(rec, note="kernel + cpio handed to userspace")

    # -- Phase 2: kernel converts initrd into a normal RAM disk -----------
    rec = machine.begin_phase(BootPhase.PHASE_2_CONVERT)
    await ctx.hooks.run_async(HookPoint.PRE_EXTRACT, {"ctx": ctx})
    ctx.ramdisk.extract()
    await ctx.hooks.run_async(HookPoint.POST_EXTRACT, {"ctx": ctx})
    machine.finish_phase(rec, note=f"extracted {ctx.ramdisk.stats.file_count} files")

    # -- Phase 3: initrd is mounted read-write as root --------------------
    rec = machine.begin_phase(BootPhase.PHASE_3_MOUNT_ROOT)
    ctx.ramdisk.mount("/", read_only=False)
    # Populate the basic pseudo filesystems the rest of the boot
    # needs: /dev, /proc, /sys.  These are real mounts inside the
    # initrd so the install / recovery scripts can use them.
    mount_dev(ctx.mount_table, ctx.ramdisk.root, mount_point="/dev")
    mount_proc(ctx.mount_table, ctx.ramdisk.root, mount_point="/proc")
    mount_sys(ctx.mount_table, ctx.ramdisk.root, mount_point="/sys")
    machine.finish_phase(rec, note="initrd mounted rw at /, /dev, /proc, /sys live")

    # -- Phase 4: /linuxrc (us) is executed as PID 1 ----------------------
    rec = machine.begin_phase(BootPhase.PHASE_4_LINUXRC)
    # Now we can ask the AI helper for module suggestions.
    suggested = ctx.ai.suggest_modules(
        list(ctx.resolver.selected.keys()),
        host_root=ctx.host_root,
    )
    for suggestion in suggested:
        spec = ctx.resolver._lookup(suggestion.name)  # noqa: SLF001
        if spec is None:
            continue
        ctx.resolver.selected[suggestion.name] = ModuleSpec(
            name=spec.name,
            parameters=dict(spec.parameters),
            dependencies=list(spec.dependencies),
            source=f"ai:suggest:{suggestion.reason}",
        )
    await ctx.hooks.run_async(HookPoint.PRE_MODULE_PROBE, {"ctx": ctx})
    # Hybrid resolver: autoprobe + user.
    ctx.resolver.hybrid(ctx.host_root, extras=ctx.extra_modules)
    await ctx.hooks.run_async(HookPoint.POST_MODULE_PROBE,
                              {"ctx": ctx,
                               "modules": ctx.resolver.export()})
    machine.finish_phase(rec, note=f"resolved {len(ctx.resolver.selected)} modules")

    # -- Phase 5: mount the real root FS ----------------------------------
    rec = machine.begin_phase(BootPhase.PHASE_5_MOUNT_REAL)
    await ctx.hooks.run_async(HookPoint.PRE_MOUNT_REAL_ROOT, {"ctx": ctx})
    _mount_real_root(ctx, scenario)
    await ctx.hooks.run_async(HookPoint.POST_MOUNT_REAL_ROOT, {"ctx": ctx})
    machine.finish_phase(rec, note="real root FS mounted at /newroot")

    # -- Phase 5b: install scenario chroots into the new root -----------
    if ctx.request.scenario == ScenarioId.INSTALL:
        try:
            ctx.chroot_ctx = chroot_into(ctx.ramdisk.root, "/newroot", new_cwd="/")
            log.info("install: chroot -> /newroot (active until installer exits)")
        except FileNotFoundError as exc:
            log.warning("install: chroot skipped (%s)", exc)

    # -- Phase 6: pivot_root ---------------------------------------------
    if scenario.keep_as_root:
        # Tear down any active chroot before continuing.
        if ctx.chroot_ctx is not None:
            chroot_undo(ctx.chroot_ctx)
            ctx.chroot_ctx = None
        machine.skip_phase("scenario keeps initrd as final root")
    else:
        rec = machine.begin_phase(BootPhase.PHASE_6_PIVOT_ROOT)
        await ctx.hooks.run_async(HookPoint.PRE_PIVOT_ROOT, {"ctx": ctx})
        result = pivot_ramdisk_to(ctx.ramdisk, ctx.real_root)
        # "file systems mounted under initrd continue to be accessible"
        # (note) - record the carry-over mounts for the report.
        await ctx.hooks.run_async(HookPoint.POST_PIVOT_ROOT, {"ctx": ctx,
                                                              "result": result,
                                                              "carried_mounts":
                                                                  ctx.mount_table.list()})
        machine.finish_phase(rec, note=f"pivot took {result.duration_seconds:.4f}s")

    # -- Phase 7: exec /sbin/init ----------------------------------------
    rec = machine.begin_phase(BootPhase.PHASE_7_EXEC_INIT)
    await ctx.hooks.run_async(HookPoint.PRE_INIT, {"ctx": ctx})
    # The actual exec happens in the host kernel; we just log it.
    log.info("would exec /sbin/init (kernel takes over from here)")
    machine.finish_phase(rec, note="transferred control to /sbin/init")

    # -- Phase 8: initrd FS is removed -----------------------------------
    rec = machine.begin_phase(BootPhase.PHASE_8_TEARDOWN)
    await ctx.hooks.run_async(HookPoint.CLEANUP, {"ctx": ctx})
    # Install scenarios may want to save the modified initrd back to
    # disk ("the image is written from /dev/ram0 to a file").
    if ctx.save_image_path and ctx.ramdisk.state != RamDiskState.PROBED:
        try:
            ctx.ramdisk.write_snapshot(ctx.save_image_path, archiver="gzip")
        except RuntimeError as exc:
            log.warning("save_image skipped: %s", exc)
    ctx.ramdisk.release()
    machine.finish_phase(rec, note="initrd memory released")

    # -- Report -----------------------------------------------------------
    _write_report(ctx, machine)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _drop_to_root() -> int:
    """Try to set the effective uid to 0 ( ``/linuxrc`` runs as uid 0).

    Returns the resulting effective uid.  In a real kernel this is a
    no-op when the process is already root, and the only way to call
    it from a non-root caller is via the setuid bit on the ``/init``
    binary.  When the host refuses (Windows has no ``geteuid``/
    ``seteuid``) we simply record the intended uid (0) so the rest
    of the boot proceeds correctly.

    [FIX H92] Acquiring uid 0 is the single most privileged operation in the
    boot path.  It is gated behind ``CAP_SYS_ADMIN`` so a wired zero-trust
    ``CapabilityManager`` (or strict mode) can refuse it; the refusal
    propagates and aborts the boot fail-closed instead of silently running
    as a non-privileged PID 1.  When no trust source is wired the gate is
    permissive (the historical default), so the boot is unchanged.
    """
    # [FIX H92] Require the capability FIRST, before any platform short-circuit,
    # so the zero-trust check applies on every platform (including ones without a
    # POSIX uid model) and a denial fails the boot rather than being skipped.
    gate.require(CAP_SYS_ADMIN)
    if not hasattr(os, "geteuid"):
        # Windows / no POSIX uid model - record the contract value.
        return 0
    try:
        if os.geteuid() != 0 and hasattr(os, "seteuid"):
            os.seteuid(0)
        return os.geteuid()
    except (PermissionError, OSError, AttributeError):
        return 0


def _mount_real_root(ctx: BootContext, scenario: InitrdScenario) -> None:
    """Mount the real root FS at ``/newroot`` inside the running initrd.

    For the install scenario this models the
    ``mount -t auto /dev/sda2 /newroot`` step where the user (or the
    autoprobe) decided which device the real root lives on.  For
    other scenarios we just stub out a real-root VFS and register
    the mount in the table.
    """
    device = "/dev/sda2"
    fstype = FilesystemType.EXT4
    ro = scenario.id == ScenarioId.LIVE  # live media is read-only
    flags: List[MountFlag] = [MountFlag.RDONLY] if ro else []

    ctx.real_root.mkdir("/newroot", parents=True, mode=0o755)
    ctx.real_root.mkdir("/newroot/bin", mode=0o755)
    ctx.real_root.mkdir("/newroot/etc", mode=0o755)
    ctx.real_root.mkdir("/newroot/sbin", mode=0o755)
    ctx.real_root.touch("/newroot/etc/hostname", data=b"umer-os\n")
    ctx.real_root.touch(
        "/newroot/etc/umeros/boot.log",
        data=_boot_log(ctx, scenario).encode("utf-8"),
    )
    mount(ctx.mount_table,
          device=device,
          fstype=fstype,
          mount_point="/newroot",
          flags=flags,
          source=ctx.real_root,
          description=f"real root from {device} ({fstype.value}, "
                      f"{'ro' if ro else 'rw'})")
    log.info("real root mounted at /newroot (%s, %s)",
             fstype.value, 'ro' if ro else 'rw')


def _boot_log(ctx: BootContext, scenario: InitrdScenario) -> str:
    lines = [
        f"Umer OS initrd boot log",
        f"  kernel_version : {ctx.request.kernel_version}",
        f"  scenario       : {scenario.id.value}",
        f"  ai_enabled     : {ctx.ai.enabled}",
        f"  effective_uid  : {ctx.effective_uid}",
        f"  modules        : {sorted(s.name for s in ctx.resolver.list_selected())}",
        f"  files          : {ctx.ramdisk.stats.file_count}",
        f"  directories    : {ctx.ramdisk.stats.dir_count}",
        f"  symlinks       : {ctx.ramdisk.stats.symlink_count}",
        f"  mounts         : {[m.mount_point for m in ctx.mount_table.list()]}",
        f"  raw_bytes      : {ctx.ramdisk.stats.raw_bytes}",
        f"  ext_bytes      : {ctx.ramdisk.stats.extracted_bytes}",
    ]
    return "\n".join(lines) + "\n"


def _write_report(ctx: BootContext, machine: PhaseMachine) -> None:
    """Persist the boot report somewhere visible to the operator."""
    report = {
        "context": {
            "kernel_version": ctx.request.kernel_version,
            "scenario":       ctx.request.scenario.value,
            "host_root":      ctx.host_root,
            "effective_uid":  ctx.effective_uid,
            "ramdisk_stats":  ctx.ramdisk.stats.as_dict(),
        },
        "machine":        machine.summary(),
        "history":        machine.report(),
        "modules":        ctx.resolver.export(),
        "mounts":         [m.as_dict() for m in ctx.mount_table.list()],
        "signal_history": ctx.signal_handler.history(),
        "reaped_pids":    ctx.signal_handler.reaped(),
    }
    text = json.dumps(report, indent=2, default=str)
    try:
        path = Path(ctx.host_root) / ctx.log_path.lstrip("/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        log.warning("could not write boot report to %s: %s", ctx.log_path, exc)
    log.info("boot report:\n%s", text)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    ctx = BootContext.default_demo()
    code = run(ctx)
    if code != 0:
        return False
    return ctx.ramdisk.state.value == "released"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("linuxrc selftest:", "OK" if _selftest() else "FAIL")
