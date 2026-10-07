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

"""Boot-subsystem fidelity tests.

``boot/`` presented a mix of genuine byte parsing and outright fabrication. This
module pins down the corrections:

* ``bzimage`` read four ``setup_header`` offsets wrong and invented a field;
* ``microcode.parse_intel_microcode_header`` parsed a non-Intel header layout;
* ``kernel_signing.SignatureVerifier.verify`` returned ``VALID`` for any file
  starting with ``MZ`` and never consulted its trust store;
* ``kernel_image.create_sample_kernel`` wrote gzip magic followed by noise;
* ``efi_system.install_grub`` wrote 4096 NUL bytes and reported success;
* ``initrd_manager.verify_image`` marked any existing file ``VALID``;
* ``microcode.MicrocodeInstaller.generate_ucode_initrd`` wrote a zero-byte file
  and returned True.

Every test here fails against the previous behaviour.
"""

from __future__ import annotations

import datetime
import gzip
import struct
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from boot.bzimage import _build_fake_bzimage, parse_bzimage_header  # noqa: E402
from boot.efi_system import EFIArchitecture, EFISystemPartition, EFISystemManager  # noqa: E402
from boot.initrd_manager import InitrdManager, InitrdStatus  # noqa: E402
from boot.kernel_image import KernelImageManager  # noqa: E402
from boot.kernel_signing import (  # noqa: E402
    KeyType,
    SignatureStatus,
    SignatureVerifier,
    SigningKey,
)
from boot.microcode import (  # noqa: E402
    CPUVendor,
    MicrocodeManager,
    MicrocodeParser,
    MicrocodeSignificance,
    MicrocodeUpdate,
    MicrocodeInstaller,
)


# ── bzImage setup_header offsets ────────────────────────────────────────────

def _fake_image() -> object:
    return parse_bzimage_header(
        "<memory>",
        data=_build_fake_bzimage(version=0x020E, setup_sects=4, payload_length=0x1000),
    )


def test_start_sys_seg_read_from_0x20c_not_0x1f6():
    """``start_sys_seg`` is a u16 at 0x20c; it used to be read at 0x1f6."""
    hdr = _fake_image()
    assert hdr.start_sys_seg == 0x1000, (
        "start_sys_seg must come from offset 0x20c (the fixture writes 0x1000 "
        "there; a read at 0x1f6 would yield 0)"
    )


def test_xloadflags_is_a_u16_not_a_u32():
    """Reading 4 bytes at 0x236 folds cmdline_size's low half into the flags."""
    hdr = _fake_image()
    assert hdr.xloadflags == 0x21, (
        f"xloadflags is u16 (0x21); a u32 read would give 0x20000021 because "
        f"cmdline_size sits at 0x238 — got 0x{hdr.xloadflags:x}"
    )
    assert hdr.is_64bit is True
    assert hdr.can_have_loader is True
    assert hdr.efi_handover is False


def test_handover_and_kernel_info_offsets():
    """``handover_offset`` is 0x264 and ``kernel_info_offset`` is 0x268."""
    hdr = _fake_image()
    assert hdr.handover_offset == 0x1400
    assert hdr.kernel_info_offset == 0x2000


def test_init_addr_field_does_not_exist():
    """0x268 is kernel_info_offset; there is no ``init_addr`` in the protocol."""
    hdr = _fake_image()
    assert not hasattr(hdr, "init_addr")
    assert "init_addr" not in hdr.as_dict()


def test_protocol_minor_is_the_minor_byte():
    """``protocol_minor`` used to return the major byte, duplicating major."""
    hdr = _fake_image()          # version 0x020e == protocol 2.14
    assert hdr.protocol_major == 0x02
    assert hdr.protocol_minor == 0x0E
    assert hdr.protocol_string() == "2.0e"


# ── Intel microcode header ──────────────────────────────────────────────────

def _intel_header(**over) -> bytes:
    fields = {
        "hdrver": 0x00000001,
        "rev": 0x000000F4,
        "date": 0x20240115,
        "sig": 0x000906EA,
        "cksum": 0xDEADBEEF,
        "ldrver": 0x00000001,
        "pf_mask": 0x00000003,
        "datasize": 0x00001000,
        "totalsize": 0x00002000,
    }
    fields.update(over)
    return b"".join(struct.pack("<I", v) for v in fields.values()) + b"\x00" * 12


def test_intel_microcode_header_layout():
    """All nine u32 fields sit at 0/4/8/12/16/20/24/28/32."""
    h = MicrocodeParser.parse_intel_microcode_header(_intel_header())
    assert h is not None
    assert h["header_version"] == 0x00000001
    assert h["revision"] == 0x000000F4
    assert h["date"] == 0x20240115
    assert h["signature"] == 0x000906EA
    assert h["checksum"] == 0xDEADBEEF
    assert h["loader_version"] == 0x00000001
    assert h["processor_flags"] == 0x00000003
    assert h["data_size"] == 0x00001000
    assert h["total_size"] == 0x00002000


def test_intel_microcode_short_buffer_rejected():
    assert MicrocodeParser.parse_intel_microcode_header(b"\x00" * 47) is None


# ── PE/Authenticode verification ────────────────────────────────────────────

def _pe_with_certificate(p7: bytes | None) -> bytes:
    """Build a minimal PE32+ image, optionally carrying a PKCS#7 blob."""
    if p7 is None:
        buf = bytearray(0x200)
        buf[0:2] = b"MZ"
        struct.pack_into("<I", buf, 0x3C, 0x80)
        buf[0x80:0x84] = b"PE\x00\x00"
        struct.pack_into("<H", buf, 0x84, 0x8664)
        struct.pack_into("<H", buf, 0x80 + 4 + 16, 0xF0)
        struct.pack_into("<H", buf, 0x80 + 24, 0x20B)
        struct.pack_into("<I", buf, 0x80 + 24 + 108, 16)
        return bytes(buf)

    off = 0x300
    length = (8 + len(p7) + 7) & ~7
    buf = bytearray(off + length)
    buf[0:2] = b"MZ"
    struct.pack_into("<I", buf, 0x3C, 0x80)
    buf[0x80:0x84] = b"PE\x00\x00"
    struct.pack_into("<H", buf, 0x84, 0x8664)
    struct.pack_into("<H", buf, 0x80 + 4 + 16, 0xF0)
    struct.pack_into("<H", buf, 0x80 + 24, 0x20B)
    struct.pack_into("<I", buf, 0x80 + 24 + 108, 16)
    struct.pack_into("<I", buf, 0x80 + 24 + 112 + 4 * 8, off)
    struct.pack_into("<I", buf, 0x80 + 24 + 112 + 4 * 8 + 4, length)
    struct.pack_into("<I", buf, off, length)
    struct.pack_into("<H", buf, off + 4, 0x0200)
    struct.pack_into("<H", buf, off + 6, 0x0002)      # PKCS_SIGNED_DATA
    buf[off + 8:off + 8 + len(p7)] = p7
    return bytes(buf)


def _signed_p7():
    """Return (pkcs7_der, sha256_fingerprint_hex, common_name)."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import pkcs7
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    cn = "UmerOS Fidelity Test Signer"
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    der = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(b"payload")
        .add_signer(cert, key, hashes.SHA256())
        .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.Binary])
    )
    return der, cert.fingerprint(hashes.SHA256()).hex(), cn


def test_unverified_status_exists():
    """Signed-but-unchecked must be distinguishable from unsigned/invalid."""
    assert hasattr(SignatureStatus, "UNVERIFIED")


def test_any_mz_file_is_no_longer_valid(tmp_path):
    """The old bug: ``VALID`` for anything starting with MZ."""
    f = tmp_path / "stub.efi"
    f.write_bytes(b"MZ" + b"\x00" * 200)
    sig = SignatureVerifier().verify(f)
    assert sig.status is not SignatureStatus.VALID
    assert sig.status is SignatureStatus.UNSIGNED


def test_non_pe_file_is_unsigned(tmp_path):
    f = tmp_path / "plain.bin"
    f.write_bytes(b"not a PE file at all")
    assert SignatureVerifier().verify(f).status is SignatureStatus.UNSIGNED


def test_missing_file_is_invalid(tmp_path):
    assert SignatureVerifier().verify(tmp_path / "nope").status is SignatureStatus.INVALID


def test_pe_without_certificate_table_is_unsigned(tmp_path):
    f = tmp_path / "unsigned.efi"
    f.write_bytes(_pe_with_certificate(None))
    sig = SignatureVerifier().verify(f)
    assert sig.status is SignatureStatus.UNSIGNED
    assert "certificate table" in sig.note


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_trust_store_is_actually_consulted(tmp_path):
    """Keys used to be ignored entirely; the note must name the signer.

    The warning filter covers a ``cryptography`` notice about its own PKCS#7
    builder emitting BER-compatible DER (it falls back to BER parsing and still
    returns the certificates). It is noise from the fixture, not a code path
    under test.
    """
    p7, fingerprint, cn = _signed_p7()
    f = tmp_path / "signed.efi"
    f.write_bytes(_pe_with_certificate(p7))

    # No anchors -> unverified, signer identified.
    sig = SignatureVerifier().verify(f)
    assert sig.status is SignatureStatus.UNVERIFIED
    assert cn in sig.signer

    # An unrelated enrolled key -> still refused, and the count proves the
    # trust store was consulted.
    unrelated = SigningKey(key_type=KeyType.DB, subject="Someone Else",
                           fingerprint="00" * 32, enrolled=True)
    sig = SignatureVerifier([unrelated]).verify(f)
    assert sig.status is SignatureStatus.UNVERIFIED
    assert "not in the trust store" in sig.note

    # The matching enrolled key is recognised (but still cannot be *proven*
    # without a PKCS#7 verification backend).
    matching = SigningKey(key_type=KeyType.DB, subject=cn,
                          fingerprint=fingerprint, enrolled=True)
    sig = SignatureVerifier([matching]).verify(f)
    assert sig.status is SignatureStatus.UNVERIFIED
    assert "enrolled" in sig.note
    assert "NOT proven unmodified" in sig.note


def test_authenticode_verification_is_declared_unavailable():
    """The honest capability flag that justifies never returning VALID."""
    from boot.kernel_signing import AUTHENTICODE_VERIFICATION_AVAILABLE
    assert AUTHENTICODE_VERIFICATION_AVAILABLE is False


# ── Kernel image fixture ────────────────────────────────────────────────────

def test_sample_kernel_is_a_valid_gzip_stream(tmp_path):
    """It used to be gzip magic + os.urandom(), which cannot be inflated."""
    mgr = KernelImageManager(tmp_path)
    ki = mgr.create_sample_kernel("6.8.0-test", size_kb=8)

    raw = gzip.decompress(ki.vmlinuz_path.read_bytes())
    assert b"UMEROS-KERNEL-IMAGE-FIXTURE" in raw
    assert b"NOT A LINUX KERNEL" in raw


def test_sample_kernel_is_flagged_as_a_fixture(tmp_path):
    mgr = KernelImageManager(tmp_path)
    ki = mgr.create_sample_kernel("6.8.0-test", size_kb=4)
    assert ki.is_fixture is True


def test_sample_kernel_config_uses_real_symbols(tmp_path):
    mgr = KernelImageManager(tmp_path)
    ki = mgr.create_sample_kernel("6.8.0-test", size_kb=4)
    text = ki.config.config_path.read_text()
    assert "CONFIG_ROOT_FSReadOnly" not in text, "not a real Kconfig symbol"
    assert "CONFIG_BLK_DEV_INITRD=y" in text
    assert "FIXTURE" in text


# ── EFI bootloader installation ─────────────────────────────────────────────

def test_install_grub_refuses_to_write_a_placeholder(tmp_path):
    """It used to write 4096 NUL bytes and report success."""
    mgr = EFISystemManager(esp_mount=tmp_path / "efi", data_dir=tmp_path / "data")
    result = mgr.install_grub(EFIArchitecture.X86_64,
                              source=tmp_path / "does-not-exist.efi")

    assert result["success"] is False
    assert result["errors"], "a missing loader must be reported"
    boot_dir = tmp_path / "efi" / "EFI" / "BOOT"
    assert not (boot_dir / "BOOTX64.EFI").exists(), "no placeholder may be written"


def test_install_grub_copies_a_real_binary(tmp_path):
    real = tmp_path / "grubx64.efi"
    real.write_bytes(b"MZ" + b"\x90" * 64)          # stand-in for the real loader

    mgr = EFISystemManager(esp_mount=tmp_path / "efi", data_dir=tmp_path / "data")
    result = mgr.install_grub(EFIArchitecture.X86_64, source=real)

    assert result["success"] is True
    assert (tmp_path / "efi" / "EFI" / "BOOT" / "BOOTX64.EFI").read_bytes() == real.read_bytes()
    assert (tmp_path / "efi" / "EFI" / "ubuntu" / "grubx64.efi").read_bytes() == real.read_bytes()


def test_install_systemd_boot_has_the_same_guarantee(tmp_path):
    mgr = EFISystemManager(esp_mount=tmp_path / "efi", data_dir=tmp_path / "data")
    assert mgr.install_systemd_boot(source=tmp_path / "missing.efi")["success"] is False

    real = tmp_path / "systemd-bootx64.efi"
    real.write_bytes(b"MZ" + b"\x90" * 32)
    result = mgr.install_systemd_boot(EFIArchitecture.X86_64, source=real)
    assert result["success"] is True
    assert (tmp_path / "efi" / "EFI" / "BOOT" / "BOOTX64.EFI").exists()


# ── initrd image verification ───────────────────────────────────────────────

def _make_initrd(tmp_path: Path, name: str) -> Path:
    from initrd.cpio import newc_dir, newc_file, pack_archive

    blob = pack_archive([newc_dir("etc"), newc_file("etc/hostname", b"umeros\n")])
    p = tmp_path / name
    p.write_bytes(gzip.compress(blob))
    return p


def test_verify_image_rejects_a_text_file(tmp_path):
    """Any existing file used to be marked VALID."""
    junk = tmp_path / "initrd.img"
    junk.write_text("this is not an initramfs")
    mgr = InitrdManager(boot_path=str(tmp_path))
    mgr.register_image("junk", str(junk))

    assert mgr.verify_image("junk") is False
    assert mgr.images["junk"].status is InitrdStatus.CORRUPTED


def test_verify_image_rejects_an_empty_file(tmp_path):
    empty = tmp_path / "empty.img"
    empty.write_bytes(b"")
    mgr = InitrdManager(boot_path=str(tmp_path))
    mgr.register_image("empty", str(empty))
    assert mgr.verify_image("empty") is False


def test_verify_image_accepts_a_real_gzipped_cpio(tmp_path):
    img = _make_initrd(tmp_path, "initrd.img")
    mgr = InitrdManager(boot_path=str(tmp_path))
    mgr.register_image("good", str(img))

    assert mgr.verify_image("good") is True
    assert mgr.images["good"].status is InitrdStatus.VALID


def test_verify_image_accepts_uncompressed_cpio(tmp_path):
    from initrd.cpio import newc_file, pack_archive

    img = tmp_path / "initrd.raw"
    img.write_bytes(pack_archive([newc_file("init", b"#!/bin/sh\n")]))
    mgr = InitrdManager(boot_path=str(tmp_path))
    mgr.register_image("raw", str(img))
    assert mgr.verify_image("raw") is True


def test_verify_image_still_honours_the_expected_hash(tmp_path):
    img = _make_initrd(tmp_path, "initrd.img")
    mgr = InitrdManager(boot_path=str(tmp_path))
    mgr.register_image("h", str(img))
    assert mgr.verify_image("h", expected_hash="0" * 128) is False


# ── Microcode initrd generation ─────────────────────────────────────────────

def _manager_with_one_update(tmp_path: Path) -> MicrocodeManager:
    """Create a manager whose firmware dir holds one real Intel microcode file.

    ``scan_updates()`` clears its cache and re-scans ``intel-ucode/microcode-*.bin``,
    so the fixture must be discoverable on disk rather than injected.
    """
    intel_dir = tmp_path / "fw" / "intel-ucode"
    intel_dir.mkdir(parents=True, exist_ok=True)
    (intel_dir / "microcode-000906EA.bin").write_bytes(_intel_header())
    return MicrocodeManager(tmp_path / "fw", tmp_path / "initrd")


def test_ucode_initrd_is_a_real_archive(tmp_path):
    """It used to write a zero-byte file and return True."""
    mgr = _manager_with_one_update(tmp_path)
    out = tmp_path / "ucode.img"
    assert MicrocodeInstaller(mgr).generate_ucode_initrd(out) is True

    data = out.read_bytes()
    assert len(data) > 0, "an empty ucode.img is not an initrd"
    assert data[:6] == b"070701", "must be a cpio (newc) archive"
    assert b"kernel/x86/microcode/GenuineIntel.bin" in data
    assert b"TRAILER!!!" in data


def test_ucode_initrd_fails_closed_without_updates(tmp_path):
    mgr = MicrocodeManager(tmp_path / "fw", tmp_path / "initrd")
    out = tmp_path / "ucode.img"
    assert MicrocodeInstaller(mgr).generate_ucode_initrd(out) is False
    assert not out.exists(), "no image should be written when there is no payload"
