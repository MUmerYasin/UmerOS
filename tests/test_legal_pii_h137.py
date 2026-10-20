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

"""H137 tests — no real PII/financial data in committed ``legal/`` sources.

The standard flagged ``legal/`` for hardcoding real personal and financial
data: the founder's personal Gmail in ``contributors.py``/``maintainers.py``,
and full IBANs / phone numbers / Wise / Payoneer details in ``donations.py``
(💭 H137, review per §4.3).

H137's remedy: move that data to a config/asset file **excluded from source
control**.  These tests pin the resulting invariants:

* the committed ``legal/`` sources contain no personal Gmail, no PK IBAN and
  no personal Pakistani phone number;
* the creator/donor values only ever come from the git-ignored local config
  (and never leak back into a committed file);
* with no config, only non-sensitive public defaults are used and no account
  details are rendered;
* the committed example config is PII-free.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LEGAL_DIR = ROOT / "legal"
LOCAL_CFG = LEGAL_DIR / "creator_accounts.local.json"
EXAMPLE_CFG = LEGAL_DIR / "creator_accounts.example.json"

from legal.creator_config import (  # noqa: E402
    DEFAULT_FOUNDER_CONTACT,
    DEFAULT_FOUNDER_EMAIL,
    DEFAULT_FUNDING_CHANNELS,
    EXAMPLE_CONFIG_NAME,
    LOCAL_CONFIG_NAME,
    get_founder_contact,
    get_founder_email,
    load_creator_config,
    resolve_config_path,
)
from legal.donations import DonationsManager  # noqa: E402
from legal.contributors import ContributorRegistry  # noqa: E402
from legal.maintainers import MaintainerRegistry  # noqa: E402

GMAIL = re.compile(r"[\w.+-]+@gmail\.com")
PK_IBAN = re.compile(r"PK\d{2}[A-Z]{4}\d{16}")
PK_PHONE = re.compile(r"\+92\d{9,10}|0306-\d{7}")

#: Keys in the local config whose values are sensitive (must never be committed).
SENSITIVE_KEYS = {"email", "email_or_handle", "phone", "mobile", "iban",
                  "account_number", "id", "url"}


def _committed_legal_texts() -> dict[str, str]:
    """Text of every *committed* file in legal/ (the git-ignored local config excluded)."""
    out: dict[str, str] = {}
    for p in sorted(LEGAL_DIR.glob("*")):
        if p.is_file() and p.name != LOCAL_CONFIG_NAME:
            try:
                out[p.name] = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                pass
    return out


def _sensitive_values(node, out: set, key=None) -> None:
    """Collect sensitive string values from the local config (skip _comment)."""
    if isinstance(node, dict):
        for k, v in node.items():
            if str(k).startswith("_"):
                continue
            if k == "funding_channels" and isinstance(v, dict):
                for chan_val in v.values():
                    if isinstance(chan_val, str) and len(chan_val) >= 6:
                        out.add(chan_val)
                continue
            _sensitive_values(v, out, k)
    elif isinstance(node, list):
        for v in node:
            _sensitive_values(v, out, key)
    elif isinstance(node, str) and key in SENSITIVE_KEYS and len(node) >= 6:
        out.add(node)


class TestNoPiiInCommittedSources(unittest.TestCase):
    """The committed source tree must carry no personal / financial data."""

    def test_no_personal_gmail_in_committed_legal_sources(self):
        for name, text in _committed_legal_texts().items():
            self.assertIsNone(GMAIL.search(text),
                              f"{name} contains a personal Gmail address")

    def test_no_pakistani_iban_in_committed_legal_sources(self):
        for name, text in _committed_legal_texts().items():
            self.assertIsNone(PK_IBAN.search(text),
                              f"{name} contains a real-looking PK IBAN")

    def test_no_personal_phone_in_committed_legal_sources(self):
        for name, text in _committed_legal_texts().items():
            self.assertIsNone(PK_PHONE.search(text),
                              f"{name} contains a personal phone number")

    def test_local_config_values_do_not_leak_into_committed_sources(self):
        if not LOCAL_CFG.exists():
            self.skipTest("no local creator config present on this machine")
        cfg = json.loads(LOCAL_CFG.read_text(encoding="utf-8"))
        values: set[str] = set()
        _sensitive_values(cfg, values)
        self.assertTrue(values, "local config should expose some sensitive values")
        texts = _committed_legal_texts()
        for value in values:
            for name, text in texts.items():
                self.assertNotIn(value, text,
                                 f"{name} leaks a sensitive value from the local config")


class TestExampleConfigIsPiiFree(unittest.TestCase):
    def test_example_exists_and_parses(self):
        self.assertTrue(EXAMPLE_CFG.exists())
        data = json.loads(EXAMPLE_CFG.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict)

    def test_example_has_no_real_pii(self):
        text = EXAMPLE_CFG.read_text(encoding="utf-8")
        self.assertIsNone(GMAIL.search(text))
        self.assertIsNone(PK_IBAN.search(text))
        self.assertIsNone(PK_PHONE.search(text))


class TestUnconfiguredDefaults(unittest.TestCase):
    """With no config, only non-sensitive public defaults are used."""

    def test_founder_defaults_are_non_pii(self):
        self.assertNotIn("@gmail.com", DEFAULT_FOUNDER_CONTACT)
        self.assertNotIn("@gmail.com", DEFAULT_FOUNDER_EMAIL)
        self.assertEqual(get_founder_contact({}), DEFAULT_FOUNDER_CONTACT)
        self.assertEqual(get_founder_email({}), DEFAULT_FOUNDER_EMAIL)

    def test_resolve_config_path_none_when_missing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(resolve_config_path(Path(d) / "absent.json"))

    def test_manager_without_config_has_no_accounts(self):
        with tempfile.TemporaryDirectory() as d:
            mgr = DonationsManager(config_path=Path(d) / "absent.json")
            self.assertEqual(mgr.get_creator_accounts(), [])
            self.assertEqual(mgr.get_funding_channels(), DEFAULT_FUNDING_CHANNELS)

    def test_unconfigured_sponsors_md_has_notice_and_no_pii(self):
        with tempfile.TemporaryDirectory() as d:
            mgr = DonationsManager(config_path=Path(d) / "absent.json")
            md = mgr.generate_sponsors_md()
        self.assertIn("not configured in this build", md)
        self.assertNotIn("@gmail.com", md)
        self.assertIsNone(PK_IBAN.search(md))

    def test_founder_contact_is_config_driven(self):
        # The roster's founder contact must come from the config loader, not a
        # hardcoded literal (which is why the source carries no PII).
        founder = ContributorRegistry().get_contributor("Muhammad Umer Yasin (MUmerYasin)")
        self.assertIsNotNone(founder)
        self.assertEqual(founder.email_or_handle, get_founder_contact())

    def test_maintainer_email_is_config_driven(self):
        lead = MaintainerRegistry().get("MUmerYasin")
        self.assertIsNotNone(lead)
        self.assertEqual(lead.email, get_founder_email())


class TestConfiguredBehaviour(unittest.TestCase):
    """A supplied config drives the accounts, channels and founder identity."""

    def _write_cfg(self, d: str) -> Path:
        p = Path(d) / "creator_accounts.local.json"
        p.write_text(json.dumps({
            "founder": {"name": "Test Founder", "email": "founder@example.org",
                        "email_or_handle": "https://example.org/founder"},
            "bank_accounts": [
                {"method": "ExampleBank", "description": "Testland",
                 "iban": "IBAN-EXAMPLE-0000", "mobile": "0000-0000000"},
                {"method": "ExampleLink", "description": "International",
                 "url": "https://example.org/pay"},
            ],
            "funding_channels": {"examplepay": "example@example.org"},
        }), encoding="utf-8")
        return p

    def test_accounts_and_channels_loaded(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = self._write_cfg(d)
            mgr = DonationsManager(config_path=cfg)
            accounts = mgr.get_creator_accounts()
            self.assertEqual(len(accounts), 2)
            self.assertEqual(accounts[0]["iban"], "IBAN-EXAMPLE-0000")
            channels = mgr.get_funding_channels()
            self.assertEqual(channels["examplepay"], "example@example.org")
            # public defaults are still present (merged, not replaced)
            self.assertIn("github_sponsors", channels)

    def test_sponsors_md_renders_configured_account(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = self._write_cfg(d)
            md = DonationsManager(config_path=cfg).generate_sponsors_md()
            self.assertIn("IBAN-EXAMPLE-0000", md)
            self.assertIn("Test Founder", md)
            self.assertNotIn("not configured in this build", md)

    def test_configured_founder_contact_helpers(self):
        cfg = {"founder": {"email": "f@example.org", "email_or_handle": "h@example.org"}}
        self.assertEqual(get_founder_email(cfg), "f@example.org")
        self.assertEqual(get_founder_contact(cfg), "h@example.org")


class TestSourceInvariants(unittest.TestCase):
    """Pin code facts (never cosmetic tags)."""

    def test_donations_uses_the_external_loader(self):
        src = (LEGAL_DIR / "donations.py").read_text(encoding="utf-8")
        self.assertIn("load_creator_config", src)
        self.assertNotIn("PK79NAYA1234503060084827", src)

    def test_contributors_and_maintainers_use_config(self):
        self.assertIn("get_founder_contact", (LEGAL_DIR / "contributors.py").read_text(encoding="utf-8"))
        self.assertIn("get_founder_email", (LEGAL_DIR / "maintainers.py").read_text(encoding="utf-8"))

    def test_gitignore_covers_the_local_config(self):
        gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertTrue("*.local.json" in gi or LOCAL_CONFIG_NAME in gi)

    def test_loader_names(self):
        self.assertEqual(LOCAL_CONFIG_NAME, "creator_accounts.local.json")
        self.assertEqual(EXAMPLE_CONFIG_NAME, "creator_accounts.example.json")
        self.assertEqual(load_creator_config(Path("does-not-exist.json")), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
