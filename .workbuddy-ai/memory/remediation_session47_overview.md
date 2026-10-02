# Remediation Session 47 — H23: `ui/flutter_ui` App-Registry DRY

**Date:** 2026-09-12 · **Expert:** CodeReviewExpert (Kim) · **Mode:** Agent
**Standard:** `MainTask/Raw Data/Code Review Standards and Process.md` §9 · **Checkpoint:** `.workbuddy-ai/memory/remediation_progress.md`

---

## Summary

H23 was a YELLOW item claiming the **same app registry was hardcoded in three widgets**
(`_DesktopGrid`, `_GlobalSearchModal`, `_LaunchPad` in `desktop_shell.dart`) and needed
centralising into one model.

**Drift-reconciliation proved the premise STALE — H23 was already resolved in a prior session.**

### Evidence (no code change required this session)
- `ui/flutter_ui/lib/src/core/app_registry.dart` already exists as the **single source of truth**
  (`AppRegistry` class). Its own docstring states it *"resolves Hotspot H23"*.
- `AppRegistry` is **wired in**, not dead:
  - `desktop_shell.dart` — L234 `byId`, L296/L298 `byId('settings'/'power')`, L429 `byId('calendar')`,
    L474 `AppRegistry.apps` (grid), L1011 `AppRegistry.apps` (spotlight), L1139 `AppRegistry.apps` (launchpad).
  - `dock.dart` — L87/L266 `byId`.
- `AppDefinition(` appears **only** in `app_registry.dart` — zero duplicate inline lists in any widget.
- `test/app_registry_test.dart` guards invariants (non-empty, unique ids, `byId` consistency, `filterKnownIds`).
- No second/stray `List<AppDefinition>` or `apps = [` exists outside `app_registry.dart`.

The DRY/consistency risk the standard flagged was already eliminated. This session corrected
only the **stale standard/checkpoint bookkeeping** so the remediation trail stays accurate.

## Bookkeeping (4 surfaces closed)
1. Standard §9 H23 tracker row (332): `🟡` → `🟢`; stale "hardcoded in three widgets" premise corrected.
2. Standard §9 HCI note (214): `- [ ]` → `- [x]`; "do not duplicate" → "already centralised".
3. Checkpoint box H23 (240): `- [ ]` → `- [x]` with corrected premise.
4. Checkpoint NEXT pointer (538): **H23 RESOLVED** → next = **H24**.
   - `MEMORY.md` Decided (new H23 line) + YELLOW pointer (29): H23 resolved, next = **H24**.
   - Daily log appended to `.workbuddy-ai/memory/2026-09-12.md`.

## Scope discipline
- **No code edited.** The premise was already false; editing would have been churn.
- Re-confirms the standing rule: **drift-reconcile every H-n premise against the real repo
  before editing** — many YELLOW items (H7/H11/H13/H14/H15/H16/H19/H20/H23) are stale drift.

## Next
**H24** — `ui/flutter_ui` Power/Idle app naming drift (`'Power & Idle'` vs `'Power & Performance'`/
`'CPUIdle & Governor'`). The `app_registry.dart` docstring notes H23's centralisation also
resolved H24's label drift — premise will be drift-reconciled on start.
