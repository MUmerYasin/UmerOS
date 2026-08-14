"""
UmerOS I2C/SMBus Framework
===========================
Kernel I2C/SMBus subsystem.
Implements I2C adapters (bit-banging, I801), clients, drivers,
SMBus byte/word/block operations, and built-in device drivers
(EEPROM, GPIO expander, OLED, environmental sensor).
"""

from __future__ import annotations

import logging
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# I2C Client Flags
# ---------------------------------------------------------------------------
I2C_CLIENT_TEN: int = 0x01       # 10-bit address
I2C_CLIENT_PEC: int = 0x02       # Packet Error Checking
I2C_CLIENT_STRETCH: int = 0x04   # clock stretching
I2C_CLIENT_WAKEUP: int = 0x08    # wake up from suspend

# ---------------------------------------------------------------------------
# I2C Message Flags
# ---------------------------------------------------------------------------
I2C_M_RD: int = 0x0001           # read data
I2C_M_TEN: int = 0x0010          # 10-bit address
I2C_M_RECV_LEN: int = 0x0400     # length first
I2C_M_NO_RD_ACK: int = 0x0800    # no ACK on read

# ---------------------------------------------------------------------------
# SMBus Protocol Constants
# ---------------------------------------------------------------------------
SMBUS_BYTE: str = "byte"
SMBUS_BYTE_DATA: str = "byte_data"
SMBUS_WORD_DATA: str = "word_data"
SMBUS_BLOCK_DATA: str = "block_data"
SMBUS_I2C_BLOCK: str = "i2c_block"
SMBUS_QUICK: str = "quick"
SMBUS_PROCESS_CALL: str = "process_call"
SMBUS_BLOCK_PROCESS_CALL: str = "block_process_call"

# ---------------------------------------------------------------------------
# Adapter Speed Constants
# ---------------------------------------------------------------------------
I2C_SPEED_STANDARD: int = 100_000    # 100 kHz
I2C_SPEED_FAST: int = 400_000        # 400 kHz
I2C_SPEED_FAST_PLUS: int = 1_000_000 # 1 MHz
I2C_SPEED_HIGH: int = 3_400_000      # 3.4 MHz

# ---------------------------------------------------------------------------
# Adapter Algorithm Constants
# ---------------------------------------------------------------------------
I2C_ALGO_BIT_BANGING: str = "bit_banging"
I2C_ALGO_I801: str = "i801"
I2C_ALGO_DESIGNWARE: str = "designware"
I2C_ALGO_TEGRA: str = "tegra"
I2C_ALGO_STM32: str = "stm32"

_VALID_ALGOS: set = {
    I2C_ALGO_BIT_BANGING,
    I2C_ALGO_I801,
    I2C_ALGO_DESIGNWARE,
    I2C_ALGO_TEGRA,
    I2C_ALGO_STM32,
}


# ---------------------------------------------------------------------------
# Core Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class I2cAdapter:
    """I2C bus adapter."""
    name: str
    nr: int                                        # bus number
    algo: str = I2C_ALGO_BIT_BANGING               # bit_banging, i801, designware, tegra, stm32
    speed: int = I2C_SPEED_STANDARD                # Hz (100kHz, 400kHz, 1MHz, 3.4MHz)
    max_speed: int = I2C_SPEED_FAST
    is_registered: bool = False
    is_exclusive: bool = False
    _clients: list = field(default_factory=list)
    _clock_stretching: bool = True
    _ten_bit_addr: bool = False
    _smbus_read: object = None
    _smbus_write: object = None

    def __post_init__(self) -> None:
        if self.speed == 0:
            self.speed = I2C_SPEED_STANDARD
        if self.max_speed == 0:
            self.max_speed = I2C_SPEED_FAST

    @property
    def speed_khz(self) -> float:
        """Return adapter speed in kHz."""
        return self.speed / 1000.0

    @property
    def functionality(self) -> int:
        """Return bitmask of supported functionality."""
        func = 0x00000001  # I2C_FUNC_I2C
        func |= 0x00000004  # I2C_FUNC_SMBUS_BYTE
        func |= 0x00000008  # I2C_FUNC_SMBUS_BYTE_DATA
        func |= 0x00000010  # I2C_FUNC_SMBUS_WORD_DATA
        func |= 0x00000080  # I2C_FUNC_SMBUS_BLOCK_DATA
        func |= 0x00000400  # I2C_FUNC_SMBUS_I2C_BLOCK
        if self._ten_bit_addr:
            func |= 0x00010000  # I2C_FUNC_10BIT_ADDR
        if self._clock_stretching:
            func |= 0x00020000  # I2C_FUNC_STRETCHING
        return func

    def __repr__(self) -> str:
        return (
            f"I2cAdapter(nr={self.nr}, name={self.name!r}, "
            f"algo={self.algo!r}, speed={self.speed_khz:.0f}kHz, "
            f"clients={len(self._clients)})"
        )


@dataclass
class I2cClient:
    """I2C client device."""
    name: str
    addr: int                                       # 7-bit or 10-bit address
    adapter_name: str
    driver_name: str = ""
    chip_name: str = ""                             # device tree compatible
    flags: int = 0
    irq: int = -1
    is_bound: bool = False
    _reg_cache: dict = field(default_factory=dict)
    _client_data: Any = None
    _driver: Optional[I2cDriver] = None

    @property
    def is_10bit(self) -> bool:
        """Check if using 10-bit addressing."""
        return bool(self.flags & I2C_CLIENT_TEN)

    @property
    def has_pec(self) -> bool:
        """Check if PEC is enabled."""
        return bool(self.flags & I2C_CLIENT_PEC)

    @property
    def addr_hex(self) -> str:
        """Return hex address string."""
        return f"0x{self.addr:02x}"

    def __repr__(self) -> str:
        bound = "bound" if self.is_bound else "unbound"
        drv = self.driver_name or "none"
        return (
            f"I2cClient(addr={self.addr_hex}, name={self.name!r}, "
            f"adapter={self.adapter_name!r}, driver={drv!r}, "
            f"chip={self.chip_name!r}, [{bound}])"
        )


@dataclass
class I2cDriver:
    """I2C device driver."""
    name: str
    probe: object = None                            # callback(client) -> bool
    remove: object = None                           # callback(client)
    shutdown: object = None                         # callback(client)
    suspend: object = None                          # callback(client) -> int
    resume: object = None                           # callback(client) -> int
    id_table: list = field(default_factory=list)    # [(name, chip_name), ...]

    def __repr__(self) -> str:
        probe_str = "yes" if self.probe else "no"
        return (
            f"I2cDriver(name={self.name!r}, id_table={self.id_table}, "
            f"probe={probe_str})"
        )


@dataclass
class I2cMsg:
    """I2C message."""
    addr: int
    flags: int                                      # I2C_M_RD, I2C_M_TEN
    buf: bytes = b''

    @property
    def is_read(self) -> bool:
        """Check if message is a read."""
        return bool(self.flags & I2C_M_RD)

    @property
    def is_write(self) -> bool:
        """Check if message is a write."""
        return not self.is_read

    @property
    def len(self) -> int:
        """Return message length."""
        return len(self.buf)

    def __repr__(self) -> str:
        direction = "RD" if self.is_read else "WR"
        return (
            f"I2cMsg(addr=0x{self.addr:02x}, {direction}, "
            f"len={self.len}, buf={self.buf.hex() if self.buf else 'empty'})"
        )


@dataclass
class SmbusData:
    """SMBus transaction data."""
    command: int
    data: bytes = b''
    read_write: str = "read"                        # read or write
    protocol: str = SMBUS_BYTE                      # byte, word, block, i2c_block

    def __repr__(self) -> str:
        return (
            f"SmbusData(cmd=0x{self.command:02x}, {self.read_write}, "
            f"proto={self.protocol!r}, data={self.data.hex() if self.data else 'empty'})"
        )


# ---------------------------------------------------------------------------
# Global Registries
# ---------------------------------------------------------------------------
_adapters: Dict[str, I2cAdapter] = {}
_clients: List[I2cClient] = []
_drivers: Dict[str, I2cDriver] = {}


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------
def _find_adapter(name: str) -> I2cAdapter:
    """Get adapter or raise."""
    adapter = _adapters.get(name)
    if adapter is None:
        raise ValueError(f"I2C adapter '{name}' not found")
    if not adapter.is_registered:
        raise RuntimeError(f"I2C adapter '{name}' is not registered")
    return adapter


def _find_client(client_name: str) -> I2cClient:
    """Find client by name or raise."""
    for client in _clients:
        if client.name == client_name:
            return client
    raise ValueError(f"I2C client '{client_name}' not found")


def _find_client_on_adapter(adapter_name: str, addr: int) -> Optional[I2cClient]:
    """Find client by adapter name and address."""
    for client in _clients:
        if client.adapter_name == adapter_name and client.addr == addr:
            return client
    return None


def _auto_bind_driver(driver: I2cDriver) -> None:
    """Attempt to bind a driver to all unbound clients."""
    for client in _clients:
        if client.is_bound:
            continue
        _try_bind(driver, client)


def _try_bind(driver: I2cDriver, client: I2cClient) -> None:
    """Try to bind a driver to a client via id_table matching."""
    if not driver.id_table:
        if driver.name == client.driver_name:
            _do_bind(driver, client)
        return

    for entry_name, entry_chip in driver.id_table:
        if entry_name == client.name or entry_name == client.driver_name:
            _do_bind(driver, client)
            return
        if entry_chip and (entry_chip == client.chip_name):
            _do_bind(driver, client)
            return

    if client.driver_name and client.driver_name == driver.name:
        _do_bind(driver, client)


def _do_bind(driver: I2cDriver, client: I2cClient) -> None:
    """Perform the actual driver binding."""
    if driver.probe:
        try:
            ok = driver.probe(client)
        except Exception as exc:
            log.error("probe(%r) threw: %s", driver.name, exc)
            print(f"[I2C] probe({driver.name!r}) threw: {exc}")
            return
        if not ok:
            log.debug("probe(%r) rejected client %r", driver.name, client.name)
            print(f"[I2C] probe({driver.name!r}) rejected {client!r}")
            return

    client.is_bound = True
    client.driver_name = driver.name
    client._driver = driver
    log.info("bound driver %r -> client %r", driver.name, client.name)
    print(f"[I2C] bound {driver.name!r} -> {client!r}")


def _do_unbind(client: I2cClient) -> None:
    """Perform driver unbinding."""
    driver = client._driver
    if driver and driver.remove:
        try:
            driver.remove(client)
        except Exception as exc:
            log.error("remove(%r) threw: %s", driver.name, exc)
            print(f"[I2C] remove({driver.name!r}) threw: {exc}")

    client.is_bound = False
    client._driver = None
    client.driver_name = ""


# ---------------------------------------------------------------------------
# Adapter Functions
# ---------------------------------------------------------------------------
def i2c_add_adapter(
    name: str,
    algo: str = I2C_ALGO_BIT_BANGING,
    speed: int = I2C_SPEED_STANDARD,
) -> I2cAdapter:
    """Add I2C adapter."""
    if name in _adapters:
        raise ValueError(f"I2C adapter '{name}' already registered")
    if algo not in _VALID_ALGOS:
        raise ValueError(f"Invalid algorithm '{algo}'; use one of {_VALID_ALGOS}")

    nr = len(_adapters)
    adapter = I2cAdapter(
        name=name,
        nr=nr,
        algo=algo,
        speed=speed,
        max_speed=max(speed, I2C_SPEED_FAST),
        is_registered=True,
    )
    _adapters[name] = adapter
    log.info("Registered I2C adapter: %r", adapter)
    print(f"[I2C] registered adapter: {adapter}")
    return adapter


def i2c_del_adapter(name: str) -> bool:
    """Remove I2C adapter."""
    adapter = _adapters.pop(name, None)
    if adapter is None:
        print(f"[I2C] ERROR: adapter '{name}' not found")
        return False

    # Unbind all clients on this adapter
    for client in list(_clients):
        if client.adapter_name == name:
            if client.is_bound:
                _do_unbind(client)
            _clients.remove(client)

    adapter.is_registered = False
    log.info("Unregistered I2C adapter: %r", adapter)
    print(f"[I2C] unregistered adapter: {name!r}")
    return True


def i2c_get_adapter(name: str) -> Optional[I2cAdapter]:
    """Get I2C adapter."""
    adapter = _adapters.get(name)
    if adapter and adapter.is_registered:
        return adapter
    return None


def i2c_adapter_set_speed(name: str, speed: int) -> bool:
    """Set adapter speed."""
    adapter = _adapters.get(name)
    if adapter is None:
        print(f"[I2C] ERROR: adapter '{name}' not found")
        return False
    if speed > adapter.max_speed:
        print(f"[I2C] WARN: speed {speed}Hz > max {adapter.max_speed}Hz, clamping")
        speed = adapter.max_speed
    adapter.speed = speed
    log.info("Adapter %r speed -> %dHz", name, speed)
    print(f"[I2C] adapter {name!r}: speed -> {speed}Hz ({speed / 1000:.0f}kHz)")
    return True


# ---------------------------------------------------------------------------
# Client Functions
# ---------------------------------------------------------------------------
def i2c_new_client_device(
    adapter_name: str,
    addr: int,
    name: str = "",
    chip_name: str = "",
    driver_name: str = "",
    irq: int = -1,
    flags: int = 0,
) -> I2cClient:
    """Create new I2C client - like i2c_new_client_device()."""
    adapter = _find_adapter(adapter_name)
    if addr < 0 or addr > 0x7FF:
        raise ValueError(f"Invalid I2C address 0x{addr:04x}")

    # Check for duplicate
    existing = _find_client_on_adapter(adapter_name, addr)
    if existing is not None:
        raise ValueError(
            f"Client at address 0x{addr:02x} on adapter '{adapter_name}' "
            f"already exists: {existing.name!r}"
        )

    if not name:
        name = f"i2c-{adapter_name}-0x{addr:02x}"

    client = I2cClient(
        name=name,
        addr=addr,
        adapter_name=adapter_name,
        driver_name=driver_name,
        chip_name=chip_name,
        flags=flags,
        irq=irq,
    )
    _clients.append(client)
    adapter._clients.append(client)

    log.info("Created I2C client: %r", client)
    print(f"[I2C] new client: {client}")

    # Auto-bind existing drivers
    for driver in _drivers.values():
        if not client.is_bound:
            _try_bind(driver, client)

    return client


def i2c_unregister_device(client_name: str) -> bool:
    """Unregister I2C client."""
    for idx, client in enumerate(_clients):
        if client.name == client_name:
            if client.is_bound:
                _do_unbind(client)

            adapter = _adapters.get(client.adapter_name)
            if adapter and client in adapter._clients:
                adapter._clients.remove(client)

            _clients.pop(idx)
            log.info("Unregistered I2C client: %r", client)
            print(f"[I2C] unregistered client: {client_name!r}")
            return True

    print(f"[I2C] ERROR: client '{client_name}' not found")
    return False


def i2c_get_device(adapter_name: str, addr: int) -> Optional[I2cClient]:
    """Get I2C client by address."""
    return _find_client_on_adapter(adapter_name, addr)


# ---------------------------------------------------------------------------
# Driver Functions
# ---------------------------------------------------------------------------
def i2c_add_driver(driver: I2cDriver) -> bool:
    """Register I2C driver - like i2c_add_driver()."""
    if driver.name in _drivers:
        print(f"[I2C] ERROR: driver '{driver.name}' already registered")
        return False
    _drivers[driver.name] = driver
    log.info("Registered I2C driver: %r", driver)
    print(f"[I2C] registered driver: {driver}")

    # Auto-bind to existing clients
    _auto_bind_driver(driver)
    return True


def i2c_del_driver(driver_name: str) -> bool:
    """Unregister I2C driver."""
    driver = _drivers.pop(driver_name, None)
    if driver is None:
        print(f"[I2C] ERROR: driver '{driver_name}' not found")
        return False

    # Unbind all clients using this driver
    for client in _clients:
        if client.driver_name == driver_name:
            _do_unbind(client)

    log.info("Unregistered I2C driver: %r", driver)
    print(f"[I2C] unregistered driver: {driver_name!r}")
    return True


# ---------------------------------------------------------------------------
# Transfer Functions
# ---------------------------------------------------------------------------
def i2c_transfer(adapter_name: str, msgs: List[I2cMsg]) -> bool:
    """Transfer I2C messages - like i2c_transfer()."""
    adapter = _find_adapter(adapter_name)
    if not msgs:
        print(f"[I2C] WARN: empty message list")
        return False

    total_bytes = sum(m.len for m in msgs)
    print(
        f"[I2C] transfer on {adapter_name!r}: "
        f"{len(msgs)} messages, {total_bytes} bytes"
    )

    for msg in msgs:
        if msg.is_read:
            print(f"  <- READ  0x{msg.addr:02x}: {msg.len}B")
        else:
            data_hex = msg.buf.hex() if msg.buf else "empty"
            print(f"  -> WRITE 0x{msg.addr:02x}: {msg.len}B [{data_hex}]")

    return True


def i2c_master_send(client_name: str, data: bytes) -> int:
    """Send data to I2C device."""
    client = _find_client(client_name)
    if not data:
        return 0

    adapter = _find_adapter(client.adapter_name)
    msg = I2cMsg(addr=client.addr, flags=0, buf=data)
    ok = i2c_transfer(client.adapter_name, [msg])
    if ok:
        log.info("master_send to %r: %d bytes", client_name, len(data))
        return len(data)
    return -1


def i2c_master_recv(client_name: str, length: int) -> Optional[bytes]:
    """Receive data from I2C device."""
    client = _find_client(client_name)
    if length <= 0:
        return b''

    adapter = _find_adapter(client.adapter_name)
    msg = I2cMsg(addr=client.addr, flags=I2C_M_RD, buf=b'\x00' * length)
    ok = i2c_transfer(client.adapter_name, [msg])
    if ok:
        # Simulate received data
        response = bytes(range(length)) if length <= 8 else b'\xaa' * length
        log.info("master_recv from %r: %d bytes", client_name, length)
        return response
    return None


# ---------------------------------------------------------------------------
# SMBus Functions
# ---------------------------------------------------------------------------
def _smbus_xfer(
    client_name: str,
    command: int,
    data: bytes,
    read_write: str,
    protocol: str,
) -> Optional[bytes]:
    """Internal SMBus transfer."""
    client = _find_client(client_name)
    adapter = _find_adapter(client.adapter_name)
    print(
        f"[SMBus] {read_write.upper()} {protocol} on {client_name!r}: "
        f"cmd=0x{command:02x}, data={data.hex() if data else 'empty'}"
    )
    if read_write == "read":
        if protocol == SMBUS_BYTE:
            return bytes([0xAB])
        elif protocol == SMBUS_BYTE_DATA:
            return bytes([0xCD])
        elif protocol == SMBUS_WORD_DATA:
            return struct.pack(">H", 0x1234)
        elif protocol == SMBUS_BLOCK_DATA:
            return bytes([0x08, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08])
        elif protocol == SMBUS_I2C_BLOCK:
            return bytes(range(32))
        return b'\x00'
    return data


def smbus_read_byte(client_name: str, command: int) -> Optional[int]:
    """SMBus read byte."""
    result = _smbus_xfer(client_name, command, b'', "read", SMBUS_BYTE)
    if result:
        return result[0]
    return None


def smbus_write_byte(client_name: str, command: int, value: int) -> bool:
    """SMBus write byte."""
    _smbus_xfer(client_name, command, bytes([value & 0xFF]), "write", SMBUS_BYTE)
    return True


def smbus_read_byte_data(client_name: str, command: int) -> Optional[int]:
    """SMBus read byte data."""
    result = _smbus_xfer(client_name, command, b'', "read", SMBUS_BYTE_DATA)
    if result:
        return result[0]
    return None


def smbus_write_byte_data(client_name: str, command: int, value: int) -> bool:
    """SMBus write byte data."""
    _smbus_xfer(client_name, command, bytes([value & 0xFF]), "write", SMBUS_BYTE_DATA)
    return True


def smbus_read_word_data(client_name: str, command: int) -> Optional[int]:
    """SMBus read word data."""
    result = _smbus_xfer(client_name, command, b'', "read", SMBUS_WORD_DATA)
    if result and len(result) >= 2:
        return struct.unpack(">H", result[:2])[0]
    return None


def smbus_write_word_data(client_name: str, command: int, value: int) -> bool:
    """SMBus write word data."""
    data = struct.pack(">H", value & 0xFFFF)
    _smbus_xfer(client_name, command, data, "write", SMBUS_WORD_DATA)
    return True


def smbus_read_block_data(client_name: str, command: int) -> Optional[bytes]:
    """SMBus read block data."""
    result = _smbus_xfer(client_name, command, b'', "read", SMBUS_BLOCK_DATA)
    if result and len(result) >= 1:
        length = result[0]
        return result[1:1 + length]
    return None


def smbus_write_block_data(client_name: str, command: int, data: bytes) -> bool:
    """SMBus write block data."""
    block = bytes([len(data) & 0xFF]) + data
    _smbus_xfer(client_name, command, block, "write", SMBUS_BLOCK_DATA)
    return True


def smbus_read_i2c_block_data(client_name: str, command: int, length: int) -> Optional[bytes]:
    """SMBus read I2C block data."""
    result = _smbus_xfer(client_name, command, b'', "read", SMBUS_I2C_BLOCK)
    if result:
        return result[:length]
    return None


def smbus_write_i2c_block_data(client_name: str, command: int, data: bytes) -> bool:
    """SMBus write I2C block data."""
    _smbus_xfer(client_name, command, data, "write", SMBUS_I2C_BLOCK)
    return True


def smbus_quick(client_name: str, read_write: str) -> bool:
    """SMBus quick command."""
    client = _find_client(client_name)
    direction = "RD" if read_write == "read" else "WR"
    print(f"[SMBus] QUICK on {client_name!r}: {direction}")
    return True


def smbus_process_call(client_name: str, command: int, value: int) -> Optional[int]:
    """SMBus process call."""
    client = _find_client(client_name)
    data = struct.pack(">H", value & 0xFFFF)
    _smbus_xfer(client_name, command, data, "write", SMBUS_PROCESS_CALL)
    result = _smbus_xfer(client_name, command, b'', "read", SMBUS_WORD_DATA)
    if result and len(result) >= 2:
        return struct.unpack(">H", result[:2])[0]
    return None


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def i2c_check_functionality(adapter_name: str, func: int) -> bool:
    """Check adapter functionality."""
    adapter = _find_adapter(adapter_name)
    return bool(adapter.functionality & func)


def i2c_set_clientdata(client_name: str, data: Any) -> None:
    """Set client private data."""
    client = _find_client(client_name)
    client._client_data = data
    log.debug("Set client data for %r", client_name)


def i2c_get_clientdata(client_name: str) -> Any:
    """Get client private data."""
    client = _find_client(client_name)
    return client._client_data


def i2c_list_clients(adapter_name: Optional[str] = None) -> List[I2cClient]:
    """List I2C clients."""
    if adapter_name:
        return [c for c in _clients if c.adapter_name == adapter_name]
    return list(_clients)


def i2c_list_adapters() -> List[I2cAdapter]:
    """List I2C adapters."""
    return list(_adapters.values())


# ---------------------------------------------------------------------------
# Built-in I2C Drivers
# ---------------------------------------------------------------------------
class At24EepromDriver(I2cDriver):
    """AT24 EEPROM driver (24C01/02/04/08/16/32/64/128/256/512)."""

    def __init__(self) -> None:
        super().__init__(
            name="at24",
            id_table=[("at24", "atmel,24c256")],
            probe=self._probe,
            remove=self._remove,
        )

    @staticmethod
    def _probe(client: I2cClient) -> bool:
        print(f"  [at24] probing {client.name} at {client.addr_hex}")
        i2c_set_clientdata(client.name, {"page_size": 64, "size": 32768})
        print(f"  [at24] detected: page=64B, size=32KB")
        return True

    @staticmethod
    def _remove(client: I2cClient) -> None:
        print(f"  [at24] removing {client.name}")
        i2c_set_clientdata(client.name, None)


class Pca9539GpioDriver(I2cDriver):
    """PCA9539 GPIO expander driver."""

    def __init__(self) -> None:
        super().__init__(
            name="pca9539",
            id_table=[("pca9539", "nxp,pca9539")],
            probe=self._probe,
            remove=self._remove,
        )

    @staticmethod
    def _probe(client: I2cClient) -> bool:
        print(f"  [pca9539] probing {client.name} at {client.addr_hex}")
        i2c_set_clientdata(client.name, {"pins": 16, "ports": 2})
        print(f"  [pca9539] detected: 16 GPIOs (2x8)")
        return True

    @staticmethod
    def _remove(client: I2cClient) -> None:
        print(f"  [pca9539] removing {client.name}")
        i2c_set_clientdata(client.name, None)


class Ssd1306Driver(I2cDriver):
    """SSD1306 OLED display driver."""

    def __init__(self) -> None:
        super().__init__(
            name="ssd1306",
            id_table=[("ssd1306", "solomon,ssd1306")],
            probe=self._probe,
            remove=self._remove,
        )

    @staticmethod
    def _probe(client: I2cClient) -> bool:
        print(f"  [ssd1306] probing {client.name} at {client.addr_hex}")
        i2c_set_clientdata(client.name, {"width": 128, "height": 64, "type": "SSD1306"})
        print(f"  [ssd1306] detected: 128x64 OLED")
        return True

    @staticmethod
    def _remove(client: I2cClient) -> None:
        print(f"  [ssd1306] removing {client.name}")
        i2c_set_clientdata(client.name, None)


class Bme280Driver(I2cDriver):
    """BME280 temperature/humidity/pressure sensor driver."""

    def __init__(self) -> None:
        super().__init__(
            name="bme280",
            id_table=[("bme280", "bosch,bme280")],
            probe=self._probe,
            remove=self._remove,
        )

    @staticmethod
    def _probe(client: I2cClient) -> bool:
        print(f"  [bme280] probing {client.name} at {client.addr_hex}")
        i2c_set_clientdata(client.name, {
            "temperature": 25.3,
            "humidity": 55.7,
            "pressure": 101325.0,
        })
        print(f"  [bme280] detected: T=25.3C, H=55.7%, P=101325Pa")
        return True

    @staticmethod
    def _remove(client: I2cClient) -> None:
        print(f"  [bme280] removing {client.name}")
        i2c_set_clientdata(client.name, None)


# ---------------------------------------------------------------------------
# Dump Utility
# ---------------------------------------------------------------------------
def i2c_dump_state() -> None:
    """Print full I2C/SMBus subsystem state."""
    print("\n=== I2C/SMBus Subsystem State ===")
    print(f"Adapters: {len(_adapters)}")
    for adapter in _adapters.values():
        print(f"  {adapter!r}")
        for client in adapter._clients:
            drv = client.driver_name or "none"
            bound = "bound" if client.is_bound else "unbound"
            print(f"    {client!r} [{bound}] driver={drv!r}")
    unbound = [c for c in _clients if not c.is_bound]
    if unbound:
        print(f"Unbound clients: {len(unbound)}")
        for client in unbound:
            print(f"  {client!r}")
    print(f"Drivers: {len(_drivers)}")
    for drv in _drivers.values():
        print(f"  {drv!r}")
    print("================================\n")


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
def demo() -> None:
    """Demonstrate the I2C/SMBus subsystem."""
    print("\n" + "=" * 60)
    print("  UmerOS I2C/SMBus Framework Demo")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Create I2C adapters
    # ------------------------------------------------------------------
    print("\n--- Creating I2C Adapters ---")
    i2c_add_adapter("i2c-0", algo=I2C_ALGO_BIT_BANGING, speed=I2C_SPEED_STANDARD)
    i2c_add_adapter("i2c-1", algo=I2C_ALGO_I801, speed=I2C_SPEED_FAST)

    # ------------------------------------------------------------------
    # 2. Register I2C clients
    # ------------------------------------------------------------------
    print("\n--- Registering I2C Clients ---")
    i2c_new_client_device(
        "i2c-0", addr=0x50, name="eeprom",
        chip_name="atmel,24c256", driver_name="at24",
    )
    i2c_new_client_device(
        "i2c-0", addr=0x74, name="gpio-expander",
        chip_name="nxp,pca9539", driver_name="pca9539",
    )
    i2c_new_client_device(
        "i2c-1", addr=0x3C, name="oled",
        chip_name="solomon,ssd1306", driver_name="ssd1306",
    )
    i2c_new_client_device(
        "i2c-1", addr=0x76, name="sensor",
        chip_name="bosch,bme280", driver_name="bme280",
    )

    # ------------------------------------------------------------------
    # 3. Register I2C drivers (auto-binds to matching clients)
    # ------------------------------------------------------------------
    print("\n--- Registering I2C Drivers ---")
    i2c_add_driver(At24EepromDriver())
    i2c_add_driver(Pca9539GpioDriver())
    i2c_add_driver(Ssd1306Driver())
    i2c_add_driver(Bme280Driver())

    # ------------------------------------------------------------------
    # 4. Show probe and bind
    # ------------------------------------------------------------------
    print("\n--- Probe & Bind Results ---")
    for client in i2c_list_clients():
        status = "BOUND" if client.is_bound else "UNBOUND"
        drv = client.driver_name or "none"
        print(f"  {client.name} ({client.addr_hex}): {status}, driver={drv}")

    # ------------------------------------------------------------------
    # 5. SMBus byte/word/block transactions
    # ------------------------------------------------------------------
    print("\n--- SMBus Transactions ---")

    print("\n  SMBus Byte:")
    val = smbus_read_byte("eeprom", 0x00)
    print(f"    read_byte(eeprom, 0x00) = 0x{val:02x}" if val is not None else "    read failed")
    smbus_write_byte("eeprom", 0x00, 0xFF)

    print("\n  SMBus Byte Data:")
    val = smbus_read_byte_data("eeprom", 0x10)
    print(f"    read_byte_data(eeprom, 0x10) = 0x{val:02x}" if val is not None else "    read failed")
    smbus_write_byte_data("eeprom", 0x10, 0xAB)

    print("\n  SMBus Word Data:")
    val = smbus_read_word_data("sensor", 0x00)
    print(f"    read_word_data(sensor, 0x00) = 0x{val:04x}" if val is not None else "    read failed")
    smbus_write_word_data("sensor", 0x00, 0xBEEF)

    print("\n  SMBus Block Data:")
    blk = smbus_read_block_data("eeprom", 0x20)
    print(f"    read_block_data(eeprom, 0x20) = {blk.hex() if blk else 'empty'}")
    smbus_write_block_data("eeprom", 0x20, bytes(range(1, 9)))

    print("\n  SMBus I2C Block Data:")
    blk = smbus_read_i2c_block_data("sensor", 0x00, 16)
    print(f"    read_i2c_block_data(sensor, 0x00, 16) = {blk.hex() if blk else 'empty'}")
    smbus_write_i2c_block_data("sensor", 0x00, bytes(range(16)))

    print("\n  SMBus Quick:")
    smbus_quick("oled", "write")
    smbus_quick("eeprom", "read")

    print("\n  SMBus Process Call:")
    val = smbus_process_call("sensor", 0x00, 0x1234)
    print(f"    process_call(sensor, 0x00, 0x1234) = 0x{val:04x}" if val is not None else "    process_call failed")

    # ------------------------------------------------------------------
    # 6. I2C master send/recv
    # ------------------------------------------------------------------
    print("\n--- I2C Master Send/Recv ---")

    print("\n  Master Send:")
    sent = i2c_master_send("eeprom", b"\x00\x01\x02\x03\x04\x05")
    print(f"    master_send(eeprom) = {sent} bytes")

    print("\n  Master Recv:")
    recv = i2c_master_recv("sensor", 8)
    print(f"    master_recv(sensor, 8) = {recv.hex() if recv else 'failed'}")

    recv = i2c_master_recv("oled", 16)
    print(f"    master_recv(oled, 16) = {recv.hex() if recv else 'failed'}")

    # ------------------------------------------------------------------
    # 7. Multi-message transfers
    # ------------------------------------------------------------------
    print("\n--- Multi-Message Transfers ---")

    msgs = [
        I2cMsg(addr=0x50, flags=0, buf=b"\x00\x10"),
        I2cMsg(addr=0x50, flags=I2C_M_RD, buf=b'\x00' * 8),
    ]
    i2c_transfer("i2c-0", msgs)

    msgs = [
        I2cMsg(addr=0x76, flags=0, buf=b"\xD0"),
        I2cMsg(addr=0x76, flags=I2C_M_RD, buf=b'\x00'),
        I2cMsg(addr=0x76, flags=0, buf=b"\x88\x01"),
    ]
    i2c_transfer("i2c-1", msgs)

    # ------------------------------------------------------------------
    # 8. Adapter speed setting
    # ------------------------------------------------------------------
    print("\n--- Adapter Speed Setting ---")
    i2c_adapter_set_speed("i2c-0", I2C_SPEED_FAST)
    i2c_adapter_set_speed("i2c-1", I2C_SPEED_FAST_PLUS)
    i2c_adapter_set_speed("i2c-0", I2C_SPEED_HIGH)

    # ------------------------------------------------------------------
    # 9. Client listing
    # ------------------------------------------------------------------
    print("\n--- Client Listing ---")
    print("  All clients:")
    for client in i2c_list_clients():
        print(f"    {client!r}")

    print("\n  Clients on i2c-0:")
    for client in i2c_list_clients("i2c-0"):
        print(f"    {client!r}")

    print("\n  Clients on i2c-1:")
    for client in i2c_list_clients("i2c-1"):
        print(f"    {client!r}")

    # ------------------------------------------------------------------
    # 10. Adapter dump
    # ------------------------------------------------------------------
    print("\n--- Adapter Listing ---")
    for adapter in i2c_list_adapters():
        print(f"  {adapter!r}")

    # ------------------------------------------------------------------
    # 11. Functionality check
    # ------------------------------------------------------------------
    print("\n--- Functionality Check ---")
    for adapter in i2c_list_adapters():
        has_i2c = i2c_check_functionality(adapter.name, 0x00000001)
        has_smbus_byte = i2c_check_functionality(adapter.name, 0x00000004)
        has_smbus_word = i2c_check_functionality(adapter.name, 0x00000010)
        print(
            f"  {adapter.name}: I2C={has_i2c}, "
            f"SMBus_byte={has_smbus_byte}, SMBus_word={has_smbus_word}"
        )

    # ------------------------------------------------------------------
    # 12. Client private data
    # ------------------------------------------------------------------
    print("\n--- Client Private Data ---")
    i2c_set_clientdata("eeprom", {"vendor": "Atmel", "model": "AT24C256"})
    pdata = i2c_get_clientdata("eeprom")
    print(f"  eeprom data: {pdata}")

    i2c_set_clientdata("oled", {"resolution": "128x64", "interface": "I2C"})
    pdata = i2c_get_clientdata("oled")
    print(f"  oled data: {pdata}")

    # ------------------------------------------------------------------
    # 13. Full state dump
    # ------------------------------------------------------------------
    i2c_dump_state()

    # ------------------------------------------------------------------
    # 14. Unregister and cleanup
    # ------------------------------------------------------------------
    print("--- Unregistering ---")
    i2c_unregister_device("oled")
    i2c_del_driver("bme280")
    i2c_del_adapter("i2c-1")

    i2c_dump_state()
    print("=" * 60)
    print("  I2C/SMBus Framework Demo Complete")
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo()
