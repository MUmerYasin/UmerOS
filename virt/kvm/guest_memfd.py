"""
KVM Guest Memory File Descriptor (guest_memfd)
===============================================

Python implementation of KVM guest_memfd for secure guest memory management.
Based on linux/virt/kvm/guest_memfd.c and guest_memfd.h
"""

import os
import mmap
import threading
from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict
from enum import IntEnum


class KVM_GMEM_FLAGS(IntEnum):
    """Guest memfd flags"""
    NONE = 0
    SHARE = 1          # Allow sharing between VMs
    PRIVATE = 2        # Private memory (encrypted)
    HUGETLB = 4        # Use huge pages
    SEAL = 8           # Seal after creation


@dataclass
class KVMCreateGuestMemfd:
    """Arguments for creating guest memfd"""
    size: int = 0
    flags: int = 0
    fd: int = -1       # Output: returned file descriptor
    # Future expansion
    reserved: bytes = field(default_factory=lambda: b'\x00' * 24)


@dataclass
class KVMGuestMemfd:
    """Guest memory file descriptor"""
    fd: int = -1
    size: int = 0
    flags: int = 0
    kvm: Optional[Any] = None
    memslot: Optional[Any] = None  # Bound memory slot
    sealed: bool = False
    mappings: Dict[int, mmap.mmap] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


# Global state for guest_memfd module
_guest_memfd_module = None
_guest_memfd_lock = threading.Lock()


def kvm_gmem_init(module: Any = None) -> int:
    """Initialize guest_memfd subsystem"""
    global _guest_memfd_module
    with _guest_memfd_lock:
        if _guest_memfd_module is not None:
            return 0
        _guest_memfd_module = {'active_gmems': {}}
    return 0


def kvm_gmem_exit():
    """Exit guest_memfd subsystem"""
    global _guest_memfd_module
    with _guest_memfd_lock:
        _guest_memfd_module = None


def kvm_gmem_create(kvm: Any, args: KVMCreateGuestMemfd) -> int:
    """Create a guest memory file descriptor"""
    if args.size == 0:
        return -22  # EINVAL
    
    # Check flags
    valid_flags = (KVM_GMEM_FLAGS.SHARE | KVM_GMEM_FLAGS.PRIVATE | 
                   KVM_GMEM_FLAGS.HUGETLB | KVM_GMEM_FLAGS.SEAL)
    if args.flags & ~valid_flags:
        return -22
    
    # Create anonymous file (memfd_create on Linux)
    try:
        import ctypes
        libc = ctypes.CDLL('libc.so.6', use_errno=True)
        MFD_CLOEXEC = 1
        MFD_ALLOW_SEALING = 2
        MFD_HUGETLB = 4
        
        mfd_flags = MFD_CLOEXEC | MFD_ALLOW_SEALING
        if args.flags & KVM_GMEM_FLAGS.HUGETLB:
            mfd_flags |= MFD_HUGETLB
        
        name = f"kvm-gmem-{id(kvm)}-{id(args)}".encode('utf-8')
        fd = libc.memfd_create(name, mfd_flags)
        
        if fd < 0:
            # Fallback to tmpfile
            fd = os.open('/dev/zero', os.O_RDWR)
            if fd < 0:
                return -12  # ENOMEM
    except (OSError, AttributeError):
        # Fallback
        try:
            fd = os.open('/dev/zero', os.O_RDWR)
        except OSError:
            return -12  # ENOMEM
    
    # Set size
    try:
        os.ftruncate(fd, args.size)
    except OSError:
        os.close(fd)
        return -28  # ENOSPC
    
    # Apply seals if requested
    if args.flags & KVM_GMEM_FLAGS.SEAL:
        try:
            import ctypes
            libc = ctypes.CDLL('libc.so.6', use_errno=True)
            F_ADD_SEALS = 1033
            F_SEAL_SHRINK = 0x01
            F_SEAL_GROW = 0x02
            F_SEAL_WRITE = 0x04
            F_SEAL_FUTURE = 0x08
            
            seals = F_SEAL_SHRINK | F_SEAL_GROW | F_SEAL_FUTURE
            if not (args.flags & KVM_GMEM_FLAGS.SHARE):
                seals |= F_SEAL_WRITE
            
            libc.fcntl(fd, F_ADD_SEALS, seals)
        except (OSError, AttributeError):
            pass  # Sealing not supported
    
    # Create guest_memfd object
    gmem = KVMGuestMemfd(
        fd=fd,
        size=args.size,
        flags=args.flags,
        kvm=kvm
    )
    
    args.fd = fd
    
    # Track in module
    with _guest_memfd_lock:
        if _guest_memfd_module:
            _guest_memfd_module['active_gmems'][fd] = gmem
    
    return 0


def kvm_gmem_bind(kvm: Any, memslot: Any, fd: int, offset: int) -> int:
    """Bind guest memfd to a memory slot"""
    if fd < 0:
        return -5  # EIO
    
    gmem = None
    with _guest_memfd_lock:
        if _guest_memfd_module:
            gmem = _guest_memfd_module['active_gmems'].get(fd)
    
    if not gmem:
        return -5  # EIO
    
    if gmem.kvm and gmem.kvm != kvm:
        return -16  # EBUSY (already bound to another VM)
    
    if gmem.memslot:
        return -16  # EBUSY (already bound)
    
    # Map the memory
    try:
        mapping = mmap.mmap(fd, memslot.npages * 4096, 
                           offset=offset, flags=mmap.MAP_SHARED)
    except (OSError, ValueError):
        return -12  # ENOMEM
    
    with gmem.lock:
        gmem.kvm = kvm
        gmem.memslot = memslot
        gmem.mappings[offset] = mapping
    
    # Update memslot
    memslot.userspace_addr = id(mapping)  # Use mapping id as pseudo-address
    memslot.flags |= 0x1  # Mark as guest_memfd backed
    
    return 0


def kvm_gmem_unbind(memslot: Any):
    """Unbind guest memfd from memory slot"""
    # Find the gmem bound to this slot
    gmem = None
    with _guest_memfd_lock:
        if _guest_memfd_module:
            for g in _guest_memfd_module['active_gmems'].values():
                if g.memslot == memslot:
                    gmem = g
                    break
    
    if not gmem:
        return
    
    with gmem.lock:
        # Unmap all mappings
        for offset, mapping in gmem.mappings.items():
            try:
                mapping.close()
            except (OSError, ValueError):
                pass
        gmem.mappings.clear()
        
        gmem.kvm = None
        gmem.memslot = None
    
    # Clear memslot flag
    memslot.flags &= ~0x1
    memslot.userspace_addr = 0


def kvm_gmem_get_fd(kvm: Any, memslot: Any) -> int:
    """Get guest_memfd fd for a memory slot"""
    with _guest_memfd_lock:
        if _guest_memfd_module:
            for g in _guest_memfd_module['active_gmems'].values():
                if g.kvm == kvm and g.memslot == memslot:
                    return g.fd
    return -1


def kvm_gmem_share(kvm_src: Any, memslot_src: Any, 
                   kvm_dst: Any, memslot_dst: Any) -> int:
    """Share guest memory between VMs"""
    fd = kvm_gmem_get_fd(kvm_src, memslot_src)
    if fd < 0:
        return -22  # EINVAL
    
    gmem = None
    with _guest_memfd_lock:
        if _guest_memfd_module:
            gmem = _guest_memfd_module['active_gmems'].get(fd)
    
    if not gmem or not (gmem.flags & KVM_GMEM_FLAGS.SHARE):
        return -13  # EACCES
    
    # Bind to destination
    return kvm_gmem_bind(kvm_dst, memslot_dst, fd, 0)


def kvm_gmem_get_info(fd: int) -> Optional[Dict[str, Any]]:
    """Get guest_memfd information"""
    with _guest_memfd_lock:
        if _guest_memfd_module:
            gmem = _guest_memfd_module['active_gmems'].get(fd)
            if gmem:
                return {
                    'fd': gmem.fd,
                    'size': gmem.size,
                    'flags': gmem.flags,
                    'sealed': gmem.sealed,
                    'bound': gmem.memslot is not None,
                    'kvm_id': id(gmem.kvm) if gmem.kvm else None,
                }
    return None


# Helper for creating guest_memfd from userspace
def create_guest_memfd(size: int, flags: int = 0) -> int:
    """Create a guest memfd (userspace helper)"""
    args = KVMCreateGuestMemfd(size=size, flags=flags)
    # Would need a KVM instance - simplified for testing
    return -1  # Not implemented without KVM context


# Memory sealing helpers
def seal_guest_memfd(fd: int, shrink: bool = True, grow: bool = True,
                     write: bool = False, future: bool = True) -> int:
    """Apply seals to guest memfd"""
    try:
        import ctypes
        libc = ctypes.CDLL('libc.so.6', use_errno=True)
        F_ADD_SEALS = 1033
        F_SEAL_SHRINK = 0x01
        F_SEAL_GROW = 0x02
        F_SEAL_WRITE = 0x04
        F_SEAL_FUTURE = 0x08
        
        seals = 0
        if shrink:
            seals |= F_SEAL_SHRINK
        if grow:
            seals |= F_SEAL_GROW
        if write:
            seals |= F_SEAL_WRITE
        if future:
            seals |= F_SEAL_FUTURE
        
        ret = libc.fcntl(fd, F_ADD_SEALS, seals)
        return 0 if ret == 0 else -1
    except (OSError, AttributeError):
        return -38  # ENOTSUP


def is_guest_memfd_sealed(fd: int) -> bool:
    """Check if guest memfd is sealed"""
    try:
        import ctypes
        libc = ctypes.CDLL('libc.so.6', use_errno=True)
        F_GET_SEALS = 1034
        
        seals = libc.fcntl(fd, F_GET_SEALS)
        return seals != 0
    except (OSError, AttributeError):
        return False