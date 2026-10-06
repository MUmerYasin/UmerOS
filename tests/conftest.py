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

"""Shared pytest configuration for the UmerOS test-suite.

Cross-test isolation for process-global state
---------------------------------------------
Some parts of UmerOS are deliberately process-global singletons, and tests
mutate them.  A test that changes one and does not put it back leaks into every
test that runs afterwards — a failure mode that is invisible when a module is
run on its own and only appears in a full-suite run.  Two real examples already
found in this tree:

* ``tests/test_kernel_security.py`` used to call
  ``logging.disable(logging.CRITICAL)`` at module scope.  pytest imports every
  test module during *collection*, so that disabled logging for the whole
  session and silently broke ``assertLogs`` in later modules.
* Booting a ``UmerKernel`` wires the capability gate to a real
  ``CapabilityManager`` (H113).  Any test that boots without shutting down would
  leave the entire process fail-closed against a kernel principal.

The fixture below snapshots and restores the two globals that carry this risk,
so a test can wire, pin, deny or otherwise reconfigure them freely without
affecting its neighbours.
"""

from __future__ import annotations

import pytest

from core.capability_gate import gate
from packages.trusted_keys import TRUSTED_PUBLIC_KEYS


@pytest.fixture(autouse=True)
def _isolate_process_globals():
    """Restore process-global capability/trust state after every test."""
    gate_posture = gate.snapshot()
    trusted_keys = dict(TRUSTED_PUBLIC_KEYS)
    try:
        yield
    finally:
        gate.restore(gate_posture)
        TRUSTED_PUBLIC_KEYS.clear()
        TRUSTED_PUBLIC_KEYS.update(trusted_keys)
