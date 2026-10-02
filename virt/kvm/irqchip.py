"""
KVM IRQ Chip / Interrupt Routing
================================

Python implementation of KVM interrupt routing and IRQ chip support.
Based on linux/virt/kvm/irqchip.c
"""

import threading
from dataclasses import dataclass, field
from typing import Optional, List, Any, Callable
from collections import defaultdict


# Constants
KVM_MAX_IRQ_ROUTES = 4096
KVM_NR_IRQCHIPS = 3
KVM_IRQCHIP_NUM_PINS = 256

# IRQ Routing types
KVM_IRQ_ROUTING_IRQCHIP = 0
KVM_IRQ_ROUTING_MSI = 1
KVM_IRQ_ROUTING_S390_ADAPTER = 2
KVM_IRQ_ROUTING_HV_SINT = 3

# MSI flags
KVM_MSI_VALID_DEVID = 0x00000001

# IRQ Sources
KVM_USERSPACE_IRQ_SOURCE_ID = 0xFFFFFFFF


@dataclass
class KVMKernelIrqRoutingEntry:
    """Kernel IRQ routing entry"""
    gsi: int = 0
    type: int = 0
    flags: int = 0
    
    # Union fields - only one valid based on type
    irqchip: Any = None
    msi: Any = None
    
    # Function pointer for setting IRQ
    set: Optional[Callable] = None


@dataclass
class KVM_IRQ_Routing_Entry:
    """Userspace IRQ routing entry"""
    gsi: int = 0
    type: int = 0
    flags: int = 0
    u: Any = None


@dataclass
class KVM_Irq_Routing_Table:
    """IRQ Routing Table"""
    nr_rt_entries: int = 0
    map: List[List[KVMKernelIrqRoutingEntry]] = field(default_factory=list)
    chip: List[List[int]] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.map:
            self.map = [[] for _ in range(KVM_MAX_IRQ_ROUTES)]
        if not self.chip:
            self.chip = [[-1 for _ in range(KVM_IRQCHIP_NUM_PINS)] 
                        for _ in range(KVM_NR_IRQCHIPS)]


def kvm_irq_map_gsi(kvm: Any, entries: List[KVMKernelIrqRoutingEntry], 
                    gsi: int) -> int:
    """Map GSI to routing entries"""
    if not kvm.irq_routing:
        return 0
    
    irq_rt = kvm.irq_routing
    n = 0
    
    if gsi < irq_rt.nr_rt_entries:
        for e in irq_rt.map[gsi]:
            if n < len(entries):
                entries[n] = e
                n += 1
    
    return n


def kvm_irq_map_chip_pin(kvm: Any, irqchip: int, pin: int) -> int:
    """Map IRQ chip and pin to GSI"""
    if not kvm.irq_routing:
        return -1
    
    irq_rt = kvm.irq_routing
    if irqchip < KVM_NR_IRQCHIPS and pin < KVM_IRQCHIP_NUM_PINS:
        return irq_rt.chip[irqchip][pin]
    return -1


def kvm_send_userspace_msi(kvm: Any, msi: Any) -> int:
    """Send MSI from userspace"""
    if not getattr(kvm, 'arch', None) or \
       not getattr(kvm.arch, 'irqchip_in_kernel', lambda: False)():
        return -22  # EINVAL
    
    if msi.flags & ~KVM_MSI_VALID_DEVID:
        return -22
    
    # Convert to routing entry
    route = KVMKernelIrqRoutingEntry()
    route.msi = msi
    route.msi.flags = msi.flags
    route.msi.devid = msi.devid
    
    return kvm_set_msi(route, kvm, KVM_USERSPACE_IRQ_SOURCE_ID, 1, False)


def kvm_set_irq(kvm: Any, irq_source_id: int, irq: int, 
                level: int, line_status: bool) -> int:
    """Set IRQ level"""
    if not kvm.irq_routing:
        return -1
    
    entries = [KVMKernelIrqRoutingEntry() for _ in range(KVM_NR_IRQCHIPS)]
    
    # Get routing entries for this IRQ
    i = kvm_irq_map_gsi(kvm, entries, irq)
    
    ret = -1
    while i > 0:
        i -= 1
        if entries[i].set:
            r = entries[i].set(entries[i], kvm, irq_source_id, level, line_status)
            if r < 0:
                continue
            ret = r + (0 if ret < 0 else ret)
    
    return ret


def free_irq_routing_table(rt: Optional[KVM_Irq_Routing_Table]):
    """Free IRQ routing table"""
    if not rt:
        return
    
    for i in range(rt.nr_rt_entries):
        rt.map[i].clear()
    
    rt.map.clear()
    rt.chip.clear()


def kvm_free_irq_routing(kvm: Any):
    """Free IRQ routing"""
    if kvm.irq_routing:
        free_irq_routing_table(kvm.irq_routing)
        kvm.irq_routing = None


def setup_routing_entry(kvm: Any, rt: KVM_Irq_Routing_Table,
                        e: KVMKernelIrqRoutingEntry,
                        ue: KVM_IRQ_Routing_Entry) -> int:
    """Setup a single routing entry"""
    gsi = ue.gsi % KVM_MAX_IRQ_ROUTES
    
    # Check for duplicate mapping
    for ei in rt.map[gsi]:
        if (ei.type != KVM_IRQ_ROUTING_IRQCHIP or 
            ue.type != KVM_IRQ_ROUTING_IRQCHIP or
            (hasattr(ue, 'irqchip') and hasattr(ei, 'irqchip') and
             ue.irqchip.irqchip == ei.irqchip.irqchip)):
            return -22  # EINVAL
    
    e.gsi = gsi
    e.type = ue.type
    
    r = kvm_set_routing_entry(kvm, e, ue)
    if r:
        return r
    
    if e.type == KVM_IRQ_ROUTING_IRQCHIP:
        if hasattr(e, 'irqchip'):
            rt.chip[e.irqchip.irqchip][e.irqchip.pin] = e.gsi
    
    rt.map[e.gsi].append(e)
    return 0


def kvm_set_routing_entry(kvm: Any, e: KVMKernelIrqRoutingEntry,
                          ue: KVM_IRQ_Routing_Entry) -> int:
    """Arch-specific routing entry setup (weak)"""
    # This would be implemented per-architecture
    return 0


def kvm_arch_irq_routing_update(kvm: Any):
    """Arch-specific IRQ routing update (weak)"""
    pass


def kvm_arch_can_set_irq_routing(kvm: Any) -> bool:
    """Arch-specific: can set IRQ routing (weak)"""
    return True


def kvm_set_irq_routing(kvm: Any, ue: List[KVM_IRQ_Routing_Entry],
                        nr: int, flags: int) -> int:
    """Set IRQ routing table"""
    # Validate entries
    nr_rt_entries = 0
    for i in range(nr):
        if ue[i].gsi >= KVM_MAX_IRQ_ROUTES:
            return -22
        nr_rt_entries = max(nr_rt_entries, ue[i].gsi)
    
    nr_rt_entries += 1
    
    # Create new routing table
    new = KVM_Irq_Routing_Table()
    new.nr_rt_entries = nr_rt_entries
    
    # Process entries
    for i in range(nr):
        e = KVMKernelIrqRoutingEntry()
        
        # Validate flags
        if ue[i].type == KVM_IRQ_ROUTING_MSI:
            if ue[i].flags & ~KVM_MSI_VALID_DEVID:
                return -22
        else:
            if ue[i].flags:
                return -22
        
        r = setup_routing_entry(kvm, new, e, ue[i])
        if r:
            free_irq_routing_table(new)
            return r
    
    # Swap with old table (with locking)
    with getattr(kvm, 'irq_lock', threading.Lock()):
        old = kvm.irq_routing
        kvm.irq_routing = new
        kvm_irq_routing_update(kvm)
        kvm_arch_irq_routing_update(kvm)
        
        # In real kernel: synchronize_srcu_expedited
        # Here we just free old
        free_irq_routing_table(old)
    
    return 0


def kvm_init_irq_routing(kvm: Any) -> int:
    """Initialize empty IRQ routing"""
    new = KVM_Irq_Routing_Table()
    new.nr_rt_entries = 1
    new.chip = [[-1 for _ in range(KVM_IRQCHIP_NUM_PINS)] 
                for _ in range(KVM_NR_IRQCHIPS)]
    
    kvm.irq_routing = new
    return 0


# Architecture-specific stubs
def kvm_arch_irqchip_in_kernel(kvm: Any) -> bool:
    """Check if IRQ chip is in kernel"""
    return hasattr(kvm, 'arch') and getattr(kvm.arch, 'irqchip_in_kernel', lambda: False)()


def kvm_set_msi(route: KVMKernelIrqRoutingEntry, kvm: Any,
                irq_source_id: int, level: int, line_status: bool) -> int:
    """Set MSI (arch-specific)"""
    return 1


def kvm_irq_routing_update(kvm: Any):
    """IRQ routing update callback"""
    pass


# Helper functions for creating routing entries
def create_irqchip_routing_entry(gsi: int, irqchip: int, pin: int) -> KVM_IRQ_Routing_Entry:
    """Create IRQCHIP routing entry"""
    entry = KVM_IRQ_Routing_Entry()
    entry.gsi = gsi
    entry.type = KVM_IRQ_ROUTING_IRQCHIP
    entry.flags = 0
    entry.u = {'irqchip': {'irqchip': irqchip, 'pin': pin}}
    return entry


def create_msi_routing_entry(gsi: int, address_lo: int, address_hi: int,
                              data: int, flags: int = 0, devid: int = 0) -> KVM_IRQ_Routing_Entry:
    """Create MSI routing entry"""
    entry = KVM_IRQ_Routing_Entry()
    entry.gsi = gsi
    entry.type = KVM_IRQ_ROUTING_MSI
    entry.flags = flags
    entry.u = {
        'msi': {
            'address_lo': address_lo,
            'address_hi': address_hi,
            'data': data,
            'flags': flags,
            'devid': devid
        }
    }
    return entry


# Weak functions for async PF
def kvm_arch_can_dequeue_async_page_present(vcpu: Any) -> bool:
    return True


def kvm_arch_async_page_ready(vcpu: Any, work: Any):
    pass


def kvm_arch_async_page_not_present(vcpu: Any, work: Any) -> bool:
    return False