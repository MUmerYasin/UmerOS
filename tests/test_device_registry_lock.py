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
pytest suite for H68 — the drivers `DEVICE_REGISTRY` must be lock-guarded.
"""

import sys
import threading
from pathlib import Path

import pytest

_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

import drivers.device_registry as dr  # noqa: E402


class _FakeDev:
    """Minimal stand-in for a Device (name + overridable release hook)."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.released = False

    def release(self) -> None:
        self.released = True


@pytest.fixture
def clean_registry():
    """Snapshot + clear the global registry, restore it afterwards."""
    saved = dict(dr.DEVICE_REGISTRY)
    dr.DEVICE_REGISTRY.clear()
    try:
        yield dr
    finally:
        dr.DEVICE_REGISTRY.clear()
        dr.DEVICE_REGISTRY.update(saved)


def test_registry_uses_reentrant_lock():
    """H68: mutations are guarded by a reentrant lock."""
    assert hasattr(dr, "_registry_lock"), "registry lock is missing"
    assert isinstance(dr._registry_lock, type(threading.RLock()))
    # Prove it is reentrant (same thread may acquire twice) — needed because
    # `device_unregister` runs the overridable `release()` hook under the lock.
    assert dr._registry_lock.acquire()
    assert dr._registry_lock.acquire()
    dr._registry_lock.release()
    dr._registry_lock.release()


def test_register_get_and_duplicate(clean_registry):
    a = _FakeDev("a")
    dr.device_register(a)
    assert dr.get_device("a") is a
    assert dr.get_device("missing") is None
    with pytest.raises(ValueError):
        dr.device_register(_FakeDev("a"))


def test_unregister_calls_release_and_removes(clean_registry):
    a = _FakeDev("a")
    dr.device_register(a)
    dr.device_unregister(a)
    assert a.released is True
    assert dr.get_device("a") is None
    with pytest.raises(KeyError):
        dr.device_unregister(a)


def test_concurrent_registration(clean_registry):
    """Many threads registering unique ids must all succeed without error."""
    errors = []

    def worker(i: int) -> None:
        try:
            dr.device_register(_FakeDev(f"dev{i}"))
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert errors == []
    assert len(dr.DEVICE_REGISTRY) == 50
