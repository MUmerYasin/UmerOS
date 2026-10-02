"""
KVM EventFD Support
===================

Python implementation of KVM eventfd for interrupt/event signaling.
Based on linux/virt/kvm/eventfd.c
"""

import os
import select
import threading
from dataclasses import dataclass, field
from typing import Optional, List, Any, Callable
from enum import IntEnum


class KVMEventFDFlags(IntEnum):
    """EventFD flags"""
    NONE = 0
    SEMAPHORE = 1  # EFD_SEMAPHORE
    NONBLOCK = 2   # EFD_NONBLOCK
    CLOEXEC = 4    # EFD_CLOEXEC


@dataclass
class KVMEventFD:
    """KVM EventFD - for signaling events to userspace"""
    fd: int = -1
    kvm: Optional[Any] = None
    virq: int = -1
    flags: int = 0
    active: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)
    waiters: List[threading.Event] = field(default_factory=list)


@dataclass
class KVMIOEventFD:
    """KVM IO EventFD - for MMIO/PIO exit notification"""
    fd: int = -1
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
    fd: int = -1
    kvm: Optional[Any] = None
    gsi: int = 0
    flags: int = 0
    active: bool = False
    irq_source_id: int = 0


def eventfd_create(flags: int = 0) -> int:
    """Create an eventfd (Linux-specific, fallback for other platforms)"""
    try:
        # Try Linux eventfd
        import ctypes
        libc = ctypes.CDLL('libc.so.6', use_errno=True)
        EFD_SEMAPHORE = 1
        EFD_NONBLOCK = 0o4000
        EFD_CLOEXEC = 0o2000000
        
        fd = libc.eventfd(0, flags & (EFD_SEMAPHORE | EFD_NONBLOCK | EFD_CLOEXEC))
        if fd >= 0:
            return fd
    except (OSError, AttributeError):
        pass
    
    # Fallback: create a pipe
    r, w = os.pipe()
    if flags & KVMEventFDFlags.NONBLOCK:
        import fcntl
        for fd in (r, w):
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    return r  # Return read end for polling


def eventfd_signal(fd: int, value: int = 1) -> int:
    """Signal an eventfd"""
    try:
        # Try Linux eventfd_write
        import ctypes
        libc = ctypes.CDLL('libc.so.6', use_errno=True)
        return libc.eventfd_write(fd, value)
    except (OSError, AttributeError):
        pass
    
    # Fallback: write to pipe
    try:
        os.write(fd, value.to_bytes(8, 'little'))
        return 0
    except OSError:
        return -1


def eventfd_read(fd: int) -> int:
    """Read from eventfd"""
    try:
        # Try Linux eventfd_read
        import ctypes
        libc = ctypes.CDLL('libc.so.6', use_errno=True)
        val = ctypes.c_uint64()
        ret = libc.eventfd_read(fd, ctypes.byref(val))
        if ret == 0:
            return val.value
    except (OSError, AttributeError):
        pass
    
    # Fallback: read from pipe
    try:
        data = os.read(fd, 8)
        if len(data) == 8:
            return int.from_bytes(data, 'little')
    except OSError:
        pass
    return 0


def kvm_eventfd_init(kvm: Any, eventfd: KVMEventFD, fd: int, 
                      virq: int = -1, flags: int = 0) -> int:
    """Initialize a KVM eventfd"""
    eventfd.fd = fd
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
    
    if eventfd.fd >= 0:
        try:
            os.close(eventfd.fd)
        except OSError:
            pass
        eventfd.fd = -1


def kvm_eventfd_signal(eventfd: KVMEventFD, value: int = 1) -> int:
    """Signal a KVM eventfd"""
    if not eventfd.active:
        return -22  # EINVAL
    
    return eventfd_signal(eventfd.fd, value)


def kvm_ioeventfd_init(kvm: Any, ioeventfd: KVMIOEventFD, fd: int,
                       addr: int, length: int, datamatch: int,
                       bus_idx: int, pio: bool, flags: int) -> int:
    """Initialize a KVM IO eventfd"""
    ioeventfd.fd = fd
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
    
    if ioeventfd.fd >= 0:
        try:
            os.close(ioeventfd.fd)
        except OSError:
            pass
        ioeventfd.fd = -1


def kvm_virqfd_init(kvm: Any, virqfd: KVMVirqFD, fd: int,
                    gsi: int, flags: int) -> int:
    """Initialize a KVM virtual IRQ fd"""
    virqfd.fd = fd
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
    
    if virqfd.fd >= 0:
        try:
            os.close(virqfd.fd)
        except OSError:
            pass
        virqfd.fd = -1


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
    if eventfd.fd < 0:
        return False
    
    try:
        r, _, _ = select.select([eventfd.fd], [], [], timeout)
        return bool(r)
    except (OSError, ValueError):
        return False


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
        self.fd = -1
    
    def __enter__(self) -> KVMEventFD:
        self.fd = eventfd_create(self.flags)
        kvm_eventfd_init(self.kvm, self.eventfd, self.fd, self.virq, self.flags)
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
        
        fds = [efd.fd for efd in self.eventfds if efd.fd >= 0 and efd.active]
        if not fds:
            return []
        
        try:
            r, _, _ = select.select(fds, [], [], timeout)
            ready = []
            for efd in self.eventfds:
                if efd.fd in r:
                    ready.append(efd)
            return ready
        except (OSError, ValueError):
            return []
    
    def wait_any(self, timeout: float = -1) -> Optional[KVMEventFD]:
        """Wait for any eventfd to be ready"""
        ready = self.poll(timeout)
        return ready[0] if ready else None