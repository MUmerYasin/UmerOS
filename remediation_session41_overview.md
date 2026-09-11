# Session 41 — H13 RESOLVED: `.umerpkg` real Ed25519 signing + chain-of-trust

**Date:** 2026-09-11 · **Expert:** CodeReviewExpert (Kim) · **Severity:** 🟡 YELLOW → 🟢

## What was wrong (H13)
`packages/umer_pkg.py` advertised **"Signed .umerpkg archives"** but the code only
computed a SHA3-256 **integrity hash** (`HASH` member). There was **no signature
and no trusted key** — anyone who can write the archive can overwrite the hash and
fully impersonate a package. `_verify_hash` was fail-closed on hash mismatch but
never authenticated *who* produced it. This is the **overstated-crypto** family
(H132/H138/H154) that the project rule forbids.

## Fix
Real Ed25519 signing + a pinned chain-of-trust, fail-closed.

| File | Change |
|------|--------|
| `packages/trusted_keys.py` (**NEW**) | Chain-of-trust anchor. `TRUSTED_PUBLIC_KEYS` maps `key_id →` raw 32-byte Ed25519 public key. Pins canonical `umer-release` public key (private key held OFFLINE, never committed). `pin_trusted_key`/`unpin_trusted_key`/`get_trusted_keys`/`is_trusted` helpers. |
| `packages/umer_pkg.py` | `[FIX H13]` — imports `cryptography` Ed25519 + `trusted_keys`; docstring corrected; `build(signing_key=, key_id=)` signs the integrity hash and writes a base64 `SIGNATURE` member; NEW fail-closed `_verify_package()` checks signature against the pinned key; `install` now gates on `_verify_package`; `verify_package()` + `trust_key()` public API. |
| `tests/test_packages.py` | `_make_pkg` signs by default with a throwaway `umer-test-dev` key pinned at import; **4 new H13 regression tests** (signed OK; unsigned refused; untrusted key refused; tampered signature refused). |

### Trust model
- A package is accepted **only** when its signature verifies against a key in the
  trust store (refuse if `key_id` is unknown / untrusted).
- Canonical production anchor = `umer-release` (public key embedded; **private key
  offline**). Operators/CI may pin additional keys via `pin_trusted_key`.
- Unsigned packages are explicitly refused on install (fail-closed).

## Verification
- `py_compile` on `umer_pkg.py`, `trusted_keys.py`, `test_packages.py` → **OK**.
- `pytest tests/test_packages.py -v` → **11 passed** (7 pre-existing H194/H195/H196/H197
  tests still green + 4 new H13 tests). The signed-by-default build did not break
  the existing hash-only tests.

## Bookkeeping (4 surfaces)
1. Standard §9 H13 row → 🟢 (stale "Signed" premise corrected).
2. Checkpoint box H13 → `- [x]` with `[FIX H13]` note.
3. Checkpoint NEXT pointer → H13 done, next = **H14**.
4. `MEMORY.md` Decided H13 + YELLOW pointer → H13 resolved, next = H14.

## Scope discipline
H13 = real signing + chain-of-trust only. README/H14 layout drift, H15
(`g4f` + floating pins), and H116 (capability-gate + real Flutter launch) remain
open (broader scope).

## Next
**H14** — README layout drift (documents an aspirational layout vs the actual tree).
Say **'continues'** for H14.
