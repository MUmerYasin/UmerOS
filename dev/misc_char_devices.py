"""
UmerOS /dev — Miscellaneous character devices.

 /dev structure covered:
  /dev/uhid         — User-space HID (major 10:239)
  /dev/userfaultfd  — User page fault handling (major 10:128)
  /dev/hpet         — High Precision Event Timer (char 10:228)
  /dev/ppp          — PPP tunnel device (major 108)
  /dev/watchdog     — Hardware watchdog (major 10:130)
  /dev/watchdog0    — First watchdog (major 10:130)
  /dev/ice          — Intel Ethernet (major 248:0+)
  /dev/psaux        — PS/2 auxiliary port (major 10:1)
  /dev/agpgart      — AGP graphics (major 10:175)
  /dev/tpm0         — TPM 1.2 (char 10:224)
  /dev/tpmrm0       — TPM Resource Manager (char 10:224+)
  /dev/snapshot     — System snapshot (major 10:231)
  /dev/mcelog       — Machine Check Exception (major 10:227)

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.MiscCharDevices")


class UHIDDevice:
    """/dev/uhid — User-space HID device.

    Allows userspace to create virtual HID devices. The kernel
    sees them as real USB HID devices. Used by pipeewire,
    android-input, and Bluetooth HID profiles.
    """

    MAJOR = 10
    MINOR = 239

    UHID_CREATE2 = 0x4D485531
    UHID_DESTROY = 0x4D485532
    UHID_START = 0x4D485533
    UHID_STOP = 0x4D485534
    UHID_OPEN = 0x4D485535
    UHID_CLOSE = 0x4D485536
    UHID_INPUT = 0x4D485537

    def __init__(self):
        self._devices: Dict[int, Dict[str, Any]] = {}
        self._register()
        log.info("UHIDDevice /dev/uhid created")

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="uhid", path="/dev/uhid", dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR, mode=0o666,
            description="User-space HID device",
            read_callback=self._read,
            write_callback=self._write,
            ioctl_callback=self._ioctl,
        ))

    def _read(self, size: int, offset: int = 0) -> bytes:
        return b"\x00" * size

    def _write(self, data: bytes, offset: int = 0) -> int:
        if len(data) >= 4:
            cmd = int.from_bytes(data[:4], "little")
            if cmd == self.UHID_CREATE2:
                dev_id = len(self._devices)
                self._devices[dev_id] = {"state": "created"}
                log.info("UHID: created device %d", dev_id)
            elif cmd == self.UHID_DESTROY:
                for dev_id in self._devices:
                    if self._devices[dev_id]["state"] == "created":
                        self._devices[dev_id]["state"] = "destroyed"
                        break
        return len(data)

    def _ioctl(self, request: int, arg: Any) -> int:
        return 0

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/uhid",
            "active_devices": sum(1 for v in self._devices.values()
                                  if v["state"] == "created"),
        }


class UserfaultfdDevice:
    """/dev/userfaultfd — User-space page fault handling.

    Allows monitoring page faults and handling them in userspace.
    Used by CRIU (checkpoint/restore), live migration, and
    user-space page management.
    """

    MAJOR = 10
    MINOR = 128

    UFFDIO_REGISTER = 0xC040AA00
    UFFDIO_UNREGISTER = 0x8008AA01
    UFFDIO_WAKE = 0x8008AA02
    UFFDIO_COPY = 0xC018AA03
    UFFDIO_ZEROPAGE = 0xC008AA04
    UFFDIO_WRITEPROTECT = 0xC010AA06
    UFFDIO_CONTINUE = 0xC018AA07

    def __init__(self):
        self._fds: Dict[int, Dict[str, Any]] = {}
        self._counter = 0
        self._register()
        log.info("UserfaultfdDevice /dev/userfaultfd created")

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="userfaultfd", path="/dev/userfaultfd",
            dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR, mode=0o666,
            description="User-space page fault handling",
            read_callback=self._read,
            write_callback=self._write,
            ioctl_callback=self._ioctl,
        ))

    def _read(self, size: int, offset: int = 0) -> bytes:
        return b"\x00" * size

    def _write(self, data: bytes, offset: int = 0) -> int:
        return len(data)

    def _ioctl(self, request: int, arg: Any) -> int:
        if request == self.UFFDIO_REGISTER:
            return 0
        if request == self.UFFDIO_UNREGISTER:
            return 0
        if request == self.UFFDIO_COPY:
            return 0
        return -1

    def get_info(self) -> Dict[str, Any]:
        return {"path": "/dev/userfaultfd", "active_fds": len(self._fds)}


class HPETDevice:
    """/dev/hpet — High Precision Event Timer.

    Provides access to the HPET hardware timer for precision
    timing. HPET provides at least 10MHz frequency timer.
    """

    MAJOR = 10
    MINOR = 228

    def __init__(self):
        self._register()
        log.info("HPETDevice /dev/hpet created")

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="hpet", path="/dev/hpet", dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR, mode=0o664,
            description="High Precision Event Timer",
            read_callback=self._read,
            ioctl_callback=self._ioctl,
        ))

    def _read(self, size: int, offset: int = 0) -> bytes:
        timestamp = int(time.time() * 1000000000)  # nanoseconds
        return timestamp.to_bytes(8, "little")[:size]

    def _ioctl(self, request: int, arg: Any) -> int:
        return 0

    def get_info(self) -> Dict[str, Any]:
        return {"path": "/dev/hpet", "major": self.MAJOR, "minor": self.MINOR}


class PPPDevice:
    """/dev/ppp — PPP tunnel device.

    Point-to-Point Protocol device used by pppd for dial-up
    VPNs, and PPPOE connections. The kernel PPP subsystem
    handles framing while pppd manages authentication.
    """

    MAJOR = 108

    def __init__(self):
        self._channels: Dict[int, Dict[str, Any]] = {}
        self._register()
        log.info("PPPDevice /dev/ppp created")

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="ppp", path="/dev/ppp", dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=0, mode=0o660,
            description="PPP tunnel device",
            ioctl_callback=self._ioctl,
        ))

    def _ioctl(self, request: int, arg: Any) -> int:
        return 0

    def get_info(self) -> Dict[str, Any]:
        return {"path": "/dev/ppp", "major": self.MAJOR, "channels": len(self._channels)}


class WatchdogDevice:
    """/dev/watchdog, /dev/watchdog0 — Hardware watchdog timer.

    The watchdog timer resets the system if not periodically
    "kicked" (petted) by the userspace daemon. Used for
    system reliability in embedded and server environments.
    """

    MAJOR = 10
    MINOR_START = 130
    MAX_WATCHDOGS = 8

    WDIOC_SETTIMEOUT = 0x40045706
    WDIOC_GETTIMEOUT = 0x40045707
    WDIOC_KEEPALIVE = 0x40045708
    WDIOC_GETTIMELEFT = 0x4004570A
    WDIOC_SETOPTIONS = 0x40045704

    def __init__(self):
        self._watchdogs: Dict[int, Dict[str, Any]] = {}
        self._register_devices()
        log.info("WatchdogDevice: registered %d watchdogs", self.MAX_WATCHDOGS)

    def _register_devices(self) -> None:
        mgr = DeviceManager.get_instance()
        for i in range(self.MAX_WATCHDOGS):
            minor = self.MINOR_START + i
            name = f"watchdog{i}" if i > 0 else "watchdog"
            mgr.create_node(DeviceNode(
                name=name, path=f"/dev/{name}",
                dev_type=DeviceType.CHAR,
                major=self.MAJOR, minor=minor, mode=0o660,
                description=f"Hardware watchdog {i}",
                ioctl_callback=lambda r, a, n=i: self._ioctl(r, a, n),
                write_callback=lambda d, n=i: self._on_write(d, n),
            ))
            self._watchdogs[i] = {
                "timeout": 30,
                "time_left": 30,
                "armed": False,
                "magic_char": b"\xff",
            }

    def _ioctl(self, request: int, arg: Any, wd_id: int) -> int:
        wd = self._watchdogs.get(wd_id, {})
        if request == self.WDIOC_SETTIMEOUT:
            wd["timeout"] = min(max(arg, 1), 60)
            wd["time_left"] = wd["timeout"]
            return 0
        if request == self.WDIOC_GETTIMEOUT:
            return wd.get("timeout", 30)
        if request == self.WDIOC_KEEPALIVE:
            wd["time_left"] = wd.get("timeout", 30)
            return 0
        if request == self.WDIOC_GETTIMELEFT:
            return wd.get("time_left", 0)
        if request == self.WDIOC_SETOPTIONS:
            wd["armed"] = bool(arg & 1)
            return 0
        return -1

    def _on_write(self, data: bytes, wd_id: int) -> int:
        wd = self._watchdogs.get(wd_id, {})
        if data and data[0:1] == wd.get("magic_char", b"\xff"):
            wd["armed"] = True
            log.info("Watchdog %d: armed", wd_id)
        return len(data)

    def get_info(self) -> Dict[str, Any]:
        return {
            "max_watchdogs": self.MAX_WATCHDOGS,
            "armed": [k for k, v in self._watchdogs.items() if v["armed"]],
        }


class IntelEtherDevice:
    """/dev/ice* — Intel Ethernet (ice driver) devices.

    Intel E1000 family Ethernet adapter control devices.
    Used for RDMA, SR-IOV, and hardware offload configuration.
    """

    MAJOR = 248
    MAX_DEVICES = 16

    def __init__(self):
        self._devices: Dict[int, Dict[str, Any]] = {}
        self._register_devices()
        log.info("IntelEtherDevice: registered %d ice devices", self.MAX_DEVICES)

    def _register_devices(self) -> None:
        mgr = DeviceManager.get_instance()
        for i in range(self.MAX_DEVICES):
            minor = i
            mgr.create_node(DeviceNode(
                name=f"ice{i}", path=f"/dev/ice{i}",
                dev_type=DeviceType.CHAR,
                major=self.MAJOR, minor=minor, mode=0o660,
                description=f"Intel Ethernet adapter {i}",
                ioctl_callback=lambda r, a, n=i: self._ioctl(r, a, n),
            ))
            self._devices[i] = {"active": False}

    def _ioctl(self, request: int, arg: Any, dev_id: int) -> int:
        return 0

    def get_info(self) -> Dict[str, Any]:
        return {"max_devices": self.MAX_DEVICES, "major": self.MAJOR}


class PSAUXDevice:
    """/dev/psaux — PS/2 auxiliary port (mouse).

    Legacy PS/2 mouse port device. On modern systems typically
    replaced by /dev/input/mice (evdev).
    """

    MAJOR = 10
    MINOR = 1

    def __init__(self):
        self._register()
        log.info("PSAUXDevice /dev/psaux created")

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="psaux", path="/dev/psaux",
            dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR, mode=0o666,
            description="PS/2 auxiliary port (mouse)",
            read_callback=self._read,
            write_callback=self._write,
        ))

    def _read(self, size: int, offset: int = 0) -> bytes:
        return b"\x00" * size

    def _write(self, data: bytes, offset: int = 0) -> int:
        return len(data)

    def get_info(self) -> Dict[str, Any]:
        return {"path": "/dev/psaux", "major": self.MAJOR, "minor": self.MINOR}


class AGPGARTDevice:
    """/dev/agpgart — AGP graphics device.

    Accelerated Graphics Port interface for direct GPU memory
    access. Largely replaced by DRM/KMS on modern systems.
    """

    MAJOR = 10
    MINOR = 175

    AGPIOC_INFO = 0x4100
    AGPIOC_ACQUIRE = 0x4101
    AGPIOC_RELEASE = 0x4102
    AGPIOC_SETUP = 0x4103
    AGPIOC_BIND = 0x4104
    AGPIOC_UNBIND = 0x4105

    def __init__(self):
        self._bound = False
        self._register()
        log.info("AGPGARTDevice /dev/agpgart created")

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="agpgart", path="/dev/agpgart",
            dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR, mode=0o660,
            description="AGP graphics device",
            ioctl_callback=self._ioctl,
        ))

    def _ioctl(self, request: int, arg: Any) -> int:
        if request == self.AGPIOC_INFO:
            return 0
        if request == self.AGPIOC_ACQUIRE:
            self._bound = True
            return 0
        if request == self.AGPIOC_RELEASE:
            self._bound = False
            return 0
        return -1

    def get_info(self) -> Dict[str, Any]:
        return {"path": "/dev/agpgart", "bound": self._bound}


class TPMDevice:
    """/dev/tpm0, /dev/tpmrm0 — Trusted Platform Module.

    TPM 1.2 (/dev/tpm0) and TPM 2.0 Resource Manager
    (/dev/tpmrm0) devices. Used for secure boot, disk
    encryption (LUKS/BitLocker), and remote attestation.
    """

    TPM_MAJOR = 10
    TPM_MINOR = 224
    TPMRM_MINOR = 225

    def __init__(self):
        self._register_devices()
        log.info("TPMDevice: created /dev/tpm0 and /dev/tpmrm0")

    def _register_devices(self) -> None:
        mgr = DeviceManager.get_instance()

        # /dev/tpm0 — TPM 1.2
        mgr.create_node(DeviceNode(
            name="tpm0", path="/dev/tpm0",
            dev_type=DeviceType.CHAR,
            major=self.TPM_MAJOR, minor=self.TPM_MINOR,
            mode=0o660,
            description="Trusted Platform Module 1.2",
            read_callback=self._read,
            write_callback=self._write,
            ioctl_callback=self._ioctl,
        ))

        # /dev/tpmrm0 — TPM 2.0 Resource Manager
        mgr.create_node(DeviceNode(
            name="tpmrm0", path="/dev/tpmrm0",
            dev_type=DeviceType.CHAR,
            major=self.TPM_MAJOR, minor=self.TPMRM_MINOR,
            mode=0o660,
            description="TPM 2.0 Resource Manager",
            read_callback=self._read,
            write_callback=self._write,
            ioctl_callback=self._ioctl,
        ))

    def _read(self, size: int, offset: int = 0) -> bytes:
        return b"\x00" * size

    def _write(self, data: bytes, offset: int = 0) -> int:
        return len(data)

    def _ioctl(self, request: int, arg: Any) -> int:
        return 0

    def get_info(self) -> Dict[str, Any]:
        return {
            "tpm0": {"path": "/dev/tpm0", "major": self.TPM_MAJOR, "minor": self.TPM_MINOR},
            "tpmrm0": {"path": "/dev/tpmrm0", "major": self.TPM_MAJOR, "minor": self.TPMRM_MINOR},
        }


class SnapshotDevice:
    """/dev/snapshot — System snapshot device.

    Used by /dev/snapshot for software suspend (hibernate).
    The kernel writes the full RAM contents to this device
    during hibernate, and reads it back during resume.
    """

    MAJOR = 10
    MINOR = 231

    SNAPSHOT_FREEZE = 0x3200
    SNAPSHOT_CREATE_IMAGE = 0x3201
    SNAPSHOT_AVAIL_SIZE = 0x3204
    SNAPSHOT_SET_IMAGE_SIZE = 0x3206
    SNAPSHOT_ATOMIC_RESTORE = 0x3209
    SNAPSHOT_PREFREEZE = 0x320B

    def __init__(self):
        self._frozen = False
        self._register()
        log.info("SnapshotDevice /dev/snapshot created")

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="snapshot", path="/dev/snapshot",
            dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR, mode=0o600,
            description="System snapshot (hibernate)",
            ioctl_callback=self._ioctl,
        ))

    def _ioctl(self, request: int, arg: Any) -> int:
        if request == self.SNAPSHOT_FREEZE:
            self._frozen = True
            log.info("snapshot: frozen")
            return 0
        if request == self.SNAPSHOT_AVAIL_SIZE:
            return 4 * 1024 * 1024 * 1024  # 4GB simulated
        if request == self.SNAPSHOT_ATOMIC_RESTORE:
            self._frozen = False
            log.info("snapshot: restored")
            return 0
        return -1

    def get_info(self) -> Dict[str, Any]:
        return {"path": "/dev/snapshot", "frozen": self._frozen}


class McelogDevice:
    """/dev/mcelog — Machine Check Exception log.

    Allows reading machine check exceptions (hardware errors)
    from the kernel. On modern kernels, replaced by
    /dev/mce/* (per-CPU MCE devices).
    """

    MAJOR = 10
    MINOR = 227

    def __init__(self):
        self._log: List[Dict[str, Any]] = []
        self._register()
        log.info("McelogDevice /dev/mcelog created")

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="mcelog", path="/dev/mcelog",
            dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR, mode=0o600,
            description="Machine Check Exception log",
            read_callback=self._read,
            ioctl_callback=self._ioctl,
        ))

    def _read(self, size: int, offset: int = 0) -> bytes:
        return b"\x00" * size

    def _ioctl(self, request: int, arg: Any) -> int:
        return 0

    def get_info(self) -> Dict[str, Any]:
        return {"path": "/dev/mcelog", "entries": len(self._log)}
