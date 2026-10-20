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

"""H133 tests — the consent-ledger default path must be OS-correct, not a CWD-relative dev path.

The standard flagged ``legal/consent.py``: ``DEFAULT_LEDGER_PATH`` was
``Path("UmerOS/var/lib/umeros/consent_ledger.json")`` on Windows — a **relative**
path resolved against the current working directory (and meaningless on any
other machine/OS).

H133 replaces it with :func:`default_ledger_path`, which resolves a proper
per-OS system location (``UMEROS_LEDGER_PATH`` override > ``XDG_STATE_HOME`` >
``/var/lib`` on POSIX; ``%PROGRAMDATA%`` > ``%ALLUSERSPROFILE%`` >
``%LOCALAPPDATA%`` > ``%APPDATA%`` > ``~/.umeros`` on Windows).
"""

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path, PurePosixPath, PureWindowsPath
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import legal.consent as consent  # noqa: E402
from legal.consent import ConsentManager, default_ledger_path  # noqa: E402

CONSENT_SRC = ROOT / "legal" / "consent.py"

_ENV_KEYS = (
    "UMEROS_LEDGER_PATH",
    "XDG_STATE_HOME",
    "PROGRAMDATA",
    "ALLUSERSPROFILE",
    "LOCALAPPDATA",
    "APPDATA",
)


class _EnvIsolated(unittest.TestCase):
    """Clear the path-related env vars around each test."""

    def setUp(self):
        self._saved = {k: os.environ.pop(k, None) for k in _ENV_KEYS}

    def tearDown(self):
        for k in _ENV_KEYS:
            os.environ.pop(k, None)
        for k, v in self._saved.items():
            if v is not None:
                os.environ[k] = v


class TestHostDefaultIsAbsolute(_EnvIsolated):
    """The core regression: the default must never be CWD-relative."""

    def test_default_ledger_path_is_absolute(self):
        self.assertTrue(default_ledger_path().is_absolute())

    def test_module_constant_is_absolute(self):
        self.assertIsInstance(consent.DEFAULT_LEDGER_PATH, Path)
        self.assertTrue(consent.DEFAULT_LEDGER_PATH.is_absolute())

    def test_no_relative_dev_path_remains(self):
        self.assertNotIn("UmerOS/var/lib", str(consent.DEFAULT_LEDGER_PATH))

    def test_env_override_wins(self):
        target = str(Path(tempfile.gettempdir()) / "custom_ledger.json")
        os.environ["UMEROS_LEDGER_PATH"] = target
        self.assertEqual(default_ledger_path(), Path(target))


class TestPosixBranch(_EnvIsolated):
    """POSIX: XDG_STATE_HOME, else /var/lib."""

    def _call(self):
        with mock.patch.object(consent, "Path", PurePosixPath), \
             mock.patch.object(consent, "os",
                               types.SimpleNamespace(name="posix", environ=os.environ)):
            return default_ledger_path()

    def test_xdg_state_home(self):
        os.environ["XDG_STATE_HOME"] = "/tmp/xdgstate"
        self.assertEqual(str(self._call()), "/tmp/xdgstate/umeros/consent_ledger.json")

    def test_var_lib_fallback(self):
        self.assertEqual(str(self._call()), "/var/lib/umeros/consent_ledger.json")

    def test_override_beats_xdg(self):
        os.environ["UMEROS_LEDGER_PATH"] = "/tmp/explicit.json"
        os.environ["XDG_STATE_HOME"] = "/tmp/xdgstate"
        with mock.patch.object(consent, "Path", PurePosixPath), \
             mock.patch.object(consent, "os",
                               types.SimpleNamespace(name="posix", environ=os.environ)):
            self.assertEqual(str(default_ledger_path()), "/tmp/explicit.json")


class TestWindowsBranch(_EnvIsolated):
    """Windows: PROGRAMDATA, else the per-user app-data chain."""

    def _call(self):
        with mock.patch.object(consent, "Path", PureWindowsPath), \
             mock.patch.object(consent, "os",
                               types.SimpleNamespace(name="nt", environ=os.environ)):
            return default_ledger_path()

    def test_programdata(self):
        os.environ["PROGRAMDATA"] = r"C:\ProgramData"
        self.assertEqual(str(self._call()),
                         r"C:\ProgramData\UmerOS\consent_ledger.json")

    def test_allusersprofile_when_no_programdata(self):
        os.environ["ALLUSERSPROFILE"] = r"C:\ProgramData"
        self.assertEqual(str(self._call()),
                         r"C:\ProgramData\UmerOS\consent_ledger.json")

    def test_localappdata_fallback(self):
        os.environ["LOCALAPPDATA"] = r"C:\Users\u\AppData\Local"
        self.assertEqual(str(self._call()),
                         r"C:\Users\u\AppData\Local\UmerOS\consent_ledger.json")

    def test_appdata_fallback(self):
        os.environ["APPDATA"] = r"C:\Users\u\AppData\Roaming"
        self.assertEqual(str(self._call()),
                         r"C:\Users\u\AppData\Roaming\UmerOS\consent_ledger.json")

    def test_old_relative_path_is_gone(self):
        """The pre-H133 default was a bare relative string — never returned now."""
        os.environ["PROGRAMDATA"] = r"C:\ProgramData"
        self.assertNotEqual(str(self._call()), "UmerOS/var/lib/umeros/consent_ledger.json")


class TestManagerUsesResolvedDefault(_EnvIsolated):
    """``ConsentManager`` still honours the module constant (patchable)."""

    def test_manager_uses_default_ledger_path(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "ledger.json"
            with mock.patch.object(consent, "DEFAULT_LEDGER_PATH", target):
                mgr = ConsentManager()
            self.assertEqual(mgr.ledger_path, target.resolve())

    def test_explicit_path_still_wins(self):
        with tempfile.TemporaryDirectory() as d:
            explicit = Path(d) / "explicit.json"
            mgr = ConsentManager(ledger_path=explicit)
            self.assertEqual(mgr.ledger_path, explicit.resolve())


class TestSourceInvariants(unittest.TestCase):
    """Pin code facts, never cosmetic tags."""

    def test_hardcoded_relative_literal_removed(self):
        src = CONSENT_SRC.read_text(encoding="utf-8")
        self.assertNotIn('Path("UmerOS/var/lib/umeros/consent_ledger.json")', src)

    def test_resolver_present(self):
        src = CONSENT_SRC.read_text(encoding="utf-8")
        self.assertIn("def default_ledger_path() -> Path:", src)
        self.assertIn("XDG_STATE_HOME", src)
        self.assertIn("PROGRAMDATA", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
