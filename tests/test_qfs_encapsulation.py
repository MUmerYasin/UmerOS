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
pytest suite for H82 — `fs/qfs.py` encapsulation + hash-strength.

H82: (a) `QFS.snapshot()` reached into the private `CASStore._blocks`/`._refs`
internals instead of a public API; (b) the CAS is SHA3-256-addressed while the
repo-wide design mandate names SHA3-512. The fix adds public
`CASStore.ref_count()`/`retain()`/`snapshot_state()` APIs (used by
`QFS.snapshot`), and single-sources + documents the deliberate SHA3-256
content-addressing exemption.
"""

import hashlib
import os
import sys
from pathlib import Path

import pytest

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

from fs.qfs import CAS_ADDRESS_HEX_LEN, CAS_HASH, CASStore, QFS  # noqa: E402

_QFS_SRC = (Path(_PROJ) / "fs" / "qfs.py").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _gate_state():
    from core.capability_gate import gate

    was_strict = gate.strict
    gate.set_strict(False)
    gate.unwire()
    yield
    gate.set_strict(was_strict)
    gate.unwire()


# ── encapsulation ───────────────────────────────────────────────────────────

def test_qfs_no_longer_touches_private_store_internals():
    assert "_store._blocks" not in _QFS_SRC
    assert "_store._refs" not in _QFS_SRC


def test_casstore_exposes_public_refcount_api():
    store = CASStore()
    for name in ("ref_count", "retain", "snapshot_state"):
        assert callable(getattr(store, name)), f"CASStore lacks public {name}()"


def test_ref_count_and_retain():
    store = CASStore()
    addr = store.put(b"payload")
    assert store.ref_count(addr) == 1
    assert store.retain(addr) == 2
    assert store.ref_count(addr) == 2
    # unknown address
    assert store.ref_count("deadbeef") == 0
    assert store.retain("deadbeef") == 0


def test_snapshot_state_returns_a_copy():
    store = CASStore()
    addr = store.put(b"payload")
    state = store.snapshot_state()
    assert state[addr] == 1
    state[addr] = 999          # mutating the copy must not affect the store
    assert store.ref_count(addr) == 1


def test_qfs_snapshot_uses_public_retain_api():
    q = QFS()
    addr = q.write_file("/a.txt", b"data")
    assert q._store.ref_count(addr) == 1
    q.snapshot()
    # snapshot retained the block via the public API (1 -> 2)
    assert q._store.ref_count(addr) == 2


def test_snapshot_restore_still_roundtrips():
    q = QFS()
    q.write_file("/a.txt", b"data")
    snap = q.snapshot()
    q.write_file("/a.txt", b"changed")
    assert q.restore_snapshot(snap) is True
    assert q.read_file("/a.txt") == b"data"


# ── hash strength (documented exemption) ────────────────────────────────────

def test_cas_hash_is_pinned_sha3_256():
    assert CAS_HASH is hashlib.sha3_256
    assert CAS_ADDRESS_HEX_LEN == 64


def test_addresses_are_64_hex_chars():
    store = CASStore()
    addr = store.put(b"payload")
    assert len(addr) == CAS_ADDRESS_HEX_LEN
    assert addr == hashlib.sha3_256(b"payload").hexdigest()


def test_exemption_is_documented_in_source():
    assert "documented exemption" in _QFS_SRC
    assert "SHA3-256" in _QFS_SRC
