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
UmerOS Legal & Compliance — Donations & Sustainability Subsystem 
==================================================================================

Manages open-source project funding, donor recognition tiers, grant allocations,
and sustainability channels.

Sensitive creator/donor details (bank IBANs, phone numbers, personal e-mail and
payment links) are **not** hardcoded here — they are loaded at runtime from a
git-ignored external config (see :mod:`legal.creator_config`).  When no
config is present, only the non-sensitive public funding channels are shown.

Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import enum
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .creator_config import DEFAULT_FUNDING_CHANNELS, load_creator_config


class DonationTier(str, enum.Enum):
    PLATINUM = "Platinum Sponsor (No Limites)"
    GOLD = "Gold Sponsor ($2,500+)"
    SILVER = "Silver Sponsor ($50+)"
    BACKER = "Project Backer ($10+)"
    COMMUNITY = "Community Supporter ($1+)"


@dataclass
class DonationRecord:
    """Record of financial or infrastructure support."""
    donor_name: str
    tier: DonationTier
    amount_usd: float
    channel: str  # GitHub Sponsors, OpenCollective, Crypto, Direct Grant
    date: float = field(default_factory=time.time)
    public_note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["tier"] = self.tier.value
        return d


# ======================================================================
# Creator bank accounts / funding channels
# ======================================================================
# Sensitive personal & financial data (bank IBANs, phone numbers, personal
# e-mail addresses) is NOT committed to source control.  It is loaded at
# runtime from a git-ignored JSON file — see ``legal/creator_config.py`` and
# the committed schema ``creator_accounts.example.json``.  When no config is
# present, only the non-sensitive public channels are shown.

#: Backwards-compatible module snapshot of the configured creator accounts
#: (empty when unconfigured).  Prefer :meth:`DonationsManager.get_creator_accounts`.
CREATOR_BANK_ACCOUNTS: List[Dict[str, str]] = list(
    load_creator_config().get("bank_accounts", []) or []
)


class DonationsManager:
    """Manages donation records, recognition tiers, and funding channels."""

    def __init__(self, config_path: Optional[Path | str] = None) -> None:
        # PII lives in a git-ignored external file; nothing sensitive is
        # hardcoded here.  Public channels are always available.
        self._cfg: Dict[str, Any] = load_creator_config(config_path)
        self._donations: List[DonationRecord] = []
        self._bank_accounts: List[Dict[str, str]] = list(
            self._cfg.get("bank_accounts", []) or []
        )
        channels: Dict[str, str] = dict(DEFAULT_FUNDING_CHANNELS)
        channels.update(self._cfg.get("funding_channels", {}) or {})
        self._funding_channels = channels

    def get_creator_accounts(self) -> List[Dict[str, str]]:
        """Returns the configured creator accounts (empty when unconfigured)."""
        return list(self._bank_accounts)

    def _founder_name(self) -> str:
        return str((self._cfg.get("founder") or {}).get("name") or "the UmerOS maintainers")

    def add_donation(
        self,
        donor_name: str,
        amount_usd: float,
        channel: str = "opencollective",
        public_note: str = "",
    ) -> DonationRecord:
        """Registers a new donation and assigns tier."""
        if amount_usd >= 10000:
            tier = DonationTier.PLATINUM
        elif amount_usd >= 2500:
            tier = DonationTier.GOLD
        elif amount_usd >= 500:
            tier = DonationTier.SILVER
        elif amount_usd >= 100:
            tier = DonationTier.BACKER
        else:
            tier = DonationTier.COMMUNITY

        rec = DonationRecord(
            donor_name=donor_name,
            tier=tier,
            amount_usd=amount_usd,
            channel=channel,
            public_note=public_note,
        )
        self._donations.append(rec)
        return rec

    def list_donations(self) -> List[DonationRecord]:
        return list(self._donations)

    def get_funding_channels(self) -> Dict[str, str]:
        return dict(self._funding_channels)

    def generate_sponsors_md(self) -> str:
        """Generates the markdown sponsor wall from the configured channels (H137)."""
        international = [a for a in self._bank_accounts if not a.get("iban")]
        domestic = [a for a in self._bank_accounts if a.get("iban")]

        lines = [
            "# UmerOS Project — Support & Sponsorship",
            "",
            "UmerOS is a free, open-source, Python-first quantum-native operating system.",
            f"If this project brings you value, please consider supporting {self._founder_name()}",
            "financially — even buying a coffee makes a real difference!",
            "",
            "---",
            "",
        ]

        if international:
            lines += ["## International Payments", "", "| Method | Details |", "|--------|---------|"]
            for a in international:
                detail = a.get("url") or " &nbsp; ".join(
                    str(x) for x in (a.get("name"), a.get("phone"), a.get("email")) if x
                )
                lines.append(f"| **{a.get('method', '')}** | {detail} |")
            lines.append("")

        if domestic:
            lines += [
                "## Bank Accounts (Direct IBAN Transfer)",
                "",
                "| Bank / Wallet | IBAN | Extra Details |",
                "|---------------|------|---------------|",
            ]
            for a in domestic:
                extra = a.get("id") or a.get("mobile") or a.get("account_number") or "—"
                lines.append(
                    f"| **{a.get('method', '')}** ({a.get('description', '')}) | "
                    f"`{a.get('iban', '')}` | {extra} |"
                )
            lines.append("")

        if not self._bank_accounts:
            lines += [
                "> *Direct donation details are not configured in this build.*",
                "> *Maintainers: copy `legal/creator_accounts.example.json` to "
                "`legal/creator_accounts.local.json` (git-ignored) to enable them.*",
                "",
            ]

        lines += ["---", "", "## Official Project Funding Channels", ""]
        for k, v in self._funding_channels.items():
            lines.append(f"- **{k.replace('_', ' ').title()}:** {v}")
        lines += ["", "---", "", "## Recognized Project Sponsors & Backers", ""]
        if not self._donations:
            lines.append("> *No public sponsorships registered yet. Be the first to support UmerOS!*")
        else:
            for d in self._donations:
                note_str = f" -- \"{d.public_note}\"" if d.public_note else ""
                lines.append(f"- **{d.donor_name}** [{d.tier.value}]{note_str}")
        lines += ["", "---", "", "> *Thank you for supporting open-source innovation!*"]
        return "\n".join(lines)

    def print_donation_appeal(self) -> None:
        """Prints a terminal-friendly donation appeal from the configured channels (H137)."""
        international = [a for a in self._bank_accounts if not a.get("iban")]
        domestic = [a for a in self._bank_accounts if a.get("iban")]
        print()
        print("=" * 65)
        print("  SUPPORT UMEROS -- BUY A COFFEE!")
        print("=" * 65)
        print(f"  UmerOS is built by {self._founder_name()}. Your support -- big or")
        print("  small -- directly fuels innovation and keeps this project going.")
        print()
        if international:
            print("  INTERNATIONAL:")
            for a in international:
                detail = a.get("url") or " | ".join(
                    str(x) for x in (a.get("name"), a.get("phone"), a.get("email")) if x
                )
                print(f"    {a.get('method', ''):<10} -> {detail}")
            print()
        if domestic:
            print("  PAKISTAN (Direct IBAN Transfer):")
            for acc in domestic:
                extra = acc.get("mobile") or acc.get("id") or acc.get("account_number") or ""
                extra_str = f"  ({extra})" if extra else ""
                print(f"    {acc.get('method', ''):<40} {acc.get('iban', '')}{extra_str}")
            print()
        if not self._bank_accounts:
            print("  (Direct donation details are not configured in this build.)")
            print()
        print("  Even a small amount helps! Thank you.")
        print("=" * 65)
        print()
