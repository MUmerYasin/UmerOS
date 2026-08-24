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
Umer OS — AI Governance / Consent Gate  [TODAY]
================================================
Fail-closed privacy gate consulted before ANY user data leaves the
device. This is the enforcement layer for review Hotspot H18: online
providers MUST call :meth:`AIGovernance.check_consent` (or be routed
through :mod:`ai.assistant_service`, which does) before a prompt is
transmitted.

Ledger format (~/.umeros/ai_state/consent.json):
    {
      "grants": {
        "openai": {"granted": true, "ts": 1730000000.0,
                    "scope": "prompts", "note": "..."}
      },
      "denials": {...}
    }

Rules:
  * Default-DENY. No entry == not consented.
  * ``revoke`` deletes the grant and records a denial.
  * The ledger is human-readable JSON so users can audit it.

Author:  Umer OS Project
License: GPLv3
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Dict, Optional

log = logging.getLogger("UmerOS.AI.Consent")

_STATE_DIR = os.environ.get(
    "UMEROS_AI_STATE_DIR",
    os.path.join(os.path.expanduser("~"), ".umeros", "ai_state"),
)
_LEDGER_FILE = os.path.join(_STATE_DIR, "consent.json")


class AIGovernance:
    """Thread-safe, fail-closed consent ledger for AI egress."""

    def __init__(self, ledger_path: Optional[str] = None) -> None:
        self._path = ledger_path or _LEDGER_FILE
        self._lock = threading.Lock()
        self._ledger: Dict[str, dict] = {"grants": {}, "denials": {}}
        self._load()

    # ── persistence ────────────────────────────────────────────────────

    def _load(self) -> None:
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    self._ledger["grants"] = data.get("grants", {}) or {}
                    self._ledger["denials"] = data.get("denials", {}) or {}
                log.info("Consent ledger loaded (%d grants).",
                         len(self._ledger["grants"]))
        except Exception as exc:  # noqa: BLE001
            log.warning("Consent ledger unreadable (%s); starting clean.", exc)

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._ledger, fh, indent=2)
            os.replace(tmp, self._path)
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to save consent ledger: %s", exc)

    # ── queries ────────────────────────────────────────────────────────

    def check_consent(self, provider_id: str) -> bool:
        """Return True only when an explicit, recorded grant exists.

        Fail-CLOSED: unknown provider / missing file / corrupt entry all
        return False.
        """
        with self._lock:
            grant = self._ledger["grants"].get(provider_id)
            return bool(grant and grant.get("granted") is True)

    def get_grant(self, provider_id: str) -> Optional[dict]:
        with self._lock:
            return self._ledger["grants"].get(provider_id)

    def list_consents(self) -> Dict[str, dict]:
        """Snapshot of grants + denials for UI rendering."""
        with self._lock:
            return {
                "grants": {k: dict(v) for k, v in self._ledger["grants"].items()},
                "denials": {k: dict(v) for k, v in self._ledger["denials"].items()},
            }

    # ── mutations ──────────────────────────────────────────────────────

    def grant_consent(self, provider_id: str, note: str = "") -> bool:
        with self._lock:
            self._ledger["grants"][provider_id] = {
                "granted": True,
                "ts": time.time(),
                "scope": "prompts+context",
                "note": note[:200],
            }
            self._ledger["denials"].pop(provider_id, None)
            self._save()
        log.info("Consent GRANTED for provider '%s'.", provider_id)
        return True

    def revoke_consent(self, provider_id: str) -> bool:
        with self._lock:
            self._ledger["grants"].pop(provider_id, None)
            self._ledger["denials"][provider_id] = {
                "revoked_ts": time.time(),
            }
            self._save()
        log.info("Consent REVOKED for provider '%s'.", provider_id)
        return True


# Module-level singleton used by assistant service + server.
governance = AIGovernance()
