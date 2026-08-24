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
Tests for the /boot consent + kernel-verification fail-closed posture.

Covers:
- H29  boot.init.Bootloader.display_waiver  (EULA must never be silently
        auto-accepted in non-interactive mode; explicit opt-in required)
- H27  boot.bootloader.verify_kernel        (missing/unverified kernel must
        be rejected, never trusted)

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""
from __future__ import annotations

import builtins
import hashlib
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ---------------------------------------------------------------------------
# H29 — boot consent must be fail-closed (no silent auto-accept)
# ---------------------------------------------------------------------------

class TestDisplayWaiverFailClosed:
    """H29: consent is only granted by explicit opt-in or typed 'I AGREE'."""

    def test_non_tty_without_opt_in_aborts(self):
        """Non-interactive run with no explicit consent must fail-closed."""
        from boot.init import Bootloader

        loader = Bootloader()
        with pytest.raises(SystemExit) as exc:
            loader.display_waiver(accept_eula=False)
        assert exc.value.code == 1

    def test_non_tty_with_opt_in_flag_accepts(self, monkeypatch):
        """Explicit opt-in flag (accept_eula=True) grants consent."""
        from boot.init import Bootloader

        # Force a non-TTY environment so the interactive branch is skipped.
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
        loader = Bootloader()
        # Must NOT raise SystemExit.
        loader.display_waiver(accept_eula=True)

    def test_tty_with_i_agree_accepts(self, monkeypatch):
        """Typing 'I AGREE' at a TTY grants consent."""
        from boot.init import Bootloader

        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr(builtins, "input", lambda *a, **k: "I AGREE")
        loader = Bootloader()
        loader.display_waiver(accept_eula=False)

    def test_tty_with_wrong_response_aborts(self, monkeypatch):
        """Anything other than 'I AGREE' at a TTY aborts the boot."""
        from boot.init import Bootloader

        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr(builtins, "input", lambda *a, **k: "nope")
        loader = Bootloader()
        with pytest.raises(SystemExit) as exc:
            loader.display_waiver(accept_eula=False)
        assert exc.value.code == 1

    def test_opt_in_flag_overrides_non_tty_without_prompt(self, monkeypatch):
        """Opt-in flag must work even when input() would otherwise be called."""
        from boot.init import Bootloader

        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
        # input must NOT be called when opt-in is given.
        monkeypatch.setattr(
            builtins, "input", lambda *a, **k: pytest.fail("input() was called")
        )
        loader = Bootloader()
        loader.display_waiver(accept_eula=True)


# ---------------------------------------------------------------------------
# H27 — kernel integrity verification must be fail-closed
# ---------------------------------------------------------------------------

class TestVerifyKernelFailClosed:
    """H27: a missing or unverified kernel image must be rejected."""

    def test_missing_kernel_rejected(self):
        """A non-existent kernel path must return False (never trusted)."""
        from boot.bootloader import verify_kernel

        assert verify_kernel("/no/such/kernel/image.bin") is False

    def test_required_without_hash_rejected(self, tmp_path):
        """required=True with no expected_hash must reject (fail-closed)."""
        from boot.bootloader import verify_kernel

        f = tmp_path / "kernel.img"
        f.write_bytes(b"fake-kernel-bytes")
        assert verify_kernel(str(f), expected_hash=None, required=True) is False

    def test_hash_mismatch_rejected(self, tmp_path):
        """A mismatched hash must reject the image."""
        from boot.bootloader import verify_kernel

        f = tmp_path / "kernel.img"
        f.write_bytes(b"fake-kernel-bytes")
        assert verify_kernel(str(f), expected_hash="0" * 64, required=True) is False

    def test_matching_hash_accepted(self, tmp_path):
        """A correct hash must accept the image."""
        from boot.bootloader import verify_kernel

        data = b"fake-kernel-bytes"
        f = tmp_path / "kernel.img"
        f.write_bytes(data)
        digest = hashlib.sha3_256(data).hexdigest()
        assert verify_kernel(str(f), expected_hash=digest, required=True) is True
