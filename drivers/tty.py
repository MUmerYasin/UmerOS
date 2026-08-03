"""
UmerOS TTY/Serial Framework
============================
Linux kernel TTY and serial port subsystem.
Implements TTY drivers, UART ports (8250/16550), serial consoles,
PTY (pseudo-terminals), terminal settings, modem control, and FIFO operations.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TTY_DRIVER_TYPE_SYSTEM = 0x0001
TTY_DRIVER_TYPE_CONSOLE = 0x0002
TTY_DRIVER_TYPE_SERIAL = 0x0004
TTY_DRIVER_TYPE_PTY = 0x0008

TTY_TYPE_LDISC = 0
TTY_TYPE_DRIVER = 1
TTY_TYPE_CONSOLE = 2

UPIO_PORT = 0
UPIO_MEM = 1
UPIO_AU = 2
UPIO_TSI = 3
UPIO_MEM32 = 4

PORT_UNKNOWN = 0
PORT_8250 = 1
PORT_16550 = 2
PORT_ST16C680 = 3

TIOCM_LE = 0x0001
TIOCM_DTR = 0x0002
TIOCM_RTS = 0x0004
TIOCM_ST = 0x0008
TIOCM_SR = 0x0010
TIOCM_CTS = 0x0020
TIOCM_CAR = 0x0040
TIOCM_CD = 0x0040
TIOCM_RNG = 0x0080
TIOCM_RI = 0x0080
TIOCM_DSR = 0x0100

CREAD = 0x0080
CLOCAL = 0x0800
CS8 = 0x0030
CSTOPB = 0x0040
PARENB = 0x0100
CCTS_OFLOW = 0x00010000
CRTSCTS = 0x0400

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TtyOps:
    """TTY operations."""
    open: Optional[Callable] = None
    close: Optional[Callable] = None
    write: Optional[Callable] = None
    put_char: Optional[Callable] = None
    flush_chars: Optional[Callable] = None
    write_room: Optional[Callable] = None
    chars_in_buffer: Optional[Callable] = None
    ioctl: Optional[Callable] = None
    set_termios: Optional[Callable] = None
    throttle: Optional[Callable] = None
    unthrottle: Optional[Callable] = None
    stop: Optional[Callable] = None
    start: Optional[Callable] = None
    hangup: Optional[Callable] = None
    break_ctl: Optional[Callable] = None
    receive_buf: Optional[Callable] = None
    driver_has_hup_int: bool = True


@dataclass
class Ktermios:
    """Terminal settings (kernel termios)."""
    iflag: int = 0
    oflag: int = 0
    cflag: int = CREAD | CLOCAL
    lflag: int = 0
    line: int = 0
    ispeed: int = 9600
    ospeed: int = 9600

    def copy(self) -> "Ktermios":
        return Ktermios(
            iflag=self.iflag,
            oflag=self.oflag,
            cflag=self.cflag,
            lflag=self.lflag,
            line=self.line,
            ispeed=self.ispeed,
            ospeed=self.ospeed,
        )

    def __repr__(self) -> str:
        return (
            f"Ktermios(iflag=0x{self.iflag:04x}, oflag=0x{self.oflag:04x}, "
            f"cflag=0x{self.cflag:04x}, lflag=0x{self.lflag:04x}, "
            f"ispeed={self.ispeed}, ospeed={self.ospeed})"
        )


@dataclass
class TtyDriver:
    """TTY driver."""
    name: str
    type: int
    subtype: int
    major: int = 0
    minor_start: int = 0
    num: int = 1
    flags: int = 0
    ops: Optional[TtyOps] = None
    is_registered: bool = False
    _ttys: list = field(default_factory=list)
    _init_termios: Optional[Ktermios] = None

    def __repr__(self) -> str:
        t = {TTY_DRIVER_TYPE_SYSTEM: "SYSTEM", TTY_DRIVER_TYPE_CONSOLE: "CONSOLE",
             TTY_DRIVER_TYPE_SERIAL: "SERIAL", TTY_DRIVER_TYPE_PTY: "PTY"}.get(self.type, f"0x{self.type:x}")
        return (
            f"TtyDriver(name={self.name!r}, type={t}, subtype={self.subtype}, "
            f"major={self.major}, num={self.num}, registered={self.is_registered})"
        )


@dataclass
class TtyPort:
    """TTY port."""
    name: str
    uart_name: str = ""
    uart: Optional[UartPort] = None
    ops: Optional[TtyOps] = None
    console: bool = False
    small_device: bool = False
    _count: int = 0
    _console_data: object = None

    def __repr__(self) -> str:
        return (
            f"TtyPort(name={self.name!r}, uart={self.uart_name!r}, "
            f"console={self.console}, count={self._count})"
        )


@dataclass
class UartPort:
    """UART port."""
    name: str
    iotype: int = UPIO_PORT
    mapbase: int = 0
    membase: int = 0
    irq: int = -1
    uartclk: int = 0
    fifosize: int = 0
    x_char: int = 0
    ignore_status_mask: int = 0
    status: int = 0
    type: int = PORT_UNKNOWN
    line: int = 0
    has_sysrq: bool = False
    quirks: int = 0
    _ops: Optional[UartOps] = None
    _state: Optional[UartState] = None
    _is_open: bool = False
    _is_suspended: bool = False
    _rx_buf: bytearray = field(default_factory=bytearray)
    _tx_buf: bytearray = field(default_factory=bytearray)
    _mctrl: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __repr__(self) -> str:
        io = {UPIO_PORT: "PORT", UPIO_MEM: "MEM", UPIO_AU: "AU",
              UPIO_TSI: "TSI", UPIO_MEM32: "MEM32"}.get(self.iotype, str(self.iotype))
        pt = {PORT_UNKNOWN: "UNKNOWN", PORT_8250: "8250",
              PORT_16550: "16550", PORT_ST16C680: "ST16C680"}.get(self.type, str(self.type))
        return (
            f"UartPort(name={self.name!r}, type={pt}, iotype={io}, "
            f"irq={self.irq}, fifosize={self.fifosize}, open={self._is_open})"
        )


@dataclass
class UartOps:
    """UART operations."""
    startup: Optional[Callable] = None
    shutdown: Optional[Callable] = None
    throttle: Optional[Callable] = None
    unthrottle: Optional[Callable] = None
    set_termios: Optional[Callable] = None
    set_mctrl: Optional[Callable] = None
    get_mctrl: Optional[Callable] = None
    stop_rx: Optional[Callable] = None
    enable_ms: Optional[Callable] = None
    wake_up_receive: Optional[Callable] = None


@dataclass
class UartState:
    """UART state."""
    port_name: str
    baud_rate: int = 115200
    is_closing: bool = False


@dataclass
class UartInfo:
    """UART type information."""
    name: str = ""
    type: int = 0
    fcr: int = 0
    flags: int = 0


@dataclass
class UartQuirks:
    """UART quirks."""
    name: str = ""
    flags: int = 0
    start_up: Optional[Callable] = None
    check_type: Optional[Callable] = None
    verify_type: Optional[Callable] = None
    reset: Optional[Callable] = None
    enable_ms: Optional[Callable] = None


# ---------------------------------------------------------------------------
# Global Registries
# ---------------------------------------------------------------------------

_tty_drivers: dict[str, TtyDriver] = {}
_uart_ports: dict[str, UartPort] = {}
_uart_info: dict[int, UartInfo] = {}
_uart_quirks: dict[str, UartQuirks] = {}
_tty_port_map: dict[str, TtyPort] = {}

# ---------------------------------------------------------------------------
# TTY Driver API
# ---------------------------------------------------------------------------

def tty_register_driver(driver_name: str) -> TtyDriver:
    """Register TTY driver -- like tty_register_driver()."""
    if driver_name in _tty_drivers:
        raise ValueError(f"TTY driver {driver_name!r} already registered")
    driver = TtyDriver(name=driver_name)
    driver.is_registered = True
    _tty_drivers[driver_name] = driver
    return driver


def tty_unregister_driver(driver_name: str) -> None:
    """Unregister TTY driver."""
    if driver_name not in _tty_drivers:
        raise KeyError(f"TTY driver {driver_name!r} not found")
    _tty_drivers[driver_name].is_registered = False
    del _tty_drivers[driver_name]


def tty_std_termios() -> Ktermios:
    """Get standard terminal settings (B9600, CS8, CREAD|CLOCAL)."""
    return Ktermios(
        cflag=CREAD | CLOCAL | CS8,
        ispeed=9600,
        ospeed=9600,
    )


def tty_register_tty(tty_driver_name: str, index: int = 0) -> TtyPort:
    """Register TTY device."""
    if tty_driver_name not in _tty_drivers:
        raise KeyError(f"TTY driver {tty_driver_name!r} not found")
    drv = _tty_drivers[tty_driver_name]
    if index >= drv.num:
        raise IndexError(f"TTY index {index} out of range for driver with {drv.num} ttys")
    port_name = f"{tty_driver_name}S{index}"
    termios = drv._init_termios or tty_std_termios()
    port = TtyPort(
        name=port_name,
        uart_name=port_name,
        ops=drv.ops,
    )
    _tty_port_map[port_name] = port
    if len(drv._ttys) <= index:
        drv._ttys.extend([None] * (index - len(drv._ttys) + 1))
    drv._ttys[index] = port
    return port


def tty_unregister_tty(tty_driver_name: str, index: int = 0) -> None:
    """Unregister TTY device."""
    port_name = f"{tty_driver_name}S{index}"
    if port_name not in _tty_port_map:
        raise KeyError(f"TTY device {port_name!r} not found")
    del _tty_port_map[port_name]
    if tty_driver_name in _tty_drivers:
        drv = _tty_drivers[tty_driver_name]
        if index < len(drv._ttys):
            drv._ttys[index] = None


def tty_open(tty_driver_name: str, index: int = 0) -> TtyPort:
    """Open TTY device."""
    port_name = f"{tty_driver_name}S{index}"
    if port_name not in _tty_port_map:
        raise KeyError(f"TTY device {port_name!r} not found")
    port = _tty_port_map[port_name]
    port._count += 1
    if port.ops and port.ops.open:
        port.ops.open(port)
    return port


def tty_close(tty_driver_name: str, index: int = 0) -> None:
    """Close TTY device."""
    port_name = f"{tty_driver_name}S{index}"
    if port_name not in _tty_port_map:
        raise KeyError(f"TTY device {port_name!r} not found")
    port = _tty_port_map[port_name]
    if port._count > 0:
        port._count -= 1
    if port._count == 0 and port.ops and port.ops.close:
        port.ops.close(port)


def tty_write(tty_driver_name: str, data: bytes, index: int = 0) -> int:
    """Write to TTY. Returns number of bytes written."""
    port_name = f"{tty_driver_name}S{index}"
    if port_name not in _tty_port_map:
        raise KeyError(f"TTY device {port_name!r} not found")
    port = _tty_port_map[port_name]
    if port.ops and port.ops.write:
        return port.ops.write(port, data)
    if port.uart:
        return uart_write(port.uart_name, data)
    return len(data)


def tty_read(tty_driver_name: str, count: int, index: int = 0) -> bytes:
    """Read from TTY."""
    port_name = f"{tty_driver_name}S{index}"
    if port_name not in _tty_port_map:
        raise KeyError(f"TTY device {port_name!r} not found")
    port = _tty_port_map[port_name]
    if port.uart:
        return uart_read(port.uart_name, count)
    return b""


def tty_ioctl(tty_driver_name: str, cmd: int, arg: Any, index: int = 0) -> Any:
    """ioctl on TTY."""
    port_name = f"{tty_driver_name}S{index}"
    if port_name not in _tty_port_map:
        raise KeyError(f"TTY device {port_name!r} not found")
    port = _tty_port_map[port_name]
    if port.ops and port.ops.ioctl:
        return port.ops.ioctl(port, cmd, arg)
    return 0


def tty_set_termios(tty_driver_name: str, termios: Ktermios, index: int = 0) -> None:
    """Set terminal settings."""
    port_name = f"{tty_driver_name}S{index}"
    if port_name not in _tty_port_map:
        raise KeyError(f"TTY device {port_name!r} not found")
    port = _tty_port_map[port_name]
    if port.ops and port.ops.set_termios:
        port.ops.set_termios(port, termios)
    if port.uart and port.uart._ops and port.uart._ops.set_termios:
        port.uart._ops.set_termios(port.uart, termios)


def tty_get_termios(tty_driver_name: str, index: int = 0) -> Ktermios:
    """Get terminal settings."""
    port_name = f"{tty_driver_name}S{index}"
    if port_name not in _tty_port_map:
        raise KeyError(f"TTY device {port_name!r} not found")
    port = _tty_port_map[port_name]
    if port.uart and port.uart._state:
        baud = port.uart._state.baud_rate
        return Ktermios(
            cflag=CREAD | CLOCAL | CS8,
            ispeed=baud,
            ospeed=baud,
        )
    return tty_std_termios()


def tty_hangup(tty_driver_name: str, index: int = 0) -> None:
    """Hang up TTY."""
    port_name = f"{tty_driver_name}S{index}"
    if port_name not in _tty_port_map:
        raise KeyError(f"TTY device {port_name!r} not found")
    port = _tty_port_map[port_name]
    if port.ops and port.ops.hangup:
        port.ops.hangup(port)
    if port.uart:
        uart_close(port.uart_name)


def tty_wakeup(tty_driver_name: str, index: int = 0) -> None:
    """Wake up TTY."""
    port_name = f"{tty_driver_name}S{index}"
    if port_name not in _tty_port_map:
        raise KeyError(f"TTY device {port_name!r} not found")
    port = _tty_port_map[port_name]
    if port.uart and port.uart._ops and port.uart._ops.wake_up_receive:
        port.uart._ops.wake_up_receive(port.uart)


# ---------------------------------------------------------------------------
# UART Port API
# ---------------------------------------------------------------------------

def uart_register_port(port_name: str, type: int = PORT_8250,
                       iotype: int = UPIO_PORT, irq: int = -1,
                       fifosize: int = 16) -> UartPort:
    """Register UART port."""
    if port_name in _uart_ports:
        raise ValueError(f"UART port {port_name!r} already registered")
    state = UartState(port_name=port_name)
    port = UartPort(
        name=port_name,
        type=type,
        iotype=iotype,
        irq=irq,
        fifosize=fifosize,
        _state=state,
    )
    _uart_ports[port_name] = port
    return port


def uart_unregister_port(port_name: str) -> None:
    """Unregister UART port."""
    if port_name not in _uart_ports:
        raise KeyError(f"UART port {port_name!r} not found")
    del _uart_ports[port_name]
    remove = [k for k, v in _tty_port_map.items() if v.uart_name == port_name]
    for k in remove:
        del _tty_port_map[k]


def uart_add_one_port(driver_name: str, port_name: str) -> TtyPort:
    """Add port to UART driver (creates TtyPort bound to UART)."""
    if driver_name not in _tty_drivers:
        raise KeyError(f"TTY driver {driver_name!r} not found")
    if port_name not in _uart_ports:
        raise KeyError(f"UART port {port_name!r} not found")
    drv = _tty_drivers[driver_name]
    port = TtyPort(
        name=f"{driver_name}-{port_name}",
        uart_name=port_name,
        uart=_uart_ports[port_name],
        ops=drv.ops,
    )
    _tty_port_map[port.name] = port
    return port


def uart_remove_one_port(driver_name: str, port_name: str) -> None:
    """Remove port from UART driver."""
    composite = f"{driver_name}-{port_name}"
    if composite in _tty_port_map:
        del _tty_port_map[composite]


# ---------------------------------------------------------------------------
# UART Operations
# ---------------------------------------------------------------------------

def uart_open(port_name: str) -> UartPort:
    """Open UART port."""
    if port_name not in _uart_ports:
        raise KeyError(f"UART port {port_name!r} not found")
    port = _uart_ports[port_name]
    with port._lock:
        if port._is_open:
            return port
        if port._ops and port._ops.startup:
            port._ops.startup(port)
        port._is_open = True
    return port


def uart_close(port_name: str) -> None:
    """Close UART port."""
    if port_name not in _uart_ports:
        raise KeyError(f"UART port {port_name!r} not found")
    port = _uart_ports[port_name]
    with port._lock:
        if not port._is_open:
            return
        if port._ops and port._ops.shutdown:
            port._ops.shutdown(port)
        port._is_open = False
        if port._state:
            port._state.is_closing = True


def uart_write(port_name: str, data: bytes) -> int:
    """Write to UART port. Returns bytes written."""
    if port_name not in _uart_ports:
        raise KeyError(f"UART port {port_name!r} not found")
    port = _uart_ports[port_name]
    if not port._is_open:
        raise RuntimeError(f"UART port {port_name!r} is not open")
    with port._lock:
        written = 0
        for byte in data:
            if port._ops and port._ops.set_mctrl:
                port._mctrl |= TIOCM_DTR | TIOCM_RTS
                port._ops.set_mctrl(port, port._mctrl)
            port._tx_buf.append(byte & 0xFF)
            written += 1
        return written


def uart_read(port_name: str, count: int) -> bytes:
    """Read from UART port."""
    if port_name not in _uart_ports:
        raise KeyError(f"UART port {port_name!r} not found")
    port = _uart_ports[port_name]
    with port._lock:
        n = min(count, len(port._rx_buf))
        data = bytes(port._rx_buf[:n])
        del port._rx_buf[:n]
        return data


def uart_set_mctrl(port_name: str, mctrl: int) -> None:
    """Set modem control lines."""
    if port_name not in _uart_ports:
        raise KeyError(f"UART port {port_name!r} not found")
    port = _uart_ports[port_name]
    with port._lock:
        port._mctrl = mctrl
        if port._ops and port._ops.set_mctrl:
            port._ops.set_mctrl(port, mctrl)


def uart_get_mctrl(port_name: str) -> int:
    """Get modem control lines."""
    if port_name not in _uart_ports:
        raise KeyError(f"UART port {port_name!r} not found")
    port = _uart_ports[port_name]
    if port._ops and port._ops.get_mctrl:
        return port._ops.get_mctrl(port)
    return port._mctrl


def uart_set_baud(port_name: str, baud: int) -> None:
    """Set baud rate."""
    if port_name not in _uart_ports:
        raise KeyError(f"UART port {port_name!r} not found")
    port = _uart_ports[port_name]
    with port._lock:
        if port._state:
            port._state.baud_rate = baud
        if port._ops and port._ops.set_termios:
            termios = Ktermios(cflag=CREAD | CLOCAL | CS8, ispeed=baud, ospeed=baud)
            port._ops.set_termios(port, termios)


def uart_set_line_control(port_name: str, bits: int = CS8,
                          parity: int = 0, stop_bits: int = 0) -> None:
    """Set line control (word length, parity, stop bits)."""
    if port_name not in _uart_ports:
        raise KeyError(f"UART port {port_name!r} not found")
    port = _uart_ports[port_name]
    with port._lock:
        cflag = CREAD | CLOCAL
        cflag |= bits & 0x30
        if parity:
            cflag |= PARENB
        if stop_bits:
            cflag |= CSTOPB
        if port._ops and port._ops.set_termios:
            baud = port._state.baud_rate if port._state else 9600
            termios = Ktermios(cflag=cflag, ispeed=baud, ospeed=baud)
            port._ops.set_termios(port, termios)


def uart_enable_ms(port_name: str) -> None:
    """Enable modem status interrupts."""
    if port_name not in _uart_ports:
        raise KeyError(f"UART port {port_name!r} not found")
    port = _uart_ports[port_name]
    if port._ops and port._ops.enable_ms:
        port._ops.enable_ms(port)


def uart_throttle(port_name: str) -> None:
    """Throttle port."""
    if port_name not in _uart_ports:
        raise KeyError(f"UART port {port_name!r} not found")
    port = _uart_ports[port_name]
    if port._ops and port._ops.throttle:
        port._ops.throttle(port)


def uart_unthrottle(port_name: str) -> None:
    """Unthrottle port."""
    if port_name not in _uart_ports:
        raise KeyError(f"UART port {port_name!r} not found")
    port = _uart_ports[port_name]
    if port._ops and port._ops.unthrottle:
        port._ops.unthrottle(port)


# ---------------------------------------------------------------------------
# Modem lines
# ---------------------------------------------------------------------------

def uart_get_tx(port_name: str) -> int:
    """Get TX state."""
    if port_name not in _uart_ports:
        raise KeyError(f"UART port {port_name!r} not found")
    return len(_uart_ports[port_name]._tx_buf)


def uart_set_tx(port_name: str, state: int) -> None:
    """Set TX state (0=empty, 1=active)."""
    if port_name not in _uart_ports:
        raise KeyError(f"UART port {port_name!r} not found")
    port = _uart_ports[port_name]
    if state == 0:
        port._tx_buf.clear()


# ---------------------------------------------------------------------------
# FIFO
# ---------------------------------------------------------------------------

def uart_tx_chars(port_name: str, count: int) -> int:
    """Transmit chars from FIFO. Returns chars transmitted."""
    if port_name not in _uart_ports:
        raise KeyError(f"UART port {port_name!r} not found")
    port = _uart_ports[port_name]
    with port._lock:
        n = min(count, len(port._tx_buf))
        port._tx_buf = port._tx_buf[n:]
        return n


def uart_rx_chars(port_name: str, count: int) -> int:
    """Receive chars to FIFO. Returns chars buffered."""
    if port_name not in _uart_ports:
        raise KeyError(f"UART port {port_name!r} not found")
    port = _uart_ports[port_name]
    with port._lock:
        space = port.fifosize - len(port._rx_buf)
        n = min(count, space)
        for _ in range(n):
            port._rx_buf.append(0)
        return n


# ---------------------------------------------------------------------------
# Info
# ---------------------------------------------------------------------------

def uart_get_type(port_name: str) -> str:
    """Get UART type name."""
    if port_name not in _uart_ports:
        raise KeyError(f"UART port {port_name!r} not found")
    port = _uart_ports[port_name]
    return {PORT_UNKNOWN: "UNKNOWN", PORT_8250: "8250",
            PORT_16550: "16550", PORT_ST16C680: "ST16C680"}.get(port.type, "UNKNOWN")


def uart_get_fifosize(port_name: str) -> int:
    """Get FIFO size."""
    if port_name not in _uart_ports:
        raise KeyError(f"UART port {port_name!r} not found")
    return _uart_ports[port_name].fifosize


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------

def tty_list_drivers() -> list[str]:
    """List registered TTY drivers."""
    return sorted(_tty_drivers.keys())


def tty_list_ports() -> list[str]:
    """List UART ports."""
    return sorted(_uart_ports.keys())


# ---------------------------------------------------------------------------
# Built-in Simulated Hardware
# ---------------------------------------------------------------------------

class SimUart8250:
    """Simulated 8250 UART."""

    def __init__(self, port_name: str = "uart0", irq: int = -1) -> None:
        self.port_name = port_name
        self.port = uart_register_port(
            port_name, type=PORT_8250, iotype=UPIO_PORT,
            irq=irq, fifosize=1,
        )
        self.port.uartclk = 1843200
        self._setup_ops()

    def _setup_ops(self) -> None:
        ops = UartOps(
            startup=_8250_startup,
            shutdown=_8250_shutdown,
            set_termios=_8250_set_termios,
            set_mctrl=_8250_set_mctrl,
            get_mctrl=_8250_get_mctrl,
        )
        self.port._ops = ops

    def __repr__(self) -> str:
        return f"SimUart8250(port={self.port_name!r}, irq={self.port.irq})"


class SimUart16550:
    """Simulated 16550 UART with FIFO."""

    def __init__(self, port_name: str = "uart1", irq: int = -1,
                 fifo_size: int = 16) -> None:
        self.port_name = port_name
        self.port = uart_register_port(
            port_name, type=PORT_16550, iotype=UPIO_PORT,
            irq=irq, fifosize=fifo_size,
        )
        self.port.uartclk = 1843200
        self._fifo_size = fifo_size
        self._setup_ops()

    def _setup_ops(self) -> None:
        ops = UartOps(
            startup=_16550_startup,
            shutdown=_16550_shutdown,
            set_termios=_16550_set_termios,
            set_mctrl=_8250_set_mctrl,
            get_mctrl=_8250_get_mctrl,
            throttle=_16550_throttle,
            unthrottle=_16550_unthrottle,
        )
        self.port._ops = ops

    def __repr__(self) -> str:
        return (
            f"SimUart16550(port={self.port_name!r}, irq={self.port.irq}, "
            f"fifo={self._fifo_size})"
        )


class SimUartConsole:
    """Simulated serial console."""

    def __init__(self, name: str = "console", port_name: str = "uart0") -> None:
        self.name = name
        if port_name not in _uart_ports:
            raise KeyError(f"UART port {port_name!r} not found")
        self.port_name = port_name
        port = _uart_ports[port_name]
        self.tty_port = TtyPort(
            name=f"console-{name}",
            uart_name=port_name,
            uart=port,
            console=True,
        )
        _tty_port_map[self.tty_port.name] = self.tty_port

    def write_console(self, data: bytes) -> int:
        """Write to serial console."""
        return uart_write(self.port_name, data)

    def read_console(self, count: int) -> bytes:
        """Read from serial console."""
        return uart_read(self.port_name, count)

    def __repr__(self) -> str:
        return f"SimUartConsole(name={self.name!r}, port={self.port_name!r})"


class SimPty:
    """Simulated PTY (pseudo-terminal)."""

    def __init__(self, name: str = "pty0") -> None:
        self.name = name
        self.master_buf = bytearray()
        self.slave_buf = bytearray()
        self.master_open = False
        self.slave_open = False
        self._lock = threading.Lock()

        master_port = TtyPort(
            name=f"{name}:master",
            uart_name=f"{name}:master",
            console=False,
            small_device=False,
        )
        slave_port = TtyPort(
            name=f"{name}:slave",
            uart_name=f"{name}:slave",
            console=False,
            small_device=False,
        )
        _tty_port_map[master_port.name] = master_port
        _tty_port_map[slave_port.name] = slave_port
        self.master_port_name = master_port.name
        self.slave_port_name = slave_port.name

    def open_master(self) -> None:
        self.master_open = True

    def close_master(self) -> None:
        self.master_open = False

    def open_slave(self) -> None:
        self.slave_open = True

    def close_slave(self) -> None:
        self.slave_open = False

    def master_write(self, data: bytes) -> int:
        """Master writes -> appears in slave read."""
        with self._lock:
            self.slave_buf.extend(data)
            return len(data)

    def slave_read(self, count: int) -> bytes:
        """Slave reads from master."""
        with self._lock:
            n = min(count, len(self.slave_buf))
            out = bytes(self.slave_buf[:n])
            del self.slave_buf[:n]
            return out

    def slave_write(self, data: bytes) -> int:
        """Slave writes -> appears in master read."""
        with self._lock:
            self.master_buf.extend(data)
            return len(data)

    def master_read(self, count: int) -> bytes:
        """Master reads from slave."""
        with self._lock:
            n = min(count, len(self.master_buf))
            out = bytes(self.master_buf[:n])
            del self.master_buf[:n]
            return out

    def __repr__(self) -> str:
        return (
            f"SimPty(name={self.name!r}, master={self.master_port_name!r}, "
            f"slave={self.slave_port_name!r})"
        )


# ---------------------------------------------------------------------------
# 8250 internal callbacks
# ---------------------------------------------------------------------------

def _8250_startup(port: UartPort) -> None:
    port._mctrl = TIOCM_DTR | TIOCM_RTS


def _8250_shutdown(port: UartPort) -> None:
    port._mctrl = 0
    port._tx_buf.clear()
    port._rx_buf.clear()


def _8250_set_termios(port: UartPort, termios: Ktermios) -> None:
    if port._state:
        port._state.baud_rate = termios.ospeed


def _8250_set_mctrl(port: UartPort, mctrl: int) -> None:
    port._mctrl = mctrl


def _8250_get_mctrl(port: UartPort) -> int:
    return port._mctrl | TIOCM_CTS | TIOCM_DSR | TIOCM_CD


# ---------------------------------------------------------------------------
# 16550 internal callbacks
# ---------------------------------------------------------------------------

def _16550_startup(port: UartPort) -> None:
    _8250_startup(port)


def _16550_shutdown(port: UartPort) -> None:
    _8250_shutdown(port)


def _16550_set_termios(port: UartPort, termios: Ktermios) -> None:
    _8250_set_termios(port, termios)


def _16550_throttle(port: UartPort) -> None:
    port._mctrl &= ~TIOCM_RTS


def _16550_unthrottle(port: UartPort) -> None:
    port._mctrl |= TIOCM_RTS


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def demo() -> None:
    print("=" * 72)
    print("UmerOS TTY/Serial Framework Demo")
    print("=" * 72)

    # --- Create TTY drivers ---
    print("\n--- TTY Drivers ---")
    serial_ops = TtyOps(
        open=lambda p: print(f"  [ops] open {p.name}"),
        close=lambda p: print(f"  [ops] close {p.name}"),
        write=lambda p, d: (print(f"  [ops] write {len(d)} bytes to {p.name}"), len(d))[1],
    )
    serial_driver = TtyDriver(
        name="ttyS",
        type=TTY_DRIVER_TYPE_SERIAL,
        subtype=TTY_TYPE_DRIVER,
        major=4,
        minor_start=64,
        num=4,
        ops=serial_ops,
    )
    _tty_drivers["ttyS"] = serial_driver
    serial_driver.is_registered = True

    system_driver = TtyDriver(
        name="tty",
        type=TTY_DRIVER_TYPE_SYSTEM,
        subtype=TTY_TYPE_LDISC,
        major=5,
        num=1,
    )
    _tty_drivers["tty"] = system_driver
    system_driver.is_registered = True

    for name in tty_list_drivers():
        print(f"  {_tty_drivers[name]}")

    # --- Create UART ports ---
    print("\n--- UART Ports ---")
    uart0 = SimUart8250(port_name="uart0", irq=4)
    uart1 = SimUart16550(port_name="uart1", irq=3, fifo_size=16)
    print(f"  {uart0}")
    print(f"  {uart1}")

    # --- Serial console ---
    print("\n--- Serial Console ---")
    console = SimUartConsole(name="ttyS0", port_name="uart0")
    print(f"  {console}")

    # --- PTY ---
    print("\n--- PTY ---")
    pty = SimPty(name="pty0")
    print(f"  {pty}")

    # --- Baud rates and line control ---
    print("\n--- Baud Rate & Line Control ---")
    uart_set_baud("uart0", 115200)
    uart_set_baud("uart1", 921600)
    print(f"  uart0 baud: {uart0.port._state.baud_rate}")
    print(f"  uart1 baud: {uart1.port._state.baud_rate}")

    uart_set_line_control("uart0", bits=CS8, parity=0, stop_bits=0)
    print(f"  uart0 line control set (CS8, no parity, 1 stop)")

    # --- Open/close TTY ---
    print("\n--- Open/Close TTY ---")
    port = tty_register_tty("ttyS", index=0)
    print(f"  Registered: {port}")
    tty_open("ttyS", index=0)
    print(f"  Opened: count={port._count}")
    tty_open("ttyS", index=0)
    print(f"  Opened again: count={port._count}")
    tty_close("ttyS", index=0)
    print(f"  Closed once: count={port._count}")
    tty_close("ttyS", index=0)
    print(f"  Closed twice: count={port._count}")

    # --- Write/read data through TTY ---
    print("\n--- Write/Read Data ---")
    tty_open("ttyS", index=0)
    uart_open("uart0")
    msg = b"Hello UmerOS!"
    written = tty_write("ttyS", msg, index=0)
    print(f"  Wrote {written} bytes: {msg!r}")
    print(f"  TX buffer: {bytes(uart0.port._tx_buf)!r}")

    uart1.port._rx_buf.extend(b"ACK")
    rx = tty_read("ttyS", 3, index=0)
    print(f"  Read from ttyS: {rx!r}")

    # --- Modem control lines ---
    print("\n--- Modem Control Lines ---")
    uart_set_mctrl("uart0", TIOCM_DTR | TIOCM_RTS)
    mctrl = uart_get_mctrl("uart0")
    lines = []
    if mctrl & TIOCM_DTR: lines.append("DTR")
    if mctrl & TIOCM_RTS: lines.append("RTS")
    if mctrl & TIOCM_CTS: lines.append("CTS")
    if mctrl & TIOCM_DSR: lines.append("DSR")
    if mctrl & TIOCM_CD:  lines.append("CD")
    print(f"  uart0 mctrl: {' | '.join(lines)} (0x{mctrl:04x})")

    # --- Terminal settings ---
    print("\n--- Terminal Settings (Termios) ---")
    termios = tty_get_termios("ttyS", index=0)
    print(f"  {termios}")
    baud_termios = Ktermios(cflag=CREAD | CLOCAL | CS8, ispeed=115200, ospeed=115200)
    tty_set_termios("ttyS", baud_termios, index=0)
    termios2 = tty_get_termios("ttyS", index=0)
    print(f"  After set: {termios2}")

    # --- FIFO operations ---
    print("\n--- FIFO Operations ---")
    uart_rx_chars("uart0", 5)
    print(f"  RX FIFO depth after rx_chars(5): {len(uart0.port._rx_buf)}")
    uart_tx_chars("uart0", 2)
    print(f"  TX FIFO depth after tx_chars(2): {len(uart0.port._tx_buf)}")

    # --- PTY read/write ---
    print("\n--- PTY Data Transfer ---")
    pty.open_master()
    pty.open_slave()
    pty.master_write(b"master->slave")
    slave_rx = pty.slave_read(20)
    print(f"  Slave read: {slave_rx!r}")
    pty.slave_write(b"slave->master")
    master_rx = pty.master_read(20)
    print(f"  Master read: {master_rx!r}")

    # --- Port listing ---
    print("\n--- Port & Driver Listing ---")
    print(f"  Drivers: {tty_list_drivers()}")
    print(f"  Ports:   {tty_list_ports()}")
    print(f"  UART type (uart0): {uart_get_type('uart0')}")
    print(f"  FIFO size (uart1): {uart_get_fifosize('uart1')}")

    # --- Close ---
    tty_close("ttyS", index=0)
    uart_close("uart0")
    print(f"  uart0 open: {uart0.port._is_open}")

    print("\n" + "=" * 72)
    print("Demo complete.")
    print("=" * 72)


if __name__ == "__main__":
    demo()
