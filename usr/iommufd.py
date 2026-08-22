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
UmerOS IOMMUFD Module
======================
Kernel IOMMU file descriptor interface.
Implements IOMMU domain management, device binding, and DMA mapping.

Reference: docs.kernel.org/userspace-api/iommufd.html
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import threading


# ============================================================================
# Constants
# ============================================================================

SUCCESS: int = 0
ERROR: int = 1
EINVAL: int = 22
ENOMEM: int = 12
EBADF: int = 9
EEXIST: int = 17
ENOENT: int = 2
ENODEV: int = 19


class IOMMUFDDomainType(IntEnum):
    """IOMMUFD domain types."""
    IOMMUFD_DOMAIN_DMA: int = 1
    IOMMUFD_DOMAIN_DMA_NESTED: int = 2


class IOMMUFDCap(IntEnum):
    """IOMMUFD capabilities."""
    IOMMUFD_CAP_DMA: int = 1
    IOMMUFD_CAP_DMA_NESTED: int = 2
    IOMMUFD_CAP_IOAS: int = 3


class IOMMUFDMapFlags(IntEnum):
    """IOMMUFD mapping flags."""
    IOMMUFD_MAP_READ: int = 1 << 0
    IOMMUFD_MAP_WRITE: int = 1 << 1
    IOMMUFD_MAP_EXEC: int = 1 << 2
    IOMMUFD_MAP_RW: int = 3


class IOMMUFDDMAFlag(IntEnum):
    """IOMMUFD DMA flags."""
    IOMMUFD_DMA_FLAG_EXEC: int = 1 << 0
    IOMMUFD_DMA_FLAG_WRITE: int = 1 << 1
    IOMMUFD_DMA_FLAG_READ: int = 1 << 2
    IOMMUFD_DMA_FLAG_CACHE_COHERENT: int = 1 << 3
    IOMMUFD_DMA_FLAG_IOVA_RANGE: int = 1 << 4


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class IOMMUFDIOVARange:
    """IOVA range for IOMMU mapping."""
    start: int = 0
    end: int = 0
    size: int = 0
    mapped: bool = False

    def contains(self, iova: int) -> bool:
        """Check if an IOVA is in this range."""
        return self.start <= iova < self.end


@dataclass
class IOMMUFDMappedPage:
    """A mapped page in IOMMU domain."""
    iova: int = 0
    physical_addr: int = 0
    size: int = 0
    flags: IOMMUFDMapFlags = IOMMUFDMapFlags.IOMMUFD_MAP_READ
    valid: bool = False


@dataclass
class IOMMUFDDomain:
    """IOMMUFD IOMMU domain."""
    domain_id: int = 0
    domain_type: IOMMUFDDomainType = IOMMUFDDomainType.IOMMUFD_DOMAIN_DMA
    ioas_id: int = -1
    attached_devices: Set[str] = field(default_factory=set)
    mapped_pages: Dict[int, IOMMUFDMappedPage] = field(default_factory=dict)
    iova_ranges: List[IOMMUFDIOVARange] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)
    created: bool = True

    def attach_device(self, device_id: str) -> int:
        """Attach a device to this domain."""
        with self.lock:
            if device_id in self.attached_devices:
                return EEXIST
            self.attached_devices.add(device_id)
        return SUCCESS

    def detach_device(self, device_id: str) -> int:
        """Detach a device from this domain."""
        with self.lock:
            self.attached_devices.discard(device_id)
        return SUCCESS

    def map_page(self, iova: int, physical_addr: int, size: int, flags: IOMMUFDMapFlags = IOMMUFDMapFlags.IOMMUFD_MAP_RW) -> int:
        """Map a physical page to IOVA."""
        with self.lock:
            page = IOMMUFDMappedPage(iova=iova, physical_addr=physical_addr, size=size, flags=flags, valid=True)
            self.mapped_pages[iova] = page
        return SUCCESS

    def unmap_page(self, iova: int) -> int:
        """Unmap an IOVA."""
        with self.lock:
            self.mapped_pages.pop(iova, None)
        return SUCCESS

    def add_iova_range(self, start: int, size: int) -> IOMMUFDIOVARange:
        """Add an IOVA range."""
        rng = IOMMUFDIOVARange(start=start, end=start + size, size=size)
        self.iova_ranges.append(rng)
        return rng

    def lookup_iova(self, iova: int) -> Optional[IOMMUFDMappedPage]:
        """Lookup a mapped page by IOVA."""
        return self.mapped_pages.get(iova)

    def stats(self) -> Dict[str, int]:
        """Get domain statistics."""
        return {
            "domain_id": self.domain_id,
            "attached_devices": len(self.attached_devices),
            "mapped_pages": len(self.mapped_pages),
            "iova_ranges": len(self.iova_ranges),
        }


@dataclass
class IOMMUFDArea:
    """IOVA area management."""
    area_id: int = 0
    start: int = 0
    end: int = 0
    size: int = 0
    used: bool = False
    allocations: Dict[int, int] = field(default_factory=dict)

    def alloc(self, size: int) -> Optional[int]:
        """Allocate an IOVA from this area."""
        if self.start + size > self.end:
            return None
        iova = self.start
        self.allocations[iova] = size
        self.start += size
        return iova

    def free(self, iova: int) -> int:
        """Free an IOVA."""
        self.allocations.pop(iova, None)
        return SUCCESS


# ============================================================================
# IOMMUFD IOAS (IO Address Space)
# ============================================================================

@dataclass
class IOMMUFDIOAS:
    """IO Address Space for IOMMUFD."""
    ioas_id: int = 0
    name: str = ""
    domains: List[IOMMUFDDomain] = field(default_factory=list)
    areas: List[IOMMUFDArea] = field(default_factory=list)
    total_size: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def create_domain(self, domain_type: IOMMUFDDomainType = IOMMUFDDomainType.IOMMUFD_DOMAIN_DMA) -> IOMMUFDDomain:
        """Create a domain in this IOAS."""
        dom = IOMMUFDDomain(domain_id=len(self.domains), domain_type=domain_type, ioas_id=self.ioas_id)
        self.domains.append(dom)
        return dom

    def alloc_iova(self, size: int) -> Optional[int]:
        """Allocate an IOVA from this IOAS."""
        for area in self.areas:
            iova = area.alloc(size)
            if iova is not None:
                return iova
        area = IOMMUFDArea(area_id=len(self.areas), start=self.total_size, end=self.total_size + 1024 * 1024, size=1024 * 1024)
        self.areas.append(area)
        return area.alloc(size)

    def free_iova(self, iova: int) -> int:
        """Free an IOVA."""
        for area in self.areas:
            if area.start <= iova < area.end:
                return area.free(iova)
        return ERROR

    def stats(self) -> Dict[str, int]:
        """Get IOAS statistics."""
        return {"ioas_id": self.ioas_id, "domains": len(self.domains), "areas": len(self.areas), "total_size": self.total_size}


# ============================================================================
# IOMMUFD Manager
# ============================================================================

class IOMMUFDManager:
    """IOMMUFD subsystem manager."""
    _instance: Optional[IOMMUFDManager] = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    ioas_map: Dict[int, IOMMUFDIOAS] = field(default_factory=dict)
    domains: Dict[int, IOMMUFDDomain] = field(default_factory=dict)
    next_ioas_id: int = 0
    next_domain_id: int = 0
    capabilities: List[IOMMUFDCap] = field(default_factory=lambda: [IOMMUFDCap.IOMMUFD_CAP_DMA, IOMMUFDCap.IOMMUFD_CAP_IOAS])

    def __new__(cls) -> IOMMUFDManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def create_ioas(self, name: str = "") -> IOMMUFDIOAS:
        """Create an IO Address Space."""
        ioas = IOMMUFDIOAS(ioas_id=self.next_ioas_id, name=name)
        self.ioas_map[ioas.ioas_id] = ioas
        self.next_ioas_id += 1
        return ioas

    def create_domain(self, ioas_id: int, domain_type: IOMMUFDDomainType = IOMMUFDDomainType.IOMMUFD_DOMAIN_DMA) -> Optional[IOMMUFDDomain]:
        """Create a domain in an IOAS."""
        ioas = self.ioas_map.get(ioas_id)
        if not ioas:
            return None
        dom = ioas.create_domain(domain_type)
        dom.domain_id = self.next_domain_id
        self.next_domain_id += 1
        self.domains[dom.domain_id] = dom
        return dom

    def get_domain(self, domain_id: int) -> Optional[IOMMUFDDomain]:
        """Get a domain by ID."""
        return self.domains.get(domain_id)

    def get_ioas(self, ioas_id: int) -> Optional[IOMMUFDIOAS]:
        """Get an IOAS by ID."""
        return self.ioas_map.get(ioas_id)

    def list_domains(self) -> List[int]:
        """List all domain IDs."""
        return list(self.domains.keys())

    def list_ioas(self) -> List[int]:
        """List all IOAS IDs."""
        return list(self.ioas_map.keys())

    def get_capabilities(self) -> List[IOMMUFDCap]:
        """Get supported capabilities."""
        return self.capabilities


# ============================================================================
# Global Singleton Accessors
# ============================================================================

_global_iommufd_manager: Optional[IOMMUFDManager] = None


def get_global_iommufd_manager() -> IOMMUFDManager:
    """Get global IOMMUFD manager."""
    global _global_iommufd_manager
    if _global_iommufd_manager is None:
        _global_iommufd_manager = IOMMUFDManager()
    return _global_iommufd_manager
