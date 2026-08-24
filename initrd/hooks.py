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
Umer OS Initrd Hooks
====================
A small, dependency-free hook system that mirrors the "hooks" pattern
of ``initramfs-tools`` (Debian/Ubuntu) and ``dracut`` (Fedora/RHEL).

Two flavours of hook are supported:

* **Sync hooks** - plain callables run inline.  They are used for
  trivial tasks like "create ``/dev/null``" or "echo progress".

* **Async hooks** - ``async def`` coroutines run inside the initrd's
  asyncio loop.  They are used for tasks that need to await I/O, e.g.
  waiting for a block device to appear or polling the AI module
  predictor.

Hooks are registered against a *hook point* (a named moment during
the boot process).  Built-in hook points match the phases::

    PRE_LOAD            -> before the cpio archive is loaded
    POST_LOAD           -> after the archive is in memory
    PRE_EXTRACT         -> before unpacking
    POST_EXTRACT        -> after the working FS is populated
    PRE_MODULE_PROBE    -> before /linuxrc asks for kernel modules
    POST_MODULE_PROBE   -> after the module list is resolved
    PRE_MOUNT_REAL_ROOT -> before mounting the real root FS
    POST_MOUNT_REAL_ROOT-> after the real root FS is mounted
    PRE_PIVOT_ROOT      -> before pivot_root
    POST_PIVOT_ROOT     -> after pivot_root
    PRE_INIT            -> before exec(/sbin/init)
    CLEANUP             -> at teardown

Custom hook points can be registered at runtime via
:meth:`HookManager.define`.  Hooks may be tagged (e.g. ``"lvm"``,
``"crypto"``) so a scenario can install only the hooks it needs.

The order in which hooks run inside a single hook point is:

1.  Tag-matched hooks, in registration order.
2.  Untagged hooks, in registration order.

If a hook raises, the manager logs the failure and continues with
the next hook.  A hook that must stop the boot should call
:meth:`HookManager.abort` which raises :class:`HookAbort`.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

log = logging.getLogger("UmerOS.Initrd.Hooks")


# ---------------------------------------------------------------------------
# Hook points
# ---------------------------------------------------------------------------

class HookPoint(str, Enum):
    """Built-in hook points.  Values are the canonical string form."""

    PRE_LOAD             = "pre_load"
    POST_LOAD            = "post_load"
    PRE_EXTRACT          = "pre_extract"
    POST_EXTRACT         = "post_extract"
    PRE_MODULE_PROBE     = "pre_module_probe"
    POST_MODULE_PROBE    = "post_module_probe"
    PRE_MOUNT_REAL_ROOT  = "pre_mount_real_root"
    POST_MOUNT_REAL_ROOT = "post_mount_real_root"
    PRE_PIVOT_ROOT       = "pre_pivot_root"
    POST_PIVOT_ROOT      = "post_pivot_root"
    PRE_INIT             = "pre_init"
    CLEANUP              = "cleanup"


# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------

class HookAbort(RuntimeError):
    """Raised by :meth:`HookManager.abort` to stop the boot."""


# ---------------------------------------------------------------------------
# Hook record
# ---------------------------------------------------------------------------

HookFn = Union[Callable[[Dict[str, Any]], Any],
               Callable[[Dict[str, Any]], Awaitable[None]]]


@dataclass
class _Hook:
    name: str
    point: str
    fn: HookFn
    tag: Optional[str] = None
    priority: int = 0
    registered_at: float = field(default_factory=time.time)
    invocations: int = 0
    failures: int = 0


# ---------------------------------------------------------------------------
# Hook manager
# ---------------------------------------------------------------------------

class HookManager:
    """Registry + runner for the initrd hook system."""

    def __init__(self) -> None:
        self._hooks: List[_Hook] = []
        self._points: Dict[str, int] = {p.value: 0 for p in HookPoint}
        self._custom_points: Dict[str, int] = {}
        self._aborted: bool = False
        self._last_context: Dict[str, Any] = {}

    # -- registration -----------------------------------------------------

    def define(self, name: str) -> str:
        """Register a custom hook point and return its canonical name."""
        if name in self._points or name in self._custom_points:
            return name
        self._custom_points[name] = 0
        log.debug("hook point defined: %s", name)
        return name

    def add(
        self,
        point: Union[str, HookPoint],
        fn: HookFn,
        *,
        name: Optional[str] = None,
        tag: Optional[str] = None,
        priority: int = 0,
    ) -> str:
        """Register a hook.  Returns the assigned hook name."""
        point_name = point.value if isinstance(point, HookPoint) else str(point)
        if point_name not in self._points and point_name not in self._custom_points:
            self.define(point_name)
        hook_name = name or fn.__name__ or f"hook_{len(self._hooks)}"
        self._hooks.append(
            _Hook(name=hook_name, point=point_name, fn=fn, tag=tag, priority=priority)
        )
        self._bump_count(point_name)
        log.debug("hook added: %s -> %s (tag=%s)", hook_name, point_name, tag)
        return hook_name

    def remove(self, hook_name: str) -> bool:
        """Remove a previously registered hook by name."""
        before = len(self._hooks)
        self._hooks = [h for h in self._hooks if h.name != hook_name]
        return len(self._hooks) < before

    # -- introspection ----------------------------------------------------

    def list(self, point: Optional[Union[str, HookPoint]] = None,
             tag: Optional[str] = None) -> List[str]:
        """List registered hook names, optionally filtered by point/tag."""
        out: List[str] = []
        for h in self._hooks:
            if point is not None:
                pn = point.value if isinstance(point, HookPoint) else str(point)
                if h.point != pn:
                    continue
            if tag is not None and h.tag != tag:
                continue
            out.append(h.name)
        return out

    def point_stats(self) -> Dict[str, int]:
        """Return a snapshot of how many hooks exist per point."""
        out: Dict[str, int] = {}
        for h in self._hooks:
            out[h.point] = out.get(h.point, 0) + 1
        return out

    # -- execution --------------------------------------------------------

    def run(self, point: Union[str, HookPoint], context: Optional[Dict[str, Any]] = None) -> int:
        """Run every hook attached to ``point`` synchronously.

        Async hooks are driven via :func:`asyncio.run` if there is no
        running loop; otherwise :meth:`run_async` should be used.

        Returns the number of hooks that were invoked.
        """
        point_name = point.value if isinstance(point, HookPoint) else str(point)
        ctx = dict(self._last_context)
        if context:
            ctx.update(context)
        self._last_context = ctx
        try:
            asyncio.get_running_loop()
            # We're in an async context - the caller should use run_async.
            raise RuntimeError(
                "HookManager.run called from async context; use run_async"
            )
        except RuntimeError as exc:
            if "no running event loop" not in str(exc) and "use run_async" not in str(exc):
                raise
        return self._execute(point_name, ctx)

    async def run_async(self, point: Union[str, HookPoint],
                        context: Optional[Dict[str, Any]] = None) -> int:
        """Run every hook attached to ``point``, awaiting async ones."""
        point_name = point.value if isinstance(point, HookPoint) else str(point)
        ctx = dict(self._last_context)
        if context:
            ctx.update(context)
        self._last_context = ctx
        return await self._execute_async(point_name, ctx)

    def abort(self, message: str) -> None:
        """Stop hook execution with a clear error message."""
        self._aborted = True
        raise HookAbort(message)

    # -- internals --------------------------------------------------------

    def _bump_count(self, point_name: str) -> None:
        if point_name in self._points:
            self._points[point_name] += 1
        else:
            self._custom_points[point_name] = self._custom_points.get(point_name, 0) + 1

    def _execute(self, point_name: str, context: Dict[str, Any]) -> int:
        if self._aborted:
            raise HookAbort("hook manager already aborted")
        candidates = [h for h in self._hooks if h.point == point_name]
        # Tag-specific hooks first, then untagged, both groups in priority order.
        candidates.sort(key=lambda h: (0 if h.tag else 1, h.priority, h.registered_at))
        invoked = 0
        # Detect whether we are already inside a running event loop so
        # async hooks can be awaited instead of forcing asyncio.run.
        in_loop = False
        try:
            asyncio.get_running_loop()
            in_loop = True
        except RuntimeError:
            in_loop = False
        for hook in candidates:
            try:
                if inspect.iscoroutinefunction(hook.fn):
                    coro = hook.fn(context)
                    if in_loop:
                        # ``run_async`` schedules the work on the
                        # currently-running loop, so we cannot block
                        # here - the caller is expected to await us.
                        raise RuntimeError(
                            "HookManager: async hook scheduled from sync run(); "
                            "use run_async instead"
                        )
                    asyncio.run(coro)
                else:
                    result = hook.fn(context)
                    if inspect.isawaitable(result):
                        if in_loop:
                            raise RuntimeError(
                                "HookManager: awaitable hook scheduled from sync run(); "
                                "use run_async instead"
                            )
                        asyncio.run(result)
                hook.invocations += 1
                invoked += 1
            except HookAbort:
                raise
            except Exception as exc:  # noqa: BLE001
                hook.failures += 1
                log.error("hook %s failed at %s: %s", hook.name, point_name, exc)
        return invoked

    async def _execute_async(self, point_name: str, context: Dict[str, Any]) -> int:
        """Async variant of :meth:`_execute` that awaits coroutine hooks."""
        if self._aborted:
            raise HookAbort("hook manager already aborted")
        candidates = [h for h in self._hooks if h.point == point_name]
        candidates.sort(key=lambda h: (0 if h.tag else 1, h.priority, h.registered_at))
        invoked = 0
        for hook in candidates:
            try:
                if inspect.iscoroutinefunction(hook.fn):
                    await hook.fn(context)
                else:
                    result = hook.fn(context)
                    if inspect.isawaitable(result):
                        await result
                hook.invocations += 1
                invoked += 1
            except HookAbort:
                raise
            except Exception as exc:  # noqa: BLE001
                hook.failures += 1
                log.error("hook %s failed at %s: %s", hook.name, point_name, exc)
        return invoked


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    mgr = HookManager()
    events: List[str] = []

    def h1(ctx):
        events.append("h1")

    def h2(ctx):
        events.append("h2")

    async def h3(ctx):
        events.append("h3")

    mgr.add(HookPoint.PRE_LOAD, h1, name="first", tag="io")
    mgr.add(HookPoint.PRE_LOAD, h2, name="second")
    mgr.add(HookPoint.PRE_LOAD, h3, name="third")
    mgr.add(HookPoint.POST_LOAD, h1, name="post1")

    mgr.run(HookPoint.PRE_LOAD, {"phase": "pre"})
    mgr.run(HookPoint.POST_LOAD, {"phase": "post"})
    # Expected order: tagged h1 first, then untagged h2 then h3 (FIFO),
    # then post-load h1.
    return events == ["h1", "h2", "h3", "h1"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("hooks selftest:", "OK" if _selftest() else "FAIL")
