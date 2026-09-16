# Remediation Session 60 — H41 (PyInstaller spec freezes retired GUI)

## Outcome
**H41 RESOLVED** with a real code fix (not just bookkeeping): the frozen `UmerOS-GUI` binary now launches the canonical Flutter frontend instead of the retired legacy GUI.

## Drift-recon
- Standard §9 H41: spec freezes `ui/umeros_gui.py` — the legacy GUI H25 retired — contradicting the Flutter mandate (H11/H25, §4.8). The standard labelled it 'Tkinter'; actual toolkit is **PyQt6** (verified by reading the imports).
- The canonical launcher already exists: `ui/launch_gui.py` is a thin Python host that boots `ui/flutter_ui/` via the Flutter SDK (desktop/android/ios/web).
- Conclusion: the fix is to **repoint the spec's `_ENTRY`** to `launch_gui.py` — exactly the standard's endorsed remedy.

## Code changes (2 files)
1. `build/UmerOS-GUI.spec` — `_ENTRY` = `ui/launch_gui.py` (was `ui/umeros_gui.py`); added `[FIX H41]` note explaining the repoint and that `umeros_gui.py` is the retired PyQt6 shell; spec still `raise SystemExit` if the entry is missing (fail-closed).
2. `ui/launch_gui.py` — `main()`'s `input()` wrapped in `try/except EOFError` -> defaults to Desktop, so the frozen `console=False` binary launches without a TTY instead of crashing.
- Verified: both files `py_compile` clean; `_ENTRY` repointed; `[FIX H41]` present; EOFError guard present.

## Bookkeeping closed (6 surfaces)
1. Checkpoint box H41: `- [ ]` -> `- [x]` (RESOLVED session 60).
2. Standard §9 row H41: 🟡 -> 🟢 + RESOLVED note.
3. Checkpoint NEXT pointer: H41 -> **H43** (H42 already 🟢).
4. Checkpoint NEXT header: `session 59` -> `session 60` (now build/ sweep).
5. MEMORY.md YELLOW pointer: build/ sweep; next 🟡 H43.
6. MEMORY.md `build/` folder map: 🟢 H42,H41; 🟡 H43–H45.

## Tooling note
Switched the bookkeeping helper to pre-check all line prefixes before writing and flush after each edit, so a later mismatch can no longer silently discard earlier edits (the bug that bit session 59).

## Next
**H43** — `build/UmerOS-GUI.spec:5` hardcoded absolute Windows path. Likely STALE (the spec already carries a `[FIX H43]` note + repo-relative `_REPO_ROOT` resolution). Say **'continues'** for H43.
