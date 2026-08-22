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

Support Muhammad Umer Yasin (creator of UmerOS) financially — even buying him a
coffee helps keep UmerOS alive and growing!

Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import enum
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


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
# CREATOR BANK ACCOUNTS - Muhammad Umer Yasin (UmerOS Lead Architect)
# ======================================================================
# If UmerOS has helped you, please consider supporting Umer financially!
# Even buying him a coffee (PKR 300 / $1) keeps this project going.
#
# PAKISTAN (Direct IBAN Transfer):
#   NayaPay (Current Account)
#     IBAN:    PK79NAYA1234503060084827
#     ID:      mumeryasin@nayapay      Mobile: 0306-0084827
#
#   The Bank of Punjab (231 Raiwind Branch)
#     IBAN:    PK53BPUN6010296643300013
#
#   FINCA Microfinance Bank Pakistan
#     IBAN:    PK29FINC0000923060084827   Account: 03060084827
#
#   EasyPaisa
#     IBAN:    PK47TMFB0000000035783567   Mobile: 0306-0084827
#
#   JazzCash
#     IBAN:    PK97JCMA3011923060084827   Mobile: 0306-0084827
#
#   National Bank of Pakistan (1552 Raja Jang Branch)
#     IBAN:    PK05NBPA1552004252285402
#
#   ABHI Wallet
#     IBAN:    PK29FINC0000923060084827
#
#   United Bank Limited / UBL (Branch 1927 Chowk Lalak Jan, Lahore)
#     IBAN:    PK09UNIL0109000276650059
#
# INTERNATIONAL:
#   Payoneer:  Muhammad Umer Yasin | +923140422313 | waumsoftwarehouse@gmail.com
#   Wise:      https://wise.com/pay/me/muhammadumery
# ======================================================================

CREATOR_BANK_ACCOUNTS: List[Dict[str, str]] = [
    {
        "method": "NayaPay",
        "description": "Current Account, Pakistan",
        "iban": "PK79NAYA1234503060084827",
        "id": "mumeryasin@nayapay",
        "mobile": "0306-0084827",
    },
    {
        "method": "The Bank of Punjab",
        "description": "231 Raiwind Branch, Pakistan",
        "iban": "PK53BPUN6010296643300013",
    },
    {
        "method": "FINCA Microfinance Bank",
        "description": "Pakistan",
        "iban": "PK29FINC0000923060084827",
        "account_number": "03060084827",
    },
    {
        "method": "EasyPaisa",
        "description": "Pakistan",
        "iban": "PK47TMFB0000000035783567",
        "mobile": "0306-0084827",
    },
    {
        "method": "JazzCash",
        "description": "Pakistan",
        "iban": "PK97JCMA3011923060084827",
        "mobile": "0306-0084827",
    },
    {
        "method": "National Bank of Pakistan",
        "description": "1552 Raja Jang Branch, Pakistan",
        "iban": "PK05NBPA1552004252285402",
    },
    {
        "method": "ABHI Wallet",
        "description": "Pakistan",
        "iban": "PK29FINC0000923060084827",
    },
    {
        "method": "United Bank Limited (UBL)",
        "description": "Branch 1927, Chowk Lalak Jan, Lahore, Pakistan",
        "iban": "PK09UNIL0109000276650059",
    },
    {
        "method": "Payoneer",
        "description": "International",
        "name": "Muhammad Umer Yasin",
        "phone": "+923140422313",
        "email": "waumsoftwarehouse@gmail.com",
    },
    {
        "method": "Wise",
        "description": "International",
        "url": "https://wise.com/pay/me/muhammadumery",
    },
]


class DonationsManager:
    """Manages donation records, recognition tiers, and funding channels."""

    def __init__(self) -> None:
        self._donations: List[DonationRecord] = []
        self._funding_channels: Dict[str, str] = {
            "wise": "https://wise.com/pay/me/muhammadumery",
            "payoneer": "waumsoftwarehouse@gmail.com | +923140422313",
            "nayapay": "mumeryasin@nayapay  (0306-0084827)",
            "jazzcash": "0306-0084827",
            "easypaisa": "0306-0084827",
            "github_sponsors": "https://github.com/sponsors/umeros",
            "opencollective": "https://opencollective.com/umeros",
            "direct_grant": "grants@umeros.local",
        }

    def get_creator_accounts(self) -> List[Dict[str, str]]:
        """Returns all bank accounts for creator Muhammad Umer Yasin."""
        return list(CREATOR_BANK_ACCOUNTS)

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
        """Generates markdown sponsor wall with full creator bank details."""
        lines = [
            "# UmerOS Project — Support & Sponsorship",
            "",
            "UmerOS is a free, open-source, Python-first quantum-native operating system",
            "built by **Muhammad Umer Yasin**, a solo developer from Pakistan.",
            "If this project brings you value, please consider supporting Umer financially",
            "— even buying him a coffee makes a real difference!",
            "",
            "---",
            "",
            "## Support Muhammad Umer Yasin",
            "",
            "### International Payments",
            "",
            "| Method | Details |",
            "|--------|---------|",
            "| **Wise** | https://wise.com/pay/me/muhammadumery |",
            "| **Payoneer** | Muhammad Umer Yasin &nbsp; `+923140422313` &nbsp; `waumsoftwarehouse@gmail.com` |",
            "",
            "### Pakistan Bank Accounts (Direct IBAN Transfer)",
            "",
            "| Bank / Wallet | IBAN | Extra Details |",
            "|---------------|------|---------------|",
            "| **NayaPay** (Current Account) | `PK79NAYA1234503060084827` | `mumeryasin@nayapay` &nbsp; 0306-0084827 |",
            "| **The Bank of Punjab** (231 Raiwind Branch) | `PK53BPUN6010296643300013` | — |",
            "| **FINCA Microfinance Bank Pakistan** | `PK29FINC0000923060084827` | Account: 03060084827 |",
            "| **EasyPaisa** | `PK47TMFB0000000035783567` | 0306-0084827 |",
            "| **JazzCash** | `PK97JCMA3011923060084827` | 0306-0084827 |",
            "| **National Bank of Pakistan** (1552 Raja Jang Branch) | `PK05NBPA1552004252285402` | — |",
            "| **ABHI Wallet** | `PK29FINC0000923060084827` | — |",
            "| **United Bank Limited / UBL** (Branch 1927, Chowk Lalak Jan, Lahore) | `PK09UNIL0109000276650059` | — |",
            "",
            "---",
            "",
            "## Official Project Funding Channels",
            "",
        ]
        for k, v in self._funding_channels.items():
            lines.append(f"- **{k.replace('_', ' ').title()}:** {v}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Recognized Project Sponsors & Backers")
        lines.append("")
        if not self._donations:
            lines.append("> *No public sponsorships registered yet. Be the first to support UmerOS!*")
        else:
            for d in self._donations:
                note_str = f" -- \"{d.public_note}\"" if d.public_note else ""
                lines.append(f"- **{d.donor_name}** [{d.tier.value}]{note_str}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("> *Thank you for supporting open-source Pakistani innovation!*")
        lines.append("> --- Muhammad Umer Yasin")
        return "\n".join(lines)

    def print_donation_appeal(self) -> None:
        """Prints a terminal-friendly donation appeal for Muhammad Umer Yasin."""
        print()
        print("=" * 65)
        print("  SUPPORT UMEROS -- BUY UMER A COFFEE!")
        print("=" * 65)
        print("  UmerOS is built by Muhammad Umer Yasin, a solo developer")
        print("  from Pakistan. Your support -- big or small -- directly")
        print("  fuels innovation and keeps this project going.")
        print()
        print("  INTERNATIONAL:")
        print("    Wise     -> https://wise.com/pay/me/muhammadumery")
        print("    Payoneer -> +923140422313 | waumsoftwarehouse@gmail.com")
        print()
        print("  PAKISTAN (Direct IBAN Transfer):")
        for acc in CREATOR_BANK_ACCOUNTS:
            if "iban" in acc:
                method = acc["method"]
                iban = acc["iban"]
                extra = acc.get("mobile") or acc.get("id") or acc.get("account_number") or ""
                extra_str = f"  ({extra})" if extra else ""
                print(f"    {method:<40} {iban}{extra_str}")
        print()
        print("  Even PKR 300 ($1) helps! Thank you.")
        print("  -- Muhammad Umer Yasin, Pakistan")
        print("=" * 65)
        print()
