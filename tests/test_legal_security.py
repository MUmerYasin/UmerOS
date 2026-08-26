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
Regression tests for /legal security RED findings
=================================================
  - H128: GPL-3.0 is the canonical (exclusive) license. ``get_license_text``
          rejects any other license name instead of silently substituting the
          wrong text, and the module docstring + README no longer advertise a
          multi-license (Apache-2.0 / GPL-2.0 / MIT) framework.
  - H129: ``LicenseManager.scan_directory`` is FAIL-CLOSED — a file is compliant
          only with an explicit GPL-3.0 declaration (canonical header,
          ``License: GPL-3.0`` or an SPDX id). A loose "GPL-3.0" substring in
          prose, or a generic "License"/"Copyright" mention, is NOT compliant.
  - H130: ``get_license_text`` raises ``ValueError`` for non-GPL-3.0 names
          (no silent Apache-2.0 substitution).
  - H131: ``ConsentManager.require_consent_interactive`` is FAIL-CLOSED — it
          never auto-grants in dry-run or non-TTY environments; it requires an
          explicit TTY "I AGREE" or ``allow_non_interactive=True``.
  - H135: ``legal_ctl consent`` never auto-grants — it requires an explicit
          ``--i-agree`` flag (or real TTY input).

Run:  python -m unittest tests.test_legal_security -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)
_legal = str(Path(_root) / "legal")
if _legal not in sys.path:
    sys.path.insert(0, _legal)

from legal.licenses import LicenseManager                                  # noqa: E402
from legal.consent import ConsentManager, ConsentGateError                  # noqa: E402
from legal.cli import main as cli_main                                      # noqa: E402

# manager.py does `from consent import ConsentManager` (top-level `consent`
# module, because legal/ is on sys.path) — a distinct module object from
# `legal.consent`. Patch THAT one so LegalManager's default ledger redirects.
import consent as consent_module                                            # noqa: E402


def _write(tmp: str, name: str, content: str) -> str:
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


CANONICAL_HEADER = LicenseManager.GPL_HEADER_TEMPLATE


class TestLicenseAuditFailClosed(unittest.TestCase):
    """H129 — the compliance audit must fail CLOSED on missing/unknown licenses."""

    def test_generic_license_word_is_not_compliant(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "mention.py", '"""This module references the LICENSE file."""\n')
            _write(d, "none.py", "x = 1\n")
            res = LicenseManager.scan_directory(d)
            missing = sorted(os.path.basename(p) for p in res.missing_license_files)
            self.assertIn("mention.py", missing)
            self.assertIn("none.py", missing)
            self.assertEqual(res.compliant_files, 0)

    def test_loose_gpl_substring_in_prose_is_not_compliant(self):
        # [H129] A bare "GPL-3.0" substring (e.g. a comment) must NOT satisfy the
        # audit — only an explicit declaration does. This is the residual fail-open.
        with tempfile.TemporaryDirectory() as d:
            _write(d, "prose.py", '"""We are not GPL-3.0 compatible, see NOTICE."""\n')
            res = LicenseManager.scan_directory(d)
            self.assertEqual(res.compliant_files, 0)
            self.assertIn("prose.py", [os.path.basename(p) for p in res.missing_license_files])

    def test_canonical_header_is_compliant(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "gpl.py", CANONICAL_HEADER + "\nprint('hi')\n")
            res = LicenseManager.scan_directory(d)
            self.assertEqual(res.compliant_files, 1)
            self.assertEqual(res.missing_license_files, [])

    def test_license_colon_grant_is_compliant(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "gpl.py", '"""License: GPL-3.0"""\n')
            res = LicenseManager.scan_directory(d)
            self.assertEqual(res.compliant_files, 1)

    def test_spdx_id_is_compliant(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "spdx.py", '"""SPDX-License-Identifier: GPL-3.0-or-later"""\n')
            res = LicenseManager.scan_directory(d)
            self.assertEqual(res.compliant_files, 1)

    def test_is_fully_compliant_false_on_missing(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "ok.py", CANONICAL_HEADER + "\n")
            _write(d, "bad.py", "print('no header')\n")
            res = LicenseManager.scan_directory(d)
            self.assertEqual(res.total_files_scanned, 2)
            self.assertFalse(res.is_fully_compliant)
            self.assertIn("bad.py", [os.path.basename(p) for p in res.missing_license_files])


class TestGetLicenseTextStrict(unittest.TestCase):
    """H130 — get_license_text must be GPL-3.0 only and reject others."""

    def test_gpl_3_0_returns_header(self):
        text = LicenseManager.get_license_text("GPL-3.0")
        self.assertIn("GNU General Public License", text)

    def test_unknown_license_raises(self):
        with self.assertRaises(ValueError):
            LicenseManager.get_license_text("Apache-2.0")
        with self.assertRaises(ValueError):
            LicenseManager.get_license_text("MIT")


class TestConsentGateFailClosed(unittest.TestCase):
    """H131 — require_consent_interactive must fail CLOSED (no auto-grant)."""

    def test_dry_run_does_not_grant(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "ledger.json"
            mgr = ConsentManager(ledger_path=ledger)
            result = mgr.require_consent_interactive("installer", dry_run=True)
            self.assertFalse(result)
            self.assertFalse(mgr.has_consented("installer"))

    def test_non_tty_without_override_raises(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "ledger.json"
            mgr = ConsentManager(ledger_path=ledger)
            with mock.patch.object(sys.stdin, "isatty", return_value=False):
                with self.assertRaises(ConsentGateError):
                    mgr.require_consent_interactive("installer")
            # No consent recorded by the failed attempt.
            self.assertFalse(mgr.has_consented("installer"))

    def test_non_tty_with_override_grants(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "ledger.json"
            mgr = ConsentManager(ledger_path=ledger)
            with mock.patch.object(sys.stdin, "isatty", return_value=False):
                result = mgr.require_consent_interactive(
                    "installer", allow_non_interactive=True
                )
            self.assertTrue(result)
            self.assertTrue(mgr.has_consented("installer"))


class TestConsentCliFailClosed(unittest.TestCase):
    """H135 — `legal_ctl consent` must never auto-grant without --i-agree."""

    def test_cli_refuses_without_i_agree_non_tty(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_ledger = Path(d) / "ledger.json"
            with mock.patch.object(sys.stdin, "isatty", return_value=False):
                with mock.patch.object(consent_module, "DEFAULT_LEDGER_PATH", tmp_ledger):
                    rc = cli_main(["consent", "general"])
            self.assertEqual(rc, 1)
            # Refusal must NOT have written/granted a ledger entry.
            self.assertFalse(tmp_ledger.exists())

    def test_cli_grants_with_i_agree(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_ledger = Path(d) / "ledger.json"
            with mock.patch.object(sys.stdin, "isatty", return_value=False):
                with mock.patch.object(consent_module, "DEFAULT_LEDGER_PATH", tmp_ledger):
                    rc = cli_main(["consent", "general", "--i-agree"])
            self.assertEqual(rc, 0)
            self.assertTrue(tmp_ledger.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
