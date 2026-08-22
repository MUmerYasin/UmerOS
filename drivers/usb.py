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
UmerOS USB Framework
====================
Kernel USB subsystem.
Implements HCDs, USB devices, interfaces, endpoints, drivers,
control/bulk/interrupt transfers, hubs, and simulated USB devices
(keyboard, mouse, mass storage, serial adapter).
"""

from __future__ import annotations

import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# USB device classes
# ---------------------------------------------------------------------------
USB_CLASS_AUDIO = 0x01
USB_CLASS_CDC = 0x02
USB_CLASS_HID = 0x03
USB_CLASS_PRINTER = 0x07
USB_CLASS_MASS_STORAGE = 0x08
USB_CLASS_HUB = 0x09
USB_CLASS_VIDEO = 0x0E
USB_CLASS_WIRELESS = 0xE0
USB_CLASS_VENDOR_SPEC = 0xFF

# ---------------------------------------------------------------------------
# USB speed constants
# ---------------------------------------------------------------------------
USB_SPEED_UNKNOWN = 0
USB_SPEED_LOW = 1
USB_SPEED_FULL = 2
USB_SPEED_HIGH = 3
USB_SPEED_SUPER = 4
USB_SPEED_SUPER_PLUS = 5

_SPEED_MAP: dict[str, int] = {
    "unknown": USB_SPEED_UNKNOWN,
    "low": USB_SPEED_LOW,
    "full": USB_SPEED_FULL,
    "high": USB_SPEED_HIGH,
    "super": USB_SPEED_SUPER,
    "super_speed_plus": USB_SPEED_SUPER_PLUS,
    "super-plus": USB_SPEED_SUPER_PLUS,
}

_SPEED_MBPS: dict[str, int] = {
    "low": 1,
    "full": 12,
    "high": 480,
    "super": 5000,
    "super_speed_plus": 10000,
    "super-plus": 10000,
}

# ---------------------------------------------------------------------------
# USB standard request codes
# ---------------------------------------------------------------------------
USB_REQ_GET_STATUS = 0x00
USB_REQ_CLEAR_FEATURE = 0x01
USB_REQ_SET_FEATURE = 0x03
USB_REQ_SET_ADDRESS = 0x05
USB_REQ_GET_DESCRIPTOR = 0x06
USB_REQ_SET_DESCRIPTOR = 0x07
USB_REQ_GET_CONFIGURATION = 0x08
USB_REQ_SET_CONFIGURATION = 0x09
USB_REQ_GET_INTERFACE = 0x0A
USB_REQ_SET_INTERFACE = 0x0B

# Descriptor types
USB_DT_DEVICE = 0x01
USB_DT_CONFIGURATION = 0x02
USB_DT_STRING = 0x03
USB_DT_INTERFACE = 0x04
USB_DT_ENDPOINT = 0x05

# ---------------------------------------------------------------------------
# Endpoint bmAttributes transfer types
# ---------------------------------------------------------------------------
USB_ENDPOINT_XFER_CONTROL = 0
USB_ENDPOINT_XFER_ISOC = 1
USB_ENDPOINT_XFER_BULK = 2
USB_ENDPOINT_XFER_INT = 3

_EP_TYPE_MAP: dict[int, str] = {
    USB_ENDPOINT_XFER_CONTROL: "control",
    USB_ENDPOINT_XFER_ISOC: "isochronous",
    USB_ENDPOINT_XFER_BULK: "bulk",
    USB_ENDPOINT_XFER_INT: "interrupt",
}

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class UsbEndpoint:
    """USB endpoint"""
    addr: int  # endpoint address
    attributes: int = 0  # bmAttributes
    max_packet_size: int = 64
    interval: int = 0
    ep_type: str = "control"  # control, isochronous, bulk, interrupt
    direction: str = "out"  # in, out
    is_enabled: bool = True

    def __post_init__(self) -> None:
        if self.addr & 0x80:
            self.direction = "in"
        else:
            self.direction = "out"
        if self.attributes:
            self.ep_type = _EP_TYPE_MAP.get(self.attributes & 0x03, "control")


@dataclass
class UsbInterface:
    """USB interface"""
    num: int  # interface number
    alternate: int = 0
    interface_class: int = 0
    interface_subclass: int = 0
    interface_protocol: int = 0
    num_endpoints: int = 0
    endpoints: list = field(default_factory=list)  # UsbEndpoint
    driver: str = ""
    is_active: bool = False


@dataclass
class UsbDevice:
    """USB device"""
    devnum: int  # device number on bus
    bus_name: str  # host controller name
    speed: str = "high"
    devpath: str = ""
    route: str = ""
    level: int = 0
    parent: str = ""
    product: str = ""
    manufacturer: str = ""
    serial: str = ""
    dev_vendor: int = 0
    dev_product: int = 0
    dev_class: int = 0
    dev_subclass: int = 0
    dev_protocol: int = 0
    maxpacket: dict = field(default_factory=dict)  # endpoint -> packet size
    ep0_in: int = 64
    ep0_out: int = 64
    num_configurations: int = 1
    is_active: bool = False
    is_configured: bool = False
    is_connected: bool = True
    is_suspended: bool = False
    config_value: int = 0
    configuration: str = ""
    _configs: list = field(default_factory=list)
    _interfaces: list = field(default_factory=list)

    @property
    def speed_mbps(self) -> int:
        return _SPEED_MBPS.get(self.speed, 0)

    @property
    def name(self) -> str:
        return f"{self.bus_name}-{self.devnum}"

    def __repr__(self) -> str:
        return (
            f"UsbDevice(name={self.name!r}, product={self.product!r}, "
            f"speed={self.speed}, vendor=0x{self.dev_vendor:04x}, "
            f"product_id=0x{self.dev_product:04x}, class={self.dev_class:#x})"
        )


@dataclass
class UsbDriver:
    """USB device driver"""
    name: str
    probe: object = None
    disconnect: object = None
    suspend: object = None
    resume: object = None
    reset_resume: object = None
    pre_reset: object = None
    post_reset: object = None
    id_table: list = field(default_factory=list)
    is_registered: bool = False


@dataclass
class UsbRequest:
    """USB transfer request"""
    ep: int  # endpoint
    buf: bytes = b''
    length: int = 0
    actual_length: int = 0
    status: int = 0
    flags: int = 0
    complete: object = None
    context: object = None


@dataclass
class UsbConfigDescriptor:
    """USB configuration descriptor"""
    bNumInterfaces: int = 1
    bmAttributes: int = 0x80  # bus-powered
    MaxPower: int = 50  # mA
    iConfiguration: str = ""


@dataclass
class UsbStringDescriptor:
    """USB string descriptor"""
    id: int
    string: str = ""


@dataclass
class UsbHubPort:
    """USB hub port"""
    portnum: int
    status: int = 0
    change: int = 0
    is_connected: bool = False
    speed: str = "high"
    power: int = 100  # mA
    is_enabled: bool = False
    reset_count: int = 0


@dataclass
class UsbHub:
    """USB hub"""
    hub_name: str
    hub_class: int = 9  # USB_CLASS_HUB
    n_ports: int = 4
    port0_is_think: bool = False
    ports: list = field(default_factory=list)  # list of UsbHubPort

    def __post_init__(self) -> None:
        if not self.ports:
            self.ports = [UsbHubPort(portnum=i + 1) for i in range(self.n_ports)]


@dataclass
class UsbHcd:
    """USB Host Controller Driver"""
    name: str
    product_desc: str = ""
    hcd_priv_size: int = 0
    flags: int = 0
    root_hub: object = None
    is_registered: bool = False
    _speed: str = "high"
    _port_count: int = 0
    _ports: list = field(default_factory=list)

    @property
    def speed(self) -> str:
        return self._speed

    @property
    def port_count(self) -> int:
        return self._port_count

    def __repr__(self) -> str:
        return (
            f"UsbHcd(name={self.name!r}, product={self.product_desc!r}, "
            f"speed={self._speed}, ports={self._port_count}, "
            f"registered={self.is_registered})"
        )


# ---------------------------------------------------------------------------
# Global registries
# ---------------------------------------------------------------------------
_hcds: dict[str, UsbHcd] = {}
_devices: dict[str, UsbDevice] = {}
_drivers: dict[str, UsbDriver] = {}
_hubs: dict[str, UsbHub] = {}
_device_counter: int = 0
_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _next_devnum() -> int:
    global _device_counter
    _device_counter += 1
    return _device_counter


def _make_devpath(bus: str, devnum: int) -> str:
    return f"{devnum}"


def _build_device(
    bus_name: str,
    speed: str,
    product: str,
    manufacturer: str,
    serial: str,
    vendor: int,
    product_id: int,
    dev_class: int,
    dev_subclass: int,
    dev_protocol: int,
    parent: str,
    level: int,
    ep0_max: int,
    num_configs: int,
    interfaces: list[UsbInterface],
) -> UsbDevice:
    devnum = _next_devnum()
    devpath = _make_devpath(bus_name, devnum)
    route = f"{devpath}"
    dev = UsbDevice(
        devnum=devnum,
        bus_name=bus_name,
        speed=speed,
        devpath=devpath,
        route=route,
        level=level,
        parent=parent,
        product=product,
        manufacturer=manufacturer,
        serial=serial,
        dev_vendor=vendor,
        dev_product=product_id,
        dev_class=dev_class,
        dev_subclass=dev_subclass,
        dev_protocol=dev_protocol,
        maxpacket={0: ep0_max},
        ep0_in=ep0_max,
        ep0_out=ep0_max,
        num_configurations=num_configs,
    )
    dev._interfaces = interfaces
    dev._configs = [UsbConfigDescriptor(bNumInterfaces=len(interfaces))]
    return dev


# ---------------------------------------------------------------------------
# HCD API
# ---------------------------------------------------------------------------

def usb_add_hcd(
    name: str,
    product_desc: str = "",
    flags: int = 0,
    speed: str = "high",
    port_count: int = 4,
) -> UsbHcd:
    """Add host controller - like usb_add_hcd()."""
    with _lock:
        if name in _hcds:
            log.warning("HCD %s already registered", name)
            return _hcds[name]
        hcd = UsbHcd(
            name=name,
            product_desc=product_desc,
            flags=flags,
            _speed=speed,
            _port_count=port_count,
            is_registered=True,
        )
        hcd.root_hub = SimRootHub(name=f"rh-{name}", n_ports=port_count, speed=speed)
        hcd._ports = list(hcd.root_hub.ports)
        _hcds[name] = hcd
        log.info("HCD registered: %s (%s, %d ports)", name, product_desc, port_count)
        return hcd


def usb_remove_hcd(name: str) -> bool:
    """Remove host controller."""
    with _lock:
        hcd = _hcds.pop(name, None)
        if hcd is None:
            log.warning("HCD %s not found", name)
            return False
        hcd.is_registered = False
        log.info("HCD removed: %s", name)
        return True


def usb_hcd_is_primary_rh(name: str) -> bool:
    """Check if HCD is primary root hub."""
    hcd = _hcds.get(name)
    return hcd is not None and hcd.is_registered


# ---------------------------------------------------------------------------
# Device API
# ---------------------------------------------------------------------------

def usb_get_dev(bus_name: str, devnum: int) -> Optional[UsbDevice]:
    """Get USB device."""
    key = f"{bus_name}-{devnum}"
    dev = _devices.get(key)
    if dev is not None:
        dev.is_connected = True
    return dev


def usb_put_dev(dev_name: str) -> bool:
    """Release USB device."""
    dev = _devices.pop(dev_name, None)
    if dev is None:
        log.warning("Device %s not found", dev_name)
        return False
    dev.is_connected = False
    log.info("Device released: %s", dev_name)
    return True


def usb_get_device_descriptor(dev_name: str) -> Optional[dict]:
    """Get device descriptor."""
    dev = _devices.get(dev_name)
    if dev is None:
        return None
    return {
        "bLength": 18,
        "bDescriptorType": USB_DT_DEVICE,
        "bcdUSB": 0x0200,
        "bDeviceClass": dev.dev_class,
        "bDeviceSubClass": dev.dev_subclass,
        "bDeviceProtocol": dev.dev_protocol,
        "bMaxPacketSize0": dev.ep0_in,
        "idVendor": dev.dev_vendor,
        "idProduct": dev.dev_product,
        "bcdDevice": 0x0100,
        "iManufacturer": dev.manufacturer,
        "iProduct": dev.product,
        "iSerialNumber": dev.serial,
        "bNumConfigurations": dev.num_configurations,
    }


def usb_get_config_descriptor(dev_name: str, config_index: int = 0) -> Optional[dict]:
    """Get configuration descriptor."""
    dev = _devices.get(dev_name)
    if dev is None:
        return None
    cfg = dev._configs[config_index] if config_index < len(dev._configs) else UsbConfigDescriptor()
    return {
        "bLength": 9,
        "bDescriptorType": USB_DT_CONFIGURATION,
        "bNumInterfaces": cfg.bNumInterfaces,
        "bmAttributes": cfg.bmAttributes,
        "MaxPower": cfg.MaxPower,
        "iConfiguration": cfg.iConfiguration,
    }


def usb_get_string_descriptor(dev_name: str, string_id: int) -> Optional[UsbStringDescriptor]:
    """Get string descriptor."""
    dev = _devices.get(dev_name)
    if dev is None:
        return None
    strings = {0: UsbStringDescriptor(0, "English"), 1: UsbStringDescriptor(1, dev.manufacturer), 2: UsbStringDescriptor(2, dev.product), 3: UsbStringDescriptor(3, dev.serial)}
    return strings.get(string_id)


# ---------------------------------------------------------------------------
# Driver API
# ---------------------------------------------------------------------------

def usb_driver_register(driver_name: str, **kwargs: Any) -> UsbDriver:
    """Register USB driver."""
    with _lock:
        if driver_name in _drivers:
            log.warning("Driver %s already registered", driver_name)
            return _drivers[driver_name]
        drv = UsbDriver(name=driver_name, **kwargs)
        drv.is_registered = True
        _drivers[driver_name] = drv
        log.info("USB driver registered: %s", driver_name)
        return drv


def usb_driver_unregister(driver_name: str) -> bool:
    """Unregister USB driver."""
    with _lock:
        drv = _drivers.pop(driver_name, None)
        if drv is None:
            log.warning("Driver %s not found", driver_name)
            return False
        drv.is_registered = False
        log.info("USB driver unregistered: %s", driver_name)
        return True


# ---------------------------------------------------------------------------
# Interface API
# ---------------------------------------------------------------------------

def usb_interface_claimed(dev_name: str, interface_num: int) -> bool:
    """Check if interface is claimed."""
    dev = _devices.get(dev_name)
    if dev is None:
        return False
    for iface in dev._interfaces:
        if iface.num == interface_num:
            return iface.driver != ""
    return False


def usb_claim_interface(dev_name: str, interface_num: int, driver_name: str) -> bool:
    """Claim interface."""
    dev = _devices.get(dev_name)
    if dev is None:
        log.warning("Device %s not found", dev_name)
        return False
    for iface in dev._interfaces:
        if iface.num == interface_num:
            if iface.driver:
                log.warning("Interface %d on %s already claimed by %s", interface_num, dev_name, iface.driver)
                return False
            iface.driver = driver_name
            iface.is_active = True
            log.info("Interface %d claimed by %s on %s", interface_num, driver_name, dev_name)
            return True
    log.warning("Interface %d not found on %s", interface_num, dev_name)
    return False


def usb_release_interface(dev_name: str, interface_num: int) -> bool:
    """Release interface."""
    dev = _devices.get(dev_name)
    if dev is None:
        return False
    for iface in dev._interfaces:
        if iface.num == interface_num:
            if not iface.driver:
                log.warning("Interface %d not claimed", interface_num)
                return False
            old = iface.driver
            iface.driver = ""
            iface.is_active = False
            log.info("Interface %d released from %s on %s", interface_num, old, dev_name)
            return True
    return False


def usb_set_interface(dev_name: str, interface_num: int, alternate: int) -> bool:
    """Set interface alternate setting."""
    dev = _devices.get(dev_name)
    if dev is None:
        return False
    for iface in dev._interfaces:
        if iface.num == interface_num:
            old = iface.alternate
            iface.alternate = alternate
            log.info("Interface %d alt setting: %d -> %d on %s", interface_num, old, alternate, dev_name)
            return True
    return False


def usb_get_interface(dev_name: str, interface_num: int) -> int:
    """Get current alternate setting."""
    dev = _devices.get(dev_name)
    if dev is None:
        return -1
    for iface in dev._interfaces:
        if iface.num == interface_num:
            return iface.alternate
    return -1


# ---------------------------------------------------------------------------
# Endpoint API
# ---------------------------------------------------------------------------

def usb_ep_enable(ep_addr: int, maxpacket: int, attributes: int, interval: int) -> UsbEndpoint:
    """Enable endpoint."""
    ep_type = _EP_TYPE_MAP.get(attributes & 0x03, "control")
    direction = "in" if ep_addr & 0x80 else "out"
    ep = UsbEndpoint(
        addr=ep_addr,
        attributes=attributes,
        max_packet_size=maxpacket,
        interval=interval,
        ep_type=ep_type,
        direction=direction,
        is_enabled=True,
    )
    log.info("Endpoint 0x%02x enabled: %s %s maxpacket=%d", ep_addr, ep_type, direction, maxpacket)
    return ep


def usb_ep_disable(ep_addr: int) -> bool:
    """Disable endpoint."""
    log.info("Endpoint 0x%02x disabled", ep_addr)
    return True


# ---------------------------------------------------------------------------
# Control transfer
# ---------------------------------------------------------------------------

def usb_control_msg(
    dev_name: str,
    request_type: int,
    request: int,
    value: int,
    index: int,
    data: bytes = b'',
    timeout_ms: int = 5000,
) -> int:
    """Send control message."""
    dev = _devices.get(dev_name)
    if dev is None:
        log.error("Control msg failed: device %s not found", dev_name)
        return -19  # -ENODEV
    if dev.is_suspended:
        log.error("Control msg failed: device %s suspended", dev_name)
        return -19  # -ENODEV

    direction = "in" if request_type & 0x80 else "out"
    log.info(
        "control_msg(%s, type=0x%02x, req=0x%02x, val=0x%04x, idx=0x%04x, len=%d, dir=%s)",
        dev_name, request_type, request, value, index, len(data), direction,
    )

    # GET_DESCRIPTOR
    if request == USB_REQ_GET_DESCRIPTOR and (value >> 8) == USB_DT_STRING:
        string_id = value & 0xFF
        desc = usb_get_string_descriptor(dev_name, string_id)
        if desc:
            encoded = desc.string.encode("utf-16-le")
            log.info("  -> string descriptor: %r (%d bytes)", desc.string, len(encoded))
            return len(encoded)
        return 0

    # SET_CONFIGURATION
    if request == USB_REQ_SET_CONFIGURATION:
        dev.config_value = value
        dev.is_configured = value != 0
        dev.is_active = value != 0
        log.info("  -> SET_CONFIGURATION: %d (configured=%s)", value, dev.is_configured)
        return 0

    # SET_ADDRESS
    if request == USB_REQ_SET_ADDRESS:
        log.info("  -> SET_ADDRESS: %d", value)
        return 0

    # SET_INTERFACE
    if request == USB_REQ_SET_INTERFACE:
        usb_set_interface(dev_name, index, value)
        return 0

    # GET_INTERFACE
    if request == USB_REQ_GET_INTERFACE:
        alt = usb_get_interface(dev_name, index)
        log.info("  -> GET_INTERFACE: alt=%d", alt)
        return 0

    log.info("  -> control_msg completed (%d bytes)", len(data))
    return len(data)


def usb_control_msg_send(
    dev_name: str,
    request_type: int,
    request: int,
    value: int,
    index: int,
    data: bytes = b'',
    timeout_ms: int = 5000,
) -> int:
    """Send control message (no data phase)."""
    return usb_control_msg(dev_name, request_type, request, value, index, data, timeout_ms)


def usb_control_msg_recv(
    dev_name: str,
    request_type: int,
    request: int,
    value: int,
    index: int,
    length: int,
    timeout_ms: int = 5000,
) -> tuple[int, bytes]:
    """Receive control message."""
    dev = _devices.get(dev_name)
    if dev is None:
        return (-19, b'')
    log.info("control_msg_recv(%s, req=0x%02x, len=%d)", dev_name, request, length)

    # Simulate getting configuration descriptor
    if request == USB_REQ_GET_DESCRIPTOR and (value >> 8) == USB_DT_CONFIGURATION:
        cfg_desc = usb_get_config_descriptor(dev_name, value & 0xFF)
        if cfg_desc:
            data = bytes([9, USB_DT_CONFIGURATION, cfg_desc["bNumInterfaces"],
                          cfg_desc["bmAttributes"], cfg_desc["MaxPower"]])
            return (min(length, len(data)), data)
    return (length, b'\x00' * length)


# ---------------------------------------------------------------------------
# Bulk transfer
# ---------------------------------------------------------------------------

def usb_bulk_msg(
    dev_name: str,
    ep: int,
    data: bytes,
    timeout_ms: int = 5000,
) -> int:
    """Send/receive bulk message."""
    dev = _devices.get(dev_name)
    if dev is None:
        return -19
    if dev.is_suspended:
        return -19
    direction = "in" if ep & 0x80 else "out"
    log.info(
        "bulk_msg(%s, ep=0x%02x, len=%d, dir=%s)",
        dev_name, ep, len(data), direction,
    )
    return len(data)


# ---------------------------------------------------------------------------
# Interrupt transfer
# ---------------------------------------------------------------------------

def usb_interrupt_msg(
    dev_name: str,
    ep: int,
    data: bytes,
    timeout_ms: int = 0,
) -> int:
    """Send/receive interrupt message."""
    dev = _devices.get(dev_name)
    if dev is None:
        return -19
    direction = "in" if ep & 0x80 else "out"
    log.info(
        "interrupt_msg(%s, ep=0x%02x, len=%d, dir=%s)",
        dev_name, ep, len(data), direction,
    )
    return len(data)


# ---------------------------------------------------------------------------
# Isochronous transfer
# ---------------------------------------------------------------------------

def usb_iso_msg(dev_name: str, ep: int, data: bytes) -> int:
    """Send isochronous message."""
    dev = _devices.get(dev_name)
    if dev is None:
        return -19
    log.info("iso_msg(%s, ep=0x%02x, len=%d)", dev_name, ep, len(data))
    return len(data)


# ---------------------------------------------------------------------------
# Suspend / Resume / Reset
# ---------------------------------------------------------------------------

def usb_suspend(dev_name: str) -> bool:
    """Suspend USB device."""
    dev = _devices.get(dev_name)
    if dev is None:
        return False
    dev.is_suspended = True
    dev.is_active = False
    log.info("Device %s suspended", dev_name)
    return True


def usb_resume(dev_name: str) -> bool:
    """Resume USB device."""
    dev = _devices.get(dev_name)
    if dev is None:
        return False
    dev.is_suspended = False
    dev.is_active = dev.is_configured
    log.info("Device %s resumed", dev_name)
    return True


def usb_reset_device(dev_name: str) -> bool:
    """Reset USB device."""
    dev = _devices.get(dev_name)
    if dev is None:
        return False
    dev.is_suspended = False
    dev.is_configured = False
    dev.is_active = False
    dev.config_value = 0
    for iface in dev._interfaces:
        iface.driver = ""
        iface.is_active = False
        iface.alternate = 0
    log.info("Device %s reset", dev_name)
    return True


# ---------------------------------------------------------------------------
# Speed / Info
# ---------------------------------------------------------------------------

def usb_get_speed(dev_name: str) -> str:
    """Get device speed."""
    dev = _devices.get(dev_name)
    return dev.speed if dev else "unknown"


def usb_get_speed_value(speed_str: str) -> int:
    """Get numeric speed value."""
    return _SPEED_MAP.get(speed_str, USB_SPEED_UNKNOWN)


def usb_get_maxpacket(dev_name: str, ep: int = 0) -> int:
    """Get max packet size for endpoint."""
    dev = _devices.get(dev_name)
    if dev is None:
        return 0
    return dev.maxpacket.get(ep, 64)


def usb_get_device_name(dev_name: str) -> str:
    """Get device name string."""
    dev = _devices.get(dev_name)
    if dev is None:
        return ""
    return f"{dev.manufacturer} {dev.product}".strip()


def usb_get_bus_name(dev_name: str) -> str:
    """Get bus (HCD) name."""
    dev = _devices.get(dev_name)
    return dev.bus_name if dev else ""


# ---------------------------------------------------------------------------
# Hub API
# ---------------------------------------------------------------------------

def usb_hub_register(hub_name: str, n_ports: int = 4) -> UsbHub:
    """Register USB hub."""
    with _lock:
        if hub_name in _hubs:
            log.warning("Hub %s already registered", hub_name)
            return _hubs[hub_name]
        hub = UsbHub(hub_name=hub_name, n_ports=n_ports)
        _hubs[hub_name] = hub
        log.info("Hub registered: %s (%d ports)", hub_name, n_ports)
        return hub


def usb_hub_unregister(hub_name: str) -> bool:
    """Unregister USB hub."""
    with _lock:
        hub = _hubs.pop(hub_name, None)
        if hub is None:
            log.warning("Hub %s not found", hub_name)
            return False
        log.info("Hub unregistered: %s", hub_name)
        return True


def usb_hub_port_connect(hub_name: str, portnum: int, speed: str = "high") -> bool:
    """Simulate device connection on hub port."""
    hub = _hubs.get(hub_name)
    if hub is None:
        log.warning("Hub %s not found", hub_name)
        return False
    for port in hub.ports:
        if port.portnum == portnum:
            port.is_connected = True
            port.speed = speed
            port.is_enabled = True
            port.status |= 0x01  # USB_PORT_STAT_CONNECTION
            port.change |= 0x01
            log.info("Hub %s port %d: device connected (%s)", hub_name, portnum, speed)
            return True
    log.warning("Hub %s port %d not found", hub_name, portnum)
    return False


def usb_hub_port_disconnect(hub_name: str, portnum: int) -> bool:
    """Simulate device disconnection from hub port."""
    hub = _hubs.get(hub_name)
    if hub is None:
        return False
    for port in hub.ports:
        if port.portnum == portnum:
            port.is_connected = False
            port.is_enabled = False
            port.status &= ~0x01
            port.change |= 0x01
            log.info("Hub %s port %d: device disconnected", hub_name, portnum)
            return True
    return False


def usb_hub_port_reset(hub_name: str, portnum: int) -> bool:
    """Reset hub port."""
    hub = _hubs.get(hub_name)
    if hub is None:
        return False
    for port in hub.ports:
        if port.portnum == portnum:
            port.reset_count += 1
            port.status |= 0x10  # USB_PORT_STAT_RESET
            port.change |= 0x02  # USB_PORT_STAT_C_RESET
            log.info("Hub %s port %d: reset (count=%d)", hub_name, portnum, port.reset_count)
            port.status &= ~0x10
            return True
    return False


def usb_hub_set_port_power(hub_name: str, portnum: int, on: bool = True) -> bool:
    """Set port power."""
    hub = _hubs.get(hub_name)
    if hub is None:
        return False
    for port in hub.ports:
        if port.portnum == portnum:
            if on:
                port.power = 100
                port.status |= 0x08  # USB_PORT_STAT_POWER
            else:
                port.power = 0
                port.status &= ~0x08
            log.info("Hub %s port %d: power %s", hub_name, portnum, "on" if on else "off")
            return True
    return False


def usb_hub_get_port_status(hub_name: str, portnum: int) -> Optional[dict]:
    """Get port status."""
    hub = _hubs.get(hub_name)
    if hub is None:
        return None
    for port in hub.ports:
        if port.portnum == portnum:
            return {
                "portnum": port.portnum,
                "status": port.status,
                "change": port.change,
                "connected": port.is_connected,
                "speed": port.speed,
                "power": port.power,
                "enabled": port.is_enabled,
                "reset_count": port.reset_count,
            }
    return None


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------

def usb_list_hcds() -> list[dict]:
    """List host controllers."""
    result = []
    for name, hcd in _hcds.items():
        result.append({
            "name": name,
            "product": hcd.product_desc,
            "speed": hcd._speed,
            "ports": hcd._port_count,
            "registered": hcd.is_registered,
            "root_hub": hcd.root_hub.name if hcd.root_hub else None,
        })
    return result


def usb_list_devices() -> list[dict]:
    """List USB devices."""
    result = []
    for name, dev in _devices.items():
        result.append({
            "name": name,
            "bus": dev.bus_name,
            "devnum": dev.devnum,
            "product": dev.product,
            "manufacturer": dev.manufacturer,
            "serial": dev.serial,
            "speed": dev.speed,
            "vendor": f"0x{dev.dev_vendor:04x}",
            "product_id": f"0x{dev.dev_product:04x}",
            "class": f"0x{dev.dev_class:02x}",
            "configured": dev.is_configured,
            "active": dev.is_active,
            "suspended": dev.is_suspended,
            "parent": dev.parent,
        })
    return result


# ---------------------------------------------------------------------------
# Simulated root hub
# ---------------------------------------------------------------------------

class SimRootHub:
    """Simulated root hub"""

    def __init__(self, name: str, n_ports: int = 4, speed: str = "high") -> None:
        self.name = name
        self.n_ports = n_ports
        self.speed = speed
        self.ports: list[UsbHubPort] = []
        for i in range(n_ports):
            port = UsbHubPort(portnum=i + 1, speed=speed, power=100)
            port.status = 0x08  # USB_PORT_STAT_POWER
            self.ports.append(port)
        log.info("Root hub created: %s (%d ports, %s)", name, n_ports, speed)

    def __repr__(self) -> str:
        return f"SimRootHub(name={self.name!r}, ports={self.n_ports}, speed={self.speed})"


# ---------------------------------------------------------------------------
# Simulated external hub
# ---------------------------------------------------------------------------

class SimExternalHub:
    """Simulated external USB hub (4/7/10 ports)"""

    def __init__(self, name: str = "hub1", n_ports: int = 4, parent_hub: str = "") -> None:
        self.name = name
        self.n_ports = n_ports
        self.parent_hub = parent_hub
        self.usb_hub = usb_hub_register(name, n_ports)
        log.info(
            "External hub created: %s (%d ports, parent=%s)",
            name, n_ports, parent_hub or "root",
        )

    def __repr__(self) -> str:
        return f"SimExternalHub(name={self.name!r}, ports={self.n_ports})"


# ---------------------------------------------------------------------------
# Simulated USB hub (alias for backward compat)
# ---------------------------------------------------------------------------

class SimUsbHub:
    """Simulated USB hub"""

    def __init__(self, name: str, n_ports: int = 4) -> None:
        self.name = name
        self.n_ports = n_ports
        self.usb_hub = usb_hub_register(name, n_ports)
        log.info("USB hub created: %s (%d ports)", name, n_ports)

    def __repr__(self) -> str:
        return f"SimUsbHub(name={self.name!r}, ports={self.n_ports})"


# ---------------------------------------------------------------------------
# Simulated USB Keyboard (HID)
# ---------------------------------------------------------------------------

class SimUsbKeyboard:
    """Simulated USB keyboard (HID)"""

    def __init__(self, name: str = "kbd1") -> None:
        self.name = name
        bus_name = "ehci.0"
        if bus_name not in _hcds:
            usb_add_hcd(bus_name, product_desc="Simulated EHCI", speed="high", port_count=4)

        interfaces = [
            UsbInterface(
                num=0,
                interface_class=USB_CLASS_HID,
                interface_subclass=1,  # Boot interface
                interface_protocol=1,  # Keyboard
                num_endpoints=1,
                endpoints=[
                    UsbEndpoint(addr=0x81, attributes=3, max_packet_size=8, interval=10),
                ],
            ),
        ]

        dev = _build_device(
            bus_name=bus_name,
            speed="high",
            product=f"USB Keyboard [{name}]",
            manufacturer="Simulated",
            serial=f"KBD-{name}",
            vendor=0x1234,
            product_id=0x5678,
            dev_class=0,
            dev_subclass=0,
            dev_protocol=0,
            parent="",
            level=0,
            ep0_max=64,
            num_configs=1,
            interfaces=interfaces,
        )
        dev.is_active = True
        dev.is_configured = True
        dev.config_value = 1

        key = f"{bus_name}-{dev.devnum}"
        _devices[key] = dev
        self.dev_name = key
        log.info("Keyboard created: %s (%s)", key, dev.product)

    def press_key(self, scancode: int) -> bytes:
        """Simulate a key press and return HID report."""
        report = bytes([0x00, 0x00, scancode, 0x00, 0x00, 0x00, 0x00, 0x00])
        log.info("Keyboard %s: key press scancode=0x%02x", self.name, scancode)
        usb_interrupt_msg(self.dev_name, 0x81, report)
        return report

    def release_key(self) -> bytes:
        """Simulate key release."""
        report = b'\x00' * 8
        log.info("Keyboard %s: key release", self.name)
        usb_interrupt_msg(self.dev_name, 0x81, report)
        return report

    def __repr__(self) -> str:
        return f"SimUsbKeyboard(name={self.name!r}, dev={self.dev_name!r})"


# ---------------------------------------------------------------------------
# Simulated USB Mouse (HID)
# ---------------------------------------------------------------------------

class SimUsbMouse:
    """Simulated USB mouse (HID)"""

    def __init__(self, name: str = "mouse1") -> None:
        self.name = name
        bus_name = "ehci.0"
        if bus_name not in _hcds:
            usb_add_hcd(bus_name, product_desc="Simulated EHCI", speed="high", port_count=4)

        interfaces = [
            UsbInterface(
                num=0,
                interface_class=USB_CLASS_HID,
                interface_subclass=1,  # Boot interface
                interface_protocol=2,  # Mouse
                num_endpoints=1,
                endpoints=[
                    UsbEndpoint(addr=0x81, attributes=3, max_packet_size=4, interval=8),
                ],
            ),
        ]

        dev = _build_device(
            bus_name=bus_name,
            speed="full",
            product=f"USB Mouse [{name}]",
            manufacturer="Simulated",
            serial=f"MOUSE-{name}",
            vendor=0xABCD,
            product_id=0xEF01,
            dev_class=0,
            dev_subclass=0,
            dev_protocol=0,
            parent="",
            level=0,
            ep0_max=8,
            num_configs=1,
            interfaces=interfaces,
        )
        dev.is_active = True
        dev.is_configured = True
        dev.config_value = 1

        key = f"{bus_name}-{dev.devnum}"
        _devices[key] = dev
        self.dev_name = key
        log.info("Mouse created: %s (%s)", key, dev.product)

    def move(self, dx: int, dy: int, buttons: int = 0) -> bytes:
        """Simulate mouse movement."""
        report = bytes([
            buttons & 0x07,
            max(-127, min(127, dx)) & 0xFF,
            max(-127, min(127, dy)) & 0xFF,
            0x00,  # wheel
        ])
        log.info("Mouse %s: move dx=%d dy=%d buttons=%d", self.name, dx, dy, buttons)
        usb_interrupt_msg(self.dev_name, 0x81, report)
        return report

    def click(self, button: int = 0) -> bytes:
        """Simulate mouse click."""
        report = bytes([1 << button, 0x00, 0x00, 0x00])
        usb_interrupt_msg(self.dev_name, 0x81, report)
        release = bytes([0x00, 0x00, 0x00, 0x00])
        usb_interrupt_msg(self.dev_name, 0x81, release)
        log.info("Mouse %s: click button=%d", self.name, button)
        return report

    def __repr__(self) -> str:
        return f"SimUsbMouse(name={self.name!r}, dev={self.dev_name!r})"


# ---------------------------------------------------------------------------
# Simulated USB Mass Storage
# ---------------------------------------------------------------------------

class SimUsbMassStorage:
    """Simulated USB mass storage"""

    def __init__(self, name: str = "usb-storage1", size_mb: int = 1024) -> None:
        self.name = name
        self.size_mb = size_mb
        self.total_sectors = (size_mb * 1024 * 1024) // 512
        self._data = bytearray(self.total_sectors * 512)
        bus_name = "xhci.0"
        if bus_name not in _hcds:
            usb_add_hcd(bus_name, product_desc="Simulated xHCI", speed="super", port_count=10)

        interfaces = [
            UsbInterface(
                num=0,
                interface_class=USB_CLASS_MASS_STORAGE,
                interface_subclass=0x06,  # SCSI
                interface_protocol=0x50,  # Bulk-Only
                num_endpoints=2,
                endpoints=[
                    UsbEndpoint(addr=0x81, attributes=2, max_packet_size=512, interval=0),
                    UsbEndpoint(addr=0x02, attributes=2, max_packet_size=512, interval=0),
                ],
            ),
        ]

        dev = _build_device(
            bus_name=bus_name,
            speed="super",
            product=f"USB Mass Storage [{name}]",
            manufacturer="Simulated",
            serial=f"STOR-{name}",
            vendor=0x1058,
            product_id=0x0702,
            dev_class=0,
            dev_subclass=0,
            dev_protocol=0,
            parent="",
            level=0,
            ep0_max=512,
            num_configs=1,
            interfaces=interfaces,
        )
        dev.is_active = True
        dev.is_configured = True
        dev.config_value = 1

        key = f"{bus_name}-{dev.devnum}"
        _devices[key] = dev
        self.dev_name = key
        log.info("Mass storage created: %s (%d MB)", key, size_mb)

    def read_sectors(self, lba: int, count: int) -> bytes:
        """Read sectors from simulated disk."""
        offset = lba * 512
        end = offset + count * 512
        data = bytes(self._data[offset:min(end, len(self._data))])
        log.info("Storage %s: read LBA=%d count=%d (%d bytes)", self.name, lba, count, len(data))
        usb_bulk_msg(self.dev_name, 0x81, data)
        return data

    def write_sectors(self, lba: int, data: bytes) -> int:
        """Write sectors to simulated disk."""
        offset = lba * 512
        end = min(offset + len(data), len(self._data))
        self._data[offset:end] = data[:end - offset]
        log.info("Storage %s: write LBA=%d (%d bytes)", self.name, lba, len(data))
        usb_bulk_msg(self.dev_name, 0x02, data)
        return end - offset

    def capacity_bytes(self) -> int:
        """Get capacity in bytes."""
        return self.total_sectors * 512

    def __repr__(self) -> str:
        return f"SimUsbMassStorage(name={self.name!r}, size={self.size_mb}MB, dev={self.dev_name!r})"


# ---------------------------------------------------------------------------
# Simulated USB Serial Adapter (CDC-ACM)
# ---------------------------------------------------------------------------

class SimUsbSerial:
    """Simulated USB serial adapter (CDC-ACM)"""

    def __init__(self, name: str = "usb-serial1") -> None:
        self.name = name
        self._rx_buffer: bytearray = bytearray()
        self._baud_rate = 9600
        bus_name = "xhci.0"
        if bus_name not in _hcds:
            usb_add_hcd(bus_name, product_desc="Simulated xHCI", speed="high", port_count=10)

        interfaces = [
            UsbInterface(
                num=0,
                interface_class=USB_CLASS_CDC,
                interface_subclass=0x02,  # ACM
                interface_protocol=0x01,  # AT
                num_endpoints=1,
                endpoints=[
                    UsbEndpoint(addr=0x81, attributes=3, max_packet_size=64, interval=1),
                ],
            ),
            UsbInterface(
                num=1,
                interface_class=USB_CLASS_CDC_DATA,
                interface_subclass=0x00,
                interface_protocol=0x00,
                num_endpoints=2,
                endpoints=[
                    UsbEndpoint(addr=0x82, attributes=2, max_packet_size=64, interval=0),
                    UsbEndpoint(addr=0x02, attributes=2, max_packet_size=64, interval=0),
                ],
            ),
        ]

        dev = _build_device(
            bus_name=bus_name,
            speed="high",
            product=f"USB Serial [{name}]",
            manufacturer="Simulated",
            serial=f"SERIAL-{name}",
            vendor=0x2341,
            product_id=0x0043,
            dev_class=0x02,  # CDC
            dev_subclass=0,
            dev_protocol=0,
            parent="",
            level=0,
            ep0_max=64,
            num_configs=1,
            interfaces=interfaces,
        )
        dev.is_active = True
        dev.is_configured = True
        dev.config_value = 1

        key = f"{bus_name}-{dev.devnum}"
        _devices[key] = dev
        self.dev_name = key
        log.info("Serial adapter created: %s", key)

    def write(self, data: bytes) -> int:
        """Write data to serial adapter."""
        log.info("Serial %s: write %d bytes", self.name, len(data))
        usb_bulk_msg(self.dev_name, 0x02, data)
        return len(data)

    def read(self, length: int = 64) -> bytes:
        """Read data from serial adapter."""
        data = bytes(self._rx_buffer[:length])
        self._rx_buffer = self._rx_buffer[length:]
        log.info("Serial %s: read %d bytes", self.name, len(data))
        usb_bulk_msg(self.dev_name, 0x82, data)
        return data

    def inject_data(self, data: bytes) -> None:
        """Inject data into receive buffer (for simulation)."""
        self._rx_buffer.extend(data)
        log.info("Serial %s: injected %d bytes", self.name, len(data))

    def set_baud(self, baud: int) -> None:
        """Set baud rate."""
        self._baud_rate = baud
        log.info("Serial %s: baud rate set to %d", self.name, baud)

    def __repr__(self) -> str:
        return f"SimUsbSerial(name={self.name!r}, baud={self._baud_rate}, dev={self.dev_name!r})"


# Include CDC_DATA class constant
USB_CLASS_CDC_DATA = 0x0A


# ===========================================================================
# Demo
# ===========================================================================

def _demo() -> None:
    """Comprehensive USB subsystem demo."""
    print("=" * 70)
    print("UmerOS USB Framework Demo")
    print("=" * 70)

    # --- HCD Registration ---
    print("\n--- Host Controller Drivers ---")
    ehci = usb_add_hcd("ehci.0", product_desc="Simulated EHCI HCD", speed="high", port_count=4)
    xhci = usb_add_hcd("xhci.0", product_desc="Simulated xHCI HCD", speed="super", port_count=10)
    ohci = usb_add_hcd("ohci.0", product_desc="Simulated OHCI HCD", speed="full", port_count=2)

    print(f"  EHCI: {ehci}")
    print(f"  xHCI: {xhci}")
    print(f"  OHCI: {ohci}")
    print(f"  Primary RH (ehci.0): {usb_hcd_is_primary_rh('ehci.0')}")
    print(f"  Primary RH (none.0): {usb_hcd_is_primary_rh('none.0')}")

    # --- Root Hub ---
    print("\n--- Root Hubs ---")
    rh = ehci.root_hub
    print(f"  Root hub: {rh}")
    for port in rh.ports:
        print(f"    Port {port.portnum}: connected={port.is_connected}, power={port.power}mA")

    # --- Connect Devices ---
    print("\n--- Connect Devices ---")
    kbd = SimUsbKeyboard("kbd1")
    mouse = SimUsbMouse("mouse1")
    storage = SimUsbMassStorage("usb-storage1", size_mb=2048)
    serial = SimUsbSerial("usb-serial1")

    print(f"  Keyboard: {kbd}")
    print(f"  Mouse: {mouse}")
    print(f"  Storage: {storage}")
    print(f"  Serial: {serial}")

    # --- Device Listing ---
    print("\n--- Device Listing ---")
    for dev in usb_list_devices():
        print(f"  {dev['name']}: {dev['manufacturer']} {dev['product']}")
        print(f"    Speed={dev['speed']}, Vendor={dev['vendor']}, Class={dev['class']}, "
              f"Configured={dev['configured']}")

    # --- Device Descriptor ---
    print("\n--- Device Descriptors ---")
    for dev in usb_list_devices():
        desc = usb_get_device_descriptor(dev['name'])
        if desc:
            print(f"  {dev['name']}:")
            print(f"    USB {desc['bcdUSB'] >> 8}.{desc['bcdUSB'] & 0xff}, "
                  f"Class=0x{desc['bDeviceClass']:02x}, "
                  f"Vendor=0x{desc['idVendor']:04x}, "
                  f"Product=0x{desc['idProduct']:04x}")

    # --- Configuration Descriptor ---
    print("\n--- Configuration Descriptors ---")
    for dev in usb_list_devices():
        cfg = usb_get_config_descriptor(dev['name'], 0)
        if cfg:
            print(f"  {dev['name']}: interfaces={cfg['bNumInterfaces']}, "
                  f"MaxPower={cfg['MaxPower']}mA")

    # --- String Descriptors ---
    print("\n--- String Descriptors ---")
    for dev in usb_list_devices():
        for sid in range(4):
            sdesc = usb_get_string_descriptor(dev['name'], sid)
            if sdesc and sdesc.string:
                print(f"  {dev['name']} string[{sid}]: {sdesc.string}")

    # --- Interface Claiming ---
    print("\n--- Interface Claiming ---")
    kbd_dev = kbd.dev_name
    print(f"  Device: {kbd_dev}")
    print(f"  Claim interface 0 with 'hid-driver': ", end="")
    print(usb_claim_interface(kbd_dev, 0, "hid-driver"))
    print(f"  Already claimed: ", end="")
    print(usb_interface_claimed(kbd_dev, 0))
    print(f"  Release interface 0: ", end="")
    print(usb_release_interface(kbd_dev, 0))
    print(f"  Claim interface 0 with 'usbhid': ", end="")
    print(usb_claim_interface(kbd_dev, 0, "usbhid"))

    # --- Interface Alternate Setting ---
    print("\n--- Interface Alternate Settings ---")
    print(f"  Current alt: {usb_get_interface(kbd_dev, 0)}")
    usb_set_interface(kbd_dev, 0, 1)
    print(f"  After set to 1: {usb_get_interface(kbd_dev, 0)}")
    usb_set_interface(kbd_dev, 0, 0)
    print(f"  After set back to 0: {usb_get_interface(kbd_dev, 0)}")

    # --- Endpoint Enable/Disable ---
    print("\n--- Endpoint Enable/Disable ---")
    ep = usb_ep_enable(0x81, 64, USB_ENDPOINT_XFER_INT, 10)
    print(f"  Enabled EP: addr=0x{ep.addr:02x}, type={ep.ep_type}, "
          f"direction={ep.direction}, maxpacket={ep.max_packet_size}")
    usb_ep_disable(0x81)
    print("  Disabled EP 0x81")

    # --- Control Transfers ---
    print("\n--- Control Transfers ---")
    for dev in usb_list_devices():
        ret = usb_control_msg(
            dev['name'],
            0x80,  # USB_DIR_IN | USB_TYPE_STANDARD | USB_RECIP_DEVICE
            USB_REQ_GET_DESCRIPTOR,
            (USB_DT_STRING << 8) | 2,
            0,
        )
        print(f"  {dev['name']}: GET_DESCRIPTOR(STRING) -> {ret} bytes")

        ret = usb_control_msg(
            dev['name'],
            0x00,  # USB_DIR_OUT
            USB_REQ_SET_CONFIGURATION,
            1,  # configuration value
            0,
        )
        print(f"  {dev['name']}: SET_CONFIGURATION(1) -> {ret}")

    # --- Bulk Transfers ---
    print("\n--- Bulk Transfers ---")
    stor_dev = storage.dev_name
    test_data = b'\xAA' * 512
    ret = usb_bulk_msg(stor_dev, 0x02, test_data)
    print(f"  Storage bulk write: {ret} bytes")
    ret = usb_bulk_msg(stor_dev, 0x81, b'\x00' * 512)
    print(f"  Storage bulk read: {ret} bytes")

    # --- Interrupt Transfers ---
    print("\n--- Interrupt Transfers ---")
    kbd_report = kbd.press_key(0x04)  # 'a' key
    print(f"  Keyboard HID report: {kbd_report.hex()}")
    kbd.release_key()
    print(f"  Keyboard key released")

    mouse_report = mouse.move(10, -5, buttons=1)
    print(f"  Mouse HID report: {mouse_report.hex()}")
    mouse.click(button=0)
    print(f"  Mouse clicked")

    # --- Isochronous Transfers ---
    print("\n--- Isochronous Transfers ---")
    ret = usb_iso_msg(kbd_dev, 0x81, b'\x00' * 1024)
    print(f"  Iso transfer: {ret} bytes")

    # --- Mass Storage Sectors ---
    print("\n--- Mass Storage Sector I/O ---")
    storage.write_sectors(0, b'\x00' * 512)
    data = storage.read_sectors(0, 1)
    print(f"  Storage capacity: {storage.capacity_bytes()} bytes")
    print(f"  Read sector 0: {len(data)} bytes")

    # --- Serial Adapter ---
    print("\n--- Serial Adapter ---")
    serial.set_baud(115200)
    serial.write(b'AT\r\n')
    serial.inject_data(b'OK\r\n')
    response = serial.read(16)
    print(f"  Serial response: {response}")

    # --- External Hubs ---
    print("\n--- External Hubs ---")
    hub1 = SimExternalHub("hub1", n_ports=4, parent_hub="ehci.0")
    print(f"  Hub: {hub1}")

    usb_hub_port_connect("hub1", 1, speed="high")
    usb_hub_port_connect("hub1", 2, speed="full")
    usb_hub_port_connect("hub1", 3, speed="low")

    for port_num in range(1, 5):
        status = usb_hub_get_port_status("hub1", port_num)
        if status:
            print(f"  Port {port_num}: connected={status['connected']}, "
                  f"speed={status['speed']}, enabled={status['enabled']}")

    # --- Hub Port Reset ---
    print("\n--- Hub Port Operations ---")
    usb_hub_port_reset("hub1", 1)
    print(f"  Port 1 reset count: "
          f"{usb_hub_get_port_status('hub1', 1)['reset_count']}")

    usb_hub_set_port_power("hub1", 4, on=True)
    print(f"  Port 4 power status: {usb_hub_get_port_status('hub1', 4)['power']}mA")

    usb_hub_set_port_power("hub1", 4, on=False)
    print(f"  Port 4 power off: {usb_hub_get_port_status('hub1', 4)['power']}mA")

    # --- Suspend/Resume ---
    print("\n--- Suspend / Resume ---")
    target_dev = kbd_dev
    print(f"  Device: {target_dev}")
    print(f"  Before suspend: active={_devices[target_dev].is_active}, "
          f"suspended={_devices[target_dev].is_suspended}")
    usb_suspend(target_dev)
    print(f"  After suspend: active={_devices[target_dev].is_active}, "
          f"suspended={_devices[target_dev].is_suspended}")
    usb_resume(target_dev)
    print(f"  After resume: active={_devices[target_dev].is_active}, "
          f"suspended={_devices[target_dev].is_suspended}")

    # --- Device Reset ---
    print("\n--- Device Reset ---")
    usb_claim_interface(kbd_dev, 0, "usbhid")
    print(f"  Interface 0 before reset: driver={_devices[kbd_dev]._interfaces[0].driver}")
    usb_reset_device(kbd_dev)
    print(f"  Interface 0 after reset: driver={_devices[kbd_dev]._interfaces[0].driver}")
    print(f"  Configured after reset: {_devices[kbd_dev].is_configured}")
    print(f"  Active after reset: {_devices[kbd_dev].is_active}")

    # --- Device Removal ---
    print("\n--- Device Removal ---")
    print(f"  Storage dev: {storage.dev_name}")
    result = usb_put_dev(storage.dev_name)
    print(f"  usb_put_dev: {result}")
    print(f"  In registry: {storage.dev_name in _devices}")

    # --- HCD Listing ---
    print("\n--- HCD Listing ---")
    for hcd in usb_list_hcds():
        print(f"  {hcd['name']}: {hcd['product']}, "
              f"speed={hcd['speed']}, ports={hcd['ports']}, "
              f"registered={hcd['registered']}")

    # --- Final Device Listing ---
    print("\n--- Final Device Listing ---")
    for dev in usb_list_devices():
        print(f"  {dev['name']}: {dev['manufacturer']} {dev['product']} "
              f"[{dev['speed']}] connected={dev['configured']}")

    # --- HCD Removal ---
    print("\n--- HCD Removal ---")
    usb_remove_hcd("ohci.0")
    print(f"  Removed ohci.0, remaining: {[h['name'] for h in usb_list_hcds()]}")

    # --- Hub Unregister ---
    print("\n--- Hub Unregister ---")
    usb_hub_unregister("hub1")
    print(f"  Unregistered hub1")

    print("\n" + "=" * 70)
    print("USB Framework demo complete")
    print("=" * 70)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    _demo()
