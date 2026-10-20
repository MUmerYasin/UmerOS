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
UmerOS - regression tests for H163
===================================

H163 (💭 ``media/filesystem.py``): ``detect_fs_type`` returned a
non-existent enum member for NVMe device names::

    if name.startswith("nvme"):
        return FsType.NVME  # type: ignore[attr-defined]

``FsType`` has no ``NVME`` member, so any ``/dev/nvme*`` path raised
``AttributeError`` — silently hidden by the ``type: ignore`` comment.
NVMe is a *transport/controller interface*, not a filesystem type, so
the correct behaviour is to fall through to the magic-byte probe
(exactly like ``loop`` devices) and return the ``fallback`` when
nothing matches.  ``list_removable_fs()`` also listed ``EXT4`` twice.

These tests pin the *code facts* — no ``FsType.NVME``, no
``type: ignore``, the enum surface, the de-duplicated list, the
preserved name heuristics, and the no-crash fall-through.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from media.filesystem import (
    FsType,
    detect_fs_type,
    fs_type_from_name,
    list_removable_fs,
    validate_fs_type,
)

SRC_PATH = Path(__file__).resolve().parent.parent / "media" / "filesystem.py"
SRC = SRC_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Source invariants
# ---------------------------------------------------------------------------

def test_source_has_no_fstype_nvme() -> None:
    assert "FsType.NVME" not in SRC, "the undefined FsType.NVME reference is back"


def test_source_has_no_type_ignore() -> None:
    assert "type: ignore" not in SRC, "a `type: ignore` hides a real attribute error again"


def test_nvme_falls_through_to_probe() -> None:
    assert 'name.startswith("loop") or name.startswith("nvme")' in SRC


# ---------------------------------------------------------------------------
# Enum surface
# ---------------------------------------------------------------------------

def test_fstype_has_no_nvme_member() -> None:
    assert not hasattr(FsType, "NVME"), "NVMe is a transport, not a filesystem type"


def test_nvme_is_not_a_valid_fs_type() -> None:
    assert validate_fs_type("nvme") is False
    assert fs_type_from_name("nvme") is FsType.UNKNOWN


# ---------------------------------------------------------------------------
# No-crash fall-through (the actual bug)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "dev",
    [
        "/dev/nvme0n1",
        "/dev/nvme0n1p1",
        "/dev/nvme1n1p2",
        "nvme0n1p1",
        b"/dev/nvme0n1p1",
    ],
)
def test_nvme_paths_do_not_raise(dev) -> None:
    # Must not raise AttributeError; no magic probe on a non-existent node.
    assert detect_fs_type(dev, probe_magic=False) is FsType.UNKNOWN


def test_nvme_honours_custom_fallback() -> None:
    assert detect_fs_type("/dev/nvme0n1p1", probe_magic=False, fallback=FsType.EXT4) is FsType.EXT4


# ---------------------------------------------------------------------------
# Preserved name heuristics
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dev", ["/dev/sr0", "/dev/cdrom", "/dev/cdrom0"])
def test_optical_heuristic_preserved(dev: str) -> None:
    assert detect_fs_type(dev) is FsType.ISO9660


def test_floppy_heuristic_preserved() -> None:
    assert detect_fs_type("/dev/fd0") is FsType.VFAT


def test_loop_still_falls_through() -> None:
    assert detect_fs_type("/dev/loop0", probe_magic=False) is FsType.UNKNOWN


# ---------------------------------------------------------------------------
# list_removable_fs() de-duplication
# ---------------------------------------------------------------------------

def test_removable_fs_has_no_duplicates() -> None:
    lst = list_removable_fs()
    assert len(lst) == len(set(lst)), f"duplicates: {[t.value for t in set(lst) if lst.count(t) > 1]}"


def test_removable_fs_contains_ext4_exactly_once() -> None:
    assert list_removable_fs().count(FsType.EXT4) == 1


def test_removable_fs_non_empty() -> None:
    assert len(list_removable_fs()) > 0


# ---------------------------------------------------------------------------
# Self-test contract
# ---------------------------------------------------------------------------

def test_selftest_returns_true() -> None:
    from media import filesystem as _m

    assert _m._selftest() is True
