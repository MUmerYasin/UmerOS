"""
UmerOS /dev/i2c-* — I2C bus devices.

Linux /dev/i2c-* (major 89):
  /dev/i2c-0 through /dev/i2c-31 — I2C bus adapters.
  Provides userspace access to I2C bus via i2c-dev driver.
  Used for sensor reading, EEPROM access, display configuration.

  ioctls:
    I2C_SLAVE = 0x0703    — Set slave address
    I2C_SLAVE_FORCE = 0x0706
    I2C_RDWR = 0x0707     — Combined read/write
    I2C_SMBUS = 0x0720    — SMBus transaction

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.I2CDevices")


class I2CDevice:
    """/dev/i2c-* — I2C bus adapter devices.

    Each I2C bus adapter is exposed as /dev/i2c-N.
    Provides ioctl-based access for I2C master operations.
    """

    MAJOR = 89
    MAX_BUSES = 32

    I2C_SLAVE = 0x0703
    I2C_SLAVE_FORCE = 0x0706
    I2C_RDWR = 0x0707
    I2C_SMBUS = 0x0720

    def __init__(self):
        self._buses: Dict[int, Dict[str, Any]] = {}
        self._register_devices()
        log.info("I2CDevice: registered %d I2C buses", self.MAX_BUSES)

    def _register_devices(self) -> None:
        mgr = DeviceManager.get_instance()
        for i in range(self.MAX_BUSES):
            minor = i
            mgr.create_node(DeviceNode(
                name=f"i2c-{i}", path=f"/dev/i2c-{i}",
                dev_type=DeviceType.CHAR,
                major=self.MAJOR, minor=minor, mode=0o666,
                description=f"I2C bus adapter {i}",
                ioctl_callback=lambda r, a, n=i: self._ioctl(r, a, n),
                read_callback=lambda sz, n=i: self._read(sz, n),
                write_callback=lambda d, n=i: self._write(d, n),
            ))
            self._buses[i] = {
                "slave_addr": 0,
                "attached_devices": [],
            }

    def _ioctl(self, request: int, arg: Any, bus_id: int) -> int:
        bus = self._buses.get(bus_id, {})
        if request == self.I2C_SLAVE:
            bus["slave_addr"] = arg
            return 0
        if request == self.I2C_SLAVE_FORCE:
            bus["slave_addr"] = arg
            return 0
        if request == self.I2C_RDWR:
            return 0
        if request == self.I2C_SMBUS:
            return 0
        return -1

    def _read(self, size: int, bus_id: int) -> bytes:
        return b"\x00" * size

    def _write(self, data: bytes, bus_id: int) -> int:
        return len(data)

    def attach_device(self, bus_id: int, addr: int) -> bool:
        if bus_id not in self._buses:
            return False
        if addr not in self._buses[bus_id]["attached_devices"]:
            self._buses[bus_id]["attached_devices"].append(addr)
        log.info("I2C: attached device 0x%02x on bus %d", addr, bus_id)
        return True

    def detach_device(self, bus_id: int, addr: int) -> bool:
        if bus_id not in self._buses:
            return False
        devices = self._buses[bus_id]["attached_devices"]
        if addr in devices:
            devices.remove(addr)
            return True
        return False

    def get_info(self) -> Dict[str, Any]:
        return {
            "max_buses": self.MAX_BUSES,
            "major": self.MAJOR,
            "active_buses": list(self._buses.keys()),
        }
