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

"""H113 — the kernel must actually wire the process-global capability gate.

Before this change ``core/capability_gate.py`` documented "the kernel calls
``gate.wire(cm)`` once" but no production code ever did: ``gate.wire`` appeared
only inside the gate's own docstring and in three test files.  Every one of the
~70 ``gate.require(...)`` sites across the privileged packages therefore took
the *permissive* branch, and ``gate.enforcing`` stayed ``False`` — which also
disabled the SSRF destination filter in ``network/http_client.py``.

These tests pin the behaviour down: wiring happens on construction, the wired
posture genuinely enforces (denying an identity that holds nothing), the
permissive default is retained *outside* a kernel, and shutting down restores
the pre-boot posture instead of leaking it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.capability_gate import CAP_SYS_ADMIN, CAP_FS_ADMIN, CapabilityGate, gate  # noqa: E402
from kernel.capability_manager import SYSTEM_PID, CapabilityManager  # noqa: E402
from kernel.umer_kernel import UmerKernel  # noqa: E402


# ── The gate's own contract ─────────────────────────────────────────────────

def test_permissive_when_unwired_and_not_strict():
    g = CapabilityGate()
    assert g.enforcing is False
    g.require(CAP_SYS_ADMIN)  # must not raise


def test_principal_defaults_to_os_pid_and_can_be_overridden():
    cm = CapabilityManager()
    cm.register(4242)
    cm.grant(4242, CAP_FS_ADMIN)

    g = CapabilityGate()
    g.wire(cm)
    # No principal: falls back to os.getpid(), which holds nothing -> denied.
    with pytest.raises(PermissionError):
        g.require(CAP_FS_ADMIN)

    # With an explicit principal that holds the capability -> allowed.
    g.set_principal(4242)
    g.require(CAP_FS_ADMIN)
    assert g.principal == 4242


def test_wire_with_principal_is_enforced_immediately():
    cm = CapabilityManager()
    cm.register(7)
    g = CapabilityGate()
    g.wire(cm, principal=7)
    assert g.enforcing is True
    with pytest.raises(PermissionError):
        g.require(CAP_FS_ADMIN)


def test_snapshot_restore_round_trips_the_posture():
    cm = CapabilityManager()
    g = CapabilityGate()
    before = g.snapshot()
    assert before["manager"] is None and before["principal"] is None

    g.wire(cm, principal=SYSTEM_PID)
    g.set_strict(True)
    assert g.enforcing is True

    g.restore(before)
    assert g.enforcing is False
    assert g.principal is None
    assert g.strict is False


def test_strict_env_override_makes_the_default_fail_closed(monkeypatch):
    monkeypatch.setenv("UMEROS_STRICT_GATE", "1")
    g = CapabilityGate()
    assert g.strict is True
    assert g.enforcing is True
    with pytest.raises(PermissionError):
        g.require(CAP_SYS_ADMIN)


def test_unknown_env_value_leaves_the_permissive_default(monkeypatch):
    monkeypatch.setenv("UMEROS_STRICT_GATE", "no-thanks")
    assert CapabilityGate().strict is False


# ── The kernel wiring ───────────────────────────────────────────────────────

def test_constructing_the_kernel_wires_the_gate():
    gate.unwire()
    gate.set_strict(False)
    assert gate.enforcing is False

    kernel = UmerKernel()

    assert gate.enforcing is True, "kernel did not wire the capability gate"
    assert gate.principal == SYSTEM_PID
    assert gate._manager is kernel.capabilities


def test_gate_is_enforcing_after_wiring_so_dependent_controls_activate():
    """``network/http_client.py`` gates its SSRF filter on ``gate.enforcing``."""
    gate.unwire()
    gate.set_strict(False)
    UmerKernel()
    assert gate.enforcing is True


def test_non_principal_identity_is_denied_on_the_wired_gate():
    """Default-deny for anything that is not the kernel principal."""
    kernel = UmerKernel()
    assert gate.query(CAP_FS_ADMIN) is True          # SYSTEM_PID is privileged

    intruder = 987_654
    kernel.capabilities.register(intruder)           # registered, zero caps
    assert gate.query(CAP_FS_ADMIN, pid=intruder) is False
    with pytest.raises(PermissionError):
        gate.require(CAP_FS_ADMIN, pid=intruder)


@pytest.mark.asyncio
async def test_shutdown_restores_the_pre_kernel_posture():
    gate.unwire()
    gate.set_strict(False)
    before = gate.snapshot()

    kernel = UmerKernel()
    assert gate.enforcing is True

    await kernel.shutdown()

    after = gate.snapshot()
    assert after["manager"] is before["manager"], "gate left wired after shutdown"
    assert after["principal"] == before["principal"]
    assert gate.enforcing is False, "kernel leaked a fail-closed posture"


@pytest.mark.asyncio
async def test_shutdown_preserves_a_pre_existing_wiring():
    """A gate wired by an embedder must survive a kernel boot/shutdown cycle."""
    outer = CapabilityManager()
    outer.register(31)
    outer.grant(31, CAP_FS_ADMIN)

    gate.unwire()
    gate.set_strict(False)
    gate.wire(outer, principal=31)

    kernel = UmerKernel()
    await kernel.shutdown()

    assert gate._manager is outer, "kernel clobbered someone else's wiring"
    assert gate.principal == 31
    gate.require(CAP_FS_ADMIN)  # still allowed for the outer principal


# ── Concrete downstream control that only works when the gate is enforcing ──

def test_ssrf_filter_activates_once_the_kernel_wires_the_gate():
    """``network/http_client.py`` only refuses internal hosts while enforcing.

    The filter is a real defence-in-depth control that was unreachable before
    H113: it is skipped whenever ``gate.enforcing`` is False, and nothing ever
    wired the gate, so ``enforcing`` was always False in production.
    """
    from network.http_client import HTTPClient

    metadata_url = "http://169.254.169.254/latest/meta-data/"  # link-local, SSRF

    gate.unwire()
    gate.set_strict(False)
    assert gate.enforcing is False
    # Permissive posture: the control is deliberately inactive.
    assert HTTPClient._validate_url(metadata_url) == metadata_url

    UmerKernel()  # wires the gate -> enforcing becomes True
    assert gate.enforcing is True
    with pytest.raises(ValueError, match="SSRF"):
        HTTPClient._validate_url(metadata_url)
