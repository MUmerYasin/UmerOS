# UmerOS /drivers — Kernel driver subsystem
# ==========================================
# GPL-3.0 — see LICENSE and README for details.
#
# A Python simulation of the Linux driver model.  The public API is
# kept stable; individual subsystems (USB, NVMe, I2C, …) live in
# sibling modules and are re-exported below.
#
# Modules
# -------
# device             - Device base class + registry.
# bus                - Bus / bus_type abstraction.
# platform_driver    - Platform driver binding.
# device_registry    - Global DEVICE_REGISTRY.
# media, pwrseq, hsi, interconnect, ntb, nvme, soundwire, virtio,
# remoteproc, rpmsg, phy, led, …  (subsystem drivers).
# driver_service     - HTTP /proc API (H64 fail-closed).
"""
UmerOS /drivers — Kernel driver subsystem.
"""

from __future__ import annotations

import logging
from typing import List

__version__ = "1.0.0"
__all__: list[str] = []

log = logging.getLogger("UmerOS.Drivers")


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
    ("example_driver", (
        "DriverManager", "DriverBase",
        "DisplayDriver", "StorageDriver",
        "NetworkDriver", "AudioDriver",
    )),
    ("media", (
        "MediaSubsystem", "MediaDevice", "MediaEntity",
        "MediaType", "MediaPadType",
    )),
    ("pwrseq", (
        "PWRSEQSubsystem", "PWRSEQSequence", "PWRSEQStep", "PWRSEQState",
    )),
    ("hsi", (
        "HSISubsystem", "HSIChannel", "HSIMessage",
        "HSIClient", "HSIMsgType",
    )),
    ("interconnect", (
        "ICCSubsystem", "ICCProvider", "ICCNode", "ICCBandwidth",
    )),
    ("ntb", (
        "NTBSubsystem", "NTBTransport", "NTBDevice", "NTBState", "NTBSpeed",
    )),
    ("nvme", (
        "NVMeSubsystem", "NVMeController", "NVMeNamespace",
        "NVMeCommand", "NVMEStatus",
    )),
    ("soundwire", (
        "SDWSubsystem", "SDWController", "SDWDevice",
        "SDWStream", "SDWState",
    )),
    ("virtio", (
        "VirtIOSubsystem", "VirtIODevice", "Virtqueue",
        "VirtIOStatus", "VirtIODeviceType",
    )),
    ("remoteproc", (
        "RprocSubsystem", "RprocDevice", "RprocState", "RprocCrashType",
    )),
    ("rpmsg", (
        "RPMsgSubsystem", "RPMsgDevice", "RPMsgEndpoint", "RPMsgMessage",
    )),
    ("phy", (
        "PHYSubsystem", "PHYDevice", "PHYProvider", "PHYMode", "PHYState",
    )),
    ("led", (
        "LEDSubsystem", "LEDDevice", "LEDState", "LEDTrigger", "LEDColor",
    )),
):
    _try_import(_mod, _names)


def _selftest() -> bool:
    """Verify the public surface is intact."""
    import importlib
    import sys

    pkg = importlib.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        print(
            f"drivers selftest FAIL: missing {missing}",
            file=sys.stderr,
        )
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
