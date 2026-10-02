"""
KVM Dirty Ring
==============

Python implementation of KVM dirty ring for dirty page tracking.
Based on linux/virt/kvm/dirty_ring.c
"""

import threading
import struct
from dataclasses import dataclass, field
from typing import Optional, List, Any
from collections import deque


# Constants
KVM_DIRTY_GFN_F_DIRTY = 0x01
KVM_DIRTY_GFN_F_RESET = 0x02
KVM_DIRTY_RING_RSVD_ENTRIES = 16
BITS_PER_LONG = 64


@dataclass
class KVMDirtyGFN:
    """Dirty GFN entry in the ring"""
    flags: int = 0
    slot: int = 0
    offset: int = 0


@dataclass
class KVMDirtyRing:
    """Dirty ring for tracking dirty pages"""
    dirty_gfns: List[KVMDirtyGFN] = field(default_factory=list)
    size: int = 0
    soft_limit: int = 0
    dirty_index: int = 0
    reset_index: int = 0
    index: int = 0  # Ring index (per vCPU)


def kvm_cpu_dirty_log_size(kvm: Any) -> int:
    """Arch-specific dirty log size (weak function)"""
    return 0


def kvm_dirty_ring_get_rsvd_entries(kvm: Any) -> int:
    """Get reserved entries for dirty ring"""
    return KVM_DIRTY_RING_RSVD_ENTRIES + kvm_cpu_dirty_log_size(kvm)


def kvm_use_dirty_bitmap(kvm: Any) -> bool:
    """Check if dirty bitmap should be used instead of dirty ring"""
    # Simplified - would check slots_lock in real implementation
    return not kvm.dirty_ring_size or kvm.dirty_ring_with_bitmap


def kvm_arch_allow_write_without_running_vcpu(kvm: Any) -> bool:
    """Arch-specific: allow write without running vCPU"""
    return False


def kvm_dirty_ring_used(ring: KVMDirtyRing) -> int:
    """Get number of used entries in dirty ring"""
    return ring.dirty_index - ring.reset_index


def kvm_dirty_ring_soft_full(ring: KVMDirtyRing) -> bool:
    """Check if dirty ring is soft full"""
    return kvm_dirty_ring_used(ring) >= ring.soft_limit


def kvm_dirty_ring_full(ring: KVMDirtyRing) -> bool:
    """Check if dirty ring is full"""
    return kvm_dirty_ring_used(ring) >= ring.size


def kvm_reset_dirty_gfn(kvm: Any, slot: int, offset: int, mask: int):
    """Reset dirty GFN in memslot"""
    # In real implementation, would call architecture-specific MMU function
    # Here we just simulate
    pass


def kvm_dirty_ring_alloc(kvm: Any, ring: KVMDirtyRing, index: int, size: int) -> int:
    """Allocate dirty ring"""
    # Round up to page size and make power of 2
    import math
    page_size = 4096
    entry_size = struct.calcsize('QQI')  # Approximate size of KVMDirtyGFN
    num_entries = max(64, size // entry_size)
    
    # Round up to next power of 2
    num_entries = 1 << (num_entries - 1).bit_length()
    
    ring.dirty_gfns = [KVMDirtyGFN() for _ in range(num_entries)]
    ring.size = num_entries
    ring.soft_limit = ring.size - kvm_dirty_ring_get_rsvd_entries(kvm)
    ring.dirty_index = 0
    ring.reset_index = 0
    ring.index = index
    
    return 0


def kvm_dirty_gfn_set_invalid(gfn: KVMDirtyGFN):
    """Mark GFN as invalid"""
    gfn.flags = 0


def kvm_dirty_gfn_set_dirtied(gfn: KVMDirtyGFN):
    """Mark GFN as dirtied"""
    gfn.flags = KVM_DIRTY_GFN_F_DIRTY


def kvm_dirty_gfn_harvested(gfn: KVMDirtyGFN) -> bool:
    """Check if GFN has been harvested"""
    return (gfn.flags & KVM_DIRTY_GFN_F_RESET) != 0


def kvm_dirty_ring_reset(kvm: Any, ring: KVMDirtyRing, 
                         nr_entries_reset: List[int]) -> int:
    """
    Reset harvested dirty ring entries.
    Batch resets for GFNs in the same slot that are close together.
    """
    # In real implementation, would hold slots_lock
    cur_slot = 0
    cur_offset = 0
    mask = 0
    
    while nr_entries_reset[0] < 2**31 - 1:  # INT_MAX
        # Check for signals (simplified)
        # if signal_pending(current): return -EINTR
        
        idx = ring.reset_index & (ring.size - 1)
        entry = ring.dirty_gfns[idx]
        
        if not kvm_dirty_gfn_harvested(entry):
            break
        
        next_slot = entry.slot
        next_offset = entry.offset
        
        # Mark as reset
        kvm_dirty_gfn_set_invalid(entry)
        ring.reset_index += 1
        nr_entries_reset[0] += 1
        
        if mask:
            # Try to coalesce with current batch
            if next_slot == cur_slot:
                delta = next_offset - cur_offset
                if 0 <= delta < BITS_PER_LONG:
                    mask |= 1 << delta
                    continue
                # Backwards visit
                if -BITS_PER_LONG < delta < 0 and \
                   (mask << -delta >> -delta) == mask:
                    cur_offset = next_offset
                    mask = (mask << -delta) | 1
                    continue
            
            # Flush current batch
            kvm_reset_dirty_gfn(kvm, cur_slot, cur_offset, mask)
        
        # Start new batch
        cur_slot = next_slot
        cur_offset = next_offset
        mask = 1
    
    # Flush final batch
    if mask:
        kvm_reset_dirty_gfn(kvm, cur_slot, cur_offset, mask)
    
    return 0


def kvm_dirty_ring_push(vcpu: Any, slot: int, offset: int):
    """Push a dirty GFN to the ring"""
    ring = vcpu.dirty_ring
    
    # Should never be full
    assert not kvm_dirty_ring_full(ring), "Dirty ring full"
    
    idx = ring.dirty_index & (ring.size - 1)
    entry = ring.dirty_gfns[idx]
    
    entry.slot = slot
    entry.offset = offset
    
    # Memory barrier (smp_wmb)
    # In Python, list assignment provides ordering
    
    kvm_dirty_gfn_set_dirtied(entry)
    ring.dirty_index += 1
    
    # Check soft limit
    if kvm_dirty_ring_soft_full(ring):
        kvm_make_request(0x100, vcpu)  # KVM_REQ_DIRTY_RING_SOFT_FULL


def kvm_dirty_ring_check_request(vcpu: Any) -> bool:
    """Check if dirty ring request is pending"""
    # Check for KVM_REQ_DIRTY_RING_SOFT_FULL
    if hasattr(vcpu, 'requests') and (vcpu.requests & 0x100):
        if kvm_dirty_ring_soft_full(vcpu.dirty_ring):
            vcpu.requests |= 0x100
            if hasattr(vcpu, 'run') and vcpu.run:
                vcpu.run.exit_reason = 31  # KVM_EXIT_DIRTY_RING_FULL
            return True
    return False


def kvm_dirty_ring_get_page(ring: KVMDirtyRing, offset: int) -> Any:
    """Get page for dirty ring offset"""
    # In real implementation: vmalloc_to_page
    return None


def kvm_dirty_ring_free(ring: KVMDirtyRing):
    """Free dirty ring"""
    ring.dirty_gfns.clear()
    ring.dirty_gfns = []


def kvm_make_request(req: int, vcpu: Any):
    """Make a request to vCPU"""
    if not hasattr(vcpu, 'requests'):
        vcpu.requests = 0
    vcpu.requests |= req


# Helper to create dirty ring for a vCPU
def create_vcpu_dirty_ring(kvm: Any, vcpu: Any, size: int = 4096) -> KVMDirtyRing:
    """Create and initialize a dirty ring for a vCPU"""
    ring = KVMDirtyRing()
    vcpu.dirty_ring = ring
    kvm_dirty_ring_alloc(kvm, ring, vcpu.vcpu_id, size)
    return ring