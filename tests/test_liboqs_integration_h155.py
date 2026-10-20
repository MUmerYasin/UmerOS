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

"""H155 tests — the vendored ``liboqs/`` C source is bound to the Python PQC layer.

The standard flagged the vendored ``liboqs/`` as **dead/unwired**: no Python
module referenced it, so the §4.2 "PQC via ``liboqs``" mandate was satisfied
only "on paper".

The fix introduces ``quantum/liboqs_integration.py`` (a provenance/integration
bridge) and wires it into ``quantum/crypto_pqc.PostQuantumCrypto`` via a
``provenance()`` method, so the vendored C source's pin/version and the
``oqs`` Python bindings are introspectable from the live PQC layer.

These tests pin that wiring and the reported provenance.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quantum import liboqs_integration as li  # noqa: E402
from quantum.crypto_pqc import PostQuantumCrypto  # noqa: E402

PIN_VERSION = "0.16.0"
NOTICES = ROOT / "THIRD_PARTY_NOTICES.md"
CRYPTO_PQC = ROOT / "quantum" / "crypto_pqc.py"


class TestVendoredSourceProvenance(unittest.TestCase):
    """The vendored C source is locatable and its version is reported."""

    def test_vendored_dir_present(self):
        d = li.vendored_liboqs_dir()
        self.assertIsNotNone(d, "vendored liboqs/ source not found")
        self.assertEqual(d.name, "liboqs")

    def test_vendored_version_matches_pin(self):
        self.assertEqual(li.vendored_version(), PIN_VERSION)

    def test_version_matches_third_party_notice(self):
        # The integration bridge and the committed notice must agree on the pin.
        self.assertIn(PIN_VERSION, NOTICES.read_text(encoding="utf-8"))

    def test_declared_in_gitmodules(self):
        self.assertTrue(li.declared_in_gitmodules())


class TestBindingsDetection(unittest.TestCase):
    """The ``oqs`` bindings are detected without ever crashing on a bad wheel."""

    def test_bindings_available_is_bool(self):
        self.assertIsInstance(li.python_bindings_available(), bool)

    def test_bindings_version_consistent(self):
        if li.python_bindings_available():
            # Version may be unknown even when importable; must be str|None.
            v = li.python_bindings_version()
            self.assertTrue(v is None or isinstance(v, str))
        else:
            self.assertIsNone(li.python_bindings_version())


class TestIntegrationStatus(unittest.TestCase):
    """``integration_status()`` reports the full provenance dictionary."""

    def test_status_keys(self):
        st = li.integration_status()
        for key in (
            "vendored_source_present",
            "vendored_source_dir",
            "vendored_version",
            "declared_in_gitmodules",
            "python_bindings_available",
            "python_bindings_version",
            "third_party_notice_present",
        ):
            self.assertIn(key, st, f"missing status key: {key}")

    def test_status_values(self):
        st = li.integration_status()
        self.assertTrue(st["vendored_source_present"])
        self.assertEqual(st["vendored_version"], PIN_VERSION)
        self.assertTrue(st["declared_in_gitmodules"])
        self.assertTrue(st["third_party_notice_present"])


class TestBuildInstructionsAndSummary(unittest.TestCase):
    def test_build_instructions_mention_toolchain(self):
        text = li.build_instructions()
        self.assertIn("git submodule", text)
        self.assertIn("cmake", text)
        self.assertIn("liboqs-python", text)

    def test_summarize_mentions_liboqs(self):
        s = li.summarize()
        self.assertIsInstance(s, str)
        self.assertIn("liboqs", s)
        self.assertIn(PIN_VERSION, s)


class TestCryptoPqcBinding(unittest.TestCase):
    """``PostQuantumCrypto.provenance()`` binds the facade to the vendored lib."""

    def test_provenance_reports_active_backend(self):
        pqc = PostQuantumCrypto()
        prov = pqc.provenance()
        self.assertEqual(prov.get("active_backend"), pqc.backend)
        self.assertEqual(prov.get("is_post_quantum"), pqc.is_post_quantum)
        # The vendored-source provenance must be included too.
        self.assertEqual(prov.get("vendored_version"), PIN_VERSION)

    def test_crypto_pqc_imports_the_bridge(self):
        src = CRYPTO_PQC.read_text(encoding="utf-8")
        self.assertIn("liboqs_integration", src)
        self.assertIn("def provenance(self)", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
