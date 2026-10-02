"""
KVM Memory Management
=====================

Python implementation of KVM memory management utilities.
Based on linux/virt/kvm/kvm_mm.h
"""

import threading
from dataclasses import dataclass, field
from typing import Optional, Any, List
from enum import IntFlag


class FOLLFlags(IntFlag):
    """Follow page flags"""
    NONE = 0
    WRITE = 1
    FORCE = 2
    GET = 4
    POPULATE = 8
    SPLIT = 16
    HWPOISON = 32
    NUMA = 64
    LONGTERM = 128
    SPLIT_PMD = 256
    PIN = 512


@dataclass
class KVMFollowPFN:
    """Parameters for HVA to PFN conversion"""
    slot: Optional[Any] = None
    gfn: int = 0
    flags: int = 0
    hva: int = 0
    pin: bool = False
    map_writable: Optional[bool] = None
    refcounted_page: Optional[Any] = None


# MMU Lock types
class KVM_HAVE_MMU_RWLOCK(IntFlag):
    NONE = 0
    RWLOCK = 1


# Global config (would be per-arch in real kernel)
_kvm_have_mmu_rwlock = KVM_HAVE_MMU_RWLOCK.NONE


def KVM_MMU_LOCK_INIT(kvm: Any):
    """Initialize MMU lock"""
    if _kvm_have_mmu_rwlock & KVM_HAVE_MMU_RWLOCK.RWLOCK:
        # Use RLock for read-write semantics
        kvm.mmu_lock = threading.RLock()
    else:
        # Use regular Lock (spinlock equivalent)
        kvm.mmu_lock = threading.Lock()


def KVM_MMU_LOCK(kvm: Any):
    """Acquire MMU lock"""
    if hasattr(kvm, 'mmu_lock'):
        kvm.mmu_lock.acquire()


def KVM_MMU_UNLOCK(kvm: Any):
    """Release MMU lock"""
    if hasattr(kvm, 'mmu_lock'):
        kvm.mmu_lock.release()


def KVM_HAVE_MMU_RWLOCK_ENABLED() -> bool:
    """Check if RWLOCK is enabled for MMU"""
    return bool(_kvm_have_mmu_rwlock & KVM_HAVE_MMU_RWLOCK.RWLOCK)


def set_kvm_have_mmu_rwlock(enabled: bool):
    """Set MMU lock type (for testing)"""
    global _kvm_have_mmu_rwlock
    if enabled:
        _kvm_have_mmu_rwlock = KVM_HAVE_MMU_RWLOCK.RWLOCK
    else:
        _kvm_have_mmu_rwlock = KVM_HAVE_MMU_RWLOCK.NONE


def hva_to_pfn(kfp: KVMFollowPFN) -> int:
    """Convert HVA to PFN"""
    # In real kernel: get_user_pages + page_to_pfn
    # Simplified implementation
    if kfp.hva == 0:
        return -1  # KVM_PFN_ERR_FAULT
    
    # Return page frame number
    return kfp.hva // 4096


# PFN cache invalidation (from pfncache)
def gfn_to_pfn_cache_invalidate_start(kvm: Any, start: int, end: int):
    """Invalidate PFN caches in range"""
    if not hasattr(kvm, 'gpc_list') or not kvm.gpc_list:
        return
    
    if not hasattr(kvm, 'gpc_lock'):
        return
    
    with kvm.gpc_lock:
        gpc = kvm.gpc_list
        while gpc:
            with gpc.lock:
                if (gpc.valid and gpc.pfn != -1 and 
                    gpc.uhva >= start and gpc.uhva < end):
                    # Need write lock for invalidation
                    gpc.lock.release()
                    gpc.lock.acquire()  # Simulate write_lock_irq
                    
                    if (gpc.valid and gpc.pfn != -1 and
                        gpc.uhva >= start and gpc.uhva < end):
                        gpc.valid = False
                    
                    gpc.lock.release()
                    gpc.lock.acquire()  # Simulate write_unlock_irq
            
            gpc = gpc.list_next


# Helper for page handling
def kvm_release_page_clean(page: Any):
    """Release page after clean use"""
    pass


def kvm_release_page_unused(page: Any):
    """Release unused page"""
    pass


def kvm_is_error_hva(hva: int) -> bool:
    """Check if HVA is error"""
    return hva == -1


def kvm_is_error_gpa(gpa: int) -> bool:
    """Check if GPA is error"""
    return gpa == -1


def kvm_is_error_noslot_pfn(pfn: int) -> bool:
    """Check if PFN is error (no slot)"""
    return pfn == -2


def pfn_valid(pfn: int) -> bool:
    """Check if PFN is valid (has struct page)"""
    return pfn > 0


def pfn_to_page(pfn: int) -> Any:
    """Convert PFN to page struct (simplified)"""
    return pfn


def page_to_pfn(page: Any) -> int:
    """Convert page struct to PFN"""
    return page


def offset_in_page(addr: int) -> int:
    """Get offset within page"""
    return addr % 4096


def PAGE_ALIGN_DOWN(addr: int) -> int:
    """Align address down to page boundary"""
    return addr & ~(4096 - 1)


# Memory slot helpers
def gfn_to_memslot(kvm: Any, gfn: int) -> Optional[Any]:
    """Find memory slot for GFN"""
    if not hasattr(kvm, 'memslots'):
        return None
    
    for slot in getattr(kvm, 'memslots', []):
        if slot and slot.base_gfn <= gfn < slot.base_gfn + slot.npages:
            return slot
    return None


def gfn_to_hva_memslot(memslot: Any, gfn: int) -> int:
    """Convert GFN to HVA within memslot"""
    if not memslot:
        return -1
    
    offset = (gfn - memslot.base_gfn) * 4096
    return memslot.userspace_addr + offset


def gpa_to_gfn(gpa: int) -> int:
    """Convert GPA to GFN"""
    return gpa // 4096


def __gfn_to_memslot(slots: List[Any], gfn: int) -> Optional[Any]:
    """Internal GFN to memslot lookup"""
    for slot in slots:
        if slot and slot.base_gfn <= gfn < slot.base_gfn + slot.npages:
            return slot
    return None


def kvm_memslots(kvm: Any) -> List[Any]:
    """Get memory slots for VM"""
    return getattr(kvm, 'memslots', [])


# Memory attribute helpers
def kvm_arch_mmu_enable_log_dirty_pt_masked(kvm: Any, memslot: Any, 
                                             offset: int, mask: int):
    """Arch-specific: enable dirty logging for page mask"""
    pass


# Generation tracking for memslots
class KVM_Memory_Slots:
    """Memory slots container with generation"""
    
    def __init__(self):
        self.slots: List[Any] = []
        self.generation: int = 0
    
    def update_generation(self):
        self.generation += 1