"""
UmerOS SPI Subsystem
====================
Linux kernel-like Serial Peripheral Interface bus framework.
Implements SPI controllers, devices, drivers, and transfers.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# SPI Mode Constants
# ---------------------------------------------------------------------------
SPI_MODE_0: int = 0x00  # CPOL=0, CPHA=0
SPI_MODE_1: int = 0x01  # CPOL=0, CPHA=1
SPI_MODE_2: int = 0x02  # CPOL=1, CPHA=0
SPI_MODE_3: int = 0x03  # CPOL=1, CPHA=1
SPI_CPHA: int = 0x01
SPI_CPOL: int = 0x10
SPI_CS_HIGH: int = 0x04
SPI_LSB_FIRST: int = 0x08
SPI_3WIRE: int = 0x10
SPI_LOOP: int = 0x20
SPI_NO_CS: int = 0x40
SPI_READY: int = 0x80


# ---------------------------------------------------------------------------
# Core Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class SpiDevice:
    """SPI device on a bus."""
    bus_num: int
    chip_select: int
    name: str
    driver_name: str = ""
    mode: int = SPI_MODE_0
    bits_per_word: int = 8
    max_speed_hz: int = 1_000_000
    speed_hz: int = 1_000_000
    cs_gpio: int = -1
    driver: Optional["SpiDriver"] = None
    platform_data: dict = field(default_factory=dict)
    controller_data: dict = field(default_factory=dict)
    _registered: bool = False

    def __post_init__(self) -> None:
        if self.speed_hz == 0:
            self.speed_hz = self.max_speed_hz

    @property
    def cpol(self) -> bool:
        return bool(self.mode & SPI_CPOL)

    @property
    def cpha(self) -> bool:
        return bool(self.mode & SPI_CPHA)

    def __repr__(self) -> str:
        return (
            f"SpiDevice(bus={self.bus_num}, cs={self.chip_select}, "
            f"name={self.name!r}, mode={self.mode})"
        )


@dataclass
class SpiController:
    """SPI master controller (bus)."""
    bus_num: int
    name: str
    mode: int = SPI_MODE_0
    bits_per_word: int = 8
    max_speed_hz: int = 1_000_000
    num_chipselect: int = 1
    cs_gpios: list = field(default_factory=list)
    _devices: list = field(default_factory=list)
    _is_registered: bool = False

    def __repr__(self) -> str:
        return (
            f"SpiController(bus={self.bus_num}, name={self.name!r}, "
            f"devs={len(self._devices)}, cs_count={self.num_chipselect})"
        )


@dataclass
class SpiTransfer:
    """Single SPI transfer."""
    tx_buf: bytes = b""
    rx_buf: bytearray = field(default_factory=bytearray)
    len: int = 0
    speed_hz: int = 0
    delay_usecs: int = 0
    bits_per_word: int = 8
    cs_change: bool = False

    def __post_init__(self) -> None:
        if self.len == 0:
            self.len = max(len(self.tx_buf), len(self.rx_buf))
        if self.speed_hz == 0:
            self.speed_hz = 1_000_000
        if self.bits_per_word == 0:
            self.bits_per_word = 8

    @property
    def bytes_written(self) -> int:
        return len(self.tx_buf)

    @property
    def bytes_read(self) -> int:
        return len(self.rx_buf)

    def __repr__(self) -> str:
        return (
            f"SpiTransfer(tx={self.bytes_written}B, rx={self.bytes_read}B, "
            f"speed={self.speed_hz}Hz)"
        )


@dataclass
class SpiMessage:
    """Bundled SPI transfers."""
    transfers: list = field(default_factory=list)
    device: Optional[SpiDevice] = None
    is_completed: bool = False

    @property
    def total_length(self) -> int:
        return sum(t.len for t in self.transfers)

    def add_transfer(self, transfer: SpiTransfer) -> None:
        self.transfers.append(transfer)

    def __repr__(self) -> str:
        return (
            f"SpiMessage(xfers={len(self.transfers)}, "
            f"total={self.total_length}B, done={self.is_completed})"
        )


@dataclass
class SpiDriver:
    """SPI device driver."""
    name: str
    probe: Optional[Callable[[SpiDevice], bool]] = None
    remove: Optional[Callable[[SpiDevice], None]] = None
    id_table: list = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            f"SpiDriver(name={self.name!r}, id_table={self.id_table}, "
            f"probe={'yes' if self.probe else 'no'})"
        )


# ---------------------------------------------------------------------------
# Global Registries
# ---------------------------------------------------------------------------
_controllers: dict[int, SpiController] = {}
_devices: list[SpiDevice] = []
_drivers: dict[str, SpiDriver] = {}


# ---------------------------------------------------------------------------
# Registration Functions
# ---------------------------------------------------------------------------
def spi_register_controller(ctrl: SpiController) -> bool:
    """Register SPI controller - like spi_register_controller()."""
    if ctrl.bus_num in _controllers:
        print(f"[SPI] ERROR: controller bus {ctrl.bus_num} already registered")
        return False
    ctrl._is_registered = True
    _controllers[ctrl.bus_num] = ctrl
    print(f"[SPI] registered controller: {ctrl!r}")
    return True


def spi_unregister_controller(bus_num: int) -> bool:
    """Unregister controller."""
    ctrl = _controllers.pop(bus_num, None)
    if ctrl is None:
        print(f"[SPI] ERROR: no controller on bus {bus_num}")
        return False
    ctrl._is_registered = False
    for dev in ctrl._devices:
        dev._registered = False
    ctrl._devices.clear()
    print(f"[SPI] unregistered controller: bus {bus_num}")
    return True


def spi_register_driver(driver: SpiDriver) -> bool:
    """Register SPI driver - auto-binds to matching devices."""
    if driver.name in _drivers:
        print(f"[SPI] ERROR: driver {driver.name!r} already registered")
        return False
    _drivers[driver.name] = driver
    print(f"[SPI] registered driver: {driver!r}")
    _auto_bind(driver)
    return True


def spi_unregister_driver(driver_name: str) -> bool:
    """Unregister driver."""
    driver = _drivers.pop(driver_name, None)
    if driver is None:
        print(f"[SPI] ERROR: no driver {driver_name!r}")
        return False
    if driver.remove:
        for dev in list(_devices):
            if dev.driver is driver:
                try:
                    driver.remove(dev)
                except Exception as exc:
                    print(f"[SPI] remove failed for {dev!r}: {exc}")
                dev.driver = None
    print(f"[SPI] unregistered driver: {driver_name!r}")
    return True


def spi_register_device(device: SpiDevice) -> bool:
    """Register SPI device."""
    for d in _devices:
        if d.bus_num == device.bus_num and d.chip_select == device.chip_select:
            print(f"[SPI] ERROR: device bus={device.bus_num} cs={device.chip_select} exists")
            return False
    device._registered = True
    _devices.append(device)
    ctrl = _controllers.get(device.bus_num)
    if ctrl:
        ctrl._devices.append(device)
    print(f"[SPI] registered device: {device!r}")
    for driver in _drivers.values():
        _try_bind(driver, device)
    return True


def spi_unregister_device(bus_num: int, cs: int) -> bool:
    """Unregister device."""
    for idx, dev in enumerate(_devices):
        if dev.bus_num == bus_num and dev.chip_select == cs:
            if dev.driver and dev.driver.remove:
                try:
                    dev.driver.remove(dev)
                except Exception as exc:
                    print(f"[SPI] remove failed: {exc}")
            ctrl = _controllers.get(bus_num)
            if ctrl and dev in ctrl._devices:
                ctrl._devices.remove(dev)
            dev._registered = False
            dev.driver = None
            _devices.pop(idx)
            print(f"[SPI] unregistered device: bus={bus_num} cs={cs}")
            return True
    print(f"[SPI] ERROR: no device bus={bus_num} cs={cs}")
    return False


def spi_new_device(
    bus_num: int,
    chip_select: int,
    name: str,
    mode: int = SPI_MODE_0,
    max_speed: int = 1_000_000,
    driver_name: str = "",
) -> Optional[SpiDevice]:
    """Create and register new SPI device."""
    dev = SpiDevice(
        bus_num=bus_num,
        chip_select=chip_select,
        name=name,
        driver_name=driver_name,
        mode=mode,
        max_speed_hz=max_speed,
        speed_hz=max_speed,
    )
    if spi_register_device(dev):
        return dev
    return None


def spi_transfer_device(device: SpiDevice, transfers: list[SpiTransfer]) -> bool:
    """Execute transfers on device - like spi_transfer()."""
    if not device._registered:
        print(f"[SPI] ERROR: device {device!r} not registered")
        return False
    ctrl = _controllers.get(device.bus_num)
    if ctrl is None:
        print(f"[SPI] ERROR: no controller for bus {device.bus_num}")
        return False
    msg = SpiMessage(transfers=transfers, device=device)
    return spi_sync(device, msg)


def spi_write(device: SpiDevice, data: bytes) -> bool:
    """Write data to SPI device."""
    txf = SpiTransfer(tx_buf=data, len=len(data), speed_hz=device.speed_hz)
    print(f"[SPI] WRITE {len(data)}B to {device.name} (bus={device.bus_num}, cs={device.chip_select})")
    return spi_transfer_device(device, [txf])


def spi_read(device: SpiDevice, length: int) -> Optional[bytearray]:
    """Read data from SPI device."""
    rxf = SpiTransfer(
        rx_buf=bytearray(length),
        len=length,
        speed_hz=device.speed_hz,
    )
    print(f"[SPI] READ {length}B from {device.name} (bus={device.bus_num}, cs={device.chip_select})")
    ok = spi_transfer_device(device, [rxf])
    return rxf.rx_buf if ok else None


def spi_write_then_read(device: SpiDevice, tx_data: bytes, rx_len: int) -> Optional[bytearray]:
    """Full duplex write-then-read."""
    txf = SpiTransfer(tx_buf=tx_data, len=len(tx_data), speed_hz=device.speed_hz, cs_change=True)
    rxf = SpiTransfer(rx_buf=bytearray(rx_len), len=rx_len, speed_hz=device.speed_hz)
    print(
        f"[SPI] WRITE_THEN_READ {len(tx_data)}B -> {rx_len}B "
        f"on {device.name} (bus={device.bus_num}, cs={device.chip_select})"
    )
    ok = spi_transfer_device(device, [txf, rxf])
    return rxf.rx_buf if ok else None


def spi_sync(device: SpiDevice, message: SpiMessage) -> bool:
    """Synchronous message transfer."""
    if not device._registered:
        print(f"[SPI] ERROR: device not registered")
        return False
    total = message.total_length
    for xf in message.transfers:
        if xf.delay_usecs > 0:
            time.sleep(xf.delay_usecs / 1_000_000)
    message.is_completed = True
    print(
        f"[SPI] sync {len(message.transfers)} xfers, "
        f"{total}B on {device.name}"
    )
    return True


def spi_get_controller(bus_num: int) -> Optional[SpiController]:
    """Get controller by bus number."""
    return _controllers.get(bus_num)


def spi_busnum_to_device(bus_num: int, cs: int) -> Optional[SpiDevice]:
    """Find device by bus number and chip select."""
    for dev in _devices:
        if dev.bus_num == bus_num and dev.chip_select == cs:
            return dev
    return None


def spi_setup(device: SpiDevice) -> bool:
    """Setup device mode/speed - like spi_setup()."""
    ctrl = _controllers.get(device.bus_num)
    if ctrl is None:
        print(f"[SPI] ERROR: no controller for bus {device.bus_num}")
        return False
    device.speed_hz = min(device.speed_hz, ctrl.max_speed_hz)
    device.bits_per_word = device.bits_per_word or ctrl.bits_per_word
    print(
        f"[SPI] setup {device.name}: mode={device.mode}, "
        f"speed={device.speed_hz}Hz, bpw={device.bits_per_word}"
    )
    return True


def spi_set_speed(device: SpiDevice, speed_hz: int) -> bool:
    """Set transfer speed."""
    ctrl = _controllers.get(device.bus_num)
    if ctrl and speed_hz > ctrl.max_speed_hz:
        print(f"[SPI] WARN: speed {speed_hz}Hz > max {ctrl.max_speed_hz}Hz, clamping")
        speed_hz = ctrl.max_speed_hz
    device.speed_hz = speed_hz
    print(f"[SPI] {device.name}: speed -> {speed_hz}Hz")
    return True


def spi_set_mode(device: SpiDevice, mode: int) -> bool:
    """Set SPI mode."""
    if mode not in (SPI_MODE_0, SPI_MODE_1, SPI_MODE_2, SPI_MODE_3):
        print(f"[SPI] ERROR: invalid mode {mode}")
        return False
    device.mode = mode
    print(f"[SPI] {device.name}: mode -> {mode}")
    return True


# ---------------------------------------------------------------------------
# Internal Auto-Bind Helpers
# ---------------------------------------------------------------------------
def _auto_bind(driver: SpiDriver) -> None:
    for dev in _devices:
        if dev.driver is not None:
            continue
        _try_bind(driver, dev)


def _try_bind(driver: SpiDriver, device: SpiDevice) -> None:
    if not driver.id_table and device.driver_name:
        if driver.name == device.driver_name:
            _do_bind(driver, device)
        return
    if device.name in driver.id_table or device.driver_name in driver.id_table:
        _do_bind(driver, device)
        return
    if not driver.id_table and not device.driver_name:
        _do_bind(driver, device)


def _do_bind(driver: SpiDriver, device: SpiDevice) -> None:
    if driver.probe:
        try:
            ok = driver.probe(device)
        except Exception as exc:
            print(f"[SPI] probe({driver.name!r}) threw: {exc}")
            return
        if not ok:
            print(f"[SPI] probe({driver.name!r}) rejected {device!r}")
            return
    device.driver = driver
    print(f"[SPI] bound {driver.name!r} -> {device!r}")


# ---------------------------------------------------------------------------
# Built-in SPI Drivers
# ---------------------------------------------------------------------------
class SpidevDriver(SpiDriver):
    """Userspace SPI driver (like /dev/spidev)."""

    def __init__(self) -> None:
        super().__init__(
            name="spidev",
            id_table=["spidev"],
            probe=self._probe,
            remove=self._remove,
        )

    @staticmethod
    def _probe(dev: SpiDevice) -> bool:
        print(f"  [spidev] probing {dev.name} (bus={dev.bus_num}, cs={dev.chip_select})")
        dev.platform_data["mode"] = dev.mode
        dev.platform_data["bits_per_word"] = dev.bits_per_word
        dev.platform_data["max_speed_hz"] = dev.max_speed_hz
        print(f"  [spidev] configured: mode={dev.mode}, bpw={dev.bits_per_word}, max={dev.max_speed_hz}Hz")
        return True

    @staticmethod
    def _remove(dev: SpiDevice) -> None:
        print(f"  [spidev] removing {dev.name}")
        dev.platform_data.clear()


class EepromSpiDriver(SpiDriver):
    """SPI EEPROM driver (93C46, M95xxx, AT25xxx)."""

    def __init__(self) -> None:
        super().__init__(
            name="eeprom-spi",
            id_table=["m95256", "at25256", "93c46"],
            probe=self._probe,
            remove=self._remove,
        )

    @staticmethod
    def _probe(dev: SpiDevice) -> bool:
        print(f"  [eeprom] probing {dev.name}")
        dev.platform_data["type"] = dev.name
        dev.platform_data["page_size"] = 32
        dev.platform_data["size"] = 32_768
        print(f"  [eeprom] detected: page=32B, size=32KB")
        return True

    @staticmethod
    def _remove(dev: SpiDevice) -> None:
        print(f"  [eeprom] removing {dev.name}")
        dev.platform_data.clear()


class Max7219Driver(SpiDriver):
    """LED matrix driver (MAX7219/MAX7221)."""

    REG_NOOP = 0x00
    REG_DIGIT0 = 0x01
    REG_DECODE = 0x09
    REG_INTENSITY = 0x0A
    REG_SCAN = 0x0B
    REG_SHUTDOWN = 0x0C
    REG_TEST = 0x0F

    def __init__(self) -> None:
        super().__init__(
            name="max7219",
            id_table=["max7219", "max7221"],
            probe=self._probe,
            remove=self._remove,
        )

    @staticmethod
    def _probe(dev: SpiDevice) -> bool:
        print(f"  [max7219] probing {dev.name}")
        dev.platform_data["digits"] = 8
        dev.platform_data["intensity"] = 8
        print(f"  [max7219] initialized: 8 digits, intensity=8")
        return True

    @staticmethod
    def _remove(dev: SpiDevice) -> None:
        print(f"  [max7219] shutting down {dev.name}")
        dev.platform_data.clear()


class Ads1256Driver(SpiDriver):
    """ADC driver (ADS1256 24-bit ADC)."""

    CMD_WAKEUP = 0x00
    CMD_RDATA = 0x01
    CMD_RDATAC = 0x03
    CMD_SDATAC = 0x0F
    CMD_RREG = 0x10
    CMD_WREG = 0x50

    def __init__(self) -> None:
        super().__init__(
            name="ads1256",
            id_table=["ads1256"],
            probe=self._probe,
            remove=self._remove,
        )

    @staticmethod
    def _probe(dev: SpiDevice) -> bool:
        print(f"  [ads1256] probing {dev.name}")
        dev.platform_data["resolution"] = 24
        dev.platform_data["channels"] = 8
        dev.platform_data["sps"] = 30000
        print(f"  [ads1256] detected: 24-bit, 8ch, 30kSPS")
        return True

    @staticmethod
    def _remove(dev: SpiDevice) -> None:
        print(f"  [ads1256] removing {dev.name}")
        dev.platform_data.clear()


class W25qxxDriver(SpiDriver):
    """Flash driver (W25Qxx SPI NOR flash)."""

    CMD_READ_JEDEC_ID = 0x9F
    CMD_READ_DATA = 0x03
    CMD_PAGE_PROGRAM = 0x02
    CMD_SECTOR_ERASE = 0x20
    CMD_CHIP_ERASE = 0xC7
    CMD_WRITE_ENABLE = 0x06
    CMD_WRITE_DISABLE = 0x04
    CMD_READ_STATUS = 0x05

    def __init__(self) -> None:
        super().__init__(
            name="w25qxx",
            id_table=["w25q64", "w25q128", "w25q256", "w25qxx"],
            probe=self._probe,
            remove=self._remove,
        )

    @staticmethod
    def _probe(dev: SpiDevice) -> bool:
        print(f"  [w25qxx] probing {dev.name}")
        dev.platform_data["manufacturer_id"] = 0xEF
        dev.platform_data["capacity"] = 8_388_608
        dev.platform_data["page_size"] = 256
        print(f"  [w25qxx] detected: Winbond, 8MB, 256B pages")
        return True

    @staticmethod
    def _remove(dev: SpiDevice) -> None:
        print(f"  [w25qxx] removing {dev.name}")
        dev.platform_data.clear()


# ---------------------------------------------------------------------------
# Registration Utilities
# ---------------------------------------------------------------------------
def spi_get_controllers() -> dict[int, SpiController]:
    """Return all registered controllers."""
    return dict(_controllers)


def spi_get_devices() -> list[SpiDevice]:
    """Return all registered devices."""
    return list(_devices)


def spi_get_drivers() -> dict[str, SpiDriver]:
    """Return all registered drivers."""
    return dict(_drivers)


def spi_dump_state() -> None:
    """Print full SPI subsystem state."""
    print("\n=== SPI Subsystem State ===")
    print(f"Controllers: {len(_controllers)}")
    for ctrl in _controllers.values():
        print(f"  {ctrl!r}")
        for dev in ctrl._devices:
            drv = dev.driver.name if dev.driver else "none"
            print(f"    {dev!r} driver={drv!r}")
    unbound = [d for d in _devices if d.driver is None]
    if unbound:
        print(f"Unbound devices: {len(unbound)}")
        for dev in unbound:
            print(f"  {dev!r}")
    print(f"Drivers: {len(_drivers)}")
    for drv in _drivers.values():
        print(f"  {drv!r}")
    print("===========================\n")


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
def demo() -> None:
    print("=" * 60)
    print("  UmerOS SPI Subsystem Demo")
    print("=" * 60)

    # -- Create controllers --
    print("\n--- Creating SPI Controllers ---")
    spi_register_controller(SpiController(bus_num=0, name="spi0", num_chipselect=2))
    spi_register_controller(SpiController(bus_num=1, name="spi1", max_speed_hz=500_000))

    # -- Register devices --
    print("\n--- Registering SPI Devices ---")
    spi_new_device(bus_num=0, chip_select=0, name="spidev0.0", mode=SPI_MODE_0, max_speed=1_000_000, driver_name="spidev")
    spi_new_device(bus_num=0, chip_select=1, name="w25q64", mode=SPI_MODE_0, max_speed=80_000_000)
    spi_new_device(bus_num=1, chip_select=0, name="ads1256", mode=SPI_MODE_1, max_speed=2_000_000)
    spi_new_device(bus_num=1, chip_select=1, name="max7219", mode=SPI_MODE_0, max_speed=10_000_000)

    # -- Register drivers (auto-binds to matching devices) --
    print("\n--- Registering SPI Drivers ---")
    spi_register_driver(SpidevDriver())
    spi_register_driver(EepromSpiDriver())
    spi_register_driver(W25qxxDriver())
    spi_register_driver(Ads1256Driver())
    spi_register_driver(Max7219Driver())

    # -- Show state after probe --
    spi_dump_state()

    # -- Demonstrate write --
    print("--- spi_write ---")
    dev = spi_busnum_to_device(0, 0)
    spi_write(dev, b"\x01\x02\x03\x04")

    # -- Demonstrate read --
    print("\n--- spi_read ---")
    data = spi_read(dev, 8)
    if data:
        print(f"  received: {data.hex()}")

    # -- Demonstrate write-then-read --
    print("\n--- spi_write_then_read ---")
    resp = spi_write_then_read(dev, b"\x9F", 3)
    if resp:
        print(f"  JEDEC ID bytes: {resp.hex()}")

    # -- Demonstrate bundled transfers --
    print("\n--- SpiMessage (bundled transfers) ---")
    msg = SpiMessage(device=dev)
    msg.add_transfer(SpiTransfer(tx_buf=b"\x03\x00\x00", speed_hz=dev.speed_hz, cs_change=True))
    msg.add_transfer(SpiTransfer(rx_buf=bytearray(64), len=64, speed_hz=dev.speed_hz))
    spi_sync(dev, msg)
    print(f"  message result: {msg!r}")

    # -- Mode changes --
    print("\n--- Mode/Speed Changes ---")
    flash = spi_busnum_to_device(0, 1)
    spi_set_mode(flash, SPI_MODE_3)
    spi_set_speed(flash, 50_000_000)
    spi_setup(flash)

    adc = spi_busnum_to_device(1, 0)
    spi_set_mode(adc, SPI_MODE_2)
    spi_set_speed(adc, 500_000)
    spi_setup(adc)

    # -- Controller lookup --
    print("\n--- Controller Lookup ---")
    ctrl = spi_get_controller(0)
    print(f"  bus 0: {ctrl!r}")
    ctrl = spi_get_controller(99)
    print(f"  bus 99: {ctrl}")

    # -- Unregister a device --
    print("\n--- Unregister device ---")
    spi_unregister_device(1, 1)

    # -- Final state --
    spi_dump_state()


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo()
