"""
Umer OS Initrd /linuxrc (a.k.a. /init)
======================================
The PID 1 program that runs *inside* the initrd.  Maps one-to-one to
the eight phases of the TLDP ``/initrd`` reference.

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
Licence: Apache 2.0
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
from initrd.phase_machine import BootPhase, PhaseMachine, PhaseOutcome
from initrd.pivot_root import pivot_ramdisk_to
from initrd.ramdisk import RamDisk
from initrd.scenarios import (
    InitrdScenario, ScenarioId, ScenarioRunner, get_scenario,
)
from initrd.vfs_ops import VfsRoot

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
        return cls(
            request=request,
            ramdisk=ramdisk,
            host_root=host_root,
            interactive=request.scenario in (ScenarioId.INSTALL,
                                            ScenarioId.RECOVERY,
                                            ScenarioId.RESCUE),
        )

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
    ctx.ramdisk.mount("/")
    machine.finish_phase(rec, note="initrd mounted at /")

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
    machine.finish_phase(rec, note="module list resolved")

    # -- Phase 5: mount the real root FS ----------------------------------
    rec = machine.begin_phase(BootPhase.PHASE_5_MOUNT_REAL)
    await ctx.hooks.run_async(HookPoint.PRE_MOUNT_REAL_ROOT, {"ctx": ctx})
    _populate_real_root(ctx, scenario)
    await ctx.hooks.run_async(HookPoint.POST_MOUNT_REAL_ROOT, {"ctx": ctx})
    machine.finish_phase(rec, note="real root FS mounted at /newroot")

    # -- Phase 6: pivot_root ---------------------------------------------
    if scenario.keep_as_root:
        machine.skip_phase("scenario keeps initrd as final root")
    else:
        rec = machine.begin_phase(BootPhase.PHASE_6_PIVOT_ROOT)
        await ctx.hooks.run_async(HookPoint.PRE_PIVOT_ROOT, {"ctx": ctx})
        result = pivot_ramdisk_to(ctx.ramdisk, ctx.real_root)
        await ctx.hooks.run_async(HookPoint.POST_PIVOT_ROOT, {"ctx": ctx,
                                                              "result": result})
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
    ctx.ramdisk.release()
    machine.finish_phase(rec, note="initrd memory released")

    # -- Report -----------------------------------------------------------
    _write_report(ctx, machine)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _populate_real_root(ctx: BootContext, scenario: InitrdScenario) -> None:
    """Create a minimal ``/newroot`` tree inside ``ctx.real_root``."""
    ctx.real_root.mkdir("/newroot", parents=True, mode=0o755)
    ctx.real_root.mkdir("/newroot/bin", mode=0o755)
    ctx.real_root.mkdir("/newroot/etc", mode=0o755)
    ctx.real_root.mkdir("/newroot/sbin", mode=0o755)
    ctx.real_root.touch("/newroot/etc/hostname", data=b"umer-os\n")
    ctx.real_root.touch(
        "/newroot/etc/umeros/boot.log",
        data=_boot_log(ctx, scenario).encode("utf-8"),
    )
    log.info("real root populated at /newroot")


def _boot_log(ctx: BootContext, scenario: InitrdScenario) -> str:
    lines = [
        f"Umer OS initrd boot log",
        f"  kernel_version : {ctx.request.kernel_version}",
        f"  scenario       : {scenario.id.value}",
        f"  ai_enabled     : {ctx.ai.enabled}",
        f"  modules        : {sorted(s.name for s in ctx.resolver.list_selected())}",
        f"  files          : {ctx.ramdisk.stats.file_count}",
        f"  directories    : {ctx.ramdisk.stats.dir_count}",
        f"  symlinks       : {ctx.ramdisk.stats.symlink_count}",
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
            "ramdisk_stats":  ctx.ramdisk.stats.as_dict(),
        },
        "machine":  machine.summary(),
        "history":  machine.report(),
        "modules":  ctx.resolver.export(),
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
