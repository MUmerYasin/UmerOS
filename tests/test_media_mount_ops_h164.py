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
UmerOS - regression tests for H164
===================================

H164 (💭 ``media/mount_ops.py``): ``_real_unmount`` was **dead code** —
``mount()`` delegated to ``_real_mount()`` and ``remount()`` to
``_real_remount()``, but ``unmount()`` had grown its own inline umount
path, leaving ``_real_unmount`` unreachable.  Worse, its lazy flag was
wired to the wrong switch::

    if sync:
        cmd.append("-l")   # lazy unmount if busy

so "flush pending writes" silently also meant "lazy unmount", and there
was no way to request a lazy unmount independently.

The dead function is removed.  The live ``unmount()`` keeps the correct
semantics (``force`` -> ``-f``, ``lazy`` -> ``-l``, mutually exclusive)
and now logs a warning when both are requested instead of silently
dropping ``lazy``.

These tests pin the *code facts* and the emitted argv.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import pytest

from media import mount_ops

SRC_PATH = Path(__file__).resolve().parent.parent / "media" / "mount_ops.py"
SRC = SRC_PATH.read_text(encoding="utf-8")


def _mp(path: str) -> str:
    """The path exactly as ``unmount()`` normalises it (platform-aware)."""
    return os.path.normpath(path)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def captured(monkeypatch):
    """Force the real (non-simulated) umount path and capture the argv."""
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return (0, "", "")

    monkeypatch.setattr(mount_ops, "_use_simulation", False)
    monkeypatch.setattr(mount_ops, "sync_mount", lambda _p: True)
    monkeypatch.setattr(mount_ops, "_run_cmd", fake_run)
    return calls


# ---------------------------------------------------------------------------
# Dead code removed
# ---------------------------------------------------------------------------

def test_real_unmount_is_gone() -> None:
    assert not hasattr(mount_ops, "_real_unmount"), "_real_unmount is dead code and must stay deleted"


def test_source_has_no_real_unmount() -> None:
    assert "def _real_unmount(" not in SRC


def test_real_mount_and_remount_are_kept() -> None:
    # Guard against over-deletion: these two ARE used by mount()/remount().
    assert hasattr(mount_ops, "_real_mount")
    assert hasattr(mount_ops, "_real_remount")


# ---------------------------------------------------------------------------
# The lazy flag is no longer conflated with `sync`
# ---------------------------------------------------------------------------

def test_no_lazy_flag_tied_to_sync() -> None:
    assert not re.search(r'if sync:\s*\n\s*cmd\.append\("-l"\)', SRC), \
        "`-l` must never be gated on `sync`"


def test_dash_l_appears_exactly_once() -> None:
    assert SRC.count('cmd.append("-l")') == 1


def test_dash_l_is_driven_by_lazy() -> None:
    assert re.search(r'elif lazy:\s*\n\s*cmd\.append\("-l"\)', SRC)


# ---------------------------------------------------------------------------
# Emitted argv
# ---------------------------------------------------------------------------

def test_plain_unmount_has_no_flags(captured) -> None:
    result = mount_ops.unmount("/media/x0", sync=False)
    assert result.success
    assert captured[-1] == ["umount", _mp("/media/x0")]


def test_lazy_adds_dash_l(captured) -> None:
    result = mount_ops.unmount("/media/x1", sync=False, lazy=True)
    assert result.success
    assert captured[-1] == ["umount", "-l", _mp("/media/x1")]


def test_force_adds_dash_f(captured) -> None:
    result = mount_ops.unmount("/media/x2", sync=False, force=True)
    assert result.success
    assert captured[-1] == ["umount", "-f", _mp("/media/x2")]


def test_force_wins_over_lazy(captured) -> None:
    result = mount_ops.unmount("/media/x3", sync=False, force=True, lazy=True)
    assert result.success
    assert captured[-1] == ["umount", "-f", _mp("/media/x3")]


def test_sync_flushes_before_umount(captured) -> None:
    result = mount_ops.unmount("/media/x4", sync=True)
    assert result.success
    # sync_mount() is patched, so only the umount argv is captured here.
    assert captured[-1] == ["umount", _mp("/media/x4")]


# ---------------------------------------------------------------------------
# Explicit precedence warning
# ---------------------------------------------------------------------------

def test_force_plus_lazy_logs_warning(captured, caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="UmerOS.Media.MountOps"):
        mount_ops.unmount("/media/x5", sync=False, force=True, lazy=True)
    msgs = [r.getMessage().lower() for r in caplog.records]
    assert any("force" in m and "lazy" in m for m in msgs), msgs


def test_lazy_alone_does_not_warn(captured, caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="UmerOS.Media.MountOps"):
        mount_ops.unmount("/media/x6", sync=False, lazy=True)
    msgs = [r.getMessage().lower() for r in caplog.records]
    assert not any("mutually exclusive" in m for m in msgs), msgs


# ---------------------------------------------------------------------------
# Public signature + self-test contract
# ---------------------------------------------------------------------------

def test_unmount_accepts_lazy_and_force() -> None:
    import inspect

    params = inspect.signature(mount_ops.unmount).parameters
    assert params["lazy"].default is False
    assert params["force"].default is False


def test_selftest_returns_true() -> None:
    assert mount_ops._selftest() is True
