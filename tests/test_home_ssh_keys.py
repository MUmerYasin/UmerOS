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
Regression tests for H87 (home/home_ssh.py).

H87 was three defects:
  1. ``generate_key`` fabricated a PEM-shaped string from ``secrets.token_hex`` --
     not a real keypair, rejected by OpenSSH (over-stated capability).
  2. ``add_authorized_key`` appended the caller's ``public_key`` with **no format
     validation** -- an arbitrary/foreign key could be smuggled into
     ``authorized_keys`` and grant SSH access.
  3. the fingerprint used SHA-256 where the design mandate says SHA3-512.

The fix generates real keys (RSA/ed25519/ECDSA via ``cryptography``), validates
every ``authorized_keys`` line against the ``ssh-<type> <base64> [comment]``
grammar *and* parses its wire record, and pins SHA3-512 fingerprints.
"""

import base64
import importlib.util
import os
import shutil
import subprocess
import sys

import pytest

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

from core.capability_gate import CAP_HOME_ADMIN, gate  # noqa: E402


def _load(mod_name, relpath):
    spec = importlib.util.spec_from_file_location(mod_name, os.path.join(_PROJ, relpath))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


ssh = _load("umeros_h87_home_ssh", "home/home_ssh.py")

_HAS_SSHKEYGEN = shutil.which("ssh-keygen") is not None
_KEYGEN = pytest.mark.skipif(not _HAS_SSHKEYGEN, reason="ssh-keygen not available")

KEYPARAMS = [("rsa", 3072), ("ed25519", 0), ("ecdsa", 256), ("ecdsa", 384), ("ecdsa", 521)]


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h


@pytest.fixture
def mgr(home):
    m = ssh.HomeSSHManager(home_path=str(home))
    m.setup_ssh("alice")
    return m


@pytest.fixture(autouse=True)
def _gate_state():
    was_strict = gate.strict
    gate.set_strict(False)
    gate.unwire()
    yield
    gate.set_strict(was_strict)
    gate.unwire()


# --------------------------------------------------------------------------- #
# 1. Real key generation                                                        #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("key_type,bits", KEYPARAMS)
def test_generate_key_produces_real_keypair(mgr, key_type, bits):
    key = mgr.generate_key("alice", key_type, bits)
    assert key is not None
    # public line matches the ssh-<type> <base64> grammar and its blob parses
    assert ssh._validate_public_key(key.public_key) == key.public_key
    # private key is a real, parseable PKCS#8 PEM (not random hex)
    assert key.private_key.startswith("-----BEGIN PRIVATE KEY-----")
    assert key.private_key.rstrip().endswith("-----END PRIVATE KEY-----")
    assert "Proc-Type" not in key.private_key


def test_no_fabricated_key_when_crypto_missing(monkeypatch, mgr):
    monkeypatch.setattr(ssh, "_CRYPTO_AVAILABLE", False)
    with pytest.raises(RuntimeError):
        mgr.generate_key("alice", "ed25519")
    # nothing was written
    assert not (mgr._ssh_dir("alice") / "id_ed25519").exists()


@_KEYGEN
@pytest.mark.parametrize("key_type,bits", KEYPARAMS)
def test_openssh_accepts_generated_public_key(mgr, key_type, bits):
    mgr.generate_key("alice", key_type, bits)
    pub = mgr._ssh_dir("alice") / f"id_{key_type}.pub"
    out = subprocess.run(["ssh-keygen", "-l", "-f", str(pub)],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert key_type.upper().replace("ECDSA", "ECDSA") in out.stdout.upper()


@_KEYGEN
def test_openssh_private_key_derives_same_public(mgr):
    key = mgr.generate_key("alice", "ed25519")
    priv = mgr._ssh_dir("alice") / "id_ed25519"
    out = subprocess.run(["ssh-keygen", "-y", "-f", str(priv)],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.split()[:2] == key.public_key.split()[:2]


def test_rsa_minimum_size_enforced(mgr):
    key = mgr.generate_key("alice", "rsa", bits=512)  # too small -> bumped to >=2048
    assert key.bits >= 2048


# --------------------------------------------------------------------------- #
# 2. authorized_keys validation                                                 #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("hostile", [
    "",
    "not a key",
    "ssh-rsa !!!!",
    "ssh-rsa AAAA",
    "ssh-ed25519 AAAA\nssh-rsa AAAA",
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAA badb64?",
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAAA",           # truncated ed25519
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQ",             # truncated rsa
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAgQAAAARDummy",  # base64 not a record
])
def test_add_authorized_key_rejects_hostile(mgr, hostile):
    with pytest.raises(ValueError):
        mgr.add_authorized_key("alice", hostile)


def test_add_authorized_key_accepts_real_and_dedups(mgr):
    key = mgr.generate_key("alice", "ed25519")
    assert mgr.add_authorized_key("alice", key.public_key) is True
    assert mgr.add_authorized_key("alice", key.public_key) is False  # dedup
    assert mgr.list_authorized_keys("alice") == [key.public_key]


def test_add_authorized_key_accepts_options_prefix(mgr):
    key = mgr.generate_key("alice", "ed25519")
    line = 'no-pty,command="echo hi" ' + key.public_key
    assert mgr.add_authorized_key("alice", line) is True


def test_add_authorized_key_is_capability_gated(mgr):
    key = mgr.generate_key("alice", "ed25519")
    gate.set_strict(True)
    with pytest.raises(PermissionError):
        mgr.add_authorized_key("alice", key.public_key)


# --------------------------------------------------------------------------- #
# 3. SHA3-512 fingerprints                                                      #
# --------------------------------------------------------------------------- #
def test_fingerprint_uses_sha3_512(mgr):
    import hashlib
    assert ssh.SSH_FINGERPRINT_HASH is hashlib.sha3_512


def test_fingerprint_is_sha512_prefixed_and_sha3_sized(mgr):
    key = mgr.generate_key("alice", "ed25519")
    fp = getattr(key, "fingerprint")
    assert fp.startswith("SHA512:")
    # SHA3-512 -> 64 bytes -> 86 base64 chars (padding stripped)
    assert len(fp.split(":", 1)[1]) == 86


def test_public_key_wire_roundtrip(mgr):
    """Our own blob serializer must parse back through our own parser."""
    for key_type, bits in (("rsa", 2048), ("ed25519", 0), ("ecdsa", 256)):
        key = mgr.generate_key("alice", key_type, bits)
        b64 = key.public_key.split()[1]
        blob = base64.b64decode(b64)
        assert ssh._parse_public_key_blob(blob) == key.public_key.split()[0]
