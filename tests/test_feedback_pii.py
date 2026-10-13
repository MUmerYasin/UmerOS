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
pytest suite for — `feedback/models.py` PII consent / erasure / attachments.

H79: `FeedbackEntry` persisted submitter PII (name / contact / attachments) with
no opt-in consent gate and no erasure path, and never validated attachment
paths. The fix adds `consent_granted`/`consent_at`/`consent_scope`/`erased_at`
fields, a fail-closed consent gate in `__post_init__` (contact without consent
raises), attachment path validation (`..` / absolute / store-escape refused),
`to_dict(include_pii=False)` redaction, `may_transmit()`, and `erase_pii()` /
`anonymize()`.
"""

import os
import sys

import pytest

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

from feedback.models import FeedbackEntry, FeedbackKind  # noqa: E402


def _make(**kw):
    return FeedbackEntry.create(FeedbackKind.BUG_REPORT, "t", "d", **kw)


# ── consent gate ────────────────────────────────────────────────────────────

def test_contact_without_consent_refused():
    with pytest.raises(ValueError):
        _make(submitter_contact="a@b.com")


def test_contact_with_consent_allowed():
    e = _make(submitter_contact="a@b.com", consent_granted=True)
    assert e.consent_granted is True
    assert e.consent_at is not None
    assert e.may_transmit() is True


def test_anonymous_entry_needs_no_consent():
    e = _make()
    assert e.submitter_contact == ""
    assert e.consent_granted is False
    assert e.may_transmit() is False


# ── attachment path validation ──────────────────────────────────────────────

@pytest.mark.parametrize("bad", ["../../etc/passwd", "/etc/passwd", "a/../../b", "\\windows\\x"])
def test_unsafe_attachment_refused(bad):
    with pytest.raises(ValueError):
        _make(attachments=[bad])


def test_safe_path_and_http_url_allowed():
    e = _make(attachments=["logs/x.txt", "https://github.com/u/r/issues/1"])
    assert e.attachments == ["logs/x.txt", "https://github.com/u/r/issues/1"]


def test_non_http_url_refused():
    with pytest.raises(ValueError):
        _make(attachments=["file:///etc/passwd"])


# ── redaction ───────────────────────────────────────────────────────────────

def test_to_dict_redaction():
    e = _make(submitter_name="Alice", submitter_contact="a@b.com",
              consent_granted=True, attachments=["x.txt"])
    red = e.to_dict(include_pii=False)
    assert red["submitter_name"] == "Anonymous"
    assert red["submitter_contact"] == ""
    assert red["attachments"] == []
    full = e.to_dict()
    assert full["submitter_contact"] == "a@b.com"


# ── erasure ─────────────────────────────────────────────────────────────────

def test_erase_pii_clears_all_pii():
    e = _make(submitter_name="Alice", submitter_contact="a@b.com",
              consent_granted=True, attachments=["x.txt"])
    ret = e.erase_pii()
    assert ret is e
    assert e.submitter_name == "Anonymous"
    assert e.submitter_contact == ""
    assert e.attachments == []
    assert e.consent_granted is False
    assert e.consent_at is None
    assert e.erased_at is not None
    assert e.may_transmit() is False
    # non-PII content survives
    assert e.title == "t" and e.description == "d"


def test_anonymize_is_erase_pii_alias():
    assert FeedbackEntry.anonymize is FeedbackEntry.erase_pii
