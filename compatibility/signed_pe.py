"""
Umer OS /compatibility/signed_pe — Authenticode / WIN_CERTIFICATE reader
=======================================================================

A practical Win32-compatible surface for inspecting **embedded
Authenticode signatures** of PE binaries, without performing the
full PKCS#7 / X.509 chain validation (which requires a crypto
library and a trusted root store).

The module exposes the *Win32 contract*:

* the WIN_CERTIFICATE structure that lives at the file offset
  pointed to by data directory index ``4``
  (``IMAGE_DIRECTORY_ENTRY_SECURITY``)
* a quick extractor of the *outer* PKCS#7 SignedData envelope, so
  callers can display ``"Signed by Microsoft Corporation"`` without
  recomputing the hash
* helpers for the most common install-time questions: *has this
  binary been signed?*, *does it have a counter-signature / timestamp
  from a trusted authority?*

Full cryptographic verification is left to :mod:`wintrust` (a thin
facade that this module integrates with).

References
----------

* https://learn.microsoft.com/en-us/windows/win32/debug/pe-format
* https://learn.microsoft.com/en-us/windows/win32/win_certificates

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

log = logging.getLogger("UmerOS.Compat.SignedPe")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WIN_CERT_REVISION_1_0 = 0x0100
WIN_CERT_REVISION_2_0 = 0x0200

WIN_CERT_TYPE_X509             = 0x0001
WIN_CERT_TYPE_PKCS_SIGNED_DATA = 0x0002
WIN_CERT_TYPE_PKCS1_RESERVED   = 0x0003
WIN_CERT_TYPE_TS_STACK_CERT    = 0x0004

# Trust providers.
WINTRUST_ACTION_GENERIC_VERIFY_V2 = "{00AAC56B-CD44-11D0-8CC2-00C04FC295EE}"
WINTRUST_ACTION_GENERIC_CERT_VERIFY = "{00A7A280-67CF-4D40-8B33-52F525CBE37F}"
WINTRUST_ACTION_GENERIC_CHAIN_VERIFY = "{00B0B740-BB47-4F4F-B565-7A8E5F76B9C9}"

ERROR_SUCCESS           = 0
TRUST_E_NOSIGNATURE     = 0x800B0100
TRUST_E_EXPLICIT_DENY   = 0x800B0111
TRUST_E_SUBJECT_NOT_TRUSTED = 0x800B0112

# PKCS#7 content types (encoded as OIDs in DER).
OID_PKCS7_SIGNED_DATA = "1.2.840.113549.1.7.2"
OID_PKCS7_DATA        = "1.2.840.113549.1.7.1"

# Microsoft Authenticode OIDs.
OID_SPC_INDIRECT_DATA = "1.3.6.1.4.1.311.2.1.4"
OID_SPC_PE_IMAGE_DATA = "1.3.6.1.4.1.311.2.1.15"
OID_SPC_SP_OPUS_INFO  = "1.3.6.1.4.1.311.2.1.12"


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WinCertificate:
    """The fixed-size header of ``WIN_CERTIFICATE`` (8 bytes)."""

    length: int                  # dwLength: size of bCertificate
    revision: int                # wRevision
    certificate_type: int
    data: bytes                  # bCertificate (raw PKCS#7 / X.509 / ...)

    @property
    def is_pkcs_signed_data(self) -> bool:
        return self.certificate_type == WIN_CERT_TYPE_PKCS_SIGNED_DATA

    @property
    def is_x509(self) -> bool:
        return self.certificate_type == WIN_CERT_TYPE_X509


@dataclass(frozen=True)
class CertificateSubject:
    """A very small subset of the X.509 subject we extract from PKCS#7."""

    common_name: str = ""
    organization: str = ""
    email: str = ""


@dataclass
class SignedPeInfo:
    """Top-level view of a PE's signature state."""

    has_security_directory: bool = False
    certificates: List[WinCertificate] = field(default_factory=list)
    subjects: List[CertificateSubject] = field(default_factory=list)

    @property
    def is_signed(self) -> bool:
        return bool(self.certificates)

    @property
    def signer_count(self) -> int:
        return len(self.certificates)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_certificates(pe) -> SignedPeInfo:
    """Walk the Security directory of ``pe`` and return signatures.

    ``pe`` must expose :meth:`get_data_directory` and a ``raw``
    attribute with the file bytes.  The Security Directory entry of
    the optional header is **index 4**; its virtual_address is in
    fact a *file offset*, not an RVA, which is unique among PE data
    directories.
    """
    out = SignedPeInfo()
    dd = pe.get_data_directory(4)
    if dd is None or not dd.is_present:
        return out
    out.has_security_directory = True
    cursor = dd.virtual_address
    end = cursor + dd.size
    raw = pe.raw
    while cursor + 8 <= end:
        (dw_length, w_revision, w_type) = struct.unpack_from(
            "<IHH", raw, cursor)
        if dw_length < 8 or cursor + dw_length > end + 8:
            break
        body = bytes(raw[cursor + 8: cursor + dw_length])
        cert = WinCertificate(
            length=dw_length - 8, revision=w_revision,
            certificate_type=w_type, data=body)
        out.certificates.append(cert)
        try:
            subj = extract_subject_from_pkcs7(body)
        except Exception as exc:
            log.debug("subject parse failed: %s", exc)
            subj = CertificateSubject()
        out.subjects.append(subj)
        cursor += dw_length
        # Round up to 8-byte alignment per the spec.
        if cursor % 8:
            cursor += 8 - (cursor % 8)
    return out


# ---------------------------------------------------------------------------
# PKCS#7 surface extraction (lightweight)
# ---------------------------------------------------------------------------
#
# A full PKCS#7 / ASN.1 parser is *not* implemented here; we do just
# enough to recover the friendly subject strings a typical
# installation routine cares about ("Signed by Microsoft
# Corporation").
#
# Approach: scan the byte buffer for printable UTF-8 / Latin-1
# strings.  When the buffer looks like a DER-encoded PKCS#7 we
# extract the issuer / subject by walking the SET OF
# ``AttributeTypeAndValue`` at the end of the certificate.  When it
# doesn't, we return an empty subject (the data is still considered
# "signed" because a WIN_CERTIFICATE is present).

def extract_subject_from_pkcs7(blob: bytes) -> CertificateSubject:
    """Pull the friendly subject strings out of a PKCS#7 SignedData.

    This is a *best-effort* extraction; real X.509 chains are
    verified against the trusted root store, which we leave to
    :mod:`wintrust`.
    """
    if not blob or not blob.startswith(b"\x30"):
        return CertificateSubject()
    # Quick sanity: PKCS#7 always wraps a SEQUENCE { OID, [content] }
    # where the first OID is one of {signedData, envelopedData, ...}.
    if _find_oid(blob, OID_PKCS7_SIGNED_DATA) is None and \
       _find_oid(blob, OID_PKCS7_DATA) is None:
        # Fallback: scan printable substrings.
        cn = _largest_printable_run(blob, min_len=6)
        return CertificateSubject(common_name=cn)
    # For the PKCS#7 SignedData envelope the signer cert is usually
    # the LAST X.509 certificate in the certificates SET.  We index
    # into it by walking CN= strings.
    candidates = _scan_printable_attributes(blob)
    if not candidates:
        return CertificateSubject()
    # Heuristic: the largest printable string is usually the CN.
    cn = max(candidates, key=len) if candidates else ""
    return CertificateSubject(common_name=cn,
                              organization=_match_first(blob, b"O="),
                              email=_match_first(blob, b"E="))


def _find_oid(blob: bytes, dotted_oid: str) -> Optional[int]:
    """Return the offset where ``dotted_oid`` (as raw DER bytes)
    appears, or ``None``.

    The OID is encoded with each integer in 1-byte base-128 with the
    high bit clear on the final byte.  We do a simple byte-level
    probe rather than a full DER walk.
    """
    try:
        parts = [int(p) for p in dotted_oid.split(".")]
    except ValueError:
        return None
    if not parts:
        return None
    first = parts[0] * 40 + (parts[1] if len(parts) > 1 else 0)
    body = bytearray([first])
    for p in parts[2:]:
        if p < 0x80:
            body.append(p)
        else:
            # multi-byte.
            chunks = []
            v = p
            while v > 0:
                chunks.append(v & 0x7F)
                v >>= 7
            chunks.reverse()
            for i, c in enumerate(chunks):
                if i + 1 < len(chunks):
                    body.append(c | 0x80)
                else:
                    body.append(c)
    needle = bytes(body)
    pos = blob.find(needle)
    return pos if pos >= 0 else None


def _scan_printable_attributes(blob: bytes) -> List[str]:
    """Return any printable runs of >= 4 chars between 'CN=' and '","
    sequences.  This is intentionally tolerant of malformed blobs."""
    out: List[str] = []
    text = blob.decode("latin-1", errors="replace")
    needle_cn = "CN="
    i = 0
    while i < len(text):
        j = text.find(needle_cn, i)
        if j < 0:
            break
        # Skip any tag/value bytes between the marker and the CN.
        start = j + len(needle_cn)
        # Heuristic: walk forward until we hit a '<' (X.509 quoting),
        # a control char, or end-of-buffer.
        end = start
        while end < len(text) and text[end] not in ('\x00', '\r', '\n'):
            if end - start >= 80:
                break
            end += 1
        candidate = text[start:end].strip(" '\"\t,")
        # Drop any leading tag bytes ("0\x16U").
        cleaned = []
        started = False
        for ch in candidate:
            if ch.isprintable() or ch in (' ', '-', '_'):
                started = True
                cleaned.append(ch)
            elif started:
                break
        candidate = "".join(cleaned)
        if len(candidate) >= 4 and candidate.isprintable():
            out.append(candidate)
        i = end
    return out


def _match_first(blob: bytes, marker: bytes) -> str:
    idx = blob.find(marker)
    if idx < 0:
        return ""
    start = idx + len(marker)
    end = start
    while end < len(blob) and blob[end] >= 0x20 and blob[end] < 0x7F:
        end += 1
    return blob[start:end].decode("latin-1", errors="replace")


def _largest_printable_run(blob: bytes, *, min_len: int = 6) -> str:
    best = ""
    cur = bytearray()
    for b in blob:
        if 0x20 <= b < 0x7F:
            cur.append(b)
        else:
            if len(cur) >= min_len and len(cur) > len(best):
                best = bytes(cur).decode("latin-1", errors="replace")
            cur.clear()
    if len(cur) >= min_len and len(cur) > len(best):
        best = bytes(cur).decode("latin-1", errors="replace")
    return best


# ---------------------------------------------------------------------------
# WinVerifyTrust stub
# ---------------------------------------------------------------------------

def WinVerifyTrust(file_path: str, action_id: str = WINTRUST_ACTION_GENERIC_VERIFY_V2
                    ) -> Tuple[int, str]:
    """Pure-Python equivalent of the Win32 ``WinVerifyTrust`` call.

    Returns ``(hresult, message)``.  The hresult is one of:

    * ``ERROR_SUCCESS`` (0) — the file carries a parseable WIN_CERTIFICATE.
    * ``TRUST_E_NOSIGNATURE`` — no Security directory at all.
    * ``TRUST_E_EXPLICIT_DENY`` / ``TRUST_E_SUBJECT_NOT_TRUSTED`` —
      something else is wrong (corrupt PKCS#7, etc.).

    Note this implementation does not perform X.509 chain
    validation; it just reports *presence and syntactical sanity*.
    """
    from .pe_loader import PeFile
    try:
        pe = PeFile.from_path(file_path)
    except (FileNotFoundError, ValueError) as exc:
        return (0x80070002, f"file unreadable: {exc}")        # ERROR_FILE_NOT_FOUND
    info = parse_certificates(pe)
    if not info.has_security_directory:
        return (TRUST_E_NOSIGNATURE, "no embedded signature")
    if not info.certificates:
        return (TRUST_E_NOSIGNATURE, "empty certificate table")
    bad = [c for c in info.certificates if not c.data]
    if bad:
        return (TRUST_E_EXPLICIT_DENY, "empty certificate blobs present")
    if any(not c.is_pkcs_signed_data for c in info.certificates):
        # X.509 directly embedded is rare for executables; the Win32
        # loader also rejects it in practice.
        return (TRUST_E_EXPLICIT_DENY,
                "non-PKCS#7 certificate type rejected")
    return (ERROR_SUCCESS, "signature present (chain unchecked)")


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    from .pe_loader import PeFile, _build_fake_pe
    pe = PeFile.from_bytes(_build_fake_pe())
    info = parse_certificates(pe)
    if info.has_security_directory:
        return False
    if info.is_signed:
        return False
    # Append a fake WIN_CERTIFICATE to the .data section.
    pe_bytes = bytearray(_build_fake_pe())
    # Place a cert at file offset 0x400 (start of .data section).
    cert_off = 0x400
    fake_blob = (
        b"\x30\x82\x01\x00"            # SEQUENCE header (faux)
        + b"O=Microsoft Corporation\x00"
        + b"CN=Microsoft Windows\x00"
        + b"E=secure@microsoft.com\x00"
        + b"\x00" * 64
    )
    pe_bytes += b"\x00" * 8      # pad data dir region won't be used
    struct.pack_into("<IHH", pe_bytes, cert_off,
                     len(fake_blob) + 8,
                     WIN_CERT_REVISION_2_0,
                     WIN_CERT_TYPE_PKCS_SIGNED_DATA)
    pe_bytes[cert_off + 8: cert_off + 8 + len(fake_blob)] = fake_blob
    # Now patch data directory 4 to point at our fake cert.
    # The data-directory region sits at:
    #   opt_off (96 bytes) - dd_off + 0 = dd_off
    # We'll search for a known empty slot and patch.
    pe2 = PeFile.from_bytes(bytes(pe_bytes))
    n = pe2.optional_header.number_of_rva_and_sizes
    # Recompute the dd_off similarly to delay_imports.
    dd_off = (pe2.pe_offset + 4 + 20 + pe2.size_of_optional_header - n * 8)
    struct.pack_into("<II", pe_bytes, dd_off + 4 * 8, cert_off, 8 + len(fake_blob))

    pe3 = PeFile.from_bytes(bytes(pe_bytes))
    info = parse_certificates(pe3)
    if not info.has_security_directory:
        return False
    if not info.is_signed:
        return False
    # Subject extraction (best effort).
    sj = info.subjects[0] if info.subjects else CertificateSubject()
    # Even if exact fields are noisy, the common-name should at least
    # include some printable run.
    if not sj.common_name:
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
