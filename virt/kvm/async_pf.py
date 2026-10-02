"""
KVM Asynchronous Page Fault Handling
=====================================

Python implementation of KVM async PF support.
Based on linux/virt/kvm/async_pf.c and async_pf.h
"""

import threading
import queue
from dataclasses import dataclass, field
from typing import Optional, List, Any
from enum import IntEnum
from collections import deque
import time


# Constants
ASYNC_PF_PER_VCPU = 64
KVM_ASYNC_PF_SYNC = True  # Configuration option


class KVMAsyncPFWorkState(IntEnum):
    QUEUED = 0
    EXECUTING = 1
    DONE = 2
    WAKEUP_ALL = 3


@dataclass
class KVMArchAsyncPF:
    """Architecture-specific async PF data"""
    # Placeholder for arch-specific fields
    pass


@dataclass
class KVMAsyncPFWork:
    """Async PF work item"""
    work_queue: 'queue.Queue' = field(default_factory=queue.Queue)
    vcpu: Optional['KVMVCPU'] = None
    cr2_or_gpa: int = 0
    addr: int = 0  # Host virtual address
    arch: KVMArchAsyncPF = field(default_factory=KVMArchAsyncPF)
    wakeup_all: bool = False
    notpresent_injected: bool = False
    state: KVMAsyncPFWorkState = KVMAsyncPFWorkState.QUEUED
    link: Optional['KVMAsyncPFWork'] = None  # For linked lists
    queue_entry: Optional['KVMAsyncPFWork'] = None  # For queue
    
    def __post_init__(self):
        self.work_queue = queue.Queue()


@dataclass
class KVMAsyncPF:
    """Per-vCPU async PF state"""
    done: deque = field(default_factory=deque)      # Completed work
    queue: deque = field(default_factory=deque)     # Pending work
    lock: threading.Lock = field(default_factory=threading.Lock)
    queued: int = 0


class KVMAsyncPFManager:
    """Manages async PF subsystem"""
    
    def __init__(self):
        self.work_cache: List[KVMAsyncPFWork] = []
        self.cache_lock = threading.Lock()
        self.initialized = False
    
    def init(self) -> int:
        """Initialize async PF subsystem"""
        if self.initialized:
            return 0
        
        # Pre-allocate work items (like kmem_cache)
        for _ in range(256):
            self.work_cache.append(KVMAsyncPFWork())
        
        self.initialized = True
        return 0
    
    def deinit(self):
        """Deinitialize async PF subsystem"""
        with self.cache_lock:
            self.work_cache.clear()
        self.initialized = False
    
    def alloc_work(self) -> Optional[KVMAsyncPFWork]:
        """Allocate a work item from cache"""
        with self.cache_lock:
            if self.work_cache:
                return self.work_cache.pop()
        return KVMAsyncPFWork()  # Fallback
    
    def free_work(self, work: KVMAsyncPFWork):
        """Return work item to cache"""
        with self.cache_lock:
            if len(self.work_cache) < 256:
                # Reset work item
                work.vcpu = None
                work.cr2_or_gpa = 0
                work.addr = 0
                work.arch = KVMArchAsyncPF()
                work.wakeup_all = False
                work.notpresent_injected = False
                work.state = KVMAsyncPFWorkState.QUEUED
                work.link = None
                work.queue_entry = None
                while not work.work_queue.empty():
                    try:
                        work.work_queue.get_nowait()
                    except queue.Empty:
                        break
                self.work_cache.append(work)


# Global manager instance
_async_pf_manager = KVMAsyncPFManager()


def kvm_async_pf_init() -> int:
    """Initialize async PF"""
    return _async_pf_manager.init()


def kvm_async_pf_deinit():
    """Deinitialize async PF"""
    _async_pf_manager.deinit()


def kvm_async_pf_vcpu_init(vcpu: 'KVMVCPU'):
    """Initialize per-vCPU async PF state"""
    vcpu.async_pf = KVMAsyncPF()


def async_pf_execute(work: KVMAsyncPFWork):
    """Execute async PF work item"""
    vcpu = work.vcpu
    if not vcpu or not vcpu.kvm:
        return
    
    # Simulate getting user pages
    # In real kernel: get_user_pages_remote()
    # Here we just mark as done
    
    # Notify vCPU
    if KVM_ASYNC_PF_SYNC:
        kvm_arch_async_page_present(vcpu, work)
    
    with vcpu.async_pf.lock:
        first = len(vcpu.async_pf.done) == 0
        vcpu.async_pf.done.append(work)
        work.state = KVMAsyncPFWorkState.DONE
    
    # Mark work as potentially freed
    work.vcpu = None
    
    if not KVM_ASYNC_PF_SYNC and first:
        kvm_arch_async_page_present_queued(vcpu)
    
    # Wake up vCPU
    _kvm_vcpu_wake_up(vcpu)


def kvm_flush_and_free_async_pf_work(work: KVMAsyncPFWork):
    """Flush and free async PF work"""
    if work.wakeup_all:
        # Wake all - no work queue to flush
        pass
    else:
        # Wait for work to complete
        try:
            work.work_queue.get(timeout=5.0)
        except queue.Empty:
            pass
    
    _async_pf_manager.free_work(work)


def kvm_clear_async_pf_completion_queue(vcpu: 'KVMVCPU'):
    """Clear async PF completion queue"""
    # Cancel outstanding work
    while vcpu.async_pf.queue:
        work = vcpu.async_pf.queue.popleft()
        if KVM_ASYNC_PF_SYNC:
            # Flush work
            try:
                work.work_queue.get(timeout=1.0)
            except queue.Empty:
                pass
        else:
            # Try to cancel
            if not work.work_queue.empty():
                _async_pf_manager.free_work(work)
    
    with vcpu.async_pf.lock:
        while vcpu.async_pf.done:
            work = vcpu.async_pf.done.popleft()
            kvm_flush_and_free_async_pf_work(work)
    
    vcpu.async_pf.queued = 0


def kvm_check_async_pf_completion(vcpu: 'KVMVCPU'):
    """Check and process completed async PFs"""
    from .irqchip import kvm_arch_can_dequeue_async_page_present
    from .irqchip import kvm_arch_async_page_ready
    
    while (vcpu.async_pf.done and 
           kvm_arch_can_dequeue_async_page_present(vcpu)):
        
        with vcpu.async_pf.lock:
            if not vcpu.async_pf.done:
                break
            work = vcpu.async_pf.done.popleft()
        
        kvm_arch_async_page_ready(vcpu, work)
        
        if not KVM_ASYNC_PF_SYNC:
            kvm_arch_async_page_present(vcpu, work)
        
        vcpu.async_pf.queued -= 1
        kvm_flush_and_free_async_pf_work(work)


def kvm_setup_async_pf(vcpu: 'KVMVCPU', cr2_or_gpa: int, 
                       hva: int, arch: KVMArchAsyncPF) -> bool:
    """Try to schedule async PF"""
    if vcpu.async_pf.queued >= ASYNC_PF_PER_VCPU:
        return False
    
    # Check for error HVA
    if hva == -1:  # KVM_HVA_ERR_BAD
        return False
    
    work = _async_pf_manager.alloc_work()
    if not work:
        return False
    
    work.wakeup_all = False
    work.vcpu = vcpu
    work.cr2_or_gpa = cr2_or_gpa
    work.addr = hva
    work.arch = arch
    work.state = KVMAsyncPFWorkState.QUEUED
    
    vcpu.async_pf.queue.append(work)
    vcpu.async_pf.queued += 1
    
    work.notpresent_injected = kvm_arch_async_page_not_present(vcpu, work)
    
    # Schedule work (in real kernel: schedule_work)
    # Here we execute immediately in a thread
    import threading
    t = threading.Thread(target=async_pf_execute, args=(work,))
    t.daemon = True
    t.start()
    
    return True


def kvm_async_pf_wakeup_all(vcpu: 'KVMVCPU') -> int:
    """Wake up all async PFs"""
    if vcpu.async_pf.done:
        return 0
    
    work = _async_pf_manager.alloc_work()
    if not work:
        return -12  # ENOMEM
    
    work.wakeup_all = True
    
    with vcpu.async_pf.lock:
        first = len(vcpu.async_pf.done) == 0
        vcpu.async_pf.done.append(work)
    
    if not KVM_ASYNC_PF_SYNC and first:
        kvm_arch_async_page_present_queued(vcpu)
    
    vcpu.async_pf.queued += 1
    return 0


# Architecture-specific stubs (would be implemented per-arch)
def kvm_arch_async_page_present(vcpu: 'KVMVCPU', work: KVMAsyncPFWork):
    """Arch-specific: async page present"""
    pass


def kvm_arch_async_page_present_queued(vcpu: 'KVMVCPU'):
    """Arch-specific: async page present queued"""
    pass


def kvm_arch_async_page_not_present(vcpu: 'KVMVCPU', work: KVMAsyncPFWork) -> bool:
    """Arch-specific: async page not present"""
    return False


def kvm_arch_can_dequeue_async_page_present(vcpu: 'KVMVCPU') -> bool:
    """Arch-specific: can dequeue async page present"""
    return True


def kvm_arch_async_page_ready(vcpu: 'KVMVCPU', work: KVMAsyncPFWork):
    """Arch-specific: async page ready"""
    pass


def _kvm_vcpu_wake_up(vcpu: 'KVMVCPU'):
    """Wake up vCPU"""
    with vcpu.wq:
        vcpu.wq.notify()


# Forward reference for type hints
from .kvm_main import KVMVCPU