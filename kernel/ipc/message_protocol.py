"""Packed binary message protocol for UmerOS IPC Fastpath.

Message header format (packed, little-endian):
  magic: uint32        (0x554D4552 = 'UMER')
  msg_id: uint64
  sender_pid: uint32
  target_pid: uint32
  payload_size: uint32
  checksum: uint32
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from typing import Optional

MSG_MAGIC = 0x554D4552  # 'UMER'
HEADER_FORMAT = "<IQIIII"  # magic(4) + msg_id(8) + sender_pid(4) + target_pid(4) + payload_size(4) + checksum(4)
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)


@dataclass
class PackedHeader:
    """Binary IPC message header."""
    magic: int = MSG_MAGIC
    msg_id: int = 0
    sender_pid: int = 0
    target_pid: int = 0
    payload_size: int = 0
    checksum: int = 0

    def pack(self) -> bytes:
        """Pack header into binary bytes."""
        return struct.pack(
            HEADER_FORMAT,
            self.magic,
            self.msg_id,
            self.sender_pid,
            self.target_pid,
            self.payload_size,
            self.checksum,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "PackedHeader":
        """Unpack header from binary bytes."""
        if len(data) < HEADER_SIZE:
            raise ValueError(f"Insufficient data: need {HEADER_SIZE} bytes, got {len(data)}")
        magic, msg_id, sender_pid, target_pid, payload_size, checksum = struct.unpack(
            HEADER_FORMAT, data[:HEADER_SIZE]
        )
        if magic != MSG_MAGIC:
            raise ValueError(f"Invalid magic: expected 0x{MSG_MAGIC:08X}, got 0x{magic:08X}")
        return cls(
            magic=magic,
            msg_id=msg_id,
            sender_pid=sender_pid,
            target_pid=target_pid,
            payload_size=payload_size,
            checksum=checksum,
        )

    def compute_checksum(self, payload: bytes) -> int:
        """Compute CRC32 checksum of payload."""
        return zlib.crc32(payload) & 0xFFFFFFFF


@dataclass
class PackedMessage:
    """Complete IPC message with header and payload."""
    header: PackedHeader
    payload: bytes = b""

    def serialize(self) -> bytes:
        """Serialize message to bytes."""
        self.header.payload_size = len(self.payload)
        self.header.checksum = self.header.compute_checksum(self.payload)
        return self.header.pack() + self.payload

    @classmethod
    def deserialize(cls, data: bytes) -> "PackedMessage":
        """Deserialize message from bytes."""
        header = PackedHeader.unpack(data)
        payload = data[HEADER_SIZE:HEADER_SIZE + header.payload_size]
        if header.checksum != 0:
            computed = header.compute_checksum(payload)
            if computed != header.checksum:
                raise ValueError(f"Checksum mismatch: expected {header.checksum}, got {computed}")
        return cls(header=header, payload=payload)

    @property
    def total_size(self) -> int:
        return HEADER_SIZE + len(self.payload)