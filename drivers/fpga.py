"""
UmerOS FPGA Subsystem
=====================
Kernel-like FPGA (Field-Programmable Gate Array) framework.
Implements FPGA device management, bitstream loading,
region management, and bridge control.

Reference: Documentation/driver-api/fpga/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional


# ============================================================================
# FPGA Constants
# ============================================================================

FPGA_SUCCESS: int = 0
FPGA_ERR_INVALID: int = 1
FPGA_ERR_BUSY: int = 2
FPGA_ERR_FAILED: int = 3
FPGA_ERR_TIMEOUT: int = 4


class FPGAState(IntEnum):
    """FPGA state (mirrors fpga_mgr_states)."""
    UNKNOWN = 0
    POWER_OFF = 1
    POWER_UP = 2
    CONFIG = 3
    INIT = 4
    RUNNING = 5
    ERR = 6
    RECONFIG = 7


# ============================================================================
# FPGA Region
# ============================================================================

@dataclass
class FPGARegion:
    """FPGA region - a segment of FPGA fabric (mirrors struct fpga_region)."""
    name: str
    index: int
    fpga_mgr: Optional[str] = None
    bridges: List[str] = field(default_factory=list)
    firmware_name: str = ""
    external_firmware: bool = False
    base_addr: int = 0
    size: int = 0
    overlays_applied: int = 0

    def add_bridge(self, bridge_name: str) -> None:
        if bridge_name not in self.bridges:
            self.bridges.append(bridge_name)

    def remove_bridge(self, bridge_name: str) -> bool:
        if bridge_name in self.bridges:
            self.bridges.remove(bridge_name)
            return True
        return False


# ============================================================================
# FPGA Bridge
# ============================================================================

@dataclass
class FPGABridge:
    """FPGA bridge for managing data paths (mirrors struct fpga_bridge)."""
    name: str
    index: int
    region_name: str = ""
    enable: bool = False
    base_addr: int = 0
    size: int = 0
    data_width: int = 32
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)

    def enable_bridge(self) -> int:
        self.enable = True
        if "enable" in self._ops:
            return self._ops["enable"](self)
        return FPGA_SUCCESS

    def disable_bridge(self) -> int:
        self.enable = False
        if "disable" in self._ops:
            return self._ops["disable"](self)
        return FPGA_SUCCESS

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enable,
            "region": self.region_name,
            "base_addr": self.base_addr,
        }


# ============================================================================
# FPGA Manager
# ============================================================================

@dataclass
class FPGAManager:
    """FPGA manager for firmware loading (mirrors struct fpga_manager)."""
    name: str
    index: int
    state: FPGAState = FPGAState.UNKNOWN
    firmware_name: str = ""
    firmware_data: bytes = b''
    flags: int = 0
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)
    _regions: List[str] = field(default_factory=list)

    def load_bitstream(self, data: bytes, name: str = "") -> int:
        """Load a bitstream into the FPGA."""
        self.state = FPGAState.CONFIG
        self.firmware_data = data
        self.firmware_name = name or self.firmware_name
        if "load" in self._ops:
            result = self._ops["load"](self, data)
            self.state = FPGAState.RUNNING if result == FPGA_SUCCESS else FPGAState.ERR
            return result
        self.state = FPGAState.RUNNING
        return FPGA_SUCCESS

    def load_file(self, filepath: str) -> int:
        """Load bitstream from file path."""
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            return self.load_bitstream(data, filepath)
        except Exception:
            self.state = FPGAState.ERR
            return FPGA_ERR_FAILED

    def get_state(self) -> FPGAState:
        if "get_state" in self._ops:
            return self._ops["get_state"](self)
        return self.state

    def add_region(self, region_name: str) -> None:
        if region_name not in self._regions:
            self._regions.append(region_name)

    def register_ops(self, ops: Dict[str, Callable]) -> None:
        self._ops.update(ops)


# ============================================================================
# FPGA Image
# ============================================================================

@dataclass
class FPGAImage:
    """FPGA bitstream image metadata."""
    name: str
    data: bytes = b''
    format: str = "bit"  # bit, bin, rbf, zimage
    region: str = ""
    description: str = ""
    author: str = ""
    timestamp: float = 0.0


# ============================================================================
# FPGA Subsystem Manager
# ============================================================================

class FPGASubsystem:
    """Central FPGA subsystem managing managers, bridges, and regions."""

    def __init__(self) -> None:
        self._managers: Dict[str, FPGAManager] = {}
        self._bridges: Dict[str, FPGABridge] = {}
        self._regions: Dict[str, FPGARegion] = {}
        self._images: Dict[str, FPGAImage] = {}
        self._next_index: int = 0

    def register_manager(self, mgr: FPGAManager) -> int:
        mgr.index = self._next_index
        self._managers[mgr.name] = mgr
        self._next_index += 1
        return 0

    def unregister_manager(self, name: str) -> int:
        self._managers.pop(name, None)
        return 0

    def get_manager(self, name: str) -> Optional[FPGAManager]:
        return self._managers.get(name)

    def register_bridge(self, bridge: FPGABridge) -> int:
        bridge.index = self._next_index
        self._bridges[bridge.name] = bridge
        self._next_index += 1
        return 0

    def unregister_bridge(self, name: str) -> int:
        self._bridges.pop(name, None)
        return 0

    def get_bridge(self, name: str) -> Optional[FPGABridge]:
        return self._bridges.get(name)

    def register_region(self, region: FPGARegion) -> int:
        region.index = self._next_index
        self._regions[region.name] = region
        self._next_index += 1
        return 0

    def unregister_region(self, name: str) -> int:
        self._regions.pop(name, None)
        return 0

    def get_region(self, name: str) -> Optional[FPGARegion]:
        return self._regions.get(name)

    def store_image(self, image: FPGAImage) -> None:
        self._images[image.name] = image

    def load_image(self, manager_name: str, image_name: str) -> int:
        mgr = self._managers.get(manager_name)
        image = self._images.get(image_name)
        if not mgr or not image:
            return FPGA_ERR_INVALID
        return mgr.load_bitstream(image.data, image.name)

    def get_all_status(self) -> Dict[str, Any]:
        return {
            "managers": {n: m.state.name for n, m in self._managers.items()},
            "bridges": {n: b.get_status() for n, b in self._bridges.items()},
            "regions": {n: r.firmware_name for n, r in self._regions.items()},
        }


# ============================================================================
# Global FPGA Instance
# ============================================================================

_global_fpga: Optional[FPGASubsystem] = None


def get_global_fpga() -> FPGASubsystem:
    global _global_fpga
    if _global_fpga is None:
        _global_fpga = FPGASubsystem()
    return _global_fpga


def register_fpga_manager(mgr: FPGAManager) -> int:
    return get_global_fpga().register_manager(mgr)


def register_fpga_bridge(bridge: FPGABridge) -> int:
    return get_global_fpga().register_bridge(bridge)
