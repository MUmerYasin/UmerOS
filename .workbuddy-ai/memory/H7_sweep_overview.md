# H7 Licence Sweep — Overview (2026-08-22, session 9)

## What was done
Completed the **H7 licence mini-sweep** directed at the 6 named files, normalizing every affected
header to the canonical **`License: GPL-3.0`** tag (per standard §9 H7 = GPL-3.0 canonical).

## Files changed (all carry a `# [FIX H7]` comment)
| File | Change |
|------|--------|
| `opt/config.py` | Added `License: GPL-3.0` to docstring (GPL boilerplate present, short tag missing) |
| `opt/var.py` | `License: GPL-3.0 (GNU General Public License Version 3)` → `License: GPL-3.0` |
| `opt/package.py` | Added `License: GPL-3.0` to docstring (GPL boilerplate present, short tag missing) |
| `srv/backup.py` | `License: GPL-3.0 (GNU General Public License Version 3)` → `License: GPL-3.0` |
| `packages/umer_pkg.py` | `License: GPL-3.0 (GNU General Public License Version 3)` → `License: GPL-3.0` |
| `tmp/tmpfs.py` | `License: GPL-3.0 (GNU General Public License Version 3)` → `License: GPL-3.0` |

## Key findings
- The 6 files already used **American `License:`** (not British `Licence:` as the prior summary predicted)
  and only carried a redundant `(GNU General Public License Version 3)` parenthetical, which the GPL v3
  boilerplate already states. The canonical tag simply drops that parenthetical.
- `packages/umer_pkg.py` is the only one of the 6 **missing the standard GPL v3 boilerplate** header entirely
  (it had only the tag) — flagged as a follow-up for the broader folder sweep.

## Verification
- All 6 files `ast.parse` clean.
- Grep: **zero** `(GNU General Public License Version 3)` remaining; `License: GPL-3.0` present in all 6.
- Full `pytest tests/` = **1688 passed, 54 skipped, 0 failures, 0 errors** (unchanged — no regressions).

## Bookkeeping updated
- `remediation_progress.md` — NEXT re-pointed: H7 mini-sweep DONE; remaining = full YELLOW/BLUE sweep.
- `MEMORY.md` — NEXT updated likewise.
- `2026-08-22.md` — appended "H7 licence sweep CLOSED" section.

## Next (resumable)
**Full YELLOW/BLUE sweep** — remaining un-gated privileged paths across H1–H307, remaining H7 folder licence
strays (other opt/srv/tmp/packages modules: items H183/H200/H269/H278 partial), missing licence headers
(sbin/scripts/sdk/sources/network/usr/security/media/etc/drivers/root/var/initrd/…), tier labels, baseline smells.
