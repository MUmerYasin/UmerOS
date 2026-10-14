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
UmerOS /kernel — cpuidle stub  [TODAY]
======================================
Minimal CPU-idle entry point used by ``kernel.power_manager``.

A real implementation would talk to ACPI C-states or platform firmware; this
stub always returns a simulated idle-state name (never ``None``).  The richer,
kernel-like implementation lives in ``drivers/cpuidle.py``.
"""

from __future__ import annotations

import logging
import random

log = logging.getLogger("UmerOS.Kernel.Cpuidle")

_IDLE_STATES = ("C1", "C2", "C3")


def cpuidle_enter():
    """Enter a simulated CPU idle state.  Returns the state name or None."""
    return random.choice(_IDLE_STATES)
