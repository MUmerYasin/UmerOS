# Remediation Session 48 — H24: `ui/flutter_ui` Power/Idle App Naming (HCI #2)

**Date:** 2026-09-12 · **Expert:** CodeReviewExpert (Kim) · **Mode:** Agent
**Standard:** `MainTask/Raw Data/Code Review Standards and Process.md` §9 · **Checkpoint:** `.workbuddy-ai/memory/remediation_progress.md`

---

## Summary

H24 was a YELLOW item claiming user-facing labels used OS-internal jargon
(`desktop_shell.dart:287` "CPUIdle & Governor", `:448` "Power & Idle", and
`apps/power_governor_app.dart:104` "CPUIdle & Power Governor Framework"), violating
HCI #2 (plain, task-oriented language).

**Drift-reconciliation proved the premise STALE — H24 was already resolved by H23's registry centralisation. No code change required.**

### Evidence
- Repo-wide grep for `Power & Idle | CPUIdle | Idle & Governor | & Governor` across `ui/flutter_ui`
  returned **only 2 hits**:
  1. `app_registry.dart:17` — the docstring *referencing* the historical H24 drift (documentation).
  2. `power_governor_app.dart:106` — an **inside-app section header** ("CPUIdle & Power Governor Framework")
     accurately naming the real subsystem the app tunes. Not a user-facing launcher label.
- The two cited launcher strings (`CPUIdle & Governor` @287, `Power & Idle` @448) **do not exist** anywhere (0 hits).
- Canonical launcher title is plain **`Power & Performance`**, single source of truth in
  `app_registry.dart:114` (id `power`), **asserted by `test/app_registry_test.dart:41`**.
  `desktop_shell.dart:325` top-bar popup matches it exactly.
- All 18 `AppRegistry` titles are plain/task-oriented → Nielsen #2 satisfied.

### 💭 Discretionary (not acted on, out of scope)
`desktop_shell.dart:320-335` top-bar quick menu hardcodes 4 labels (incl. `Power & Performance`
matching the registry; but `settings` shown as `System Settings...` diverging from registry `Settings`).
It is a curated 4-item menu, not a registry-driven surface — not naming drift. Left as-is to avoid churn.

## Bookkeeping (4 surfaces closed)
1. Standard §9 H24 tracker row (333): `🟡` → `🟢`; stale jargon-label premise corrected.
2. Checkpoint box H24 (241): `- [ ]` → `- [x]`.
3. Checkpoint NEXT pointer (538): **H24 RESOLVED** → next = **H26**.
   - `MEMORY.md` Decided (new H24 line) + YELLOW pointer (29): H24 resolved, next = **H26**.
   - Daily log appended to `.workbuddy-ai/memory/2026-09-12.md`.

## Scope discipline
- **No code edited.** The jargon naming drift the standard flagged no longer exists; editing would be churn.
- 10th consecutive YELLOW (H7/H11/H13/H14/H15/H16/H19/H20/H23/H24) where drift-reconciliation
  found a stale premise — the standard's §9 hotspot rows are aging and should be re-verified before any edit.

## Next
**H26** — `ui/flutter_ui/lib/src/widgets/*` (Dock, DraggableWindow, LaunchPad, ControlCenter) +
`test/widget_test.dart` lack `Semantics` labels / a11y coverage; only a mount smoke test exists
(Nielsen #9 + WCAG 2.1 AA, §4.8). This is a substantive, real finding — will drift-reconcile on start.
