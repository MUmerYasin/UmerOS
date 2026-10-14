"""tests — initrd/ integrity hashes migrate SHA-256 -> SHA3-512.

Live sites fixed:
  * ai_helper.entropy_bytes  - entropy whitener
  * builder.InitrdBuilder.build - raw-image + final-image integrity hashes
  * BuildResult.sha3_512_raw / sha3_512_final (renamed from sha256_*)

`module_resolver.py` "sha256" entries are Linux **kernel module names**, NOT
hash calls, and must stay unchanged.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from initrd.ai_helper import AIHelper  # noqa: E402
from initrd.builder import BuildRequest, InitrdBuilder, OutputFormat  # noqa: E402
from initrd.scenarios import ScenarioId  # noqa: E402

INITRD = ROOT / "initrd"


# ── ai_helper entropy whitening ───────────────────────────────────────────
def test_entropy_uses_sha3_512():
    src = (INITRD / "ai_helper.py").read_text(encoding="utf-8")
    assert "hashlib.sha3_512" in src
    assert "hashlib.sha256" not in src


def test_entropy_bytes_length_and_deterministic_slicing():
    h = AIHelper()
    for n in (1, 8, 16, 32, 64):
        out = h.entropy_bytes(n)
        assert isinstance(out, bytes)
        assert len(out) == n


def test_entropy_bytes_zero_and_negative():
    h = AIHelper()
    assert h.entropy_bytes(0) == b""
    assert h.entropy_bytes(-5) == b""


def test_entropy_is_not_all_zero():
    h = AIHelper()
    # whitened output must not be trivially empty/zero
    assert h.entropy_bytes(32) != b"\x00" * 32


# ── builder image hashes ──────────────────────────────────────────────────
@pytest.fixture()
def built(tmp_path):
    req = BuildRequest(
        kernel_version="test-h97",
        scenario=ScenarioId.NORMAL,
        output_format=OutputFormat.CPIO_GZ,
        output_path=str(tmp_path / "initramfs.img.gz"),
    )
    result = InitrdBuilder().build(req)
    return result


def test_builder_source_uses_sha3_512():
    src = (INITRD / "builder.py").read_text(encoding="utf-8")
    assert "hashlib.sha3_512" in src
    assert "hashlib.sha256" not in src


def test_buildresult_fields_are_sha3_512(built):
    assert hasattr(built, "sha3_512_raw")
    assert hasattr(built, "sha3_512_final")
    assert not hasattr(built, "sha256_raw")
    assert not hasattr(built, "sha256_final")


def test_buildresult_hashes_are_128_hex(built):
    # SHA3-512 -> 128 hex chars
    assert len(built.sha3_512_raw) == 128
    assert len(built.sha3_512_final) == 128
    int(built.sha3_512_raw, 16)      # valid hex
    int(built.sha3_512_final, 16)


def test_buildresult_hashes_match_sha3_512_of_image(built):
    final_bytes = Path(built.output_path).read_bytes()
    assert built.sha3_512_final == hashlib.sha3_512(final_bytes).hexdigest()


def test_as_dict_keys_renamed(built):
    d = built.as_dict()
    assert "sha3_512_raw" in d
    assert "sha3_512_final" in d
    assert "sha256_raw" not in d
    assert "sha256_final" not in d


# ── module_resolver false-positive guard ──────────────────────────────────
def test_module_resolver_sha256_is_a_module_name_not_a_hash():
    """'sha256' in module_resolver is a Linux kernel module; must be intact."""
    from initrd.module_resolver import DEFAULT_MODULE_DB, _ALIASES
    assert "sha256" in DEFAULT_MODULE_DB
    assert DEFAULT_MODULE_DB["sha256"].name == "sha256"
    assert "sha256" in _ALIASES
    # no crypto hashing API is used in that file
    src = (INITRD / "module_resolver.py").read_text(encoding="utf-8")
    assert "hashlib" not in src


def test_no_live_sha256_hash_call_in_initrd():
    """No live `hashlib.sha256` call remains anywhere in initrd/."""
    offenders = []
    for path in INITRD.glob("*.py"):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "hashlib.sha256" in line:
                offenders.append(f"{path.name}:{i}")
    assert offenders == []
