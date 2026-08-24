"""
pytest suite for legal/licenses.py — license-compliance audit.

Locks the fail-closed behaviour of LicenseManager.scan_directory: a file is
compliant only if it carries an explicit license *declaration* (SPDX id or a
clear grant phrase).  Merely mentioning the words "License"/"Copyright" — which
any source docstring that references licenses contains — is NOT sufficient and
the file is reported as missing.  Previously every file matched the generic
"License"/"Copyright" branch and was counted compliant (fail-open).
"""

import os
import sys
import tempfile

from pathlib import Path

import pytest

_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from legal.licenses import LicenseManager  # noqa: E402


def _write(tmp: str, name: str, content: str) -> str:
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


def test_scan_directory_fails_closed_on_generic_mention():
    with tempfile.TemporaryDirectory() as d:
        _write(d, "mention.py", '"""This module references the LICENSE file."""\n')
        _write(d, "none.py", "x = 1\n")
        res = LicenseManager.scan_directory(d)
        # scan_directory stores absolute paths; compare on basename.
        missing = sorted(os.path.basename(p) for p in res.missing_license_files)
        assert "mention.py" in missing
        assert "none.py" in missing
        # Previously these would have been counted as compliant (fail-open).
        assert res.compliant_files == 0


def test_scan_directory_compliant_with_declaration():
    with tempfile.TemporaryDirectory() as d:
        _write(d, "gpl.py", '"""License: GPL-3.0"""\n')
        res = LicenseManager.scan_directory(d)
        # Exactly one file is written and it carries a real GPL-3.0 declaration,
        # so exactly one file is counted compliant (not two — a prior assertion
        # of `== 2` was a typo; scan_directory correctly reports 1 here).
        assert res.compliant_files == 1
        assert res.missing_license_files == []


def test_scan_directory_tracks_missing_count():
    with tempfile.TemporaryDirectory() as d:
        _write(d, "ok.py", '"""SPDX-License-Identifier: GPL-3.0"""\n')
        _write(d, "bad.py", "print('hi')\n")
        res = LicenseManager.scan_directory(d)
        assert res.total_files_scanned == 2
        assert res.is_fully_compliant is False
        # scan_directory stores absolute paths; compare on basename.
        missing = sorted(os.path.basename(p) for p in res.missing_license_files)
        assert "bad.py" in missing
