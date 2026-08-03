"""
UmerOS Mailbox Subsystem
========================
Linux kernel-like mailbox framework for inter-processor
and inter-system communication.
"""

from dataclasses import dataclass, field
from typing import Optional, Callable
import time

# Try imports with fallbacks
try:
    from dataclasses import dataclass, field
except ImportError:
    raise ImportError("dataclasses module required (Python 3.7+)")

# ============================================================
# Message Flags
# ============================================================

MBOX_MSG_BYTES = 0x01   # Data is raw bytes
MBOX_MSG_CMD = 0x02     # Data is command
MBOX_MSG_SIGNAL = 0x04  # Signal-only (no data)
MBOX_MSG_ACK = 0x08     # Requires acknowledgement

# ============================================================
# Global Registries
# ============================================================

_controller_registry: dict[str, 'MboxController'] = {}
_channel_registry: dict[str, 'MboxChannel'] = {}
_rx_callback_registry: dict[str, Callable] = {}

# ============================================================
# Core Dataclasses
# ============================================================


@dataclass
class MboxMsg:
    """Mailbox message"""
    data: bytes = b''
    cmd: int = 0
    flags: int = 0
    tx_buf: bytes = b''
    rx_buf: bytearray = field(default_factory=bytearray)


@dataclass
class MboxChannel:
    """Mailbox channel (one direction link)"""
    controller_name: str
    index: int
    name: str
    tx_buffer: list = field(default_factory=list)
    rx_buffer: list = field(default_factory=list)
    _consumer: str = ''
    _rx_callback: Callable = None
    _max_msg_size: int = 256
    _is_busy: bool = False


@dataclass
class MboxController:
    """Mailbox controller"""
    name: str
    id: int
    num_channels: int
    tx_irq: bool = True
    rx_irq: bool = True
    channels: list = field(default_factory=list)
    _is_registered: bool = False


# ============================================================
# Built-in Controllers
# ============================================================


class IpcMailboxController(MboxController):
    """IPC mailbox (for multi-core SoC communication)"""
    def __init__(self, name: str = "ipc-mailbox", ctrl_id: int = 0,
                 num_channels: int = 4):
        super().__init__(name=name, id=ctrl_id, num_channels=num_channels)


class SmdMailboxController(MboxController):
    """Shared Memory Device mailbox"""
    def __init__(self, name: str = "smd-mailbox", ctrl_id: int = 1,
                 num_channels: int = 2):
        super().__init__(name=name, id=ctrl_id, num_channels=num_channels)


class RpmMailboxController(MboxController):
    """RPM (Resource Power Manager) mailbox"""
    def __init__(self, name: str = "rpm-mailbox", ctrl_id: int = 2,
                 num_channels: int = 1):
        super().__init__(name=name, id=ctrl_id, num_channels=num_channels)


# ============================================================
# Kernel API Functions
# ============================================================


def mbox_controller_register(controller: MboxController) -> None:
    """Register mailbox controller"""
    if controller.name in _controller_registry:
        raise ValueError(f"Controller '{controller.name}' already registered")
    _controller_registry[controller.name] = controller
    controller._is_registered = True
    for i in range(controller.num_channels):
        ch_name = f"{controller.name}:ch{i}"
        ch = MboxChannel(controller_name=controller.name, index=i, name=ch_name)
        controller.channels.append(ch)
        _channel_registry[ch_name] = ch
    print(f"[mbox] Controller '{controller.name}' registered with {controller.num_channels} channels")


def mbox_controller_unregister(name: str) -> None:
    """Unregister controller"""
    if name not in _controller_registry:
        raise ValueError(f"Controller '{name}' not found")
    ctrl = _controller_registry.pop(name)
    ctrl._is_registered = False
    for ch in ctrl.channels:
        _channel_registry.pop(ch.name, None)
        _rx_callback_registry.pop(ch._consumer, None)
    ctrl.channels.clear()
    print(f"[mbox] Controller '{name}' unregistered")


def mbox_request_channel(consumer_name: str, controller_name: str,
                         index: int) -> MboxChannel:
    """Request mailbox channel - like mbox_request_channel()"""
    if controller_name not in _controller_registry:
        raise ValueError(f"Controller '{controller_name}' not found")
    ch_key = f"{controller_name}:ch{index}"
    if ch_key not in _channel_registry:
        raise ValueError(f"Channel {index} not found on controller '{controller_name}'")
    ch = _channel_registry[ch_key]
    if ch._consumer:
        raise ResourceWarning(f"Channel {ch_key} already owned by '{ch._consumer}'")
    ch._consumer = consumer_name
    print(f"[mbox] Channel {ch_key} claimed by consumer '{consumer_name}'")
    return ch


def mbox_free_channel(consumer_name: str) -> None:
    """Free mailbox channel"""
    for ch in _channel_registry.values():
        if ch._consumer == consumer_name:
            ch._consumer = ''
            ch._rx_callback = None
            ch.tx_buffer.clear()
            ch.rx_buffer.clear()
            ch._is_busy = False
            _rx_callback_registry.pop(consumer_name, None)
            print(f"[mbox] Channel {ch.name} freed by consumer '{consumer_name}'")
            return
    raise ValueError(f"No channel owned by consumer '{consumer_name}'")


def mbox_send_message(consumer_name: str, message: MboxMsg) -> bool:
    """Send message - like mbox_send_message()"""
    ch = _find_channel_by_consumer(consumer_name)
    if ch is None:
        raise ValueError(f"No channel owned by consumer '{consumer_name}'")
    if ch._is_busy:
        print(f"[mbox] Channel {ch.name} busy, message queued")
        ch.tx_buffer.append(message)
        return False
    ch._is_busy = True
    payload = message.data if message.data else message.tx_buf
    ch.tx_buffer.append(message)
    print(f"[mbox] TX on {ch.name}: {len(payload)} bytes, flags=0x{message.flags:02x}")
    ctrl = _controller_registry[ch.controller_name]
    if ctrl.rx_irq:
        print(f"[mbox] RX IRQ triggered on {ch.controller_name}")
    ch._is_busy = False
    return True


def mbox_recv_message(controller_name: str, index: int) -> Optional[MboxMsg]:
    """Receive message"""
    ch_key = f"{controller_name}:ch{index}"
    if ch_key not in _channel_registry:
        raise ValueError(f"Channel {ch_key} not found")
    ch = _channel_registry[ch_key]
    if not ch.rx_buffer:
        return None
    msg = ch.rx_buffer.pop(0)
    print(f"[mbox] RX on {ch.name}: {len(msg.data)} bytes")
    return msg


def mbox_client_register_rx(consumer_name: str,
                            callback: Callable) -> None:
    """Register RX callback"""
    _rx_callback_registry[consumer_name] = callback
    ch = _find_channel_by_consumer(consumer_name)
    if ch is not None:
        ch._rx_callback = callback
    print(f"[mbox] RX callback registered for consumer '{consumer_name}'")


def mbox_client_unregister_rx(consumer_name: str) -> None:
    """Unregister RX callback"""
    if consumer_name in _rx_callback_registry:
        del _rx_callback_registry[consumer_name]
        print(f"[mbox] RX callback unregistered for consumer '{consumer_name}'")


def mbox_message_received(controller_name: str, index: int) -> None:
    """Signal message received (simulates RX IRQ)"""
    ch_key = f"{controller_name}:ch{index}"
    if ch_key not in _channel_registry:
        raise ValueError(f"Channel {ch_key} not found")
    ch = _channel_registry[ch_key]
    if not ch.rx_buffer:
        print(f"[mbox] No pending messages on {ch_key}")
        return
    msg = ch.rx_buffer[0]
    cb = ch._rx_callback or _rx_callback_registry.get(ch._consumer)
    if cb:
        print(f"[mbox] Firing RX callback on {ch_key} for consumer '{ch._consumer}'")
        cb(msg)
    else:
        print(f"[mbox] Message received on {ch_key} (no callback registered)")


def mbox_channel_busy(consumer_name: str) -> bool:
    """Check if channel is busy"""
    ch = _find_channel_by_consumer(consumer_name)
    if ch is None:
        return False
    return ch._is_busy


def mbox_flush(consumer_name: str) -> None:
    """Flush pending messages"""
    ch = _find_channel_by_consumer(consumer_name)
    if ch is None:
        raise ValueError(f"No channel owned by consumer '{consumer_name}'")
    tx_count = len(ch.tx_buffer)
    rx_count = len(ch.rx_buffer)
    ch.tx_buffer.clear()
    ch.rx_buffer.clear()
    print(f"[mbox] Flushed {ch.name}: {tx_count} TX, {rx_count} RX messages dropped")


# ============================================================
# Internal Helpers
# ============================================================


def _find_channel_by_consumer(consumer_name: str) -> Optional[MboxChannel]:
    """Find channel owned by given consumer"""
    for ch in _channel_registry.values():
        if ch._consumer == consumer_name:
            return ch
    return None


# ============================================================
# Demo
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("UmerOS Mailbox Subsystem Demo")
    print("=" * 60)

    # --- Create controllers ---
    print("\n--- Creating Mailbox Controllers ---")
    ipc = IpcMailboxController(name="ipc-mailbox", num_channels=4)
    smd = SmdMailboxController(name="smd-mailbox", num_channels=2)
    rpm = RpmMailboxController(name="rpm-mailbox", num_channels=1)

    # --- Register controllers ---
    print("\n--- Registering Controllers ---")
    mbox_controller_register(ipc)
    mbox_controller_register(smd)
    mbox_controller_register(rpm)

    # --- Consumer devices request channels ---
    print("\n--- Consumers Requesting Channels ---")
    mbox_request_channel("cpu0-smp", "ipc-mailbox", 0)
    mbox_request_channel("gpu-driver", "ipc-mailbox", 1)
    mbox_request_channel("codec-dsp", "smd-mailbox", 0)
    mbox_request_channel("rpm-cmd", "rpm-mailbox", 0)

    # --- Register RX callbacks ---
    print("\n--- Registering RX Callbacks ---")

    def cpu0_rx_cb(msg: MboxMsg):
        print(f"  [cpu0-rx] Got message: data={msg.data}, cmd={msg.cmd}")

    def gpu_rx_cb(msg: MboxMsg):
        print(f"  [gpu-rx] Got message: data={msg.data}, flags=0x{msg.flags:02x}")

    def rpm_rx_cb(msg: MboxMsg):
        print(f"  [rpm-rx] Got command: {msg.cmd}")

    mbox_client_register_rx("cpu0-smp", cpu0_rx_cb)
    mbox_client_register_rx("gpu-driver", gpu_rx_cb)
    mbox_client_register_rx("rpm-cmd", rpm_rx_cb)

    # --- Send and receive messages ---
    print("\n--- Sending Messages ---")
    msg1 = MboxMsg(data=b"Hello from CPU0", flags=MBOX_MSG_BYTES)
    mbox_send_message("cpu0-smp", msg1)

    msg2 = MboxMsg(cmd=0x42, flags=MBOX_MSG_CMD | MBOX_MSG_ACK)
    mbox_send_message("gpu-driver", msg2)

    msg3 = MboxMsg(data=b"clock-set", cmd=0x01, flags=MBOX_MSG_CMD)
    mbox_send_message("rpm-cmd", msg3)

    # --- Show channel busy status ---
    print("\n--- Channel Busy Status ---")
    for consumer in ["cpu0-smp", "gpu-driver", "codec-dsp", "rpm-cmd"]:
        busy = mbox_channel_busy(consumer)
        print(f"  {consumer}: {'BUSY' if busy else 'IDLE'}")

    # --- Simulate RX (inject messages into RX buffers) ---
    print("\n--- Simulating RX Messages ---")
    rx_msg1 = MboxMsg(data=b"ACK from cpu1", flags=MBOX_MSG_ACK)
    _channel_registry["ipc-mailbox:ch0"].rx_buffer.append(rx_msg1)

    rx_msg2 = MboxMsg(cmd=0x10, flags=MBOX_MSG_SIGNAL)
    _channel_registry["ipc-mailbox:ch1"].rx_buffer.append(rx_msg2)

    rx_msg3 = MboxMsg(data=b"rpm-query", cmd=0x05, flags=MBOX_MSG_CMD | MBOX_MSG_ACK)
    _channel_registry["rpm-mailbox:ch0"].rx_buffer.append(rx_msg3)

    # --- Fire RX callbacks ---
    print("\n--- Firing RX Callbacks ---")
    mbox_message_received("ipc-mailbox", 0)
    mbox_message_received("ipc-mailbox", 1)
    mbox_message_received("rpm-mailbox", 0)

    # --- Message flags demo ---
    print("\n--- Message Flags Demo ---")
    flag_msgs = [
        MboxMsg(data=b"raw-bytes", flags=MBOX_MSG_BYTES),
        MboxMsg(cmd=0xFF, flags=MBOX_MSG_CMD),
        MboxMsg(flags=MBOX_MSG_SIGNAL),
        MboxMsg(data=b"ack-me", flags=MBOX_MSG_BYTES | MBOX_MSG_ACK),
    ]
    for fm in flag_msgs:
        names = []
        if fm.flags & MBOX_MSG_BYTES:
            names.append("BYTES")
        if fm.flags & MBOX_MSG_CMD:
            names.append("CMD")
        if fm.flags & MBOX_MSG_SIGNAL:
            names.append("SIGNAL")
        if fm.flags & MBOX_MSG_ACK:
            names.append("ACK")
        print(f"  Flags 0x{fm.flags:02x} -> {' | '.join(names)}")

    # --- Flush demo ---
    print("\n--- Flush Demo ---")
    _channel_registry["smd-mailbox:ch0"].tx_buffer.append(
        MboxMsg(data=b"queued-1", flags=MBOX_MSG_BYTES)
    )
    _channel_registry["smd-mailbox:ch0"].tx_buffer.append(
        MboxMsg(data=b"queued-2", flags=MBOX_MSG_BYTES)
    )
    mbox_flush("codec-dsp")

    # --- Unregister callbacks ---
    print("\n--- Cleanup ---")
    mbox_client_unregister_rx("gpu-driver")
    mbox_free_channel("gpu-driver")
    mbox_free_channel("rpm-cmd")

    # --- Unregister controllers ---
    print("\n--- Unregistering Controllers ---")
    mbox_controller_unregister("ipc-mailbox")
    mbox_controller_unregister("smd-mailbox")
    mbox_controller_unregister("rpm-mailbox")

    print("\n" + "=" * 60)
    print("Mailbox subsystem demo complete")
    print("=" * 60)
