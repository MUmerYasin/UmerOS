"""
Umer OS Reboot / Power-Off Subsystem
=====================================
``kernel/reboot.c`` (Linus Torvalds, 2013).

Models system shutdown as an ordered sequence of notifier chains
and ``system_state`` transitions:

    enum system_state {
        SYSTEM_BOOTING, SYSTEM_SCHEDULING, SYSTEM_RUNNING,
        SYSTEM_HALT, SYSTEM_POWER_OFF, SYSTEM_RESTART,
        SYSTEM_SUSPEND,
    };

    reboot_notifier_list      – called first (SYS_HALT/POWER_OFF/RESTART)
    restart_handler_list      – priority-ordered; 0=last-resort, 255=best
    sys_off_handler / pm_power_off – final machine power cut

This module reproduces that structure in Python so the kernel can run
ordered shutdown sequences and so drivers/services can register
callbacks for each phase.

Semantics preserved:
  * ``register_reboot_notifier()`` / ``unregister_reboot_notifier()``.
  * ``register_restart_handler()`` with priority ordering.
  * ``kernel_restart()``  – prepare → notify RESTART → restart handlers.
  * ``kernel_halt()``     – prepare → notify HALT.
  * ``kernel_power_off()``– prepare → notify POWER_OFF → power handlers.
  * ``orderly_poweroff()`` / ``orderly_reboot()`` – userspace-style.
  * Ctrl-Alt-Del (cad_pid) – deliver SIGINT to a chosen task.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Awaitable, Callable, List, Optional

log = logging.getLogger("UmerOS.Reboot")


class SystemState(IntEnum):
    """``enum system_state``."""
    BOOTING = 0
    SCHEDULING = 1
    RUNNING = 2
    HALT = 3
    POWER_OFF = 4
    RESTART = 5
    SUSPEND = 6


class RebootAction(IntEnum):
    """Values passed to notifier callbacks (mirrors ``SYS_*``)."""
    RESTART = 0x0001
    HALT = 0x0002
    POWER_OFF = 0x0003
    SUSPEND = 0x0004


# Notify return codes (notifier.h).
NOTIFY_DONE = 0x0000      # nothing for me; keep going
NOTIFY_OK = 0x0001        # ok; keep going
NOTIFY_STOP_MASK = 0x8000
NOTIFY_STOP = NOTIFY_STOP_MASK | 0x4000  # stop the chain
NOTIFY_BAD = NOTIFY_STOP_MASK | 0x8002   # error; stop & roll back


# A notifier callback: async, takes (action, data) -> int.
NotifierFn = Callable[[RebootAction, Any], Awaitable[int]]


@dataclass
class NotifierBlock:
    """Mirrors ``struct notifier_block``.

    Attributes:
        fn:       The async callback.
        priority: Higher = called first.  255 = highest, 0 = last resort.
        name:     Human label for debugging.
        data:     Opaque data passed back to the callback.
    """
    fn: NotifierFn
    priority: int = 0
    name: str = ""
    data: Any = None


class NotifierChain:
    """Priority-ordered, dedup async notifier chain.

    Registration inserts in priority order (descending).  Duplicate
    (same object / same fn) registrations are rejected with a warning,
    ``notifier_chain_register()`` which WARN()s on
    duplicates.
    """

    def __init__(self, label: str) -> None:
        self._blocks: List[NotifierBlock] = []
        self._label = label

    def register(self, block: NotifierBlock) -> bool:
        """Insert ``block`` keeping descending-priority order.

        Returns False (and warns) if the callback is already registered.
        """
        for existing in self._blocks:
            if existing.fn is block.fn:
                log.warning("[%s] notifier %r already registered",
                            self._label, block.name)
                return False
        # Insert before the first block with strictly lower priority.
        idx = len(self._blocks)
        for i, existing in enumerate(self._blocks):
            if block.priority > existing.priority:
                idx = i
                break
        self._blocks.insert(idx, block)
        log.debug("[%s] registered %r at priority %d",
                  self._label, block.name, block.priority)
        return True

    def unregister(self, block: NotifierBlock) -> bool:
        for i, existing in enumerate(self._blocks):
            if existing is block or existing.fn is block.fn:
                self._blocks.pop(i)
                log.debug("[%s] unregistered %r", self._label, block.name)
                return True
        return False

    async def call(self, action: RebootAction, data: Any = None) -> int:
        """Fire the chain.  Stops on ``NOTIFY_STOP_MASK``.

        Returns the last callback's return value.
        """
        ret = NOTIFY_DONE
        for block in list(self._blocks):
            try:
                ret = await block.fn(action, data if data is not None else block.data)
            except Exception as exc:  # noqa: BLE001
                log.exception("[%s] notifier %r raised: %s",
                              self._label, block.name, exc)
                ret = NOTIFY_BAD
            if ret & NOTIFY_STOP_MASK:
                log.debug("[%s] chain stopped by %r (ret=0x%x)",
                          self._label, block.name, ret)
                break
        return ret

    def __len__(self) -> int:
        return len(self._blocks)


class RebootManager:
    """Ordered system shutdown coordinator (mirrors ``kernel/reboot.c``).

    Owns three notifier chains:
      * ``reboot_notifiers``  – called first, broadly, before teardown.
      * ``restart_handlers``  – priority-ordered actual restart hooks.
      * ``power_off_handlers``– priority-ordered actual power-off hooks.

    And the global ``system_state`` that other subsystems can poll.
    """

    def __init__(self) -> None:
        self.system_state: SystemState = SystemState.BOOTING
        self.reboot_notifiers = NotifierChain("reboot")
        self.restart_handlers = NotifierChain("restart")
        self.power_off_handlers = NotifierChain("power_off")

        # Ctrl-Alt-Del target (mirrors cad_pid). 0 = kernel/init.
        self.cad_pid: int = 0
        # ``reboot_force`` flag set by forced reboot paths.
        self.forced: bool = False
        # Last reboot reason string (for diagnostics).
        self.reason: str = ""

    # ── State ────────────────────────────────────────────────────────────

    def mark_running(self) -> None:
        """Transition BOOTING → SCHEDULING → RUNNING."""
        if self.system_state == SystemState.BOOTING:
            self.system_state = SystemState.SCHEDULING
        self.system_state = SystemState.RUNNING

    def is_running(self) -> bool:
        return self.system_state == SystemState.RUNNING

    # ── Public registration API ──────────────────────────────────────────

    def register_reboot_notifier(self, fn: NotifierFn, *,
                                 priority: int = 0,
                                 name: str = "",
                                 data: Any = None) -> NotifierBlock:
        """Register a broad reboot notifier (called for every action)."""
        block = NotifierBlock(fn=fn, priority=priority, name=name or fn.__name__, data=data)
        self.reboot_notifiers.register(block)
        return block

    def register_restart_handler(self, fn: NotifierFn, *,
                                 priority: int = 0,
                                 name: str = "",
                                 data: Any = None) -> NotifierBlock:
        """Register a restart handler.  Higher priority = called first.

        Convention (from docs):
          255 – best/only restart mechanism available.
          128 – default restart handler.
            0 – last resort.
        """
        block = NotifierBlock(fn=fn, priority=priority, name=name or fn.__name__, data=data)
        self.restart_handlers.register(block)
        return block

    def register_power_off_handler(self, fn: NotifierFn, *,
                                   priority: int = 0,
                                   name: str = "",
                                   data: Any = None) -> NotifierBlock:
        """Register a power-off handler (priority-ordered)."""
        block = NotifierBlock(fn=fn, priority=priority, name=name or fn.__name__, data=data)
        self.power_off_handlers.register(block)
        return block

    # ── Shutdown entry points ────────────────────────────────────────────

    async def _prepare(self, action: RebootAction, reason: str) -> None:
        """Common prepare step: notify broad reboot chain + set state."""
        self.reason = reason
        log.info("reboot prepare: action=%s reason=%r", action.name, reason)
        await self.reboot_notifiers.call(action, reason)

    async def kernel_restart(self, reason: str = "") -> None:
        """Orderly restart (mirrors ``kernel_restart``).

        Sequence: prepare → set RESTART → fire restart handlers.
        """
        if self.system_state in (SystemState.HALT, SystemState.POWER_OFF):
            log.warning("kernel_restart ignored — already in %s",
                        self.system_state.name)
            return
        await self._prepare(RebootAction.RESTART, reason or "restart")
        self.system_state = SystemState.RESTART
        ret = await self.restart_handlers.call(RebootAction.RESTART, reason)
        if ret == NOTIFY_BAD:
            log.error("restart handler failed (ret=0x%x) — falling back to halt", ret)
            await self.kernel_halt("restart-fallback")

    async def kernel_halt(self, reason: str = "") -> None:
        """Orderly halt (mirrors ``kernel_halt``)."""
        if self.system_state == SystemState.HALT:
            return
        await self._prepare(RebootAction.HALT, reason or "halt")
        self.system_state = SystemState.HALT
        log.warning("System halted.")

    async def kernel_power_off(self, reason: str = "") -> None:
        """Orderly power-off (mirrors ``kernel_power_off``).

        Sequence: prepare → set POWER_OFF → fire power-off handlers.
        """
        if self.system_state == SystemState.POWER_OFF:
            return
        await self._prepare(RebootAction.POWER_OFF, reason or "power-off")
        self.system_state = SystemState.POWER_OFF
        ret = await self.power_off_handlers.call(RebootAction.POWER_OFF, reason)
        if ret == NOTIFY_BAD:
            log.error("power-off handler failed — falling back to halt")
            self.poweroff_fallback_to_halt = True
            await self.kernel_halt("poweroff-fallback")

    # ── Userspace-style entry points ─────────────────────────────────────

    async def orderly_poweroff(self, force: bool = False) -> None:
        """Userspace-requested poweroff (mirrors ``orderly_poweroff``)."""
        self.forced = force
        await self.kernel_power_off("orderly-poweroff")

    async def orderly_reboot(self, force: bool = False) -> None:
        """Userspace-requested reboot (mirrors ``orderly_reboot``)."""
        self.forced = force
        await self.kernel_restart("orderly-reboot")

    async def emergency_restart(self) -> None:
        """Best-effort restart from a broken state (mirrors same name).

        Skips the broad reboot notifier chain and goes straight to
        restart handlers.
        """
        log.critical("EMERGENCY RESTART — %s", self.reason or "(no reason)")
        self.system_state = SystemState.RESTART
        await self.restart_handlers.call(RebootAction.RESTART, "emergency")

    # ── Ctrl-Alt-Del ─────────────────────────────────────────────────────

    def ctrl_alt_del(self, signal_fn: Optional[Callable[[int], None]] = None) -> None:
        """Deliver Ctrl-Alt-Del to ``cad_pid`` (mirrors ``ctrl_alt_del``).

        If ``signal_fn`` is provided it is called with ``cad_pid`` (so the
        caller can ``kill()`` the target task).  Otherwise just logs.
        """
        log.info("Ctrl-Alt-Del received — targeting PID %d", self.cad_pid)
        if signal_fn is not None:
            signal_fn(self.cad_pid)

    # ── Diagnostics ──────────────────────────────────────────────────────

    def status(self) -> dict:
        return {
            "system_state": self.system_state.name,
            "reason": self.reason,
            "forced": self.forced,
            "reboot_notifiers": len(self.reboot_notifiers),
            "restart_handlers": len(self.restart_handlers),
            "power_off_handlers": len(self.power_off_handlers),
        }


__all__ = [
    "SystemState",
    "RebootAction",
    "NotifierBlock",
    "NotifierChain",
    "RebootManager",
    "NOTIFY_DONE", "NOTIFY_OK", "NOTIFY_STOP", "NOTIFY_BAD", "NOTIFY_STOP_MASK",
]
