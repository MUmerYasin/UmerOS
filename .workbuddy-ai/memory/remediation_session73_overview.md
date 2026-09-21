# UmerOS Remediation — Session 73 (H59)

**Expert:** CodeReviewExpert (Kim)
**Date:** 2026-09-21 (continuation of the `dev/` sweep; s70–72 = compatibility/ + core/)
**Severity:** 🟡 YELLOW (kept — genuine zero-trust gap, only the "long list" overstatement was stale)

---

## Summary

`dev/` (the FHS `/dev` virtual device-node filesystem, ~43 modules) carried a world-writable
default on the base `DeviceNode` dataclass (`mode=0o666`) and a few privileged pseudo/misc nodes.
H59 tightened the safe defaults and privileged nodes while **keeping** the classic non-security
data devices (`null`/`zero`/`full`/`log`/`shm`/`vsock`) world-rw per Unix norm — but now each is
explicit and justified in a comment.

## Drift-recon (premise check)

The standard (§9 H59) asserted the base `DeviceNode` defaults to `0o666` **and** "a long list of
device nodes are explicitly `0o666`." Live repo check showed `dev/` was already **mostly
disciplined**:

- `memory_devices.py` already uses `0o640` (the model to copy).
- Many helper/mknod defaults were already `0o660`/`0o640`.
- Genuine gaps found:
  1. `DeviceNode.mode` default `0o666` (`dev/core.py`).
  2. `makedev.py` / `mknod_virtual.py` `create_device()` default perms `0o666`.
  3. Privileged pseudo/misc nodes still `0o666`: `tty`, `ptmx`, `tun` (`net_device.py`/`devtmpfs.py`),
     `fuse`, `i2c`, `misc_char_devices.py`.
  4. Classic data devices at `0o666` (`null`/`zero`/`full`/`log`/`shm`/`vsock`) — world-rw is the
     correct Unix norm for non-security **data sinks**; these are NOT a privilege-escalation vector.

**Conclusion:** real fix needed, but scoped — not a blanket sweep.

## Changes (21 edits, all tagged `# [FIX H59]`)

| Change | Files |
|---|---|
| `DeviceNode.mode` default `0o666` → `0o640` (owner rw, group r) | `dev/core.py` |
| `create_device()` helper default perms `0o666` → `0o640` | `dev/makedev.py` (×2), `dev/mknod_virtual.py` (×2) |
| Privileged pseudo/misc nodes `0o666` → `0o660` | `tty_device.py`, `ptmx_device.py`, `net_device.py`, `fuse_device.py`, `i2c_devices.py`, `misc_char_devices.py` (×3) |
| Classic data devices kept `0o666` but made explicit + justified | `null_device.py`, `zero_device.py`, `full_device.py`, `log_device.py`, `shm_device.py`, `virtual_devices.py` |
| `PSEUDO_DEVICES` table + tun node tightened/justified | `dev/devtmpfs.py` (7 line-fixes) |

### Two application-time SyntaxError bugs fixed
- `makedev.py:124` / `mknod_virtual.py:147`: an inline `# [FIX H59] safe default)` comment **swallowed
  the closing `)`** of the multi-line `def create_device(...)` signature → moved the comment after the
  signature.
- `devtmpfs.py` `PSEUDO_DEVICES`: inline `# ...` comments sat **between** the trailing value and the
  next tuple element (e.g. `, "Null device")`), so the tuples never closed → moved each comment to the
  end of the full tuple.

## Verification

- `py_compile` clean across **all 21 edited `dev/` files** (full `dev/**/*.py` recompile → `COMPILE_BAD=0`).
- Source enumeration: the only remaining `0o666` literals are the explicitly-justified data devices
  (`null`/`zero`/`full`/`log`/`shm`/`vsock`) — confirmed intended.
- Smoke test: `DeviceNode(name="x", path="/dev/x", dev_type=..., major=1, minor=3).mode == 0o640` → **OK**.
- No test asserts device modes (`tests/` grep → 0 hits), so the default change is behavior-safe.

## Bookkeeping (6 surfaces)

1. ✅ Checkpoint `remediation_progress.md` — H59 box `- [ ]` → `- [x]` + RESOLVED note.
2. ✅ NEXT pointer → **H60** (`DeviceManager.sync_to_filesystem` capability gate, H61 registry lock).
3. ✅ Standard §9 H59 🟡 row — RESOLVED note appended (premise corrected: only "long list" was overstated).
4. ✅ MEMORY.md — pointer → session 73; `dev/` folder map `🟡 H59,H60,H61` → `🟢 H59; 🟡 H60,H61`.
5. ✅ Daily log `2026-09-21.md` — Session 73 entry + Next pointer → H60.
6. ✅ This per-session overview.

## Next (H60 — Session 74)

`dev/core.py:211-237` `DeviceManager.sync_to_filesystem()` calls `os.mknod`/`os.mkfifo`/`os.symlink_to`/
`os.mkdir` to materialize **real** device nodes into the VFS with **no capability/privilege gate** —
same "privileged op / no gate" family as H27/H28/H46/H51. Gate behind `CapabilityManager` + a root/
capability check; restrict the default node mode (now `0o640` via H59); never create into a host `/dev`
unless explicitly authorized. H61 (registry `threading.Lock`) follows.

## Standing user action (H1)

User must rotate the leaked OpenRouter key + purge git history — not handled by the loop.
