# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
UmerOS Distributed Soft Bus - Session & Framing Protocol.

Implements binary framing with HMAC-SHA256 message integrity verification
for high-throughput inter-node message exchange across UmerOS instances.
"""

from __future__ import annotations

import hashlib
import hmac
import struct
import time
from dataclasses import dataclass
from typing import Optional, Tuple

FRAME_MAGIC: int = 0x534F4654  # "SOFT"
PROTOCOL_VERSION: int = 1

# Header format:
# Magic: uint32 (4B)
# Version: uint16 (2B)
# MsgType: uint16 (2B)
# MsgID: uint32 (4B)
# Timestamp: uint64 (8B)
# PayloadLength: uint32 (4B)
# HMAC Signature: 32 bytes (SHA-256)
# Total Header = 56 bytes
HEADER_FORMAT: str = "<IHHII32s"  # Note: 4+2+2+4+4 = 16B + 32s = 48B
HEADER_SIZE: int = struct.calcsize("<IHHII32s")


@dataclass
class SoftBusFrame:
    """Decoded SoftBus transport message frame."""

    msg_type: int
    msg_id: int
    payload: bytes
    timestamp: float = 0.0
    is_valid: bool = True


class SoftBusSession:
    """Manages channel framing and HMAC-SHA256 signing for inter-node communication."""

    def __init__(self, shared_secret: bytes = b"umeros_softbus_default_key_2026") -> None:
        self.shared_secret: bytes = shared_secret

    def encode_frame(self, msg_type: int, msg_id: int, payload: bytes) -> bytes:
        """Encode and sign a message payload into a binary SoftBus frame."""
        payload_len = len(payload)
        # Compute HMAC over (msg_type, msg_id, payload)
        h = hmac.new(self.shared_secret, digestmod=hashlib.sha256)
        h.update(struct.pack("<HHI", msg_type, msg_id, payload_len))
        h.update(payload)
        sig = h.digest()

        header = struct.pack(
            HEADER_FORMAT,
            FRAME_MAGIC,
            PROTOCOL_VERSION,
            msg_type,
            msg_id,
            payload_len,
            sig,
        )
        return header + payload

    def decode_frame(self, frame_bytes: bytes) -> Tuple[bool, Optional[SoftBusFrame]]:
        """Decode and verify a binary SoftBus frame.

        Returns:
            Tuple (is_valid, SoftBusFrame or None).
        """
        if len(frame_bytes) < HEADER_SIZE:
            return False, None

        magic, version, msg_type, msg_id, payload_len, sig = struct.unpack_from(
            HEADER_FORMAT, frame_bytes, 0
        )

        if magic != FRAME_MAGIC or version != PROTOCOL_VERSION:
            return False, None

        if len(frame_bytes) < HEADER_SIZE + payload_len:
            return False, None

        payload = frame_bytes[HEADER_SIZE : HEADER_SIZE + payload_len]

        # Verify HMAC signature
        h = hmac.new(self.shared_secret, digestmod=hashlib.sha256)
        h.update(struct.pack("<HHI", msg_type, msg_id, payload_len))
        h.update(payload)
        expected_sig = h.digest()

        if not hmac.compare_digest(sig, expected_sig):
            return False, SoftBusFrame(
                msg_type=msg_type,
                msg_id=msg_id,
                payload=payload,
                is_valid=False,
            )

        return True, SoftBusFrame(
            msg_type=msg_type,
            msg_id=msg_id,
            payload=payload,
            is_valid=True,
        )
