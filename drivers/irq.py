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
UmerOS IRQ/Interrupt Handling Framework
=======================================
Kernel interrupt management.
Implements IRQ descriptors, threaded handlers, IRQ chips,
IRQ domains, affinity, masking, and simulated GIC/IOAPIC controllers.
"""

from __future__ import annotations

import ctypes
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────
# IRQ Flags (IRQF_*)
# ─────────────────────────────────────────────────────────────
IRQF_SHARED = 0x00000800
IRQF_PROBE_SHARED = 0x00001000
IRQF_NO_THREAD = 0x00010000
IRQF_EARLY_RESUME = 0x00040000
IRQF_COND_SUSPEND = 0x00100000
IRQF_NO_SUSPEND = 0x00200000
IRQF_FORCE_RESUME = 0x00400000
IRQF_NO_BALANCING = 0x01000000
IRQF_PERCPU = 0x02000000
IRQF_TRIGGER_NONE = 0x00000000
IRQF_TRIGGER_RISING = 0x00000001
IRQF_TRIGGER_FALLING = 0x00000002
IRQF_TRIGGER_HIGH = 0x00000004
IRQF_TRIGGER_LOW = 0x00000008

IRQF_TRIGGER_EDGE = IRQF_TRIGGER_RISING | IRQF_TRIGGER_FALLING
IRQF_TRIGGER_LEVEL = IRQF_TRIGGER_HIGH | IRQF_TRIGGER_LOW
IRQF_TRIGGER_MASK = 0x0000000F
IRQF_TYPE_MASK = 0x0000000F

# ─────────────────────────────────────────────────────────────
# IRQ Descriptor Status Flags
# ─────────────────────────────────────────────────────────────
IRQS_AUTODETECT = 0x00000100
IRQS_SPURIOUS_DISABLED = 0x00000200
IRQS_POLL_IN_PROGRESS = 0x00000800
IRQS_ONESHOT = 0x00002000
IRQS_NOREQUEST = 0x00004000
IRQS_NO_DEBUG = 0x00008000
IRQS_MOVE_PCNTXT = 0x00040000
IRQS_IRQ_INPROGRESS = 0x00010000
IRQS_THREAD_INPROGRESS = 0x00020000
IRQS_REPLAYED = 0x00400000
IRQS_WAITING = 0x00800000
IRQS_PENDING = 0x01000000
IRQS_SUSPENDED = 0x02000000
IRQS_TIMERSYNC = 0x04000000
IRQS_PERCPU = 0x10000000
IRQS_NMI = 0x20000000
IRQS_POSTED = 0x40000000

IRQ_DESC_STATUS_NAMES: Dict[int, str] = {
    IRQS_AUTODETECT: "AUTODETECT",
    IRQS_SPURIOUS_DISABLED: "SPURIOUS_DISABLED",
    IRQS_POLL_IN_PROGRESS: "POLL_IN_PROGRESS",
    IRQS_ONESHOT: "ONESHOT",
    IRQS_NOREQUEST: "NOREQUEST",
    IRQS_NO_DEBUG: "NO_DEBUG",
    IRQS_MOVE_PCNTXT: "MOVE_PCNTXT",
    IRQS_IRQ_INPROGRESS: "IRQ_INPROGRESS",
    IRQS_THREAD_INPROGRESS: "THREAD_INPROGRESS",
    IRQS_REPLAYED: "REPLAYED",
    IRQS_WAITING: "WAITING",
    IRQS_PENDING: "PENDING",
    IRQS_SUSPENDED: "SUSPENDED",
    IRQS_TIMERSYNC: "TIMERSYNC",
    IRQS_PERCPU: "PERCPU",
    IRQS_NMI: "NMI",
    IRQS_POSTED: "POSTED",
}

# ─────────────────────────────────────────────────────────────
# Default handler sentinel
# ─────────────────────────────────────────────────────────────
def _default_irq_handler(irq: int, dev_id: object) -> int:
    """Default IRQ handler (noop)."""
    logging.debug("IRQ %d: default handler fired", irq)
    return 0


def _spurious_irq_handler(irq: int, dev_id: object) -> int:
    """Spurious IRQ handler – counts and warns."""
    logging.warning("IRQ %d: spurious interrupt detected", irq)
    return 0


# ═════════════════════════════════════════════════════════════
# Dataclasses – kernel objects
# ═════════════════════════════════════════════════════════════

@dataclass
class IrqDesc:
    """IRQ descriptor – core representation of an interrupt line."""
    irq: int
    name: str = ""
    status: int = 0
    depth: int = 0
    handler_data: Any = None
    action: Any = None          # IrqAction (first in linked list)
    chip: Any = None            # IrqChip
    domain: Any = None          # IrqDomain
    affinity: int = 0
    node: int = 0
    timer_rand_state: Any = None
    is_percpu: bool = False
    is_chained: bool = False
    is_setup: bool = False
    spurious_count: int = 0
    irq_count: int = 0
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    # ── helpers ──────────────────────────────────────────────
    def status_str(self) -> str:
        flags = []
        for bit, name in IRQ_DESC_STATUS_NAMES.items():
            if self.status & bit:
                flags.append(name)
        return "|".join(flags) if flags else "0"

    def is_disabled(self) -> bool:
        return self.depth > 0

    def action_count(self) -> int:
        count = 0
        cur = self.action
        while cur is not None:
            count += 1
            cur = cur.next
        return count

    def all_actions(self) -> List["IrqAction"]:
        result: List[IrqAction] = []
        cur = self.action
        while cur is not None:
            result.append(cur)
            cur = cur.next
        return result

    def __str__(self) -> str:
        state = "DISABLED" if self.is_disabled() else "ENABLED"
        return (
            f"IrqDesc(irq={self.irq}, name={self.name!r}, "
            f"state={state}, depth={self.depth}, "
            f"status=[{self.status_str()}], "
            f"actions={self.action_count()}, "
            f"chip={self.chip.name if self.chip else 'none'})"
        )


@dataclass
class IrqAction:
    """IRQ handler action – one registered handler per (irq, dev_id)."""
    handler: Callable[..., int]    # top-half callback
    thread_fn: Optional[Callable[..., int]] = None
    thread: Optional[threading.Thread] = None
    irq: int = 0
    flags: int = 0
    name: str = ""
    dev_id: Any = None
    next: Any = None               # linked list pointer
    is_disabled: bool = False
    irq_count: int = 0
    handler_time_ns: int = 0       # cumulative execution time
    thread_time_ns: int = 0

    def is_shared(self) -> bool:
        return bool(self.flags & IRQF_SHARED)

    def is_percpu(self) -> bool:
        return bool(self.flags & IRQF_PERCPU)

    def is_threaded(self) -> bool:
        return self.thread_fn is not None

    def __str__(self) -> str:
        flags_str = []
        if self.is_shared():
            flags_str.append("SHARED")
        if self.is_percpu():
            flags_str.append("PERCPU")
        if self.thread_fn:
            flags_str.append("THREADED")
        return (
            f"IrqAction(irq={self.irq}, name={self.name!r}, "
            f"dev_id={self.dev_id}, flags=[{'|'.join(flags_str) or '0'}], "
            f"disabled={self.is_disabled})"
        )


@dataclass
class IrqChip:
    """IRQ chip – abstraction over an interrupt controller."""
    name: str
    irq_startup: Optional[Callable[[int], int]] = None
    irq_shutdown: Optional[Callable[[int], None]] = None
    irq_enable: Optional[Callable[[int], None]] = None
    irq_disable: Optional[Callable[[int], None]] = None
    irq_ack: Optional[Callable[[int], None]] = None
    irq_mask: Optional[Callable[[int], None]] = None
    irq_unmask: Optional[Callable[[int], None]] = None
    irq_mask_ack: Optional[Callable[[int], None]] = None
    irq_eoi: Optional[Callable[[int], None]] = None
    irq_set_type: Optional[Callable[[int, int], int]] = None
    irq_set_affinity: Optional[Callable[[int, int], int]] = None
    irq_chip_flags: int = 0

    # ── convenience methods ──────────────────────────────────
    def startup(self, irq: int) -> int:
        if self.irq_startup:
            return self.irq_startup(irq)
        if self.irq_enable:
            self.irq_enable(irq)
        return 0

    def shutdown_chip(self, irq: int) -> None:
        if self.irq_shutdown:
            self.irq_shutdown(irq)
        elif self.irq_disable:
            self.irq_disable(irq)

    def enable_irq(self, irq: int) -> None:
        if self.irq_enable:
            self.irq_enable(irq)
        logging.debug("Chip %s: enable IRQ %d", self.name, irq)

    def disable_irq(self, irq: int) -> None:
        if self.irq_disable:
            self.irq_disable(irq)
        logging.debug("Chip %s: disable IRQ %d", self.name, irq)

    def ack_irq(self, irq: int) -> None:
        if self.irq_ack:
            self.irq_ack(irq)
        logging.debug("Chip %s: ack IRQ %d", self.name, irq)

    def mask_irq(self, irq: int) -> None:
        if self.irq_mask:
            self.irq_mask(irq)
        logging.debug("Chip %s: mask IRQ %d", self.name, irq)

    def unmask_irq(self, irq: int) -> None:
        if self.irq_unmask:
            self.irq_unmask(irq)
        logging.debug("Chip %s: unmask IRQ %d", self.name, irq)

    def mask_ack_irq(self, irq: int) -> None:
        if self.irq_mask_ack:
            self.irq_mask_ack(irq)
        else:
            self.mask_irq(irq)
            self.ack_irq(irq)
        logging.debug("Chip %s: mask+ack IRQ %d", self.name, irq)

    def eoi_irq(self, irq: int) -> None:
        if self.irq_eoi:
            self.irq_eoi(irq)

    def set_type(self, irq: int, trigger_type: int) -> int:
        if self.irq_set_type:
            return self.irq_set_type(irq, trigger_type)
        logging.debug("Chip %s: set_type IRQ %d -> 0x%x", self.name, irq, trigger_type)
        return 0

    def set_affinity(self, irq: int, cpu_mask: int) -> int:
        if self.irq_set_affinity:
            return self.irq_set_affinity(irq, cpu_mask)
        logging.debug("Chip %s: set_affinity IRQ %d -> 0x%x", self.name, irq, cpu_mask)
        return 0

    def __str__(self) -> str:
        caps = []
        if self.irq_startup:
            caps.append("startup")
        if self.irq_shutdown:
            caps.append("shutdown")
        if self.irq_enable:
            caps.append("enable")
        if self.irq_disable:
            caps.append("disable")
        if self.irq_ack:
            caps.append("ack")
        if self.irq_mask:
            caps.append("mask")
        if self.irq_unmask:
            caps.append("unmask")
        if self.irq_mask_ack:
            caps.append("mask_ack")
        if self.irq_eoi:
            caps.append("eoi")
        if self.irq_set_type:
            caps.append("set_type")
        if self.irq_set_affinity:
            caps.append("set_affinity")
        return f"IrqChip(name={self.name!r}, caps=[{', '.join(caps)}])"


@dataclass
class IrqDomain:
    """IRQ domain – maps hardware IRQ numbers to virtual IRQs."""
    name: str
    hwirq_base: int = 0
    size: int = 0
    revmap_type: int = 0  # 0=linear, 1=radix, 2=tree
    ops: Any = None
    _map: Dict[int, int] = field(default_factory=dict)   # hwirq -> virq
    _revmap: Dict[int, int] = field(default_factory=dict) # virq -> hwirq

    def associate(self, virq: int, hwirq: int) -> None:
        self._map[hwirq] = virq
        self._revmap[virq] = hwirq
        logging.debug(
            "Domain %s: associate hwirq=%d -> virq=%d",
            self.name, hwirq, virq,
        )

    def mapping(self, hwirq: int) -> Optional[int]:
        virq = self._map.get(hwirq)
        if virq is not None:
            logging.debug(
                "Domain %s: mapping hwirq=%d -> virq=%d",
                self.name, hwirq, virq,
            )
        return virq

    def revmap(self, virq: int) -> Optional[int]:
        return self._revmap.get(virq)

    def is_registered(self) -> bool:
        return self.size > 0

    def __str__(self) -> str:
        return (
            f"IrqDomain(name={self.name!r}, hwirq_base={self.hwirq_base}, "
            f"size={self.size}, mapped={len(self._map)})")


@dataclass
class IrqCommonData:
    """Common IRQ data – shared state for an IRQ line."""
    state: int = 0
    state_use_accessors: int = 0
    handler_data: Any = None
    affinity_data: Any = None
    Affinity: int = 0
    pending_mask: int = 0
    node: int = 0
    handler_stats: Dict[str, int] = field(default_factory=dict)

    def record_dispatch(self, source: str = "hardirq") -> None:
        self.handler_stats[source] = self.handler_stats.get(source, 0) + 1

    def __str__(self) -> str:
        return (
            f"IrqCommonData(state={self.state}, node={self.node}, "
            f"Affinity=0x{self.Affinity:08x}, "
            f"stats={dict(self.handler_stats)})")


# ═════════════════════════════════════════════════════════════
# Global registries
# ═════════════════════════════════════════════════════════════

_irq_descs: Dict[int, IrqDesc] = {}
_irq_chips: Dict[str, IrqChip] = {}
_irq_domains: Dict[str, IrqDomain] = {}
_irq_common: Dict[int, IrqCommonData] = {}
_default_handler: Callable[..., int] = _default_irq_handler
_irq_lock = threading.RLock()

# Per-CPU IRQ counters (simulated – single "CPU" 0)
_percpu_irq_counts: Dict[int, int] = {}

# Spurious IRQ tracking
_spurious_threshold = 9990  # after this many, disable


# ═════════════════════════════════════════════════════════════
# Internal helpers
# ═════════════════════════════════════════════════════════════

def _get_or_create_desc(irq: int, name: str = "") -> IrqDesc:
    with _irq_lock:
        if irq not in _irq_descs:
            _irq_descs[irq] = IrqDesc(irq=irq, name=name or f"irq-{irq}")
        else:
            if name:
                _irq_descs[irq].name = name
        if irq not in _irq_common:
            _irq_common[irq] = IrqCommonData()
        return _irq_descs[irq]


def _find_action_by_dev_id(desc: IrqDesc, dev_id: Any) -> Optional[IrqAction]:
    cur = desc.action
    while cur is not None:
        if cur.dev_id is dev_id:
            return cur
        cur = cur.next
    return None


def _remove_action(desc: IrqDesc, dev_id: Any) -> Optional[IrqAction]:
    prev = None
    cur = desc.action
    while cur is not None:
        if cur.dev_id is dev_id:
            if prev is None:
                desc.action = cur.next
            else:
                prev.next = cur.next
            cur.next = None
            return cur
        prev = cur
        cur = cur.next
    return None


def _trigger_type_name(t: int) -> str:
    names = {
        IRQF_TRIGGER_NONE: "NONE",
        IRQF_TRIGGER_RISING: "RISING",
        IRQF_TRIGGER_FALLING: "FALLING",
        IRQF_TRIGGER_HIGH: "HIGH",
        IRQF_TRIGGER_LOW: "LOW",
    }
    return names.get(t, f"0x{t:08x}")


# ═════════════════════════════════════════════════════════════
# Public API – Setup
# ═════════════════════════════════════════════════════════════

def request_irq(
    irq: int,
    handler: Callable[..., int],
    flags: int = 0,
    name: str = "",
    dev_id: Any = None,
) -> int:
    """Request an interrupt line – equivalent to request_irq()."""
    return request_threaded_irq(irq, handler, None, flags, name, dev_id)


def request_threaded_irq(
    irq: int,
    handler: Optional[Callable[..., int]],
    thread_fn: Optional[Callable[..., int]],
    flags: int = 0,
    name: str = "",
    dev_id: Any = None,
) -> int:
    """Request a threaded interrupt line."""
    with _irq_lock:
        desc = _get_or_create_desc(irq, name)

        if desc.status & IRQS_NOREQUEST:
            logging.error(
                "request_threaded_irq(%d): IRQ %d marked NOREQUEST", irq, irq
            )
            return -16  # -EBUSY

        if handler is None and thread_fn is None:
            logging.error(
                "request_threaded_irq(%d): no handler provided", irq
            )
            return -22  # -EINVAL

        # Check for duplicate (same dev_id)
        if _find_action_by_dev_id(desc, dev_id) is not None:
            logging.warning(
                "request_threaded_irq(%d): IRQ already requested "
                "for dev_id=%s", irq, dev_id,
            )
            return -16  # -EBUSY

        # Enforce shared: all actions on this IRQ must be shared
        existing = desc.action
        if existing is not None and not (flags & IRQF_SHARED):
            if not existing.is_shared():
                logging.error(
                    "request_threaded_irq(%d): IRQ not shared but "
                    "already has action", irq,
                )
                return -16  # -EBUSY

        action = IrqAction(
            handler=handler or _default_irq_handler,
            thread_fn=thread_fn,
            irq=irq,
            flags=flags,
            name=name or f"irq-{irq}",
            dev_id=dev_id,
        )

        # Insert at head of linked list
        action.next = desc.action
        desc.action = action
        desc.is_setup = True
        desc.name = name or desc.name

        if flags & IRQF_PERCPU:
            desc.is_percpu = True
            desc.status |= IRQS_PERCPU
            _percpu_irq_counts.setdefault(irq, 0)

        if flags & IRQF_NO_THREAD:
            desc.status |= IRQS_ONESHOT

        logging.info(
            "request_threaded_irq(%d): handler=%s, thread=%s, "
            "flags=0x%08x, name=%r, dev_id=%s",
            irq,
            handler.__name__ if handler else "none",
            thread_fn.__name__ if thread_fn else "none",
            flags,
            name,
            dev_id,
        )
        return 0


def free_irq(irq: int, dev_id: Any = None) -> Optional[IrqAction]:
    """Free an interrupt line – equivalent to free_irq()."""
    with _irq_lock:
        desc = _irq_descs.get(irq)
        if desc is None:
            logging.warning("free_irq(%d): no descriptor found", irq)
            return None

        action = _remove_action(desc, dev_id)
        if action is None:
            logging.warning(
                "free_irq(%d): no action for dev_id=%s", irq, dev_id,
            )
            return None

        # Stop threaded handler if running
        if action.thread is not None and action.thread.is_alive():
            logging.info(
                "free_irq(%d): stopping thread for action %r", irq, action.name,
            )
            # In real kernel this would kthread_stop; here we let it finish

        # If no actions left, mark as not setup
        if desc.action is None:
            desc.is_setup = False
            if desc.chip:
                desc.chip.shutdown_chip(irq)

        logging.info(
            "free_irq(%d): freed action %r, dev_id=%s", irq, action.name, dev_id,
        )
        return action


# ═════════════════════════════════════════════════════════════
# Public API – Enable / Disable
# ═════════════════════════════════════════════════════════════

def enable_irq(irq: int) -> int:
    """Enable IRQ – equivalent to enable_irq()."""
    with _irq_lock:
        desc = _irq_descs.get(irq)
        if desc is None:
            logging.error("enable_irq(%d): no descriptor", irq)
            return -22  # -EINVAL

        if desc.depth > 0:
            desc.depth -= 1
            if desc.depth == 0:
                if desc.chip:
                    desc.chip.enable_irq(irq)
                logging.debug("enable_irq(%d): now enabled (depth=0)", irq)
            else:
                logging.debug(
                    "enable_irq(%d): depth now %d", irq, desc.depth,
                )
        else:
            logging.debug("enable_irq(%d): already at depth 0", irq)
        return 0


def disable_irq(irq: int) -> int:
    """Disable IRQ synchronously – equivalent to disable_irq()."""
    return _do_disable_irq(irq, wait=True)


def disable_irq_nosync(irq: int) -> int:
    """Disable IRQ without waiting – equivalent to disable_irq_nosync()."""
    return _do_disable_irq(irq, wait=False)


def _do_disable_irq(irq: int, wait: bool) -> int:
    with _irq_lock:
        desc = _irq_descs.get(irq)
        if desc is None:
            logging.error("disable_irq(%d): no descriptor", irq)
            return -22  # -EINVAL

        if desc.depth == 0:
            if desc.chip:
                desc.chip.disable_irq(irq)
            logging.debug(
                "disable_irq(%d): depth now 1 (chip disabled=%s)",
                irq, wait,
            )
        desc.depth += 1
        return 0


def irq_set_disabled(irq: int) -> int:
    """Mark IRQ as disabled in descriptor."""
    with _irq_lock:
        desc = _irq_descs.get(irq)
        if desc is None:
            return -22
        if desc.depth == 0:
            desc.depth = 1
            if desc.chip:
                desc.chip.disable_irq(irq)
        return 0


def irq_set_enabled(irq: int) -> int:
    """Mark IRQ as enabled in descriptor."""
    return enable_irq(irq)


# ═════════════════════════════════════════════════════════════
# Public API – Acknowledgment
# ═════════════════════════════════════════════════════════════

def irq_ack(irq: int) -> int:
    """Acknowledge IRQ at the chip level."""
    with _irq_lock:
        desc = _irq_descs.get(irq)
        if desc is None:
            return -22
        if desc.chip:
            desc.chip.ack_irq(irq)
        return 0


def irq_chip_ack_parent(irq: int) -> int:
    """Acknowledge IRQ through parent chip (for hierarchical domains)."""
    with _irq_lock:
        desc = _irq_descs.get(irq)
        if desc is None:
            return -22
        # Walk up the domain hierarchy – if domain has a parent chip,
        # use it.  In our simulation the "parent" is the chip itself
        # if the domain is the top-level one.
        if desc.chip:
            desc.chip.ack_irq(irq)
            logging.debug("irq_chip_ack_parent(%d): acked via %s", irq, desc.chip.name)
        return 0


# ═════════════════════════════════════════════════════════════
# Public API – Masking
# ═════════════════════════════════════════════════════════════

def irq_mask(irq: int) -> int:
    """Mask IRQ at the chip level."""
    with _irq_lock:
        desc = _irq_descs.get(irq)
        if desc is None:
            return -22
        if desc.chip:
            desc.chip.mask_irq(irq)
        return 0


def irq_unmask(irq: int) -> int:
    """Unmask IRQ at the chip level."""
    with _irq_lock:
        desc = _irq_descs.get(irq)
        if desc is None:
            return -22
        if desc.chip:
            desc.chip.unmask_irq(irq)
        return 0


def irq_mask_ack(irq: int) -> int:
    """Mask and acknowledge IRQ simultaneously."""
    with _irq_lock:
        desc = _irq_descs.get(irq)
        if desc is None:
            return -22
        if desc.chip:
            desc.chip.mask_ack_irq(irq)
        return 0


# ═════════════════════════════════════════════════════════════
# Public API – Affinity
# ═════════════════════════════════════════════════════════════

def irq_set_affinity_hint(irq: int, cpu_mask: int) -> int:
    """Set CPU affinity hint for an IRQ (advisory, not enforced)."""
    with _irq_lock:
        desc = _irq_descs.get(irq)
        if desc is None:
            return -22
        desc.affinity = cpu_mask
        common = _irq_common.get(irq)
        if common:
            common.Affinity = cpu_mask
        logging.info(
            "irq_set_affinity_hint(%d): affinity -> 0x%08x", irq, cpu_mask,
        )
        return 0


def irq_set_affinity(irq: int, cpu: int) -> int:
    """Set CPU affinity for an IRQ (enforced by chip if available)."""
    with _irq_lock:
        desc = _irq_descs.get(irq)
        if desc is None:
            return -22
        mask = 1 << cpu
        if desc.chip:
            ret = desc.chip.set_affinity(irq, mask)
            if ret != 0:
                return ret
        desc.affinity = mask
        common = _irq_common.get(irq)
        if common:
            common.Affinity = mask
        logging.info(
            "irq_set_affinity(%d): cpu=%d, mask=0x%08x", irq, cpu, mask,
        )
        return 0


# ═════════════════════════════════════════════════════════════
# Public API – Trigger type
# ═════════════════════════════════════════════════════════════

def irq_set_irq_type(irq: int, trigger_type: int) -> int:
    """Set the trigger type for an IRQ (edge/level/etc)."""
    with _irq_lock:
        desc = _irq_descs.get(irq)
        if desc is None:
            return -22
        if desc.chip:
            ret = desc.chip.set_type(irq, trigger_type)
            if ret != 0:
                logging.error(
                    "irq_set_irq_type(%d): chip rejected type 0x%x",
                    irq, trigger_type,
                )
                return ret
        logging.info(
            "irq_set_irq_type(%d): type -> %s",
            irq, _trigger_type_name(trigger_type),
        )
        return 0


# ═════════════════════════════════════════════════════════════
# Public API – Domain
# ═════════════════════════════════════════════════════════════

def irq_domain_register(
    name: str,
    hwirq_base: int,
    size: int,
    ops: Any = None,
) -> IrqDomain:
    """Register an IRQ domain (maps hwirq -> virq)."""
    with _irq_lock:
        if name in _irq_domains:
            logging.warning("irq_domain_register(%r): already registered", name)
            return _irq_domains[name]
        domain = IrqDomain(
            name=name,
            hwirq_base=hwirq_base,
            size=size,
            ops=ops,
        )
        _irq_domains[name] = domain
        logging.info(
            "irq_domain_register(%r): hwirq_base=%d, size=%d",
            name, hwirq_base, size,
        )
        return domain


def irq_domain_unregister(name: str) -> bool:
    """Unregister an IRQ domain."""
    with _irq_lock:
        if name not in _irq_domains:
            logging.warning("irq_domain_unregister(%r): not found", name)
            return False
        domain = _irq_domains.pop(name)
        logging.info("irq_domain_unregister(%r): removed", domain.name)
        return True


def irq_domain_associate(domain_name: str, virq: int, hwirq: int) -> int:
    """Associate a hardware IRQ with a virtual IRQ inside a domain."""
    with _irq_lock:
        domain = _irq_domains.get(domain_name)
        if domain is None:
            logging.error("irq_domain_associate(%r): domain not found", domain_name)
            return -22
        domain.associate(virq, hwirq)
        # Ensure the IRQ descriptor exists
        _get_or_create_desc(virq, f"irq-{virq}")
        _irq_descs[virq].domain = domain
        return 0


def irq_domain_mapping(domain_name: str, hwirq: int) -> Optional[int]:
    """Map a hardware IRQ through a domain, returning the virtual IRQ."""
    with _irq_lock:
        domain = _irq_domains.get(domain_name)
        if domain is None:
            logging.error("irq_domain_mapping(%r): domain not found", domain_name)
            return None
        return domain.mapping(hwirq)


# ═════════════════════════════════════════════════════════════
# Public API – Threaded IRQ
# ═════════════════════════════════════════════════════════════

def irq_thread_fn(irq: int) -> int:
    """Simulate running the threaded handler for an IRQ."""
    with _irq_lock:
        desc = _irq_descs.get(irq)
        if desc is None:
            return -22

        action = desc.action
        while action is not None:
            if action.thread_fn and not action.is_disabled:
                desc.status |= IRQS_THREAD_INPROGRESS
                try:
                    t0 = time.perf_counter_ns()
                    ret = action.thread_fn(irq, action.dev_id)
                    elapsed = time.perf_counter_ns() - t0
                    action.thread_time_ns += elapsed
                    logging.debug(
                        "irq_thread_fn(%d): action=%r returned %s "
                        "in %.3f us",
                        irq, action.name, ret, elapsed / 1000.0,
                    )
                except Exception as exc:
                    logging.error(
                        "irq_thread_fn(%d): action=%r raised %s: %s",
                        irq, action.name, type(exc).__name__, exc,
                    )
                finally:
                    desc.status &= ~IRQS_THREAD_INPROGRESS
            action = action.next
        return 0


def irq_set_default_handler(handler: Callable[..., int]) -> None:
    """Set the default IRQ handler used when no specific handler is registered."""
    global _default_handler
    with _irq_lock:
        _default_handler = handler
        logging.info(
            "irq_set_default_handler: set to %s", handler.__name__,
        )


# ═════════════════════════════════════════════════════════════
# Public API – Statistics / Info
# ═════════════════════════════════════════════════════════════

def irq_get_stats(irq: int) -> Optional[Dict[str, Any]]:
    """Return statistics for an IRQ."""
    with _irq_lock:
        desc = _irq_descs.get(irq)
        if desc is None:
            return None
        common = _irq_common.get(irq)
        actions = desc.all_actions()
        return {
            "irq": irq,
            "name": desc.name,
            "depth": desc.depth,
            "disabled": desc.is_disabled(),
            "status": desc.status_str(),
            "status_raw": desc.status,
            "irq_count": desc.irq_count,
            "spurious_count": desc.spurious_count,
            "action_count": len(actions),
            "is_percpu": desc.is_percpu,
            "is_chained": desc.is_chained,
            "affinity": f"0x{desc.affinity:08x}",
            "node": desc.node,
            "chip": desc.chip.name if desc.chip else None,
            "domain": desc.domain.name if desc.domain else None,
            "common": str(common) if common else None,
            "actions": [
                {
                    "name": a.name,
                    "irq": a.irq,
                    "flags": f"0x{a.flags:08x}",
                    "dev_id": str(a.dev_id),
                    "irq_count": a.irq_count,
                    "handler_time_ns": a.handler_time_ns,
                    "thread_time_ns": a.thread_time_ns,
                    "disabled": a.is_disabled,
                    "shared": a.is_shared(),
                    "percpu": a.is_percpu(),
                    "threaded": a.is_threaded(),
                }
                for a in actions
            ],
        }


def irq_get_desc_name(irq: int) -> str:
    """Return the name of an IRQ descriptor."""
    with _irq_lock:
        desc = _irq_descs.get(irq)
        return desc.name if desc else ""


def irq_get_chip(irq: int) -> Optional[IrqChip]:
    """Return the IRQ chip for an IRQ."""
    with _irq_lock:
        desc = _irq_descs.get(irq)
        return desc.chip if desc else None


# ═════════════════════════════════════════════════════════════
# Public API – Spurious / Probe
# ═════════════════════════════════════════════════════════════

def irq_set_noprobe(irq: int) -> int:
    """Mark IRQ as not probe-able."""
    with _irq_lock:
        desc = _irq_descs.get(irq)
        if desc is None:
            return -22
        desc.status |= IRQS_NOREQUEST
        logging.info("irq_set_noprobe(%d): marked NOREQUEST", irq)
        return 0


def irq_set_probe(irq: int) -> int:
    """Allow IRQ probing (clear NOREQUEST)."""
    with _irq_lock:
        desc = _irq_descs.get(irq)
        if desc is None:
            return -22
        desc.status &= ~IRQS_NOREQUEST
        logging.info("irq_set_probe(%d): probing allowed", irq)
        return 0


# ═════════════════════════════════════════════════════════════
# Public API – Listing
# ═════════════════════════════════════════════════════════════

def irq_list_all() -> List[IrqDesc]:
    """Return a list of all registered IRQ descriptors."""
    with _irq_lock:
        return sorted(_irq_descs.values(), key=lambda d: d.irq)


def irq_list_actions(irq: int) -> List[IrqAction]:
    """Return all registered actions for a given IRQ."""
    with _irq_lock:
        desc = _irq_descs.get(irq)
        if desc is None:
            return []
        return desc.all_actions()


# ═════════════════════════════════════════════════════════════
# Spurious IRQ detection (called from dispatch simulation)
# ═════════════════════════════════════════════════════════════

def _check_spurious(irq: int, desc: IrqDesc) -> bool:
    """Check if IRQ is spurious; returns True if it should be skipped."""
    actions = desc.all_actions()
    if not actions:
        desc.spurious_count += 1
        if desc.spurious_count >= _spurious_threshold:
            desc.status |= IRQS_SPURIOUS_DISABLED
            logging.warning(
                "IRQ %d: DISABLED after %d spurious interrupts",
                irq, desc.spurious_count,
            )
        return True
    return False


# ═════════════════════════════════════════════════════════════
# Public API – Dispatch simulation
# ═════════════════════════════════════════════════════════════

def irq_dispatch(irq: int) -> int:
    """
    Simulate firing an IRQ – invoke all registered handlers.
    Returns 0 on success, negative on error.
    """
    with _irq_lock:
        desc = _irq_descs.get(irq)
        if desc is None:
            logging.error("irq_dispatch(%d): no descriptor", irq)
            return -22

        if desc.is_disabled():
            desc.status |= IRQS_PENDING
            logging.debug("irq_dispatch(%d): IRQ disabled, deferred", irq)
            return 0

        if desc.status & IRQS_IRQ_INPROGRESS:
            logging.debug("irq_dispatch(%d): already in progress", irq)
            return 0

        if _check_spurious(irq, desc):
            logging.debug("irq_dispatch(%d): spurious, skipped", irq)
            return 0

        desc.status |= IRQS_IRQ_INPROGRESS
        desc.irq_count += 1

        # Record in common data
        common = _irq_common.get(irq)
        if common:
            common.record_dispatch("hardirq")

    # Run outside lock (simulated hardirq context)
    try:
        desc = _irq_descs.get(irq)
        if desc is None:
            return -22

        # Acknowledge if chip supports it
        if desc.chip:
            desc.chip.ack_irq(irq)

        # Invoke all handlers
        actions = desc.all_actions()
        handled = 0
        for action in actions:
            if action.is_disabled:
                continue
            try:
                t0 = time.perf_counter_ns()
                ret = action.handler(irq, action.dev_id)
                elapsed = time.perf_counter_ns() - t0
                action.handler_time_ns += elapsed
                action.irq_count += 1
                if ret == 1:
                    handled += 1
                    logging.debug(
                        "irq_dispatch(%d): action %r handled IRQ "
                        "(%.3f us)",
                        irq, action.name, elapsed / 1000.0,
                    )
                elif ret == 0:
                    logging.debug(
                        "irq_dispatch(%d): action %r returned NONE "
                        "(%.3f us)",
                        irq, action.name, elapsed / 1000.0,
                    )
            except Exception as exc:
                logging.error(
                    "irq_dispatch(%d): action %r raised %s: %s",
                    irq, action.name, type(exc).__name__, exc,
                )

        # End of interrupt
        if desc.chip:
            desc.chip.eoi_irq(irq)

        return 0

    finally:
        with _irq_lock:
            desc = _irq_descs.get(irq)
            if desc:
                desc.status &= ~IRQS_IRQ_INPROGRESS
                if not (desc.status & IRQS_PENDING):
                    pass
                else:
                    desc.status &= ~IRQS_PENDING


# ═════════════════════════════════════════════════════════════
# Built-in interrupt controllers
# ═════════════════════════════════════════════════════════════

class GicController:
    """
    ARM Generic Interrupt Controller (GIC).

    Creates a GIC-style IRQ chip with 1020 (configurable) IRQ lines.
    Each line gets an IrqChip operation stub and an IrqDesc.
    """

    def __init__(self, name: str = "gic", n_irqs: int = 1020) -> None:
        self.name = name
        self.n_irqs = n_irqs
        self._enabled: set[int] = set()
        self._masked: set[int] = set()
        self._trigger_types: Dict[int, int] = {}

        def _gic_enable(irq: int) -> None:
            self._enabled.add(irq)
            self._masked.discard(irq)

        def _gic_disable(irq: int) -> None:
            self._enabled.discard(irq)

        def _gic_ack(irq: int) -> None:
            pass  # GIC acknowledges automatically on EOI

        def _gic_mask(irq: int) -> None:
            self._masked.add(irq)
            self._enabled.discard(irq)

        def _gic_unmask(irq: int) -> None:
            self._masked.discard(irq)
            self._enabled.add(irq)

        def _gic_mask_ack(irq: int) -> None:
            self._masked.add(irq)
            self._enabled.discard(irq)

        def _gic_eoi(irq: int) -> None:
            pass  # End of interrupt

        def _gic_set_type(irq: int, t: int) -> int:
            self._trigger_types[irq] = t
            return 0

        def _gic_set_affinity(irq: int, mask: int) -> int:
            logging.debug("GIC %s: IRQ %d affinity -> 0x%08x", name, irq, mask)
            return 0

        chip = IrqChip(
            name=name,
            irq_enable=_gic_enable,
            irq_disable=_gic_disable,
            irq_ack=_gic_ack,
            irq_mask=_gic_mask,
            irq_unmask=_gic_unmask,
            irq_mask_ack=_gic_mask_ack,
            irq_eoi=_gic_eoi,
            irq_set_type=_gic_set_type,
            irq_set_affinity=_gic_set_affinity,
            irq_chip_flags=0,
        )

        # Register the chip globally
        _irq_chips[name] = chip

        # Create descriptors for all IRQ lines
        for i in range(n_irqs):
            desc = _get_or_create_desc(i, f"{name}-{i}")
            desc.chip = chip

        logging.info(
            "GicController(%r): created with %d IRQs", name, n_irqs,
        )

    def get_chip(self) -> IrqChip:
        return _irq_chips[self.name]

    def __str__(self) -> str:
        return (
            f"GicController(name={self.name!r}, n_irqs={self.n_irqs}, "
            f"enabled={len(self._enabled)}, masked={len(self._masked)})")


class IoapicController:
    """
    x86 I/O APIC interrupt controller.

    Creates an IOAPIC-style chip with 24 IRQ lines (standard PC).
    """

    def __init__(self, name: str = "ioapic", n_irqs: int = 24) -> None:
        self.name = name
        self.n_irqs = n_irqs
        self._enabled: set[int] = set()
        self._masked: set[int] = set()
        self._redirection: Dict[int, Dict[str, Any]] = {}

        def _ioapic_enable(irq: int) -> None:
            self._enabled.add(irq)
            self._masked.discard(irq)

        def _ioapic_disable(irq: int) -> None:
            self._enabled.discard(irq)

        def _ioapic_ack(irq: int) -> None:
            pass  # EOI via APIC

        def _ioapic_mask(irq: int) -> None:
            self._masked.add(irq)
            self._enabled.discard(irq)

        def _ioapic_unmask(irq: int) -> None:
            self._masked.discard(irq)
            self._enabled.add(irq)

        def _ioapic_mask_ack(irq: int) -> None:
            self._masked.add(irq)
            self._enabled.discard(irq)

        def _ioapic_eoi(irq: int) -> None:
            pass

        def _ioapic_set_type(irq: int, t: int) -> int:
            if irq not in self._redirection:
                self._redirection[irq] = {}
            self._redirection[irq]["trigger"] = t
            return 0

        def _ioapic_set_affinity(irq: int, mask: int) -> int:
            if irq not in self._redirection:
                self._redirection[irq] = {}
            self._redirection[irq]["dest"] = mask
            return 0

        chip = IrqChip(
            name=name,
            irq_enable=_ioapic_enable,
            irq_disable=_ioapic_disable,
            irq_ack=_ioapic_ack,
            irq_mask=_ioapic_mask,
            irq_unmask=_ioapic_unmask,
            irq_mask_ack=_ioapic_mask_ack,
            irq_eoi=_ioapic_eoi,
            irq_set_type=_ioapic_set_type,
            irq_set_affinity=_ioapic_set_affinity,
            irq_chip_flags=0,
        )

        _irq_chips[name] = chip

        for i in range(n_irqs):
            desc = _get_or_create_desc(i, f"{name}-{i}")
            desc.chip = chip

        logging.info(
            "IoapicController(%r): created with %d IRQs", name, n_irqs,
        )

    def get_chip(self) -> IrqChip:
        return _irq_chips[self.name]

    def get_redirection(self, irq: int) -> Optional[Dict[str, Any]]:
        return self._redirection.get(irq)

    def __str__(self) -> str:
        return (
            f"IoapicController(name={self.name!r}, n_irqs={self.n_irqs}, "
            f"enabled={len(self._enabled)}, masked={len(self._masked)})")


class CascadeController:
    """
    Chained cascade controller.

    Models the classic x86 cascade where IRQ0 (timer) and IRQ8 (RTC)
    are cascaded through the PIC.  IRQ2 is typically the cascade line.
    """

    def __init__(self, name: str = "cascade") -> None:
        self.name = name
        self._cascaded_irqs: List[int] = [2]  # IRQ2 is the cascade line
        self._slave_irqs: List[int] = list(range(8, 16))  # IRQ8-15

        def _cascade_enable(irq: int) -> None:
            logging.debug("Cascade %s: enable IRQ %d", name, irq)

        def _cascade_disable(irq: int) -> None:
            logging.debug("Cascade %s: disable IRQ %d", name, irq)

        def _cascade_ack(irq: int) -> None:
            logging.debug("Cascade %s: ack IRQ %d", name, irq)

        def _cascade_mask(irq: int) -> None:
            logging.debug("Cascade %s: mask IRQ %d", name, irq)

        def _cascade_unmask(irq: int) -> None:
            logging.debug("Cascade %s: unmask IRQ %d", name, irq)

        chip = IrqChip(
            name=name,
            irq_enable=_cascade_enable,
            irq_disable=_cascade_disable,
            irq_ack=_cascade_ack,
            irq_mask=_cascade_mask,
            irq_unmask=_cascade_unmask,
            irq_chip_flags=0,
        )

        _irq_chips[name] = chip

        # Set IRQ2 as cascaded
        desc2 = _get_or_create_desc(2, f"{name}-2")
        desc2.chip = chip
        desc2.is_chained = True

        logging.info(
            "CascadeController(%r): created, cascade IRQ=%d, "
            "slave IRQs=%s",
            name, 2, self._slave_irqs,
        )

    def get_chip(self) -> IrqChip:
        return _irq_chips[self.name]

    def is_slave_irq(self, irq: int) -> bool:
        return irq in self._slave_irqs

    def __str__(self) -> str:
        return (
            f"CascadeController(name={self.name!r}, "
            f"cascade_irq=2, slaves={self._slave_irqs})")


# ═════════════════════════════════════════════════════════════
# Convenience utilities
# ═════════════════════════════════════════════════════════════

def irq_summary() -> str:
    """Return a human-readable summary of all IRQ state."""
    lines: List[str] = []
    lines.append("=" * 64)
    lines.append("  UmerOS IRQ Subsystem Summary")
    lines.append("=" * 64)

    # Chips
    lines.append(f"\n  Registered IRQ Chips ({len(_irq_chips)}):")
    for name, chip in _irq_chips.items():
        lines.append(f"    {chip}")

    # Domains
    lines.append(f"\n  Registered IRQ Domains ({len(_irq_domains)}):")
    for name, domain in _irq_domains.items():
        lines.append(f"    {domain}")

    # Descriptors
    descs = irq_list_all()
    lines.append(f"\n  IRQ Descriptors ({len(descs)}):")
    for desc in descs:
        depth_str = f"depth={desc.depth}" if desc.depth else "enabled"
        actions = desc.all_actions()
        action_names = [a.name for a in actions]
        lines.append(
            f"    IRQ {desc.irq:>4d}: {desc.name:<20s} "
            f"[{depth_str}] "
            f"status=[{desc.status_str()}] "
            f"count={desc.irq_count} "
            f"actions={action_names}"
        )

    lines.append("\n" + "=" * 64)
    return "\n".join(lines)


def irq_reset() -> None:
    """Reset all IRQ subsystem state (for testing)."""
    with _irq_lock:
        _irq_descs.clear()
        _irq_chips.clear()
        _irq_domains.clear()
        _irq_common.clear()
        _percpu_irq_counts.clear()
        logging.info("irq_reset: all state cleared")


# ═════════════════════════════════════════════════════════════
# Demo / self-test
# ═════════════════════════════════════════════════════════════

def _demo() -> None:
    """Demonstrate the IRQ/Interrupt handling framework."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-8s %(message)s",
    )
    log = logging.getLogger("irq_demo")

    print("=" * 70)
    print("  UmerOS IRQ/Interrupt Handling Framework – Demo")
    print("=" * 70)

    # ── 1. Create interrupt controllers ──────────────────────
    print("\n[1] Creating interrupt controllers...\n")

    gic = GicController("gic", n_irqs=32)
    print(f"  {gic}")

    ioapic = IoapicController("ioapic", n_irqs=24)
    print(f"  {ioapic}")

    cascade = CascadeController("cascade")
    print(f"  {cascade}")

    print(f"\n  Registered chips:")
    for name, chip in _irq_chips.items():
        print(f"    {chip}")

    # ── 2. Request shared IRQs ───────────────────────────────
    print("\n[2] Requesting shared IRQs...\n")

    def timer_handler(irq: int, dev_id: object) -> int:
        print(f"    -> Timer handler fired (IRQ {irq})")
        return 1

    def keyboard_handler(irq: int, dev_id: object) -> int:
        print(f"    -> Keyboard handler fired (IRQ {irq}, dev={dev_id})")
        return 1

    def mouse_handler(irq: int, dev_id: object) -> int:
        print(f"    -> Mouse handler fired (IRQ {irq})")
        return 1

    def serial_handler(irq: int, dev_id: object) -> int:
        print(f"    -> Serial handler fired (IRQ {irq})")
        return 1

    # Timer on IRQ0 (GIC)
    ret = request_irq(0, timer_handler, IRQF_SHARED, "timer", "8254_timer")
    print(f"  request_irq(0, 'timer'):       ret={ret}")

    # Keyboard on IRQ1 (IOAPIC)
    ret = request_irq(1, keyboard_handler, IRQF_SHARED, "keyboard", "i8042_kbd")
    print(f"  request_irq(1, 'keyboard'):    ret={ret}")

    # Mouse on IRQ12 (shared with IOAPIC)
    ret = request_irq(12, mouse_handler, IRQF_SHARED, "mouse", "i8042_mouse")
    print(f"  request_irq(12, 'mouse'):      ret={ret}")

    # Serial on IRQ4
    ret = request_irq(4, serial_handler, IRQF_SHARED, "serial", "serial0")
    print(f"  request_irq(4, 'serial'):      ret={ret}")

    # ── 3. Request threaded IRQs ─────────────────────────────
    print("\n[3] Requesting threaded IRQs...\n")

    def nvme_handler(irq: int, dev_id: object) -> int:
        print(f"    -> NVMe hard IRQ (IRQ {irq})")
        return 0  # will be handled in thread

    def nvme_thread_fn(irq: int, dev_id: object) -> int:
        print(f"    -> NVMe threaded handler (IRQ {irq})")
        return 0

    def net_handler(irq: int, dev_id: object) -> int:
        print(f"    -> Network hard IRQ (IRQ {irq})")
        return 0

    def net_thread_fn(irq: int, dev_id: object) -> int:
        print(f"    -> Network threaded handler (IRQ {irq})")
        return 0

    ret = request_threaded_irq(
        32, nvme_handler, nvme_thread_fn,
        IRQF_SHARED, "nvme", "nvme0",
    )
    print(f"  request_threaded_irq(32, 'nvme'):      ret={ret}")

    ret = request_threaded_irq(
        33, net_handler, net_thread_fn,
        IRQF_SHARED | IRQF_NO_THREAD, "eth0", "netdev0",
    )
    print(f"  request_threaded_irq(33, 'eth0'):      ret={ret}")

    # ── 4. Enable / Disable IRQs ─────────────────────────────
    print("\n[4] Enable / Disable operations...\n")

    disable_irq(0)
    print(f"  disable_irq(0):   depth={_irq_descs[0].depth}")

    disable_irq(0)
    print(f"  disable_irq(0):   depth={_irq_descs[0].depth}")

    enable_irq(0)
    print(f"  enable_irq(0):    depth={_irq_descs[0].depth}")

    enable_irq(0)
    print(f"  enable_irq(0):    depth={_irq_descs[0].depth}")

    disable_irq_nosync(12)
    print(f"  disable_irq_nosync(12): depth={_irq_descs[12].depth}")

    irq_set_enabled(12)
    print(f"  irq_set_enabled(12):    depth={_irq_descs[12].depth}")

    # ── 5. Mask / Unmask operations ──────────────────────────
    print("\n[5] Mask / Unmask operations...\n")

    irq_mask(4)
    print(f"  irq_mask(4):    ioapic masked={ioapic._masked}")

    irq_unmask(4)
    print(f"  irq_unmask(4):  ioapic masked={ioapic._masked}")

    irq_mask_ack(4)
    print(f"  irq_mask_ack(4): ioapic masked={ioapic._masked}")

    # ── 6. Affinity setting ──────────────────────────────────
    print("\n[6] Setting IRQ affinity...\n")

    irq_set_affinity_hint(0, 0x01)  # CPU 0
    print(f"  irq_set_affinity_hint(0, cpu0):  affinity=0x{_irq_descs[0].affinity:08x}")

    irq_set_affinity(0, 2)  # CPU 2
    print(f"  irq_set_affinity(0, cpu2):       affinity=0x{_irq_descs[0].affinity:08x}")

    irq_set_affinity_hint(32, 0x0F)  # All CPUs
    print(f"  irq_set_affinity_hint(32, all):  affinity=0x{_irq_descs[32].affinity:08x}")

    # ── 7. Trigger type configuration ────────────────────────
    print("\n[7] Configuring trigger types...\n")

    irq_set_irq_type(1, IRQF_TRIGGER_FALLING)
    print(f"  irq_set_irq_type(1, FALLING):   OK")

    irq_set_irq_type(12, IRQF_TRIGGER_LEVEL | IRQF_TRIGGER_LOW)
    print(f"  irq_set_irq_type(12, LOW):      OK")

    irq_set_irq_type(4, IRQF_TRIGGER_RISING)
    print(f"  irq_set_irq_type(4, RISING):    OK")

    ioapic_r = ioapic.get_redirection(1)
    if ioapic_r:
        print(f"  IOAPIC redir[1]: trigger=0x{ioapic_r.get('trigger', 0):x}")

    # ── 8. IRQ domain mapping ────────────────────────────────
    print("\n[8] IRQ domain mapping...\n")

    domain = irq_domain_register("gic", hwirq_base=32, size=96)
    print(f"  Registered domain: {domain}")

    irq_domain_associate("gic", 32, 32)
    irq_domain_associate("gic", 33, 33)
    irq_domain_associate("gic", 34, 34)
    print(f"  Associated hwirq 32 -> virq 32")
    print(f"  Associated hwirq 33 -> virq 33")
    print(f"  Associated hwirq 34 -> virq 34")

    mapped = irq_domain_mapping("gic", 32)
    print(f"  irq_domain_mapping(gic, hwirq=32) -> virq={mapped}")

    revmapped = domain.revmap(33)
    print(f"  domain.revmap(virq=33) -> hwirq={revmapped}")

    print(f"  Updated domain: {domain}")

    # ── 9. Dispatch simulation ───────────────────────────────
    print("\n[9] Dispatching IRQs...\n")

    print("  Dispatching IRQ 0 (timer):")
    irq_dispatch(0)

    print("\n  Dispatching IRQ 1 (keyboard):")
    irq_dispatch(1)

    print("\n  Dispatching IRQ 4 (serial):")
    irq_dispatch(4)

    print("\n  Dispatching IRQ 12 (mouse):")
    irq_dispatch(12)

    print("\n  Running threaded handler for IRQ 32 (NVMe):")
    irq_thread_fn(32)

    # ── 10. IRQ statistics ───────────────────────────────────
    print("\n[10] IRQ statistics...\n")

    for irq_num in [0, 1, 4, 12, 32, 33]:
        stats = irq_get_stats(irq_num)
        if stats:
            print(f"  IRQ {irq_num}: {stats['name']}")
            print(f"    depth={stats['depth']}, "
                  f"count={stats['irq_count']}, "
                  f"spurious={stats['spurious_count']}")
            print(f"    chip={stats['chip']}, "
                  f"domain={stats['domain']}")
            if stats['actions']:
                for a in stats['actions']:
                    print(f"    action: {a['name']}, "
                          f"irq_count={a['irq_count']}, "
                          f"shared={a['shared']}, "
                          f"threaded={a['threaded']}")
            print()

    # ── 11. Action listing ───────────────────────────────────
    print("[11] Listing actions for IRQ 0...\n")

    actions = irq_list_actions(0)
    for action in actions:
        print(f"  {action}")

    print(f"\n  IRQ 1 actions:")
    for action in irq_list_actions(1):
        print(f"    {action}")

    # ── 12. Spurious IRQ detection ───────────────────────────
    print("\n[12] Spurious IRQ detection...\n")

    desc_unreg = _get_or_create_desc(99, "unregistered-irq")
    print(f"  Created unregistered IRQ 99: {desc_unreg}")
    # No actions registered – should be detected as spurious

    # Simulate a few dispatches on an unregistered-action IRQ
    for i in range(5):
        irq_dispatch(99)
    print(f"  After 5 dispatches: spurious_count={_irq_descs[99].spurious_count}")

    # ── 13. Cascade interrupt handling ────────────────────────
    print("\n[13] Cascade interrupt handling...\n")

    def cascade_slave_handler(irq: int, dev_id: object) -> int:
        print(f"    -> Cascade slave handler (IRQ {irq})")
        return 1

    ret = request_irq(
        8, cascade_slave_handler, IRQF_SHARED, "cascade-rtc", "rtc",
    )
    print(f"  request_irq(8, 'cascade-rtc'):  ret={ret}")
    print(f"  IRQ 8 is_slave: {cascade.is_slave_irq(8)}")
    print(f"  IRQ 9 is_slave: {cascade.is_slave_irq(9)}")

    print("  Dispatching cascade IRQ 8:")
    irq_dispatch(8)

    # ── 14. Free IRQs ────────────────────────────────────────
    print("\n[14] Freeing IRQs...\n")

    freed = free_irq(12, "i8042_mouse")
    print(f"  free_irq(12, 'i8042_mouse'): freed={freed}")
    print(f"  IRQ 12 actions: {irq_list_actions(12)}")

    freed = free_irq(8, "rtc")
    print(f"  free_irq(8, 'rtc'): freed={freed}")

    # ── 15. Probe control ────────────────────────────────────
    print("\n[15] Probe control...\n")

    irq_set_noprobe(4)
    print(f"  irq_set_noprobe(4): status has NOREQUEST = "
          f"{bool(_irq_descs[4].status & IRQS_NOREQUEST)}")

    irq_set_probe(4)
    print(f"  irq_set_probe(4):   status has NOREQUEST = "
          f"{bool(_irq_descs[4].status & IRQS_NOREQUEST)}")

    # ── 16. Full subsystem summary ───────────────────────────
    print("\n[16] Full IRQ subsystem summary...\n")
    print(irq_summary())

    # ── 17. All descriptors ──────────────────────────────────
    print("\n[17] All registered IRQ descriptors:\n")
    for desc in irq_list_all():
        print(f"  {desc}")

    # ── 18. Cleanup ──────────────────────────────────────────
    print("\n[18] Cleaning up...\n")
    irq_reset()
    print("  All IRQ state reset.")
    print(f"  Chips remaining: {len(_irq_chips)}")
    print(f"  Descriptors remaining: {len(_irq_descs)}")

    print("\n" + "=" * 70)
    print("  Demo complete.")
    print("=" * 70)


if __name__ == "__main__":
    _demo()
