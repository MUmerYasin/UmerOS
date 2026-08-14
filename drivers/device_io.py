"""
UmerOS Device I/O Framework
===========================
Kernel Bus-Independent Device Accesses.
Implements MMIO (readb/w/l/q, writeb/w/l/q, ioremap),
Port I/O (inb/w/l, outb/w/l), DMA buffers (alloc, map, sync),
and simulated UART/SPI/I2C devices.
"""

from __future__ import annotations

import ctypes
import struct
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Global registries
# ---------------------------------------------------------------------------
_mmio_regions: Dict[str, "MmioRegion"] = {}
_io_ports: Dict[int, "IoPort"] = {}
_dma_buffers: Dict[str, "DmaBuffer"] = {}
_port_regions: Dict[Tuple[int, int], str] = {}
_next_dma_phys: int = 0x4000_0000
_next_io_virt: int = 0xF000_0000
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MmioRegion:
    """Memory-mapped I/O region"""
    name: str
    phys_addr: int
    size: int
    virt_addr: int  # in simulation, just offset from base
    base_addr: int = 0
    is_mapped: bool = False
    access_size: int = 4  # 1,2,4,8 bytes
    _memory: bytearray = field(default_factory=lambda: bytearray(4096))
    _ops: Dict[str, Any] = field(default_factory=dict)
    _owner: str = ""

    def read(self, offset: int, width: int = 4) -> int:
        if not self.is_mapped:
            raise RuntimeError(f"MMIO region '{self.name}' is not mapped")
        # Fire read callback if registered (device overrides memory-backed read)
        cb = self._ops.get("read")
        if cb is not None:
            return cb(self.name, offset)
        if offset + width > len(self._memory):
            raise ValueError(f"Read at offset 0x{offset:X} + {width} exceeds region size {len(self._memory)}")
        val = int.from_bytes(self._memory[offset:offset + width], byteorder="little")
        return val

    def write(self, offset: int, value: int, width: int = 4) -> None:
        if not self.is_mapped:
            raise RuntimeError(f"MMIO region '{self.name}' is not mapped")
        if offset + width > len(self._memory):
            raise ValueError(f"Write at offset 0x{offset:X} + {width} exceeds region size {len(self._memory)}")
        self._memory[offset:offset + width] = value.to_bytes(width, byteorder="little")
        # Fire write callback if registered
        cb = self._ops.get("write")
        if cb is not None:
            cb(self.name, offset, value, width)


@dataclass
class IoPort:
    """I/O port (x86-style port I/O)"""
    port: int  # 0x0000 - 0xFFFF
    size: int  # 1, 2, 4 bytes
    name: str = ""
    _value: int = 0
    _read_only: bool = False
    _write_only: bool = False
    _callback_read: Optional[Callable] = None
    _callback_write: Optional[Callable] = None

    def read(self) -> int:
        if self._callback_read is not None:
            return self._callback_read(self.port, self.size)
        return self._value

    def write(self, value: int) -> None:
        if self._read_only:
            raise PermissionError(f"Port 0x{self.port:04X} is read-only")
        mask = (1 << (self.size * 8)) - 1
        self._value = value & mask
        if self._callback_write is not None:
            self._callback_write(self.port, self.size, self._value)


@dataclass
class DmaBuffer:
    """DMA buffer"""
    name: str
    size: int
    phys_addr: int
    virt_addr: int
    is_coherent: bool = True
    direction: str = "bidirectional"
    _data: bytearray = field(default_factory=bytes)
    _is_allocated: bool = False
    _owner: str = ""

    def allocate(self) -> None:
        self._data = bytearray(self.size)
        self._is_allocated = True

    def free(self) -> None:
        self._data = bytearray()
        self._is_allocated = False


@dataclass
class PioXfer:
    """Port I/O transfer descriptor"""
    port: int
    size: int  # 1,2,4
    value: int = 0
    count: int = 1


# ---------------------------------------------------------------------------
# MMIO API  (Kernel ioremap / readb / writeb style)
# ---------------------------------------------------------------------------

def devm_ioremap(name: str, phys_addr: int, size: int) -> MmioRegion:
    """Map MMIO region - like devm_ioremap()"""
    global _next_io_virt
    with _lock:
        if name in _mmio_regions:
            raise KeyError(f"MMIO region '{name}' already mapped")
        region = MmioRegion(
            name=name,
            phys_addr=phys_addr,
            size=size,
            virt_addr=_next_io_virt,
            base_addr=phys_addr,
            is_mapped=True,
            _memory=bytearray(size),
        )
        _next_io_virt += size
        _mmio_regions[name] = region
    return region


def devm_iounmap(name: str) -> None:
    """Unmap MMIO region"""
    with _lock:
        if name not in _mmio_regions:
            raise KeyError(f"MMIO region '{name}' not found")
        region = _mmio_regions.pop(name)
        region.is_mapped = False


def _get_region(name: str) -> MmioRegion:
    try:
        return _mmio_regions[name]
    except KeyError:
        raise KeyError(f"MMIO region '{name}' not mapped")


def readb(region_name: str, offset: int = 0) -> int:
    """Read byte - like readb()"""
    return _get_region(region_name).read(offset, 1)


def readw(region_name: str, offset: int = 0) -> int:
    """Read 16-bit word"""
    return _get_region(region_name).read(offset, 2)


def readl(region_name: str, offset: int = 0) -> int:
    """Read 32-bit word"""
    return _get_region(region_name).read(offset, 4)


def readq(region_name: str, offset: int = 0) -> int:
    """Read 64-bit quad word"""
    return _get_region(region_name).read(offset, 8)


def writeb(region_name: str, value: int, offset: int = 0) -> None:
    """Write byte - like writeb()"""
    _get_region(region_name).write(offset, value, 1)


def writew(region_name: str, value: int, offset: int = 0) -> None:
    """Write 16-bit word"""
    _get_region(region_name).write(offset, value, 2)


def writel(region_name: str, value: int, offset: int = 0) -> None:
    """Write 32-bit word"""
    _get_region(region_name).write(offset, value, 4)


def writeq(region_name: str, value: int, offset: int = 0) -> None:
    """Write 64-bit quad word"""
    _get_region(region_name).write(offset, value, 8)


def ioread8(region_name: str, offset: int = 0) -> int:
    """Read 8-bit (ioremapped)"""
    return readb(region_name, offset)


def ioread16(region_name: str, offset: int = 0) -> int:
    """Read 16-bit (ioremapped)"""
    return readw(region_name, offset)


def ioread32(region_name: str, offset: int = 0) -> int:
    """Read 32-bit (ioremapped)"""
    return readl(region_name, offset)


def iowrite8(region_name: str, value: int, offset: int = 0) -> None:
    """Write 8-bit (ioremapped)"""
    writeb(region_name, value, offset)


def iowrite16(region_name: str, value: int, offset: int = 0) -> None:
    """Write 16-bit (ioremapped)"""
    writew(region_name, value, offset)


def iowrite32(region_name: str, value: int, offset: int = 0) -> None:
    """Write 32-bit (ioremapped)"""
    writel(region_name, value, offset)


def memset_io(region_name: str, value: int, count: int, offset: int = 0) -> None:
    """memset on I/O memory"""
    region = _get_region(region_name)
    for i in range(count):
        region.write(offset + i, value, 1)


def memcpy_from_io(dest: bytearray, region_name: str, offset: int, count: int) -> bytearray:
    """Copy from I/O memory"""
    region = _get_region(region_name)
    for i in range(count):
        dest[i] = region.read(offset + i, 1) & 0xFF
    return dest


def memcpy_to_io(region_name: str, offset: int, src: bytes | bytearray) -> None:
    """Copy to I/O memory"""
    region = _get_region(region_name)
    for i, byte_val in enumerate(src):
        region.write(offset + i, byte_val, 1)


# ---------------------------------------------------------------------------
# Port I/O API  (x86-style in/out)
# ---------------------------------------------------------------------------

def devm_request_region(port: int, size: int, name: str) -> IoPort:
    """Request I/O port region"""
    with _lock:
        key = (port, size)
        if key in _port_regions:
            raise KeyError(f"Port region 0x{port:04X} size {size} already claimed")
        io_port = IoPort(port=port, size=size, name=name)
        _io_ports[port] = io_port
        _port_regions[key] = name
    return io_port


def devm_release_region(port: int, size: int) -> None:
    """Release I/O port region"""
    with _lock:
        key = (port, size)
        if key not in _port_regions:
            raise KeyError(f"Port region 0x{port:04X} size {size} not found")
        _port_regions.pop(key, None)
        _io_ports.pop(port, None)


def _get_port(port: int) -> IoPort:
    try:
        return _io_ports[port]
    except KeyError:
        raise KeyError(f"I/O port 0x{port:04X} not allocated")


def inb(port: int) -> int:
    """Read byte from port - like inb()"""
    return _get_port(port).read() & 0xFF


def inw(port: int) -> int:
    """Read 16-bit from port"""
    return _get_port(port).read() & 0xFFFF


def inl(port: int) -> int:
    """Read 32-bit from port"""
    return _get_port(port).read() & 0xFFFFFFFF


def outb(port: int, value: int) -> None:
    """Write byte to port - like outb()"""
    _get_port(port).write(value & 0xFF)


def outw(port: int, value: int) -> None:
    """Write 16-bit to port"""
    _get_port(port).write(value & 0xFFFF)


def outl(port: int, value: int) -> None:
    """Write 32-bit to port"""
    _get_port(port).write(value & 0xFFFFFFFF)


def insb(port: int, count: int) -> List[int]:
    """Read string of bytes from port"""
    return [inb(port) for _ in range(count)]


def insw(port: int, count: int) -> List[int]:
    """Read string of words from port"""
    return [inw(port) for _ in range(count)]


def outsb(port: int, data: bytes | bytearray | List[int]) -> None:
    """Write string of bytes to port"""
    for b in data:
        outb(port, b & 0xFF)


def outsw(port: int, data: bytes | bytearray | List[int]) -> None:
    """Write string of words to port"""
    for i in range(0, len(data), 2):
        word = data[i] | (data[i + 1] << 8) if i + 1 < len(data) else data[i]
        outw(port, word & 0xFFFF)


# ---------------------------------------------------------------------------
# DMA API
# ---------------------------------------------------------------------------

def dma_alloc_coherent(name: str, size: int, direction: str = "bidirectional") -> DmaBuffer:
    """Allocate coherent DMA buffer"""
    global _next_dma_phys
    with _lock:
        if name in _dma_buffers:
            raise KeyError(f"DMA buffer '{name}' already exists")
        phys = _next_dma_phys
        _next_dma_phys += size
        buf = DmaBuffer(
            name=name,
            size=size,
            phys_addr=phys,
            virt_addr=phys,  # simulation: identity map
            is_coherent=True,
            direction=direction,
        )
        buf.allocate()
        buf._owner = name
        _dma_buffers[name] = buf
    return buf


def dma_free_coherent(name: str) -> None:
    """Free coherent DMA buffer"""
    with _lock:
        if name not in _dma_buffers:
            raise KeyError(f"DMA buffer '{name}' not found")
        buf = _dma_buffers.pop(name)
        buf.free()


def dma_map_single(name: str, phys_addr: int, size: int, direction: str) -> int:
    """Map single buffer for DMA - returns (simulated) bus address"""
    if name not in _dma_buffers:
        raise KeyError(f"DMA buffer '{name}' not found")
    return phys_addr  # simulation: identity mapping


def dma_unmap_single(name: str, phys_addr: int, size: int, direction: str) -> None:
    """Unmap single DMA buffer"""
    pass  # no-op in simulation


def dma_sync_single_for_cpu(name: str, phys_addr: int, size: int, direction: str) -> None:
    """Sync DMA buffer for CPU access"""
    if name not in _dma_buffers:
        raise KeyError(f"DMA buffer '{name}' not found")


def dma_sync_single_for_device(name: str, phys_addr: int, size: int, direction: str) -> None:
    """Sync DMA buffer for device access"""
    if name not in _dma_buffers:
        raise KeyError(f"DMA buffer '{name}' not found")


# ---------------------------------------------------------------------------
# Simulated devices
# ---------------------------------------------------------------------------

class SimUart:
    """Simulated UART with MMIO registers"""
    # Standard 16550-compatible register offsets
    REG_THR = 0x00   # Transmit Holding Register (write)
    REG_RBR = 0x00   # Receive Buffer Register (read)
    REG_DLL = 0x00   # Divisor Latch Low (write, when DLAB=1)
    REG_DLH = 0x01   # Divisor Latch High (write, when DLAB=1)
    REG_IER = 0x01   # Interrupt Enable Register
    REG_IIR = 0x02   # Interrupt Identification Register (read)
    REG_FCR = 0x02   # FIFO Control Register (write)
    REG_LCR = 0x03   # Line Control Register
    REG_MCR = 0x04   # Modem Control Register
    REG_LSR = 0x05   # Line Status Register
    REG_MSR = 0x06   # Modem Status Register
    REG_SCR = 0x07   # Scratch Register

    LSR_THRE = 0x20  # TX holding register empty
    LSR_DR = 0x01    # Data ready

    def __init__(self, base_addr: int, name: str = "uart0") -> None:
        self.name = name
        self.base_addr = base_addr
        self._rx_fifo: bytearray = bytearray()
        self._tx_fifo: bytearray = bytearray()
        self._ier: int = 0
        self._lcr: int = 0
        self._mcr: int = 0
        self._fcr: int = 0
        self._msr: int = 0
        self._scr: int = 0
        self._dll: int = 0x01  # default divisor = 1 (115200 baud at 1.8432 MHz)
        self._dlh: int = 0
        self._region: Optional[MmioRegion] = None
        self._region = devm_ioremap(name, base_addr, 0x1000)
        # Register callbacks for simulated MMIO
        self._region._ops["write"] = self._on_mmio_write
        self._region._ops["read"] = self._on_mmio_read
        # Initialize LSR so THRE is set (TX empty)
        self._region._memory[self.REG_LSR] = self.LSR_THRE

    def _on_mmio_write(self, region_name: str, offset: int, value: int, width: int) -> None:
        reg = offset & 0x07
        dlab = (self._lcr >> 7) & 1
        if reg == self.REG_THR:
            if dlab:
                self._dll = value & 0xFF
            else:
                self._tx_fifo.append(value & 0xFF)
        elif reg == self.REG_DLH:
            if dlab:
                self._dlh = value & 0xFF
        elif reg == self.REG_IER:
            if not dlab:
                self._ier = value & 0xFF
        elif reg == self.REG_FCR:
            self._fcr = value & 0xFF
        elif reg == self.REG_LCR:
            self._lcr = value & 0xFF
        elif reg == self.REG_MCR:
            self._mcr = value & 0xFF
        elif reg == self.REG_SCR:
            self._scr = value & 0xFF

    def _on_mmio_read(self, region_name: str, offset: int) -> int:
        reg = offset & 0x07
        dlab = (self._lcr >> 7) & 1
        # DLAB must be checked first — on real 16550, DLAB=1 remaps
        # offsets 0x00/0x01 from RBR/IER to DLL/DLH
        if reg == self.REG_DLL and dlab:
            return self._dll
        elif reg == self.REG_DLH and dlab:
            return self._dlh
        elif reg == self.REG_RBR:
            if self._rx_fifo:
                return self._rx_fifo.pop(0)
            return 0
        elif reg == self.REG_IER and not dlab:
            return self._ier
        elif reg == self.REG_IIR:
            return 0x01  # no interrupt pending
        elif reg == self.REG_LCR:
            return self._lcr
        elif reg == self.REG_LSR:
            lsr = self.LSR_THRE  # always TX empty in simulation
            if self._rx_fifo:
                lsr |= self.LSR_DR
            return lsr
        elif reg == self.REG_MSR:
            return self._msr
        elif reg == self.REG_SCR:
            return self._scr
        return 0

    def put_rx_byte(self, byte_val: int) -> None:
        """Simulate receiving a byte from the serial line"""
        if len(self._rx_fifo) < 256:
            self._rx_fifo.append(byte_val & 0xFF)

    def get_tx_bytes(self) -> bytes:
        """Retrieve bytes written to the TX FIFO"""
        data = bytes(self._tx_fifo)
        self._tx_fifo.clear()
        return data

    def read_register(self, reg_offset: int) -> int:
        if self._region is None:
            return 0
        return self._region.read(reg_offset, 1)

    def write_register(self, reg_offset: int, value: int) -> None:
        if self._region is not None:
            self._region.write(reg_offset, value, 1)

    def shutdown(self) -> None:
        if self.name in _mmio_regions:
            devm_iounmap(self.name)


class SimSpi:
    """Simulated SPI controller with MMIO registers"""
    REG_CR = 0x00    # Control register
    REG_SR = 0x01    # Status register
    REG_DR = 0x02    # Data register (TX/RX)
    REG_BAUD = 0x03  # Baud rate divisor
    REG_CS = 0x04    # Chip select

    SR_TXE = 0x02    # TX empty
    SR_RXNE = 0x01   # RX not empty
    SR_BSY = 0x04    # Busy

    def __init__(self, base_addr: int, name: str = "spi0") -> None:
        self.name = name
        self.base_addr = base_addr
        self._cr: int = 0
        self._baud: int = 0
        self._cs: int = 0
        self._tx_fifo: bytearray = bytearray()
        self._rx_fifo: bytearray = bytearray()
        self._region: Optional[MmioRegion] = devm_ioremap(name, base_addr, 0x1000)
        self._region._ops["write"] = self._on_write
        self._region._ops["read"] = self._on_read
        self._region._memory[self.REG_SR] = self.SR_TXE

    def _on_write(self, region_name: str, offset: int, value: int, width: int) -> None:
        reg = offset & 0x07
        if reg == self.REG_CR:
            self._cr = value & 0xFF
        elif reg == self.REG_DR:
            self._tx_fifo.append(value & 0xFF)
            # Simulate echo-back for loopback testing
            self._rx_fifo.append(value & 0xFF)
        elif reg == self.REG_BAUD:
            self._baud = value & 0xFF
        elif reg == self.REG_CS:
            self._cs = value & 0xFF

    def _on_read(self, region_name: str, offset: int) -> int:
        reg = offset & 0x07
        if reg == self.REG_DR:
            if self._rx_fifo:
                return self._rx_fifo.pop(0)
            return 0
        elif reg == self.REG_SR:
            sr = self.SR_TXE
            if self._rx_fifo:
                sr |= self.SR_RXNE
            return sr
        elif reg == self.REG_CR:
            return self._cr
        return 0

    def read_register(self, reg_offset: int) -> int:
        if self._region is None:
            return 0
        return self._region.read(reg_offset, 1)

    def write_register(self, reg_offset: int, value: int) -> None:
        if self._region is not None:
            self._region.write(reg_offset, value, 1)

    def exchange(self, data: bytes) -> bytes:
        """Full-duplex SPI exchange - sends data and returns response"""
        result = bytearray()
        for b in data:
            self.write_register(self.REG_DR, b)
            result.append(self.read_register(self.REG_DR))
        return bytes(result)

    def shutdown(self) -> None:
        if self.name in _mmio_regions:
            devm_iounmap(self.name)


class SimI2c:
    """Simulated I2C controller with MMIO registers"""
    REG_CR = 0x00    # Control register
    REG_SR = 0x01    # Status register
    REG_DR = 0x02    # Data register
    REG_ADDR = 0x03  # Slave address
    REG_SCL = 0x04   # SCL period

    CR_START = 0x08
    CR_STOP = 0x04
    CR_ACK = 0x02
    CR_NACK = 0x01

    SR_TXE = 0x02
    SR_RXNE = 0x01
    SR_BSY = 0x04
    SR_NACK = 0x10

    def __init__(self, base_addr: int, name: str = "i2c0") -> None:
        self.name = name
        self.base_addr = base_addr
        self._cr: int = 0
        self._sr: int = self.SR_TXE
        self._addr: int = 0
        self._scl: int = 100  # kHz
        self._tx_fifo: bytearray = bytearray()
        self._rx_fifo: bytearray = bytearray()
        self._region: Optional[MmioRegion] = devm_ioremap(name, base_addr, 0x1000)
        self._region._ops["write"] = self._on_write
        self._region._ops["read"] = self._on_read

    def _on_write(self, region_name: str, offset: int, value: int, width: int) -> None:
        reg = offset & 0x07
        if reg == self.REG_CR:
            self._cr = value & 0xFF
            if value & self.CR_START:
                self._sr |= self.SR_BSY
            if value & self.CR_STOP:
                self._sr &= ~self.SR_BSY
        elif reg == self.REG_DR:
            self._tx_fifo.append(value & 0xFF)
        elif reg == self.REG_ADDR:
            self._addr = value & 0x7F
        elif reg == self.REG_SCL:
            self._scl = value & 0xFF

    def _on_read(self, region_name: str, offset: int) -> int:
        reg = offset & 0x07
        if reg == self.REG_DR:
            if self._rx_fifo:
                return self._rx_fifo.pop(0)
            return 0
        elif reg == self.REG_SR:
            sr = self._sr
            if self._tx_fifo:
                sr |= self.SR_TXE
            if self._rx_fifo:
                sr |= self.SR_RXNE
            return sr
        elif reg == self.REG_CR:
            return self._cr
        return 0

    def read_register(self, reg_offset: int) -> int:
        if self._region is None:
            return 0
        return self._region.read(reg_offset, 1)

    def write_register(self, reg_offset: int, value: int) -> None:
        if self._region is not None:
            self._region.write(reg_offset, value, 1)

    def write_byte(self, addr: int, data: bytes) -> None:
        """Simulate I2C write transaction"""
        self.write_register(self.REG_ADDR, addr)
        self.write_register(self.REG_CR, self.CR_START)
        for b in data:
            self.write_register(self.REG_DR, b)
        self.write_register(self.REG_CR, self.CR_STOP)

    def read_byte(self, addr: int, count: int = 1) -> bytes:
        """Simulate I2C read transaction"""
        result = bytearray()
        self.write_register(self.REG_ADDR, addr)
        self.write_register(self.REG_CR, self.CR_START)
        for _ in range(count):
            result.append(self.read_register(self.REG_DR))
        self.write_register(self.REG_CR, self.CR_STOP)
        return bytes(result)

    def shutdown(self) -> None:
        if self.name in _mmio_regions:
            devm_iounmap(self.name)


# ---------------------------------------------------------------------------
# Registry access helpers
# ---------------------------------------------------------------------------

def list_mmio_regions() -> Dict[str, MmioRegion]:
    """Return snapshot of all mapped MMIO regions"""
    return dict(_mmio_regions)


def list_io_ports() -> Dict[int, IoPort]:
    """Return snapshot of all allocated I/O ports"""
    return dict(_io_ports)


def list_dma_buffers() -> Dict[str, DmaBuffer]:
    """Return snapshot of all DMA buffers"""
    return dict(_dma_buffers)


# ---------------------------------------------------------------------------
# Demo / self-test
# ---------------------------------------------------------------------------

def _demo() -> None:
    """Comprehensive demonstration of device I/O framework"""
    print("=" * 72)
    print("UmerOS Device I/O Framework  -  Bus-Independent Device Accesses")
    print("=" * 72)

    # ------------------------------------------------------------------ MMIO
    print("\n--- MMIO Regions ---")
    uart_region = devm_ioremap("uart0_regs", 0x1000_0000, 4096)
    flash_region = devm_ioremap("flash0", 0x0010_0000, 0x100000)
    print(f"  Mapped '{uart_region.name}' at phys 0x{uart_region.phys_addr:08X}, "
          f"size {uart_region.size} bytes, virt 0x{uart_region.virt_addr:08X}")
    print(f"  Mapped '{flash_region.name}' at phys 0x{flash_region.phys_addr:08X}, "
          f"size {flash_region.size} bytes, virt 0x{flash_region.virt_addr:08X}")

    # Write/read at various widths
    writeb("flash0", 0xAB, offset=0x00)
    writew("flash0", 0xBEEF, offset=0x100)
    writel("flash0", 0xDEAD_BEEF, offset=0x200)
    writeq("flash0", 0x0123_4567_89AB_CDEF, offset=0x300)
    print(f"  writeb  @0x000: 0x{readb('flash0', 0x00):02X}")
    print(f"  writew  @0x100: 0x{readw('flash0', 0x100):04X}")
    print(f"  writel  @0x200: 0x{readl('flash0', 0x200):08X}")
    print(f"  writeq  @0x300: 0x{readq('flash0', 0x300):016X}")

    # ioread / iowrite variants
    iowrite8("flash0", 0x42, offset=0x400)
    iowrite16("flash0", 0x1234, offset=0x410)
    iowrite32("flash0", 0xCAFE_BABE, offset=0x420)
    print(f"  ioread8  @0x400: 0x{ioread8('flash0', 0x400):02X}")
    print(f"  ioread16 @0x410: 0x{ioread16('flash0', 0x410):04X}")
    print(f"  ioread32 @0x420: 0x{ioread32('flash0', 0x420):08X}")

    # memset_io
    memset_io("flash0", 0xFF, count=16, offset=0x500)
    sample = readl("flash0", 0x500)
    print(f"  memset_io @0x500 (16 bytes 0xFF): readback 0x{sample:08X}")

    # memcpy_to_io / memcpy_from_io
    src_data = bytes(range(16))
    memcpy_to_io("flash0", 0x600, src_data)
    dest = bytearray(16)
    memcpy_from_io(dest, "flash0", 0x600, 16)
    print(f"  memcpy roundtrip @0x600: {list(dest)}")

    # Unmap
    devm_iounmap("flash0")
    print("  Unmapped 'flash0'")

    # ------------------------------------------------------------- Port I/O
    print("\n--- Port I/O (x86-style) ---")
    pio0 = devm_request_region(0x3F8, 8, "serial0")
    pio1 = devm_request_region(0x60, 1, "keyboard")
    print(f"  Requested port 0x{pio0.port:04X} name='{pio0.name}'")
    print(f"  Requested port 0x{pio1.port:04X} name='{pio1.name}'")

    outb(0x3F8, 0x41)
    outw(0x3F8, 0x1234)
    outl(0x3F8, 0xDEADBEEF)
    print(f"  inb  0x3F8 = 0x{inb(0x3F8):02X}")
    print(f"  inw  0x3F8 = 0x{inw(0x3F8):04X}")
    print(f"  inl  0x3F8 = 0x{inl(0x3F8):08X}")

    # String I/O
    outsb(0x3F8, [0x48, 0x65, 0x6C, 0x6C, 0x6F])
    echo = insb(0x3F8, 5)
    print(f"  outsb/insb: {echo}  -> {''.join(chr(b) for b in echo)}")

    outsw(0x3F8, [0x4142, 0x4344])
    echo_w = insw(0x3F8, 2)
    print(f"  outsw/insw: {[f'0x{w:04X}' for w in echo_w]}")

    devm_release_region(0x3F8, 8)
    devm_release_region(0x60, 1)
    print("  Released port regions")

    # --------------------------------------------------------------- DMA
    print("\n--- DMA Buffers ---")
    dma_tx = dma_alloc_coherent("dma_tx", 4096, direction="to_device")
    dma_rx = dma_alloc_coherent("dma_rx", 8192, direction="from_device")
    print(f"  Allocated '{dma_tx.name}': size={dma_tx.size}, "
          f"phys=0x{dma_tx.phys_addr:08X}, coherent={dma_tx.is_coherent}")
    print(f"  Allocated '{dma_rx.name}': size={dma_rx.size}, "
          f"phys=0x{dma_rx.phys_addr:08X}, coherent={dma_rx.is_coherent}")

    # DMA map / sync
    bus_addr = dma_map_single("dma_tx", dma_tx.phys_addr, dma_tx.size, "to_device")
    print(f"  dma_map_single '{dma_tx.name}': bus addr=0x{bus_addr:08X}")
    dma_sync_single_for_cpu("dma_tx", dma_tx.phys_addr, dma_tx.size, "to_device")
    dma_sync_single_for_device("dma_tx", dma_tx.phys_addr, dma_tx.size, "to_device")
    dma_unmap_single("dma_tx", dma_tx.phys_addr, dma_tx.size, "to_device")
    print(f"  DMA sync and unmap completed for '{dma_tx.name}'")

    dma_free_coherent("dma_tx")
    dma_free_coherent("dma_rx")
    print("  Freed DMA buffers")

    # --------------------------------------------------------- SimUart
    print("\n--- Simulated UART (16550) ---")
    uart = SimUart(base_addr=0x1000_1000, name="sim_uart")
    print(f"  Created UART '{uart.name}' at base 0x{uart.base_addr:08X}")

    # Write divisor latch (set baud rate)
    uart.write_register(SimUart.REG_LCR, 0x80)  # DLAB=1
    uart.write_register(SimUart.REG_DLL, 0x01)
    uart.write_register(SimUart.REG_DLH, 0x00)
    print(f"  DLL=0x{uart.read_register(SimUart.REG_DLL):02X}, "
          f"DLH=0x{uart.read_register(SimUart.REG_DLH):02X}")

    # Restore DLAB=0
    uart.write_register(SimUart.REG_LCR, 0x03)

    # TX test
    for ch in b"Hello UmerOS":
        uart.write_register(SimUart.REG_THR, ch)
    tx_data = uart.get_tx_bytes()
    print(f"  TX output: '{tx_data.decode()}'")

    # RX test
    for ch in b"ACK":
        uart.put_rx_byte(ch)
    lsr = uart.read_register(SimUart.REG_LSR)
    print(f"  LSR=0x{lsr:02X} (DR={'set' if lsr & SimUart.LSR_DR else 'clear'}, "
          f"THRE={'set' if lsr & SimUart.LSR_THRE else 'clear'})")
    rx = bytearray()
    for _ in range(3):
        rx.append(uart.read_register(SimUart.REG_RBR))
    print(f"  RX input: '{bytes(rx).decode()}'")

    # Scratch register
    uart.write_register(SimUart.REG_SCR, 0xA5)
    print(f"  SCR readback: 0x{uart.read_register(SimUart.REG_SCR):02X}")

    uart.shutdown()

    # ---------------------------------------------------------- SimSpi
    print("\n--- Simulated SPI Controller ---")
    spi = SimSpi(base_addr=0x1000_2000, name="sim_spi")
    print(f"  Created SPI '{spi.name}' at base 0x{spi.base_addr:08X}")

    resp = spi.exchange(b"\x9F\x00\x00\x00")
    print(f"  SPI exchange JEDEC ID: {[f'0x{b:02X}' for b in resp]}")
    spi.shutdown()

    # --------------------------------------------------------- SimI2c
    print("\n--- Simulated I2C Controller ---")
    i2c = SimI2c(base_addr=0x1000_3000, name="sim_i2c")
    print(f"  Created I2C '{i2c.name}' at base 0x{i2c.base_addr:08X}")

    i2c.write_byte(0x50, b"\x00\x42")
    i2c.write_register(SimI2c.REG_DR, 0x55)
    print(f"  I2C DR readback: 0x{i2c.read_register(SimI2c.REG_DR):02X}")
    i2c.shutdown()

    # -------------------------------------------------------- Summary
    print("\n--- Registry Summary ---")
    mmio = list_mmio_regions()
    ports = list_io_ports()
    dma = list_dma_buffers()
    print(f"  MMIO regions:  {list(mmio.keys())}")
    print(f"  I/O ports:     {[f'0x{p:04X}' for p in ports]}")
    print(f"  DMA buffers:   {list(dma.keys())}")

    print("\n" + "=" * 72)
    print("Device I/O framework demo complete.")
    print("=" * 72)


if __name__ == "__main__":
    _demo()
