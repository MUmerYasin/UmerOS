# UmerOS /dev — Device-file management
# ======================================
# GPL-3.0 — see LICENSE and README for details.
#
# /dev: device files (char/block/FIFO/socket/symlink),
# devtmpfs population, MAKEDEV / mknod / udevadm / losetup commands.
"""
UmerOS /dev — Device-file management.
"""

from __future__ import annotations

import logging
from typing import List

__version__ = "1.0.0"
__all__: list[str] = []

log = logging.getLogger("UmerOS.Dev")


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
    ("core", ("DeviceType", "DeviceNode", "DeviceManager", "get_device_manager")),
    ("null_device", ("NullDevice",)),
    ("zero_device", ("ZeroDevice",)),
    ("random_device", ("RandomDevice",)),
    ("full_device", ("FullDevice",)),
    ("tty_device", ("TTYDevice",)),
    ("ptmx_device", ("PtmxDevice",)),
    ("fd_device", ("FdDevice",)),
    ("devtmpfs", ("DevTmpFS",)),
    ("makedev", ("MAKEDEVCommand",)),
    ("mknod_virtual", ("MknodVirtualCommand",)),
    ("udevadm", ("UdevadmCommand",)),
    ("losetup", ("LosetupCommand",)),
    ("input_device", ("InputDevice",)),
    ("pts_device", ("PtsDevice",)),
    ("shm_device", ("ShmDevice",)),
    ("block_devices", ("BlockDeviceLinks",)),
    ("char_devices", ("CharDeviceLinks",)),
    ("disk_device", ("DiskDeviceLinks",)),
    ("net_device", ("NetDevice",)),
    ("usb_device", ("UsbDevice",)),
    ("dri_device", ("DriDevice",)),
    ("snd_device", ("SndDevice",)),
    ("log_device", ("LogDevice",)),
    ("mapper_device", ("MapperDevice",)),
    ("memory_devices", ("MemoryDevice", "KernelMemoryDevice", "PortDevice")),
    ("scsi_devices", (
        "SCSIBlockDevice", "SCSIGenericDevice",
        "SCSITapeDevice", "SCSIBSGDevice",
    )),
    ("nvme_devices", ("NVMeController", "NVMeNamespace")),
    ("virtual_devices", (
        "KVMDevice", "TUNDevice", "VhostNetDevice", "VhostVSockDevice",
        "VhostUserDevice", "VHCIDevice", "CUSEDevice", "VSockDevice",
    )),
    ("fuse_device", ("FuseDevice",)),
    ("misc_char_devices", (
        "UHIDDevice", "UserfaultfdDevice", "HPETDevice", "PPPDevice",
        "WatchdogDevice", "IntelEtherDevice", "PSAUXDevice",
        "AGPGARTDevice", "TPMDevice", "SnapshotDevice", "McelogDevice",
    )),
    ("i2c_devices", ("I2CDevice",)),
    ("hugepages_device", ("HugePagesDevice",)),
    ("mqueue_device", ("MQueueDevice",)),
    ("loop_control", ("LoopControlDevice",)),
    ("usb_serial_device", ("USBSerialDevice",)),
    ("hidraw_device", ("HidrawDevice",)),
    ("uinput_device", ("UinputDevice",)),
    ("framebuffer_device", ("FramebufferDevice",)),
    ("media_device", ("MediaDevice",)),
    ("parallel_device", ("ParallelDevice",)),
    ("misc_system_devices", (
        "BtrfsControlDevice", "DAXDevice", "VGAArbiterDevice",
    )),
    ("virtualization_devices", ("VFIODevice", "DmaBufHeap", "MdevDevice")),
    ("modern_devices", (
        "GpioCharDevice", "ZramDevice", "UserfaultfdNode",
        "UsbGadgetDevice", "NvmeGenericDevice",
        "PtpClockDevice", "RfKillDevice",
    )),
    ("udev_modern", (
        "UeventNetlinkMonitor", "DeviceTagRegistry",
        "PredictableNamingPolicy", "SystemdDeviceUnits", "MknodPolicy",
    )),
    ("ioctl_codec", ("IoctlCodec",)),
    ("kmsg_rtc", ("KmsgRing", "RtcWakeDevice")),
    ("io_subsystems", (
        "UsbmonTracer", "IioBufferDevice",
        "LoopModernOps", "TunModernOps",
    )),
):
    _try_import(_mod, _names)


def _selftest() -> bool:
    """Verify the public surface of the /dev package."""
    import importlib
    import sys

    pkg = importlib.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        print(f"dev selftest FAIL: missing {missing}", file=sys.stderr)
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
