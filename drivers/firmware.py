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
UmerOS Firmware Framework
==========================
Kernel firmware loading subsystem.
Implements firmware image loading, fallback mechanisms,
and platform firmware interfaces.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Firmware Constants
# ---------------------------------------------------------------------------
FW_OPT_NOWAIT: int = 0x01
FW_OPT_USERHELPER: int = 0x02
FW_OPT_NO_WARN: int = 0x04
FW_OPT_NO_FALLBACK: int = 0x08
FW_OPT_NOCACHE: int = 0x10

FW_STATUS_SUCCESS: str = "success"
FW_STATUS_LOADING: str = "loading"
FW_STATUS_FAILED: str = "failed"
FW_STATUS_PENDING: str = "pending"

# ---------------------------------------------------------------------------
# Global Registries
# ---------------------------------------------------------------------------
_firmware_images: Dict[str, FirmwareImage] = {}
_firmware_lookups: List[FirmwareLookup] = []
_firmware_cache: Dict[str, bytes] = {}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class FirmwareImage:
    """Loaded firmware image"""
    name: str
    data: bytes = b""
    size: int = 0
    status: str = FW_STATUS_PENDING
    is_pinned: bool = False
    load_time: float = 0.0
    source: str = ""  # "direct", "platform", "userhelper"
    _priv: Any = None


@dataclass
class FirmwareLookup:
    """Firmware search path/pattern"""
    name: str
    path: str
    priority: int = 0
    is_enabled: bool = True


@dataclass
class FirmwareOps:
    """Platform firmware operations"""
    name: str
    read: Optional[Callable] = None
    write: Optional[Callable] = None
    status: Optional[Callable] = None


# ---------------------------------------------------------------------------
# Built-in Firmware Database (simulated)
# ---------------------------------------------------------------------------
_BUILTIN_FW: Dict[str, bytes] = {
    "test.bin": b"\x01\x02\x03\x04\x05\x06\x07\x08",
    "calibration.bin": b"\xAA\xBB\xCC\xDD\xEE\xFF",
    "dsp_firmware.bin": b"\xDE\xAD\xBE\xEF" * 256,
}


# ---------------------------------------------------------------------------
# Registration Functions
# ---------------------------------------------------------------------------
def add_firmware_lookup(name: str, path: str, priority: int = 0) -> FirmwareLookup:
    """Add a firmware search path"""
    lookup = FirmwareLookup(name=name, path=path, priority=priority)
    _firmware_lookups.append(lookup)
    _firmware_lookups.sort(key=lambda x: x.priority, reverse=True)
    log.info("Added firmware lookup: %s -> %s (priority=%d)", name, path, priority)
    return lookup


def register_firmware(name: str, data: bytes, source: str = "direct") -> FirmwareImage:
    """Register a firmware image directly"""
    if name in _firmware_images:
        log.warning("Firmware %s already registered", name)
        return _firmware_images[name]

    fw = FirmwareImage(
        name=name,
        data=data,
        size=len(data),
        status=FW_STATUS_SUCCESS,
        source=source,
        load_time=time.time(),
    )
    _firmware_images[name] = fw
    log.info("Registered firmware: %s (%d bytes)", name, len(data))
    return fw


def unregister_firmware(name: str) -> bool:
    """Unregister a firmware image"""
    if name not in _firmware_images:
        log.warning("Firmware %s not found", name)
        return False

    fw = _firmware_images[name]
    if fw.is_pinned:
        log.warning("Cannot unregister pinned firmware %s", name)
        return False

    del _firmware_images[name]
    log.info("Unregistered firmware: %s", name)
    return True


def get_firmware(name: str) -> Optional[FirmwareImage]:
    """Get a loaded firmware image"""
    return _firmware_images.get(name)


def list_firmware() -> List[str]:
    """List all loaded firmware images"""
    return list(_firmware_images.keys())


# ---------------------------------------------------------------------------
# Firmware Loading Operations
# ---------------------------------------------------------------------------
def request_firmware(name: str, options: int = 0) -> Optional[FirmwareImage]:
    """Request firmware by name (load if not cached)"""
    # Check cache
    if name in _firmware_images and not (options & FW_OPT_NOCACHE):
        log.debug("Firmware %s served from cache", name)
        return _firmware_images[name]

    # Try direct registration
    fw = _firmware_images.get(name)
    if fw is not None:
        return fw

    # Try built-in
    if name in _BUILTIN_FW:
        data = _BUILTIN_FW[name]
        fw = register_firmware(name, data, source="direct")
        return fw

    # Try lookups
    for lookup in _firmware_lookups:
        if lookup.is_enabled:
            log.debug("Trying lookup %s for %s", lookup.name, name)
            # Simulated lookup

    # Mark as failed
    if not (options & FW_OPT_NO_FALLBACK):
        fw = FirmwareImage(name=name, status=FW_STATUS_FAILED, source="fallback")
        _firmware_images[name] = fw
        log.warning("Firmware %s not found", name)

    return None


def release_firmware(name: str) -> bool:
    """Release a firmware reference"""
    fw = get_firmware(name)
    if fw is None:
        return False

    if fw.is_pinned:
        log.debug("Firmware %s is pinned, not releasing", name)
        return True

    # Simulated release
    log.debug("Released firmware %s", name)
    return True


def pin_firmware(name: str) -> bool:
    """Pin firmware in memory (prevent eviction)"""
    fw = get_firmware(name)
    if fw is None:
        log.warning("Firmware %s not found", name)
        return False

    fw.is_pinned = True
    log.info("Pinned firmware: %s", name)
    return True


def unpin_firmware(name: str) -> bool:
    """Unpin firmware from memory"""
    fw = get_firmware(name)
    if fw is None:
        return False

    fw.is_pinned = False
    log.info("Unpinned firmware: %s", name)
    return True


def cache_firmware(name: str, data: bytes) -> None:
    """Cache firmware data"""
    _firmware_cache[name] = data
    log.debug("Cached firmware: %s (%d bytes)", name, len(data))


def get_firmware_size(name: str) -> int:
    """Get firmware image size"""
    fw = get_firmware(name)
    if fw is None:
        return 0
    return fw.size


def get_firmware_status(name: str) -> str:
    """Get firmware loading status"""
    fw = get_firmware(name)
    if fw is None:
        return FW_STATUS_PENDING
    return fw.status


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== UmerOS Firmware Framework Demo ===\n")

    # Add lookups
    add_firmware_lookup("platform", "/lib/firmware", priority=100)
    add_firmware_lookup("userhelper", "/etc/firmware", priority=50)

    # Request firmware
    print("--- Requesting firmware ---")
    fw1 = request_firmware("test.bin")
    if fw1:
        print(f"  {fw1.name}: {fw1.size} bytes, status={fw1.status}, source={fw1.source}")

    fw2 = request_firmware("dsp_firmware.bin")
    if fw2:
        print(f"  {fw2.name}: {fw2.size} bytes, status={fw2.status}")

    # Register custom firmware
    custom_data = b"\x01\x02\x03\x04"
    register_firmware("custom.bin", custom_data)
    print(f"\nCustom firmware: {get_firmware_size('custom.bin')} bytes")

    # Pin
    pin_firmware("test.bin")
    print(f"Pinned: {get_firmware('test.bin').is_pinned}")

    # Status
    print(f"\nAll firmware: {list_firmware()}")
    print(f"test.bin status: {get_firmware_status('test.bin')}")
