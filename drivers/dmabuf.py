"""
UmerOS DMA Buffer Sharing Framework
====================================
Kernel dma-buf sharing.
Implements buffer export, attachment, mapping, CPU access,
scatter-gather tables, and DMA heaps (system, CMA, carveout).
"""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Optional imports with fallback
# ---------------------------------------------------------------------------
try:
    from dataclasses import dataclass, field  # stdlib
except ImportError:
    raise RuntimeError("UmerOS requires Python 3.10+ (dataclasses)")

try:
    import hashlib  # for simulated fd generation
except ImportError:
    hashlib = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DMA_BUF_FLAGS_READ: int = 0x01
DMA_BUF_FLAGS_WRITE: int = 0x02
DMA_BUF_FLAGS_RW: int = 0x03
DMA_BUF_FLAGS_CACHED: int = 0x04
DMA_BUF_FLAGS_UNCACHED: int = 0x08
DMA_BUF_FLAGS_CONTIG: int = 0x10
DMA_BUF_FLAGS_CMA: int = 0x20
DMA_BUF_FLAGS_DYNAMIC: int = 0x40

_DIRECTION_MAP: Dict[str, int] = {
    "bidirectional": 0x03,
    "to_device": 0x01,
    "from_device": 0x02,
    "none": 0x00,
}

# ---------------------------------------------------------------------------
# Global registries
# ---------------------------------------------------------------------------
_registry_lock = threading.Lock()

_buffers: Dict[str, "DmaBuf"] = {}
_heaps: Dict[str, "DmaHeap"] = {}
_fd_map: Dict[int, str] = {}  # fd -> buf_name
_fd_counter: int = 100  # simulated fd numbers start at 100


def _next_fd() -> int:
    """Allocate next simulated file descriptor."""
    global _fd_counter
    _fd_counter += 1
    return _fd_counter


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DmaBufOps:
    """dma_buf operations (callbacks)"""
    name: str = ""
    attach: Optional[Callable[..., Any]] = None
    detach: Optional[Callable[..., Any]] = None
    pin: Optional[Callable[..., Any]] = None
    unpin: Optional[Callable[..., Any]] = None
    map_dma_buf: Optional[Callable[..., Any]] = None
    unmap_dma_buf: Optional[Callable[..., Any]] = None
    release: Optional[Callable[..., Any]] = None
    begin_cpu_access: Optional[Callable[..., Any]] = None
    end_cpu_access: Optional[Callable[..., Any]] = None
    vmap: Optional[Callable[..., Any]] = None
    vunmap: Optional[Callable[..., Any]] = None
    mmap: Optional[Callable[..., Any]] = None


@dataclass
class DmaBuf:
    """dma_buf object"""
    name: str
    size: int
    fd: int  # file descriptor (simulated)
    ops: DmaBufOps
    exp_name: str = ""
    flags: int = 0
    is_exported: bool = True
    _data: bytearray = field(default_factory=lambda: bytearray())
    _attachments: List["DmaBufAttachment"] = field(default_factory=list)
    _refs: int = 1
    _is_mapped: bool = False
    _is_vmapped: bool = False

    def __post_init__(self) -> None:
        if not self._data:
            self._data = bytearray(self.size)

    def __repr__(self) -> str:
        return (
            f"DmaBuf(name={self.name!r}, size={self.size}, fd={self.fd}, "
            f"refs={self._refs}, mapped={self._is_mapped})"
        )


@dataclass
class DmaBufAttachment:
    """Attachment from device to dma_buf"""
    device_name: str
    buf_name: str
    is_attached: bool = True
    is_pinned: bool = False
    _sgt: List[Tuple[int, int]] = field(default_factory=list)  # [(dma_addr, len), ...]


@dataclass
class DmaBufExpInfo:
    """Export info for dma_buf_export()"""
    exp_name: str
    size: int
    ops: DmaBufOps
    flags: int = 0
    file: str = ""


@dataclass
class DmaHeap:
    """DMA heap (allocates dma-bufs)"""
    name: str
    heap_type: str  # "system", "cma", "system_uncached", "carveout"
    total_allocated: int = 0
    total_buffers: int = 0
    max_size: int = 0
    _buffers: List[str] = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            f"DmaHeap(name={self.name!r}, type={self.heap_type!r}, "
            f"allocated={self.total_allocated}, buffers={self.total_buffers})"
        )


@dataclass
class DmaSgTable:
    """Scatter-gather table"""
    entries: List[Tuple[int, int]] = field(default_factory=list)  # [(dma_addr, len), ...]
    nents: int = 0
    orig_nents: int = 0


# ---------------------------------------------------------------------------
# Built-in DMA heaps
# ---------------------------------------------------------------------------

class SystemDmaHeap:
    """System DMA heap (kmalloc-based).
    Allocates from the kernel's system allocator. Buffers may be
    physically non-contiguous.
    """

    def __init__(self) -> None:
        self._base_addr: int = 0x1000_0000  # simulated base address

    def alloc(self, size: int, flags: int = 0) -> Tuple[bytearray, int]:
        """Allocate a buffer and return (data, dma_addr)."""
        data = bytearray(size)
        dma_addr = self._base_addr
        self._base_addr += size
        return data, dma_addr

    @property
    def heap_type(self) -> str:
        return "system"


class CmaDmaHeap:
    """CMA DMA heap (Contiguous Memory Allocator).
    Allocates physically contiguous memory from the CMA region.
    """

    def __init__(self) -> None:
        self._base_addr: int = 0x2000_0000

    def alloc(self, size: int, flags: int = 0) -> Tuple[bytearray, int]:
        aligned = (size + 0xFFF) & ~0xFFF
        data = bytearray(aligned)
        dma_addr = self._base_addr
        self._base_addr += aligned
        return data, dma_addr

    @property
    def heap_type(self) -> str:
        return "cma"


class CarveoutDmaHeap:
    """Carveout DMA heap (reserved memory).
    Allocates from a reserved memory region at boot time.
    """

    def __init__(self) -> None:
        self._base_addr: int = 0x3000_0000

    def alloc(self, size: int, flags: int = 0) -> Tuple[bytearray, int]:
        data = bytearray(size)
        dma_addr = self._base_addr
        self._base_addr += size
        return data, dma_addr

    @property
    def heap_type(self) -> str:
        return "carveout"


class IonDmaHeap:
    """ION-compatible DMA heap.
    Provides backward compatibility with Android's ION allocator.
    Routes to system or CMA depending on ION flags.
    """

    def __init__(self) -> None:
        self._system = SystemDmaHeap()
        self._cma = CmaDmaHeap()
        self._base_addr: int = 0x4000_0000

    def alloc(self, size: int, flags: int = 0) -> Tuple[bytearray, int]:
        if flags & DMA_BUF_FLAGS_CMA:
            return self._cma.alloc(size, flags)
        data = bytearray(size)
        dma_addr = self._base_addr
        self._base_addr += size
        return data, dma_addr

    @property
    def heap_type(self) -> str:
        return "ion"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _generate_sgt(size: int, contig: bool = False) -> List[Tuple[int, int]]:
    """Generate a simulated scatter-gather table for *size* bytes."""
    import random

    if contig or size <= 0x1000:
        return [(random.randint(0x4000_0000, 0x7FFF_FFFF), size)]

    entries: List[Tuple[int, int]] = []
    remaining = size
    page_size = 0x1000
    base = 0x4000_0000
    while remaining > 0:
        chunk = min(page_size, remaining)
        entries.append((base, chunk))
        base += page_size + random.randint(0x100, 0x2000)
        remaining -= chunk
    return entries


def _validate_buf(name: str) -> DmaBuf:
    """Lookup and validate a buffer by name."""
    buf = _buffers.get(name)
    if buf is None:
        raise KeyError(f"dma_buf '{name}' not found in registry")
    if buf._refs <= 0:
        raise RuntimeError(f"dma_buf '{name}' has been released (refs=0)")
    return buf


def _validate_attachment(buf: DmaBuf, device_name: str) -> DmaBufAttachment:
    """Find an active attachment for *device_name* on *buf*."""
    for att in buf._attachments:
        if att.device_name == device_name and att.is_attached:
            return att
    raise KeyError(
        f"No active attachment for device '{device_name}' on dma_buf '{buf.name}'"
    )


# ---------------------------------------------------------------------------
# Export / import / reference counting
# ---------------------------------------------------------------------------

def dma_buf_export(
    exp_name: str,
    size: int,
    ops: Optional[DmaBufOps] = None,
    flags: int = 0,
) -> DmaBuf:
    """Export a dma_buf — analogous to dma_buf_export().

    Creates a new buffer, assigns a simulated fd, and registers it
    in the global buffer registry.
    """
    if size <= 0:
        raise ValueError(f"Buffer size must be > 0, got {size}")
    if ops is None:
        ops = DmaBufOps(name=exp_name)

    fd = _next_fd()
    buf_name = f"{exp_name}_{fd}"

    buf = DmaBuf(
        name=buf_name,
        size=size,
        fd=fd,
        ops=ops,
        exp_name=exp_name,
        flags=flags,
        is_exported=True,
    )

    with _registry_lock:
        _buffers[buf_name] = buf
        _fd_map[fd] = buf_name

    return buf


def dma_buf_get(fd: int) -> DmaBuf:
    """Get dma_buf by file descriptor — analogous to dma_buf_get().

    Increments the reference count.
    """
    with _registry_lock:
        buf_name = _fd_map.get(fd)
    if buf_name is None:
        raise KeyError(f"No dma_buf registered for fd={fd}")
    buf = _validate_buf(buf_name)
    with _registry_lock:
        buf._refs += 1
    return buf


def dma_buf_put(buf_name: str) -> int:
    """Put dma_buf reference — analogous to dma_buf_put().

    Decrements the reference count and releases when it reaches zero.
    Returns the remaining reference count.
    """
    buf = _validate_buf(buf_name)
    with _registry_lock:
        buf._refs -= 1
        remaining = buf._refs
        if remaining <= 0:
            # Invoke release callback
            if buf.ops and buf.ops.release:
                try:
                    buf.ops.release(buf)
                except Exception:
                    pass
            _fd_map.pop(buf.fd, None)
            del _buffers[buf_name]
    return remaining


# ---------------------------------------------------------------------------
# Attachment management
# ---------------------------------------------------------------------------

def dma_buf_attach(buf_name: str, device_name: str) -> DmaBufAttachment:
    """Attach a device to a dma_buf — analogous to dma_buf_attach().

    Returns the new attachment object.
    """
    buf = _validate_buf(buf_name)

    # Check for duplicate
    with _registry_lock:
        for att in buf._attachments:
            if att.device_name == device_name and att.is_attached:
                raise RuntimeError(
                    f"Device '{device_name}' is already attached to '{buf.name}'"
                )

    att = DmaBufAttachment(device_name=device_name, buf_name=buf_name)

    # Invoke attach callback
    if buf.ops and buf.ops.attach:
        try:
            buf.ops.attach(buf, att)
        except Exception:
            pass

    with _registry_lock:
        buf._attachments.append(att)

    return att


def dma_buf_detach(buf_name: str, device_name: str) -> None:
    """Detach a device from a dma_buf — analogous to dma_buf_detach().

    This is a convenience alias that calls dma_buf_unattach().
    """
    dma_buf_unattach(buf_name, device_name)


def dma_buf_unattach(buf_name: str, device_name: str) -> None:
    """Detach a device from a dma_buf.

    Unmaps and unpins first if necessary.
    """
    buf = _validate_buf(buf_name)
    att = _validate_attachment(buf, device_name)

    with _registry_lock:
        att.is_attached = False
        att.is_pinned = False
        att._sgt.clear()

    # Invoke detach callback
    if buf.ops and buf.ops.detach:
        try:
            buf.ops.detach(buf, att)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------

def dma_buf_map_attachment(
    buf_name: str,
    device_name: str,
    direction: str = "bidirectional",
) -> DmaSgTable:
    """Map an attachment for DMA — analogous to dma_buf_map_attachment().

    Returns a DmaSgTable with scatter-gather entries.
    """
    buf = _validate_buf(buf_name)
    att = _validate_attachment(buf, device_name)

    if direction not in _DIRECTION_MAP:
        raise ValueError(f"Invalid direction '{direction}'")

    contig = bool(buf.flags & DMA_BUF_FLAGS_CONTIG)
    sgt_entries = _generate_sgt(buf.size, contig=contig)

    sgt = DmaSgTable(
        entries=sgt_entries,
        nents=len(sgt_entries),
        orig_nents=len(sgt_entries),
    )

    with _registry_lock:
        att._sgt = sgt_entries
        buf._is_mapped = True

    # Invoke map callback
    if buf.ops and buf.ops.map_dma_buf:
        try:
            buf.ops.map_dma_buf(buf, att)
        except Exception:
            pass

    return sgt


def dma_buf_unmap_attachment(buf_name: str, device_name: str) -> None:
    """Unmap an attachment — analogous to dma_buf_unmap_attachment().

    Clears the scatter-gather table for this attachment.
    """
    buf = _validate_buf(buf_name)
    att = _validate_attachment(buf, device_name)

    # Invoke unmap callback
    if buf.ops and buf.ops.unmap_dma_buf:
        try:
            buf.ops.unmap_dma_buf(buf, att)
        except Exception:
            pass

    with _registry_lock:
        att._sgt.clear()
        buf._is_mapped = False


# ---------------------------------------------------------------------------
# Pin / unpin
# ---------------------------------------------------------------------------

def dma_buf_pin(buf_name: str, device_name: str) -> None:
    """Pin buffer for DMA — analogous to dma_buf_pin().

    Prevents the buffer from being moved or swapped while pinned.
    """
    buf = _validate_buf(buf_name)
    att = _validate_attachment(buf, device_name)

    # Invoke pin callback
    if buf.ops and buf.ops.pin:
        try:
            buf.ops.pin(buf, att)
        except Exception:
            pass

    with _registry_lock:
        att.is_pinned = True


def dma_buf_unpin(buf_name: str, device_name: str) -> None:
    """Unpin buffer — analogous to dma_buf_unpin().

    Allows the buffer to be moved or swapped again.
    """
    buf = _validate_buf(buf_name)
    att = _validate_attachment(buf, device_name)

    # Invoke unpin callback
    if buf.ops and buf.ops.unpin:
        try:
            buf.ops.unpin(buf, att)
        except Exception:
            pass

    with _registry_lock:
        att.is_pinned = False


# ---------------------------------------------------------------------------
# CPU access
# ---------------------------------------------------------------------------

def dma_buf_begin_cpu_access(buf_name: str, mode: str = "read") -> None:
    """Begin CPU access — analogous to dma_buf_begin_cpu_access().

    Flushes device caches and prepares the buffer for CPU read/write.
    """
    if mode not in ("read", "write", "rw"):
        raise ValueError(f"Invalid mode '{mode}', expected 'read', 'write', or 'rw'")

    buf = _validate_buf(buf_name)

    if buf.ops and buf.ops.begin_cpu_access:
        try:
            buf.ops.begin_cpu_access(buf, mode)
        except Exception:
            pass

    # Simulate cache maintenance
    if buf.flags & DMA_BUF_FLAGS_CACHED:
        pass  # cached: no-op (already coherent for CPU)


def dma_buf_end_cpu_access(buf_name: str, mode: str = "read") -> None:
    """End CPU access — analogous to dma_buf_end_cpu_access().

    Flushes CPU caches back so the device can see updated data.
    """
    if mode not in ("read", "write", "rw"):
        raise ValueError(f"Invalid mode '{mode}', expected 'read', 'write', or 'rw'")

    buf = _validate_buf(buf_name)

    if buf.ops and buf.ops.end_cpu_access:
        try:
            buf.ops.end_cpu_access(buf, mode)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Virtual mapping (vmap/vunmap)
# ---------------------------------------------------------------------------

def dma_buf_vmap(buf_name: str) -> int:
    """Virtual map buffer — analogous to dma_buf_vmap().

    Returns a simulated virtual address.
    """
    buf = _validate_buf(buf_name)

    if buf._is_vmapped:
        raise RuntimeError(f"dma_buf '{buf.name}' is already vmapped")

    if buf.ops and buf.ops.vmap:
        try:
            vaddr = buf.ops.vmap(buf)
            if vaddr is not None:
                with _registry_lock:
                    buf._is_vmapped = True
                return vaddr
        except Exception:
            pass

    # Simulated virtual address
    vaddr = 0xFFFF_0000_0000_0000 + buf.fd * 0x1000
    with _registry_lock:
        buf._is_vmapped = True
    return vaddr


def dma_buf_vunmap(buf_name: str) -> None:
    """Virtual unmap buffer — analogous to dma_buf_vunmap().

    Releases the virtual mapping.
    """
    buf = _validate_buf(buf_name)

    if not buf._is_vmapped:
        raise RuntimeError(f"dma_buf '{buf.name}' is not vmapped")

    if buf.ops and buf.ops.vunmap:
        try:
            buf.ops.vunmap(buf)
        except Exception:
            pass

    with _registry_lock:
        buf._is_vmapped = False


# ---------------------------------------------------------------------------
# Mmap
# ---------------------------------------------------------------------------

def dma_buf_mmap(buf_name: str, vma_start: int, vma_size: int) -> int:
    """Mmap buffer to userspace — analogous to dma_buf_mmap().

    Maps the buffer into a virtual memory area. Returns a simulated
    mmap offset.
    """
    buf = _validate_buf(buf_name)

    if vma_size > buf.size:
        raise ValueError(
            f"mmap size {vma_size} exceeds buffer size {buf.size}"
        )

    if buf.ops and buf.ops.mmap:
        try:
            result = buf.ops.mmap(buf, vma_start, vma_size)
            if result is not None:
                return result
        except Exception:
            pass

    return vma_start


# ---------------------------------------------------------------------------
# File operations (info queries)
# ---------------------------------------------------------------------------

def dma_buf_set_opener(buf_name: str, opener_name: str) -> None:
    """Set opener (file descriptor holder) for a dma_buf.

    Tracks which process/entity holds the fd.
    """
    buf = _validate_buf(buf_name)
    with _registry_lock:
        buf.exp_name = opener_name


def dma_buf_get_flags(buf_name: str) -> int:
    """Get buffer flags."""
    buf = _validate_buf(buf_name)
    return buf.flags


def dma_buf_get_size(buf_name: str) -> int:
    """Get buffer size."""
    buf = _validate_buf(buf_name)
    return buf.size


def dma_buf_get_exp_name(buf_name: str) -> str:
    """Get exporter name."""
    buf = _validate_buf(buf_name)
    return buf.exp_name


# ---------------------------------------------------------------------------
# DMA Heaps
# ---------------------------------------------------------------------------

def dma_heap_register(
    name: str,
    heap_type: str,
    max_size: int = 0,
) -> DmaHeap:
    """Register a DMA heap — analogous to dma_heap_register().

    Supported types: "system", "cma", "system_uncached", "carveout".
    """
    if heap_type not in ("system", "cma", "system_uncached", "carveout", "ion"):
        raise ValueError(f"Unknown heap type '{heap_type}'")

    with _registry_lock:
        if name in _heaps:
            raise RuntimeError(f"Heap '{name}' is already registered")

        heap = DmaHeap(name=name, heap_type=heap_type, max_size=max_size)
        _heaps[name] = heap

    return heap


def dma_heap_unregister(name: str) -> None:
    """Unregister a DMA heap — analogous to dma_heap_unregister().

    Fails if the heap still has live buffers.
    """
    with _registry_lock:
        heap = _heaps.get(name)
        if heap is None:
            raise KeyError(f"Heap '{name}' not found")
        if heap.total_buffers > 0:
            raise RuntimeError(
                f"Cannot unregister heap '{name}': {heap.total_buffers} "
                "buffer(s) still live"
            )
        del _heaps[name]


def dma_heap_alloc(
    heap_name: str,
    size: int,
    flags: int = 0,
) -> DmaBuf:
    """Allocate a buffer from a DMA heap — analogous to dma_heap_buffer_alloc().

    Creates a dma_buf backed by the appropriate allocator.
    """
    with _registry_lock:
        heap = _heaps.get(heap_name)
    if heap is None:
        raise KeyError(f"Heap '{heap_name}' not found")

    if size <= 0:
        raise ValueError(f"Allocation size must be > 0, got {size}")

    if heap.max_size > 0 and size > heap.max_size:
        raise ValueError(
            f"Allocation {size} exceeds heap max_size {heap.max_size}"
        )

    # Select allocator
    alloc_impl = {
        "system": lambda s, f: SystemDmaHeap().alloc(s, f),
        "cma": lambda s, f: CmaDmaHeap().alloc(s, f),
        "system_uncached": lambda s, f: SystemDmaHeap().alloc(s, f | DMA_BUF_FLAGS_UNCACHED),
        "carveout": lambda s, f: CarveoutDmaHeap().alloc(s, f),
        "ion": lambda s, f: IonDmaHeap().alloc(s, f),
    }

    allocator = alloc_impl.get(heap.heap_type)
    if allocator is None:
        raise ValueError(f"No allocator for heap type '{heap.heap_type}'")

    data, dma_addr = allocator(size, flags)

    # Export as a dma_buf
    exp_ops = DmaBufOps(name=heap_name)
    buf = dma_buf_export(exp_name=heap_name, size=size, ops=exp_ops, flags=flags)
    buf._data = data

    with _registry_lock:
        heap.total_allocated += size
        heap.total_buffers += 1
        heap._buffers.append(buf.name)

    return buf


def dma_heap_free(buf_name: str) -> None:
    """Free a buffer allocated from a DMA heap — analogous to dma_heap_buffer_free().

    Returns the buffer's memory to the originating heap.
    """
    buf = _validate_buf(buf_name)

    # Find the originating heap
    with _registry_lock:
        heap = _heaps.get(buf.exp_name)
        if heap is not None and buf_name in heap._buffers:
            heap.total_allocated -= buf.size
            heap.total_buffers -= 1
            heap._buffers.remove(buf_name)

    # Release the dma_buf
    dma_buf_put(buf_name)


def dma_heap_get(name: str) -> DmaHeap:
    """Get a registered heap by name."""
    with _registry_lock:
        heap = _heaps.get(name)
    if heap is None:
        raise KeyError(f"Heap '{name}' not found")
    return heap


# ---------------------------------------------------------------------------
# Scatter-gather helpers
# ---------------------------------------------------------------------------

def dma_buf_get_sgt(
    buf_name: str,
    device_name: str,
) -> DmaSgTable:
    """Get scatter-gather table for an attachment.

    If the attachment is not yet mapped, this performs an implicit map.
    """
    buf = _validate_buf(buf_name)
    att = _validate_attachment(buf, device_name)

    if att._sgt:
        return DmaSgTable(
            entries=list(att._sgt),
            nents=len(att._sgt),
            orig_nents=len(att._sgt),
        )

    # Implicit map
    return dma_buf_map_attachment(buf_name, device_name)


def dma_buf_sgt_iterate(
    buf_name: str,
    device_name: str,
) -> List[Tuple[int, int]]:
    """Iterate scatter-gather entries — returns list of (dma_addr, length).

    Raises if the attachment is not mapped.
    """
    buf = _validate_buf(buf_name)
    att = _validate_attachment(buf, device_name)

    if not att._sgt:
        raise RuntimeError(
            f"Attachment for '{device_name}' on '{buf.name}' is not mapped"
        )

    return list(att._sgt)


# ---------------------------------------------------------------------------
# Status / helpers
# ---------------------------------------------------------------------------

def dma_buf_is_valid(buf_name: str) -> bool:
    """Check if a dma_buf exists and has live references."""
    return buf_name in _buffers and _buffers[buf_name]._refs > 0


def dma_buf_get_refs(buf_name: str) -> int:
    """Get the current reference count for a dma_buf."""
    buf = _validate_buf(buf_name)
    return buf._refs


def dma_buf_list_all() -> List[Dict[str, Any]]:
    """List all registered dma_bufs with summary information."""
    with _registry_lock:
        result = []
        for name, buf in _buffers.items():
            result.append({
                "name": buf.name,
                "size": buf.size,
                "fd": buf.fd,
                "exp_name": buf.exp_name,
                "flags": buf.flags,
                "refs": buf._refs,
                "mapped": buf._is_mapped,
                "vmapped": buf._is_vmapped,
                "attachments": sum(1 for a in buf._attachments if a.is_attached),
            })
        return result


def dma_buf_list_heaps() -> List[Dict[str, Any]]:
    """List all registered DMA heaps."""
    with _registry_lock:
        result = []
        for name, heap in _heaps.items():
            result.append({
                "name": heap.name,
                "type": heap.heap_type,
                "total_allocated": heap.total_allocated,
                "total_buffers": heap.total_buffers,
                "max_size": heap.max_size,
            })
        return result


# ---------------------------------------------------------------------------
# Module cleanup
# ---------------------------------------------------------------------------

def _cleanup() -> None:
    """Release all buffers and heaps — for clean shutdown."""
    global _buffers, _heaps, _fd_map, _fd_counter
    with _registry_lock:
        _buffers.clear()
        _heaps.clear()
        _fd_map.clear()
        _fd_counter = 100


# ---------------------------------------------------------------------------
# Demo / self-test
# ---------------------------------------------------------------------------

def _demo() -> None:
    """Comprehensive demo of the DMA Buffer Sharing framework."""
    _cleanup()

    print("=" * 72)
    print("UmerOS DMA Buffer Sharing Framework — Demo")
    print("=" * 72)

    # --- 1. Register heaps ---------------------------------------------------
    print("\n--- Registering DMA Heaps ---")
    sys_heap = dma_heap_register("system-heap", "system", max_size=64 * 1024 * 1024)
    cma_heap = dma_heap_register("cma-heap", "cma", max_size=128 * 1024 * 1024)
    carve_heap = dma_heap_register("carveout-heap", "carveout")
    ion_heap = dma_heap_register("ion-heap", "ion")

    for h in dma_buf_list_heaps():
        print(f"  Heap: {h['name']:20s}  type={h['type']:16s}  "
              f"allocated={h['total_allocated']:>10}  buffers={h['total_buffers']}")

    # --- 2. Allocate from heaps ----------------------------------------------
    print("\n--- Allocating Buffers from Heaps ---")
    buf_sys = dma_heap_alloc("system-heap", 4096, DMA_BUF_FLAGS_CACHED)
    print(f"  Allocated from system-heap: {buf_sys.name}  size={buf_sys.size}  fd={buf_sys.fd}")

    buf_cma = dma_heap_alloc("cma-heap", 65536, DMA_BUF_FLAGS_CONTIG | DMA_BUF_FLAGS_CMA)
    print(f"  Allocated from cma-heap:    {buf_cma.name}  size={buf_cma.size}  fd={buf_cma.fd}")

    buf_carve = dma_heap_alloc("carveout-heap", 8192)
    print(f"  Allocated from carveout:    {buf_carve.name}  size={buf_carve.size}  fd={buf_carve.fd}")

    buf_ion = dma_heap_alloc("ion-heap", 16384, DMA_BUF_FLAGS_UNCACHED)
    print(f"  Allocated from ion-heap:    {buf_ion.name}  size={buf_ion.size}  fd={buf_ion.fd}")

    # --- 3. Export dma_buf directly ------------------------------------------
    print("\n--- Exporting a DMA Buffer ---")
    exp_ops = DmaBufOps(name="test-exporter")
    exported = dma_buf_export("test-exporter", 32768, ops=exp_ops, flags=DMA_BUF_FLAGS_READ | DMA_BUF_FLAGS_WRITE)
    print(f"  Exported: {exported.name}  size={exported.size}  fd={exported.fd}")

    # --- 4. Attach devices ---------------------------------------------------
    print("\n--- Attaching Devices ---")
    devices = ["gpu", "display", "camera"]
    for dev in devices:
        att = dma_buf_attach(buf_cma.name, dev)
        print(f"  Attached '{dev}' to '{buf_cma.name}'  attached={att.is_attached}")

    # --- 5. Map for DMA and get scatter-gather table -------------------------
    print("\n--- Mapping Attachments for DMA ---")
    for dev in devices:
        sgt = dma_buf_map_attachment(buf_cma.name, dev, direction="bidirectional")
        print(f"  Device '{dev}':  nents={sgt.nents}  entries={sgt.entries[:3]}...")

    # --- 6. Pin / Unpin ------------------------------------------------------
    print("\n--- Pinning Buffer ---")
    dma_buf_pin(buf_cma.name, "gpu")
    att_gpu = _validate_attachment(buf_cma, "gpu")
    print(f"  GPU pinned={att_gpu.is_pinned}")

    dma_buf_unpin(buf_cma.name, "gpu")
    att_gpu = _validate_attachment(buf_cma, "gpu")
    print(f"  GPU pinned after unpin={att_gpu.is_pinned}")

    # --- 7. CPU access -------------------------------------------------------
    print("\n--- CPU Access ---")
    dma_buf_begin_cpu_access(buf_cma.name, mode="write")
    print(f"  begin_cpu_access(mode='write') on '{buf_cma.name}'")

    # Simulate writing data
    buf_cma._data[:8] = b"\xDE\xAD\xBE\xEF\xCA\xFE\xBA\xBE"
    print(f"  Wrote 8 bytes: {buf_cma._data[:8].hex()}")

    dma_buf_end_cpu_access(buf_cma.name, mode="write")
    print(f"  end_cpu_access(mode='write') on '{buf_cma.name}'")

    # --- 8. vmap / vunmap ----------------------------------------------------
    print("\n--- Virtual Mapping ---")
    vaddr = dma_buf_vmap(buf_cma.name)
    print(f"  vmap: virtual address = 0x{vaddr:016X}")

    dma_buf_vunmap(buf_cma.name)
    print(f"  vunmap: released")

    # --- 9. Mmap to userspace ------------------------------------------------
    print("\n--- Mmap to Userspace ---")
    offset = dma_buf_mmap(buf_cma.name, 0x7000_0000, buf_cma.size)
    print(f"  mmap: vma_start=0x{0x7000_0000:016X}  offset=0x{offset:016X}")

    # --- 10. Scatter-gather iteration ----------------------------------------
    print("\n--- Scatter-Gather Iteration ---")
    for dev in devices:
        entries = dma_buf_sgt_iterate(buf_cma.name, dev)
        print(f"  '{dev}': {len(entries)} entries")
        for i, (addr, length) in enumerate(entries[:5]):
            print(f"    [{i}] dma_addr=0x{addr:08X}  length={length}")

    # --- 11. List all buffers ------------------------------------------------
    print("\n--- All Registered DMA Buffers ---")
    for info in dma_buf_list_all():
        print(f"  {info['name']:40s}  size={info['size']:>8}  fd={info['fd']:>4}  "
              f"refs={info['refs']}  attached={info['attachments']}")

    # --- 12. List all heaps --------------------------------------------------
    print("\n--- All DMA Heaps ---")
    for h in dma_buf_list_heaps():
        print(f"  {h['name']:20s}  type={h['type']:16s}  "
              f"allocated={h['total_allocated']:>10}  buffers={h['total_buffers']}")

    # --- 13. Reference counting ----------------------------------------------
    print("\n--- Reference Counting ---")
    ref_buf = dma_heap_alloc("system-heap", 1024)
    print(f"  Allocated ref-test buf: {ref_buf.name}  initial refs: {dma_buf_get_refs(ref_buf.name)}")

    fd = ref_buf.fd
    ref1 = dma_buf_get(fd)
    print(f"  After dma_buf_get(fd={fd}): refs={dma_buf_get_refs(ref_buf.name)}")

    ref2 = dma_buf_get(fd)
    print(f"  After second get:          refs={dma_buf_get_refs(ref_buf.name)}")

    dma_buf_put(ref_buf.name)
    print(f"  After one put:             refs={dma_buf_get_refs(ref_buf.name)}")

    dma_buf_put(ref_buf.name)
    print(f"  After second put:          refs={dma_buf_get_refs(ref_buf.name)}")

    dma_heap_free(ref_buf.name)
    print(f"  Freed ref-test buf via dma_heap_free (refs dropped to 0, buf released)")

    # --- 14. Query helpers ---------------------------------------------------
    print("\n--- Query Helpers ---")
    print(f"  Valid '{buf_sys.name}': {dma_buf_is_valid(buf_sys.name)}")
    print(f"  Flags:  0x{dma_buf_get_flags(buf_sys.name):02X}")
    print(f"  Size:   {dma_buf_get_size(buf_sys.name)}")
    print(f"  Exp:    {dma_buf_get_exp_name(buf_sys.name)}")

    # --- 15. Detach devices and free -----------------------------------------
    print("\n--- Detaching and Freeing ---")
    # Re-attach and detach demo
    dma_buf_attach(buf_sys.name, "nic")
    sgt = dma_buf_map_attachment(buf_sys.name, "nic")
    print(f"  Attached and mapped 'nic' to '{buf_sys.name}': {sgt.nents} entries")

    dma_buf_unmap_attachment(buf_sys.name, "nic")
    dma_buf_detach(buf_sys.name, "nic")
    print(f"  Detached 'nic' from '{buf_sys.name}'")

    dma_heap_free(buf_sys.name)
    print(f"  Freed '{buf_sys.name}' from system-heap")

    dma_heap_free(buf_cma.name)
    print(f"  Freed '{buf_cma.name}' from cma-heap")

    dma_heap_free(buf_carve.name)
    dma_heap_free(buf_ion.name)
    dma_buf_put(exported.name)
    print(f"  Freed remaining heap buffers and exported buf")

    # Unregister heaps
    dma_heap_unregister("system-heap")
    dma_heap_unregister("cma-heap")
    dma_heap_unregister("carveout-heap")
    dma_heap_unregister("ion-heap")
    print(f"  All heaps unregistered")

    print("\n" + "=" * 72)
    print("Demo complete.")
    print("=" * 72)


if __name__ == "__main__":
    _demo()
