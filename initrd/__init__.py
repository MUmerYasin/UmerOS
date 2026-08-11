"""
Umer OS /initrd
===============
A pure-Python implementation of Linux's ``/initrd`` (initial RAM disk)
runtime, builder and tools, tailored to Umer OS.

This package is the runtime companion to the image-inventory module
in :mod:`boot.initrd_manager`.  It implements the eight boot phases
from the TLDP reference (see
https://tldp.org/LDP/Linux-Filesystem-Hierarchy/html/initrd.html) and
adds UmerOS-specific extras (post-quantum ready hooks, AI-driven
module suggestion, scenario-based recovery).

Public surface
--------------

* :class:`initrd.ramdisk.RamDisk`            - in-memory tmpfs stand-in
* :class:`initrd.ramdisk.RamDiskState`        - lifecycle states
* :class:`initrd.cpio.CpioEntry`              - one cpio record
* :func:`initrd.cpio.pack_archive`            - newc writer
* :func:`initrd.cpio.unpack_archive`          - newc reader
* :func:`initrd.archivers.get_archiver`       - lookup by name
* :func:`initrd.archivers.detect_archiver`    - magic-byte detect
* :class:`initrd.phase_machine.PhaseMachine`  - eight-phase state machine
* :class:`initrd.hooks.HookManager`           - initramfs-tools-style hooks
* :func:`initrd.pivot_root.pivot_root`        - new/old root swap
* :class:`initrd.module_resolver.ModuleResolver`
* :class:`initrd.ai_helper.AIHelper`
* :class:`initrd.scenarios.ScenarioId`        - install / live / recovery / etc.
* :class:`initrd.scenarios.SCENARIO_CATALOGUE`
* :class:`initrd.builder.InitrdBuilder`       - cpio image builder
* :class:`initrd.builder.BuildRequest`        - builder input
* :func:`initrd.linuxrc.run`                  - the eight-phase runner

Quick start
-----------

Build a real initramfs image and run it through the runtime::

    from initrd.builder import BuildRequest, InitrdBuilder, OutputFormat
    from initrd.scenarios import ScenarioId
    from initrd.linuxrc import BootContext, run

    request = BuildRequest(
        kernel_version="6.6.0-umeros",
        scenario=ScenarioId.NORMAL,
        output_format=OutputFormat.CPIO_GZ,
        output_path="initramfs-6.6.0-umeros.img.gz",
    )
    builder = InitrdBuilder()
    result = builder.build(request)
    print("built", result.output_path, "in", result.duration_seconds, "s")

    # Smoke test the runtime on the freshly built image.
    blob = result.sha256_final  # placeholder
    with open(result.output_path, "rb") as fh:
        from initrd.archivers import detect_archiver
        raw = detect_archiver(fh.read()).decompress(fh.seek(0) or fh.read())
    ctx = BootContext.from_request(request, blob=raw, host_root=os.getcwd())
    sys.exit(run(ctx))

CLI
---

The package also installs a small CLI: ``python -m initrd``.

See :mod:`initrd.__main__` for the supported sub-commands.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

__version__ = "2.0.0"
__all__ = [
    # foundation
    "archivers",
    "cpio",
    "vfs_ops",
    "ramdisk",
    # orchestration
    "hooks",
    "phase_machine",
    "pivot_root",
    "module_resolver",
    "scenarios",
    "ai_helper",
    # builder + runtime
    "builder",
    "linuxrc",
    "linuxrc_main",
]

# Re-export the most common names so callers can ``from initrd import X``.
from initrd.ai_helper import AIHelper
from initrd.archivers import (
    Archiver,
    GzipArchiver,
    Lz4Archiver,
    RawArchiver,
    XzArchiver,
    ZstdArchiver,
    detect_archiver,
    get_archiver,
    list_archivers,
)
from initrd.builder import (
    BuildRequest,
    BuildResult,
    InitrdBuilder,
    OutputFormat,
)
from initrd.cpio import (
    CpioEntry,
    newc_dir,
    newc_file,
    newc_symlink,
    pack_archive,
    unpack_archive,
)
from initrd.hooks import HookAbort, HookManager, HookPoint
from initrd.linuxrc import BootContext, run
from initrd.module_resolver import ModuleResolver, ModuleSpec
from initrd.phase_machine import BootPhase, PhaseMachine, PhaseOutcome
from initrd.pivot_root import PivotResult, pivot_root
from initrd.ramdisk import RamDisk, RamDiskState, RamDiskStats
from initrd.scenarios import (
    SCENARIO_CATALOGUE,
    InitrdScenario,
    ScenarioId,
    ScenarioRunner,
    get_scenario,
    list_scenarios,
)
from initrd.vfs_ops import VfsNode, VfsRoot
