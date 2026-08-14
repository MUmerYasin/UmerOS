"""
UmerOS /dev/random, /dev/urandom — Entropy devices.

FHS 3.0 /dev/random:
  /dev/random   — Entropy pool; blocks when entropy is low.
  /dev/urandom  — Pseudo-random; never blocks, reuses pool.
  /dev/arandom  — Autoseeding urandom (if available).

 major:minor = 1:8 (random), 1:9 (urandom)

Note: For UmerOS simulation, uses Python's `os.urandom` and
`secrets` module for cryptographic-quality randomness.

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from typing import Any, Dict, List

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.Random")


class RandomDevice:
    """Character device providing entropy.

    /dev/random:
      - read(n) → n cryptographically random bytes (blocks if needed)
      - In simulation, always returns immediately

    /dev/urandom:
      - read(n) → n pseudo-random bytes (never blocks)
      - Suitable for most cryptographic purposes
    """

    # /dev/random: major 1, minor 8
    RANDOM_MAJOR = 1
    RANDOM_MINOR = 8
    RANDOM_PATH = "/dev/random"

    # /dev/urandom: major 1, minor 9
    URANDOM_MAJOR = 1
    URANDOM_MINOR = 9
    URANDOM_PATH = "/dev/urandom"

    # /dev/arandom: major 1, minor 4 (auto-seeding)
    ARANDOM_MAJOR = 1
    ARANDOM_MINOR = 4
    ARANDOM_PATH = "/dev/arandom"

    def __init__(self):
        self._total_read = 0
        self._read_count = 0
        self._devices: Dict[str, DeviceNode] = {}
        self._register_all()
        log.info("RandomDevice created (/dev/random, /dev/urandom, /dev/arandom)")

    def _register_all(self) -> None:
        mgr = DeviceManager.get_instance()
        devs = [
            DeviceNode(
                name="random", path=self.RANDOM_PATH, dev_type=DeviceType.CHAR,
                major=self.RANDOM_MAJOR, minor=self.RANDOM_MINOR, mode=0o644,
                description="Entropy pool (blocks on low entropy)",
                read_callback=self._on_read,
            ),
            DeviceNode(
                name="urandom", path=self.URANDOM_PATH, dev_type=DeviceType.CHAR,
                major=self.URANDOM_MAJOR, minor=self.URANDOM_MINOR, mode=0o644,
                description="Pseudo-random (never blocks)",
                read_callback=self._on_read,
            ),
            DeviceNode(
                name="arandom", path=self.ARANDOM_PATH, dev_type=DeviceType.CHAR,
                major=self.ARANDOM_MAJOR, minor=self.ARANDOM_MINOR, mode=0o644,
                description="Auto-seeding random",
                read_callback=self._on_read,
            ),
        ]
        for dev in devs:
            mgr.create_node(dev)
            self._devices[dev.path] = dev

    def _on_read(self, size: int) -> bytes:
        data = os.urandom(size)
        self._total_read += size
        self._read_count += 1
        return data

    def read_random(self, size: int = 4096) -> bytes:
        return self._on_read(size)

    def read_urandom(self, size: int = 4096) -> bytes:
        return self._on_read(size)

    def get_random_bits(self, bits: int) -> int:
        nbytes = (bits + 7) // 8
        data = os.urandom(nbytes)
        return int.from_bytes(data, "big") >> (nbytes * 8 - bits)

    def choice(self, seq):
        return secrets.choice(seq)

    def randbelow(self, n: int) -> int:
        return secrets.randbelow(n)

    def get_entropy_estimate(self) -> int:
        """Simulated entropy pool size in bits."""
        return 4096 * 8  # always full for simulation

    def get_info(self) -> Dict[str, Any]:
        return {
            "random": {"device": self.RANDOM_PATH, "type": "char", "major": self.RANDOM_MAJOR, "minor": self.RANDOM_MINOR},
            "urandom": {"device": self.URANDOM_PATH, "type": "char", "major": self.URANDOM_MAJOR, "minor": self.URANDOM_MINOR},
            "arandom": {"device": self.ARANDOM_PATH, "type": "char", "major": self.ARANDOM_MAJOR, "minor": self.ARANDOM_MINOR},
            "total_bytes_read": self._total_read,
            "read_count": self._read_count,
            "entropy_estimate_bits": self.get_entropy_estimate(),
        }

    def __repr__(self) -> str:
        return "<RandomDevice /dev/random, /dev/urandom>"
