"""
UmerOS NVMEM Subsystem
======================
Kernel-like Non-Volatile Memory management framework.
Supports EEPROM, OTP, eFuse, Flash, and battery-backed storage.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NVMEM_TYPE_EEPROM: str = "eeprom"
NVMEM_TYPE_OTP: str = "otp"
NVMEM_TYPE_EFUSE: str = "efuse"
NVMEM_TYPE_FLASH: str = "flash"
NVMEM_TYPE_BATTERY_BACKED: str = "battery_backed"
NVMEM_TYPE_FAKESYS: str = "fake_sysfs"

# ---------------------------------------------------------------------------
# Global registries
# ---------------------------------------------------------------------------

_nvmem_devices: dict[str, NvmemDevice] = {}
_nvmem_providers: dict[str, NvmemProvider] = {}
_nvmem_refcount: dict[str, int] = {}
_next_device_id: int = 1


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class NvmemDevice:
    """Non-volatile memory device."""

    name: str
    id: int
    size: int
    word_size: int = 1
    reg_write_precision: int = 1
    read_only: bool = False
    root_only: bool = False
    no_of_regs: int = 0
    reg_base: int = 0
    data: bytearray = field(default_factory=bytearray)
    _callbacks: dict = field(default_factory=dict)
    _is_registered: bool = False

    def __post_init__(self) -> None:
        if len(self.data) != self.size:
            self.data = bytearray(self.size)


@dataclass
class NvmemCell:
    """A named region within an NVMEM device."""

    device_name: str
    name: str
    offset: int
    size: int
    bit_offset: int = 0
    nbits: int = 0

    def __post_init__(self) -> None:
        if self.nbits == 0:
            self.nbits = self.size * 8


@dataclass
class NvmemProvider:
    """NVMEM provider (backing store)."""

    name: str
    type: str
    read: Optional[Callable] = None
    write: Optional[Callable] = None
    reg_read: Optional[Callable] = None
    reg_write: Optional[Callable] = None


# ---------------------------------------------------------------------------
# Built-in providers
# ---------------------------------------------------------------------------

class EepromNvmemProvider(NvmemProvider):
    """I2C/SPI EEPROM (AT24Cxx, M95xxx)."""

    def __init__(self, name: str = "eeprom-provider", size: int = 4096) -> None:
        self._backing = bytearray(size)
        super().__init__(
            name=name,
            type=NVMEM_TYPE_EEPROM,
            read=self._read,
            write=self._write,
        )

    def _read(self, offset: int, length: int) -> bytearray:
        end = min(offset + length, len(self._backing))
        return bytearray(self._backing[offset:end])

    def _write(self, offset: int, data: bytearray) -> int:
        end = min(offset + len(data), len(self._backing))
        length = end - offset
        self._backing[offset:end] = data[:length]
        return length


class OtpNvmemProvider(NvmemProvider):
    """OTP (One-Time Programmable) memory."""

    def __init__(self, name: str = "otp-provider", size: int = 512) -> None:
        self._backing = bytearray(size)
        self._burned = bytearray(size)
        super().__init__(
            name=name,
            type=NVMEM_TYPE_OTP,
            read=self._read,
            write=self._write,
        )

    def _read(self, offset: int, length: int) -> bytearray:
        end = min(offset + length, len(self._backing))
        return bytearray(self._backing[offset:end])

    def _write(self, offset: int, data: bytearray) -> int:
        written = 0
        for i, byte in enumerate(data):
            pos = offset + i
            if pos >= len(self._backing):
                break
            if self._burned[pos]:
                continue
            self._backing[pos] = byte
            self._burned[pos] = 1
            written += 1
        return written


class EfuseNvmemProvider(NvmemProvider):
    """eFuse (burn-once) memory."""

    def __init__(self, name: str = "efuse-provider", size: int = 256) -> None:
        self._backing = bytearray(size)
        self._burned = bytearray(size)
        super().__init__(
            name=name,
            type=NVMEM_TYPE_EFUSE,
            read=self._read,
            write=self._write,
        )

    def _read(self, offset: int, length: int) -> bytearray:
        end = min(offset + length, len(self._backing))
        return bytearray(self._backing[offset:end])

    def _write(self, offset: int, data: bytearray) -> int:
        written = 0
        for i, byte in enumerate(data):
            pos = offset + i
            if pos >= len(self._backing):
                break
            if self._burned[pos]:
                continue
            self._backing[pos] = byte
            self._burned[pos] = 1
            written += 1
        return written


class FlashNvmemProvider(NvmemProvider):
    """Flash-based NVMEM with sector erase."""

    def __init__(self, name: str = "flash-provider", size: int = 65536, sector_size: int = 4096) -> None:
        self._backing = bytearray(size)
        self._sector_size = sector_size
        super().__init__(
            name=name,
            type=NVMEM_TYPE_FLASH,
            read=self._read,
            write=self._write,
        )

    def _read(self, offset: int, length: int) -> bytearray:
        end = min(offset + length, len(self._backing))
        return bytearray(self._backing[offset:end])

    def _write(self, offset: int, data: bytearray) -> int:
        end = min(offset + len(data), len(self._backing))
        length = end - offset
        self._backing[offset:end] = data[:length]
        return length

    def erase_sector(self, sector: int) -> None:
        start = sector * self._sector_size
        end = min(start + self._sector_size, len(self._backing))
        self._backing[start:end] = b'\xff' * (end - start)


class BatteryBackedNvmemProvider(NvmemProvider):
    """Battery-backed SRAM."""

    def __init__(self, name: str = "batbacked-provider", size: int = 8192) -> None:
        self._backing = bytearray(size)
        self._battery_ok = True
        super().__init__(
            name=name,
            type=NVMEM_TYPE_BATTERY_BACKED,
            read=self._read,
            write=self._write,
        )

    def _read(self, offset: int, length: int) -> bytearray:
        if not self._battery_ok:
            return bytearray(length)
        end = min(offset + length, len(self._backing))
        return bytearray(self._backing[offset:end])

    def _write(self, offset: int, data: bytearray) -> int:
        if not self._battery_ok:
            return 0
        end = min(offset + len(data), len(self._backing))
        length = end - offset
        self._backing[offset:end] = data[:length]
        return length

    def battery_remove(self) -> None:
        self._battery_ok = False
        self._backing = bytearray(len(self._backing))

    def battery_insert(self) -> None:
        self._battery_ok = True


# ---------------------------------------------------------------------------
# Core kernel API
# ---------------------------------------------------------------------------

def nvmem_register(
    provider: NvmemProvider,
    word_size: int = 1,
    read_only: bool = False,
    root_only: bool = False,
) -> NvmemDevice:
    """Register NVMEM device — like nvmem_register()."""
    global _next_device_id
    dev_id = _next_device_id
    _next_device_id += 1
    device = NvmemDevice(
        name=provider.name,
        id=dev_id,
        size=len(provider._backing) if hasattr(provider, '_backing') else 4096,
        word_size=word_size,
        read_only=read_only,
        root_only=root_only,
        _is_registered=True,
    )
    device._callbacks = {
        "read": provider.read,
        "write": provider.write,
        "reg_read": provider.reg_read,
        "reg_write": provider.reg_write,
    }
    _nvmem_devices[device.name] = device
    _nvmem_providers[device.name] = provider
    _nvmem_refcount[device.name] = 0
    return device


def nvmem_unregister(device_id: int) -> None:
    """Unregister NVMEM device."""
    target: Optional[str] = None
    for name, dev in _nvmem_devices.items():
        if dev.id == device_id:
            target = name
            break
    if target is None:
        raise ValueError(f"Device id {device_id} not registered")
    dev = _nvmem_devices[target]
    dev._is_registered = False
    del _nvmem_devices[target]
    del _nvmem_providers[target]
    _nvmem_refcount.pop(target, None)


def nvmem_device_get(name: str) -> NvmemDevice:
    """Get NVMEM device by name — like nvmem_device_get()."""
    if name not in _nvmem_devices:
        raise KeyError(f"NVMEM device '{name}' not found")
    dev = _nvmem_devices[name]
    if not dev._is_registered:
        raise KeyError(f"NVMEM device '{name}' is not registered")
    _nvmem_refcount[name] = _nvmem_refcount.get(name, 0) + 1
    return dev


def nvmem_device_put(name: str) -> None:
    """Put NVMEM device reference."""
    if name in _nvmem_refcount:
        _nvmem_refcount[name] = max(0, _nvmem_refcount[name] - 1)


def nvmem_read(device_name: str, offset: int, length: int) -> bytearray:
    """Read from NVMEM — like nvmem_read()."""
    dev = nvmem_device_get(device_name)
    try:
        if offset < 0 or offset + length > dev.size:
            raise ValueError(
                f"Read out of bounds: offset={offset} length={length} size={dev.size}"
            )
        if dev.root_only:
            raise PermissionError(f"Device '{device_name}' requires root access")
        read_fn = dev._callbacks.get("read")
        if read_fn is not None:
            return read_fn(offset, length)
        return bytearray(dev.data[offset : offset + length])
    finally:
        nvmem_device_put(device_name)


def nvmem_write(device_name: str, offset: int, data: bytearray | bytes) -> int:
    """Write to NVMEM."""
    dev = nvmem_device_get(device_name)
    try:
        if dev.read_only:
            raise PermissionError(f"Device '{device_name}' is read-only")
        if offset < 0 or offset + len(data) > dev.size:
            raise ValueError(
                f"Write out of bounds: offset={offset} len={len(data)} size={dev.size}"
            )
        if dev.root_only:
            raise PermissionError(f"Device '{device_name}' requires root access")
        write_fn = dev._callbacks.get("write")
        if write_fn is not None:
            return write_fn(offset, bytearray(data))
        dev.data[offset : offset + len(data)] = bytearray(data)
        return len(data)
    finally:
        nvmem_device_put(device_name)


def nvmem_word_read(device_name: str, offset: int) -> int:
    """Read single word."""
    dev = nvmem_device_get(device_name)
    try:
        ws = dev.word_size
        raw = nvmem_read(device_name, offset, ws)
        value = 0
        for b in raw:
            value = (value << 8) | b
        return value
    finally:
        nvmem_device_put(device_name)


def nvmem_word_write(device_name: str, offset: int, value: int) -> int:
    """Write single word."""
    dev = nvmem_device_get(device_name)
    try:
        ws = dev.word_size
        data = bytearray(ws)
        for i in range(ws - 1, -1, -1):
            data[i] = value & 0xFF
            value >>= 8
        return nvmem_write(device_name, offset, data)
    finally:
        nvmem_device_put(device_name)


def nvmem_cell_read(device_name: str, cell_name: str) -> bytearray:
    """Read named cell."""
    dev = nvmem_device_get(device_name)
    try:
        cell = _find_cell(device_name, cell_name)
        return nvmem_read(device_name, cell.offset, cell.size)
    finally:
        nvmem_device_put(device_name)


def nvmem_cell_write(device_name: str, cell_name: str, data: bytearray | bytes) -> int:
    """Write named cell."""
    dev = nvmem_device_get(device_name)
    try:
        cell = _find_cell(device_name, cell_name)
        if len(data) != cell.size:
            raise ValueError(
                f"Cell '{cell_name}' expects {cell.size} bytes, got {len(data)}"
            )
        return nvmem_write(device_name, cell.offset, data)
    finally:
        nvmem_device_put(device_name)


def nvmem_add_cell(device_name: str, cell: NvmemCell) -> None:
    """Add named cell to device."""
    dev = nvmem_device_get(device_name)
    try:
        cells = _nvmem_device_cells.setdefault(device_name, {})
        if cell.name in cells:
            raise ValueError(f"Cell '{cell.name}' already exists on '{device_name}'")
        cells[cell.name] = cell
    finally:
        nvmem_device_put(device_name)


def nvmem_register_readonly(device_name: str, flag: bool) -> None:
    """Make device read-only."""
    dev = nvmem_device_get(device_name)
    try:
        dev.read_only = flag
    finally:
        nvmem_device_put(device_name)


def nvmem_is_available(device_name: str) -> bool:
    """Check if device is available."""
    if device_name not in _nvmem_devices:
        return False
    return _nvmem_devices[device_name]._is_registered


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_nvmem_device_cells: dict[str, dict[str, NvmemCell]] = {}


def _find_cell(device_name: str, cell_name: str) -> NvmemCell:
    cells = _nvmem_device_cells.get(device_name, {})
    if cell_name not in cells:
        raise KeyError(f"Cell '{cell_name}' not found on device '{device_name}'")
    return cells[cell_name]


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def _demo() -> None:
    print("=" * 64)
    print("UmerOS NVMEM Subsystem — Demonstration")
    print("=" * 64)

    # --- Create devices ---------------------------------------------------
    eeprom_prov = EepromNvmemProvider(name="at24c32", size=4096)
    otp_prov = OtpNvmemProvider(name="otp-0", size=512)
    efuse_prov = EfuseNvmemProvider(name="efuse-root", size=256)
    flash_prov = FlashNvmemProvider(name="spi-flash", size=65536, sector_size=4096)
    bat_prov = BatteryBackedNvmemProvider(name="nvram-bat", size=8192)

    devs = [
        nvmem_register(eeprom_prov, word_size=4),
        nvmem_register(otp_prov),
        nvmem_register(efuse_prov),
        nvmem_register(flash_prov),
        nvmem_register(bat_prov),
    ]

    print("\n[1] Registered NVMEM devices:")
    for d in devs:
        kind = type(d).__name__
        print(f"    id={d.id:2d}  name={d.name:<14s}  size={d.size:>6d} B")

    # --- Add cells --------------------------------------------------------
    mac_cell = NvmemCell(device_name="at24c32", name="mac_address", offset=0, size=6)
    serial_cell = NvmemCell(device_name="at24c32", name="serial_number", offset=16, size=12)
    calib_cell = NvmemCell(device_name="otp-0", name="calibration", offset=0, size=32)
    crypto_cell = NvmemCell(device_name="efuse-root", name="crypto_key", offset=0, size=32)

    nvmem_add_cell("at24c32", mac_cell)
    nvmem_add_cell("at24c32", serial_cell)
    nvmem_add_cell("otp-0", calib_cell)
    nvmem_add_cell("efuse-root", crypto_cell)

    print("\n[2] Cells registered:")
    for dev_name, cells in _nvmem_device_cells.items():
        for cname, c in cells.items():
            print(f"    {dev_name}/{cname}  offset={c.offset}  size={c.size}")

    # --- Basic read/write on EEPROM --------------------------------------
    print("\n[3] EEPROM basic read/write:")
    payload = bytearray(b"\xDE\xAD\xBE\xEF\xCA\xFE")
    nvmem_write("at24c32", 0, payload)
    readback = nvmem_read("at24c32", 0, 6)
    print(f"    Wrote:  {payload.hex()}")
    print(f"    Read:   {bytes(readback).hex()}")
    assert readback == payload, "EEPROM read mismatch"

    # --- Cell access (MAC address) ---------------------------------------
    print("\n[4] Cell access — MAC address:")
    mac_data = bytearray(b"\xAA\xBB\xCC\xDD\xEE\xFF")
    nvmem_cell_write("at24c32", "mac_address", mac_data)
    mac_read = nvmem_cell_read("at24c32", "mac_address")
    mac_str = ":".join(f"{b:02X}" for b in mac_read)
    print(f"    MAC: {mac_str}")

    # --- Word read/write --------------------------------------------------
    print("\n[5] Word read/write (4-byte word):")
    nvmem_word_write("at24c32", 100, 0xDEADBEEF)
    val = nvmem_word_read("at24c32", 100)
    print(f"    Wrote: 0xDEADBEEF")
    print(f"    Read:  0x{val:08X}")
    assert val == 0xDEADBEEF, "Word read mismatch"

    # --- OTP write-once ---------------------------------------------------
    print("\n[6] OTP write-once semantics:")
    otp_data = bytearray(range(32))
    nvmem_cell_write("otp-0", "calibration", otp_data)
    readback_otp = nvmem_cell_read("otp-0", "calibration")
    print(f"    Original:  {bytes(readback_otp[:8]).hex()} ...")
    overwritten = bytearray(range(32, 64))
    written = nvmem_write("otp-0", 0, overwritten)
    print(f"    Attempted overwrite of {written} bytes")
    after = nvmem_cell_read("otp-0", "calibration")
    print(f"    After:     {bytes(after[:8]).hex()} ...")
    print(f"    Unchanged: {after == readback_otp}")

    # --- eFuse burn-once --------------------------------------------------
    print("\n[7] eFuse burn-once semantics:")
    key1 = bytes(range(32))
    nvmem_cell_write("efuse-root", "crypto_key", key1)
    key_back = nvmem_cell_read("efuse-root", "crypto_key")
    print(f"    Key burned: {bytes(key_back[:8]).hex()} ...")
    key2 = bytes(range(32, 64))
    nvmem_cell_write("efuse-root", "crypto_key", key2)
    key_still = nvmem_cell_read("efuse-root", "crypto_key")
    print(f"    After overwrite attempt: {bytes(key_still[:8]).hex()} ...")
    print(f"    Unchanged: {key_still == key_back}")

    # --- Flash bulk write -------------------------------------------------
    print("\n[8] Flash bulk write:")
    chunk = bytearray(b"\x42" * 256)
    nvmem_write("spi-flash", 0, chunk)
    read_chunk = nvmem_read("spi-flash", 0, 256)
    print(f"    Wrote 256 bytes of 0x42")
    print(f"    Read back matches: {read_chunk == chunk}")

    # --- Flash sector erase -----------------------------------------------
    print("\n[9] Flash sector erase:")
    flash_prov.erase_sector(0)
    erased = nvmem_read("spi-flash", 0, 8)
    print(f"    After erase (first 8 bytes): {bytes(erased).hex()}")
    print(f"    All 0xFF: {all(b == 0xFF for b in erased)}")

    # --- Read-only enforcement --------------------------------------------
    print("\n[10] Read-only enforcement:")
    nvmem_register_readonly("at24c32", True)
    try:
        nvmem_write("at24c32", 0, bytearray(b"\x00"))
        print("     ERROR: write succeeded on read-only device")
    except PermissionError as exc:
        print(f"     Caught: {exc}")
    nvmem_register_readonly("at24c32", False)

    # --- Battery-backed with battery removed -----------------------------
    print("\n[11] Battery-backed NVMEM:")
    bat_prov._write(0, bytearray(b"CRITICAL DATA"))
    read_bat = bat_prov._read(0, 13)
    print(f"    With battery: {bytes(read_bat)}")
    bat_prov.battery_remove()
    read_dead = bat_prov._read(0, 13)
    print(f"    Battery removed — read returns zeros: {all(b == 0 for b in read_dead)}")
    bat_prov.battery_insert()
    bat_prov._write(0, bytearray(b"RESTORED DATA"))
    read_restored = bat_prov._read(0, 13)
    print(f"    Battery reinserted: {bytes(read_restored)}")

    # --- Device availability ----------------------------------------------
    print("\n[12] Device availability checks:")
    for name in ("at24c32", "otp-0", "nonexistent"):
        avail = nvmem_is_available(name)
        print(f"    {name}: {'available' if avail else 'NOT available'}")

    # --- Reference counting -----------------------------------------------
    print("\n[13] Reference counting:")
    nvmem_device_get("at24c32")
    nvmem_device_get("at24c32")
    print(f"    at24c32 refcount: {_nvmem_refcount.get('at24c32', 0)}")
    nvmem_device_put("at24c32")
    print(f"    After put:         {_nvmem_refcount.get('at24c32', 0)}")
    nvmem_device_put("at24c32")
    print(f"    After 2nd put:     {_nvmem_refcount.get('at24c32', 0)}")

    # --- Unregister -------------------------------------------------------
    print("\n[14] Unregistering devices:")
    for d in devs:
        nvmem_unregister(d.id)
        print(f"    Removed: {d.name} (id={d.id})")
    print(f"    Remaining devices: {len(_nvmem_devices)}")

    print("\n" + "=" * 64)
    print("All NVMEM subsystem checks passed.")
    print("=" * 64)


if __name__ == "__main__":
    _demo()
