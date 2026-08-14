"""
UmerOS Perf Module
===================
Kernel perf event subsystem and ring buffer interface.
Implements performance counters, sampling, and ring buffer I/O.

Reference: docs.kernel.org/userspace-api/perf.html
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple
import struct
import threading
import time


# ============================================================================
# Constants
# ============================================================================

SUCCESS: int = 0
ERROR: int = 1
EINVAL: int = 22
ENOENT: int = 2
EACCES: int = 13
ENOMEM: int = 12
EBUSY: int = 16
EAGAIN: int = 11

PERF_TYPE_HARDWARE: int = 0
PERF_TYPE_SOFTWARE: int = 1
PERF_TYPE_TRACEPOINT: int = 2
PERF_TYPE_HW_CACHE: int = 3
PERF_TYPE_RAW: int = 4
PERF_TYPE_BREAKPOINT: int = 5

PERF_COUNT_HW_CPU_CYCLES: int = 0
PERF_COUNT_HW_INSTRUCTIONS: int = 1
PERF_COUNT_HW_CACHE_REFERENCES: int = 2
PERF_COUNT_HW_CACHE_MISSES: int = 3
PERF_COUNT_HW_BRANCH_INSTRUCTIONS: int = 4
PERF_COUNT_HW_BRANCH_MISSES: int = 5
PERF_COUNT_HW_BUS_CYCLES: int = 6
PERF_COUNT_HW_STALLED_CYCLES_FRONTEND: int = 7
PERF_COUNT_HW_STALLED_CYCLES_BACKEND: int = 8
PERF_COUNT_HW_REF_CPU_CYCLES: int = 9

PERF_COUNT_SW_CPU_CLOCK: int = 0
PERF_COUNT_SW_TASK_CLOCK: int = 1
PERF_COUNT_SW_PAGE_FAULTS_MIN: int = 2
PERF_COUNT_SW_PAGE_FAULTS_MAJ: int = 3
PERF_COUNT_SW_CONTEXT_SWITCHES: int = 4
PERF_COUNT_SW_CPU_MIGRATIONS: int = 5
PERF_COUNT_SW_PAGE_FAULTS: int = 6
PERF_COUNT_SW_ALIGNMENT_FAULTS: int = 7
PERF_COUNT_SW_EMULATION_FAULTS: int = 8
PERF_COUNT_SW_DUMMY: int = 9
PERF_COUNT_SW_BPF_OUTPUT: int = 10

PERF_SAMPLE_IP: int = 1
PERF_SAMPLE_TID: int = 2
PERF_SAMPLE_TIME: int = 4
PERF_SAMPLE_ADDR: int = 8
PERF_SAMPLE_READ: int = 16
PERF_SAMPLE_CALLCHAIN: int = 32
PERF_SAMPLE_ID: int = 64
PERF_SAMPLE_CPU: int = 128
PERF_SAMPLE_PERIOD: int = 256
PERF_SAMPLE_STREAM_ID: int = 512
PERF_SAMPLE_RAW: int = 1024
PERF_SAMPLE_BRANCH_STACK: int = 2048
PERF_SAMPLE_REGS_USER: int = 4096
PERF_SAMPLE_STACK_USER: int = 8192
PERF_SAMPLE_REGS_INTR: int = 16384
PERF_SAMPLE_DATA_SRC: int = 32768
PERF_SAMPLE_IDENTIFIER: int = 65536
PERF_SAMPLE_TRANSACTION: int = 131072
PERF_SAMPLE_REGS_INTR: int = 16384

PERF_ATTR_SIZE_VER1: int = 64
PERF_ATTR_SIZE_VER2: int = 72
PERF_ATTR_SIZE_VER3: int = 80
PERF_ATTR_SIZE_VER4: int = 96
PERF_ATTR_SIZE_VER5: int = 104

PERF_FLAG_FD_CLOEXEC: int = 8
PERF_FLAG_NONBLOCK: int = 1
PERF_FLAG_FD_OUTPUT: int = 2
PERF_FLAG_PID_CGROUP: int = 4

PERF_TYPE_SOFTWARE_MAX: int = 10
PERF_TYPE_HW_CACHE_MAX: int = 3

PERF_EVENT_IOC_ENABLE: int = 0x2400
PERF_EVENT_IOC_DISABLE: int = 0x2401
PERF_EVENT_IOC_REFRESH: int = 0x2402
PERF_EVENT_IOC_RESET: int = 0x2403
PERF_EVENT_IOC_PERIOD: int = 0x2404
PERF_EVENT_IOC_SET_OUTPUT: int = 0x2405
PERF_EVENT_IOC_SET_FILTER: int = 0x2406
PERF_EVENT_IOC_ID: int = 0x2407
PERF_EVENT_IOC_SET_BPF: int = 0x2408
PERF_EVENT_IOC_PAUSE_OUTPUT: int = 0x2409
PERF_EVENT_IOC_QUERY_BPF: int = 0x240A
PERF_EVENT_IOC_MODIFY_ATTRIBUTES: int = 0x240B


# ============================================================================
# Perf Enums
# ============================================================================

class PerfEventIOC(IntEnum):
    """Perf event ioctl commands."""
    ENABLE = PERF_EVENT_IOC_ENABLE
    DISABLE = PERF_EVENT_IOC_DISABLE
    REFRESH = PERF_EVENT_IOC_REFRESH
    RESET = PERF_EVENT_IOC_RESET
    PERIOD = PERF_EVENT_IOC_PERIOD
    SET_OUTPUT = PERF_EVENT_IOC_SET_OUTPUT
    SET_FILTER = PERF_EVENT_IOC_SET_FILTER
    ID = PERF_EVENT_IOC_ID
    SET_BPF = PERF_EVENT_IOC_SET_BPF
    PAUSE_OUTPUT = PERF_EVENT_IOC_PAUSE_OUTPUT
    QUERY_BPF = PERF_EVENT_IOC_QUERY_BPF
    MODIFY_ATTRIBUTES = PERF_EVENT_IOC_MODIFY_ATTRIBUTES


class PerfRecordType(IntEnum):
    """Perf record types."""
    PERF_RECORD_MMAP: int = 1
    PERF_RECORD_LOST: int = 2
    PERF_RECORD_COMM: int = 3
    PERF_RECORD_EXIT: int = 4
    PERF_RECORD_THROTTLE: int = 5
    PERF_RECORD_UNTHROTTLE: int = 6
    PERF_RECORD_FORK: int = 7
    PERF_RECORD_READ: int = 8
    PERF_RECORD_SAMPLE: int = 9
    PERF_RECORD_MMAP2: int = 10
    PERF_RECORD_AUX: int = 11
    PERF_RECORD_ITER: int = 12
    PERF_RECORD_CALLCHAIN: int = 13
    PERF_RECORD_LOST_SAMPLES: int = 14
    PERF_RECORD_SWITCH: int = 15
    PERF_RECORD_SWITCH_CPU_WIDE: int = 16
    PERF_RECORD_NAMESPACES: int = 17
    PERF_RECORD_STACK_TOP: int = 18
    PERF_RECORD_THREAD_MAP: int = 19
    PERF_RECORD_CPU_MAP: int = 20
    PERF_RECORD_STAT_CONFIG: int = 21
    PERF_RECORD_STAT: int = 22
    PERF_RECORD_STAT_ROUND: int = 23
    PERF_RECORD_EVENT_UPDATE: int = 24
    PERF_RECORD_HEADER_FEATURE: int = 25
    PERF_RECORD_HEADER_COMPRESSED: int = 26


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class PerfEventAttr:
    """Perf event attribute structure."""
    type: int = 0
    size: int = PERF_ATTR_SIZE_VER1
    config: int = 0
    sample_period_or_freq: int = 0
    sample_type: int = 0
    read_format: int = 0
    flags: int = 0
    wake_events: int = 0
    bp_type: int = 0
    config1: int = 0
    config2: int = 0
    branch_sample_type: int = 0
    sample_regs_user: int = 0
    sample_stack_user: int = 0
    clockid: int = 0
    sample_regs_intr: int = 0
    aux_watermark: int = 0
    sample_max_stack: int = 0
    __reserved_2: int = 0

    def pack(self) -> bytes:
        """Pack attribute structure."""
        return struct.pack(
            "IIiQQQQiQQQQQQiQiIi",
            self.type, self.size, self.config,
            self.sample_period_or_freq, self.sample_type,
            self.read_format, self.flags, self.wake_events,
            self.bp_type, self.config1, self.config2,
            self.branch_sample_type, self.sample_regs_user,
            self.sample_stack_user, self.clockid,
            self.sample_regs_intr, self.aux_watermark,
            self.sample_max_stack, self.__reserved_2
        )

    @classmethod
    def unpack(cls, data: bytes) -> PerfEventAttr:
        """Unpack attribute structure."""
        if len(data) < 64:
            raise ValueError("Data too short for perf_event_attr")
        fields = struct.unpack("IIiQQQQiQQQQQQiQiIi", data[:72])
        return cls(
            type=fields[0], size=fields[1], config=fields[2],
            sample_period_or_freq=fields[3], sample_type=fields[4],
            read_format=fields[5], flags=fields[6], wake_events=fields[7],
            bp_type=fields[8], config1=fields[9], config2=fields[10],
            branch_sample_type=fields[11], sample_regs_user=fields[12],
            sample_stack_user=fields[13], clockid=fields[14],
            sample_regs_intr=fields[15], aux_watermark=fields[16],
            sample_max_stack=fields[17]
        )


@dataclass
class PerfSampleRecord:
    """Perf sample record."""
    record_type: int = PerfRecordType.PERF_RECORD_SAMPLE
    misc: int = 0
    size: int = 0
    ip: int = 0
    pid: int = 0
    tid: int = 0
    time: int = 0
    addr: int = 0
    id: int = 0
    stream_id: int = 0
    period: int = 0
    cpu: int = 0
    callchain: List[int] = field(default_factory=list)
    raw_data: bytes = b""

    RECORD_HEADER_SIZE: int = 8

    def pack(self) -> bytes:
        """Pack sample record."""
        header = struct.pack("BBHi", self.record_type, self.misc, 0, self.RECORD_HEADER_SIZE + 48)
        body = struct.pack("QQiIQQQQQi",
                           self.ip, self.pid, self.tid, self.time,
                           self.addr, self.id, self.stream_id,
                           self.period, self.cpu)
        return header + body + self.raw_data

    @classmethod
    def unpack(cls, data: bytes) -> PerfSampleRecord:
        """Unpack sample record."""
        record_type, misc, _, size = struct.unpack("BBHi", data[:8])
        if len(data) < 56:
            return cls(record_type=record_type, misc=misc, size=size)
        ip, pid, tid, time, addr, rid, stream_id, period, cpu = struct.unpack(
            "QQiIQQQQQi", data[8:56]
        )
        return cls(
            record_type=record_type, misc=misc, size=size,
            ip=ip, pid=pid, tid=tid, time=time,
            addr=addr, id=rid, stream_id=stream_id,
            period=period, cpu=cpu
        )


@dataclass
class PerfRingBuffer:
    """Perf ring buffer for event delivery."""
    data: bytearray = field(default_factory=bytearray)
    head: int = 0
    tail: int = 0
    size: int = 0
    overwritten: bool = False
    lost_events: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __init__(self, size: int = 65536) -> None:
        self.size = size
        self.data = bytearray(size)
        self.head = 0
        self.tail = 0

    @property
    def available(self) -> int:
        """Available space in ring buffer."""
        return self.size - (self.head - self.tail)

    @property
    def used(self) -> int:
        """Used space in ring buffer."""
        return self.head - self.tail

    def write(self, data: bytes) -> int:
        """Write data to ring buffer."""
        with self.lock:
            data_len = len(data)
            if data_len > self.available:
                self.lost_events += 1
                return -EAGAIN

            offset = self.head % self.size
            end = offset + data_len

            if end <= self.size:
                self.data[offset:end] = data
            else:
                first = self.size - offset
                self.data[offset:offset + first] = data[:first]
                self.data[0:data_len - first] = data[first:]

            self.head += data_len
            return data_len

    def read(self, size: int) -> bytes:
        """Read data from ring buffer."""
        with self.lock:
            available = self.used
            if available == 0:
                return b""

            read_size = min(size, available)
            offset = self.tail % self.size
            end = offset + read_size

            result = bytes(self.data[offset:end]) if end <= self.size else (
                bytes(self.data[offset:self.size]) + bytes(self.data[0:end - self.size])
            )

            self.tail += read_size
            return result

    def reset(self) -> None:
        """Reset the ring buffer."""
        with self.lock:
            self.head = 0
            self.tail = 0
            self.lost_events = 0

    def peek(self, size: int) -> bytes:
        """Peek at data without consuming."""
        with self.lock:
            available = self.used
            if available == 0:
                return b""

            read_size = min(size, available)
            offset = self.tail % self.size
            end = offset + read_size

            return bytes(self.data[offset:end]) if end <= self.size else (
                bytes(self.data[offset:self.size]) + bytes(self.data[0:end - self.size])
            )


@dataclass
class PerfEvent:
    """A single perf event."""
    event_fd: int = 0
    attr: PerfEventAttr = field(default_factory=PerfEventAttr)
    pid: int = 0
    tid: int = 0
    cpu: int = 0
    group_fd: int = -1
    enabled: bool = False
    count: int = 0
    enabled_time: float = 0.0
    ring_buffer: Optional[PerfRingBuffer] = None

    def enable(self) -> int:
        """Enable the perf event."""
        self.enabled = True
        self.enabled_time = time.time()
        return SUCCESS

    def disable(self) -> int:
        """Disable the perf event."""
        self.enabled = False
        return SUCCESS

    def reset(self) -> int:
        """Reset the perf event count."""
        self.count = 0
        return SUCCESS

    def read_count(self) -> int:
        """Read the event count."""
        return self.count

    def add_sample(self, ip: int, period: int = 1) -> None:
        """Add a sample to the event."""
        self.count += period
        if self.ring_buffer:
            sample = PerfSampleRecord(
                ip=ip, pid=self.pid, tid=self.tid,
                time=int(time.time() * 1e9), period=period, cpu=self.cpu
            )
            self.ring_buffer.write(sample.pack())


@dataclass
class PerfEventGroup:
    """A group of perf events."""
    group_fd: int = 0
    events: Dict[int, PerfEvent] = field(default_factory=dict)
    leader_fd: int = -1

    def add_event(self, event: PerfEvent) -> int:
        """Add an event to the group."""
        self.events[event.event_fd] = event
        if self.leader_fd == -1:
            self.leader_fd = event.event_fd
        return SUCCESS

    def remove_event(self, event_fd: int) -> int:
        """Remove an event from the group."""
        self.events.pop(event_fd, None)
        return SUCCESS

    def enable(self) -> int:
        """Enable all events in the group."""
        for event in self.events.values():
            event.enable()
        return SUCCESS

    def disable(self) -> int:
        """Disable all events in the group."""
        for event in self.events.values():
            event.disable()
        return SUCCESS


# ============================================================================
# Perf Subsystem
# ============================================================================

class Perf:
    """Perf event subsystem."""
    def __init__(self) -> None:
        self.events: Dict[int, PerfEvent] = {}
        self.groups: Dict[int, PerfEventGroup] = {}
        self.ring_buffers: Dict[int, PerfRingBuffer] = {}
        self._next_event_fd: int = 1
        self._next_group_fd: int = 1
        self.lock: threading.Lock = threading.Lock()
        self.hw_counters: Dict[int, int] = {}
        self.sw_counters: Dict[int, int] = {}

    def create_event(self, attr: PerfEventAttr, pid: int = 0, cpu: int = 0,
                     group_fd: int = -1, flags: int = 0) -> PerfEvent:
        """Create a perf event."""
        with self.lock:
            event_fd = self._next_event_fd
            self._next_event_fd += 1

            ring_buf = PerfRingBuffer(65536)
            event = PerfEvent(
                event_fd=event_fd, attr=attr, pid=pid, cpu=cpu,
                group_fd=group_fd, ring_buffer=ring_buf
            )
            self.events[event_fd] = event
            self.ring_buffers[event_fd] = ring_buf
        return event

    def destroy_event(self, event_fd: int) -> int:
        """Destroy a perf event."""
        with self.lock:
            self.events.pop(event_fd, None)
            self.ring_buffers.pop(event_fd, None)
        return SUCCESS

    def enable_event(self, event_fd: int) -> int:
        """Enable a perf event."""
        event = self.events.get(event_fd)
        if event:
            return event.enable()
        return ENOENT

    def disable_event(self, event_fd: int) -> int:
        """Disable a perf event."""
        event = self.events.get(event_fd)
        if event:
            return event.disable()
        return ENOENT

    def read_event(self, event_fd: int) -> Optional[PerfEvent]:
        """Read a perf event."""
        return self.events.get(event_fd)

    def create_group(self) -> PerfEventGroup:
        """Create a perf event group."""
        with self.lock:
            group_fd = self._next_group_fd
            self._next_group_fd += 1
            group = PerfEventGroup(group_fd=group_fd)
            self.groups[group_fd] = group
        return group

    def destroy_group(self, group_fd: int) -> int:
        """Destroy a perf event group."""
        with self.lock:
            self.groups.pop(group_fd, None)
        return SUCCESS

    def add_event_to_group(self, group_fd: int, event: PerfEvent) -> int:
        """Add an event to a group."""
        group = self.groups.get(group_fd)
        if group:
            return group.add_event(event)
        return ENOENT

    def get_event_from_ring_buffer(self, event_fd: int, size: int) -> bytes:
        """Read from an event's ring buffer."""
        ring_buf = self.ring_buffers.get(event_fd)
        if ring_buf:
            return ring_buf.read(size)
        return b""

    def record_sample(self, event_fd: int, ip: int, period: int = 1) -> int:
        """Record a sample for an event."""
        event = self.events.get(event_fd)
        if event:
            event.add_sample(ip, period)
            return SUCCESS
        return ENOENT

    def get_stats(self) -> Dict[str, int]:
        """Get perf statistics."""
        return {
            "events": len(self.events),
            "groups": len(self.groups),
            "ring_buffers": len(self.ring_buffers),
            "total_samples": sum(e.count for e in self.events.values()),
        }


# ============================================================================
# Global Singleton Accessors
# ============================================================================

_global_perf: Optional[Perf] = None


def get_global_perf() -> Perf:
    """Get global Perf instance."""
    global _global_perf
    if _global_perf is None:
        _global_perf = Perf()
    return _global_perf
