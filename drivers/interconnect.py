"""
UmerOS Interconnect (NoC) Subsystem
====================================
Linux kernel-like interconnect (formerly NoC bus) framework for
managing bandwidth, clock, and path resources between hardware
components.

Reference: drivers/interconnect/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional


# ============================================================================
# Interconnect Constants
# ============================================================================

ICC_SUCCESS: int = 0
ICC_ERROR: int = 1
ICC_NOT_FOUND: int = 2

ICC_MAX_PATHS: int = 32
ICC_MAX_NODES: int = 128
ICC_MAX_PROVIDERS: int = 16


class ICCState(IntEnum):
    """Interconnect node state."""
    FREE: int = 0
    ACTIVE: int = 1
    SUSPENDED: int = 2
    ERROR: int = 3


class ICCRequestType(IntEnum):
    """Interconnect request type."""
    AVERAGE: int = 0
    PEAK: int = 1
    MAX: int = 2


# ============================================================================
# Interconnect Bandwidth
# ============================================================================

@dataclass
class ICCBandwidth:
    """Bandwidth requirement."""
    avg: int = 0  # average bandwidth in bytes/sec
    peak: int = 0  # peak bandwidth in bytes/sec
    ceiling: int = 0  # ceiling bandwidth

    def is_zero(self) -> bool:
        return self.avg == 0 and self.peak == 0


# ============================================================================
# Interconnect Node
# ============================================================================

@dataclass
class ICCNode:
    """Interconnect node (mirrors struct icc_node)."""
    name: str
    node_id: int
    state: ICCState = ICCState.FREE
    avg_bw: int = 0
    peak_bw: int = 0
    links: List[int] = field(default_factory=list)  # node IDs
    provider: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)

    def set_bandwidth(self, avg: int, peak: int) -> int:
        self.avg_bw = avg
        self.peak_bw = peak
        self.state = ICCState.ACTIVE if avg > 0 or peak > 0 else ICCState.FREE
        return ICC_SUCCESS

    def get_bandwidth(self) -> ICCBandwidth:
        return ICCBandwidth(avg=self.avg_bw, peak=self.peak_bw)

    def add_link(self, node_id: int) -> None:
        if node_id not in self.links:
            self.links.append(node_id)

    def remove_link(self, node_id: int) -> None:
        if node_id in self.links:
            self.links.remove(node_id)

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "node_id": self.node_id,
            "state": self.state.name,
            "avg_bw": self.avg_bw,
            "peak_bw": self.peak_bw,
            "links": len(self.links),
        }


# ============================================================================
# Interconnect Path
# ============================================================================

@dataclass
class ICCPath:
    """Interconnect path between two nodes."""
    source: int
    destination: int
    avg_bw: int = 0
    peak_bw: int = 0
    active: bool = False
    node_ids: List[int] = field(default_factory=list)


# ============================================================================
# Interconnect Provider
# ============================================================================

@dataclass
class ICCProvider:
    """Interconnect provider (mirrors struct icc_provider)."""
    name: str
    index: int
    nodes: Dict[int, ICCNode] = field(default_factory=dict)
    paths: List[ICCPath] = field(default_factory=list)
    registered: bool = False
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)

    def add_node(self, node: ICCNode) -> int:
        self.nodes[node.node_id] = node
        return ICC_SUCCESS

    def remove_node(self, node_id: int) -> int:
        self.nodes.pop(node_id, None)
        return ICC_SUCCESS

    def get_node(self, node_id: int) -> Optional[ICCNode]:
        return self.nodes.get(node_id)

    def create_path(self, src: int, dst: int) -> int:
        if src not in self.nodes or dst not in self.nodes:
            return ICC_ERROR
        path = ICCPath(source=src, destination=dst, node_ids=[src, dst])
        self.paths.append(path)
        self.nodes[src].add_link(dst)
        self.nodes[dst].add_link(src)
        return ICC_SUCCESS

    def set_bandwidth(self, node_id: int, avg: int, peak: int) -> int:
        node = self.nodes.get(node_id)
        return node.set_bandwidth(avg, peak) if node else ICC_ERROR

    def aggregate_bandwidth(self) -> int:
        total_avg = 0
        total_peak = 0
        for node in self.nodes.values():
            total_avg += node.avg_bw
            total_peak += node.peak_bw
        return total_avg + total_peak


# ============================================================================
# Interconnect Subsystem
# ============================================================================

class ICCSubsystem:
    """Central interconnect subsystem managing providers and paths."""

    def __init__(self) -> None:
        self._providers: Dict[str, ICCProvider] = {}
        self._next_index: int = 0

    def register_provider(self, provider: ICCProvider) -> int:
        provider.index = self._next_index
        provider.registered = True
        self._providers[provider.name] = provider
        self._next_index += 1
        return ICC_SUCCESS

    def unregister_provider(self, name: str) -> int:
        self._providers.pop(name, None)
        return ICC_SUCCESS

    def get_provider(self, name: str) -> Optional[ICCProvider]:
        return self._providers.get(name)

    def set_path_bandwidth(self, provider: str, src: int, dst: int, avg: int, peak: int) -> int:
        prov = self._providers.get(provider)
        if not prov:
            return ICC_ERROR
        node = prov.get_node(src)
        return node.set_bandwidth(avg, peak) if node else ICC_ERROR

    def get_topology(self) -> Dict[str, Any]:
        return {
            "providers": len(self._providers),
            "provider_names": list(self._providers.keys()),
            "total_nodes": sum(len(p.nodes) for p in self._providers.values()),
            "total_paths": sum(len(p.paths) for p in self._providers.values()),
        }


# ============================================================================
# Global Interconnect Instance
# ============================================================================

_global_icc: Optional[ICCSubsystem] = None


def get_global_icc() -> ICCSubsystem:
    global _global_icc
    if _global_icc is None:
        _global_icc = ICCSubsystem()
    return _global_icc


def register_icc_provider(provider: ICCProvider) -> int:
    return get_global_icc().register_provider(provider)


def icc_set_bandwidth(provider: str, node_id: int, avg: int, peak: int) -> int:
    return get_global_icc().set_path_bandwidth(provider, node_id, node_id, avg, peak)
