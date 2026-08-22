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
Umer OS Resource (I/O Port / MMIO) Tracking
============================================
``kernel/resource.c`` and ``<linux/ioport.h>``.

Represents hardware resources (I/O ports, MMIO regions, IRQ lines,
DMA channels) as a **tree of half-open intervals** ``[start, end]``.
A parent resource owns a big range; children carve out sub-ranges and
are refused if they overlap an existing sibling.

    struct resource {
        resource_size_t start, end;
        const char      *name;
        unsigned long    flags;       /* IORESOURCE_MEM | IORESOURCE_IO ... */
        struct resource *parent, *child, *sibling;
    };

This module reproduces that model so the UmerOS HAL can claim MMIO
ranges for "devices" and detect conflicts at registration time.

semantics preserved:
  * ``request_resource()``  – claim a region; fails on overlap.
  * ``release_resource()``  – release a previously-claimed region.
  * ``lookup_resource()``   – find the resource owning a given address.
  * ``request_region()``    – convenience: claim + name in one call.
  * ``check_region()``      – probe whether a region is free.
  * Resource flags (IORESOURCE_IO, MEM, IRQ, DMA).
  * Hierarchy: a child must lie entirely within its parent.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, Iterator, List, Optional

log = logging.getLogger("UmerOS.Resource")


# ── Resource type flags (mirrors IORESOURCE_*) ───────────────────────────

IORESOURCE_IO = 0x100       # I/O port region (x86 in/out)
IORESOURCE_MEM = 0x200      # Memory-mapped I/O region
IORESOURCE_IRQ = 0x400      # IRQ line
IORESOURCE_DMA = 0x800      # DMA channel
IORESOURCE_PREFETCH = 0x1000  # Prefetchable (for MEM regions)
IORESOURCE_READONLY = 0x2000
IORESOURCE_BUSY = 0x80000   # Region claimed by a driver

# Human-readable type names.
_TYPE_NAMES = {
    IORESOURCE_IO: "IO",
    IORESOURCE_MEM: "MEM",
    IORESOURCE_IRQ: "IRQ",
    IORESOURCE_DMA: "DMA",
}


def flag_name(flags: int) -> str:
    """Return a short string label for a resource's flags."""
    parts = [_TYPE_NAMES[t] for t in (IORESOURCE_IO, IORESOURCE_MEM,
                                      IORESOURCE_IRQ, IORESOURCE_DMA)
             if flags & t]
    if flags & IORESOURCE_PREFETCH:
        parts.append("PREFETCH")
    if flags & IORESOURCE_READONLY:
        parts.append("RO")
    if flags & IORESOURCE_BUSY:
        parts.append("BUSY")
    return "|".join(parts) or "NONE"


@dataclass
class Resource:
    """A claimed hardware resource range.

    Mirrors ``struct resource``.  A region is the half-open interval
    ``[start, end]`` (inclusive both ends).  ``owner`` is
    the PID or driver name that claimed it.

    Attributes:
        start: First address in the range (inclusive).
        end:   Last address in the range (inclusive).
        name:  Human label (e.g. "uart0").
        flags: Type + attributes bitmask (IORESOURCE_*).
        owner: Who claimed it (int PID or str driver name).
        children: Sub-ranges carved out of this region.
    """
    start: int
    end: int
    name: str = ""
    flags: int = 0
    owner: object = None
    children: List["Resource"] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(f"resource {self.name!r}: end({self.end}) < start({self.start})")
        self.flags |= IORESOURCE_BUSY

    # ── Geometry helpers ────────────────────────────────────────────────

    def size(self) -> int:
        """Number of addresses spanned (inclusive)."""
        return self.end - self.start + 1

    def contains(self, addr: int) -> bool:
        """True if ``addr`` lies in ``[start, end]``."""
        return self.start <= addr <= self.end

    def overlaps(self, other: "Resource") -> bool:
        """True if the two ranges share at least one address."""
        return not (self.end < other.start or other.end < self.start)

    def encloses(self, child: "Resource") -> bool:
        """True if ``child`` lies entirely within this region."""
        return self.start <= child.start and child.end <= self.end

    # ── Diagnostics ──────────────────────────────────────────────────────

    def describe(self) -> str:
        return (f"[{self.start:#x}-{self.end:#x}] "
                f"{flag_name(self.flags)} '{self.name or '?'}' "
                f"owner={self.owner}")


class ResourceConflictError(Exception):
    """Raised when a requested region overlaps an existing one."""


class ResourceManager:
    """A tree of resources rooted at top-level bus regions.

    ``iomem_resource`` and ``ioport_resource`` roots.
    Use :meth:`request_region` to claim a sub-range; the manager rejects
    any request that overlaps an existing sibling at the same level.
    """

    def __init__(self) -> None:
        # Two root resources (mirrors iomem_resource / ioport_resource).
        self.ioport_root = Resource(0, 0xFFFF, name="ioport",
                                    flags=IORESOURCE_IO)
        self.iomem_root = Resource(0, 0xFFFFFFFF, name="iomem",
                                   flags=IORESOURCE_MEM)
        self.irq_root = Resource(0, 256, name="irq",
                                 flags=IORESOURCE_IRQ)
        self.dma_root = Resource(0, 8, name="dma",
                                 flags=IORESOURCE_DMA)

    def _root_for(self, flags: int) -> Resource:
        if flags & IORESOURCE_IO:
            return self.ioport_root
        if flags & IORESOURCE_MEM:
            return self.iomem_root
        if flags & IORESOURCE_IRQ:
            return self.irq_root
        if flags & IORESOURCE_DMA:
            return self.dma_root
        raise ValueError(f"unknown resource type in flags={flags:#x}")

    # ── Claim / release ─────────────────────────────────────────────────

    def request_resource(self, parent: Resource, child: Resource) -> bool:
        """Try to register ``child`` under ``parent``.

        Returns True on success; raises :class:`ResourceConflictError`
        if ``child`` overlaps a sibling or escapes ``parent``.
        ``request_resource()``.
        """
        if not parent.encloses(child):
            raise ResourceConflictError(
                f"{child.name!r} [{child.start:#x}-{child.end:#x}] "
                f"escapes parent [{parent.start:#x}-{parent.end:#x}]")
        for sibling in parent.children:
            if sibling.overlaps(child):
                raise ResourceConflictError(
                    f"{child.name!r} overlaps existing "
                    f"{sibling.describe()}")
        parent.children.append(child)
        log.info("resource claimed: %s", child.describe())
        return True

    def release_resource(self, child: Resource) -> bool:
        """Release a previously-claimed resource.

        Walks all roots looking for the parent that owns ``child``.
        Returns True if found & removed, False if not registered.
        """
        for root in (self.ioport_root, self.iomem_root,
                     self.irq_root, self.dma_root):
            if self._release_recursive(root, child):
                log.info("resource released: %s", child.describe())
                return True
        return False

    def _release_recursive(self, parent: Resource, target: Resource) -> bool:
        for i, child in enumerate(parent.children):
            if child is target:
                parent.children.pop(i)
                return True
            if self._release_recursive(child, target):
                return True
        return False

    # ── Convenience API ─────────────────────────────────────────────────

    def request_region(self, start: int, n: int, name: str, *,
                       flags: int = IORESOURCE_MEM,
                       owner: object = None) -> Resource:
        """Claim ``n`` addresses starting at ``start``.

        ``request_mem_region()`` / ``request_region()``.
        Returns the new Resource on success.
        """
        root = self._root_for(flags)
        child = Resource(start, start + n - 1, name=name,
                         flags=flags, owner=owner)
        self.request_resource(root, child)
        return child

    def release_region(self, start: int, n: int, *, flags: int = IORESOURCE_MEM) -> bool:
        """Release a previously-claimed region by address+size."""
        res = self.lookup_resource(start, flags=flags)
        if res is None or res.size() != n:
            return False
        return self.release_resource(res)

    def check_region(self, start: int, n: int, *, flags: int = IORESOURCE_MEM) -> bool:
        """Return True if the region is currently free (mirrors ``check_region``)."""
        root = self._root_for(flags)
        probe = Resource(start, start + n - 1, name="__probe__", flags=flags)
        for sibling in root.children:
            if sibling.overlaps(probe):
                return False
        return True

    def lookup_resource(self, addr: int, *, flags: int = 0) -> Optional[Resource]:
        """Find the (deepest) resource owning ``addr``.

        If ``flags`` is given, restrict the search to the matching root.
        """
        roots: Iterable[Resource]
        if flags:
            roots = [self._root_for(flags)]
        else:
            roots = (self.ioport_root, self.iomem_root,
                     self.irq_root, self.dma_root)
        for root in roots:
            found = self._lookup_recursive(root, addr)
            if found is not None:
                return found
        return None

    def _lookup_recursive(self, node: Resource, addr: int) -> Optional[Resource]:
        deepest: Optional[Resource] = None
        for child in node.children:
            if child.contains(addr):
                # Descend for a tighter match.
                deeper = self._lookup_recursive(child, addr) or child
                if deepest is None or deeper.size() < deepest.size():
                    deepest = deeper
        return deepest

    # ── Enumeration ─────────────────────────────────────────────────────

    def walk(self, flags: int = 0) -> Iterator[Resource]:
        """Yield every claimed resource (optionally filtered by type)."""
        roots: Iterable[Resource]
        if flags:
            roots = [self._root_for(flags)]
        else:
            roots = (self.ioport_root, self.iomem_root,
                     self.irq_root, self.dma_root)
        for root in roots:
            yield from self._walk_recursive(root)

    def _walk_recursive(self, node: Resource) -> Iterator[Resource]:
        for child in node.children:
            yield child
            yield from self._walk_recursive(child)

    def status(self) -> dict:
        return {
            "ioport": sum(1 for _ in self.walk(IORESOURCE_IO)),
            "iomem": sum(1 for _ in self.walk(IORESOURCE_MEM)),
            "irq": sum(1 for _ in self.walk(IORESOURCE_IRQ)),
            "dma": sum(1 for _ in self.walk(IORESOURCE_DMA)),
        }


__all__ = [
    "Resource",
    "ResourceManager",
    "ResourceConflictError",
    "IORESOURCE_IO", "IORESOURCE_MEM", "IORESOURCE_IRQ", "IORESOURCE_DMA",
    "IORESOURCE_PREFETCH", "IORESOURCE_READONLY", "IORESOURCE_BUSY",
    "flag_name",
]
