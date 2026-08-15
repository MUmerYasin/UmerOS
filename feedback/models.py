"""
UmerOS /feedback -- Feedback Data Models
========================================

Core data structures for structured community feedback, bug reports,
corrections, and feature suggestions.

Appendix G specifies:
  - Subject heading  for email-based feedback identification
  - Categories: corrections, suggestions, questions, bug reports
  - No guarantee of response (volunteer-maintained)

Author: Muhammad Umer Yasin / UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


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

    Mirrors the TLDP Appendix G specification:
      - kind: type of feedback (bug / correction / suggestion / question)
      - subject_tag: "LHFS" subject heading used by TLDP for email triage
      - channel: how the feedback was received
    """
    feedback_id: str
    kind: FeedbackKind
    title: str
    description: str
    submitter_name: str
    submitter_contact: str          # Email, GitHub handle, or anonymous
    channel: str                    # email, github, mailing_list, matrix
    subject_tag: str                # e.g. "LHFS" per TLDP spec
    component: str                  # Which UmerOS subsystem this relates to
    status: FeedbackStatus = FeedbackStatus.NEW
    priority: FeedbackPriority = FeedbackPriority.MEDIUM
    submitted_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    assigned_to: Optional[str] = None
    resolution_note: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    attachments: List[str] = field(default_factory=list)  # Paths or URLs

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
    ) -> "FeedbackEntry":
        """Factory to create a new feedback entry with a generated UUID."""
        return cls(
            feedback_id=str(uuid.uuid4()),
            kind=kind,
            title=title,
            description=description,
            submitter_name=submitter_name,
            submitter_contact=submitter_contact,
            channel=channel,
            subject_tag="LHFS",   # TLDP standard identifier tag
            component=component,
            priority=priority,
            tags=tags or [],
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["status"] = self.status.value
        d["priority"] = self.priority.value
        return d

    def summary(self) -> str:
        return (
            f"[{self.feedback_id[:8]}] [{self.kind.value.upper()}] "
            f"[{self.priority.value.upper()}] [{self.status.value.upper()}] "
            f"{self.title} -- {self.submitter_name} via {self.channel}"
        )
