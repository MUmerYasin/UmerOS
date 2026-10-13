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
UmerOS /feedback -- Feedback Data Models  [TODAY]
========================================

Core data structures for structured community feedback, bug reports,
corrections, and feature suggestions.

Appendix G specifies:
  - Subject heading  for email-based feedback identification
  - Categories: corrections, suggestions, questions, bug reports
  - No guarantee of response (volunteer-maintained)

Author: Muhammad Umer Yasin / UmerOS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import enum
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Shared path-traversal guard (CWE-22) for attachment paths.
try:
    from core.path_guard import PathTraversalError, safe_join
except Exception:  # pragma: no cover - standalone fallback
    import sys as _sys

    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in _sys.path:
        _sys.path.insert(0, _proj)
    from core.path_guard import PathTraversalError, safe_join

# Root under which attachment *paths* (not URLs) must stay.
FEEDBACK_STORE_ROOT = os.path.expanduser("~/.umeros/feedback_store")

_URL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*://")
_ALLOWED_URL_SCHEMES = ("http", "https")


def _validate_attachment(attachment: str) -> str:
    """Validate an attachment entry (a path or an http(s) URL). [FIX H79]

    Rejects absolute paths, ``..`` traversal, and any path that escapes
    :data:`FEEDBACK_STORE_ROOT`; URLs are limited to http/https.

    Raises:
        ValueError: if the attachment is not a safe path or an allowed URL.
    """
    if not isinstance(attachment, str) or not attachment.strip():
        raise ValueError("attachment must be a non-empty string")
    value = attachment.strip()
    if _URL_RE.match(value):
        scheme = value.split("://", 1)[0].lower()
        if scheme not in _ALLOWED_URL_SCHEMES:
            raise ValueError(f"refusing non-http(s) attachment URL: {attachment!r}")
        return attachment
    if Path(value).is_absolute() or value.startswith(("\\", "/")):
        raise ValueError(f"refusing absolute attachment path: {attachment!r}")
    try:
        safe_join(FEEDBACK_STORE_ROOT, value)
    except PathTraversalError as exc:
        raise ValueError(
            f"refusing attachment path escaping the feedback store: {attachment!r}"
        ) from exc
    return attachment


class FeedbackKind(str, enum.Enum):
    """Classification of community feedback submissions."""
    BUG_REPORT     = "bug_report"       # Defect or incorrect behaviour
    CORRECTION     = "correction"       # Factual / documentation error
    SUGGESTION     = "suggestion"       # Enhancement or new feature proposal
    QUESTION       = "question"         # User question requiring clarification
    DOCUMENTATION  = "documentation"    # Docs improvement request
    SECURITY       = "security"         # Security vulnerability disclosure
    PERFORMANCE    = "performance"      # Performance regression or bottleneck
    COMPATIBILITY  = "compatibility"    # Platform / version compatibility issue


class FeedbackStatus(str, enum.Enum):
    """Lifecycle state of a feedback entry through triage and resolution."""
    NEW         = "new"         # Freshly submitted, not yet triaged
    TRIAGED     = "triaged"     # Reviewed and categorised
    IN_PROGRESS = "in_progress" # Actively being worked on
    RESOLVED    = "resolved"    # Fix or answer delivered
    CLOSED      = "closed"      # No further action needed
    DUPLICATE   = "duplicate"   # Duplicate of an existing entry
    WONT_FIX    = "wont_fix"    # Valid but intentionally not addressed


class FeedbackPriority(str, enum.Enum):
    """Priority level for scheduling attention."""
    CRITICAL = "critical"   # Must fix before next release
    HIGH     = "high"       # Fix soon
    MEDIUM   = "medium"     # Normal backlog
    LOW      = "low"        # Nice to have


@dataclass
class FeedbackEntry:
    """
    A structured record of a single community feedback submission.

    Mirrors the Appendix G specification:
      - kind: type of feedback (bug / correction / suggestion / question)
      - subject_tag: "LHFS" subject heading used for email triage
      - channel: how the feedback was received
    """
    feedback_id: str
    kind: FeedbackKind
    title: str
    description: str
    submitter_name: str
    submitter_contact: str          # Email, GitHub handle, or anonymous
    channel: str                    # email, github, mailing_list, matrix
    subject_tag: str                # e.g. "LHFS" 
    component: str                  # Which UmerOS subsystem this relates to
    status: FeedbackStatus = FeedbackStatus.NEW
    priority: FeedbackPriority = FeedbackPriority.MEDIUM
    submitted_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    assigned_to: Optional[str] = None
    resolution_note: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    attachments: List[str] = field(default_factory=list)  # Paths or URLs

    # Consent / erasure modelling (§4.3, GDPR/ISO, H18).
    consent_granted: bool = False
    consent_at: Optional[float] = None
    consent_scope: str = ""
    erased_at: Optional[float] = None

    def __post_init__(self) -> None:
        """Enforce the consent gate + validate attachment paths. [FIX H79]

        Raises:
            ValueError: if submitter contact (PII) is present without consent,
                or an attachment is an unsafe path / disallowed URL.
        """
        if self.submitter_contact and not self.consent_granted:
            raise ValueError(
                "refusing to store submitter contact (PII) without explicit "
                "consent (§4.3/H18); pass consent_granted=True"
            )
        for attachment in self.attachments:
            _validate_attachment(attachment)

    @classmethod
    def create(
        cls,
        kind: FeedbackKind,
        title: str,
        description: str,
        submitter_name: str = "Anonymous",
        submitter_contact: str = "",
        channel: str = "github",
        component: str = "general",
        priority: FeedbackPriority = FeedbackPriority.MEDIUM,
        tags: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
        consent_granted: bool = False,
        consent_scope: str = "",
    ) -> "FeedbackEntry":
        """Factory to create a new feedback entry with a generated UUID.

        ``consent_granted`` is required whenever ``submitter_contact``
        (PII) is supplied; ``attachments`` are path-validated by
        :func:`_validate_attachment`.
        """
        return cls(
            feedback_id=str(uuid.uuid4()),
            kind=kind,
            title=title,
            description=description,
            submitter_name=submitter_name,
            submitter_contact=submitter_contact,
            channel=channel,
            subject_tag="LHFS",   # standard identifier tag
            component=component,
            priority=priority,
            tags=tags or [],
            attachments=attachments or [],
            consent_granted=consent_granted,
            consent_at=time.time() if consent_granted else None,
            consent_scope=consent_scope,
        )

    def to_dict(self, include_pii: bool = True) -> Dict[str, Any]:
        """Serialize the entry.

        Args:
            include_pii: When False, redact ``submitter_name``,
                ``submitter_contact`` and ``attachments`` (safe for logging,
                analytics, or third-party export).

        Returns:
            A JSON-serializable dict.
        """
        d = asdict(self)
        d["kind"] = self.kind.value
        d["status"] = self.status.value
        d["priority"] = self.priority.value
        if not include_pii:
            d["submitter_name"] = "Anonymous"
            d["submitter_contact"] = ""
            d["attachments"] = []
        return d

    def may_transmit(self) -> bool:
        """Whether outbound channel egress is permitted. 

        The (planned) collector/channels must *additionally* check
        :meth:`ai.consent.AIGovernance.check_consent` for the target channel
        before any egress, so that egress is never silent.

        Returns:
            True only when the submitter granted explicit consent.
        """
        return bool(self.consent_granted)

    def erase_pii(self) -> "FeedbackEntry":
        """Irreversibly erase submitter PII (GDPR right to erasure).

        Clears ``submitter_name`` / ``submitter_contact`` / ``attachments`` and
        the consent record, then stamps ``erased_at``. The non-PII content
        (title / description / kind / status) is retained so the feedback item
        itself is not lost.

        Returns:
            self, for chaining.
        """
        self.submitter_name = "Anonymous"
        self.submitter_contact = ""
        self.attachments = []
        self.consent_granted = False
        self.consent_at = None
        self.consent_scope = ""
        self.erased_at = time.time()
        self.updated_at = self.erased_at
        return self

    # GDPR terminology alias for :meth:`erase_pii`.
    anonymize = erase_pii

    def summary(self) -> str:
        return (
            f"[{self.feedback_id[:8]}] [{self.kind.value.upper()}] "
            f"[{self.priority.value.upper()}] [{self.status.value.upper()}] "
            f"{self.title} -- {self.submitter_name} via {self.channel}"
        )
