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
pytest suite for kernel CryptoEngine (H111) and OTA signature verification
(H154).

H111: CryptoEngine.verify() used to return True unconditionally and sign()
returned a constant, so every signature validated (dummy crypto).  Now
sign/verify use HMAC-SHA256 with a per-instance key.

H154: UpdateManager.verify_and_apply() used to sign the payload with its own
engine and declare success, or skip verification entirely (fail-open) and the
manifest shipped a hardcoded fake signature.  Now it applies an update only when
a real signature verifies against a trusted key.
"""

import os
import sys

from pathlib import Path

import pytest

_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from kernel.umer_kernel import CryptoEngine  # noqa: E402
from cloud.ota_updater.update_system import UpdateManager  # noqa: E402


def test_crypto_sign_verify_roundtrip():
    ce = CryptoEngine()
    data = b"important firmware blob"
    sig = ce.sign(data)
    assert ce.verify(data, sig) is True
    # Tampered data must NOT verify.
    assert ce.verify(b"tampered", sig) is False
    # A wrong signature must NOT verify.
    assert ce.verify(data, b"wrong-sig") is False


def test_crypto_verify_is_key_bound():
    ce_a = CryptoEngine()
    ce_b = CryptoEngine()
    data = b"payload"
    sig = ce_a.sign(data)
    # Signature from one key must not validate under another.
    assert ce_b.verify(data, sig, key=ce_a._key) is True
    assert ce_a.verify(data, sig, key=ce_b._key) is False


def test_ota_verify_fail_closed():
    ce = CryptoEngine()
    payload = b"UMER_OS_DELTA_PAYLOAD_v2.1.0"

    # No crypto engine / trusted key -> refuse (fail-closed).
    um = UpdateManager()
    assert um.verify_and_apply(
        payload, {"signature": b"x", "latest_version": "2.1.0"}
    ) is False

    # Real signature + trusted key -> accept.
    sig = ce.sign(payload)
    um_ok = UpdateManager(crypto_engine=ce, trusted_public_key=ce._key)
    assert um_ok.verify_and_apply(
        payload, {"signature": sig, "latest_version": "2.1.0"}
    ) is True

    # Wrong signature -> refuse.
    um_bad = UpdateManager(crypto_engine=ce, trusted_public_key=ce._key)
    assert um_bad.verify_and_apply(
        payload, {"signature": b"bad", "latest_version": "2.1.0"}
    ) is False
