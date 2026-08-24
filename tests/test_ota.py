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
Tests for the /cloud OTA update fail-closed signature verification (H46).

Covers ``cloud/ota_updater/update_system.py::UpdateManager.verify_and_apply``:
an update must be applied ONLY after a verifiable signature; anything else
(missing crypto engine / trusted key / signature, a verify error, or a failed
verification) must be refused — never silently applied.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class _StubCrypto:
    """Controllable fake crypto engine — `verify` return value is test-driven."""

    def __init__(self, result: bool = True, raises: bool = False) -> None:
        self.result = result
        self.raises = raises
        self.calls = 0

    def verify(self, payload, signature, public_key):  # noqa: D401 - test double
        self.calls += 1
        if self.raises:
            raise ValueError("simulated verify failure")
        return self.result


def _manager(crypto, key: str | None = "trusted-key"):
    from cloud.ota_updater.update_system import UpdateManager
    return UpdateManager(crypto_engine=crypto, trusted_public_key=key)


class TestOtaVerifyFailClosed:
    """H46: OTA signature verification must be fail-closed."""

    def test_valid_signature_applies(self):
        mgr = _manager(_StubCrypto(result=True))
        rc = mgr.verify_and_apply(b"payload", {"signature": "sig", "latest_version": "2.1.0"})
        assert rc is True

    def test_invalid_signature_refused(self):
        mgr = _manager(_StubCrypto(result=False))
        rc = mgr.verify_and_apply(b"payload", {"signature": "sig", "latest_version": "2.1.0"})
        assert rc is False

    def test_verify_error_refused(self):
        mgr = _manager(_StubCrypto(raises=True))
        rc = mgr.verify_and_apply(b"payload", {"signature": "sig", "latest_version": "2.1.0"})
        assert rc is False

    def test_no_crypto_engine_refused(self):
        mgr = _manager(None)
        rc = mgr.verify_and_apply(b"payload", {"signature": "sig", "latest_version": "2.1.0"})
        assert rc is False

    def test_no_trusted_key_refused(self):
        mgr = _manager(_StubCrypto(result=True), key=None)
        rc = mgr.verify_and_apply(b"payload", {"signature": "sig", "latest_version": "2.1.0"})
        assert rc is False

    def test_no_signature_in_manifest_refused(self):
        mgr = _manager(_StubCrypto(result=True))
        rc = mgr.verify_and_apply(b"payload", {"latest_version": "2.1.0"})
        assert rc is False

    def test_pipeline_refuses_without_signature(self):
        # run_update_pipeline -> check_for_updates (no "signature" key) ->
        # download -> verify_and_apply must REFUSE (fail-closed), never apply.
        mgr = _manager(_StubCrypto(result=True))
        assert mgr.run_update_pipeline() is False
