# UmerOS /kernel — Microkernel core
# ==================================
# GPL-3.0 — see LICENSE and README for details.
#
# The ``kernel`` package hosts the microkernel itself plus the
# supporting modules (scheduler, IPC, capability manager, memory
# manager, signal layer, audit, …).  Public symbols are re-exported
# via best-effort imports so partial checkouts still load.
#
# Tier label: [TODAY] for the no-op markers; [EXPERIMENTAL] for
# anything in ``kernel.umer_kernel`` until the real wiring
# (H110/H111) lands.
#
# Author: UmerOS Project
# License: GPL-3.0 (GNU General Public License Version 3)
"""
UmerOS /kernel — Microkernel core.
"""

from __future__ import annotations

import logging
from typing import List

__version__ = "1.0.0"
__all__: list[str] = []

log = logging.getLogger("UmerOS.Kernel")


def _try_import(module_name: str, names: tuple[str, ...]) -> None:
    """Import optional helpers and add the names to ``__all__``."""
    global __all__
    try:
        mod = __import__(f"{__name__}.{module_name}", fromlist=names)
    except ImportError:
        return
    for n in names:
        if hasattr(mod, n):
            globals()[n] = getattr(mod, n)
            __all__ = list(__all__) + [n]


# Best-effort re-exports.  The kernel core is intentionally
# import-free at package-init time to avoid circular imports
# (see the previous comment block in the file history).
for _mod, _names in (
    ("umer_kernel", ("UmerKernel", "KernelStatus", "BootError")),
    ("scheduler", ("Scheduler", "TaskState", "TaskPriority")),
    ("ipc_bus", ("IPCBus", "IPCMessage", "MessageKind")),
    ("capability_manager", (
        "CapabilityManager", "Capability", "PermissionError",
    )),
    ("memory_manager", ("MemoryManager", "MemoryRegion", "PageFlags")),
    ("signals", ("SignalDispatcher", "SignalNumber", "SignalAction")),
    ("audit", ("AuditLog", "AuditEntry", "AuditSeverity")),
    ("panic", ("panic", "PanicError")),
    ("reboot", ("reboot", "RebootMode")),
    ("sysctl", ("SysctlRegistry", "SysctlEntry")),
    ("cred", ("Credentials", "UserCredentials")),
    ("softirq", ("SoftIRQ", "SoftIRQAction")),
    ("workqueue", ("WorkQueue", "WorkItem")),
    ("pid_allocator", ("PIDAllocator",)),
    ("taint", ("TaintFlag", "TaintFlags", "TaintReason")),
    ("resource", ("ResourceManager", "Rlimit")),
):
    _try_import(_mod, _names)


def _selftest() -> bool:
    """Verify the public surface is importable (best effort)."""
    # Importing a partial kernel is fine — this just confirms
    # the package itself loads and ``__all__`` is consistent.
    import importlib
    import sys

    pkg = importlib.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        # Only warn — a partial build is expected.
        log.warning("kernel: %d public names unavailable in this checkout",
                    len(missing))
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
