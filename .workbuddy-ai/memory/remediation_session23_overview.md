# UmerOS Remediation — Session 23 Overview (legal/ consent + licensing)

**Cluster:** `legal/` RED hotspots — H128, H129, H130, H131, H135
**Date:** 2026-08-24 · **Status:** CLOSED · Full suite: **1460 passed, 0 failures, 0 errors**

---

## What was wrong

| ID | Severity | Finding | Fix |
|----|----------|--------|-----|
| **H128** | 🔴 | License framework contradicted the GPL-3.0 canonical decision (H7). `README.md:40` still described the project as multi-license Apache-2.0 / GPL-2.0 / MIT. | Tightened `licenses.py` docstring to "GPL-3.0-exclusive …"; `README.md:40` now says "GPL-3.0 exclusive license enforcement". (`get_license_text` already raised on non-GPL — code was already correct.) `# [FIX H128]` |
| **H129** | 🔴 | `scan_directory` license audit was fail-open — a loose `"GPL-3.0"` substring let any prose mention pass as compliant. | Removed the loose substring match. A file is now compliant ONLY with an explicit declaration: canonical GPL-3.0 header, `License: GPL-3.0`, or an SPDX id (`SPDX-License-Identifier: GPL-3.0[-or-later]`). `is_fully_compliant` is False on any missing/unknown license. `# [FIX H129]` |
| **H130** | 🔴 | `get_license_text(name)` silently returned the wrong (Apache-2.0) text for unknown names incl. "GPL-3.0". | Already raises `ValueError` on non-GPL-3.0; added `# [FIX H130]` documenting the no-silent-substitution guarantee + a regression test. |
| **H131** | 🔴 | `require_consent_interactive` **auto-granted** in `dry_run` and in any non-TTY env (called `grant_consent("I AGREE")` with no user input) — bypassed the mandatory liability-waiver gate. | Fail-CLOSED. Added `allow_non_interactive=False`; `dry_run` returns `False` (no ledger write); non-TTY without explicit opt-in raises `ConsentGateError`; only a real TTY "I AGREE" or `allow_non_interactive=True` grants. `# [FIX H131]` |
| **H135** | 🔴 | `legal_ctl consent` subcommand **hardcoded** `user_response="I AGREE"`, auto-granting consent with no user action. | Requires an explicit `--i-agree` flag (or real TTY "I AGREE" input); refuses (exit 1) in non-TTY without it. `legal/test_legal.py` (the fail-open assertion) updated to pass `--i-agree`. `# [FIX H135]` |

*(H129's checkbox was already `[x]` from session 3 — this session tightened the residual loose-substring
fail-open that the session-3 audit still permitted.)*

---

## Files changed (all carry `# [FIX Hxxx]` traceability comments)

- `legal/licenses.py` — docstring + `scan_directory` declaration matching + `get_license_text` comment.
- `legal/consent.py` — `require_consent_interactive` rewritten fail-closed.
- `legal/cli.py` — `consent` subcommand `--i-agree` guard.
- `legal/README.md` — module table no longer advertises multi-license set.
- `legal/test_legal.py` — consent assertion now passes `--i-agree`.
- `tests/test_legal_security.py` — **NEW**, 13 unittest tests locking H128/H129/H130/H131/H135.

---

## Tests

`tests/test_legal_security.py` (13 tests, stdlib `unittest`):
- `TestLicenseAuditFailClosed` (6): generic "License" word → not compliant; loose "GPL-3.0" prose → **not** compliant; canonical header / `License: GPL-3.0` / SPDX → compliant; `is_fully_compliant` False on missing.
- `TestGetLicenseTextStrict` (2): GPL-3.0 returns header; non-GPL raises `ValueError`.
- `TestConsentGateFailClosed` (3): dry_run does not grant; non-TTY without override raises; non-TTY with override grants.
- `TestConsentCliFailClosed` (2): non-TTY without `--i-agree` refuses (exit 1, no ledger write); `--i-agree` grants (exit 0, ledger written).

Standalone `legal/test_legal.py` = 8 passed (updated `--i-agree`).

---

## Verification

```
tests/test_legal_security.py  = 13 passed
standalone legal/test_legal.py = 8 passed
Full suite (excl. tests/test_ai.py collection error) = 1460 passed, 0 failures, 0 errors
```

---

## Bookkeeping (4 surfaces)

1. **Checkpoint** `remediation_progress.md`: H128/H130/H131/H135 → `[x]` (H129 already `[x]`).
2. **Standard §9** `Code Review Standards and Process.md`: H128/H129/H130/H131/H135 → 🟢 (session-23 FIXED notes); H141 marked PARTIAL (consent-CLI fail-open test fixed + security tests added; H139 safety-block coverage still pending).
3. **`MEMORY.md`**: `legal/` → 🟢 H128,H129,H130,H131,H135; Session 23 DONE bullet added.
4. **Daily log** `2026-08-24.md`: full Session 23 journal block + NEXT pointer.

---

## Next

Say **"continues"** to pick up `lib/` H3,H147 (next open RED cluster).

Open RED after this: `lib/` H3,H147 → `media/` H157 → `mnt/` H167,H168 → `opt/` H184,H187 →
`packages/` H198 → `quantum/` H215,H216,H217,H221 → `security/` H244,H245,H246.
