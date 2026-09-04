# UmerOS /kernel/modules/dev — Kernel-level device subsystem
# ============================================================
# GPL-3.0 — see LICENSE and README for details.
#
# Re-exports the kernel-side device manager, hotplug bus, and udev
# rules engine.  This is the **kernel** view of the device tree;
# the user-space ``dev`` package is the matching **user** view.
#
# Author: UmerOS Project
# License: GPL-3.0 (GNU General Public License Version 3)
"""
UmerOS /kernel/modules/dev — Kernel-level device subsystem.
"""

from __future__ import annotations

import logging
from typing import List

__version__ = "1.0.0"
__all__: list[str] = []

log = logging.getLogger("UmerOS.Kernel.Dev")


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


for _mod, _names in (
    ("device_manager", ("DeviceManager", "DeviceNode", "DeviceType")),
    ("hotplug", (
        "HotplugBus", "HotplugEvent", "HotplugEventType", "HotplugSimulator",
    )),
    ("udev_rules", (
        "UdevAction", "UdevEvent", "UdevRule", "UdevRulesEngine",
    )),
):
    _try_import(_mod, _names)


def create_dev_subsystem(dev_path: str | None = None):
    """Create a complete device subsystem wired together.

    Args:
        dev_path: Path to ``/dev`` (default: ``/dev``).

    Returns:
        Tuple of ``(device_manager, rules_engine, hotplug_bus, simulator)``.
    """
    DeviceManager = globals().get("DeviceManager")
    HotplugBus = globals().get("HotplugBus")
    HotplugSimulator = globals().get("HotplugSimulator")
    if not all([DeviceManager, HotplugBus, HotplugSimulator]):
        raise ImportError(
            "kernel.modules.dev: required symbols are not importable; "
            "check that device_manager, hotplug, udev_rules modules exist.",
        )
    device_manager = DeviceManager(dev_path)
    hotplug_bus = HotplugBus(device_manager)
    rules_engine = hotplug_bus.rules_engine
    simulator = HotplugSimulator(hotplug_bus)
    return device_manager, rules_engine, hotplug_bus, simulator


def _selftest() -> bool:
    """Verify the public surface is importable."""
    import importlib
    import sys

    pkg = importlib.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        print(
            f"kernel.modules.dev selftest FAIL: missing {missing}",
            file=sys.stderr,
        )
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
