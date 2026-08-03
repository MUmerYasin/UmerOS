"""
UmerOS PCI Subsystem
====================
Linux kernel PCI bus infrastructure.
Implements PCI devices, BARs, config space, drivers, MSI/MSI-X,
bridges, DMA masks, and simulated devices (IDE, NIC, VGA, USB, SATA, NVMe).
"""

from __future__ import annotations

import copy
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PCI Register Offsets (Linux kernel pci_regs.h)
# ---------------------------------------------------------------------------
PCI_VENDOR_ID = 0x00
PCI_DEVICE_ID = 0x02
PCI_COMMAND = 0x04
PCI_STATUS = 0x06
PCI_CLASS_REVISION = 0x08
PCI_CACHE_LINE_SIZE = 0x0C
PCI_LATENCY_TIMER = 0x0D
PCI_HEADER_TYPE = 0x0E
PCI_BIST = 0x0F
PCI_BASE_ADDRESS_0 = 0x10
PCI_BASE_ADDRESS_1 = 0x14
PCI_BASE_ADDRESS_2 = 0x18
PCI_BASE_ADDRESS_3 = 0x1C
PCI_BASE_ADDRESS_4 = 0x20
PCI_BASE_ADDRESS_5 = 0x24
PCI_SUBVENDOR_ID = 0x2C
PCI_SUBDEVICE_ID = 0x2E
PCI_INTERRUPT_LINE = 0x3C
PCI_INTERRUPT_PIN = 0x3D
PCI_MIN_GNT = 0x3E
PCI_MAX_LAT = 0x3F

# ---------------------------------------------------------------------------
# PCI Command Register Bits
# ---------------------------------------------------------------------------
PCI_COMMAND_IO_SPACE = 0x0001
PCI_COMMAND_MEMORY_SPACE = 0x0002
PCI_COMMAND_BUS_MASTER = 0x0004
PCI_COMMAND_INTX_DISABLE = 0x0400

# ---------------------------------------------------------------------------
# PCI Status Register Bits
# ---------------------------------------------------------------------------
PCI_STATUS_CAP_LIST = 0x0010
PCI_STATUS_66MHZ = 0x0020
PCI_STATUS_FAST_BACK_CAPABLE = 0x0080
PCI_STATUS_DEVSEL_MASK = 0x0600

# ---------------------------------------------------------------------------
# PCI Header Types
# ---------------------------------------------------------------------------
PCI_HEADER_TYPE_NORMAL = 0
PCI_HEADER_TYPE_BRIDGE = 1
PCI_HEADER_TYPE_CARDBUS = 2

# ---------------------------------------------------------------------------
# PCI I/O Resource Flags
# ---------------------------------------------------------------------------
PCI_IORESOURCE_IO = 0x00000100
PCI_IORESOURCE_MEM = 0x00000200
PCI_IORESOURCE_MEM_64 = 0x00000400
PCI_IORESOURCE_PREFETCH = 0x00000800
PCI_IORESOURCE_READONLY = 0x00001000
PCI_IORESOURCE_CACHEABLE = 0x00002000
PCI_IORESOURCE_UNCACHEABLE = 0x00004000
PCI_IORESOURCE_STARTALIGN = 0x00100000

# ---------------------------------------------------------------------------
# PCI Class Codes
# ---------------------------------------------------------------------------
PCI_CLASS_STORAGE_SATA = 0x010600
PCI_CLASS_NETWORK_ETHERNET = 0x020000
PCI_CLASS_DISPLAY_VGA = 0x030000
PCI_CLASS_BRIDGE_PCI = 0x060400
PCI_CLASS_SERIAL_USB = 0x0C0300
PCI_CLASS_MULTIPROCESSOR = 0x0F0100
PCI_CLASS_MEMORY_RAM = 0x050000
PCI_CLASS_SERIAL_SCSI = 0x010700

# ---------------------------------------------------------------------------
# PCI Capability IDs
# ---------------------------------------------------------------------------
PCI_CAP_ID_PM = 0x01
PCI_CAP_ID_VPD = 0x03
PCI_CAP_ID_MSI = 0x05
PCI_CAP_ID_EXP = 0x10
PCI_CAP_ID_MSIX = 0x11

# ---------------------------------------------------------------------------
# MSI/MSI-X Flags
# ---------------------------------------------------------------------------
MSI_FLAG_ENABLE = 0x01
MSIX_FLAG_ENABLE = 0x02

# ---------------------------------------------------------------------------
# PCIe Reset States
# ---------------------------------------------------------------------------
PCI_RESET_FUNCTION = 0
PCI_RESET_hot = 1
PCI_RESET_warm = 2
PCI_RESET_cold = 3

# ---------------------------------------------------------------------------
# Well-known Vendor/Device IDs
# ---------------------------------------------------------------------------
VENDOR_INTEL = 0x8086
VENDOR_AMD = 0x1022
VENDOR_NVIDIA = 0x10DE
VENDOR_REALTEK = 0x10EC
VENDOR_BROADCOM = 0x14E4
VENDOR_VMWARE = 0x15AD
VENDOR_QEMU = 0x1234

DEVICE_E1000 = 0x100E
DEVICE_VGA = 0x1234
DEVICE_SATA_AHCI = 0x2922
DEVICE_USB_EHCI = 0x293A
DEVICE_USB_XHCI = 0x31D6
DEVICE_NVME = 0x5845
DEVICE_IDE = 0x7010
DEVICE_PCI_BRIDGE = 0x2400

# ---------------------------------------------------------------------------
# PCI Class Name Lookup
# ---------------------------------------------------------------------------
_PCI_CLASS_NAMES: Dict[int, str] = {
    0x000000: "Legacy Device",
    0x000100: "VGA-Compatible Device",
    0x010000: "SCSI Controller",
    0x010100: "IDE Controller",
    0x010600: "SATA AHCI Controller",
    0x010700: "SCSI Storage Controller",
    0x010800: "NVMe Controller",
    0x011000: "RAID Controller",
    0x020000: "Ethernet Controller",
    0x020100: "Token Ring Controller",
    0x030000: "VGA Controller",
    0x030001: "XGA Controller",
    0x030100: "3D Controller",
    0x040000: "Multimedia Video Controller",
    0x040100: "Multimedia Audio Controller",
    0x050000: "RAM Memory",
    0x060000: "Host Bridge",
    0x060100: "ISA Bridge",
    0x060200: "EISA Bridge",
    0x060300: "PCI-to-PCI Bridge",
    0x060400: "PCI-to-PCI Bridge (Subtractive Decode)",
    0x070000: "Serial Controller",
    0x070100: "Parallel Controller",
    0x080000: "PIC (8259)",
    0x080100: "DMA Controller",
    0x080200: "Timer (8254)",
    0x080300: "RTC Controller",
    0x090000: "Keyboard Controller",
    0x090100: "Digitizer (Pen)",
    0x090200: "Mouse Controller",
    0x0C0000: "FireWire (IEEE 1394) Controller",
    0x0C0100: "Access Bus Controller",
    0x0C0300: "USB Controller (UHCI)",
    0x0C0310: "USB Controller (OHCI)",
    0x0C0320: "USB Controller (EHCI)",
    0x0C0330: "USB Controller (xHCI)",
    0x0D0000: "Bluetooth Controller",
    0x0E0000: "Infiniband Controller",
    0x0F0100: "Multiprocessor Controller",
    0x100000: "Fibre Channel Controller",
    0x110000: "Encryption Controller",
    0xFF0000: "Unassigned Class",
}


# ============================================================================
# Dataclasses
# ============================================================================

@dataclass
class PciBar:
    """PCI Base Address Register."""
    bar_num: int
    bar_type: str  # "io" or "mem"
    base_addr: int = 0
    size: int = 0
    is_prefetchable: bool = False
    is_64bit: bool = False
    is_allocated: bool = False


@dataclass
class PciResource:
    """PCI resource (BAR)."""
    start: int
    end: int
    flags: int = 0
    name: str = ""


@dataclass
class PciDeviceId:
    """PCI device ID entry."""
    vendor: int
    device: int
    subvendor: int = 0
    subdevice: int = 0
    class_code: int = 0
    class_mask: int = 0
    driver_data: Any = None


@dataclass
class PciDev:
    """PCI device."""
    name: str
    bus: int
    devfn: int  # (device << 3) | function
    vendor: int
    device_id: int
    revision: int = 0
    class_code: int = 0
    subclass: int = 0
    prog_if: int = 0
    header_type: int = 0
    pci_irq: int = -1
    pci_dma: str = "dma_mask_width=64"
    rom_base: int = 0
    rom_size: int = 0
    is_enabled: bool = False
    is_master: bool = False
    is_bridge: bool = False
    is_virtfn: bool = False
    is_physfn: bool = False
    is_online: bool = True
    msi_enabled: bool = False
    msix_enabled: bool = False
    _bars: List[PciBar] = field(default_factory=list)
    _mmio: Dict[int, int] = field(default_factory=dict)  # bar_num -> mapped address
    _resources: List[PciResource] = field(default_factory=list)
    _config_space: Dict[int, int] = field(default_factory=dict)
    _saved_state: Optional[Dict[int, int]] = None
    _ref_count: int = 1
    _regions_requested: set = field(default_factory=set)
    _dma_mask: int = 0xFFFFFFFFFFFFFFFF  # 64-bit default
    _consistent_dma_mask: int = 0xFFFFFFFFFFFFFFFF
    _msi_vectors: int = 0
    _msix_vectors: int = 0
    _sub_vendor: int = 0
    _sub_device: int = 0

    def __post_init__(self) -> None:
        device = (self.devfn >> 3) & 0x1F
        function = self.devfn & 0x07
        if not self.name:
            self.name = f"pci{self.bus:04x}:{device:02x}.{function}"
        self._init_config_space()

    def _init_config_space(self) -> None:
        self._config_space = {
            PCI_VENDOR_ID: self.vendor & 0xFFFF,
            PCI_DEVICE_ID: self.device_id & 0xFFFF,
            PCI_COMMAND: 0x0000,
            PCI_STATUS: 0x0000,
            PCI_CLASS_REVISION: ((self.class_code & 0xFF) << 16)
            | ((self.subclass & 0xFF) << 8)
            | (self.revision & 0xFF),
            PCI_CACHE_LINE_SIZE: 0x00,
            PCI_LATENCY_TIMER: 0x00,
            PCI_HEADER_TYPE: self.header_type & 0xFF,
            PCI_BIST: 0x00,
            PCI_BASE_ADDRESS_0: 0x00000000,
            PCI_BASE_ADDRESS_1: 0x00000000,
            PCI_BASE_ADDRESS_2: 0x00000000,
            PCI_BASE_ADDRESS_3: 0x00000000,
            PCI_BASE_ADDRESS_4: 0x00000000,
            PCI_BASE_ADDRESS_5: 0x00000000,
            PCI_SUBVENDOR_ID: (self._sub_vendor & 0xFFFF)
            | ((self._sub_device & 0xFFFF) << 16),
            PCI_INTERRUPT_LINE: self.pci_irq & 0xFF,
            PCI_INTERRUPT_PIN: 0x01 if self.pci_irq >= 0 else 0x00,
            PCI_MIN_GNT: 0x00,
            PCI_MAX_LAT: 0x00,
        }

    # --- Device property helpers ---

    @property
    def device_num(self) -> int:
        return (self.devfn >> 3) & 0x1F

    @property
    def function_num(self) -> int:
        return self.devfn & 0x07

    @property
    def full_class(self) -> int:
        return ((self.class_code & 0xFF) << 16) | (
            (self.subclass & 0xFF) << 8
        ) | (self.prog_if & 0xFF)

    @property
    def pci_name(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return (
            f"PciDev({self.name} vendor=0x{self.vendor:04X} "
            f"device=0x{self.device_id:04X} "
            f"class=0x{self.full_class:06X})"
        )


@dataclass
class PciDriver:
    """PCI device driver."""
    name: str
    probe: Optional[Callable] = None
    remove: Optional[Callable] = None
    suspend: Optional[Callable] = None
    resume: Optional[Callable] = None
    shutdown: Optional[Callable] = None
    err_handler: Optional[Callable] = None
    id_table: List[PciDeviceId] = field(default_factory=list)
    is_registered: bool = False

    def __repr__(self) -> str:
        return f"PciDriver({self.name} registered={self.is_registered})"


@dataclass
class PciBus:
    """PCI bus."""
    number: int
    name: str = ""
    parent: Optional[PciBus] = None
    children: List[PciBus] = field(default_factory=list)
    devices: List[PciDev] = field(default_factory=list)
    is_root: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"pci{self.number}"


# ============================================================================
# Global Registries
# ============================================================================

_devices: Dict[str, PciDev] = {}
_buses: Dict[int, PciBus] = {}
_drivers: Dict[str, PciDriver] = {}
_next_irq: int = 16  # Simulated IRQ allocation starting at 16
_next_mmio: int = 0xFE000000  # Simulated MMIO base for BAR mappings


# ============================================================================
# Internal Helpers
# ============================================================================

def _alloc_irq() -> int:
    global _next_irq
    irq = _next_irq
    _next_irq += 1
    return irq


def _alloc_mmio(size: int) -> int:
    global _next_mmio
    # Align up to page boundary (4K)
    size = (size + 0xFFF) & ~0xFFF
    base = _next_mmio
    _next_mmio += size
    return base


def _bar_offset(bar_num: int) -> int:
    return PCI_BASE_ADDRESS_0 + bar_num * 4


def _class_name(class_code: int) -> str:
    if class_code in _PCI_CLASS_NAMES:
        return _PCI_CLASS_NAMES[class_code]
    major = (class_code >> 16) & 0xFF
    names = {
        0: "Legacy", 1: "Mass Storage", 2: "Network",
        3: "Display", 4: "Multimedia", 5: "Memory",
        6: "Bridge", 7: "Communication", 8: "System",
        9: "Input", 10: "Docking", 11: "Processor",
        12: "Serial Bus", 13: "Wireless", 14: "Intelligent I/O",
        15: "Satellite", 16: "Cryptographic", 17: "Signal Processing",
    }
    return names.get(major, f"Unknown(0x{major:02X})")


# ============================================================================
# PCI Device Functions (Kernel API)
# ============================================================================

def pci_get_device(vendor_id: int, device_id: Optional[int] = None) -> Optional[PciDev]:
    """Find PCI device by vendor/device ID."""
    for dev in _devices.values():
        if dev.vendor == vendor_id:
            if device_id is None or dev.device_id == device_id:
                return dev
    return None


def pci_get_slot(bus: int, devfn: int) -> Optional[PciDev]:
    """Get PCI device by bus/devfn."""
    for dev in _devices.values():
        if dev.bus == bus and dev.devfn == devfn:
            return dev
    return None


def pci_dev_get(dev_name: str) -> Optional[PciDev]:
    """Increment PCI device reference count."""
    dev = _devices.get(dev_name)
    if dev:
        dev._ref_count += 1
        log.debug("pci_dev_get: %s ref_count=%d", dev_name, dev._ref_count)
    return dev


def pci_dev_put(dev_name: str) -> None:
    """Decrement PCI device reference count."""
    dev = _devices.get(dev_name)
    if dev:
        dev._ref_count -= 1
        log.debug("pci_dev_put: %s ref_count=%d", dev_name, dev._ref_count)
        if dev._ref_count <= 0:
            log.info("pci_dev_put: %s refcount reached zero", dev_name)


# ---------------------------------------------------------------------------
# Enable / Disable
# ---------------------------------------------------------------------------

def pci_enable_device(dev_name: str) -> int:
    """Enable PCI device - sets MEMORY_SPACE | IO_SPACE."""
    dev = _devices.get(dev_name)
    if not dev:
        log.error("pci_enable_device: device %s not found", dev_name)
        return -1
    if dev.is_enabled:
        log.debug("pci_enable_device: %s already enabled", dev_name)
        return 0
    dev.is_enabled = True
    cmd = dev._config_space.get(PCI_COMMAND, 0)
    cmd |= PCI_COMMAND_IO_SPACE | PCI_COMMAND_MEMORY_SPACE
    dev._config_space[PCI_COMMAND] = cmd
    log.info("pci_enable_device: %s enabled", dev_name)
    return 0


def pci_disable_device(dev_name: str) -> int:
    """Disable PCI device."""
    dev = _devices.get(dev_name)
    if not dev:
        log.error("pci_disable_device: device %s not found", dev_name)
        return -1
    if not dev.is_enabled:
        return 0
    dev.is_enabled = False
    cmd = dev._config_space.get(PCI_COMMAND, 0)
    cmd &= ~(PCI_COMMAND_IO_SPACE | PCI_COMMAND_MEMORY_SPACE)
    dev._config_space[PCI_COMMAND] = cmd
    log.info("pci_disable_device: %s disabled", dev_name)
    return 0


def pci_set_master(dev_name: str) -> int:
    """Set bus master bit."""
    dev = _devices.get(dev_name)
    if not dev:
        return -1
    dev.is_master = True
    cmd = dev._config_space.get(PCI_COMMAND, 0)
    cmd |= PCI_COMMAND_BUS_MASTER
    dev._config_space[PCI_COMMAND] = cmd
    log.info("pci_set_master: %s bus master enabled", dev_name)
    return 0


def pci_clear_master(dev_name: str) -> int:
    """Clear bus master bit."""
    dev = _devices.get(dev_name)
    if not dev:
        return -1
    dev.is_master = False
    cmd = dev._config_space.get(PCI_COMMAND, 0)
    cmd &= ~PCI_COMMAND_BUS_MASTER
    dev._config_space[PCI_COMMAND] = cmd
    log.info("pci_clear_master: %s bus master cleared", dev_name)
    return 0


# ---------------------------------------------------------------------------
# BAR / Resource Functions
# ---------------------------------------------------------------------------

def pci_resource_start(dev_name: str, bar_num: int) -> int:
    """Get BAR start address."""
    dev = _devices.get(dev_name)
    if not dev:
        return 0
    if 0 <= bar_num < len(dev._bars):
        return dev._bars[bar_num].base_addr
    return 0


def pci_resource_len(dev_name: str, bar_num: int) -> int:
    """Get BAR length."""
    dev = _devices.get(dev_name)
    if not dev:
        return 0
    if 0 <= bar_num < len(dev._bars):
        return dev._bars[bar_num].size
    return 0


def pci_resource_flags(dev_name: str, bar_num: int) -> int:
    """Get BAR flags."""
    dev = _devices.get(dev_name)
    if not dev:
        return 0
    if 0 <= bar_num < len(dev._bars):
        bar = dev._bars[bar_num]
        flags = 0
        if bar.bar_type == "io":
            flags |= PCI_IORESOURCE_IO
        elif bar.bar_type == "mem":
            flags |= PCI_IORESOURCE_MEM
            if bar.is_64bit:
                flags |= PCI_IORESOURCE_MEM_64
            if bar.is_prefetchable:
                flags |= PCI_IORESOURCE_PREFETCH
        return flags
    return 0


def pci_request_region(dev_name: str, bar_num: int, name: str = "") -> int:
    """Request PCI region."""
    dev = _devices.get(dev_name)
    if not dev:
        return -1
    if bar_num in dev._regions_requested:
        log.warning("pci_request_region: %s BAR%d already requested", dev_name, bar_num)
        return -1
    if bar_num < 0 or bar_num >= len(dev._bars):
        return -1
    bar = dev._bars[bar_num]
    bar.is_allocated = True
    dev._regions_requested.add(bar_num)
    resource = PciResource(
        start=bar.base_addr,
        end=bar.base_addr + bar.size - 1,
        flags=pci_resource_flags(dev_name, bar_num),
        name=name or dev_name,
    )
    dev._resources.append(resource)
    log.info(
        "pci_request_region: %s BAR%d [0x%X-0x%X] %s",
        dev_name, bar_num, resource.start, resource.end, name,
    )
    return 0


def pci_release_region(dev_name: str, bar_num: int) -> None:
    """Release PCI region."""
    dev = _devices.get(dev_name)
    if not dev:
        return
    dev._regions_requested.discard(bar_num)
    if bar_num < len(dev._bars):
        dev._bars[bar_num].is_allocated = False
    dev._resources = [r for r in dev._resources if r.name != dev_name]
    log.info("pci_release_region: %s BAR%d released", dev_name, bar_num)


def pci_request_regions(dev_name: str, name: str = "") -> int:
    """Request all regions."""
    dev = _devices.get(dev_name)
    if not dev:
        return -1
    for i, bar in enumerate(dev._bars):
        if bar.size > 0:
            rc = pci_request_region(dev_name, i, name=name)
            if rc != 0:
                pci_release_regions(dev_name)
                return rc
    log.info("pci_request_regions: %s all regions requested", dev_name)
    return 0


def pci_release_regions(dev_name: str) -> None:
    """Release all regions."""
    dev = _devices.get(dev_name)
    if not dev:
        return
    for bar_num in list(dev._regions_requested):
        pci_release_region(dev_name, bar_num)
    log.info("pci_release_regions: %s all regions released", dev_name)


# ---------------------------------------------------------------------------
# MMIO Mapping
# ---------------------------------------------------------------------------

def pci_ioremap_bar(dev_name: str, bar_num: int) -> int:
    """Map BAR into virtual address space."""
    dev = _devices.get(dev_name)
    if not dev:
        return 0
    if bar_num < 0 or bar_num >= len(dev._bars):
        return 0
    bar = dev._bars[bar_num]
    if bar.size == 0:
        log.error("pci_ioremap_bar: %s BAR%d has zero size", dev_name, bar_num)
        return 0
    vaddr = _alloc_mmio(bar.size)
    dev._mmio[bar_num] = vaddr
    log.info(
        "pci_ioremap_bar: %s BAR%d mapped 0x%X -> 0x%X (size=0x%X)",
        dev_name, bar_num, bar.base_addr, vaddr, bar.size,
    )
    return vaddr


def pci_iounmap(dev_name: str, bar_num: int) -> None:
    """Unmap BAR."""
    dev = _devices.get(dev_name)
    if not dev:
        return
    vaddr = dev._mmio.pop(bar_num, 0)
    log.info("pci_iounmap: %s BAR%d unmapped 0x%X", dev_name, bar_num, vaddr)


# ---------------------------------------------------------------------------
# Config Space
# ---------------------------------------------------------------------------

def pci_read_config_byte(dev_name: str, where: int) -> int:
    """Read config byte."""
    dev = _devices.get(dev_name)
    if not dev:
        return 0xFF
    val = dev._config_space.get(where, 0)
    return val & 0xFF


def pci_write_config_byte(dev_name: str, where: int, value: int) -> None:
    """Write config byte."""
    dev = _devices.get(dev_name)
    if not dev:
        return
    dev._config_space[where] = value & 0xFF


def pci_save_state(dev_name: str) -> None:
    """Save PCI config state."""
    dev = _devices.get(dev_name)
    if not dev:
        return
    dev._saved_state = copy.deepcopy(dev._config_space)
    log.info("pci_save_state: %s saved (%d registers)", dev_name, len(dev._saved_state))


def pci_restore_state(dev_name: str) -> None:
    """Restore PCI config state."""
    dev = _devices.get(dev_name)
    if not dev:
        return
    if dev._saved_state is None:
        log.warning("pci_restore_state: %s no saved state", dev_name)
        return
    dev._config_space = copy.deepcopy(dev._saved_state)
    log.info("pci_restore_state: %s restored", dev_name)


# ---------------------------------------------------------------------------
# DMA
# ---------------------------------------------------------------------------

def pci_set_dma_mask(dev_name: str, mask: int) -> int:
    """Set DMA mask."""
    dev = _devices.get(dev_name)
    if not dev:
        return -1
    if mask & (mask + 1) != 0 and mask != 0:
        log.error("pci_set_dma_mask: %s invalid mask 0x%X", dev_name, mask)
        return -1
    dev._dma_mask = mask
    dev.pci_dma = f"dma_mask_width={mask.bit_length() - 1}"
    log.info("pci_set_dma_mask: %s mask=0x%X", dev_name, mask)
    return 0


def pci_set_consistent_dma_mask(dev_name: str, mask: int) -> int:
    """Set consistent DMA mask."""
    dev = _devices.get(dev_name)
    if not dev:
        return -1
    dev._consistent_dma_mask = mask
    log.info("pci_set_consistent_dma_mask: %s mask=0x%X", dev_name, mask)
    return 0


# ---------------------------------------------------------------------------
# MSI / MSI-X
# ---------------------------------------------------------------------------

def pci_alloc_irq_vectors(
    dev_name: str, min_vectors: int, max_vectors: int, flags: int
) -> int:
    """Allocate MSI/MSI-X vectors. Returns actual count allocated."""
    dev = _devices.get(dev_name)
    if not dev:
        return -1
    if max_vectors <= 0 or min_vectors <= 0:
        return -1

    use_msix = bool(flags & MSIX_FLAG_ENABLE)
    use_msi = bool(flags & MSI_FLAG_ENABLE)

    if use_msix:
        count = min(max_vectors, 32)  # Max 32 MSI-X vectors
        dev.msix_enabled = True
        dev.msi_enabled = False
        dev._msix_vectors = count
        log.info(
            "pci_alloc_irq_vectors: %s allocated %d MSI-X vectors", dev_name, count,
        )
    elif use_msi:
        count = min(max_vectors, 32)  # Max 32 MSI vectors
        dev.msi_enabled = True
        dev.msix_enabled = False
        dev._msi_vectors = count
        log.info(
            "pci_alloc_irq_vectors: %s allocated %d MSI vectors", dev_name, count,
        )
    else:
        # Legacy INTx
        count = 1
        log.info("pci_alloc_irq_vectors: %s using legacy INTx", dev_name)

    # Allocate IRQ for the first vector
    if dev.pci_irq < 0:
        dev.pci_irq = _alloc_irq()
        dev._config_space[PCI_INTERRUPT_LINE] = dev.pci_irq & 0xFF

    return count


def pci_free_irq_vectors(dev_name: str) -> None:
    """Free MSI/MSI-X vectors."""
    dev = _devices.get(dev_name)
    if not dev:
        return
    dev.msi_enabled = False
    dev.msix_enabled = False
    dev._msi_vectors = 0
    dev._msix_vectors = 0
    log.info("pci_free_irq_vectors: %s vectors freed", dev_name)


def pci_irq_vector(dev_name: str, index: int = 0) -> int:
    """Get IRQ number for vector."""
    dev = _devices.get(dev_name)
    if not dev:
        return -1
    if dev.msi_enabled:
        if index < dev._msi_vectors:
            return dev.pci_irq + index
        return -1
    if dev.msix_enabled:
        if index < dev._msix_vectors:
            return dev.pci_irq + index
        return -1
    return dev.pci_irq


def pci_msix_enable(dev_name: str) -> int:
    """Enable MSI-X."""
    dev = _devices.get(dev_name)
    if not dev:
        return -1
    dev.msix_enabled = True
    if dev.pci_irq < 0:
        dev.pci_irq = _alloc_irq()
        dev._config_space[PCI_INTERRUPT_LINE] = dev.pci_irq & 0xFF
    log.info("pci_msix_enable: %s MSI-X enabled irq=%d", dev_name, dev.pci_irq)
    return 0


def pci_msi_enable(dev_name: str) -> int:
    """Enable MSI."""
    dev = _devices.get(dev_name)
    if not dev:
        return -1
    dev.msi_enabled = True
    if dev.pci_irq < 0:
        dev.pci_irq = _alloc_irq()
        dev._config_space[PCI_INTERRUPT_LINE] = dev.pci_irq & 0xFF
    log.info("pci_msi_enable: %s MSI enabled irq=%d", dev_name, dev.pci_irq)
    return 0


# ---------------------------------------------------------------------------
# Error Handling / Status
# ---------------------------------------------------------------------------

def pci_set_pcie_reset_state(dev_name: str, state: int) -> None:
    """Set PCIe reset state."""
    log.info(
        "pci_set_pcie_reset_state: %s state=%d (%s)",
        dev_name,
        state,
        {0: "FUNCTION", 1: "HOT", 2: "WARM", 3: "COLD"}.get(state, "UNKNOWN"),
    )


def pci_dev_set_status(dev_name: str, status: int) -> None:
    """Set device status register."""
    dev = _devices.get(dev_name)
    if not dev:
        return
    dev._config_space[PCI_STATUS] = status
    log.info("pci_dev_set_status: %s status=0x%04X", dev_name, status)


# ---------------------------------------------------------------------------
# Driver Registration
# ---------------------------------------------------------------------------

def pci_register_driver(driver_name: str) -> int:
    """Register PCI driver."""
    if driver_name not in _drivers:
        log.error("pci_register_driver: driver %s not found", driver_name)
        return -1
    drv = _drivers[driver_name]
    drv.is_registered = True
    log.info("pci_register_driver: %s registered (%d ids)", driver_name, len(drv.id_table))
    return 0


def pci_unregister_driver(driver_name: str) -> None:
    """Unregister PCI driver."""
    drv = _drivers.get(driver_name)
    if drv:
        drv.is_registered = False
        log.info("pci_unregister_driver: %s unregistered", driver_name)


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------

def pci_bus_get_bridgedev(bus_number: int) -> Optional[PciDev]:
    """Get bridge device for bus."""
    bus = _buses.get(bus_number)
    if not bus or not bus.parent:
        return None
    for dev in bus.parent.devices:
        if dev.is_bridge:
            return dev
    return None


# ---------------------------------------------------------------------------
# Info / Listing
# ---------------------------------------------------------------------------

def pci_info(dev_name: str) -> str:
    """Get device info string."""
    dev = _devices.get(dev_name)
    if not dev:
        return f"PCI device {dev_name} not found"
    device = (dev.devfn >> 3) & 0x1F
    func = dev.devfn & 0x07
    class_str = pci_class_string(dev.full_class)
    bars_info = []
    for i, bar in enumerate(dev._bars):
        if bar.size > 0:
            bars_info.append(
                f"  BAR{i}: {bar.bar_type} base=0x{bar.base_addr:08X} "
                f"size=0x{bar.size:X} 64bit={bar.is_64bit} "
                f"prefetch={bar.is_prefetchable}"
            )
    lines = [
        f"PCI Device: {dev.name}",
        f"  Location:   {dev.bus:04X}:{device:02X}.{func}",
        f"  Vendor:     0x{dev.vendor:04X}",
        f"  Device:     0x{dev.device_id:04X}",
        f"  Revision:   0x{dev.revision:02X}",
        f"  Class:      {class_str} (0x{dev.full_class:06X})",
        f"  Header:     0x{dev.header_type:02X}",
        f"  IRQ:        {dev.pci_irq}",
        f"  Enabled:    {dev.is_enabled}",
        f"  Master:     {dev.is_master}",
        f"  MSI:        {dev.msi_enabled}",
        f"  MSI-X:      {dev.msix_enabled}",
        f"  DMA Mask:   0x{dev._dma_mask:X}",
        f"  Ref Count:  {dev._ref_count}",
    ]
    if bars_info:
        lines.append("  BARs:")
        lines.extend(bars_info)
    if dev._mmio:
        mmio_lines = [f"    BAR{i} -> 0x{v:08X}" for i, v in dev._mmio.items()]
        lines.append("  MMIO Mappings:")
        lines.extend(mmio_lines)
    return "\n".join(lines)


def pci_name(dev_name: str) -> str:
    """Get device name."""
    dev = _devices.get(dev_name)
    return dev.name if dev else ""


def pci_class_string(class_code: int) -> str:
    """Get class name string."""
    return _class_name(class_code)


def pci_list_devices() -> List[str]:
    """List all PCI devices. Returns list of device names."""
    names = sorted(_devices.keys())
    return names


def pci_list_drivers() -> List[str]:
    """List registered PCI drivers."""
    return [n for n, d in _drivers.items() if d.is_registered]


def pci_find_bus(domain: int, busnum: int) -> Optional[PciBus]:
    """Find PCI bus."""
    return _buses.get(busnum)


# ============================================================================
# Built-in Device Simulation Classes
# ============================================================================

class PciIdeController:
    """Simulated PCI IDE controller."""

    def __init__(self, bus: int = 0, devfn: int = 0) -> None:
        device_num = (devfn >> 3) & 0x1F
        func = devfn & 0x07
        name = f"pci{bus:04x}:{device_num:02x}.{func}"
        self.name = name
        dev = PciDev(
            name=name,
            bus=bus,
            devfn=devfn,
            vendor=VENDOR_INTEL,
            device_id=DEVICE_IDE,
            revision=0x03,
            class_code=0x01,
            subclass=0x01,
            prog_if=0x80,
            header_type=PCI_HEADER_TYPE_NORMAL,
            pci_irq=_alloc_irq(),
        )
        dev._sub_vendor = VENDOR_INTEL
        dev._sub_device = 0x0000
        dev._bars = [
            PciBar(bar_num=0, bar_type="io", base_addr=0x1F0, size=8),
            PciBar(bar_num=1, bar_type="io", base_addr=0x3F6, size=1),
            PciBar(bar_num=2, bar_type="io", base_addr=0x170, size=8),
            PciBar(bar_num=3, bar_type="io", base_addr=0x376, size=1),
            PciBar(bar_num=4, bar_type="io", base_addr=0xCC00, size=16),
            PciBar(bar_num=5, bar_type="mem", base_addr=0, size=0),
        ]
        dev._init_config_space()
        _devices[name] = dev

        bus_obj = _buses.setdefault(bus, PciBus(number=bus))
        bus_obj.devices.append(dev)
        log.info("PciIdeController created: %s", name)


class PciNetworkCard:
    """Simulated PCI network card (e1000)."""

    def __init__(self, bus: int = 0, devfn: int = 0x10, mac: str = "00:0C:29:00:00:01") -> None:
        device_num = (devfn >> 3) & 0x1F
        func = devfn & 0x07
        name = f"pci{bus:04x}:{device_num:02x}.{func}"
        self.name = name
        dev = PciDev(
            name=name,
            bus=bus,
            devfn=devfn,
            vendor=VENDOR_INTEL,
            device_id=DEVICE_E1000,
            revision=0x03,
            class_code=0x02,
            subclass=0x00,
            prog_if=0x00,
            header_type=PCI_HEADER_TYPE_NORMAL,
            pci_irq=_alloc_irq(),
        )
        dev._sub_vendor = VENDOR_VMWARE
        dev._sub_device = 0x0750
        rom_size = 64 * 1024
        mmio_size = 128 * 1024
        io_size = 64
        dev._bars = [
            PciBar(bar_num=0, bar_type="mem", base_addr=0xFD5E0000, size=mmio_size,
                   is_64bit=False),
            PciBar(bar_num=1, bar_type="io", base_addr=0x2000, size=io_size),
            PciBar(bar_num=2, bar_type="mem", base_addr=0, size=0),
            PciBar(bar_num=3, bar_type="mem", base_addr=0xFD5C0000, size=rom_size),
            PciBar(bar_num=4, bar_type="mem", base_addr=0, size=0),
            PciBar(bar_num=5, bar_type="mem", base_addr=0, size=0),
        ]
        dev._init_config_space()

        # Store MAC in config space (simulated EEPROM offset)
        mac_bytes = [int(b, 16) for b in mac.split(":")]
        for i, b in enumerate(mac_bytes):
            dev._config_space[0x80 + i] = b

        _devices[name] = dev
        bus_obj = _buses.setdefault(bus, PciBus(number=bus))
        bus_obj.devices.append(dev)
        log.info("PciNetworkCard created: %s mac=%s", name, mac)


class PciVgaCard:
    """Simulated PCI VGA/SVGA card."""

    def __init__(self, bus: int = 0, devfn: int = 0x18, vram_size: int = 256 * 1024) -> None:
        device_num = (devfn >> 3) & 0x1F
        func = devfn & 0x07
        name = f"pci{bus:04x}:{device_num:02x}.{func}"
        self.name = name
        dev = PciDev(
            name=name,
            bus=bus,
            devfn=devfn,
            vendor=VENDOR_QEMU,
            device_id=DEVICE_VGA,
            revision=0x04,
            class_code=0x03,
            subclass=0x00,
            prog_if=0x00,
            header_type=PCI_HEADER_TYPE_NORMAL,
            pci_irq=_alloc_irq(),
        )
        vram_phys = 0xFD000000
        dev._bars = [
            PciBar(bar_num=0, bar_type="mem", base_addr=vram_phys,
                   size=vram_size, is_prefetchable=True),
            PciBar(bar_num=1, bar_type="mem", base_addr=vram_phys + vram_size,
                   size=4096),
            PciBar(bar_num=2, bar_type="io", base_addr=0x3C0, size=32),
            PciBar(bar_num=3, bar_type="mem", base_addr=0, size=0),
            PciBar(bar_num=4, bar_type="mem", base_addr=0, size=0),
            PciBar(bar_num=5, bar_type="mem", base_addr=0, size=0),
        ]
        dev._init_config_space()
        _devices[name] = dev
        bus_obj = _buses.setdefault(bus, PciBus(number=bus))
        bus_obj.devices.append(dev)
        log.info("PciVgaCard created: %s vram=0x%X", name, vram_size)


class PciUsbController:
    """Simulated PCI USB controller."""

    def __init__(self, bus: int = 0, devfn: int = 0x20, version: str = "2.0") -> None:
        device_num = (devfn >> 3) & 0x1F
        func = devfn & 0x07
        name = f"pci{bus:04x}:{device_num:02x}.{func}"
        self.name = name

        if version == "3.0":
            dev_id = DEVICE_USB_XHCI
            prog = 0x30  # xHCI
        else:
            dev_id = DEVICE_USB_EHCI
            prog = 0x20  # EHCI

        dev = PciDev(
            name=name,
            bus=bus,
            devfn=devfn,
            vendor=VENDOR_INTEL,
            device_id=dev_id,
            revision=0x05,
            class_code=0x0C,
            subclass=0x03,
            prog_if=prog,
            header_type=PCI_HEADER_TYPE_NORMAL,
            pci_irq=_alloc_irq(),
        )
        mmio_size = 4096
        io_size = 32
        dev._bars = [
            PciBar(bar_num=0, bar_type="mem", base_addr=0xFD700000, size=mmio_size),
            PciBar(bar_num=1, bar_type="io", base_addr=0x3000, size=io_size),
            PciBar(bar_num=2, bar_type="mem", base_addr=0, size=0),
            PciBar(bar_num=3, bar_type="mem", base_addr=0, size=0),
            PciBar(bar_num=4, bar_type="mem", base_addr=0, size=0),
            PciBar(bar_num=5, bar_type="mem", base_addr=0, size=0),
        ]
        dev._init_config_space()
        _devices[name] = dev
        bus_obj = _buses.setdefault(bus, PciBus(number=bus))
        bus_obj.devices.append(dev)
        log.info("PciUsbController created: %s version=%s", name, version)


class PciSataController:
    """Simulated PCI SATA AHCI controller."""

    def __init__(self, bus: int = 0, devfn: int = 0x18, ports: int = 6) -> None:
        device_num = (devfn >> 3) & 0x1F
        func = devfn & 0x07
        name = f"pci{bus:04x}:{device_num:02x}.{func}"
        self.name = name
        dev = PciDev(
            name=name,
            bus=bus,
            devfn=devfn,
            vendor=VENDOR_INTEL,
            device_id=DEVICE_SATA_AHCI,
            revision=0x02,
            class_code=0x01,
            subclass=0x06,
            prog_if=0x01,
            header_type=PCI_HEADER_TYPE_NORMAL,
            pci_irq=_alloc_irq(),
        )
        dev._sub_vendor = VENDOR_INTEL
        dev._sub_device = 0x2922
        mmio_size = 4096
        dev._bars = [
            PciBar(bar_num=0, bar_type="mem", base_addr=0xFD6FF000, size=mmio_size),
            PciBar(bar_num=1, bar_type="mem", base_addr=0, size=0),
            PciBar(bar_num=2, bar_type="mem", base_addr=0, size=0),
            PciBar(bar_num=3, bar_type="mem", base_addr=0, size=0),
            PciBar(bar_num=4, bar_type="mem", base_addr=0, size=0),
            PciBar(bar_num=5, bar_type="mem", base_addr=0, size=0),
        ]
        dev._init_config_space()
        _devices[name] = dev
        bus_obj = _buses.setdefault(bus, PciBus(number=bus))
        bus_obj.devices.append(dev)
        log.info("PciSataController created: %s ports=%d", name, ports)


class PciNvmeController:
    """Simulated PCI NVMe controller."""

    def __init__(self, bus: int = 0, devfn: int = 0x28) -> None:
        device_num = (devfn >> 3) & 0x1F
        func = devfn & 0x07
        name = f"pci{bus:04x}:{device_num:02x}.{func}"
        self.name = name
        dev = PciDev(
            name=name,
            bus=bus,
            devfn=devfn,
            vendor=VENDOR_NVMExpress,
            device_id=DEVICE_NVME,
            revision=0x01,
            class_code=0x01,
            subclass=0x08,
            prog_if=0x02,
            header_type=PCI_HEADER_TYPE_NORMAL,
            pci_irq=_alloc_irq(),
        )
        mmio_size = 16384  # 16K for NVMe BAR0 (controller registers)
        dev._bars = [
            PciBar(bar_num=0, bar_type="mem", base_addr=0xFD800000, size=mmio_size,
                   is_64bit=False),
            PciBar(bar_num=1, bar_type="mem", base_addr=0xFD810000, size=4096),
            PciBar(bar_num=2, bar_type="mem", base_addr=0, size=0),
            PciBar(bar_num=3, bar_type="mem", base_addr=0, size=0),
            PciBar(bar_num=4, bar_type="mem", base_addr=0, size=0),
            PciBar(bar_num=5, bar_type="mem", base_addr=0, size=0),
        ]
        dev._init_config_space()
        _devices[name] = dev
        bus_obj = _buses.setdefault(bus, PciBus(number=bus))
        bus_obj.devices.append(dev)
        log.info("PciNvmeController created: %s", name)


# Alias the vendor constant for NVMe (typically uses standard NVM Express vendor)
VENDOR_NVMExpress = 0x144D  # Samsung


class PciPciBridge:
    """Simulated PCI-to-PCI bridge."""

    def __init__(self, bus: int = 0, devfn: int = 0x00, secondary_bus: int = 1) -> None:
        device_num = (devfn >> 3) & 0x1F
        func = devfn & 0x07
        name = f"pci{bus:04x}:{device_num:02x}.{func}"
        self.name = name
        dev = PciDev(
            name=name,
            bus=bus,
            devfn=devfn,
            vendor=VENDOR_INTEL,
            device_id=DEVICE_PCI_BRIDGE,
            revision=0x02,
            class_code=0x06,
            subclass=0x04,
            prog_if=0x01,
            header_type=PCI_HEADER_TYPE_BRIDGE,
            pci_irq=_alloc_irq(),
            is_bridge=True,
        )
        # Bridge-specific BARs: mem/io windows
        dev._bars = [
            PciBar(bar_num=0, bar_type="mem", base_addr=0, size=0),
            PciBar(bar_num=1, bar_type="mem", base_addr=0, size=0),
            PciBar(bar_num=2, bar_type="mem", base_addr=0, size=0),
            PciBar(bar_num=3, bar_type="mem", base_addr=0, size=0),
            PciBar(bar_num=4, bar_type="mem", base_addr=0, size=0),
            PciBar(bar_num=5, bar_type="mem", base_addr=0, size=0),
        ]
        # Bridge config space registers (bridge header)
        dev._config_space[0x18] = bus & 0xFF              # Primary bus
        dev._config_space[0x19] = secondary_bus & 0xFF    # Secondary bus
        dev._config_space[0x1A] = 0xFF                    # Subordinate bus
        dev._config_space[0x1C] = 0x00                    # I/O base
        dev._config_space[0x1D] = 0x00                    # I/O limit
        dev._config_space[0x20] = 0xFD40                  # Memory base
        dev._config_space[0x22] = 0xFD4F                  # Memory limit
        dev._init_config_space()

        _devices[name] = dev
        # Create secondary bus
        sec_bus = _buses.setdefault(secondary_bus, PciBus(number=secondary_bus))
        sec_bus.parent = _buses.setdefault(bus, PciBus(number=bus))
        sec_bus.parent.children.append(sec_bus)
        sec_bus.parent.devices.append(dev)
        log.info(
            "PciPciBridge created: %s secondary_bus=%d", name, secondary_bus,
        )


# ============================================================================
# Module Init / Cleanup
# ============================================================================

def pci_subsystem_init() -> None:
    """Initialize PCI subsystem buses."""
    root = _buses.setdefault(0, PciBus(number=0, name="pci0", is_root=True))
    log.info("PCI subsystem initialized: root bus %s", root.name)


def pci_subsystem_cleanup() -> None:
    """Shut down PCI subsystem."""
    global _devices, _buses, _drivers, _next_irq, _next_mmio
    _devices.clear()
    _buses.clear()
    _drivers.clear()
    _next_irq = 16
    _next_mmio = 0xFE000000
    log.info("PCI subsystem cleaned up")


# ============================================================================
# Demo
# ============================================================================

def _demo() -> None:
    """Demonstrate PCI subsystem functionality."""
    print("=" * 72)
    print("  UmerOS PCI Subsystem Demo")
    print("=" * 72)

    # --- Initialize subsystem ---
    pci_subsystem_init()
    print("\n[1] PCI subsystem initialized (root bus pci0)")

    # --- Enumerate built-in devices ---
    print("\n[2] Enumerating PCI devices...")

    bridge = PciPciBridge(bus=0, devfn=0x00, secondary_bus=1)
    ide = PciIdeController(bus=0, devfn=0x08)
    nic = PciNetworkCard(bus=0, devfn=0x10, mac="00:0C:29:AB:CD:EF")
    vga = PciVgaCard(bus=0, devfn=0x18, vram_size=256 * 1024)
    usb2 = PciUsbController(bus=0, devfn=0x20, version="2.0")
    usb3 = PciUsbController(bus=1, devfn=0x00, version="3.0")
    sata = PciSataController(bus=0, devfn=0x28, ports=6)
    nvme = PciNvmeController(bus=0, devfn=0x30)

    print("    Built-in devices created on bus 0 and bus 1")

    # --- List all devices ---
    print("\n[3] PCI device listing:")
    for dev_name in pci_list_devices():
        dev = _devices[dev_name]
        print(
            f"    {dev_name:20s}  "
            f"vendor=0x{dev.vendor:04X}  "
            f"device=0x{dev.device_id:04X}  "
            f"class={pci_class_string(dev.full_class)}"
        )

    # --- Enable devices and set bus master ---
    print("\n[4] Enabling devices and setting bus master...")
    for dev_name in [ide.name, nic.name, nvme.name]:
        pci_enable_device(dev_name)
        pci_set_master(dev_name)

    # --- Config space read/write ---
    print("\n[5] Config space operations:")
    ide_name = ide.name
    pci_write_config_byte(ide_name, PCI_CACHE_LINE_SIZE, 0x10)
    cache_line = pci_read_config_byte(ide_name, PCI_CACHE_LINE_SIZE)
    print(f"    {ide_name} cache line size = 0x{cache_line:02X}")

    pci_save_state(ide_name)
    pci_write_config_byte(ide_name, PCI_LATENCY_TIMER, 0x40)
    pci_restore_state(ide_name)
    restored = pci_read_config_byte(ide_name, PCI_LATENCY_TIMER)
    print(f"    After restore, latency timer = 0x{restored:02X}")

    # --- BAR info ---
    print("\n[6] BAR information for network card:")
    nic_name = nic.name
    for i in range(6):
        start = pci_resource_start(nic_name, i)
        length = pci_resource_len(nic_name, i)
        flags = pci_resource_flags(nic_name, i)
        if length > 0:
            bar_type = "IO" if flags & PCI_IORESOURCE_IO else "MEM"
            print(
                f"    BAR{i}: {bar_type} start=0x{start:08X} "
                f"length=0x{length:X} flags=0x{flags:04X}"
            )

    # --- MMIO mapping ---
    print("\n[7] MMIO mapping:")
    vaddr = pci_ioremap_bar(nic_name, 0)
    print(f"    {nic_name} BAR0 mapped -> virtual 0x{vaddr:08X}")
    vaddr2 = pci_ioremap_bar(vga.name, 0)
    print(f"    {vga.name} BAR0 mapped -> virtual 0x{vaddr2:08X}")

    # --- Request / release regions ---
    print("\n[8] Region request/release:")
    rc = pci_request_region(sata.name, 0, name="AHCI registers")
    print(f"    Request SATA BAR0: rc={rc}")
    pci_release_region(sata.name, 0)
    print(f"    Released SATA BAR0")

    # --- MSI allocation ---
    print("\n[9] MSI/MSI-X allocation:")
    nvme_name = nvme.name
    count = pci_alloc_irq_vectors(nvme_name, 1, 4, MSI_FLAG_ENABLE)
    print(f"    {nvme_name}: allocated {count} MSI vectors")
    for i in range(count):
        irq = pci_irq_vector(nvme_name, i)
        print(f"      vector[{i}] -> IRQ {irq}")
    pci_free_irq_vectors(nvme_name)

    pci_msix_enable(nic_name)
    irq0 = pci_irq_vector(nic_name, 0)
    print(f"    {nic_name}: MSI-X enabled, vector[0] -> IRQ {irq0}")

    # --- DMA mask ---
    print("\n[10] DMA mask operations:")
    pci_set_dma_mask(nvme_name, 0xFFFFFFFF)
    print(f"    {nvme_name} DMA mask: {_devices[nvme_name].pci_dma}")
    pci_set_dma_mask(nvme_name, 0xFFFFFFFFFFFFFFFF)
    print(f"    {nvme_name} DMA mask (64-bit): {_devices[nvme_name].pci_dma}")

    # --- Reference counting ---
    print("\n[11] Reference counting:")
    print(f"    {ide_name} ref_count = {_devices[ide_name]._ref_count}")
    pci_dev_get(ide_name)
    print(f"    After pci_dev_get: ref_count = {_devices[ide_name]._ref_count}")
    pci_dev_put(ide_name)
    print(f"    After pci_dev_put: ref_count = {_devices[ide_name]._ref_count}")

    # --- Find by vendor/device ID ---
    print("\n[12] Lookup by vendor/device ID:")
    found = pci_get_device(0x8086, 0x100E)
    if found:
        print(f"    Found Intel e1000: {found.name}")
    found_slot = pci_get_slot(0, 0x10)
    if found_slot:
        print(f"    Slot 0000:00.2 -> {found_slot.name}")

    # --- Bridge ---
    print("\n[13] PCI bridge:")
    bridgedev = pci_bus_get_bridgedev(1)
    if bridgedev:
        print(f"    Bus 1 bridge device: {bridgedev.name}")
    sec_bus = pci_find_bus(0, 1)
    if sec_bus:
        print(
            f"    Secondary bus: {sec_bus.name} "
            f"(parent={sec_bus.parent.name if sec_bus.parent else 'none'})"
        )

    # --- Device info ---
    print("\n[14] Device info dump:")
    print(pci_info(nic.name))

    # --- Class name lookup ---
    print("\n[15] PCI class names:")
    classes = [
        PCI_CLASS_STORAGE_SATA,
        PCI_CLASS_NETWORK_ETHERNET,
        PCI_CLASS_DISPLAY_VGA,
        PCI_CLASS_BRIDGE_PCI,
        PCI_CLASS_SERIAL_USB,
        PCI_CLASS_MULTIPROCESSOR,
        PCI_CLASS_MEMORY_RAM,
        PCI_CLASS_SERIAL_SCSI,
    ]
    for cc in classes:
        print(f"    0x{cc:06X} -> {pci_class_string(cc)}")

    # --- Driver registration ---
    print("\n[16] Driver registration:")
    test_driver = PciDriver(
        name="e1000_driver",
        id_table=[
            PciDeviceId(vendor=VENDOR_INTEL, device=DEVICE_E1000),
        ],
    )
    _drivers[test_driver.name] = test_driver
    pci_register_driver(test_driver.name)
    print(f"    Registered drivers: {pci_list_drivers()}")

    # --- PCIe reset state ---
    print("\n[17] PCIe reset state:")
    pci_set_pcie_reset_state(nvme_name, PCI_RESET_cold)

    # --- Cleanup ---
    pci_unregister_driver(test_driver.name)
    pci_subsystem_cleanup()
    print("\n[18] PCI subsystem cleaned up")
    print("\n" + "=" * 72)
    print("  PCI Subsystem Demo Complete")
    print("=" * 72)


if __name__ == "__main__":
    _demo()
