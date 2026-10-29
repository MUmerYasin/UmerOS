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
UmerOS 32-Bit Event Groups (los_event.c).

Provides bitmask-based task synchronization with support for:
- WAIT_ALL: Wait until all requested bits in the mask are set.
- WAIT_ANY: Wait until at least one requested bit in the mask is set.
- Automatic or manual clearing of flags.
"""

from __future__ import annotations

import asyncio
from typing import Dict, Tuple


class EventGroup:
    """32-bit bitmask event group for multi-condition task synchronization."""

    WAIT_ALL = "WAIT_ALL"
    WAIT_ANY = "WAIT_ANY"

    def __init__(self, initial_flags: int = 0) -> None:
        self._flags: int = initial_flags & 0xFFFFFFFF
        # Map: asyncio.Event -> (required_mask, wait_mode, auto_clear)
        self._waiters: Dict[asyncio.Event, Tuple[int, str, bool]] = {}
        self._lock = asyncio.Lock()

    @property
    def flags(self) -> int:
        """Return the current 32-bit event mask."""
        return self._flags

    async def set_flags(self, mask: int) -> int:
        """Set bits in the event mask and wake any satisfying waiters.

        Args:
            mask: 32-bit integer mask of bits to set.

        Returns:
            The new 32-bit event flag value.
        """
        async with self._lock:
            self._flags |= (mask & 0xFFFFFFFF)
            for event, (req_mask, mode, auto_clear) in list(self._waiters.items()):
                satisfied = False
                if mode == self.WAIT_ANY and (self._flags & req_mask) != 0:
                    satisfied = True
                elif mode == self.WAIT_ALL and (self._flags & req_mask) == req_mask:
                    satisfied = True

                if satisfied:
                    if auto_clear:
                        self._flags &= ~req_mask
                    event.set()
            return self._flags

    async def clear_flags(self, mask: int) -> int:
        """Clear specific bits from the event mask.

        Args:
            mask: 32-bit integer mask of bits to clear.

        Returns:
            The new 32-bit event flag value.
        """
        async with self._lock:
            self._flags &= ~(mask & 0xFFFFFFFF)
            return self._flags

    async def wait(
        self,
        mask: int,
        mode: str = WAIT_ALL,
        auto_clear: bool = False,
        timeout: float | None = None,
    ) -> bool:
        """Wait for flags matching the mask according to mode.

        Args:
            mask: 32-bit integer mask to watch.
            mode: WAIT_ALL (default) or WAIT_ANY.
            auto_clear: If True, automatically clears the matching bits upon waking.
            timeout: Optional timeout in seconds.

        Returns:
            True if flags matched, False if timed out.
        """
        mask &= 0xFFFFFFFF
        async with self._lock:
            # Check immediate satisfaction
            if mode == self.WAIT_ANY and (self._flags & mask) != 0:
                if auto_clear:
                    self._flags &= ~mask
                return True
            if mode == self.WAIT_ALL and (self._flags & mask) == mask:
                if auto_clear:
                    self._flags &= ~mask
                return True

            event = asyncio.Event()
            self._waiters[event] = (mask, mode, auto_clear)

        try:
            if timeout is not None:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            else:
                await event.wait()
            return True
        except asyncio.TimeoutError:
            return False
        finally:
            async with self._lock:
                self._waiters.pop(event, None)
