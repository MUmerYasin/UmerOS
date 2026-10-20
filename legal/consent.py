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
UmerOS Legal & Compliance — Cryptographic Consent Gate & Audit Ledger
=====================================================================

Implements the mandatory legal liability waiver consent gate, user verification,
and a tamper-evident consent ledger required by the UmerOS Master Engineering
Blueprint.

Integrity model:
----------------
Each consent record is signed with HMAC-SHA256 using a 256-bit secret kept in a
sidecar key file next to the ledger (mode 0600; override with the
UMEROS_CONSENT_KEY env var).  load_ledger verifies every record and rejects any
whose signature does not match, so a forged or edited ledger entry is never
trusted.  (A plain hash of public values is NOT a signature — an attacker can
reproduce it.)

Privacy model :
---------------------
Consent is attributed to a *resolved* OS identity (``getpass.getuser()`` or an
explicit ``user_name``) — never silently to a default ``admin`` account.  The
ledger is encrypted at rest with AES-256-GCM (key derived via HKDF-SHA256 from
the ledger secret), so the recorded PII (user / host / machine id) is not
readable in the file.  ``forget_consent`` and ``erase_all`` provide the
data-erasure (right to be forgotten) hooks.

Legal Mandate:
--------------
"Every installer flow and high-risk operation MUST display a legal liability
waiver and require explicit user consent ('I AGREE') before proceeding."

Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import getpass
import hashlib
import hmac
import json
import logging
import os
import platform
import socket
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .disclaimer import DisclaimerNotice, DisclaimerRegistry

log = logging.getLogger("UmerOS.Legal.Consent")

#: Explicit config override for the ledger location.
_LEDGER_ENV_VAR = "UMEROS_LEDGER_PATH"


def default_ledger_path() -> Path:
    """Resolve the consent-ledger location for the host OS.

    Never returns a CWD-relative path.  Precedence:

    * ``UMEROS_LEDGER_PATH`` env var (explicit configuration override);
    * POSIX — ``$XDG_STATE_HOME/umeros/consent_ledger.json`` when set, else
      ``/var/lib/umeros/consent_ledger.json``;
    * Windows — ``%PROGRAMDATA%\\UmerOS\\consent_ledger.json`` (falling back to
      ``%ALLUSERSPROFILE%`` / ``%LOCALAPPDATA%`` / ``%APPDATA%``, then
      ``~/.umeros/``).
    """
    override = os.environ.get(_LEDGER_ENV_VAR)
    if override:
        return Path(override)

    if os.name == "nt":
        for var in ("PROGRAMDATA", "ALLUSERSPROFILE", "LOCALAPPDATA", "APPDATA"):
            base = os.environ.get(var)
            if base:
                return Path(base) / "UmerOS" / "consent_ledger.json"
        return Path.home() / ".umeros" / "consent_ledger.json"

    xdg_state = os.environ.get("XDG_STATE_HOME")
    if xdg_state:
        return Path(xdg_state) / "umeros" / "consent_ledger.json"
    return Path("/var/lib/umeros/consent_ledger.json")


DEFAULT_LEDGER_PATH = default_ledger_path()

# HMAC-SHA256 secret used to sign consent records.
_KEY_ENV_VAR = "UMEROS_CONSENT_KEY"
_KEY_BYTES = 32  # 256-bit key


@dataclass
class ConsentRecord:
    """HMAC-SHA256-signed (tamper-evident) record of user legal consent."""
    disclaimer_key: str
    user_name: str
    hostname: str
    machine_id: str
    agreed_at: float
    disclaimer_version: str
    consent_token: str
    status: str = "GRANTED"  # GRANTED, REVOKED, EXPIRED
    identity_verified: bool = False  # True when the user identity was resolved

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConsentRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def get_machine_fingerprint() -> str:
    """Generates a stable hardware / system fingerprint string."""
    raw = f"{platform.node()}:{platform.machine()}:{platform.processor()}:{platform.system()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _key_path_for(ledger_path: Path) -> Path:
    """Sidecar file holding the ledger's HMAC secret."""
    return ledger_path.with_name(ledger_path.name + ".key")


def load_or_create_ledger_key(ledger_path: Path) -> bytes:
    """Return the ledger's 256-bit HMAC key, creating it on first use.

    Precedence: ``UMEROS_CONSENT_KEY`` env var (hex) > sidecar
    ``<ledger>.key`` file > a freshly generated key written to that sidecar
    with mode ``0600`` (best effort).
    """
    env = os.environ.get(_KEY_ENV_VAR)
    if env:
        try:
            key = bytes.fromhex(env.strip())
        except ValueError as exc:
            raise ConsentGateError(f"{_KEY_ENV_VAR} must be hex-encoded") from exc
        if len(key) < _KEY_BYTES:
            raise ConsentGateError(f"{_KEY_ENV_VAR} must be >= {_KEY_BYTES} bytes")
        return key

    key_file = _key_path_for(ledger_path)
    if key_file.exists():
        try:
            key = bytes.fromhex(key_file.read_text(encoding="ascii").strip())
        except (ValueError, UnicodeDecodeError, OSError) as exc:
            raise ConsentGateError(f"Corrupt consent key file: {key_file}") from exc
        if len(key) < _KEY_BYTES:
            raise ConsentGateError(f"Consent key file too short: {key_file}")
        return key

    key = os.urandom(_KEY_BYTES)
    try:
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text(key.hex(), encoding="ascii")
        os.chmod(key_file, 0o600)  # best-effort (no-op on some platforms)
    except OSError as exc:
        raise ConsentGateError(f"Could not create consent key file {key_file}: {exc}") from exc
    log.info("Created consent-ledger HMAC key at %s", key_file)
    return key


def _canonical_payload(record: Dict[str, Any]) -> bytes:
    """Deterministic encoding of the signed fields (the token itself excluded)."""
    signed = {k: v for k, v in record.items() if k != "consent_token"}
    return json.dumps(signed, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sign_record(record: Dict[str, Any], key: bytes) -> str:
    """Return the HMAC-SHA256 hex signature over ``record`` (token excluded)."""
    return hmac.new(key, _canonical_payload(record), hashlib.sha256).hexdigest()


def verify_record(record: Dict[str, Any], key: bytes) -> bool:
    """Constant-time check of ``record``'s HMAC signature."""
    token = record.get("consent_token")
    if not isinstance(token, str) or not token:
        return False
    return hmac.compare_digest(token, sign_record(record, key))


# --- At-rest encryption + identity resolution ------------------------

_LEDGER_MAGIC = "UMEROS-CONSENT-V2"

try:  # AES-256-GCM at-rest encryption (HMAC still protects each record).
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF as _HKDF
    from cryptography.hazmat.primitives import hashes as _hashes
    _HAVE_AESGCM = True
except ImportError:  # pragma: no cover - cryptography is a hard dependency in CI
    _AESGCM = _HKDF = _hashes = None
    _HAVE_AESGCM = False


def _derive_cipher_key(mac_key: bytes) -> bytes:
    """Derive a distinct 256-bit AES key from the ledger MAC key (HKDF-SHA256)."""
    if not _HAVE_AESGCM:
        return mac_key[:32]
    return _HKDF(
        algorithm=_hashes.SHA256(),
        length=32,
        salt=None,
        info=b"umeros-consent-ledger-at-rest",
    ).derive(mac_key)


def encode_ledger(records: Dict[str, Any], key: bytes) -> bytes:
    """Serialise ``records`` to the encrypted on-disk envelope.

    AES-256-GCM with a fresh 96-bit nonce; the magic string is bound as
    associated data so a foreign blob cannot be substituted.  Falls back to
    plaintext JSON (still HMAC-protected per record) when ``cryptography`` is
    unavailable.
    """
    payload = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if not _HAVE_AESGCM:
        log.warning("cryptography unavailable — consent ledger stored unencrypted")
        return payload
    nonce = os.urandom(12)
    ct = _AESGCM(_derive_cipher_key(key)).encrypt(
        nonce, payload, _LEDGER_MAGIC.encode("ascii"))
    return json.dumps(
        {
            "magic": _LEDGER_MAGIC,
            "alg": "AES-256-GCM",
            "nonce": nonce.hex(),
            "ct": ct.hex(),
        },
        sort_keys=True,
    ).encode("utf-8")


def decode_ledger(blob: bytes, key: bytes) -> Dict[str, Any]:
    """Decode a ledger blob written by :func:`encode_ledger` .

    Also accepts a legacy *plaintext* JSON object for migration; the
    per-record HMAC is still verified by the caller.  Raises
    :class:`ConsentGateError` if an encrypted envelope fails authentication.
    """
    try:
        data = json.loads(blob.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ConsentGateError(f"Consent ledger is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ConsentGateError("Consent ledger must be a JSON object")
    if data.get("magic") != _LEDGER_MAGIC:
        # Legacy plaintext ledger (pre-H134); per-record HMAC still applies.
        return data
    if not _HAVE_AESGCM:
        raise ConsentGateError(
            "Encrypted consent ledger requires the 'cryptography' package")
    try:
        nonce = bytes.fromhex(data["nonce"])
        ct = bytes.fromhex(data["ct"])
        plain = _AESGCM(_derive_cipher_key(key)).decrypt(
            nonce, ct, _LEDGER_MAGIC.encode("ascii"))
    except Exception as exc:  # InvalidTag, KeyError, ValueError, ...
        raise ConsentGateError(f"Consent ledger failed authentication: {exc}") from exc
    try:
        inner = json.loads(plain.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ConsentGateError(f"Consent ledger payload is corrupt: {exc}") from exc
    if not isinstance(inner, dict):
        raise ConsentGateError("Consent ledger payload must be a JSON object")
    return inner


def _resolve_identity(explicit: Optional[str]) -> tuple[str, bool]:
    """Resolve the consenting user's identity.

    Returns ``(name, verified)``.  ``verified`` is True when the name comes from
    an explicit argument or a real OS identity lookup.  The privileged-looking
    literal default is never fabricated: when nothing can be resolved the name
    is ``"unauthenticated"`` and ``verified`` is False.
    """
    if explicit and explicit.strip():
        return explicit.strip(), True
    try:
        name = getpass.getuser()
        if name and name.strip():
            return name.strip(), True
    except Exception:  # getpass raises when no user can be determined
        pass
    for var in ("USERNAME", "USER", "LOGNAME"):
        val = os.environ.get(var)
        if val and val.strip():
            return val.strip(), True
    return "unauthenticated", False


class ConsentGateError(Exception):
    """Raised when an operation is attempted without valid user consent."""
    pass


class ConsentManager:
    """Manages user legal consent, verification, and audit logging."""

    def __init__(self, ledger_path: Optional[Path | str] = None) -> None:
        self.ledger_path = Path(ledger_path or DEFAULT_LEDGER_PATH).resolve()
        self._ledger: Dict[str, ConsentRecord] = {}
        self._key: Optional[bytes] = None
        self.load_ledger()

    def _key_material(self) -> bytes:
        """Lazily load (or create) the ledger's HMAC key."""
        if self._key is None:
            self._key = load_or_create_ledger_key(self.ledger_path)
        return self._key

    def load_ledger(self) -> None:
        """Loads (and decrypts) consent records from disk.

        Fail-CLOSED: a record whose HMAC signature does not verify — or an
        envelope that fails AES-GCM authentication — is never trusted.
        """
        if not self.ledger_path.exists():
            return
        try:
            blob = self.ledger_path.read_bytes()
            if not blob.strip():
                return
            key = self._key_material()
            data = decode_ledger(blob, key)
            rejected = 0
            for k, rec in data.items():
                if not isinstance(rec, dict):
                    continue
                if not verify_record(rec, key):
                    # Fail CLOSED: an unsigned / forged / edited record is
                    # never trusted.
                    rejected += 1
                    log.warning("Rejecting consent record %r — HMAC signature invalid", k)
                    continue
                self._ledger[k] = ConsentRecord.from_dict(rec)
            if rejected:
                log.warning("Rejected %d unverifiable consent record(s) in %s",
                            rejected, self.ledger_path)
        except ConsentGateError as e:
            log.warning("Could not read consent ledger %s: %s", self.ledger_path, e)
        except Exception as e:
            log.warning(f"Could not load consent ledger from {self.ledger_path}: {e}")

    def save_ledger(self) -> None:
        """Encrypts and saves consent records to disk (AES-256-GCM)."""
        try:
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            data = {k: rec.to_dict() for k, rec in self._ledger.items()}
            self.ledger_path.write_bytes(encode_ledger(data, self._key_material()))
        except Exception as e:
            log.error(f"Failed to write consent ledger to {self.ledger_path}: {e}")

    def has_consented(self, disclaimer_key: str = "general", version: Optional[str] = None) -> bool:
        """Checks whether valid consent exists for the specified disclaimer."""
        rec = self._ledger.get(disclaimer_key)
        if not rec or rec.status != "GRANTED":
            return False

        if version and rec.disclaimer_version != version:
            return False  # Requires re-consent on version change

        return True

    def grant_consent(
        self,
        disclaimer_key: str = "general",
        user_response: str = "I AGREE",
        user_name: Optional[str] = None,
        require_identity: bool = True,
    ) -> ConsentRecord:
        """
        Grants explicit legal consent and signs the audit record.

        Consent is attributed to a resolved OS identity.  When no
        identity can be established and ``require_identity`` is True (the
        default), a :class:`ConsentGateError` is raised rather than silently
        recording a default privileged account name.
        """
        if user_response.strip().upper() != "I AGREE":
            raise ValueError(f"Explicit consent rejected: Expected 'I AGREE', got '{user_response}'")

        notice = DisclaimerRegistry.get_notice(disclaimer_key)
        now = time.time()
        username, identity_verified = _resolve_identity(user_name)
        if not identity_verified and require_identity:
            raise ConsentGateError(
                "Refusing to record consent without a verifiable user identity. "
                "Pass user_name=... or ensure an OS identity is available "
                "(getpass.getuser())."
            )
        host = socket.gethostname()
        mach_id = get_machine_fingerprint()

        record = ConsentRecord(
            disclaimer_key=disclaimer_key,
            user_name=username,
            hostname=host,
            machine_id=mach_id,
            agreed_at=now,
            disclaimer_version=notice.version,
            consent_token="",
            status="GRANTED",
            identity_verified=identity_verified,
        )
        # Sign the record with the ledger's HMAC key.  A plain hash of
        # public values is reproducible by anyone — it is not a signature.
        record.consent_token = sign_record(record.to_dict(), self._key_material())

        self._ledger[disclaimer_key] = record
        self.save_ledger()
        return record

    def revoke_consent(self, disclaimer_key: str = "general") -> bool:
        """Revokes previously granted consent (re-signs the record)."""
        rec = self._ledger.get(disclaimer_key)
        if rec is None:
            return False
        rec.status = "REVOKED"
        rec.consent_token = sign_record(rec.to_dict(), self._key_material())
        self.save_ledger()
        return True

    def require_consent_interactive(
        self,
        disclaimer_key: str = "installer",
        dry_run: bool = False,
        allow_non_interactive: bool = False,
    ) -> bool:
        """
        Interactive legal-consent gate (FAIL-CLOSED).

        Consent is granted ONLY when one of:
          * the user is on a TTY and explicitly types "I AGREE", or
          * `allow_non_interactive=True` is passed by a caller that has already
            obtained consent out-of-band (e.g. a CI job given `--i-agree`).

        It NEVER auto-grants in dry-run or non-TTY environments — that would
        bypass the mandatory liability-waiver gate (same fail-open family as
        H29/H99). The default `allow_non_interactive=False` keeps it closed.
        """
        notice = DisclaimerRegistry.get_notice(disclaimer_key)

        if dry_run:
            # Dry-run simulates the flow but MUST NOT record legal consent.
            print("\n" + "=" * 65)
            print(f"       {notice.title.upper()} (DRY-RUN — no consent recorded)")
            print("=" * 65)
            print(notice.full_text)
            print("=" * 65)
            print("[CONSENT] Dry-run mode: NO consent was granted. Re-run without --dry-run to grant.\n")
            return False

        if sys.stdin.isatty():
            print("\n" + "=" * 65)
            print(f"       {notice.title.upper()}")
            print("=" * 65)
            print(notice.full_text)
            print("=" * 65 + "\n")
            resp = input("Type 'I AGREE' to accept and proceed: ").strip()
            if resp.upper() == "I AGREE":
                self.grant_consent(disclaimer_key=disclaimer_key, user_response="I AGREE")
                print("✓ Legal consent recorded successfully.\n")
                return True
            print("✗ Consent declined. Operation aborted.\n")
            return False

        # Non-interactive / headless: fail CLOSED. Auto-granting the
        # liability waiver in automation is the exact bypass this gate exists to
        # prevent. Require explicit opt-in, otherwise abort with a clear error.
        if not allow_non_interactive:
            raise ConsentGateError(
                f"Refusing to grant consent for '{disclaimer_key}' non-interactively. "
                "A TTY is required to capture an explicit 'I AGREE', or pass "
                "allow_non_interactive=True when consent was obtained out-of-band."
            )
        self.grant_consent(disclaimer_key=disclaimer_key, user_response="I AGREE")
        return True

    def list_consents(self) -> Dict[str, ConsentRecord]:
        """Returns all recorded consents."""
        return dict(self._ledger)

    def verify_ledger(self) -> tuple[int, int]:
        """Re-verify every in-memory record's HMAC signature.

        Returns:
            ``(valid, invalid)`` counts.
        """
        key = self._key_material()
        valid = invalid = 0
        for rec in self._ledger.values():
            if verify_record(rec.to_dict(), key):
                valid += 1
            else:
                invalid += 1
        return valid, invalid

    # ------------------------------------------------------------------
    # Data-erasure hooks (right to be forgotten)
    # ------------------------------------------------------------------
    def forget_consent(self, disclaimer_key: str = "general") -> bool:
        """Erase a single recorded consent (and its PII) from the ledger."""
        if self._ledger.pop(disclaimer_key, None) is None:
            return False
        self.save_ledger()
        return True

    def erase_all(self, delete_file: bool = False) -> int:
        """Erase every recorded consent; return how many were removed.

        With ``delete_file=True`` the ledger file is unlinked as well.  The HMAC
        key sidecar is left in place so other ledgers that share it (e.g. via the
        env var) keep working.
        """
        removed = len(self._ledger)
        self._ledger.clear()
        if delete_file:
            try:
                self.ledger_path.unlink(missing_ok=True)
            except OSError as exc:  # pragma: no cover
                log.warning("Could not delete consent ledger %s: %s", self.ledger_path, exc)
        else:
            self.save_ledger()
        return removed
