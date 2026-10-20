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
UmerOS - regression tests for H161
===================================

H161 (💭 ``media/`` ``_selftest()`` conformance): ``device_info``,
``cleanup``, ``hotplug`` and ``mount_manager`` shipped ``_selftest()``
bodies that either crashed (calling non-existent APIs such as
``scan_stale_mounts`` / ``HotplugEventType`` / ``MountManager(media_root=...)``)
or did not conform to the tree-wide pattern used by the rest of ``media/``
(``media/usb/storage.py`` et al.):

    def _selftest() -> bool:
        ...
        print("selftest OK")
        return True

    if __name__ == "__main__":
        import sys
        sys.exit(0 if _selftest() else 1)

These tests pin the *code facts* (return annotation, ``return True``, the
``__main__`` guard, and the absence of the removed broken call sites) —
never a cosmetic ``[FIX Hxxx]`` comment tag, which an external process
periodically strips.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

# Modules fixed by H161 (dotted import name -> source path relative to repo root).
TARGETS = {
    "media.device_info": "media/device_info.py",
    "media.cleanup": "media/cleanup.py",
    "media.hotplug": "media/hotplug.py",
    "media.mount_manager": "media/mount_manager.py",
}

REPO_ROOT = Path(__file__).resolve().parent.parent

# Broken call sites / tokens that must no longer appear in these modules.
FORBIDDEN_TOKENS = (
    "scan_stale_mounts",
    "HotplugEventType",
    "MountManager(media_root=",
)


@pytest.mark.parametrize("dotted", sorted(TARGETS))
def test_selftest_is_callable(dotted: str) -> None:
    mod = importlib.import_module(dotted)
    assert callable(getattr(mod, "_selftest", None)), f"{dotted} has no callable _selftest"


@pytest.mark.parametrize("dotted", sorted(TARGETS))
def test_selftest_returns_true(dotted: str) -> None:
    mod = importlib.import_module(dotted)
    assert mod._selftest() is True, f"{dotted}._selftest() should return True"


@pytest.mark.parametrize("dotted", sorted(TARGETS))
def test_selftest_has_bool_return_annotation(dotted: str) -> None:
    mod = importlib.import_module(dotted)
    ann = getattr(mod._selftest, "__annotations__", {})
    # ``from __future__ import annotations`` stringifies the annotation.
    assert ann.get("return") in (bool, "bool"), f"{dotted}._selftest lacks a '-> bool' annotation"


@pytest.mark.parametrize("dotted, relpath", sorted(TARGETS.items()))
def test_source_has_canonical_guard(dotted: str, relpath: str) -> None:
    src = (REPO_ROOT / relpath).read_text(encoding="utf-8")
    assert "def _selftest() -> bool:" in src, f"{relpath}: missing canonical signature"
    assert "return True" in src, f"{relpath}: missing 'return True'"
    assert 'sys.exit(0 if _selftest() else 1)' in src, f"{relpath}: missing canonical __main__ guard"


@pytest.mark.parametrize("dotted, relpath", sorted(TARGETS.items()))
def test_source_has_no_broken_tokens(dotted: str, relpath: str) -> None:
    src = (REPO_ROOT / relpath).read_text(encoding="utf-8")
    for tok in FORBIDDEN_TOKENS:
        assert tok not in src, f"{relpath}: stale broken token {tok!r} still present"


def test_hotplug_selftest_uses_hotplug_action_enum() -> None:
    """The fixed hotplug selftest must exercise the real HotplugAction enum."""
    src = (REPO_ROOT / TARGETS["media.hotplug"]).read_text(encoding="utf-8")
    assert "HotplugAction.ADD" in src
    assert "HotplugEvent(action=" in src


def test_mount_manager_selftest_uses_media_config() -> None:
    """The fixed mount_manager selftest must build a MediaConfig, not pass media_root=."""
    src = (REPO_ROOT / TARGETS["media.mount_manager"]).read_text(encoding="utf-8")
    assert "MediaConfig(media_root=" in src
    assert "MountManager(config=" in src


def test_cleanup_selftest_uses_cleanup_media() -> None:
    """The fixed cleanup selftest must call the real cleanup_media() entry point."""
    src = (REPO_ROOT / TARGETS["media.cleanup"]).read_text(encoding="utf-8")
    assert "cleanup_media(cfg)" in src
    assert "CleanupConfig(" in src
