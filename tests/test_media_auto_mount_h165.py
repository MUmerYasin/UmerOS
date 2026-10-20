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
UmerOS - regression tests for H165
===================================

H165 (💭 ``media/auto_mount.py``): ``AutoMountPolicy.user_mode`` was a
**decorative field** — declared with ``user_mode: bool = True`` and never
read by anything, so the daemon always mounted into the system-wide
``/media`` root regardless of the setting.  There was also no consent
step before auto-mounting, despite the §4.2 consent mandate: plugging a
USB stick silently mounted it.

The fix gives ``user_mode`` real semantics (a per-user namespace,
``<base>/<user>/``, matching udisks2's ``--enable-fhs-media`` layout) and
adds a fail-closed consent gate:

* ``require_consent`` + ``consent_provider`` -> mount only on an explicit
  ``True``;
* ``require_consent`` with **no** provider -> ``SKIPPED_CONSENT``
  (fail-closed: consent cannot be established);
* a provider that raises -> ``False`` (deny).

The default ``user_mode`` is now ``False`` because that is what the daemon
has always actually done — the old ``True`` default was inert, so this
change is behaviour-neutral for existing callers.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from media import auto_mount
from media.auto_mount import (
    AutoMountDaemon,
    AutoMountPolicy,
    AutoMountStatus,
)
from media.hotplug import HotplugBus
from media.media_types import MediaType
from media.mount_ops import clear_sim_mounts, set_simulation

SRC_PATH = Path(__file__).resolve().parent.parent / "media" / "auto_mount.py"
SRC = SRC_PATH.read_text(encoding="utf-8")


@pytest.fixture
def sim():
    set_simulation(True)
    clear_sim_mounts()
    yield
    clear_sim_mounts()


# ---------------------------------------------------------------------------
# user_mode is no longer decorative
# ---------------------------------------------------------------------------

def test_user_mode_default_is_honest() -> None:
    # The daemon has always mounted system-wide; the default must say so.
    assert AutoMountPolicy().user_mode is False


def test_user_mode_is_read_by_the_policy() -> None:
    assert "self.user_mode" in SRC, "user_mode is decorative again"


def test_mount_base_system_wide_without_user_mode() -> None:
    assert AutoMountPolicy().mount_base("/media") == "/media"
    assert AutoMountPolicy(user_mode=False, user="alice").mount_base("/media") == "/media"


def test_mount_base_scoped_when_user_mode_and_user() -> None:
    policy = AutoMountPolicy(user_mode=True, user="alice")
    assert policy.mount_base("/media") == os.path.join("/media", "alice")


def test_mount_base_falls_back_without_user() -> None:
    assert AutoMountPolicy(user_mode=True, user=None).mount_base("/media") == "/media"


def test_do_mount_uses_user_namespace(sim, tmp_path: Path) -> None:
    policy = AutoMountPolicy(user_mode=True, user="alice")
    daemon = AutoMountDaemon(policy=policy, base_path=str(tmp_path))
    ev = daemon.mount_device("/dev/sdq1", MediaType.USB)
    assert ev.status is AutoMountStatus.MOUNTED, ev.message
    assert ev.mount_point == os.path.join(str(tmp_path), "alice", "usb0")


# ---------------------------------------------------------------------------
# Consent gate
# ---------------------------------------------------------------------------

def test_no_consent_required_by_default() -> None:
    assert AutoMountPolicy().consent_for("/dev/sdb1", MediaType.USB) is True


def test_required_consent_without_provider_fails_closed() -> None:
    assert AutoMountPolicy(require_consent=True).consent_for(
        "/dev/sdb1", MediaType.USB
    ) is None


def test_consent_provider_denies() -> None:
    policy = AutoMountPolicy(require_consent=True, consent_provider=lambda _d, _m: False)
    assert policy.consent_for("/dev/sdb1", MediaType.USB) is False


def test_consent_provider_grants() -> None:
    policy = AutoMountPolicy(require_consent=True, consent_provider=lambda _d, _m: True)
    assert policy.consent_for("/dev/sdb1", MediaType.USB) is True


def test_consent_provider_exception_denies() -> None:
    def boom(_d, _m):
        raise RuntimeError("provider exploded")

    policy = AutoMountPolicy(require_consent=True, consent_provider=boom)
    assert policy.consent_for("/dev/sdb1", MediaType.USB) is False


def test_skipped_consent_status_exists() -> None:
    assert AutoMountStatus.SKIPPED_CONSENT.value == "skipped_consent"


def test_daemon_skips_mount_when_consent_unobtainable(sim) -> None:
    daemon = AutoMountDaemon(policy=AutoMountPolicy(require_consent=True))
    ev = daemon.mount_device("/dev/sdr1", MediaType.USB)
    assert ev.status is AutoMountStatus.SKIPPED_CONSENT
    assert "/dev/sdr1" not in daemon.active_mounts


def test_daemon_skips_mount_when_consent_denied(sim) -> None:
    policy = AutoMountPolicy(require_consent=True, consent_provider=lambda _d, _m: False)
    daemon = AutoMountDaemon(policy=policy)
    ev = daemon.mount_device("/dev/sdr2", MediaType.USB)
    assert ev.status is AutoMountStatus.SKIPPED_CONSENT
    assert "/dev/sdr2" not in daemon.active_mounts


def test_daemon_mounts_when_consent_granted(sim) -> None:
    policy = AutoMountPolicy(require_consent=True, consent_provider=lambda _d, _m: True)
    daemon = AutoMountDaemon(policy=policy)
    ev = daemon.mount_device("/dev/sdr3", MediaType.USB)
    assert ev.status is AutoMountStatus.MOUNTED, ev.message


# ---------------------------------------------------------------------------
# start() warning + identity threading
# ---------------------------------------------------------------------------

def test_start_warns_when_user_mode_has_no_user(sim, caplog) -> None:
    daemon = AutoMountDaemon(policy=AutoMountPolicy(user_mode=True, user=None))
    with caplog.at_level(logging.WARNING, logger="UmerOS.Media.AutoMount"):
        daemon.start()
    daemon.stop()
    msgs = [r.getMessage().lower() for r in caplog.records]
    assert any("user_mode" in m and "no `user`" in m for m in msgs), msgs


def test_no_warning_when_user_mode_disabled(sim, caplog) -> None:
    daemon = AutoMountDaemon(policy=AutoMountPolicy(user_mode=False))
    with caplog.at_level(logging.WARNING, logger="UmerOS.Media.AutoMount"):
        daemon.start()
    daemon.stop()
    msgs = [r.getMessage().lower() for r in caplog.records]
    assert not any("user_mode" in m for m in msgs), msgs


def test_user_identity_threaded_to_mount(sim, monkeypatch) -> None:
    captured = {}

    def fake_mount(device, mnt, **kwargs):
        captured.update(kwargs)
        from types import SimpleNamespace

        return SimpleNamespace(success=True, summary="ok")

    monkeypatch.setattr(auto_mount, "mount", fake_mount)
    daemon = AutoMountDaemon(policy=AutoMountPolicy(user="alice"))
    daemon.mount_device("/dev/sds1", MediaType.USB)
    assert captured.get("user") == "alice"


def test_no_user_kwarg_when_identity_unset(sim, monkeypatch) -> None:
    captured = {}

    def fake_mount(device, mnt, **kwargs):
        captured.update(kwargs)
        from types import SimpleNamespace

        return SimpleNamespace(success=True, summary="ok")

    monkeypatch.setattr(auto_mount, "mount", fake_mount)
    daemon = AutoMountDaemon(policy=AutoMountPolicy())
    daemon.mount_device("/dev/sds2", MediaType.USB)
    assert "user" not in captured


# ---------------------------------------------------------------------------
# Self-test contract
# ---------------------------------------------------------------------------

def test_selftest_returns_true() -> None:
    assert auto_mount._selftest() is True
