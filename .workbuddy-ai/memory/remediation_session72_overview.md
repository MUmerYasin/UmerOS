# Session 72 — H59 (`dev/` DeviceNode world-writable default `0o666`) ✅ RESOLVED

**Drift-recon:**&#x200B; The standard's premise was *partially* stale — `dev/` was already mostly disciplined (`memory_devices.py` uses `0o640`, many helpers already `0o660`/`0o640`). The real gaps were the base `DeviceNode.mode` default, the `makedev`/`mknod` helper defaults, and a handful of privileged pseudo/misc nodes. The classic data devices (`null`/`zero`/`full`/`log`/`shm`/`vsock`) are legitimately world-rw per Unix norm (they're non-security data sinks), so they were **kept** `0o666` but made explicit + justified.

**Changes (21 edits, all `# [FIX H59]`):**&#x200B;

- `DeviceNode.mode` default `0o666 → 0o640` (`dev/core.py`)
- `create_device()` helper perms `0o666 → 0o640` (`makedev.py` ×2, `mknod_virtual.py` ×2)
- Privileged pseudo/misc nodes `0o666 → 0o660` (`tty`/`ptmx`/`tun`/`fuse`/`i2c`/`misc-char`)
- `devtmpfs.py` `PSEUDO_DEVICES` table tightened/justified (7 line-fixes)

**Two application-time SyntaxErrors fixed:**&#x200B; an inline `# [FIX H59]` comment had swallowed the closing `)` of `create_device(...)` (in `makedev.py`/`mknod_virtual.py`), and six tuple comments in `devtmpfs.py` sat *between* a value and the next tuple element so the tuples never closed — both corrected by moving comments after the full expression.

**Verification:**&#x200B; `py_compile` clean across all 21 edited `dev/` files; the only remaining `0o666` are the explicitly-justified data devices; smoke `DeviceNode().mode == 0o640` → OK; no test asserts device modes.

**Bookkeeping (6 surfaces):**&#x200B; checkpoint box `[x]` + RESOLVED; NEXT pointer → **H60**; standard §9 H59 row RESOLVED note; MEMORY pointer → session 73 + `dev/` map `🟢 H59; 🟡 H60,H61`; daily log `2026-09-21.md` entry; per-session overview.

- Checkpoint `remediation_progress.md`: H57 BLUE box `[x]` + RESOLVED(session 72) note.
- Standard §9: H57 💭 row RESOLVED note (license-header half was stale).
- `MEMORY.md`: pointer → session 72; folder map corrected `core/ 🟢 H55,H56; 💭 H57` (was overstated 🟡).
- Daily log `2026-09-21.md`: Session 72 entry.
- This `remediation_session72_overview.md`.
- NEXT pointer → **H59** (`dev/`, next true YELLOW).

## Next

**H59** — `dev/` (next open YELLOW): `DeviceNode` default mode `0o666` world-rw (privilege-escalation vector), `DeviceManager.sync_to_filesystem` missing a capability gate (H60), and the `DeviceManager` registry lacks a `threading.Lock` (H61). Say **'continues'** for H59.
