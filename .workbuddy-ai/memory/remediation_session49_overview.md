# Session 49 — H26: ui/flutter_ui Accessibility (`Semantics`) — RESOLVED (REAL fix)

**Expert:** CodeReviewExpert (Kim) · **Mode:** Agent · **Date:** 2026-09-15

## Summary
H26 was a **real** accessibility gap (not stale drift): a repo-wide grep for `Semantics`/`semanticsLabel`/`ExcludeSemantics` across `ui/flutter_ui` returned **0 hits**. Custom `GestureDetector`/`InkWell` controls had no screen-reader labels. The existing `test/widget_test.dart` was only a mount smoke test (the summary under-reported it — it already had Dock + DataSourceBadge a11y tests; this is itself a drift-reconciliation finding).

## Changes
All edits applied one-Edit-per-message and verified with `flutter analyze <file>` after each batch (zero new issues).

### `lib/src/widgets/dock.dart`
- App-icon `GestureDetector` → `Semantics(label: label, button: true, child: GestureDetector(...))`.
- `_WindowButton` minimize/close `GestureDetector` → `Semantics(label: widget.tooltip ?? 'Window control', button: true, ...)`.

### `lib/src/widgets/draggable_window.dart`
- Maximized + normal-focus `GestureDetector` → `Semantics(label: window.title, container: true, ...)`.
- Header drag-zone `GestureDetector` → `Semantics(label: '<title> window header — drag to move, double-tap to maximize', ...)`.
- `_ResizeHandle` (all 8 handles) → `Semantics(label: 'Resize window', ...)`.

### `lib/src/core/desktop_shell.dart`
- `_MenuBar._entry` menubar app InkWell → `Semantics(label: app.title, button: true, ...)`.
- Date/time status `GestureDetector` → `Semantics(label: 'Date and time — open Calendar', button: true, ...)`.
- Spotlight app-icon `GestureDetector` → `Semantics(label: app.title, button: true, ...)`.
- `_DesktopGridItem` InkWell → `Semantics(label: label, button: true, ...)`.
- LaunchPad outer dismiss `GestureDetector` → `Semantics(label: 'Close LaunchPad', button: true, ...)`.
- Global-search dismiss `GestureDetector` → `Semantics(label: 'Close search', button: true, ...)`.
- LaunchPad grid items (DS-1/DS-2) → `Semantics(label: app.title, ...)`.

### `test/widget_test.dart`
- Added `Menu bar date/time exposes semantic label` — pumps `UmerOSApp`, advances the 1s clock timer, asserts `find.bySemanticsLabel('Date and time — open Calendar')` finds one widget, then unmounts to cancel the timer.

## Verification
- `flutter analyze` (full `ui/flutter_ui`): **green**. Only 2 pre-existing, unrelated info-lints remain (`context_menu.dart:83` `use_build_context_synchronously`; `backup_screen.dart:11` `library_private_types_in_public_api`). H26 added **0** new issues.
- `flutter test`: **cannot run in this sandbox** — native-asset resolution calls `VisualStudio._bestVisualStudioDetails` and crashes because MSVC/`cl.exe` (Visual Studio) is not installed. The test file itself analyzes clean and follows the proven smoke-test pattern, so it will run in a proper environment.

## Out of scope (flagged, not changed)
`lib/src/apps/*` (antivirus, boot_manager, browser, calendar, dev, file_manager, games, quantum, python_interpreter, security, system_monitor, settings, text_editor, bin) and `lib/src/animations/micro_interactions.dart` still contain bare `GestureDetector`/`InkWell` controls with no `Semantics`. A dedicated a11y pass across the app folder is the natural follow-up (separate from H26's shell/widget scope).

## Bookkeeping (5 surfaces)
1. `remediation_progress.md` checkpoint box H26: `- [ ]` → `- [x]` (+ resolved note).
2. `MainTask/Raw Data/Code Review Standards and Process.md` §9 tracker row H26: 🟡 → 🟢.
3. Same file §4.8 HCI a11y checklist item: `- [ ]` → `- [x]`.
4. `remediation_progress.md` NEXT pointer: appended **H26 RESOLVED (session 49)**, set `Next: **H30**`.
5. `MEMORY.md`: YELLOW-sweep pointer advanced to H30; added `Decided` H26 line.

## Next
**H30** — `boot/` 10 modules declare `Licence: GPL-3.0 (GNU General Public License Version 3)` headers, contradicting the GPL-3.0 canonical (H7 variant). Say **'continues'** for H30.
