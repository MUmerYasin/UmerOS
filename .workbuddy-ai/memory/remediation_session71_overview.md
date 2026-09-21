# Session 71 — H56: `core/command.py` base `Command` privilege enforcement (fail-closed gate)

**Status:** 🟡 RESOLVED · **Expert:** CodeReviewExpert (Kim) · **Loop:** H1–H307 remediation

## Premise vs. live state (drift-recon)
The standard (§9 H56, 🟡) asserted: *"The base `Command` declares a `privileges: List[str]` field … but never enforces it — nothing gates `execute()` on the declared privileges/capabilities. For a zero-trust OS the command base should verify the caller holds the required privileges (via `CapabilityManager`) before running."*

Live findings (premise CONFIRMED — not stale):
- `core/command.py:53` — `privileges: List[str] = []` is declared on the base `Command`.
- The class docstring (L40–42) already self-documents the gap: *"`privileges` is declared but NOT yet enforced by the base (see H56) — enforcement is a separate follow-up."*
- `\.privileges` has **0 consumers** repo-wide → the field is decorative today (root/su/login-style commands can declare `privileges=["root"]` with no check).
- `execute()` is the H55-locked contract (signature `execute(self, args: Optional[List[str]] = None) -> int`) and is called across `bin/` + `kernel/` (and locked by `tests/test_command.py`). It MUST NOT change signature or gain enforcement inline. The standard explicitly permits *"a `run()` wrapper"* as the fix.
- No `def run` exists in `bin/` (0 hits) → adding `run()` to the base `Command` introduces no subclass collision.

## Changes applied
Fail-closed enforcement, decoupled from any specific privilege backend (no import cycle):
1. `import logging` + `log = logging.getLogger("UmerOS.Core.Command")` + `EXIT_PERMISSION_DENIED = 77  # sysexits.h EX_NOPERM`.
2. `from typing import Callable, List, Optional` (added `Callable` for the verifier type).
3. `check_privileges(self, has_privilege: Optional[Callable[[str], bool]]) -> bool`:
   - no `privileges` declared → `True` (unprivileged command);
   - `has_privilege is None` → `False` (**fail-closed**: no verifier wired = deny);
   - otherwise → `all(has_privilege(p) for p in self.privileges)`.
4. `run(self, args=None, has_privilege=None) -> int`: when `check_privileges` fails, `log.warning("[FIX H56] command %s denied: …", …)` and `return EXIT_PERMISSION_DENIED`; else delegates to `execute(args)`.
5. Docstring updated: the old "NOT yet enforced (see H56)" note replaced with an enforcement description pointing at `run()` / `check_privileges()` and the `has_privilege` → `CapabilityManager`/`Credentials` seam.

`execute()` is untouched — H55 contract + every existing `bin/`/`kernel/` caller + `tests/test_command.py` are unaffected. The kernel wires `has_privilege` when it adopts capability-gated command dispatch (tracked under H114/H115).

## Verification
- `python -m py_compile core/command.py` → clean.
- `python -m pytest tests/test_command.py -q` → **6 passed** (H55 contract preserved).
- Enforcement smoke (inline): `RootCmd(privileges=["root"]).run()` → `77`; `.run(has_privilege=lambda p: p=="root")` → `0`; `.run(has_privilege=lambda p: False)` → `77`; `PlainCmd(privileges=[]).run()` → `0` even with no verifier; `check_privileges(None)` is `True` for plain / `False` for privileged. **SMOKE_OK.** Log capture shows the denial via the logger (no `print`).

## Bookkeeping (6 surfaces)
- Checkpoint `remediation_progress.md`: H56 box `[x]` + RESOLVED(session 71) note.
- Standard §9: H56 🟡 row appended RESOLVED note (fail-closed `run()`/`check_privileges()` gate; `execute()` untouched; `has_privilege` seam → `CapabilityManager`/`Credentials`).
- `MEMORY.md`: YELLOW pointer → session 71; folder map `core/ 🟢 H55,H56; 🟡 H57`.
- Daily log `2026-09-21.md`: Session 70 close-out + Session 71.
- This `remediation_session71_overview.md`.
- NEXT pointer → **H57**.

## Next
**H57** — `core/` (last open YELLOW): `core/command.py` tier label + GPL header (consistency with §4.4). Say **'continues'** for H57.
