"""
KVM Coalesced MMIO
==================

Python implementation of KVM coalesced MMIO for batching MMIO writes.
Based on linux/virt/kvm/coalesced_mmio.c and coalesced_mmio.h
"""

import threading
import struct
from dataclasses import dataclass, field
from typing import Optional, List, Any
from collections import deque


# Constants
KVM_COALESCED_MMIO_MAX = 64  # Maximum entries in ring


@dataclass
class KVMCoalescedMMIOZone:
    """Coalesced MMIO zone"""
    addr: int = 0           # Guest physical address
    size: int = 0           # Size in bytes
    pio: int = 0            # 1 for PIO, 0 for MMIO


@dataclass
class KVMCoalescedMMIOEntry:
    """Single coalesced MMIO entry"""
    phys_addr: int = 0
    len: int = 0
    data: bytes = field(default_factory=lambda: b'\x00' * 256)
    pio: int = 0


@dataclass
class KVMCoalescedMMIORing:
    """Coalesced MMIO ring buffer"""
    first: int = 0
    last: int = 0
    coalesced_mmio: List['KVMCoalescedMMIOEntry'] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.coalesced_mmio:
            self.coalesced_mmio = [KVMCoalescedMMIOEntry() for _ in range(KVM_COALESCED_MMIO_MAX)]


@dataclass
class KVMCoalescedMMIODev:
    """Coalesced MMIO device"""
    dev: Any = None  # Would be KVMIODevice in real implementation
    kvm: Optional['KVM'] = None
    zone: KVMCoalescedMMIOZone = field(default_factory=KVMCoalescedMMIOZone)
    list_node: Any = None  # For linked list


def coalesced_mmio_in_range(dev: KVMCoalescedMMIODev, addr: int, length: int) -> bool:
    """Check if address range is within coalesced zone"""
    if length < 0:
        return False
    if addr + length < addr:  # Overflow check
        return False
    if addr < dev.zone.addr:
        return False
    if addr + length > dev.zone.addr + dev.zone.size:
        return False
    return True


def coalesced_mmio_write(vcpu: Any, dev: Any, addr: int, 
                         length: int, val: bytes) -> int:
    """Write to coalesced MMIO"""
    mmio_dev = dev  # In real: container_of(dev, KVMCoalescedMMIODev, dev)
    kvm = mmio_dev.kvm
    
    if not kvm or not kvm.coalesced_mmio_ring:
        return -95  # EOPNOTSUPP
    
    if not coalesced_mmio_in_range(mmio_dev, addr, length):
        return -95  # EOPNOTSUPP
    
    ring = kvm.coalesced_mmio_ring
    
    with kvm.ring_lock:
        insert = ring.last
        
        # Check bounds and ring full
        if insert >= KVM_COALESCED_MMIO_MAX:
            return -95
        
        next_insert = (insert + 1) % KVM_COALESCED_MMIO_MAX
        if next_insert == ring.first:
            return -95  # Ring full
        
        # Copy data to ring
        entry = ring.coalesced_mmio[insert]
        entry.phys_addr = addr
        entry.len = length
        entry.data = val[:length].ljust(256, b'\x00')
        entry.pio = mmio_dev.zone.pio
        
        # Memory barrier (smp_wmb equivalent)
        # In Python, GIL provides some ordering, but we use lock
        
        ring.last = next_insert
    
    return 0


def coalesced_mmio_destructor(dev: Any):
    """Destructor for coalesced MMIO device"""
    mmio_dev = dev
    # Remove from list
    if mmio_dev.kvm and hasattr(mmio_dev.kvm, 'coalesced_zones'):
        try:
            mmio_dev.kvm.coalesced_zones.remove(mmio_dev)
        except ValueError:
            pass


class KVMCoalescedMMIOOps:
    """Coalesced MMIO operations"""
    write = staticmethod(coalesced_mmio_write)
    destructor = staticmethod(coalesced_mmio_destructor)


def kvm_coalesced_mmio_init(kvm: 'KVM') -> int:
    """Initialize coalesced MMIO for a VM"""
    # Allocate ring buffer (one page)
    ring = KVMCoalescedMMIORing()
    kvm.coalesced_mmio_ring = ring
    
    # Initialize ring lock
    kvm.ring_lock = threading.Lock()
    
    # Initialize zones list
    kvm.coalesced_zones = []
    
    return 0


def kvm_coalesced_mmio_free(kvm: 'KVM'):
    """Free coalesced MMIO resources"""
    kvm.coalesced_mmio_ring = None


def kvm_vm_ioctl_register_coalesced_mmio(kvm: 'KVM', 
                                          zone: KVMCoalescedMMIOZone) -> int:
    """Register a coalesced MMIO zone"""
    if zone.pio not in (0, 1):
        return -22  # EINVAL
    
    dev = KVMCoalescedMMIODev()
    dev.kvm = kvm
    dev.zone = zone
    
    # Initialize device ops
    dev.dev = KVMCoalescedMMIOOps()
    
    with kvm.slots_lock:
        # In real implementation: kvm_io_bus_register_dev
        # Here we just add to list
        kvm.coalesced_zones.append(dev)
    
    return 0


def kvm_vm_ioctl_unregister_coalesced_mmio(kvm: 'KVM',
                                            zone: KVMCoalescedMMIOZone) -> int:
    """Unregister a coalesced MMIO zone"""
    if zone.pio not in (0, 1):
        return -22  # EINVAL
    
    with kvm.slots_lock:
        # Find and remove matching zone
        to_remove = []
        for dev in kvm.coalesced_zones:
            if (zone.pio == dev.zone.pio and 
                coalesced_mmio_in_range(dev, zone.addr, zone.size)):
                to_remove.append(dev)
        
        for dev in to_remove:
            kvm.coalesced_zones.remove(dev)
            coalesced_mmio_destructor(dev)
    
    return 0