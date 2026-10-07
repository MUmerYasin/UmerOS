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
UmerOS Kernel Signing Module  [TODAY]
============================
Secure Boot and UEFI kernel signing support.

Manages:
- Kernel image signing (UEFI Secure Boot)
- Machine Owner Key (MOK) management
- Unified Kernel Image (UKI) PE/COFF structure
- Signature verification and key enrollment
- sbsigntools / pesign integration

"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("UmerOS.Boot.KernelSigning")


# -------------------------------------------------------------------
# Enums
# -------------------------------------------------------------------

class SecureBootState(Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    SETUP_MODE = "setup_mode"
    LOCKDOWN = "lockdown"
    UNKNOWN = "unknown"


class SignatureStatus(Enum):
    VALID = "valid"
    INVALID = "invalid"
    UNSIGNED = "unsigned"
    #: The image carries a signature, but it could not be checked against a
    #: trust anchor. Distinct from UNSIGNED (nothing to check) and INVALID
    #: (checked and failed). Callers must treat this as **not trusted**.
    UNVERIFIED = "unverified"
    REVOKED = "revoked"
    UNKNOWN = "unknown"


class KeyType(Enum):
    PK = "pk"          # Platform Key
    KEK = "kek"        # Key Exchange Key
    DB = "db"          # Signature Database
    DBX = "dbx"        # Forbidden Signatures Database
    MOK = "mok"        # Machine Owner Key
    CUSTOM = "custom"


class KeyAlgorithm(Enum):
    RSA_2048 = "RSA-2048"
    RSA_4096 = "RSA-4096"
    ECDSA_P256 = "ECDSA-P256"
    ECDSA_P384 = "ECDSA-P384"
    ED25519 = "Ed25519"


class SignatureFormat(Enum):
    GIBBON = "gibbon"      # sbsiglist format
    PE = "pe"              # PE/COFF Authenticode
    HASH = "hash"          # Hash-based


# -------------------------------------------------------------------
# Data classes
# -------------------------------------------------------------------

@dataclass
class SigningKey:
    key_type: KeyType
    algorithm: KeyAlgorithm = KeyAlgorithm.RSA_2048
    subject: str = ""
    issuer: str = ""
    serial: str = ""
    not_before: Optional[float] = None
    not_after: Optional[float] = None
    fingerprint: str = ""
    path: Optional[Path] = None
    enrolled: bool = False

    @property
    def is_expired(self) -> bool:
        if self.not_after is None:
            return False
        return time.time() > self.not_after

    def as_dict(self) -> dict:
        return {
            "key_type": self.key_type.value,
            "algorithm": self.algorithm.value,
            "subject": self.subject,
            "issuer": self.issuer,
            "fingerprint": self.fingerprint,
            "enrolled": self.enrolled,
            "is_expired": self.is_expired,
        }


@dataclass
class Signature:
    format: SignatureFormat = SignatureFormat.PE
    status: SignatureStatus = SignatureStatus.UNKNOWN
    signer: str = ""
    certificate_chain: List[str] = field(default_factory=list)
    timestamp: Optional[float] = None
    hash_algorithm: str = "sha256"
    #: Human-readable explanation of how ``status`` was reached, and of anything
    #: that could NOT be checked. Empty for a clean VALID result.
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "format": self.format.value,
            "status": self.status.value,
            "signer": self.signer,
            "chain_length": len(self.certificate_chain),
            "hash_algorithm": self.hash_algorithm,
            "note": self.note,
        }


@dataclass
class UKISection:
    name: str
    data: bytes = b""
    size: int = 0

    def as_dict(self) -> dict:
        return {"name": self.name, "size": self.size}


@dataclass
class KernelSignatureInfo:
    path: Path
    signature: Signature
    sections: List[UKISection] = field(default_factory=list)
    pe_header_valid: bool = False
    is_uki: bool = False

    def as_dict(self) -> dict:
        return {
            "path": str(self.path),
            "signature": self.signature.as_dict(),
            "section_count": len(self.sections),
            "pe_header_valid": self.pe_header_valid,
            "is_uki": self.is_uki,
        }


@dataclass
class SigningConfig:
    key_path: Optional[Path] = None
    cert_path: Optional[Path] = None
    key_type: KeyType = KeyType.MOK
    algorithm: KeyAlgorithm = KeyAlgorithm.RSA_2048
    hash_algo: str = "sha256"
    pad: bool = True
    output_path: Optional[Path] = None

    def as_dict(self) -> dict:
        return {
            "key_path": str(self.key_path) if self.key_path else None,
            "cert_path": str(self.cert_path) if self.cert_path else None,
            "key_type": self.key_type.value,
            "algorithm": self.algorithm.value,
            "hash_algo": self.hash_algo,
            "pad": self.pad,
        }


# -------------------------------------------------------------------
# PE/COFF / UKI detection
# -------------------------------------------------------------------

# Known UKI section names (per systemd-boot spec)
UKI_SECTION_NAMES = [
    ".osrel", ".cmdline", ".splash", ".initrd",
    ".linux", ".uname", ".sbat", ".pcrsig",
]


class PEParser:
    PE_MAGIC = b"PE\x00\x00"
    MZ_MAGIC = b"MZ"

    @staticmethod
    def is_pe(path: Path) -> bool:
        try:
            with open(path, "rb") as f:
                header = f.read(2)
                if header != PEParser.MZ_MAGIC:
                    return False
                f.seek(0x3C)
                offset_bytes = f.read(4)
                if len(offset_bytes) < 4:
                    return False
                offset = int.from_bytes(offset_bytes, "little")
                f.seek(offset)
                sig = f.read(4)
                return sig == PEParser.PE_MAGIC
        except OSError:
            return False

    @staticmethod
    def detect_uki_sections(path: Path) -> List[UKISection]:
        sections: List[UKISection] = []
        try:
            with open(path, "rb") as f:
                header = f.read(2)
                if header != PEParser.MZ_MAGIC:
                    return sections
                f.seek(0x3C)
                pe_offset = int.from_bytes(f.read(4), "little")
                f.seek(pe_offset + 4)  # skip PE sig
                coff = f.read(20)
                if len(coff) < 20:
                    return sections
                num_sections = int.from_bytes(coff[2:4], "little")
                opt_size = int.from_bytes(coff[16:18], "little")
                section_start = pe_offset + 4 + 20 + opt_size
                for _ in range(num_sections):
                    sec = f.read(40)
                    if len(sec) < 40:
                        break
                    name = sec[:8].rstrip(b"\x00").decode("ascii", errors="replace")
                    vsize = int.from_bytes(sec[8:12], "little")
                    if name in UKI_SECTION_NAMES or name.startswith("."):
                        sections.append(UKISection(name=name, size=vsize))
        except OSError:
            pass
        return sections


# -------------------------------------------------------------------
# Signature verification
# -------------------------------------------------------------------

#: PE optional-header offsets used to find the certificate table.
_OPT_MAGIC_PE32 = 0x10B
_OPT_MAGIC_PE32_PLUS = 0x20B
_SECURITY_DIR_INDEX = 4          # IMAGE_DIRECTORY_ENTRY_SECURITY
_WIN_CERT_TYPE_PKCS_SIGNED_DATA = 0x0002

#: ``cryptography`` (through 48.x) exposes no PKCS#7 *verification* API — only
#: ``load_der_pkcs7_certificates`` for extracting the certificates. Until a
#: verifier exists, an Authenticode-signed image can be reported as UNVERIFIED
#: (signer identified, signature not checked) but never as VALID.
AUTHENTICODE_VERIFICATION_AVAILABLE = False


def _pe_certificate_table(data: bytes) -> Optional[Tuple[int, int]]:
    """Return ``(file_offset, size)`` of the PE certificate table, or None.

    The security data directory is unusual: its ``VirtualAddress`` is a **file
    offset**, not an RVA. Returns ``(0, 0)`` when the entry is present but empty.
    """
    if len(data) < 0x40 or data[:2] != b"MZ":
        return None
    e_lfanew = int.from_bytes(data[0x3C:0x40], "little")
    if e_lfanew + 24 > len(data) or data[e_lfanew:e_lfanew + 4] != b"PE\x00\x00":
        return None

    opt = e_lfanew + 24
    if opt + 2 > len(data):
        return None
    magic = int.from_bytes(data[opt:opt + 2], "little")

    if magic == _OPT_MAGIC_PE32:
        dirs_off = opt + 96
    elif magic == _OPT_MAGIC_PE32_PLUS:
        dirs_off = opt + 112
    else:
        return None

    entry = dirs_off + _SECURITY_DIR_INDEX * 8
    if entry + 8 > len(data):
        return None
    offset = int.from_bytes(data[entry:entry + 4], "little")
    size = int.from_bytes(data[entry + 4:entry + 8], "little")
    return (offset, size)


def _parse_win_certificates(data: bytes, table_offset: int,
                            table_size: int) -> List[bytes]:
    """Return the ``bCertificate`` blobs of the WIN_CERTIFICATE records.

    Each record is ``dwLength`` (u32) + ``wRevision`` (u16) +
    ``wCertificateType`` (u16) + payload, padded to an 8-byte boundary.
    """
    blobs: List[bytes] = []
    end = min(table_offset + table_size, len(data))
    pos = table_offset
    while pos + 8 <= end:
        length = int.from_bytes(data[pos:pos + 4], "little")
        cert_type = int.from_bytes(data[pos + 6:pos + 8], "little")
        if length < 8 or pos + length > end:
            break
        if cert_type == _WIN_CERT_TYPE_PKCS_SIGNED_DATA:
            blobs.append(data[pos + 8:pos + length])
        pos += (length + 7) & ~7          # records are 8-byte aligned
    return blobs


class SignatureVerifier:
    """Verify the Authenticode signature of a PE/COFF image.

    Trust model: a signature is only meaningful relative to a set of enrolled
    keys.  ``verify`` therefore consults ``self.keys`` and reports:

    * ``UNSIGNED``   — not a PE image, or the PE has no certificate table;
    * ``INVALID``    — a certificate table exists but is malformed/unreadable;
    * ``UNVERIFIED`` — the image is signed but the signature was not (or could
      not be) checked against a trust anchor.  Callers must treat this as
      **not trusted**;
    * ``VALID``      — reserved for a signature that was cryptographically
      verified against an enrolled key.

    .. warning::
       ``AUTHENTICODE_VERIFICATION_AVAILABLE`` is currently ``False``: the
       ``cryptography`` package exposes no PKCS#7 verification, so this class
       can identify *who* signed an image and whether they are enrolled, but it
       cannot yet prove the image is unmodified.  It will therefore never return
       ``VALID`` until a verifier backend is added.  Previously this method
       returned ``VALID`` for **any** file starting with ``MZ`` without ever
       consulting ``self.keys``.
    """

    def __init__(self, keys: Optional[List[SigningKey]] = None) -> None:
        self.keys = keys or []

    def verify(self, path: Path) -> Signature:
        sig = Signature()
        if not path.exists():
            sig.status = SignatureStatus.INVALID
            sig.note = "file does not exist"
            return sig
        try:
            data = path.read_bytes()
        except OSError as exc:
            sig.status = SignatureStatus.INVALID
            sig.note = f"unreadable: {exc}"
            return sig

        if data[:2] != b"MZ":
            sig.status = SignatureStatus.UNSIGNED
            sig.note = "not a PE/COFF image"
            return sig

        table = _pe_certificate_table(data)
        if table is None:
            # Distinguish "not a PE image at all" (a DOS/NE executable simply has
            # no Authenticode signature) from "PE header exists but is
            # malformed" (which is corrupt, not merely unsigned).
            pe_off = int.from_bytes(data[0x3C:0x40], "little")
            has_pe_header = (
                pe_off + 4 <= len(data) and data[pe_off:pe_off + 4] == b"PE\x00\x00"
            )
            if not has_pe_header:
                sig.status = SignatureStatus.UNSIGNED
                sig.note = (
                    "MZ image without a PE/COFF header (DOS/NE); "
                    "no Authenticode signature"
                )
            else:
                sig.status = SignatureStatus.INVALID
                sig.note = "malformed PE optional header"
            return sig
        table_offset, table_size = table
        if table_size == 0 or table_offset == 0:
            sig.status = SignatureStatus.UNSIGNED
            sig.note = "PE image has no Authenticode certificate table"
            return sig
        if table_offset + table_size > len(data):
            sig.status = SignatureStatus.INVALID
            sig.note = (
                f"certificate table ({table_size} bytes at {table_offset}) "
                f"lies outside the file"
            )
            return sig

        blobs = _parse_win_certificates(data, table_offset, table_size)
        if not blobs:
            sig.status = SignatureStatus.INVALID
            sig.note = "no PKCS#7 WIN_CERTIFICATE record in the certificate table"
            return sig

        subjects, fingerprints = self._certificates_from(blobs)
        if not subjects:
            sig.status = SignatureStatus.UNVERIFIED
            sig.note = (
                "certificate table present but no X.509 certificate could be "
                "extracted (PKCS#7 is malformed, or 'cryptography' is not "
                "installed); image NOT verified"
            )
            return sig

        sig.certificate_chain = subjects
        sig.signer = subjects[0]

        if not self.keys:
            sig.status = SignatureStatus.UNVERIFIED
            sig.note = "no trust anchors enrolled; signature not evaluated"
            return sig

        if not any(k.enrolled for k in self.keys):
            sig.status = SignatureStatus.UNVERIFIED
            sig.note = "no *enrolled* trust anchors; signature not evaluated"
            return sig

        trusted = self._find_trusted_key(fingerprints)
        if trusted is None:
            sig.status = SignatureStatus.UNVERIFIED
            sig.note = (
                f"signer '{subjects[0]}' is not in the trust store "
                f"({len(self.keys)} key(s) configured, 0 matched)"
            )
            return sig

        sig.signer = trusted.subject or subjects[0]
        if not AUTHENTICODE_VERIFICATION_AVAILABLE:
            sig.status = SignatureStatus.UNVERIFIED
            sig.note = (
                f"signer '{sig.signer}' is enrolled, but Authenticode "
                f"signature verification is unavailable in this build "
                f"(cryptography exposes no PKCS#7 verify); image NOT proven "
                f"unmodified"
            )
            return sig

        # Reached only once a real verification backend exists.
        sig.status = SignatureStatus.INVALID  # pragma: no cover
        sig.note = "verification backend returned no result"  # pragma: no cover
        return sig  # pragma: no cover

    # -- helpers -------------------------------------------------------

    @staticmethod
    def _certificates_from(blobs: List[bytes]) -> Tuple[List[str], List[str]]:
        """Return ``(subjects, sha256_fingerprints)`` for the PKCS#7 blobs."""
        subjects: List[str] = []
        fingerprints: List[str] = []
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.serialization import pkcs7
        except ImportError:
            return subjects, fingerprints

        for blob in blobs:
            try:
                certs = pkcs7.load_der_pkcs7_certificates(blob)
            except Exception:  # noqa: BLE001 - malformed DER must not crash
                continue
            for cert in certs:
                try:
                    subjects.append(cert.subject.rfc4514_string())
                    fingerprints.append(
                        cert.fingerprint(hashes.SHA256()).hex()
                    )
                except Exception:  # noqa: BLE001
                    continue
        return subjects, fingerprints

    def _find_trusted_key(self, fingerprints: List[str]) -> Optional[SigningKey]:
        """Return the enrolled key matching any of ``fingerprints``."""
        wanted = {f.lower().replace(":", "") for f in fingerprints if f}
        for key in self.keys:
            if not key.enrolled:
                continue
            have = (key.fingerprint or "").lower().replace(":", "")
            if have and have in wanted:
                return key
        return None


# -------------------------------------------------------------------
# MOK / Key enrollment
# -------------------------------------------------------------------

class MOKManager:
    def __init__(self, efi_dir: Optional[Path] = None) -> None:
        self.efi_dir = efi_dir or Path("/sys/firmware/efi")
        self._keys: List[SigningKey] = []

    def list_keys(self) -> List[SigningKey]:
        return list(self._keys)

    def add_key(self, key: SigningKey) -> None:
        self._keys.append(key)

    def remove_key(self, fingerprint: str) -> bool:
        before = len(self._keys)
        self._keys = [k for k in self._keys if k.fingerprint != fingerprint]
        return len(self._keys) < before

    def get_enrolled_keys(self) -> List[SigningKey]:
        return [k for k in self._keys if k.enrolled]

    def generate_enrollment_command(self, key: SigningKey) -> str:
        if key.key_type == KeyType.MOK:
            return f"mokutil --import {key.path}"
        return f"efi-update-var -e -g {key.subject} -f {key.path} {key.key_type.value}"


# -------------------------------------------------------------------
# Signing command builder
# -------------------------------------------------------------------

class SigningCommandBuilder:
    def __init__(self, config: Optional[SigningConfig] = None) -> None:
        self.config = config or SigningConfig()

    def build_sign_command(self, kernel_path: Path) -> str:
        key = self.config.key_path or Path("/etc/ssl/keys/kernel.key")
        cert = self.config.cert_path or Path("/etc/ssl/certs/kernel.pem")
        output = self.config.output_path or kernel_path.with_suffix(".signed")
        return (
            f"sb sign --key {key} --cert {cert} "
            f"--output {output} {kernel_path}"
        )

    def build_verify_command(self, path: Path) -> str:
        return f"sb verify --cert {self.config.cert_path} {path}"

    def build_enroll_command(self, key_path: Path) -> str:
        if self.config.key_type == KeyType.MOK:
            return f"mokutil --import {key_path}"
        return f"mokutil --import-hash {key_path}"

    def build_uki_command(self, kernel: Path, initrd: Path, cmdline: str, output: Path) -> str:
        return (
            f"objcopy"
            f" --add-section .osrel=/etc/os-release --change-section .osrel .data=.rodata"
            f" --add-section .cmdline=. --change-section .cmdline .data=.rodata"
            f" --add-section .linux={kernel} --change-section .linux .data=.rodata"
            f" --add-section .initrd={initrd} --change-section .initrd .data=.rodata"
            f" /usr/lib/systemd/boot/efi/linuxx64.efi.stub {output}"
        )


# -------------------------------------------------------------------
# Secure boot state
# -------------------------------------------------------------------

class SecureBootManager:
    def __init__(self, efi_dir: Optional[Path] = None) -> None:
        self.efi_dir = efi_dir or Path("/sys/firmware/efi")
        self.mok = MOKManager(efi_dir)
        self.verifier = SignatureVerifier()

    def get_state(self) -> SecureBootState:
        var_dir = self.efi_dir / "efivars"
        sb_var = var_dir / "SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c"
        if not sb_var.exists():
            return SecureBootState.UNKNOWN
        try:
            data = sb_var.read_bytes()
            if len(data) >= 5:
                return SecureBootState.ENABLED if data[4] == 1 else SecureBootState.DISABLED
        except OSError:
            pass
        return SecureBootState.UNKNOWN

    def get_db_keys(self) -> List[SigningKey]:
        return [k for k in self.mok.list_keys() if k.key_type == KeyType.DB]

    def get_kek_keys(self) -> List[SigningKey]:
        return [k for k in self.mok.list_keys() if k.key_type == KeyType.KEK]

    def get_pk(self) -> Optional[SigningKey]:
        keys = [k for k in self.mok.list_keys() if k.key_type == KeyType.PK]
        return keys[0] if keys else None

    def verify_kernel(self, path: Path) -> KernelSignatureInfo:
        sig = self.verifier.verify(path)
        sections = PEParser.detect_uki_sections(path)
        is_pe = PEParser.is_pe(path)
        return KernelSignatureInfo(
            path=path, signature=sig, sections=sections,
            pe_header_valid=is_pe, is_uki=len(sections) > 2,
        )

    def get_system_info(self) -> Dict[str, str]:
        return {
            "secure_boot": self.get_state().value,
            "mok_keys": str(len(self.mok.list_keys())),
            "enrolled_keys": str(len(self.mok.get_enrolled_keys())),
        }


def _selftest() -> bool:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmppath = Path(tmp)

        # PEParser: non-PE file
        fake = tmppath / "vmlinuz"
        fake.write_bytes(b"not a PE file at all")
        if PEParser.is_pe(fake):
            return False
        if PEParser.detect_uki_sections(fake):
            return False

        # SignatureVerifier: unsigned file
        verifier = SignatureVerifier()
        sig = verifier.verify(fake)
        if sig.status != SignatureStatus.UNSIGNED:
            return False

        # SigningConfig round-trip
        cfg = SigningConfig(
            key_path=tmppath / "key.pem",
            cert_path=tmppath / "cert.pem",
            key_type=KeyType.MOK,
        )
        d = cfg.as_dict()
        if d["key_type"] != "mok":
            return False

        # SigningCommandBuilder
        builder = SigningCommandBuilder(cfg)
        cmd = builder.build_sign_command(tmppath / "vmlinuz")
        if "sb sign" not in cmd:
            return False

        # MOKManager
        mok = MOKManager()
        k = SigningKey(key_type=KeyType.MOK, subject="test", fingerprint="abc123")
        mok.add_key(k)
        if len(mok.list_keys()) != 1:
            return False
        k.enrolled = True
        if len(mok.get_enrolled_keys()) != 1:
            return False
        if not mok.remove_key("abc123"):
            return False
        if len(mok.list_keys()) != 0:
            return False

        # SecureBootManager (no EFI vars)
        sb = SecureBootManager(efi_dir=tmppath)
        if sb.get_state() != SecureBootState.UNKNOWN:
            return False
        info = sb.get_system_info()
        if "secure_boot" not in info:
            return False

        # Verify kernel (non-PE)
        ksi = sb.verify_kernel(fake)
        if ksi.is_uki:
            return False

        # Signature as_dict
        sd = sig.as_dict()
        if "status" not in sd:
            return False

        # Key as_dict
        kd = k.as_dict()
        if "key_type" not in kd:
            return False

    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("kernel_signing selftest:", "OK" if _selftest() else "FAIL")
