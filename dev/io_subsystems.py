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
UmerOS /dev I/O subsystems — usbmon tracing, IIO sensor buffers,
modern loop-device configuration and multi-queue TUN.

  UsbmonTracer   /dev/usbmon0 binary-API model (64-byte header, S/C/E
                 events, MON_IOC magic 0x92, mon_bin_stats).
  IioBufferDev   /dev/iio:device0 continuous capture with scan_elements
                 ("le:s16/32>>0" types) and int64 sample timestamps.
  LoopModernOps  LOOP_CONFIGURE / LOOP_SET_CAPACITY / SET_DIRECT_IO.
  TunModernOps   TUNSETIFF / TUNSETPERSIST / TUNSETQUEUE multiqueue.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from dev.core import DeviceManager, DeviceNode, DeviceType
from dev.ioctl_codec import IoctlCodec

log = logging.getLogger("UmerOS.Dev.IOSys")


class UsbmonTracer:
    """/dev/usbmonN — USB bus trace facility (binary API)."""

    PATH = "/dev/usbmon0"
    MON_IOC_MAGIC = 0x92

    def __init__(self):
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="usbmon0", path=self.PATH,
            dev_type=DeviceType.CHAR, major=10, minor=54, mode=0o600,
            description="USB monitor - all buses (mode must be 0600)",
            read_callback=self._on_read,
        ))
        self.events: List[Dict[str, Any]] = []
        self.dropped = 0
        self.iocq_urb_len = IoctlCodec.io(self.MON_IOC_MAGIC, 1)
        self.iocg_stats = IoctlCodec.ior(self.MON_IOC_MAGIC, 3, 8)
        log.info("UsbmonTracer created (%s)", self.PATH)

    def submit(self, xfer: str, bus: int, dev: int, ep: int, length: int) -> Dict[str, Any]:
        return self._record("S", xfer, bus, dev, ep, length)

    def callback(self, xfer: str, bus: int, dev: int, ep: int, length: int, status: int = 0) -> Dict[str, Any]:
        return self._record("C", xfer, bus, dev, ep, length, status)

    def _record(self, etype: str, xfer: str, bus: int, dev: int, ep: int,
                length: int, status: int = 0) -> Dict[str, Any]:
        if len(self.events) >= 128:
            self.events.pop(0)
            self.dropped += 1
        evt = {
            "type": etype,
            "xfer": xfer,                       # Bi/Bo/Ci/Co/Ii/Io/Zi/Zo
            "bus": bus, "devnum": dev, "epnum": ep,
            "status": status,
            "length": length,
            "ts_sec": int(time.time()),
            "ts_usec": time.monotonic_ns() // 1000 % 1_000_000,
        }
        self.events.append(evt)
        return evt

    def text_line(self, evt: Dict[str, Any]) -> str:
        addr = f"{evt['xfer']}:{evt['bus']}:{evt['devnum']:03d}:{evt['epnum']}"
        status = f"{evt['status']:d}" if evt["status"] else "-"
        return (f"{'-' * 16} {evt['ts_sec']}{evt['ts_usec']:06d} "
                f"{evt['type']} {addr} {status} {evt['length']} :")

    def _on_read(self, size: int) -> bytes:
        """read(2) compat: first 48 bytes of the newest event header."""
        line = self.text_line(self.events[-1]) if self.events else "no events"
        return line.encode()[:48]

    def stats(self) -> Dict[str, int]:
        return {"queued": len(self.events), "dropped": self.dropped}

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": self.PATH,
            "events": len(self.events),
            "stats": self.stats(),
            "iocq_urb_len": f"0x{self.iocq_urb_len:08x}",
            "iocg_stats": f"0x{self.iocg_stats:08x}",
        }

    def __repr__(self) -> str:
        return f"<UsbmonTracer events={len(self.events)}>"


class IioBufferDevice:
    """/dev/iio:device0 — Industrial I/O triggered buffer capture."""

    IIO_MAJOR = 242

    CHANNELS = (
        ("accel_x", "le:s16/32>>0", 0),
        ("accel_y", "le:s16/32>>0", 1),
        ("accel_z", "le:s16/32>>4", 2),
    )

    def __init__(self):
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="iio:device0", path="/dev/iio:device0",
            dev_type=DeviceType.CHAR, major=self.IIO_MAJOR, minor=0, mode=0o660,
            description="Industrial I/O accelerometer buffer",
            read_callback=self._on_read,
        ))
        self.buffer_length = 256
        self.enabled = False
        self.sampling_frequency_hz = 100
        self.scan_enabled = {name: True for name, _, _ in self.CHANNELS}
        log.info("IioBufferDevice created")

    @staticmethod
    def sysfs_view() -> Dict[str, Any]:
        base = "/sys/bus/iio/devices/iio:device0"
        return {
            "buffer": [f"{base}/buffer/length", f"{base}/buffer/enable"],
            "scan_elements": [
                f"{base}/scan_elements/in_accel_{ax}_en" for ax in ("x", "y", "z")
            ],
        }

    def start(self, frequency_hz: int = 100) -> Dict[str, Any]:
        self.sampling_frequency_hz = frequency_hz
        self.enabled = True
        return {"capturing": True, "hz": frequency_hz,
                "scan_order": [c[0] for c in self.CHANNELS]}

    def stop(self) -> None:
        self.enabled = False

    def read_sample(self) -> Dict[str, Any]:
        t_ns = time.time_ns()
        frame = {}
        order = 0
        for name, storage_type, _shift in self.CHANNELS:
            if not self.scan_enabled.get(name):
                continue
            frame[name] = {"type": storage_type, "raw": (t_ns >> (order * 5)) & 0xFFFF,
                           "storage_bytes": int(storage_type.split("/")[-1].split(">>")[0]) // 8}
            order += 1
        return {"timestamp_ns": t_ns, "scan": frame}

    def _on_read(self, size: int) -> bytes:
        sample = self.read_sample()
        payload = repr(sample["scan"]).encode()
        return payload[:size]

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/iio:device0",
            "enabled": self.enabled,
            "length": self.buffer_length,
            "sampling_hz": self.sampling_frequency_hz,
            "channels": {n: {"type": t, "enabled": self.scan_enabled[n]}
                         for n, t, _s in self.CHANNELS},
            "sysfs": self.sysfs_view(),
        }

    def __repr__(self) -> str:
        return f"<IioBufferDevice enabled={self.enabled}>"


class LoopModernOps:
    """Modern loop management: LOOP_CONFIGURE + online resize."""

    LOOP_CTL_GET_FREE = IoctlCodec.io(0x4C, 0)
    LOOP_CONFIGURE = IoctlCodec.iow(0x4C, 0x22, 64)
    LOOP_SET_CAPACITY = IoctlCodec.io(0x4C, 0x07)
    LOOP_SET_DIRECT_IO = IoctlCodec.io(0x4C, 0x08)

    def __init__(self):
        self._devices: Dict[int, Dict[str, Any]] = {}

    def configure(self, index: int, backing_fd_name: str, size_bytes: int,
                  direct_io: bool = False) -> Dict[str, Any]:
        self._devices[index] = {
            "backing_file": backing_fd_name,
            "size_bytes": size_bytes,
            "direct_io": direct_io,
            "autoclear": True,
            "configured_with": "LOOP_CONFIGURE",
        }
        log.debug("loop%d configured -> %s (%d bytes)", index, backing_fd_name, size_bytes)
        return dict(self._devices[index])

    def resize_online(self, index: int, new_size_bytes: int) -> Dict[str, Any]:
        dev = self._devices.get(index)
        if not dev:
            return {"ok": False, "error": "-ENXIO: loop device not configured"}
        old = dev["size_bytes"]
        dev["size_bytes"] = new_size_bytes
        return {"ok": True, "ioctl": "LOOP_SET_CAPACITY", "old": old, "new": new_size_bytes}

    def get_info(self) -> Dict[str, Any]:
        return {
            "devices": {str(k): v for k, v in sorted(self._devices.items())},
            "ioctls": {
                "LOOP_CONFIGURE": f"0x{self.LOOP_CONFIGURE:08x}",
                "LOOP_SET_CAPACITY": f"0x{self.LOOP_SET_CAPACITY:08x}",
            },
        }

    def __repr__(self) -> str:
        return f"<LoopModernOps n={len(self._devices)}>"


class TunModernOps:
    """Multi-queue TUN: TUNSETIFF / TUNSETPERSIST / TUNSETQUEUE."""

    TUNSETIFF = IoctlCodec.iowr(0x54, 202, 24)
    TUNSETPERSIST = IoctlCodec.iow(0x54, 203, 4)
    TUNSETOWNER = IoctlCodec.iow(0x54, 204, 4)
    TUNSETQUEUE = IoctlCodec.iow(0x54, 217, 8)

    def __init__(self):
        self.interfaces: Dict[str, Dict[str, Any]] = {}

    def attach(self, ifname: str, queues: int = 1, persistent: bool = False) -> Dict[str, Any]:
        self.interfaces[ifname] = {
            "queues": [{"id": q, "enabled": True} for q in range(max(1, queues))],
            "persistent": persistent,
            "mtu": 1500,
        }
        log.debug("tun %s attached with %d queue(s)", ifname, queues)
        return dict(self.interfaces[ifname])

    def set_queue(self, ifname: str, queue_id: int, enabled: bool) -> bool:
        iface = self.interfaces.get(ifname)
        if not iface:
            return False
        for q in iface["queues"]:
            if q["id"] == queue_id:
                q["enabled"] = enabled
                return True
        return False

    def get_info(self) -> Dict[str, Any]:
        return {"interfaces": self.interfaces,
                "tunsetiff": f"0x{self.TUNSETIFF:08x}"}

    def __repr__(self) -> str:
        return f"<TunModernOps ifaces={len(self.interfaces)}>"
