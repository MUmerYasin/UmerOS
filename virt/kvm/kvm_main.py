"""
KVM Main Module
===============

Core KVM data structures and main entry points.
Based on linux/virt/kvm/kvm_main.c
"""

import ctypes
import threading
import mmap
import os
import struct
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import IntEnum
from collections import deque


# Constants from Linux KVM
KVM_MAX_VCPUS = 1024
KVM_MAX_MEM_SLOTS = 1024
KVM_PAGE_SIZE = 4096
KVM_DIRTY_LOG_MAX_PAGES = 65536

# Exit reasons
class KVM_EXIT_REASONS(IntEnum):
    UNKNOWN = 0
    EXCEPTION = 1
    IO = 2
    HYPERCALL = 3
    DEBUG = 4
    HLT = 5
    MMIO = 6
    IRQ_WINDOW_OPEN = 7
    SHUTDOWN = 8
    FAIL_ENTRY = 9
    INTR = 10
    SET_TPR = 11
    TPR_ACCESS = 12
    S390_SIEIC = 13
    S390_RESET = 14
    DCR = 15
    NMI = 16
    INTERNAL_ERROR = 17
    OSI = 18
    PAPR_HCALL = 19
    S390_UCONTROL = 20
    WATCHDOG = 21
    S390_TSCH = 22
    EPR = 23
    SYSTEM_EVENT = 24
    S390_STSI = 25
    IOAPIC_EOI = 26
    HYPERV = 27
    ARM_NISV = 28
    X86_RDMSR = 29
    X86_WRMSR = 30
    DIRTY_RING_FULL = 31
    MAX = 32


@dataclass
class KVMMemorySlot:
    """KVM Memory Slot - maps guest physical memory to host virtual memory"""
    id: int = 0
    base_gfn: int = 0           # Guest frame number
    npages: int = 0             # Number of pages
    userspace_addr: int = 0     # Host virtual address
    flags: int = 0
    dirty_bitmap: Optional[bytearray] = None
    dirty_bitmap_pages: int = 0
    
    # Arch-specific data
    arch: Any = None


@dataclass
class KVMRun:
    """KVM Run structure - shared between kernel and userspace"""
    request_interrupt_window: int = 0
    immediate_exit: int = 0
    padding1: bytes = field(default_factory=lambda: b'\x00' * 6)
    exit_reason: int = 0
    ready_for_interrupt_injection: int = 0
    if_flag: int = 0
    flags: int = 0
    cr8: int = 0
    apic_base: int = 0
    
    # Exit-specific data (union-like)
    exit_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KVMVCPU:
    """KVM Virtual CPU"""
    vcpu_id: int = 0
    kvm: Optional['KVM'] = None
    run: Optional[KVMRun] = None
    
    # vCPU state
    fpu_active: int = 0
    requests: int = 0
    
    # Interrupt state
    interrupt_injected: int = 0
    interrupt_nr: int = 0
    
    # MMU
    mmu: Any = None
    
    # Async PF
    async_pf: Any = None
    
    # Dirty ring
    dirty_ring: Any = None
    
    # Architecture-specific
    arch: Any = None
    
    # Statistics
    stat: Dict[str, int] = field(default_factory=dict)
    
    # Synchronization
    mutex: threading.Lock = field(default_factory=threading.Lock)
    wq: threading.Condition = field(default_factory=lambda: threading.Condition())


class KVM:
    """Main KVM Virtual Machine structure"""
    
    def __init__(self, vm_id: int = 0):
        self.vm_id = vm_id
        self.created = False
        
        # vCPU management
        self.vcpus: List[Optional[KVMVCPU]] = [None] * KVM_MAX_VCPUS
        self.online_vcpus = 0
        self.max_vcpus = KVM_MAX_VCPUS
        
        # Memory management
        self.memslots: List[Optional[KVMMemorySlot]] = [None] * KVM_MAX_MEM_SLOTS
        self.used_memslots = 0
        self.memslots_lock = threading.RLock()
        
        # MMU
        self.mmu_lock = threading.RLock()
        self.mmu_notifier_seq = 0
        self.mn_active_invalidate_count = 0
        
        # Dirty logging
        self.dirty_log_lock = threading.Lock()
        self.dirty_ring_size = 0
        self.dirty_ring_with_bitmap = False
        
        # IRQ routing
        self.irq_routing: Optional['KVM_Irq_Routing_Table'] = None
        self.irq_srcu = threading.RLock()  # Simplified SRCU
        self.irq_lock = threading.Lock()
        
        # Coalesced MMIO
        self.coalesced_mmio_ring: Optional['KVMCoalescedMMIORing'] = None
        self.coalesced_zones: List[Any] = []
        self.ring_lock = threading.Lock()
        self.slots_lock = threading.RLock()
        
        # EventFDs
        self.eventfds: List['KVMEventFD'] = []
        self.ioeventfds: List['KVMIOEventFD'] = []
        self.virqfds: List['KVMVirqFD'] = []
        
        # VFIO
        self.devices: List[Any] = []
        self.lock = threading.Lock()
        
        # PFN Cache
        self.gpc_list: List['GFNToPFNCache'] = []
        self.gpc_lock = threading.Lock()
        
        # Statistics
        self.stats_header: Optional['KVMStatsHeader'] = None
        self.stats_desc: List['KVMStatsDesc'] = []
        self.stats_data: bytearray = bytearray()
        
        # Guest memfd
        self.gmem: Optional['KVMGuestMemfd'] = None
        
        # Arch-specific
        self.arch: Any = None
    
    def create_vcpu(self, vcpu_id: int) -> KVMVCPU:
        """Create a new vCPU"""
        if vcpu_id >= KVM_MAX_VCPUS:
            raise ValueError(f"vcpu_id {vcpu_id} exceeds KVM_MAX_VCPUS")
        
        vcpu = KVMVCPU(vcpu_id=vcpu_id, kvm=self)
        vcpu.run = KVMRun()
        
        with self.lock:
            self.vcpus[vcpu_id] = vcpu
            self.online_vcpus += 1
        
        return vcpu
    
    def get_vcpu(self, vcpu_id: int) -> Optional[KVMVCPU]:
        """Get vCPU by ID"""
        if 0 <= vcpu_id < KVM_MAX_VCPUS:
            return self.vcpus[vcpu_id]
        return None
    
    def set_memory_region(self, slot: int, flags: int, guest_phys_addr: int,
                          memory_size: int, userspace_addr: int) -> int:
        """Set a memory region (KVM_SET_USER_MEMORY_REGION)"""
        if slot >= KVM_MAX_MEM_SLOTS:
            return -1  # EINVAL
        
        npages = (memory_size + KVM_PAGE_SIZE - 1) // KVM_PAGE_SIZE
        base_gfn = guest_phys_addr // KVM_PAGE_SIZE
        
        with self.memslots_lock:
            # Remove existing slot if present
            if self.memslots[slot] is not None:
                self.memslots[slot] = None
                self.used_memslots -= 1
            
            # Create new slot if size > 0
            if memory_size > 0:
                memslot = KVMMemorySlot(
                    id=slot,
                    base_gfn=base_gfn,
                    npages=npages,
                    userspace_addr=userspace_addr,
                    flags=flags
                )
                # Allocate dirty bitmap
                memslot.dirty_bitmap_pages = (npages + 63) // 64
                memslot.dirty_bitmap = bytearray(memslot.dirty_bitmap_pages * 8)
                
                self.memslots[slot] = memslot
                self.used_memslots += 1
        
        return 0
    
    def get_memory_region(self, slot: int) -> Optional[KVMMemorySlot]:
        """Get memory region by slot"""
        if 0 <= slot < KVM_MAX_MEM_SLOTS:
            return self.memslots[slot]
        return None
    
    def gfn_to_hva(self, gfn: int) -> int:
        """Convert guest frame number to host virtual address"""
        with self.memslots_lock:
            for slot in self.memslots:
                if slot and slot.base_gfn <= gfn < slot.base_gfn + slot.npages:
                    offset = (gfn - slot.base_gfn) * KVM_PAGE_SIZE
                    return slot.userspace_addr + offset
        return -1  # KVM_HVA_ERR_BAD
    
    def gfn_to_pfn(self, gfn: int, write: bool = False) -> int:
        """Convert guest frame number to physical frame number (simplified)"""
        hva = self.gfn_to_hva(gfn)
        if hva == -1:
            return -1  # KVM_PFN_ERR_FAULT
        # In real implementation, would use get_user_pages
        # For Python simulation, we'll return a pseudo-PFN
        return hva // KVM_PAGE_SIZE
    
    def init_irq_routing(self) -> int:
        """Initialize IRQ routing table"""
        from .irqchip import kvm_init_irq_routing
        return kvm_init_irq_routing(self)
    
    def set_irq_routing(self, entries: List['KVMKernelIrqRoutingEntry']) -> int:
        """Set IRQ routing entries"""
        if not self.irq_routing:
            self.init_irq_routing()
        
        with self.irq_lock:
            return self.irq_routing.set_routing(entries)
    
    def create_device(self, device_type: int) -> Any:
        """Create a KVM device"""
        with self.lock:
            # Check for existing device of same type
            for dev in self.devices:
                if getattr(dev, 'type', None) == device_type:
                    raise OSError(16)  # EBUSY
            
            # In real implementation, would create specific device
            # For now, return a placeholder
            dev = {'type': device_type, 'private': None}
            self.devices.append(dev)
            return dev
    
    def run_vcpu(self, vcpu_id: int) -> KVMRun:
        """Run a vCPU (simplified simulation)"""
        vcpu = self.get_vcpu(vcpu_id)
        if not vcpu:
            raise ValueError(f"vCPU {vcpu_id} not found")
        
        # In real implementation, this would enter the guest
        # For simulation, we just return the run struct
        return vcpu.run
    
    def inject_irq(self, irq: int, level: int, irq_source_id: int = 0) -> int:
        """Inject an interrupt"""
        if not self.irq_routing:
            return -1
        
        # Simplified - would call architecture-specific handlers
        return 1
    
    def get_dirty_log(self, slot: int, dirty_bitmap: bytearray) -> int:
        """Get dirty page log for a memory slot"""
        memslot = self.get_memory_region(slot)
        if not memslot or not memslot.dirty_bitmap:
            return -1
        
        # Copy dirty bitmap
        dirty_bitmap[:len(memslot.dirty_bitmap)] = memslot.dirty_bitmap
        return 0
    
    def clear_dirty_log(self, slot: int) -> int:
        """Clear dirty page log for a memory slot"""
        memslot = self.get_memory_region(slot)
        if not memslot or not memslot.dirty_bitmap:
            return -1
        
        memslot.dirty_bitmap[:] = b'\x00' * len(memslot.dirty_bitmap)
        return 0


# KVM_MMU_LOCK macros
def KVM_MMU_LOCK_INIT(kvm: KVM):
    """Initialize MMU lock"""
    kvm.mmu_lock = threading.RLock()

def KVM_MMU_LOCK(kvm: KVM):
    """Acquire MMU lock"""
    kvm.mmu_lock.acquire()

def KVM_MMU_UNLOCK(kvm: KVM):
    """Release MMU lock"""
    kvm.mmu_lock.release()