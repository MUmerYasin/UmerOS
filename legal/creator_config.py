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
UmerOS Legal & Compliance — Creator / Donor Configuration Loader [TODAY]
========================================================================

Sensitive personal and financial data — bank IBANs, phone numbers and personal
e-mail addresses — is **not** committed to source control.  It is
loaded at runtime from a git-ignored JSON file so the public source tree carries
no PII.

Resolution order for the config path:

1. the ``UMEROS_CREATOR_CONFIG`` environment variable (explicit override);
2. ``<legal>/creator_accounts.local.json`` (git-ignored local file).

When neither exists, only non-sensitive public defaults are used and the
donation appeal renders a short "not configured" notice.  A committed
``creator_accounts.example.json`` documents the schema.

Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger("UmerOS.Legal.CreatorConfig")

#: Explicit override for the creator-config file path.
CONFIG_ENV_VAR = "UMEROS_CREATOR_CONFIG"

#: Git-ignored local file (next to this module) holding the real values.
LOCAL_CONFIG_NAME = "creator_accounts.local.json"

#: Committed, PII-free template documenting the schema.
EXAMPLE_CONFIG_NAME = "creator_accounts.example.json"

#: Non-sensitive, public funding channels — safe to commit (no PII).
DEFAULT_FUNDING_CHANNELS: Dict[str, str] = {
    "github_sponsors": "https://github.com/sponsors/umeros",
    "opencollective": "https://opencollective.com/umeros",
    "direct_grant": "grants@umeros.local",
}

#: Non-sensitive fallbacks used when no founder identity is configured.
DEFAULT_FOUNDER_CONTACT = "https://github.com/MUmerYasin"
DEFAULT_FOUNDER_EMAIL = "maintainers@umeros.local"


def default_config_path() -> Path:
    """Path of the git-ignored local config file (next to this module)."""
    return Path(__file__).resolve().parent / LOCAL_CONFIG_NAME


def example_config_path() -> Path:
    """Path of the committed, PII-free example config."""
    return Path(__file__).resolve().parent / EXAMPLE_CONFIG_NAME


def resolve_config_path(path: Optional[Path | str] = None) -> Optional[Path]:
    """Return the config file to load, or ``None`` when none is configured.

    Precedence: explicit ``path`` > ``UMEROS_CREATOR_CONFIG`` > local file.
    """
    if path is not None:
        p = Path(path)
        return p if p.exists() else None
    env = os.environ.get(CONFIG_ENV_VAR)
    if env:
        p = Path(env)
        return p if p.exists() else None
    p = default_config_path()
    return p if p.exists() else None


def load_creator_config(path: Optional[Path | str] = None) -> Dict[str, Any]:
    """Load the creator/donor configuration (PII) from the external file.

    Returns an empty mapping when no config is present or it cannot be parsed —
    callers then fall back to non-sensitive public defaults.
    """
    p = resolve_config_path(path)
    if p is None:
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("Could not read creator config %s: %s", p, exc)
        return {}
    if not isinstance(data, dict):
        log.warning("Creator config %s must be a JSON object", p)
        return {}
    return data


def _founder_field(field: str, config: Optional[Dict[str, Any]], default: str) -> str:
    cfg = config if config is not None else load_creator_config()
    founder = cfg.get("founder") or {}
    value = str(founder.get(field) or "").strip()
    return value or default


def get_founder_contact(config: Optional[Dict[str, Any]] = None) -> str:
    """Public contact for the founder — configured value or a non-PII default."""
    return _founder_field("email_or_handle", config, DEFAULT_FOUNDER_CONTACT)


def get_founder_email(config: Optional[Dict[str, Any]] = None) -> str:
    """Founder e-mail — configured value or a non-PII project default."""
    return _founder_field("email", config, DEFAULT_FOUNDER_EMAIL)
