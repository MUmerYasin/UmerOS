"""
KVM Binary Statistics
=====================

Python implementation of KVM binary statistics interface.
Based on linux/virt/kvm/binary_stats.c
"""

import struct
from dataclasses import dataclass, field
from typing import Optional, List, Any, BinaryIO
from io import BytesIO


# Constants
KVM_STATS_NAME_SIZE = 64
KVM_STATS_TYPE_SHIFT = 0
KVM_STATS_TYPE_MASK = (1 << 4) - 1
KVM_STATS_UNIT_SHIFT = 4
KVM_STATS_UNIT_MASK = (1 << 8) - 1
KVM_STATS_SCALE_SHIFT = 12
KVM_STATS_SCALE_MASK = (1 << 4) - 1

# Stat types
KVM_STATS_TYPE_CUMULATIVE = 0
KVM_STATS_TYPE_INSTANT = 1
KVM_STATS_TYPE_PEAK = 2
KVM_STATS_TYPE_LINEAR_HIST = 3
KVM_STATS_TYPE_LOG_HIST = 4

# Stat units
KVM_STATS_UNIT_NONE = 0
KVM_STATS_UNIT_BYTES = 1
KVM_STATS_UNIT_SECONDS = 2
KVM_STATS_UNIT_CYCLES = 3


@dataclass
class KVMStatsHeader:
    """KVM Statistics Header"""
    name_size: int = KVM_STATS_NAME_SIZE
    num_desc: int = 0
    id_offset: int = 0
    desc_offset: int = 0
    data_offset: int = 0
    
    def pack(self) -> bytes:
        """Pack header into bytes"""
        return struct.pack('<QQQQQ',
            self.name_size,
            self.num_desc,
            self.id_offset,
            self.desc_offset,
            self.data_offset)
    
    @classmethod
    def unpack(cls, data: bytes) -> 'KVMStatsHeader':
        """Unpack header from bytes"""
        name_size, num_desc, id_offset, desc_offset, data_offset = struct.unpack('<QQQQQ', data[:40])
        hdr = cls()
        hdr.name_size = name_size
        hdr.num_desc = num_desc
        hdr.id_offset = id_offset
        hdr.desc_offset = desc_offset
        hdr.data_offset = data_offset
        return hdr


@dataclass
class KVMStatsDesc:
    """KVM Statistics Descriptor"""
    offset: int = 0
    size: int = 0
    type: int = 0
    unit: int = 0
    scale: int = 0
    name: str = ""
    
    def pack(self) -> bytes:
        """Pack descriptor into bytes"""
        name_bytes = self.name.encode('utf-8')[:KVM_STATS_NAME_SIZE]
        name_bytes = name_bytes.ljust(KVM_STATS_NAME_SIZE, b'\x00')
        # Linux kernel uses: u64, u64, u32, u32, u32 = 8+8+4+4+4 = 24 bytes
        return struct.pack('<QQIII', 
            self.offset, self.size, self.type, self.unit, self.scale) + name_bytes
    
    @classmethod
    def unpack(cls, data: bytes) -> 'KVMStatsDesc':
        """Unpack descriptor from bytes"""
        offset, size, type_, unit, scale = struct.unpack('<QQIII', data[:28])
        name = data[28:28+KVM_STATS_NAME_SIZE].rstrip(b'\x00').decode('utf-8')
        desc = cls()
        desc.offset = offset
        desc.size = size
        desc.type = type_
        desc.unit = unit
        desc.scale = scale
        desc.name = name
        return desc


def kvm_stats_read(id_str: str, header: KVMStatsHeader,
                   desc: List[KVMStatsDesc], stats_data: bytes,
                   user_buffer: bytearray, size: int, offset: int) -> int:
    """
    Read binary statistics data.
    
    This is the Python equivalent of kvm_stats_read() from binary_stats.c
    """
    # Calculate sizes
    size_header = 40  # sizeof(KVMStatsHeader) - 5 * 8 bytes
    size_desc = header.num_desc * (24 + KVM_STATS_NAME_SIZE)  # sizeof(KVMStatsDesc)
    size_stats = len(stats_data)
    
    total_size = KVM_STATS_NAME_SIZE + size_header + size_desc + size_stats
    pos = offset
    remain = size
    
    if pos >= total_size:
        return 0
    
    len_to_read = min(total_size - pos, remain)
    if len_to_read <= 0:
        return 0
    
    remain = len_to_read
    dest = user_buffer
    dest_pos = 0
    
    # Create source buffer with all data
    src_buffer = BytesIO()
    src_buffer.write(header.pack())
    src_buffer.write(id_str.encode('utf-8').ljust(KVM_STATS_NAME_SIZE, b'\x00'))
    for d in desc:
        src_buffer.write(d.pack())
    src_buffer.write(stats_data)
    
    src_data = src_buffer.getvalue()
    
    # Copy requested range
    end_pos = min(pos + remain, len(src_data))
    copy_len = end_pos - pos
    
    if copy_len > 0:
        dest[:copy_len] = src_data[pos:end_pos]
    
    return copy_len


class KVMStatsBuilder:
    """Helper class to build KVM statistics"""
    
    def __init__(self, id_str: str):
        self.id_str = id_str
        self.descriptors: List[KVMStatsDesc] = []
        self.stats_data = bytearray()
        self._current_offset = 0
    
    def add_stat(self, name: str, value: int, size: int = 8,
                 type_: int = KVM_STATS_TYPE_CUMULATIVE,
                 unit: int = KVM_STATS_UNIT_NONE,
                 scale: int = 0) -> int:
        """Add a statistic"""
        desc = KVMStatsDesc(
            offset=self._current_offset,
            size=size,
            type=type_,
            unit=unit,
            scale=scale,
            name=name
        )
        self.descriptors.append(desc)
        
        # Pack value
        if size == 8:
            self.stats_data.extend(struct.pack('<Q', value))
        elif size == 4:
            self.stats_data.extend(struct.pack('<I', value))
        elif size == 2:
            self.stats_data.extend(struct.pack('<H', value))
        elif size == 1:
            self.stats_data.extend(struct.pack('<B', value))
        else:
            raise ValueError(f"Unsupported size: {size}")
        
        self._current_offset += size
        return len(self.descriptors) - 1
    
    def build_header(self) -> KVMStatsHeader:
        """Build the statistics header"""
        size_header = 40
        size_desc = len(self.descriptors) * (24 + KVM_STATS_NAME_SIZE)
        size_stats = len(self.stats_data)
        
        return KVMStatsHeader(
            name_size=KVM_STATS_NAME_SIZE,
            num_desc=len(self.descriptors),
            id_offset=size_header,
            desc_offset=size_header + KVM_STATS_NAME_SIZE,
            data_offset=size_header + KVM_STATS_NAME_SIZE + size_desc
        )
    
    def get_buffer(self) -> bytes:
        """Get complete statistics buffer"""
        header = self.build_header()
        buf = BytesIO()
        buf.write(header.pack())
        buf.write(self.id_str.encode('utf-8').ljust(KVM_STATS_NAME_SIZE, b'\x00'))
        for d in self.descriptors:
            buf.write(d.pack())
        buf.write(self.stats_data)
        return buf.getvalue()


# Pre-defined stat builders for VM and VCPU
def create_vm_stats_builder(vm_id: int) -> KVMStatsBuilder:
    """Create stats builder for VM"""
    builder = KVMStatsBuilder(f"kvm-vm-{vm_id}")
    
    # Common VM stats
    builder.add_stat("vcpu_count", 0, type_=KVM_STATS_TYPE_INSTANT)
    builder.add_stat("memory_size", 0, unit=KVM_STATS_UNIT_BYTES)
    builder.add_stat("dirty_pages", 0, type_=KVM_STATS_TYPE_INSTANT)
    builder.add_stat("io_exits", 0)
    builder.add_stat("mmio_exits", 0)
    builder.add_stat("hypercall_exits", 0)
    builder.add_stat("irq_injections", 0)
    builder.add_stat("halt_exits", 0)
    
    return builder


def create_vcpu_stats_builder(vcpu_id: int) -> KVMStatsBuilder:
    """Create stats builder for VCPU"""
    builder = KVMStatsBuilder(f"kvm-vcpu-{vcpu_id}")
    
    # Common VCPU stats
    builder.add_stat("exits", 0)
    builder.add_stat("io_exits", 0)
    builder.add_stat("mmio_exits", 0)
    builder.add_stat("hypercall_exits", 0)
    builder.add_stat("halt_exits", 0)
    builder.add_stat("irq_exits", 0)
    builder.add_stat("nmi_injections", 0)
    builder.add_stat("cpu_time_ns", 0, unit=KVM_STATS_UNIT_SECONDS, scale=3)
    builder.add_stat("guest_mode_time_ns", 0, unit=KVM_STATS_UNIT_SECONDS, scale=3)
    
    return builder