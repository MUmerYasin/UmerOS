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
UmerOS ~/.ssh/ Key Manager [EXPERIMENTAL]
Manages SSH keys: id_rsa, id_rsa.pub, authorized_keys, known_hosts, config.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import base64
import binascii
import hashlib
import logging
import re
import secrets
import struct

# [FIX H84] Fail-closed path-traversal containment (CWE-22): every caller-supplied
# name (username / message id / subdir / filename) is validated as a single safe
# path segment -- or a contained multi-segment join -- before any home path is built.
try:
    from core.path_guard import PathTraversalError, safe_child, safe_join
except Exception:  # pragma: no cover - standalone fallback
    import os as _os
    import sys as _sys
    _proj = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if _proj not in _sys.path:
        _sys.path.insert(0, _proj)
    from core.path_guard import PathTraversalError, safe_child, safe_join

# [FIX H85] Zero-trust capability gate for privileged /home mutations. When a
# CapabilityManager is wired the gate is fail-closed (PermissionError); standalone it
# is permissive-with-warning so existing tooling keeps working (H60/H66/H73/H80).
try:
    from core.capability_gate import gate, CAP_HOME_ADMIN
except Exception:  # pragma: no cover - standalone fallback
    import os as _os
    import sys as _sys
    _proj = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if _proj not in _sys.path:
        _sys.path.insert(0, _proj)
    from core.capability_gate import gate, CAP_HOME_ADMIN

# [FIX H87] Real SSH key generation backend (``cryptography``; a declared dep).
try:
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat, PublicFormat,
    )
    _CRYPTO_AVAILABLE = True
except Exception:  # pragma: no cover - cryptography is a declared dependency
    _CRYPTO_AVAILABLE = False


# [FIX H87] SSH key integrity + ``authorized_keys`` validation.
#
# (a) ``generate_key`` now produces a **real** keypair via ``cryptography`` (the
#     same library 10 other UmerOS modules use) serialised in OpenSSH format,
#     instead of fabricating a PEM-shaped string from ``secrets.token_hex`` (which
#     OpenSSH rejects -- it over-stated capability like H33/H49/H14).
# (b) ``add_authorized_key`` validates the caller line against the
#     ``ssh-<type> <base64> [comment]`` grammar AND cross-checks that the base64
#     body decodes to an SSH wire record of that type, so an arbitrary/foreign key
#     cannot be smuggled into ``authorized_keys``.
# (c) fingerprints use SHA3-512 ("SHA512:..."), matching the design mandate and
#     the repo-wide SHA3-512 precedent (30+ uses in ``boot/``). The CAS-style
#     exemption applied to ``fs/qfs.py`` (H82) does NOT extend here: the mandate
#     explicitly pins *SSH* fingerprints to SHA3-512.
log = logging.getLogger("UmerOS.Home.SSH")

SSH_FINGERPRINT_HASH = hashlib.sha3_512  # [FIX H87] design mandate: SHA3-512
SSH_KEY_TYPES = (
    "ssh-rsa", "ssh-ed25519", "ssh-dss",
    "ecdsa-sha2-nistp256", "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521",
)
_AUTHORIZED_KEY_RE = re.compile(
    r"^(ssh-rsa|ssh-ed25519|ssh-dss|ecdsa-sha2-nistp(?:256|384|521))"
    r"[ \t]+([A-Za-z0-9+/]+={0,3})(?:[ \t]+([^\t\n\r]*))?[ \t]*$"
)
# [FIX H87] authorized_keys options are a comma-separated list that may itself
# contain double-quoted values with spaces (``command="echo hi"``), so the
# options field cannot be matched by a naive whitespace token. ``_strip_options``
# walks the prefix, tracking quote state, and returns the remainder.
_KEY_TYPE_TOKENS = ("ssh-rsa", "ssh-ed25519", "ssh-dss", "ecdsa-sha2-")


def _ssh_string(data: bytes) -> bytes:
    """Length-prefix ``data`` per the SSH wire format."""
    return struct.pack(">I", len(data)) + data


def _read_ssh_string(blob: bytes, offset: int):
    """Parse one length-prefixed SSH string; return ``(value, new_offset)``."""
    if offset + 4 > len(blob):
        raise ValueError("truncated SSH record")
    (length,) = struct.unpack(">I", blob[offset:offset + 4])
    start = offset + 4
    end = start + length
    if end > len(blob):
        raise ValueError("truncated SSH record")
    return blob[start:end], end


def _mpint(value: int) -> bytes:
    """Encode an int as an SSH ``mpint`` (length-prefixed two's-complement).

    [FIX H87] SSH mpints are *strings* on the wire: the big-endian two's-
    complement bytes are themselves length-prefixed, exactly like every other
    SSH string (RFC 4251 §5). Returning bare bytes produced an unparseable RSA
    record that ``ssh-keygen`` rejected.
    """
    if value == 0:
        return _ssh_string(b"")
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    if raw[0] & 0x80:
        raw = b"\x00" + raw
    return _ssh_string(raw)


def _parse_public_key_blob(blob: bytes) -> str:
    """Return the embedded key-type string if ``blob`` is a valid SSH record.

    [FIX H87] Parses the *whole* record for every supported type, so a truncated
    or structurally bogus blob (e.g. a lone type field with no key material) is
    rejected rather than merely having its first field inspected.
    """
    if len(blob) < 4:
        raise ValueError("public key blob too short")
    type_bytes, offset = _read_ssh_string(blob, 0)
    try:
        key_type = type_bytes.decode("ascii", "strict")
    except UnicodeDecodeError as exc:
        raise ValueError("public key type is not ASCII") from exc

    def _need_string(pos):
        value, pos = _read_ssh_string(blob, pos)
        if not value:
            raise ValueError("empty field in public key record")
        return value, pos

    if key_type == "ssh-rsa":
        _e, offset = _need_string(offset)          # mpint e
        _n, offset = _need_string(offset)          # mpint n
    elif key_type in ("ssh-ed25519", "ssh-dss"):
        _k, offset = _need_string(offset)
    elif key_type.startswith("ecdsa-sha2-"):
        _curve, offset = _need_string(offset)
        _point, offset = _need_string(offset)
    else:
        raise ValueError(f"unsupported public key type: {key_type!r}")
    if offset != len(blob):
        raise ValueError("trailing bytes after public key record")
    return key_type


def _strip_options(line: str) -> str:
    """Strip an optional ``authorized_keys`` options prefix.

    [FIX H87] The options field is comma-separated and may contain double-quoted
    values with spaces, so it cannot be split on whitespace. Walk the prefix
    tracking quote state and cut immediately before the first bare ``ssh-`` /
    ``ecdsa-`` token.
    """
    in_quote = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_quote = not in_quote
        elif not in_quote and ch in " \t" and i + 1 < len(line):
            rest = line[i + 1:]
            if any(rest.startswith(tok) for tok in _KEY_TYPE_TOKENS):
                return rest
    return line


def _validate_public_key(public_key: str) -> str:
    """[FIX H87] Validate a single ``authorized_keys`` line; return it stripped."""
    if not public_key or "\n" in public_key or "\r" in public_key:
        raise ValueError("authorized key must be a single non-empty line")
    stripped = public_key.strip()
    body = _strip_options(stripped)
    match = _AUTHORIZED_KEY_RE.match(body)
    if not match:
        raise ValueError("authorized key does not match ssh-<type> <base64> [comment]")
    key_type, b64, _comment = match.groups()
    try:
        blob = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"authorized key has invalid base64: {exc}") from exc
    try:
        embedded = _parse_public_key_blob(blob)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError(f"authorized key has an invalid wire record: {exc}") from exc
    if embedded != key_type:
        raise ValueError(
            f"authorized key type mismatch: token {key_type!r} vs blob {embedded!r}"
        )
    return stripped


def _public_key_blob(pub) -> bytes:
    """Serialise a ``cryptography`` public key to an SSH wire blob."""
    if isinstance(pub, rsa.RSAPublicKey):
        numbers = pub.public_numbers()
        # [FIX H87] SSH RSA record is: type-string, then mpint(e), then mpint(n).
        body = _mpint(numbers.e) + _mpint(numbers.n)
        return _ssh_string(b"ssh-rsa") + body
    if isinstance(pub, ed25519.Ed25519PublicKey):
        raw = pub.public_bytes(Encoding.Raw, PublicFormat.Raw)
        return _ssh_string(b"ssh-ed25519") + _ssh_string(raw)
    if isinstance(pub, ec.EllipticCurvePublicKey):
        if isinstance(pub.curve, ec.SECP256R1):
            name = "nistp256"
        elif isinstance(pub.curve, ec.SECP384R1):
            name = "nistp384"
        elif isinstance(pub.curve, ec.SECP521R1):
            name = "nistp521"
        else:
            raise ValueError(f"unsupported EC curve: {pub.curve.name}")
        point = pub.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
        return (_ssh_string(f"ecdsa-sha2-{name}".encode())
                + _ssh_string(name.encode()) + _ssh_string(point))
    raise ValueError(f"unsupported public key type: {type(pub).__name__}")


def _openssh_public_line(pub, comment: str) -> str:
    """Return ``ssh-<type> <base64> <comment>`` for a public key."""
    blob = _public_key_blob(pub)
    key_type = _parse_public_key_blob(blob)
    return f"{key_type} {base64.b64encode(blob).decode()} {comment}".strip()


def _ssh_public_fingerprint(pub) -> str:
    """SHA3-512 fingerprint of the key blob, as ``SHA512:<base64 no padding>``."""
    digest = SSH_FINGERPRINT_HASH(_public_key_blob(pub)).digest()
    return "SHA512:" + base64.b64encode(digest).decode().rstrip("=")


def _new_keypair(key_type: str, bits: int):
    """Build a real private/public keypair for ``key_type``."""
    if key_type == "rsa":
        private = rsa.generate_private_key(public_exponent=65537,
                                           key_size=max(2048, int(bits or 4096)))
    elif key_type == "ed25519":
        private = ed25519.Ed25519PrivateKey.generate()
    elif key_type == "ecdsa":
        curve = {256: ec.SECP256R1, 384: ec.SECP384R1, 521: ec.SECP521R1}.get(int(bits or 521))
        private = ec.generate_private_key((curve or ec.SECP521R1)())
    else:
        raise ValueError(f"unsupported key type: {key_type!r}")
    return private, private.public_key()


def _effective_bits(pub) -> int:
    """Return the real key size (RSA modulus bits, EC curve size, ed25519=256)."""
    if isinstance(pub, rsa.RSAPublicKey):
        return pub.key_size
    if isinstance(pub, ed25519.Ed25519PublicKey):
        return 256
    if isinstance(pub, ec.EllipticCurvePublicKey):
        return pub.curve.key_size
    return 0


def _private_pem(private) -> str:
    """Serialise a private key as unencrypted PKCS#8 PEM for ``id_<type>``."""
    return private.private_bytes(
        Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
    ).decode("ascii")


@dataclass
class SSHKey:
    name: str
    private_key: str = ""
    public_key: str = ""
    key_type: str = "rsa"
    bits: int = 4096
    comment: str = ""

    def is_valid(self) -> bool:
        return bool(self.private_key and self.public_key)


@dataclass
class KnownHost:
    hostname: str
    key_type: str = "rsa"
    fingerprint: str = ""
    key: str = ""


class HomeSSHManager:
    KEY_TYPES = ["rsa", "ed25519", "ecdsa"]
    DEFAULT_BITS = {"rsa": 4096, "ecdsa": 521, "ed25519": 256}

    def __init__(self, home_path: str = "/home"):
        self.home_path = Path(home_path)
        self.keys: Dict[str, Dict[str, SSHKey]] = {}
        self.known_hosts: Dict[str, List[KnownHost]] = {}

    def _ssh_dir(self, username: str) -> Path:
        """Return the validated ``<home>/<username>/.ssh`` path.

        [FIX H84] Fail-closed (CWE-22): the username must be a single safe segment
        and ``.ssh`` a contained child, so no traversal can escape the home root.
        """
        return safe_join(safe_child(self.home_path, username), ".ssh")

    def setup_ssh(self, username: str) -> bool:
        ssh_dir = self._ssh_dir(username)
        ssh_dir.mkdir(parents=True, exist_ok=True)
        try:
            ssh_dir.chmod(0o700)
        except (OSError, PermissionError):
            pass
        self.keys[username] = {}
        self.known_hosts[username] = []
        return True

    def generate_key(self, username: str, key_type: str = "rsa",
                     bits: int = 4096, comment: str = "") -> Optional[SSHKey]:
        """Generate a **real** SSH keypair and write ``id_<type>`` / ``.pub``.

        [FIX H87] Previously fabricated a PEM-shaped string from random hex that
        OpenSSH could not use. Now uses ``cryptography`` for a genuine keypair
        (RSA/ed25519/ECDSA), a real OpenSSH public line and a SHA3-512 fingerprint.
        Raises ``RuntimeError`` if the crypto backend is unavailable (fail-closed:
        no fake key is ever written).
        """
        gate.require(CAP_HOME_ADMIN)  # [FIX H85] privileged /home mutation
        if not _CRYPTO_AVAILABLE:
            raise RuntimeError(
                "SSH key generation requires the 'cryptography' package; refusing to "
                "write a non-functional placeholder key."
            )
        private, pub = _new_keypair(key_type, bits)

        pub_comment = comment or f"{username}@UmerOS"
        pub_line = _openssh_public_line(pub, pub_comment)
        priv_pem = _private_pem(private)
        fingerprint = _ssh_public_fingerprint(pub)

        key = SSHKey(name=key_type, private_key=priv_pem, public_key=pub_line,
                     key_type=key_type, bits=_effective_bits(pub), comment=pub_comment)
        key.fingerprint = fingerprint  # type: ignore[attr-defined]

        ssh_dir = self._ssh_dir(username)
        ssh_dir.mkdir(parents=True, exist_ok=True)
        priv_file = ssh_dir / f"id_{key_type}"
        priv_file.write_text(priv_pem, encoding='utf-8')
        try:
            priv_file.chmod(0o600)
        except (OSError, PermissionError):
            pass
        pub_file = ssh_dir / f"id_{key_type}.pub"
        pub_file.write_text(pub_line + "\n", encoding='utf-8')
        try:
            pub_file.chmod(0o644)
        except (OSError, PermissionError):
            pass
        if username not in self.keys:
            self.keys[username] = {}
        self.keys[username][key_type] = key
        return key

    def get_key(self, username: str, key_type: str = "rsa") -> Optional[SSHKey]:
        return self.keys.get(username, {}).get(key_type)

    def list_keys(self, username: str) -> List[str]:
        return list(self.keys.get(username, {}).keys())

    def add_authorized_key(self, username: str, public_key: str) -> bool:
        """Append a validated public key to ``authorized_keys``.

        [FIX H87] the line is validated against the ``ssh-<type> <base64>
        [comment]`` grammar (and the blob is parsed), so arbitrary/foreign text
        cannot grant SSH access. Invalid input raises ``ValueError`` (fail-closed).
        """
        # [FIX H85] appending to authorized_keys grants SSH access
        gate.require(CAP_HOME_ADMIN)
        # [FIX H87] resolve/validate the username (CWE-22) *before* parsing the
        # key, so a traversal attempt fails as PathTraversalError, not a key error.
        ssh_dir = self._ssh_dir(username)
        validated = _validate_public_key(public_key)
        ssh_dir.mkdir(parents=True, exist_ok=True)
        auth_file = ssh_dir / "authorized_keys"
        existing = ""
        if auth_file.exists():
            existing = auth_file.read_text(encoding='utf-8')
        if validated in (line.strip() for line in existing.splitlines()):
            return False
        with open(str(auth_file), 'a', encoding='utf-8') as f:
            f.write(validated + "\n")
        try:
            auth_file.chmod(0o644)
        except (OSError, PermissionError):
            pass
        return True

    def remove_authorized_key(self, username: str, public_key: str) -> bool:
        gate.require(CAP_HOME_ADMIN)  # [FIX H85] privileged /home mutation
        ssh_dir = self._ssh_dir(username)
        auth_file = ssh_dir / "authorized_keys"
        if not auth_file.exists():
            return False
        lines = auth_file.read_text(encoding='utf-8').splitlines()
        new_lines = [l for l in lines if l.strip() != public_key.strip()]
        auth_file.write_text("\n".join(new_lines) + "\n", encoding='utf-8')
        return True

    def list_authorized_keys(self, username: str) -> List[str]:
        ssh_dir = self._ssh_dir(username)
        auth_file = ssh_dir / "authorized_keys"
        if not auth_file.exists():
            return []
        return [l.strip() for l in auth_file.read_text(encoding='utf-8').splitlines()
                if l.strip() and not l.startswith('#')]

    def add_known_host(self, username: str, hostname: str,
                       key_type: str = "rsa", key: str = "") -> bool:
        ssh_dir = self._ssh_dir(username)
        known_file = ssh_dir / "known_hosts"
        entry = f"{hostname} ssh-{key_type} {key}\n"
        with open(str(known_file), 'a', encoding='utf-8') as f:
            f.write(entry)
        self.known_hosts.setdefault(username, []).append(
            KnownHost(hostname=hostname, key_type=key_type, key=key))
        return True

    def remove_known_host(self, username: str, hostname: str) -> bool:
        ssh_dir = self._ssh_dir(username)
        known_file = ssh_dir / "known_hosts"
        if not known_file.exists():
            return False
        lines = known_file.read_text(encoding='utf-8').splitlines()
        new_lines = [l for l in lines if not l.startswith(hostname)]
        known_file.write_text("\n".join(new_lines) + "\n", encoding='utf-8')
        return True

    def list_known_hosts(self, username: str) -> List[str]:
        ssh_dir = self._ssh_dir(username)
        known_file = ssh_dir / "known_hosts"
        if not known_file.exists():
            return []
        return [l.split()[0] for l in known_file.read_text(encoding='utf-8').splitlines()
                if l.strip()]

    def write_config(self, username: str, config: str) -> bool:
        # [FIX H85] ssh config can redirect hosts / weaken auth
        gate.require(CAP_HOME_ADMIN)
        ssh_dir = self._ssh_dir(username)
        ssh_dir.mkdir(parents=True, exist_ok=True)
        config_file = ssh_dir / "config"
        config_file.write_text(config, encoding='utf-8')
        try:
            config_file.chmod(0o600)
        except (OSError, PermissionError):
            pass
        return True

    def get_config(self, username: str) -> str:
        ssh_dir = self._ssh_dir(username)
        config_file = ssh_dir / "config"
        if config_file.exists():
            return config_file.read_text(encoding='utf-8')
        return ""

    def get_ssh_stats(self, username: str) -> Dict:
        return {
            "keys": self.list_keys(username),
            "authorized_keys": len(self.list_authorized_keys(username)),
            "known_hosts": len(self.list_known_hosts(username)),
            "has_config": bool(self.get_config(username)),
        }
