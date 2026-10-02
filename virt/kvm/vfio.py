"""
KVM VFIO Device Integration
===========================

Python implementation of KVM VFIO bridge for device assignment.
Based on linux/virt/kvm/vfio.c and vfio.h
"""

import os
import threading
from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict
from enum import IntEnum


# Device types
KVM_DEV_TYPE_VFIO = 1

# VFIO file operations
KVM_DEV_VFIO_FILE = 1
KVM_DEV_VFIO_FILE_ADD = 1
KVM_DEV_VFIO_FILE_DEL = 2
KVM_DEV_VFIO_GROUP_SET_SPAPR_TCE = 3


@dataclass
class KVMVFIOFile:
    """VFIO file attached to VM"""
    file: Any = None  # File descriptor or file object
    fd: int = -1
    iommu_group: Optional[Any] = None  # For SPAPR TCE
    list_next: Optional['KVMVFIOFile'] = None
    list_prev: Optional['KVMVFIOFile'] = None


@dataclass
class KVMVFIO:
    """VFIO device state for a VM"""
    file_list: List[KVMVFIOFile] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)
    noncoherent: bool = False
    dev: Optional[Any] = None  # Back-reference to KVMDevice


@dataclass
class KVMDevice:
    """KVM Device"""
    kvm: Optional[Any] = None
    ops: Optional[Any] = None
    type: int = 0
    private: Optional[Any] = None
    vm_node: Any = None  # For device list


@dataclass
class KVMDeviceAttr:
    """KVM Device Attribute"""
    group: int = 0
    attr: int = 0
    addr: int = 0
    flags: int = 0


def vfio_file_set_kvm(file_obj: Any, kvm: Any):
    """Set KVM for VFIO file (via VFIO module)"""
    # In real kernel: calls vfio_file_set_kvm via symbol_get
    # Here we just store the reference
    if hasattr(file_obj, 'kvm_ref'):
        file_obj.kvm_ref = kvm


def vfio_file_enforced_coherent(file_obj: Any) -> bool:
    """Check if VFIO file enforces coherency"""
    # In real kernel: calls vfio_file_enforced_coherent
    return getattr(file_obj, 'enforced_coherent', False)


def vfio_file_is_valid(file_obj: Any) -> bool:
    """Check if file is a valid VFIO file"""
    # In real kernel: calls vfio_file_is_valid
    return hasattr(file_obj, 'is_vfio') and file_obj.is_vfio


def vfio_file_iommu_group(file_obj: Any) -> Optional[Any]:
    """Get IOMMU group for VFIO file (SPAPR)"""
    # In real kernel: calls vfio_file_iommu_group
    return getattr(file_obj, 'iommu_group', None)


def kvm_vfio_update_coherency(dev: KVMDevice):
    """Update DMA coherency state"""
    kv = dev.private
    if not kv:
        return
    
    noncoherent = False
    
    with kv.lock:
        for kvf in kv.file_list:
            if not vfio_file_enforced_coherent(kvf.file):
                noncoherent = True
                break
    
    if noncoherent != kv.noncoherent:
        kv.noncoherent = noncoherent
        
        if kv.noncoherent:
            # Would call kvm_arch_register_noncoherent_dma
            pass
        else:
            # Would call kvm_arch_unregister_noncoherent_dma
            pass


def kvm_vfio_file_add(dev: KVMDevice, fd: int) -> int:
    """Add VFIO file to VM"""
    kv = dev.private
    if not kv:
        return -22  # EINVAL
    
    # Validate file
    # In real kernel: fget + vfio_file_is_valid
    file_obj = _get_file_object(fd)
    if not file_obj:
        return -9  # EBADF
    
    if not vfio_file_is_valid(file_obj):
        _put_file_object(file_obj)
        return -22  # EINVAL
    
    with kv.lock:
        # Check for duplicate
        for kvf in kv.file_list:
            if kvf.fd == fd:
                _put_file_object(file_obj)
                return -17  # EEXIST
        
        # Create new entry
        kvf = KVMVFIOFile()
        kvf.file = file_obj
        kvf.fd = fd
        kv.file_list.append(kvf)
        
        vfio_file_set_kvm(file_obj, dev.kvm)
    
    kvm_vfio_update_coherency(dev)
    return 0


def kvm_vfio_file_free(dev: KVMDevice, kvf: KVMVFIOFile):
    """Free VFIO file entry"""
    # For SPAPR: release TCE
    if kvf.iommu_group:
        # kvm_spapr_tce_release_iommu_group(dev.kvm, kvf.iommu_group)
        kvf.iommu_group = None
    
    vfio_file_set_kvm(kvf.file, None)
    _put_file_object(kvf.file)
    
    # Remove from list
    if kvf in dev.private.file_list:
        dev.private.file_list.remove(kvf)


def kvm_vfio_file_del(dev: KVMDevice, fd: int) -> int:
    """Remove VFIO file from VM"""
    kv = dev.private
    if not kv:
        return -22
    
    file_obj = _get_file_object(fd)
    if not file_obj:
        return -9  # EBADF
    
    with kv.lock:
        for kvf in kv.file_list:
            if kvf.fd == fd:
                kvm_vfio_file_free(dev, kvf)
                kvm_vfio_update_coherency(dev)
                _put_file_object(file_obj)
                return 0
    
    _put_file_object(file_obj)
    return -2  # ENOENT


def kvm_vfio_file_set_spapr_tce(dev: KVMDevice, arg: Any) -> int:
    """Set SPAPR TCE for VFIO group (PowerPC)"""
    # Not implemented for non-SPAPR platforms
    return -19  # ENXIO


def kvm_vfio_set_attr(dev: KVMDevice, attr: KVMDeviceAttr) -> int:
    """Set VFIO device attribute"""
    if attr.group != KVM_DEV_VFIO_FILE:
        return -19  # ENXIO
    
    # Convert addr to userspace pointer (simplified)
    fd = attr.addr & 0xFFFFFFFF
    
    if attr.attr == KVM_DEV_VFIO_FILE_ADD:
        return kvm_vfio_file_add(dev, fd)
    elif attr.attr == KVM_DEV_VFIO_FILE_DEL:
        return kvm_vfio_file_del(dev, fd)
    elif attr.attr == KVM_DEV_VFIO_GROUP_SET_SPAPR_TCE:
        return kvm_vfio_file_set_spapr_tce(dev, attr.addr)
    
    return -19  # ENXIO


def kvm_vfio_has_attr(dev: KVMDevice, attr: KVMDeviceAttr) -> int:
    """Check if VFIO device has attribute"""
    if attr.group != KVM_DEV_VFIO_FILE:
        return -19
    
    if attr.attr in (KVM_DEV_VFIO_FILE_ADD, KVM_DEV_VFIO_FILE_DEL,
                     KVM_DEV_VFIO_GROUP_SET_SPAPR_TCE):
        return 0
    
    return -19


def kvm_vfio_release(dev: KVMDevice):
    """Release VFIO device"""
    kv = dev.private
    if not kv:
        return
    
    with kv.lock:
        # Free all files
        for kvf in kv.file_list[:]:
            kvm_vfio_file_free(dev, kvf)
    
    kvm_vfio_update_coherency(dev)
    
    dev.private = None


def kvm_vfio_create(dev: KVMDevice, type_: int) -> int:
    """Create VFIO device"""
    # Check for existing VFIO device
    if dev.kvm:
        for d in getattr(dev.kvm, 'devices', []):
            if getattr(d, 'ops', None) and d.ops.name == "kvm-vfio":
                return -16  # EBUSY
    
    kv = KVMVFIO()
    kv.dev = dev
    dev.private = kv
    
    return 0


class KVMVFIOOps:
    """VFIO device operations"""
    name = "kvm-vfio"
    create = staticmethod(kvm_vfio_create)
    release = staticmethod(kvm_vfio_release)
    set_attr = staticmethod(kvm_vfio_set_attr)
    has_attr = staticmethod(kvm_vfio_has_attr)


def kvm_vfio_ops_init() -> int:
    """Initialize VFIO ops"""
    # In real kernel: kvm_register_device_ops
    return 0


def kvm_vfio_ops_exit():
    """Exit VFIO ops"""
    # In real kernel: kvm_unregister_device_ops
    pass


# File object management (simplified)
_file_objects: Dict[int, Any] = {}
_file_lock = threading.Lock()


def _get_file_object(fd: int) -> Optional[Any]:
    """Get file object from fd"""
    with _file_lock:
        return _file_objects.get(fd)


def _put_file_object(file_obj: Any):
    """Put file object reference"""
    # Simplified - no actual refcounting
    pass


def register_vfio_file(fd: int, file_obj: Any) -> bool:
    """Register a VFIO file object (for testing)"""
    with _file_lock:
        if fd in _file_objects:
            return False
        file_obj.is_vfio = True
        file_obj.fd = fd
        _file_objects[fd] = file_obj
        return True


def unregister_vfio_file(fd: int):
    """Unregister VFIO file object"""
    with _file_lock:
        _file_objects.pop(fd, None)


# Helper for creating VFIO device
def create_vfio_device(kvm: Any) -> KVMDevice:
    """Create a VFIO device for a VM"""
    dev = KVMDevice()
    dev.kvm = kvm
    dev.ops = KVMVFIOOps()
    dev.type = KVM_DEV_TYPE_VFIO
    kvm_vfio_create(dev, KVM_DEV_TYPE_VFIO)
    return dev