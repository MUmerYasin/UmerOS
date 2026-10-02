"""
KVM Page Frame Number Cache (gfn_to_pfn_cache)
===============================================

Python implementation of KVM PFN cache for fast guest memory access.
Based on linux/virt/kvm/pfncache.c
"""

import threading
import mmap
import os
from dataclasses import dataclass, field
from typing import Optional, Any, List
from enum import IntEnum


# Error codes
KVM_PFN_ERR_FAULT = -1
INVALID_GPA = -1
KVM_HVA_ERR_BAD = -1
KVM_PFN_ERR_NOSLOT = -2

# Page size
PAGE_SIZE = 4096


class KVMPageFlags(IntEnum):
    """Page flags"""
    NONE = 0
    WRITE = 1
    PIN = 2


@dataclass
class KVMFollowPFN:
    """Follow PFN parameters"""
    slot: Optional[Any] = None
    gfn: int = 0
    flags: int = 0
    hva: int = 0
    pin: bool = False
    map_writable: Optional[bool] = None
    refcounted_page: Optional[Any] = None


@dataclass
class GFNToPFNCache:
    """GFN to PFN cache entry"""
    kvm: Optional[Any] = None
    lock: threading.RLock = field(default_factory=threading.RLock)
    refresh_lock: threading.Lock = field(default_factory=threading.Lock)
    
    # Cache state
    active: bool = False
    valid: bool = False
    
    # Address info
    gpa: int = INVALID_GPA
    generation: int = 0
    memslot: Optional[Any] = None
    uhva: int = KVM_HVA_ERR_BAD
    
    # Cached PFN and kernel mapping
    pfn: int = KVM_PFN_ERR_FAULT
    khva: int = 0
    
    # For list management
    list_next: Optional['GFNToPFNCache'] = None
    list_prev: Optional['GFNToPFNCache'] = None


def kvm_gpc_is_valid_len(gpa: int, uhva: int, length: int) -> bool:
    """Check if cached access fits within a single page"""
    if gpa == INVALID_GPA:
        offset = uhva % PAGE_SIZE
    else:
        offset = gpa % PAGE_SIZE
    
    return offset + length <= PAGE_SIZE


def kvm_gpc_check(gpc: GFNToPFNCache, length: int) -> bool:
    """Check if cache entry is valid"""
    if not gpc.active:
        return False
    
    # Check memslot generation
    if gpc.gpa != INVALID_GPA:
        if not gpc.kvm:
            return False
        slots = getattr(gpc.kvm, 'memslots', lambda: None)()
        if slots and gpc.generation != getattr(slots, 'generation', 0):
            return False
    
    if gpc.uhva == KVM_HVA_ERR_BAD:
        return False
    
    if not kvm_gpc_is_valid_len(gpc.gpa, gpc.uhva, length):
        return False
    
    if not gpc.valid:
        return False
    
    return True


def gpc_map(pfn: int) -> int:
    """Map PFN to kernel virtual address (simplified)"""
    # In real kernel: kmap() or memremap()
    # Here we return a pseudo-address
    return pfn * PAGE_SIZE + 0xFFFF000000000000


def gpc_unmap(pfn: int, khva: int):
    """Unmap kernel virtual address"""
    # In real kernel: kunmap() or memunmap()
    pass


def mmu_notifier_retry_cache(kvm: Any, mmu_seq: int) -> bool:
    """Check if MMU notifier requires cache retry"""
    if getattr(kvm, 'mn_active_invalidate_count', 0) > 0:
        return True
    
    # Memory barrier (smp_rmb)
    return getattr(kvm, 'mmu_invalidate_seq', 0) != mmu_seq


def hva_to_pfn(kfp: KVMFollowPFN) -> int:
    """Convert HVA to PFN (simplified)"""
    # In real kernel: get_user_pages + page_to_pfn
    # Here we simulate
    if kfp.hva == KVM_HVA_ERR_BAD:
        return KVM_PFN_ERR_FAULT
    
    # Simulate successful mapping
    return kfp.hva // PAGE_SIZE


def hva_to_pfn_retry(gpc: GFNToPFNCache) -> int:
    """Retry HVA to PFN conversion with MMU notifier handling"""
    old_khva = gpc.khva & ~(PAGE_SIZE - 1) if gpc.khva else 0
    new_pfn = KVM_PFN_ERR_FAULT
    new_khva = 0
    
    # Prepare follow PFN parameters
    kfp = KVMFollowPFN()
    kfp.hva = gpc.uhva
    kfp.flags = 1  # FOLL_WRITE
    
    # In real kernel, this would be more complex with proper locking
    # Simplified version:
    with gpc.lock:
        gpc.valid = False
        
        # Try to get new PFN
        mmu_seq = getattr(gpc.kvm, 'mmu_invalidate_seq', 0)
        
        # Release lock for potentially blocking operations
        gpc.lock.release()
        try:
            # Unmap old if different
            if new_pfn != KVM_PFN_ERR_FAULT and new_khva != old_khva:
                gpc_unmap(new_pfn, new_khva)
            
            # Get new PFN
            new_pfn = hva_to_pfn(kfp)
            
            if new_pfn == KVM_PFN_ERR_FAULT:
                gpc.lock.acquire()
                return -14  # EFAULT
            
            # Map new PFN
            new_khva = gpc_map(new_pfn)
            if not new_khva:
                gpc.lock.acquire()
                return -14
            
        finally:
            gpc.lock.acquire()
        
        # Check for MMU notifier retry
        if mmu_notifier_retry_cache(gpc.kvm, mmu_seq):
            # Retry loop would go here in real implementation
            pass
        
        # Update cache
        gpc.valid = True
        gpc.pfn = new_pfn
        gpc.khva = new_khva + (gpc.uhva % PAGE_SIZE)
    
    return 0


def __kvm_gpc_refresh(gpc: GFNToPFNCache, gpa: int, uhva: int) -> int:
    """Internal refresh function"""
    page_offset = 0
    unmap_old = False
    old_uhva = 0
    old_pfn = gpc.pfn
    hva_change = False
    
    # Validate parameters
    if (gpa == INVALID_GPA) == (uhva == KVM_HVA_ERR_BAD):
        return -22  # EINVAL
    
    # refresh_lock is already held by caller (__kvm_gpc_activate)
    with gpc.lock:
        if not gpc.active:
            return -22
        
        old_pfn = gpc.pfn
        old_khva = gpc.khva & ~(PAGE_SIZE - 1) if gpc.khva else 0
        old_uhva = gpc.uhva & ~(PAGE_SIZE - 1)
        
        if gpa == INVALID_GPA:
            # HVA-based cache
            page_offset = uhva % PAGE_SIZE
            gpc.gpa = INVALID_GPA
            gpc.memslot = None
            gpc.uhva = uhva & ~(PAGE_SIZE - 1)
            if gpc.uhva != old_uhva:
                hva_change = True
        else:
            # GPA-based cache
            page_offset = gpa % PAGE_SIZE
            if gpc.kvm:
                slots = gpc.kvm.memslots() if callable(getattr(gpc.kvm, 'memslots', None)) else None
                if slots:
                    if gpc.gpa != gpa or gpc.generation != getattr(slots, 'generation', 0):
                        gfn = gpa // PAGE_SIZE
                        gpc.gpa = gpa
                        gpc.generation = slots.generation
                        # Find memslot (simplified)
                        gpc.memslot = None
                        gpc.uhva = 0  # Would compute from memslot
                        if gpc.uhva == KVM_HVA_ERR_BAD:
                            return -14
                        if gpc.uhva != old_uhva:
                            hva_change = True
                    else:
                        gpc.uhva = old_uhva
        
        gpc.uhva += page_offset
        
        if not gpc.valid or hva_change:
            # Drop lock and retry
            gpc.lock.release()
            try:
                ret = hva_to_pfn_retry(gpc)
            finally:
                gpc.lock.acquire()
        else:
            # Just update offset within page
            gpc.khva = old_khva + page_offset
            ret = 0
    
    # Invalidate the cache and purge the pfn/khva if the refresh failed.
    # Some/all of the uhva, gpa, and memslot generation info may still be
    # valid, leave it as is.
    if ret:
        gpc.valid = False
        gpc.pfn = KVM_PFN_ERR_FAULT
        gpc.khva = None
    
    # Detect a pfn change before dropping the lock!
    unmap_old = (old_pfn != gpc.pfn)
    
    if unmap_old:
        gpc_unmap(old_pfn, old_khva)
    
    return ret


def kvm_gpc_refresh(gpc: GFNToPFNCache, length: int) -> int:
    """Refresh cache entry"""
    if not kvm_gpc_is_valid_len(gpc.gpa, gpc.uhva, length):
        return -22
    
    # For GPA-based caches, ignore passed HVA
    uhva = gpc.uhva if gpc.gpa == INVALID_GPA else KVM_HVA_ERR_BAD
    
    return __kvm_gpc_refresh(gpc, gpc.gpa, uhva)


def kvm_gpc_init(gpc: GFNToPFNCache, kvm: Any):
    """Initialize cache entry"""
    gpc.kvm = kvm
    gpc.lock = threading.RLock()
    gpc.refresh_lock = threading.Lock()
    gpc.pfn = KVM_PFN_ERR_FAULT
    gpc.gpa = INVALID_GPA
    gpc.uhva = KVM_HVA_ERR_BAD
    gpc.active = False
    gpc.valid = False
    
    # Add to VM's GPC list
    if kvm and hasattr(kvm, 'gpc_list'):
        with getattr(kvm, 'gpc_lock', threading.Lock()):
            gpc.list_next = kvm.gpc_list
            if kvm.gpc_list:
                kvm.gpc_list.list_prev = gpc
            kvm.gpc_list = gpc


def __kvm_gpc_activate(gpc: GFNToPFNCache, gpa: int, uhva: int, length: int) -> int:
    """Internal activate function"""
    if not kvm_gpc_is_valid_len(gpa, uhva, length):
        return -22
    
    if not gpc.active:
        # Initialize locks
        if not hasattr(gpc, 'lock') or gpc.lock is None:
            gpc.lock = threading.RLock()
        if not hasattr(gpc, 'refresh_lock') or gpc.refresh_lock is None:
            gpc.refresh_lock = threading.RLock()  # Use RLock for reentrancy
        
        if gpc.valid:
            return -5  # EIO
        
        # Add to VM's GPC list
        if gpc.kvm:
            with getattr(gpc.kvm, 'gpc_lock', threading.Lock()):
                gpc.list_next = gpc.kvm.gpc_list
                if gpc.kvm.gpc_list:
                    gpc.kvm.gpc_list.list_prev = gpc
                gpc.kvm.gpc_list = gpc
        
        # Activate
        with gpc.lock:
            gpc.active = True
    
    return __kvm_gpc_refresh(gpc, gpa, uhva)


def kvm_gpc_activate(gpc: GFNToPFNCache, gpa: int, length: int) -> int:
    """Activate GPA-based cache"""
    if gpa == INVALID_GPA:
        return -22
    return __kvm_gpc_activate(gpc, gpa, KVM_HVA_ERR_BAD, length)


def kvm_gpc_activate_hva(gpc: GFNToPFNCache, uhva: int, length: int) -> int:
    """Activate HVA-based cache"""
    # Check access permissions (simplified)
    if uhva == KVM_HVA_ERR_BAD:
        return -22
    return __kvm_gpc_activate(gpc, INVALID_GPA, uhva, length)


def kvm_gpc_deactivate(gpc: GFNToPFNCache):
    """Deactivate cache entry"""
    if not gpc.kvm:
        return
    
    with gpc.refresh_lock:
        if gpc.active:
            # Deactivate
            with gpc.lock:
                gpc.active = False
                gpc.valid = False
                
                old_khva = gpc.khva - (gpc.khva % PAGE_SIZE) if gpc.khva else 0
                gpc.khva = 0
                old_pfn = gpc.pfn
                gpc.pfn = KVM_PFN_ERR_FAULT
            
            # Remove from VM's GPC list
            with getattr(gpc.kvm, 'gpc_lock', threading.Lock()):
                if gpc.list_prev:
                    gpc.list_prev.list_next = gpc.list_next
                if gpc.list_next:
                    gpc.list_next.list_prev = gpc.list_prev
                if gpc.kvm.gpc_list == gpc:
                    gpc.kvm.gpc_list = gpc.list_next
            
            gpc.list_next = None
            gpc.list_prev = None
            
            # Unmap
            gpc_unmap(old_pfn, old_khva)


def kvm_gpc_get_khva(gpc: GFNToPFNCache) -> int:
    """Get kernel virtual address from cache (with validation)"""
    with gpc.lock:
        if gpc.valid:
            return gpc.khva
        return 0


def kvm_gpc_get_pfn(gpc: GFNToPFNCache) -> int:
    """Get PFN from cache (with validation)"""
    with gpc.lock:
        if gpc.valid:
            return gpc.pfn
        return KVM_PFN_ERR_FAULT


# High-level cache usage helpers
class GPCContext:
    """Context manager for using a GPC"""
    
    def __init__(self, gpc: GFNToPFNCache, length: int):
        self.gpc = gpc
        self.length = length
        self.khva = 0
    
    def __enter__(self) -> int:
        if kvm_gpc_check(self.gpc, self.length):
            with self.gpc.lock:
                self.khva = self.gpc.khva
                return self.khva
        
        # Need to refresh
        ret = kvm_gpc_refresh(self.gpc, self.length)
        if ret == 0:
            with self.gpc.lock:
                self.khva = self.gpc.khva
                return self.khva
        return 0
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass  # No cleanup needed, cache stays valid


def create_gpc(kvm: Any, gpa: int = INVALID_GPA, 
               uhva: int = KVM_HVA_ERR_BAD, length: int = PAGE_SIZE) -> GFNToPFNCache:
    """Create and activate a new GPC"""
    gpc = GFNToPFNCache()
    kvm_gpc_init(gpc, kvm)
    
    if gpa != INVALID_GPA:
        kvm_gpc_activate(gpc, gpa, length)
    else:
        kvm_gpc_activate_hva(gpc, uhva, length)
    
    return gpc