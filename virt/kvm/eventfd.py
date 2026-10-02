"""
KVM EventFD Support
===================

Python implementation of KVM eventfd for interrupt/event signaling.
Based on linux/virt/kvm/eventfd.c
"""

import os
import select
import threading
import queue
from dataclasses import dataclass, field
from typing import Optional, List, Any, Callable
from enum import IntEnum


class KVMEventFDFlags(IntEnum):
    """EventFD flags"""
    NONE = 0
    SEMAPHORE = 1  # EFD_SEMAPHORE
    NONBLOCK = 2   # EFD_NONBLOCK
    CLOEXEC = 4    # EFD_CLOEXEC


# Cross-platform eventfd implementation using queue.Queue
class _EventFD:
    """Internal eventfd implementation using queue.Queue"""
    def __init__(self, flags: int = 0):
        self.queue = queue.Queue()
        self.flags = flags
        self.value = 0
        self._semaphore = (flags & KVMEventFDFlags.SEMAPHORE) != 0
    
    def write(self, value: int = 1) -> int:
        if self._semaphore:
            # Semaphore mode: increment counter
            self.value += value
        else:
            # Eventfd mode: add value to queue
            try:
                self.queue.put_nowait(value)
            except queue.Full:
                return -1
        return 0
    
    def read(self) -> int:
        if self._semaphore:
            if self.value == 0:
                return 0
            val = self.value
            self.value = 0
            return val
        else:
            try:
                return self.queue.get_nowait()
            except queue.Empty:
                return 0
    
    def poll(self, timeout: float = -1) -> bool:
        if self._semaphore:
            return self.value > 0
        return not self.queue.empty()


def eventfd_create(flags: int = 0) -> _EventFD:
    """Create an eventfd (cross-platform using queue.Queue)"""
    return _EventFD(flags)


def eventfd_signal(efd: _EventFD, value: int = 1) -> int:
    """Signal an eventfd"""
    return efd.write(value)


def eventfd_read(efd: _EventFD) -> int:
    """Read from eventfd"""
    return efd.read()


def eventfd_poll(efd: _EventFD, timeout: float = -1) -> bool:
    """Poll eventfd for readability"""
    return efd.poll(timeout)


@dataclass
class KVMEventFD:
    """KVM EventFD - for signaling events to userspace"""
    fd: _EventFD = field(default_factory=_EventFD)
    kvm: Optional[Any] = None
    virq: int = -1
    flags: int = 0
    active: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)
    waiters: List[threading.Event] = field(default_factory=list)


@dataclass
class KVMIOEventFD:
    """KVM IO EventFD - for MMIO/PIO exit notification"""
    fd: _EventFD = field(default_factory=_EventFD)
    kvm: Optional[Any] = None
    addr: int = 0
    length: int = 0
    datamatch: int = 0
    bus_idx: int = 0
    pio: bool = False
    flags: int = 0
    active: bool = False


@dataclass
class KVMVirqFD:
    """KVM Virtual IRQ FD - for IRQ injection"""
    fd: _EventFD = field(default_factory=_EventFD)
    kvm: Optional[Any] = None
    gsi: int = 0
    flags: int = 0
    active: bool = False
    irq_source_id: int = 0


def kvm_eventfd_init(kvm: Any, eventfd: KVMEventFD, efd: _EventFD, 
                      virq: int = -1, flags: int = 0) -> int:
    """Initialize a KVM eventfd"""
    eventfd.fd = efd
    eventfd.kvm = kvm
    eventfd.virq = virq
    eventfd.flags = flags
    eventfd.active = True
    
    # Add to VM's eventfd list
    if not hasattr(kvm, 'eventfds'):
        kvm.eventfds = []
    kvm.eventfds.append(eventfd)
    
    return 0


def kvm_eventfd_deinit(eventfd: KVMEventFD):
    """Deinitialize a KVM eventfd"""
    eventfd.active = False
    
    if eventfd.kvm and hasattr(eventfd.kvm, 'eventfds'):
        try:
            eventfd.kvm.eventfds.remove(eventfd)
        except ValueError:
            pass


def kvm_eventfd_signal(eventfd: KVMEventFD, value: int = 1) -> int:
    """Signal a KVM eventfd"""
    if not eventfd.active:
        return -22  # EINVAL
    
    return eventfd_signal(eventfd.fd, value)


def kvm_ioeventfd_init(kvm: Any, ioeventfd: KVMIOEventFD, efd: _EventFD,
                       addr: int, length: int, datamatch: int,
                       bus_idx: int, pio: bool, flags: int) -> int:
    """Initialize a KVM IO eventfd"""
    ioeventfd.fd = efd
    ioeventfd.kvm = kvm
    ioeventfd.addr = addr
    ioeventfd.length = length
    ioeventfd.datamatch = datamatch
    ioeventfd.bus_idx = bus_idx
    ioeventfd.pio = pio
    ioeventfd.flags = flags
    ioeventfd.active = True
    
    if not hasattr(kvm, 'ioeventfds'):
        kvm.ioeventfds = []
    kvm.ioeventfds.append(ioeventfd)
    
    return 0


def kvm_ioeventfd_deinit(ioeventfd: KVMIOEventFD):
    """Deinitialize a KVM IO eventfd"""
    ioeventfd.active = False
    
    if ioeventfd.kvm and hasattr(ioeventfd.kvm, 'ioeventfds'):
        try:
            ioeventfd.kvm.ioeventfds.remove(ioeventfd)
        except ValueError:
            pass


def kvm_virqfd_init(kvm: Any, virqfd: KVMVirqFD, efd: _EventFD,
                    gsi: int, flags: int) -> int:
    """Initialize a KVM virtual IRQ fd"""
    virqfd.fd = efd
    virqfd.kvm = kvm
    virqfd.gsi = gsi
    virqfd.flags = flags
    virqfd.active = True
    virqfd.irq_source_id = id(virqfd) & 0xFFFFFFFF
    
    if not hasattr(kvm, 'virqfds'):
        kvm.virqfds = []
    kvm.virqfds.append(virqfd)
    
    return 0


def kvm_virqfd_deinit(virqfd: KVMVirqFD):
    """Deinitialize a KVM virtual IRQ fd"""
    virqfd.active = False
    
    if virqfd.kvm and hasattr(virqfd.kvm, 'virqfds'):
        try:
            virqfd.kvm.virqfds.remove(virqfd)
        except ValueError:
            pass


def kvm_virqfd_signal(virqfd: KVMVirqFD, level: int = 1) -> int:
    """Signal a virtual IRQ (inject interrupt)"""
    if not virqfd.active or not virqfd.kvm:
        return -22
    
    # Inject IRQ into VM
    return kvm_inject_irq(virqfd.kvm, virqfd.gsi, level, virqfd.irq_source_id)


def kvm_inject_irq(kvm: Any, gsi: int, level: int, irq_source_id: int) -> int:
    """Inject IRQ into VM (calls through to irqchip)"""
    if hasattr(kvm, 'inject_irq'):
        return kvm.inject_irq(gsi, level, irq_source_id)
    return 0


# Polling support
def kvm_eventfd_poll(eventfd: KVMEventFD, timeout: float = -1) -> bool:
    """Poll eventfd for readability"""
    return eventfd_poll(eventfd.fd, timeout)


def kvm_eventfd_wait(eventfd: KVMEventFD, timeout: float = -1) -> int:
    """Wait for eventfd signal"""
    if not kvm_eventfd_poll(eventfd, timeout):
        return -110  # ETIMEDOUT
    
    return eventfd_read(eventfd.fd)


# EventFD context manager
class KVMEventFDContext:
    """Context manager for KVM eventfd"""
    
    def __init__(self, kvm: Any, virq: int = -1, flags: int = 0):
        self.kvm = kvm
        self.virq = virq
        self.flags = flags
        self.eventfd = KVMEventFD()
        self.efd = None
    
    def __enter__(self) -> KVMEventFD:
        self.efd = eventfd_create(self.flags)
        kvm_eventfd_init(self.kvm, self.eventfd, self.efd, self.virq, self.flags)
        return self.eventfd
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        kvm_eventfd_deinit(self.eventfd)


# Batch eventfd operations
class KVMEventFDBatch:
    """Batch multiple eventfds for efficient polling"""
    
    def __init__(self):
        self.eventfds: List[KVMEventFD] = []
    
    def add(self, eventfd: KVMEventFD):
        self.eventfds.append(eventfd)
    
    def remove(self, eventfd: KVMEventFD):
        self.eventfds.remove(eventfd)
    
    def poll(self, timeout: float = -1) -> List[KVMEventFD]:
        """Poll all eventfds, return ready ones"""
        if not self.eventfds:
            return []
        
        ready = []
        for efd in self.eventfds:
            if efd.active and eventfd_poll(efd.fd, 0):
                ready.append(efd)
        return ready
    
    def wait_any(self, timeout: float = -1) -> Optional[KVMEventFD]:
        """Wait for any eventfd to be ready"""
        ready = self.poll(timeout)
        return ready[0] if ready else None