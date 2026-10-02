"""
UmerOS KVM Python Implementation
=================================

A Python port of the Linux Kernel KVM (Kernel-based Virtual Machine) subsystem.
This module provides core KVM functionality including:

- VM and vCPU management
- Memory management (slots, dirty logging, dirty rings)
- Interrupt routing and IRQ chips
- Asynchronous page fault handling
- Coalesced MMIO
- Binary statistics
- VFIO device integration
- Guest memory file descriptors (guest_memfd)
- Page frame number caching

Based on Linux kernel source: https://github.com/torvalds/linux/tree/master/virt/kvm
"""

from .kvm_main import (
    KVM,
    KVMMemorySlot,
    KVMVCPU,
    KVMRun,
    KVM_EXIT_REASONS,
    KVM_MAX_VCPUS,
    KVM_MAX_MEM_SLOTS,
    KVM_PAGE_SIZE,
)

from .async_pf import (
    KVMAsyncPF,
    KVMAsyncPFWork,
    ASYNC_PF_PER_VCPU,
)

from .coalesced_mmio import (
    KVMCoalescedMMIODev,
    KVMCoalescedMMIORing,
    KVM_COALESCED_MMIO_MAX,
)

from .binary_stats import (
    KVMStatsHeader,
    KVMStatsDesc,
    KVM_STATS_NAME_SIZE,
    kvm_stats_read,
)

from .dirty_ring import (
    KVMDirtyRing,
    KVMDirtyGFN,
    KVM_DIRTY_GFN_F_DIRTY,
    KVM_DIRTY_GFN_F_RESET,
    KVM_DIRTY_RING_RSVD_ENTRIES,
)

from .irqchip import (
    KVMKernelIrqRoutingEntry,
    KVM_Irq_Routing_Table,
    KVM_IRQ_ROUTING_MSI,
    KVM_IRQ_ROUTING_IRQCHIP,
    KVM_MAX_IRQ_ROUTES,
    KVM_NR_IRQCHIPS,
    KVM_IRQCHIP_NUM_PINS,
)

from .eventfd import (
    KVMEventFD,
    KVMIOEventFD,
    KVMVirqFD,
    KVMEventFDFlags,
)

from .guest_memfd import (
    KVMGuestMemfd,
    KVMCreateGuestMemfd,
    KVM_GMEM_FLAGS,
)

from .pfncache import (
    GFNToPFNCache,
    KVM_PFN_ERR_FAULT,
    INVALID_GPA,
    KVM_HVA_ERR_BAD,
)

from .vfio import (
    KVMVFIO,
    KVMVFIOFile,
    KVM_DEV_VFIO_FILE_ADD,
    KVM_DEV_VFIO_FILE_DEL,
)

from .kvm_mm import (
    KVMFollowPFN,
    KVM_MMU_LOCK,
    KVM_MMU_UNLOCK,
    KVM_MMU_LOCK_INIT,
)

__version__ = "1.0.0"
__author__ = "UmerOS Team"
__license__ = "GPL-2.0"

__all__ = [
    # Main KVM types
    "KVM",
    "KVMMemorySlot",
    "KVMVCPU",
    "KVMRun",
    "KVM_EXIT_REASONS",
    "KVM_MAX_VCPUS",
    "KVM_MAX_MEM_SLOTS",
    "KVM_PAGE_SIZE",
    # Async PF
    "KVMAsyncPF",
    "KVMAsyncPFWork",
    "ASYNC_PF_PER_VCPU",
    # Coalesced MMIO
    "KVMCoalescedMMIODev",
    "KVMCoalescedMMIORing",
    "KVM_COALESCED_MMIO_MAX",
    # Binary Stats
    "KVMStatsHeader",
    "KVMStatsDesc",
    "KVM_STATS_NAME_SIZE",
    "kvm_stats_read",
    # Dirty Ring
    "KVMDirtyRing",
    "KVMDirtyGFN",
    "KVM_DIRTY_GFN_F_DIRTY",
    "KVM_DIRTY_GFN_F_RESET",
    "KVM_DIRTY_RING_RSVD_ENTRIES",
    # IRQ Chip
    "KVMKernelIrqRoutingEntry",
    "KVM_Irq_Routing_Table",
    "KVM_IRQ_ROUTING_MSI",
    "KVM_IRQ_ROUTING_IRQCHIP",
    "KVM_MAX_IRQ_ROUTES",
    "KVM_NR_IRQCHIPS",
    "KVM_IRQCHIP_NUM_PINS",
    # EventFD
    "KVMEventFD",
    "KVMIOEventFD",
    "KVMVirqFD",
    "KVMEventFDFlags",
    # Guest Memfd
    "KVMGuestMemfd",
    "KVMCreateGuestMemfd",
    "KVM_GMEM_FLAGS",
    # PFN Cache
    "GFNToPFNCache",
    "KVM_PFN_ERR_FAULT",
    "INVALID_GPA",
    "KVM_HVA_ERR_BAD",
    # VFIO
    "KVMVFIO",
    "KVMVFIOFile",
    "KVM_DEV_VFIO_FILE_ADD",
    "KVM_DEV_VFIO_FILE_DEL",
    # Memory Management
    "KVMFollowPFN",
    "KVM_MMU_LOCK",
    "KVM_MMU_UNLOCK",
    "KVM_MMU_LOCK_INIT",
]