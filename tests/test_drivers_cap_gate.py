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
pytest suite for H66 — zero-trust capability gating of privileged driver ops.

Proves the integration seam: with a real CapabilityManager wired that denies the
caller CAP_SYS_ADMIN, the privileged driver entry points (MMIO map, raw port
I/O, DMA alloc, PCI BAR claim, crypto TFM alloc) raise PermissionError BEFORE
touching any device state. With the capability held they proceed.
"""

import importlib
import os
import sys
from pathlib import Path

import pytest

_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from core.capability_gate import CapabilityGate, CAP_SYS_ADMIN  # noqa: E402
from kernel.capability_manager import CapabilityManager  # noqa: E402


def _wired_gate(caps):
    """A gate wired to a real CapabilityManager granting `caps` to our PID."""
    cm = CapabilityManager()
    cm.register(os.getpid())
    for c in caps:
        cm.grant(os.getpid(), c)
    g = CapabilityGate()
    g.wire(cm)
    return g


# ── Deny path: current pid lacks CAP_SYS_ADMIN ────────────────────────────────

@pytest.mark.parametrize(
    "mod_name,func,args",
    [
        ("drivers.device_io", "devm_ioremap", ("mmio0", 0xF0000000, 4096)),
        ("drivers.device_io", "inb", (0x60,)),
        ("drivers.device_io", "inw", (0x60,)),
        ("drivers.device_io", "inl", (0x60,)),
        ("drivers.device_io", "outb", (0x60, 0xFF)),
        ("drivers.device_io", "outw", (0x60, 0xFFFF)),
        ("drivers.device_io", "outl", (0x60, 0xFFFFFFFF)),
        ("drivers.device_io", "dma_alloc_coherent", ("dma0", 4096)),
        ("drivers.pci", "pci_request_region", ("dev0", 0)),
        ("drivers.crypto", "crypto_alloc_tfm", ("aes",)),
    ],
)
def test_driver_privileged_ops_deny_without_sys_admin(mod_name, func, args):
    """Each privileged driver entry point must raise PermissionError when the
    wired CapabilityManager denies the caller CAP_SYS_ADMIN (H66)."""
    mod = importlib.import_module(mod_name)
    prev = mod.gate
    mod.gate = _wired_gate(caps=[])  # current pid lacks sys.admin
    try:
        with pytest.raises(PermissionError):
            getattr(mod, func)(*args)
    finally:
        mod.gate = prev  # restore benign permissive default


# ── Allow path: current pid holds CAP_SYS_ADMIN ───────────────────────────────

def test_devm_ioremap_allows_when_sys_admin_held():
    """Positive path: with CAP_SYS_ADMIN held, the MMIO map proceeds."""
    import drivers.device_io as dio

    prev = dio.gate
    dio.gate = _wired_gate(caps=[CAP_SYS_ADMIN])
    try:
        reg = dio.devm_ioremap("mmio_ok", 0xF1000000, 4096)
        assert reg.is_mapped is True
        dio.devm_iounmap("mmio_ok")
    finally:
        dio.gate = prev


def test_crypto_alloc_tfm_allows_when_sys_admin_held():
    """Positive path: with CAP_SYS_ADMIN held, the crypto TFM alloc proceeds."""
    import drivers.crypto as dc

    prev = dc.gate
    dc.gate = _wired_gate(caps=[CAP_SYS_ADMIN])
    try:
        # Built-ins are only registered on demand, not at import time.
        dc._register_builtin_algorithms()
        tfm = dc.crypto_alloc_tfm("aes")
        assert tfm.name == "aes"
    finally:
        dc.gate = prev
