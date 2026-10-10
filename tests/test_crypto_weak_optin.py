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
pytest suite for H67 — weak/legacy crypto algorithms (DES, MD5) must be
opt-in only, never registered by default.
"""

import sys
from pathlib import Path

import pytest

_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

import drivers.crypto as dc  # noqa: E402


@pytest.fixture
def fresh_registry():
    """Snapshot + clear the global alg registry, restore it afterwards."""
    saved = dict(dc._alg_registry)
    dc._alg_registry.clear()
    try:
        yield dc
    finally:
        dc._alg_registry.clear()
        dc._alg_registry.update(saved)


def test_weak_algos_absent_by_default(fresh_registry):
    """Default registration must NOT expose DES or MD5 (H67)."""
    dc._register_builtin_algorithms()  # no opt-in
    assert dc.crypto_get_alg("aes") is not None
    assert dc.crypto_get_alg("sha256") is not None
    assert dc.crypto_get_alg("des") is None
    assert dc.crypto_get_alg("des-cbc") is None
    assert dc.crypto_get_alg("md5") is None


def test_weak_algos_present_with_explicit_optin(fresh_registry):
    """allow_weak=True registers the legacy algos and flags them weak."""
    dc._register_builtin_algorithms(allow_weak=True)
    for name in ("des", "des-cbc", "md5"):
        alg = dc.crypto_get_alg(name)
        assert alg is not None, f"{name} should be registered under opt-in"
        assert alg.weak is True


def test_weak_algos_optin_via_env(fresh_registry, monkeypatch):
    """UMEROS_ALLOW_WEAK_CRYPTO=1 is an explicit opt-in."""
    monkeypatch.setenv("UMEROS_ALLOW_WEAK_CRYPTO", "1")
    dc._register_builtin_algorithms()
    assert dc.crypto_get_alg("des") is not None
    assert dc.crypto_get_alg("md5") is not None


def test_strong_algos_not_flagged_weak(fresh_registry):
    """Strong primitives must never carry the weak flag."""
    dc._register_builtin_algorithms()
    assert dc.crypto_get_alg("aes").weak is False
    assert dc.crypto_get_alg("sha256").weak is False
    assert dc.crypto_get_alg("aes-gcm").weak is False
