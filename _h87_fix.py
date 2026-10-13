# [H87] Real SSH keys + validated authorized_keys + SHA3-512 fingerprints.
# Two-phase: verify all anchors/counts first, then apply.
from pathlib import Path

ROOT = Path(__file__).resolve().parent

IMPORT_OLD = "from dataclasses import dataclass\nimport hashlib\nimport secrets\n"
IMPORT_NEW = (
    "from dataclasses import dataclass\n"
    "import base64\n"
    "import binascii\n"
    "import hashlib\n"
    "import logging\n"
    "import re\n"
    "import secrets\n"
    "import struct\n"
)

CRYPTO_IMPORT = '''# [FIX H87] Real SSH key generation backend (``cryptography``; a declared dep).
try:
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat, PublicFormat,
    )
    _CRYPTO_AVAILABLE = True
except Exception:  # pragma: no cover - cryptography is a declared dependency
    _CRYPTO_AVAILABLE = False

'''

H87_BLOCK = '''# [FIX H87] SSH key integrity + ``authorized_keys`` validation.
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
    r"^(?:[^\\s]+\\s+)?(ssh-rsa|ssh-ed25519|ssh-dss|"
    r"ecdsa-sha2-nistp(?:256|384|521))\\s+([A-Za-z0-9+/]+={0,3})(?:\\s+(.*))?$"
)


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
    """Encode an int as an SSH ``mpint`` (two's-complement, big-endian)."""
    if value == 0:
        return b""
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    if raw[0] & 0x80:
        raw = b"\\x00" + raw
    return raw


def _parse_public_key_blob(blob: bytes) -> str:
    """Return the embedded key-type string if ``blob`` is a valid SSH record."""
    if len(blob) < 4:
        raise ValueError("public key blob too short")
    type_bytes, offset = _read_ssh_string(blob, 0)
    if offset >= len(blob):
        raise ValueError("public key record has no key material")
    return type_bytes.decode("ascii", "strict")


def _validate_public_key(public_key: str) -> str:
    """[FIX H87] Validate a single ``authorized_keys`` line; return it stripped."""
    if not public_key or "\\n" in public_key or "\\r" in public_key:
        raise ValueError("authorized key must be a single non-empty line")
    match = _AUTHORIZED_KEY_RE.match(public_key.strip())
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
    return public_key.strip()


def _public_key_blob(pub) -> bytes:
    """Serialise a ``cryptography`` public key to an SSH wire blob."""
    if isinstance(pub, rsa.RSAPublicKey):
        numbers = pub.public_numbers()
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


def _private_pem(private) -> str:
    """Serialise a private key as unencrypted PKCS#8 PEM for ``id_<type>``."""
    return private.private_bytes(
        Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
    ).decode("ascii")'''

GENERATE_OLD = '''    def generate_key(self, username: str, key_type: str = "rsa",
                     bits: int = 4096, comment: str = "") -> Optional[SSHKey]:
        gate.require(CAP_HOME_ADMIN)  # [FIX H85] privileged /home mutation
        ssh_dir = self._ssh_dir(username)
        ssh_dir.mkdir(parents=True, exist_ok=True)
        pseudo_random = secrets.token_hex(bits // 8)
        fingerprint = hashlib.sha256(pseudo_random.encode()).hexdigest()
        priv = (
            f"-----BEGIN {key_type.upper()} PRIVATE KEY-----\\n"
            f"Proc-Type: 4,ENCRYPTED\\n"
            f"DEK-Info: AES-256-CBC,{fingerprint[:32]}\\n\\n"
            f"{pseudo_random}\\n"
            f"-----END {key_type.upper()} PRIVATE KEY-----"
        )
        pub_comment = comment or f"{username}@UmerOS"
        pub = f"ssh-{key_type} {fingerprint[:96]} {pub_comment}"
        key = SSHKey(name=key_type, private_key=priv, public_key=pub,
                     key_type=key_type, bits=bits, comment=pub_comment)
        priv_file = ssh_dir / f"id_{key_type}"
        priv_file.write_text(priv, encoding='utf-8')
        try:
            priv_file.chmod(0o600)
        except (OSError, PermissionError):
            pass
        pub_file = ssh_dir / f"id_{key_type}.pub"
        pub_file.write_text(pub, encoding='utf-8')
        try:
            pub_file.chmod(0o644)
        except (OSError, PermissionError):
            pass
        if username not in self.keys:
            self.keys[username] = {}
        self.keys[username][key_type] = key
        return key
'''

GENERATE_NEW = '''    def generate_key(self, username: str, key_type: str = "rsa",
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
                     key_type=key_type, bits=bits, comment=pub_comment)
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
        pub_file.write_text(pub_line + "\\n", encoding='utf-8')
        try:
            pub_file.chmod(0o644)
        except (OSError, PermissionError):
            pass
        if username not in self.keys:
            self.keys[username] = {}
        self.keys[username][key_type] = key
        return key
'''

ADD_OLD = '''    def add_authorized_key(self, username: str, public_key: str) -> bool:
        # [FIX H85] appending to authorized_keys grants SSH access
        gate.require(CAP_HOME_ADMIN)
        ssh_dir = self._ssh_dir(username)
        auth_file = ssh_dir / "authorized_keys"
        existing = ""
        if auth_file.exists():
            existing = auth_file.read_text(encoding='utf-8')
        if public_key.strip() in existing:
            return False
        with open(str(auth_file), 'a', encoding='utf-8') as f:
            f.write(public_key.rstrip() + "\\n")
'''

ADD_NEW = '''    def add_authorized_key(self, username: str, public_key: str) -> bool:
        """Append a validated public key to ``authorized_keys``.

        [FIX H87] the line is validated against the ``ssh-<type> <base64>
        [comment]`` grammar (and the blob is parsed), so arbitrary/foreign text
        cannot grant SSH access. Invalid input raises ``ValueError`` (fail-closed).
        """
        # [FIX H85] appending to authorized_keys grants SSH access
        gate.require(CAP_HOME_ADMIN)
        validated = _validate_public_key(public_key)
        ssh_dir = self._ssh_dir(username)
        ssh_dir.mkdir(parents=True, exist_ok=True)
        auth_file = ssh_dir / "authorized_keys"
        existing = ""
        if auth_file.exists():
            existing = auth_file.read_text(encoding='utf-8')
        if validated in (line.strip() for line in existing.splitlines()):
            return False
        with open(str(auth_file), 'a', encoding='utf-8') as f:
            f.write(validated + "\\n")
'''

PLAN = [
    ("home/home_ssh.py", [
        (IMPORT_OLD, IMPORT_NEW, 1),
        (
            "    from core.capability_gate import gate, CAP_HOME_ADMIN\n\n\n@dataclass\nclass SSHKey:",
            "    from core.capability_gate import gate, CAP_HOME_ADMIN\n\n" + CRYPTO_IMPORT + "\n" + H87_BLOCK + "\n\n\n@dataclass\nclass SSHKey:",
            1,
        ),
        (GENERATE_OLD, GENERATE_NEW, 1),
        (ADD_OLD, ADD_NEW, 1),
        (
            "UmerOS ~/.ssh/ Key Manager\nManages SSH keys:",
            "UmerOS ~/.ssh/ Key Manager [EXPERIMENTAL]\nManages SSH keys:",
            1,
        ),
    ]),
]


def verify():
    for rel, subs in PLAN:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for old, new, cnt in subs:
            if old == new:
                continue  # no-op anchor guard
            got = text.count(old)
            if got != cnt:
                raise SystemExit(f"VERIFY FAIL {rel}: expected {cnt} got {got} for {old[:70]!r}")
    print("verify OK")


def apply():
    for rel, subs in PLAN:
        p = ROOT / rel
        text = p.read_text(encoding="utf-8")
        for old, new, cnt in subs:
            if old == new:
                continue
            text = text.replace(old, new, cnt)
        p.write_text(text, encoding="utf-8")
        print("applied", rel)


if __name__ == "__main__":
    verify()
    apply()
    print("DONE")
