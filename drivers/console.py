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
UmerOS Console Subsystem
========================
Kernel-like console management with serial, framebuffer,
and network consoles. Includes kernel log buffer and printk.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

# ── Console Flags ──────────────────────────────────────────────────────────────
# Bitmask flags for console devices (kernel/console.h)

CON_PRINTBUFFER: int = 0x0001  # Print output to kernel log buffer
CON_CONSDEV:     int = 0x0002  # Last preferred console
CON_ENABLED:     int = 0x0004  # Console is enabled
CON_BOOT:        int = 0x0008  # Boot-time console
CON_ANYTIME:     int = 0x0010  # Can be called at any time
CON_BRL:         int = 0x0020  # Braille device
CON_STUB:        int = 0x0040  # Stub/no-op console
CON_PRINTK:      int = 0x0100  # printk source console
CON_EXTENDED:    int = 0x0200  # Extended log format

# ── Log Levels (kernel/printk/printk.h) ───────────────────────────────────────

KERN_EMERG:   int = 0  # System is unusable
KERN_ALERT:   int = 1  # Action must be taken immediately
KERN_CRIT:    int = 2  # Critical conditions
KERN_ERR:     int = 3  # Error conditions
KERN_WARNING: int = 4  # Warning conditions
KERN_NOTICE:  int = 5  # Normal but significant
KERN_INFO:    int = 6  # Informational
KERN_DEBUG:   int = 7  # Debug-level messages

_LOG_LEVEL_NAMES: Dict[int, str] = {
    KERN_EMERG:   "EMERG",
    KERN_ALERT:   "ALERT",
    KERN_CRIT:    "CRIT",
    KERN_ERR:     "ERR",
    KERN_WARNING: "WARN",
    KERN_NOTICE:  "NOTICE",
    KERN_INFO:    "INFO",
    KERN_DEBUG:   "DEBUG",
}

# ── Global Registries ─────────────────────────────────────────────────────────

CONSOLE_REGISTRY: Dict[str, Console] = {}
TTY_CONSOLE_REGISTRY: Dict[str, TtyConsole] = {}
LOG_BUFFER: Optional[LogBuffer] = None
_EARLY_CONSOLE: Optional[Console] = None
_LOCK: threading.Lock = threading.Lock()


# ── Core Dataclasses ───────────────────────────────────────────────────────────

@dataclass
class Console:
    """Kernel console device.

    Mirrors ``struct console`` — each registered console has a
    ``write`` callback, optional ``setup`` callback, and flag bitmask.
    """
    name: str
    index: int
    flags: int = CON_ENABLED
    write: Optional[Callable[["Console", str, int], None]] = field(default=None, repr=False)
    setup: Optional[Callable[["Console"], bool]] = field(default=None, repr=False)
    data: Dict[str, Any] = field(default_factory=dict)
    device: str = ""
    _is_boot_console: bool = field(default=False, repr=False)
    _is_registered: bool = field(default=False, repr=False)

    def emit(self, buf: str) -> None:
        """Write *buf* to this console if write callback is installed.

        The log buffer is NOT written here — callers (printk,
        console_write) are responsible for logging to avoid duplicates.
        """
        if self.write is not None:
            self.write(self, buf, len(buf))


@dataclass
class TtyConsole:
    """TTY-based console (serial port, USB adapter, etc.).

    Stores UART-style parameters matching the ``console=ttyS0,115200``
    kernel command-line syntax.
    """
    name: str
    index: int
    device: str
    baud: int = 115200
    parity: str = "none"
    stopbits: int = 1
    databits: int = 8
    flow_control: str = "none"
    _registered: bool = field(default=False, repr=False)


@dataclass
class LogBuffer:
    """Kernel log buffer (analogous to /dev/kmsg / dmesg).

    Fixed-size ring buffer with ``head`` and ``tail`` pointers.  Old
    entries are silently overwritten when the buffer is full.
    """
    entries: List[str] = field(default_factory=list)
    max_entries: int = 10000
    head: int = 0
    tail: int = 0

    def write(self, level: int, msg: str) -> None:
        """Append a level-prefixed message to the ring buffer."""
        prefix = _LOG_LEVEL_NAMES.get(level, f"L{level}")
        entry = f"[{prefix}] {msg}"
        if len(self.entries) < self.max_entries:
            self.entries.append(entry)
        else:
            self.entries[self.head] = entry
            self.head = (self.head + 1) % self.max_entries
        self.tail = (self.tail + 1) % self.max_entries

    def read(self, count: int = 0) -> str:
        """Return the last *count* entries (0 = all)."""
        if count <= 0:
            return "\n".join(self.entries)
        start = max(0, len(self.entries) - count)
        return "\n".join(self.entries[start:])

    def clear(self) -> None:
        """Clear the ring buffer."""
        self.entries.clear()
        self.head = 0
        self.tail = 0

    def __len__(self) -> int:
        return len(self.entries)


# ── Internal: ensure log buffer exists ────────────────────────────────────────

def _get_log_buffer() -> LogBuffer:
    """Lazy-initialise the global log buffer."""
    global LOG_BUFFER
    if LOG_BUFFER is None:
        LOG_BUFFER = LogBuffer()
    return LOG_BUFFER


# ── Console Registration API ───────────────────────────────────────────────────

def console_register(con: Console) -> None:
    """Register a console — like ``console_register()``.

    Calls ``con.setup(con)`` when a setup callback is present.
    Raises ``ValueError`` on duplicate (name, index) pair.
    """
    key = _console_key(con.name, con.index)
    with _LOCK:
        if key in CONSOLE_REGISTRY:
            raise ValueError(f"Console '{key}' is already registered")
        if con.setup is not None:
            try:
                if not con.setup(con):
                    raise RuntimeError(f"Console setup failed for '{key}'")
            except Exception as exc:
                raise RuntimeError(f"Console setup error for '{key}': {exc}") from exc
        con._is_registered = True
        CONSOLE_REGISTRY[key] = con
        if con.flags & CON_ENABLED:
            _get_log_buffer().write(KERN_INFO, f"console: registered '{con.name}' (index {con.index})")


def console_unregister(name: str, index: int = 0) -> None:
    """Unregister a console by *name* and *index*."""
    key = _console_key(name, index)
    with _LOCK:
        if key not in CONSOLE_REGISTRY:
            raise KeyError(f"Console '{key}' not found")
        con = CONSOLE_REGISTRY.pop(key)
        con._is_registered = False
        _get_log_buffer().write(KERN_INFO, f"console: unregistered '{name}' (index {index})")


def console_enable(name: str, index: int = 0) -> None:
    """Enable a registered console."""
    con = _find_console(name, index)
    con.flags |= CON_ENABLED
    _get_log_buffer().write(KERN_INFO, f"console: enabled '{name}' (index {index})")


def console_disable(name: str, index: int = 0) -> None:
    """Disable a registered console."""
    con = _find_console(name, index)
    con.flags &= ~CON_ENABLED
    _get_log_buffer().write(KERN_INFO, f"console: disabled '{name}' (index {index})")


def console_write(name: str, buf: str, index: int = 0) -> None:
    """Write *buf* to a console — like ``con->write(con, buf, count)``."""
    con = _find_console(name, index)
    con.emit(buf)


def console_setup(console_str: str) -> Console:
    """Parse a ``console=`` kernel parameter and return a Console.

    Accepted formats::

        console=ttyS0,115200
        console=ttyUSB0,9600n8
        console=netconsole,1@192.168.1.1/1234

    Returns a ``Console`` instance ready for ``console_register()``.
    """
    # Strip optional "console=" prefix from kernel cmdline
    raw = console_str.strip()
    if raw.startswith("console="):
        raw = raw[len("console="):]

    parts = raw.split(",")
    name = parts[0].strip()
    index = 0
    baud = 115200
    device = f"/dev/{name}"

    # Parse baud rate from second token
    if len(parts) >= 2:
        token = parts[1].strip()
        if token.isdigit():
            baud = int(token)
            index = 0
        else:
            # e.g. 115200n8 — strip trailing mode chars
            baud_str = "".join(c for c in token if c.isdigit())
            if baud_str:
                baud = int(baud_str)

    con = Console(name=name, index=index, flags=CON_ENABLED | CON_PRINTBUFFER)
    con.data["baud"] = baud
    con.device = device
    con.write = _default_console_write
    _get_log_buffer().write(KERN_INFO,
        f"console_setup: parsed '{console_str}' -> name={name} baud={baud}")
    return con


def console_select(name: str) -> None:
    """Select the preferred console (set CON_CONSDEV)."""
    with _LOCK:
        for key, con in CONSOLE_REGISTRY.items():
            if con.name == name:
                con.flags |= CON_CONSDEV
            else:
                con.flags &= ~CON_CONSDEV
    _get_log_buffer().write(KERN_INFO, f"console: preferred console set to '{name}'")


def console_get_by_name(name: str) -> Optional[Console]:
    """Return the first console matching *name*, or ``None``."""
    for con in CONSOLE_REGISTRY.values():
        if con.name == name:
            return con
    return None


def console_list() -> List[str]:
    """Return a list of registered console descriptions."""
    result = []
    for key, con in sorted(CONSOLE_REGISTRY.items()):
        flags_str = _flags_to_string(con.flags)
        result.append(f"  {con.name} (index={con.index}, flags={flags_str})")
    return result


# ── Log Buffer (dmesg) API ────────────────────────────────────────────────────

def logbuf_write(level: int, msg: str) -> None:
    """Write to the kernel log buffer."""
    _get_log_buffer().write(level, msg)


def logbuf_read(count: int = 0) -> str:
    """Read from the kernel log buffer (0 = all entries)."""
    return _get_log_buffer().read(count)


def logbuf_clear() -> None:
    """Clear the kernel log buffer."""
    _get_log_buffer().clear()


def dmesg() -> str:
    """Print all kernel messages — like the ``dmesg`` command."""
    return _get_log_buffer().read(0)


def dmesg_clear() -> None:
    """Clear the kernel ring buffer (dmesg -C)."""
    _get_log_buffer().clear()


def printk(level: int, fmt: str, *args: Any) -> str:
    """Kernel print function — like  ``printk()``.

    Supports %-style formatting.  Output is written to every enabled
    console and the log buffer.  Returns the formatted message.
    """
    if args:
        msg = fmt % args
    else:
        msg = fmt
    prefix = _LOG_LEVEL_NAMES.get(level, f"L{level}")
    formatted = f"<{level}>{msg}"

    # Write to all enabled consoles
    for con in list(CONSOLE_REGISTRY.values()):
        if con.flags & CON_ENABLED:
            con.emit(f"[{prefix}] {msg}")

    # Always write to log buffer
    _get_log_buffer().write(level, msg)

    # Also write to early console if active
    global _EARLY_CONSOLE
    if _EARLY_CONSOLE is not None and _EARLY_CONSOLE.flags & CON_ENABLED:
        _EARLY_CONSOLE.emit(f"[{prefix}] {msg}")

    return formatted


# ── Early Boot Console API ─────────────────────────────────────────────────────

def early_console_register(name: str, write_fn: Optional[Callable] = None) -> Console:
    """Register an early boot console.

    Early consoles are used before the full driver model is available
    (e.g., UART output during bootloader handoff).
    """
    global _EARLY_CONSOLE
    con = Console(
        name=name,
        index=0,
        flags=CON_ENABLED | CON_BOOT | CON_PRINTBUFFER,
        write=write_fn or _default_console_write,
    )
    con._is_boot_console = True
    _EARLY_CONSOLE = con
    _get_log_buffer().write(KERN_INFO, f"early_console: registered '{name}'")
    return con


def early_console_output(msg: str) -> None:
    """Output via the early boot console."""
    if _EARLY_CONSOLE is not None:
        _EARLY_CONSOLE.emit(msg)


def register_console_cmdline(console_str: str) -> Console:
    """Register a console via kernel command-line string.

    Parses ``console=ttyS0,115200`` and registers the resulting Console.
    """
    con = console_setup(console_str)
    console_register(con)
    return con


# ── TTY Console Helpers ────────────────────────────────────────────────────────

def tty_console_register(tty: TtyConsole) -> None:
    """Register a TTY console."""
    key = f"{tty.name}:{tty.device}"
    if key in TTY_CONSOLE_REGISTRY:
        raise ValueError(f"TTY console '{key}' already registered")
    tty._registered = True
    TTY_CONSOLE_REGISTRY[key] = tty
    _get_log_buffer().write(KERN_INFO,
        f"tty: registered '{tty.name}' on {tty.device} @ {tty.baud}")


def tty_console_unregister(name: str, device: str) -> None:
    """Unregister a TTY console."""
    key = f"{name}:{device}"
    if key not in TTY_CONSOLE_REGISTRY:
        raise KeyError(f"TTY console '{key}' not found")
    TTY_CONSOLE_REGISTRY[key]._registered = False
    del TTY_CONSOLE_REGISTRY[key]
    _get_log_buffer().write(KERN_INFO, f"tty: unregistered '{name}'")


# ── Built-in Console Implementations ───────────────────────────────────────────

class SerialConsole(Console):
    """Serial port console (UART).

    Wraps a ``TtyConsole`` and provides a ``write`` callback that
    formats output for a serial device.
    """

    def __init__(self, name: str = "ttyS", index: int = 0,
                 baud: int = 115200, device: str = "") -> None:
        tty = TtyConsole(
            name=name, index=index,
            device=device or f"/dev/{name}{index}",
            baud=baud,
        )
        tty_console_register(tty)
        super().__init__(
            name=name,
            index=index,
            flags=CON_ENABLED | CON_PRINTBUFFER | CON_BOOT,
            write=self._serial_write,
            setup=self._serial_setup,
            device=tty.device,
        )
        self.tty = tty
        self._lines: List[str] = []

    def _serial_setup(self, con: Console) -> bool:
        return True

    def _serial_write(self, con: Console, buf: str, count: int) -> None:
        self._lines.append(buf)


class FramebufferConsole(Console):
    """Framebuffer console (fbcon).

    Simulates a text-mode framebuffer device that renders output
    to a virtual framebuffer.
    """

    def __init__(self, name: str = "fbcon", index: int = 0,
                 width: int = 80, height: int = 25) -> None:
        super().__init__(
            name=name,
            index=index,
            flags=CON_ENABLED | CON_PRINTBUFFER,
            write=self._fb_write,
            setup=self._fb_setup,
        )
        self.width = width
        self.height = height
        self._framebuffer: List[str] = [""] * height
        self._cursor_x: int = 0
        self._cursor_y: int = 0

    def _fb_setup(self, con: Console) -> bool:
        return True

    def _fb_write(self, con: Console, buf: str, count: int) -> None:
        for ch in buf:
            if ch == "\n":
                self._cursor_x = 0
                self._cursor_y = (self._cursor_y + 1) % self.height
                if self._cursor_y == 0:
                    self._framebuffer = [""] * self.height
            elif ch == "\r":
                self._cursor_x = 0
            else:
                if self._cursor_y < self.height:
                    row = list(self._framebuffer[self._cursor_y])
                    if self._cursor_x < self.width:
                        while len(row) <= self._cursor_x:
                            row.append(" ")
                        row[self._cursor_x] = ch
                        self._framebuffer[self._cursor_y] = "".join(row)
                    self._cursor_x = (self._cursor_x + 1) % self.width

    def dump_screen(self) -> str:
        """Return the current framebuffer contents."""
        return "\n".join(self._framebuffer)


class NetConsole(Console):
    """Network console (netconsole).

    Simulates sending console output to a remote host over UDP.
    """

    def __init__(self, name: str = "netconsole", index: int = 0,
                 remote_ip: str = "192.168.1.1", remote_port: int = 6666,
                 local_port: int = 6666) -> None:
        super().__init__(
            name=name,
            index=index,
            flags=CON_ENABLED | CON_PRINTBUFFER | CON_ANYTIME,
            write=self._net_write,
            setup=self._net_setup,
        )
        self.remote_ip = remote_ip
        self.remote_port = remote_port
        self.local_port = local_port
        self._packets: List[Dict[str, Any]] = []

    def _net_setup(self, con: Console) -> bool:
        return True

    def _net_write(self, con: Console, buf: str, count: int) -> None:
        self._packets.append({
            "src_port": self.local_port,
            "dst_ip": self.remote_ip,
            "dst_port": self.remote_port,
            "payload": buf,
            "length": count,
            "timestamp": time.time(),
        })


class DummyConsole(Console):
    """Dummy/null console — discards all output."""

    def __init__(self, name: str = "nullcon", index: int = 0) -> None:
        super().__init__(
            name=name,
            index=index,
            flags=CON_ENABLED | CON_STUB | CON_PRINTBUFFER,
            write=self._dummy_write,
        )

    def _dummy_write(self, con: Console, buf: str, count: int) -> None:
        pass  # intentionally discarded


# ── Internal Helpers ───────────────────────────────────────────────────────────

def _console_key(name: str, index: int) -> str:
    return f"{name}:{index}"


def _find_console(name: str, index: int) -> Console:
    key = _console_key(name, index)
    if key not in CONSOLE_REGISTRY:
        raise KeyError(f"Console '{key}' not registered")
    return CONSOLE_REGISTRY[key]


def _default_console_write(con: Console, buf: str, count: int) -> None:
    """Fallback write that prints to stdout."""
    print(f"[{con.name}] {buf}", end="", flush=True)


def _flags_to_string(flags: int) -> str:
    parts = []
    mapping = [
        (CON_PRINTBUFFER, "PB"),
        (CON_CONSDEV,     "CD"),
        (CON_ENABLED,     "EN"),
        (CON_BOOT,        "BT"),
        (CON_ANYTIME,     "AT"),
        (CON_BRL,         "BRL"),
        (CON_STUB,        "STB"),
        (CON_PRINTK,      "PK"),
        (CON_EXTENDED,    "EXT"),
    ]
    for flag, label in mapping:
        if flags & flag:
            parts.append(label)
    return "|".join(parts) if parts else "0"


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 72)
    print("  UmerOS Console Subsystem — Demo")
    print("=" * 72)

    # ── 1. Early boot console ──────────────────────────────────────────────
    print("\n--- Early Boot Console ---")
    early = early_console_register("early_uart")
    early_console_output("[BOOT] UmerOS booting...\n")
    early_console_output("[BOOT] Memory: 256 MB OK\n")
    early_console_output("[BOOT] CPU: 4 cores detected\n")
    early_console_output("[BOOT] Early console active\n")
    print(f"  Early console '{early.name}' registered, "
          f"boot={early._is_boot_console}")

    # ── 2. Serial console ──────────────────────────────────────────────────
    print("\n--- Serial Console (UART) ---")
    serial = SerialConsole(name="ttyS", index=0, baud=115200)
    console_register(serial)
    console_write("ttyS", "[UART] Serial port ready at 115200 baud\n")
    print(f"  Serial: {serial.device} @ {serial.tty.baud} baud")
    print(f"  Lines buffered: {len(serial._lines)}")

    # ── 3. Framebuffer console ─────────────────────────────────────────────
    print("\n--- Framebuffer Console (fbcon) ---")
    fb = FramebufferConsole(name="fbcon", index=0, width=40, height=10)
    console_register(fb)
    console_write("fbcon", "Hello from fbcon!\n")
    console_write("fbcon", "Line 2 of framebuffer\n")
    print(f"  Framebuffer: {fb.width}x{fb.height}")
    print(f"  Screen contents:\n    {fb.dump_screen().replace(chr(10), chr(10) + '    ')}")

    # ── 4. Network console ─────────────────────────────────────────────────
    print("\n--- Network Console (netconsole) ---")
    net = NetConsole(
        name="netconsole", index=0,
        remote_ip="10.0.0.50", remote_port=514,
    )
    console_register(net)
    console_write("netconsole", "SYSLOG: eth0 link up\n")
    console_write("netconsole", "SYSLOG: new TCP connection\n")
    print(f"  Remote: {net.remote_ip}:{net.remote_port}")
    print(f"  Packets queued: {len(net._packets)}")
    if net._packets:
        p = net._packets[0]
        print(f"  First packet: {p['dst_ip']}:{p['dst_port']} -> {p['payload']!r}")

    # ── 5. Dummy console ───────────────────────────────────────────────────
    print("\n--- Dummy Console (nullcon) ---")
    dummy = DummyConsole()
    console_register(dummy)
    console_write("nullcon", "This goes nowhere\n")
    print(f"  Dummy console registered (output discarded)")

    # ── 6. printk with different log levels ────────────────────────────────
    print("\n--- printk() with Different Log Levels ---")
    printk(KERN_EMERG,   "System is unusable")
    printk(KERN_ALERT,   "Action required immediately")
    printk(KERN_CRIT,    "Critical hardware fault")
    printk(KERN_ERR,     "Driver probe failed for %s", "ttyS0")
    printk(KERN_WARNING, "IRQ %d disabled for %d ms", 17, 500)
    printk(KERN_NOTICE,  "All devices initialized")
    printk(KERN_INFO,    "UmerOS %s started", "0.1.0")
    printk(KERN_DEBUG,   "allocating %d pages", 256)
    print("  (8 printk calls made — see dmesg below)")

    # ── 7. dmesg output ────────────────────────────────────────────────────
    print("\n--- dmesg Output ---")
    print(dmesg())

    # ── 8. console_setup parsing ───────────────────────────────────────────
    print("\n--- console_setup() Parsing ---")
    for cmdline in ["console=ttyS0,115200", "console=ttyUSB0,9600", "console=fbcon"]:
        con = console_setup(cmdline)
        print(f"  '{cmdline}' -> name={con.name} baud={con.data.get('baud', 'n/a')} "
              f"device={con.device}")

    # ── 9. Console selection and enable/disable ────────────────────────────
    print("\n--- Console Selection & Enable/Disable ---")
    console_select("serial")
    print("  Preferred console set to 'serial'")
    console_disable("netconsole", 0)
    print("  Net console disabled")
    print(f"  Net console flags: {_flags_to_string(console_get_by_name('netconsole').flags)}")
    console_enable("netconsole", 0)
    print("  Net console re-enabled")
    print(f"  Net console flags: {_flags_to_string(console_get_by_name('netconsole').flags)}")

    # ── 10. Console list ───────────────────────────────────────────────────
    print("\n--- Registered Consoles ---")
    for line in console_list():
        print(line)

    # ── 11. Log buffer wrapping ────────────────────────────────────────────
    print("\n--- Log Buffer Wrapping ---")
    _get_log_buffer().clear()
    for i in range(10005):
        logbuf_write(KERN_DEBUG, f"message {i:06d}")
    print(f"  Buffer max_entries: {LOG_BUFFER.max_entries}")
    print(f"  Total messages written: 10005")
    print(f"  Entries stored (wrapped): {len(LOG_BUFFER.entries)}")
    print(f"  Head pointer: {LOG_BUFFER.head}")
    print(f"  Last 3 entries:")
    for line in logbuf_read(3).split("\n"):
        print(f"    {line}")

    # ── 12. Early console cleanup ──────────────────────────────────────────
    print("\n--- Boot Sequence Summary ---")
    print("  [1] early_console_register('early_uart')")
    print("  [2] SerialConsole('ttyS0') registered")
    print("  [3] FramebufferConsole('fbcon') registered")
    print("  [4] NetConsole('netconsole') registered")
    print("  [5] DummyConsole('nullcon') registered")
    print("  [6] printk() tested at all 8 log levels")
    print("  [7] dmesg shows full boot log")
    print("  [8] console_setup parses kernel cmdline")
    print("  [9] Console select/enable/disable toggling")
    print("  [10] Log buffer wrapping at 10000 entries")
    print("  Console subsystem demo complete.\n")
