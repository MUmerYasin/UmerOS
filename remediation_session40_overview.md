# Session 40 — H11 RESOLVED · UI Tech Reconciliation (Kivy → Flutter/Dart canonical)

**Expert:** CodeReviewExpert (Kim) · **Mode:** Agentic · **Date:** 2026-09-11

## What was wrong
The standard (`Code Review Standards and Process.md` §9 H11) recorded the UI stack as
*inconsistent*: "Kivy in code, Flutter in blueprint," with the decision (2026-08-20)
that **Flutter (Dart) is canonical** and Kivy must be dropped/marked legacy. H22 added
that `setup.py` still declared `kivy>=2.3.0` in `install_requires` and README described
Kivy as *the* UI in ~7 places.

## Verification first (drift check — same class as H7/H9)
Before editing, a scoped sweep proved the premise was **partly stale**:
- `ui/flutter_ui/` is a **real, actively-built** Flutter/Dart desktop shell (full Windows
  build: WebView2, nlohmann.json, CMake artifacts) — the canonical frontend exists.
- `ui/__init__.py` already frames the `ui/` package as **legacy** ("pre-date the Flutter
  (Dart) desktop shell… kept only for backwards compatibility").
- `setup.py` kivy lives only in `extras_require` ([ui] / [all]), **not** `install_requires`,
  and line 75 already carried the note "legacy UI; Flutter is the canonical frontend."
- `kernel/umer_kernel.py:1148` `start_gui_shell` docstring already said "Flutter-based."

So the *decision* was documented; the remaining drift was concrete and fixable.

## Changes (11 edits / 5 files)
| File | Change | Hotspot |
|------|--------|---------|
| `setup.py:110` | `[all]` extras `kivy>=2.3.0` lacked the legacy note → added `  # legacy UI; Flutter is the canonical frontend (H11/H25)` | H11/H15 |
| `kernel/requirements.txt:2` | active `kivy>=2.2.0` → commented `# kivy>=2.2.0  # RETIRED: … Flutter (Dart) is the canonical frontend (H11/H25)` | H125 |
| `kernel/gui.py:16` | added RETIRED/LEGACY banner docstring (Kivy prototype; canonical = `ui/flutter_ui/`; kernel must not launch it) | H122 |
| `kernel/umer_kernel.py:1147` | `start_gui_shell` docstring reconciled (was "Flutter-based" but launched Tkinter `ui/launch_gui.py`); added `[FIX H11]`/`[FIX H116]` block + TODO to repoint at the built Flutter binary | H11/H116 |
| `README.md:146` | §6 Fluidic UI — Kivy → **Flutter (Dart)** canonical; Kivy/Tkinter prototypes retired | H14 |
| `README.md:167` | Key Features "Kivy-Based Shell" → "Flutter-Based Shell" (In Progress) | H22 |
| `README.md:206` | Tech-Stack box `kivy 2.3+` → `flutter (Dart)` (canonical UI) | H22 |
| `README.md:262` | Project Structure `ui/shell.py (Kivy)` → `(legacy Kivy/Tkinter)` | H14 |
| `README.md:362` | Architecture diagram `(Kivy Shell, GUI)` → `(Legacy Kivy/Tkinter GUI)` | H14 |
| `README.md:748` | Phase-4 TODO "Kivy-based shell UI" → "Flutter-based shell UI" | H22 |
| `README.md:862` | References "Kivy Framework" → "(retired UI prototype)" | H14 |

## Verification
- `python -m py_compile setup.py kernel/gui.py kernel/umer_kernel.py` → **OK**.
- Re-grep `README.md` for `kivy` → only legacy/retired-framed hits remain (lines 146,
  262, 362, 748, 862); lines 167/206 now name Flutter.

## Bookkeeping (4 surfaces)
1. **Standard §9 H11 row (320):** 🟡 → 🟢.
2. **Checkpoint** `remediation_progress.md`: flipped `[x]` → H11, H22, H25, H122, H125.
   Kept `[ ]` → H14 (README layout drift beyond Kivy), H15 (`g4f` + floating `>=` pins),
   H116 (capability-gate + real Flutter launch still pending — only docstring/comment
   reconciled this pass).
3. **Checkpoint NEXT pointer (538):** H11 done → next = **H13**.
4. **MEMORY.md:** Decided H11 (9) + YELLOW pointer (22) updated to H11 resolved, next = H13.

## Scope discipline
H11 = Kivy↔Flutter reconciliation only. The master prompts
(`Umer_OS_Antigravity_Master_Prompt.md`, `Umer_OS_Prompt_deepseek.md`, etc.) still
describe Kivy as the UI in several places — these are **historical design docs**; the
engineering blueprint (authoritative) says Flutter/Dart. Left as design history, not
rewritten (consistent with H7's handling of stale doc premises). `ui/*.py` Tkinter files
remain the retired headless fallback; `ui/__init__.py` already frames them legacy.

## Next
**H13** — security/package signing (`.umerpkg` signing + chain-of-trust must hold).
Say **'continues'** for H13.
