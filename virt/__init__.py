"""
UmerOS Virt - Virtualization Subsystem
======================================

Python implementation of Linux kernel's virt/ subsystem.
Contains KVM (Kernel-based Virtual Machine) and common virtualization utilities.

Based on linux/virt/
"""

# KVM subsystem
from .kvm import (
    # Main KVM types
    KVM,
    KVMMemorySlot,
    KVMVCPU,
    KVMRun,
    KVM_EXIT_REASONS,
    KVM_MAX_VCPUS,
    KVM_MAX_MEM_SLOTS,
    KVM_PAGE_SIZE,
    # Async PF
    KVMAsyncPF,
    KVMAsyncPFWork,
    ASYNC_PF_PER_VCPU,
    kvm_async_pf_init,
    kvm_async_pf_deinit,
    kvm_async_pf_vcpu_init,
    # Coalesced MMIO
    KVMCoalescedMMIOZone,
    KVMCoalescedMMIODev,
    KVMCoalescedMMIORing,
    KVM_COALESCED_MMIO_MAX,
    kvm_coalesced_mmio_init,
    kvm_coalesced_mmio_free,
    kvm_vm_ioctl_register_coalesced_mmio,
    kvm_vm_ioctl_unregister_coalesced_mmio,
    # Binary Stats
    KVMStatsHeader,
    KVMStatsDesc,
    KVM_STATS_NAME_SIZE,
    kvm_stats_read,
    KVM_STATS_TYPE_CUMULATIVE,
    KVM_STATS_TYPE_INSTANT,
    KVM_STATS_UNIT_BYTES,
    # Dirty Ring
    KVMDirtyRing,
    KVMDirtyGFN,
    KVM_DIRTY_GFN_F_DIRTY,
    KVM_DIRTY_GFN_F_RESET,
    KVM_DIRTY_RING_RSVD_ENTRIES,
    kvm_dirty_ring_alloc,
    kvm_dirty_ring_used,
    kvm_dirty_ring_soft_full,
    kvm_dirty_ring_full,
    kvm_dirty_ring_reset,
    kvm_dirty_ring_push,
    kvm_dirty_ring_free,
    # IRQ Chip
    KVMKernelIrqRoutingEntry,
    KVM_Irq_Routing_Table,
    KVM_IRQ_ROUTING_MSI,
    KVM_IRQ_ROUTING_IRQCHIP,
    KVM_MAX_IRQ_ROUTES,
    KVM_NR_IRQCHIPS,
    KVM_IRQCHIP_NUM_PINS,
    # EventFD
    KVMEventFD,
    KVMIOEventFD,
    KVMVirqFD,
    KVMEventFDFlags,
    # Guest Memfd
    KVMGuestMemfd,
    KVMCreateGuestMemfd,
    KVM_GMEM_FLAGS,
    kvm_gmem_init,
    kvm_gmem_exit,
    kvm_gmem_create,
    kvm_gmem_bind,
    kvm_gmem_unbind,
    # PFN Cache
    GFNToPFNCache,
    KVM_PFN_ERR_FAULT,
    INVALID_GPA,
    KVM_HVA_ERR_BAD,
    kvm_gpc_init,
    kvm_gpc_activate,
    kvm_gpc_activate_hva,
    kvm_gpc_deactivate,
    # VFIO
    KVMVFIO,
    KVMVFIOFile,
    KVM_DEV_VFIO_FILE_ADD,
    KVM_DEV_VFIO_FILE_DEL,
    kvm_vfio_ops_init,
    kvm_vfio_ops_exit,
    # Memory Management
    KVMFollowPFN,
    KVM_MMU_LOCK,
    KVM_MMU_UNLOCK,
    KVM_MMU_LOCK_INIT,
)

# Common virtualization library
from .lib import (
    IRQBypassProducer,
    IRQBypassConsumer,
    IRQBypassManager,
    EventFDContext,
    irq_bypass_register_producer,
    irq_bypass_unregister_producer,
    irq_bypass_register_consumer,
    irq_bypass_unregister_consumer,
    get_global_manager,
    set_global_manager,
    EINVAL,
    ENOMEM,
)

__version__ = "1.0.0"
__author__ = "UmerOS"
__license__ = "GPL-3.0"

__all__ = [
    # KVM subsystem
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
    "kvm_async_pf_init",
    "kvm_async_pf_deinit",
    "kvm_async_pf_vcpu_init",
    # Coalesced MMIO
    "KVMCoalescedMMIOZone",
    "KVMCoalescedMMIODev",
    "KVMCoalescedMMIORing",
    "KVM_COALESCED_MMIO_MAX",
    "kvm_coalesced_mmio_init",
    "kvm_coalesced_mmio_free",
    "kvm_vm_ioctl_register_coalesced_mmio",
    "kvm_vm_ioctl_unregister_coalesced_mmio",
    # Binary Stats
    "KVMStatsHeader",
    "KVMStatsDesc",
    "KVM_STATS_NAME_SIZE",
    "kvm_stats_read",
    "KVM_STATS_TYPE_CUMULATIVE",
    "KVM_STATS_TYPE_INSTANT",
    "KVM_STATS_UNIT_BYTES",
    # Dirty Ring
    "KVMDirtyRing",
    "KVMDirtyGFN",
    "KVM_DIRTY_GFN_F_DIRTY",
    "KVM_DIRTY_GFN_F_RESET",
    "KVM_DIRTY_RING_RSVD_ENTRIES",
    "kvm_dirty_ring_alloc",
    "kvm_dirty_ring_used",
    "kvm_dirty_ring_soft_full",
    "kvm_dirty_ring_full",
    "kvm_dirty_ring_reset",
    "kvm_dirty_ring_push",
    "kvm_dirty_ring_free",
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
    "kvm_gmem_init",
    "kvm_gmem_exit",
    "kvm_gmem_create",
    "kvm_gmem_bind",
    "kvm_gmem_unbind",
    # PFN Cache
    "GFNToPFNCache",
    "KVM_PFN_ERR_FAULT",
    "INVALID_GPA",
    "KVM_HVA_ERR_BAD",
    "kvm_gpc_init",
    "kvm_gpc_activate",
    "kvm_gpc_activate_hva",
    "kvm_gpc_deactivate",
    # VFIO
    "KVMVFIO",
    "KVMVFIOFile",
    "KVM_DEV_VFIO_FILE_ADD",
    "KVM_DEV_VFIO_FILE_DEL",
    "kvm_vfio_ops_init",
    "kvm_vfio_ops_exit",
    # Memory Management
    "KVMFollowPFN",
    "KVM_MMU_LOCK",
    "KVM_MMU_UNLOCK",
    "KVM_MMU_LOCK_INIT",
    # Common lib
    "IRQBypassProducer",
    "IRQBypassConsumer",
    "IRQBypassManager",
    "EventFDContext",
    "irq_bypass_register_producer",
    "irq_bypass_unregister_producer",
    "irq_bypass_register_consumer",
    "irq_bypass_unregister_consumer",
    "get_global_manager",
    "set_global_manager",
    "EINVAL",
    "ENOMEM",
]