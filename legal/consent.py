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
UmerOS Legal & Compliance — Cryptographic Consent Gate & Audit Ledger
=====================================================================

Implements the mandatory legal liability waiver consent gate, user verification,
and cryptographic audit trail required by the UmerOS Master Engineering Blueprint.

Legal Mandate:
--------------
"Every installer flow and high-risk operation MUST display a legal liability
waiver and require explicit user consent ('I AGREE') before proceeding."

Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import socket
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from disclaimer import DisclaimerNotice, DisclaimerRegistry

log = logging.getLogger("UmerOS.Legal.Consent")

DEFAULT_LEDGER_PATH = Path("F:/Pension Person Details/UmerOS/var/lib/umeros/consent_ledger.json") if os.name == "nt" else Path("/var/lib/umeros/consent_ledger.json")


@dataclass
class ConsentRecord:
    """Cryptographically verifiable record of user legal consent."""
    disclaimer_key: str
    user_name: str
    hostname: str
    machine_id: str
    agreed_at: float
    disclaimer_version: str
    consent_token: str
    status: str = "GRANTED"  # GRANTED, REVOKED, EXPIRED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConsentRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def get_machine_fingerprint() -> str:
    """Generates a stable hardware / system fingerprint string."""
    raw = f"{platform.node()}:{platform.machine()}:{platform.processor()}:{platform.system()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class ConsentGateError(Exception):
    """Raised when an operation is attempted without valid user consent."""
    pass


class ConsentManager:
    """Manages user legal consent, verification, and audit logging."""

    def __init__(self, ledger_path: Optional[Path | str] = None) -> None:
        self.ledger_path = Path(ledger_path or DEFAULT_LEDGER_PATH).resolve()
        self._ledger: Dict[str, ConsentRecord] = {}
        self.load_ledger()

    def load_ledger(self) -> None:
        """Loads consent records from disk."""
        if not self.ledger_path.exists():
            return
        try:
            with open(self.ledger_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    for k, rec in data.items():
                        if isinstance(rec, dict):
                            self._ledger[k] = ConsentRecord.from_dict(rec)
        except Exception as e:
            log.warning(f"Could not load consent ledger from {self.ledger_path}: {e}")

    def save_ledger(self) -> None:
        """Saves consent records to disk."""
        try:
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            data = {k: rec.to_dict() for k, rec in self._ledger.items()}
            with open(self.ledger_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True)
        except Exception as e:
            log.error(f"Failed to write consent ledger to {self.ledger_path}: {e}")

    def has_consented(self, disclaimer_key: str = "general", version: Optional[str] = None) -> bool:
        """Checks whether valid consent exists for the specified disclaimer."""
        rec = self._ledger.get(disclaimer_key)
        if not rec or rec.status != "GRANTED":
            return False

        if version and rec.disclaimer_version != version:
            return False  # Requires re-consent on version change

        return True

    def grant_consent(
        self,
        disclaimer_key: str = "general",
        user_response: str = "I AGREE",
        user_name: Optional[str] = None,
    ) -> ConsentRecord:
        """
        Grants explicit legal consent and signs the audit record.
        """
        if user_response.strip().upper() != "I AGREE":
            raise ValueError(f"Explicit consent rejected: Expected 'I AGREE', got '{user_response}'")

        notice = DisclaimerRegistry.get_notice(disclaimer_key)
        now = time.time()
        username = user_name or os.environ.get("USERNAME") or os.environ.get("USER") or "admin"
        host = socket.gethostname()
        mach_id = get_machine_fingerprint()

        # Generate cryptographic consent token
        payload = f"{disclaimer_key}:{username}:{host}:{mach_id}:{notice.version}:{now}:{notice.full_text}"
        token = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        record = ConsentRecord(
            disclaimer_key=disclaimer_key,
            user_name=username,
            hostname=host,
            machine_id=mach_id,
            agreed_at=now,
            disclaimer_version=notice.version,
            consent_token=token,
            status="GRANTED",
        )

        self._ledger[disclaimer_key] = record
        self.save_ledger()
        return record

    def revoke_consent(self, disclaimer_key: str = "general") -> bool:
        """Revokes previously granted consent."""
        if disclaimer_key in self._ledger:
            self._ledger[disclaimer_key].status = "REVOKED"
            self.save_ledger()
            return True
        return False

    def require_consent_interactive(
        self,
        disclaimer_key: str = "installer",
        dry_run: bool = False,
        allow_non_interactive: bool = False,
    ) -> bool:
        """
        Interactive legal-consent gate (FAIL-CLOSED).

        Consent is granted ONLY when one of:
          * the user is on a TTY and explicitly types "I AGREE", or
          * `allow_non_interactive=True` is passed by a caller that has already
            obtained consent out-of-band (e.g. a CI job given `--i-agree`).

        It NEVER auto-grants in dry-run or non-TTY environments — that would
        bypass the mandatory liability-waiver gate (same fail-open family as
        H29/H99). The default `allow_non_interactive=False` keeps it closed.
        """
        notice = DisclaimerRegistry.get_notice(disclaimer_key)

        if dry_run:
            # [FIX H131] Dry-run simulates the flow but MUST NOT record legal consent.
            print("\n" + "=" * 65)
            print(f"       {notice.title.upper()} (DRY-RUN — no consent recorded)")
            print("=" * 65)
            print(notice.full_text)
            print("=" * 65)
            print("[CONSENT] Dry-run mode: NO consent was granted. Re-run without --dry-run to grant.\n")
            return False

        if sys.stdin.isatty():
            print("\n" + "=" * 65)
            print(f"       {notice.title.upper()}")
            print("=" * 65)
            print(notice.full_text)
            print("=" * 65 + "\n")
            resp = input("Type 'I AGREE' to accept and proceed: ").strip()
            if resp.upper() == "I AGREE":
                self.grant_consent(disclaimer_key=disclaimer_key, user_response="I AGREE")
                print("✓ Legal consent recorded successfully.\n")
                return True
            print("✗ Consent declined. Operation aborted.\n")
            return False

        # [FIX H131] Non-interactive / headless: fail CLOSED. Auto-granting the
        # liability waiver in automation is the exact bypass this gate exists to
        # prevent. Require explicit opt-in, otherwise abort with a clear error.
        if not allow_non_interactive:
            raise ConsentGateError(
                f"Refusing to grant consent for '{disclaimer_key}' non-interactively. "
                "A TTY is required to capture an explicit 'I AGREE', or pass "
                "allow_non_interactive=True when consent was obtained out-of-band."
            )
        self.grant_consent(disclaimer_key=disclaimer_key, user_response="I AGREE")
        return True

    def list_consents(self) -> Dict[str, ConsentRecord]:
        """Returns all recorded consents."""
        return dict(self._ledger)
