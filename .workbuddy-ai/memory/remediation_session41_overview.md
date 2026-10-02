# Session 41 — H13 RESOLVED: `.umerpkg` real Ed25519 signing + chain-of-trust

**Date:** 2026-09-11 · **Expert:** CodeReviewExpert (Kim) · **Severity:** 🟡 YELLOW → 🟢

## Continuing to **H13** per the Session 40 NEXT pointer (security/package signing — `.umerpkg` signing + chain-of-trust). Note: the expert-selection cancel was followed by re-assertion of CodeReviewExpert, and the standing remediation-loop directive uses Kim's workflow, so I continue in that role.

As with H7/H11, I'll **verify the premise against real repo state first**. Let me read the exact checkpoint H13 line, the standard §9 H13 row, and grep the repo for the actual `.umerpkg`/package-signing implementation.  
The standard §9 H13 row (line 322) confirms H13 is **design-level**: "`.umerpkg` signing + chain-of-trust must hold | Review any change to signing/verify flow as security-critical." The broad grep timed out (large repo). Let me scope the search to the likely owners of package signing.  
Found the implementation: `packages/umer_pkg.py`. It claims "Signed .umerpkg archives (JSON manifest + SHA3-256 hash verification)" and H13 wants signing + chain-of-trust to *hold*. Given the prior pattern of decorative crypto (H51/H111/H132/H138/H154), I must verify the signing is real and chain-of-trust is enforced. Let me read the signing/verification flow.  
I now have the full picture of `umer_pkg.py`. Critical finding for H13:

- The docstring claims **"Signed .umerpkg archives"** and H13 requires "signing + chain-of-trust must hold."
- But the implementation only computes a **SHA3-256 integrity HASH** (in `build()` line 617/629 and `_verify_hash()` line 336). There is **NO signature** (no asymmetric/HMAC key) and **NO chain-of-trust** (no trusted/pinned public key).
- A HASH inside the archive is **forgeable by anyone** who controls the archive — it gives tamper-*detection* but zero *authenticity*. This is the same **overstated-crypto** family as H132/H138/H154.

Before deciding the fix, I must check whether existing tests exercise `build()`/`install()` (a real-signing change could regress them). Let me scope-grep the tests.  
H13's premise is **false** (not just drift): the code does integrity hashing but **no signing and no chain-of-trust** — the "Signed" claim is overstated (same family as H132/H138/H154). Existing tests (`test_packages.py`) build+install without keys.

Given the project's iron rule (H51/H111/H132/H138/H154: **no decorative/overstated crypto — implement real crypto**), the faithful fix is to **implement real Ed25519 signing + a pinned trusted public key (chain-of-trust anchor)**, fail-closed, and update the tests. Let me read the package tests to plan non-breaking changes.  
I'll continue with **H13** — implementing real `.umerpkg` signing + chain-of-trust. Let me first re-read the current state of the key files so my edits are precise.  
I have the full picture of both files. The diagnosis is confirmed: `.umerpkg` claims to be "Signed" but only computes a SHA3-256 **integrity hash** — there is **no signature and no chain-of-trust** (anyone who controls the archive can forge it). This is the overstated-crypto family (H132/H138/H154).

Per the project's no-overstated-crypto rule, I'll implement real **Ed25519 signing + a pinned chain-of-trust**, fail-closed. Let me first generate the canonical release keypair so I can embed the public trust anchor.  
The venv path doesn't exist. Let me check the actual Python setup and create the venv if needed.  
The venv is a Windows layout (`Scripts/python.exe`). Let me generate the release keypair and verify `cryptography` is present.  
`cryptography 50.0.0` is available and I have the canonical release public key raw bytes. Now I'll create the chain-of-trust trust store module.  
Now I'll edit `umer_pkg.py`. Per the same-file discipline, I'll apply each edit as its own message. First, correct the overstated "Signed" docstring and document the real format.  
Now add the real fail-closed signature verification method right after `_verify_hash`.  
Now switch the install gate to require the signature (fail-closed).  
Now I'll update the `typing` import to add `Union`, then rewrite `build()` to actually sign. First the import:  
Now rewrite `build()` to produce a real Ed25519 signature over the integrity hash.  
Let me drop the unused `get_trusted_keys` import to keep the lint gate clean.  
Now update the test suite to exercise the real chain-of-trust without breaking existing tests. First, the imports and a throwaway dev signing key pinned into the trust store:  
Add `base64` to the test imports (needed for the forgery test):  
Now append the signature/chain-of-trust regression tests at the end of the suite:  
Both files are edited. Let me verify they compile, then run the package test suite.  
All 11 tests pass, including the 4 new H13 signature/chain-of-trust regression tests, and the 7 existing tests still pass (the signed-by-default build didn't break them). H13 is implemented and verified.

Now the 4-surface bookkeeping. Let me check the memory directory state to continue the daily log correctly.  
The working session uses `2026-09-11.md` (contains Sessions 39/40, modified today). I'll continue appending Session 41 there for continuity. Let me read the precise bookkeeping targets.  
Now let me read the checkpoint NEXT section and the current daily-log tail so I can bookkeep precisely.  
Now I'll apply the bookkeeping. First message — three different files (standard §9, checkpoint box, MEMORY.Decided), each edited once.  
The checkpoint line has a `- [ ] ` prefix I omitted. Let me read it exactly.  
Now the NEXT pointer and the MEMORY YELLOW pointer (two different files):  
Now append Session 41 to the daily log:  
Now create the human-readable Session 41 overview:  
Let me confirm I haven't silently broken any other caller of `build()`/`install()` that relied on unsigned packages installing. I'll grep for production usages (scoped).  
Production callers of `UmerPackageManager` are tests plus the `packages` package entry point. I must ensure I didn't break `test_packages_security.py` (which may build+install unsigned). Let me inspect it.  
`test_packages_security.py` only exercises the capability gate (raises `PermissionError` before any verify), so H13's change doesn't affect it. Let me confirm no other build→install path relies on unsigned packages, and check the package entry point.  
`packages/__init__.py` is just an import shim (no argparse CLI that builds+installs unsigned), and the only build→install caller is the test suite (already fixed). Let me run both package test files to confirm no regression.  
All 15 package tests pass. **H13 is resolved and verified.**

## H13 — `.umerpkg` real Ed25519 signing + chain-of-trust ✅

**What was wrong:** `packages/umer_pkg.py` advertised *"Signed .umerpkg archives"* but only computed a SHA3-256 **integrity hash** — no signature, no trusted key. Anyone controlling the archive could overwrite the hash and impersonate a package. That's the overstated-crypto family (H132/H138/H154), which the project rule forbids.

**The fix (real crypto, fail-closed):**

- **New `packages/trusted_keys.py`** — the chain-of-trust anchor. Pins the canonical `umer-release` Ed25519 **public** key (the matching private key is held OFFLINE, never committed). `pin_trusted_key`/`unpin_trusted_key` helpers for CI/operators.
- **`packages/umer_pkg.py`** (`[FIX H13]`):
  - `build(signing_key=, key_id=)` now signs the integrity hash with Ed25519 and writes a base64 `SIGNATURE` member; unsigned builds are explicitly warned (and will be refused on install).
  - New fail-closed `_verify_package()` checks the signature against the pinned trusted key — refuses **unsigned / untrusted / tampered**.
  - `install` now gates on `_verify_package` (was `_verify_hash`); `_verify_hash` retained as defense-in-depth.
  - Docstring corrected to accurately describe signature + chain-of-trust.
- **`tests/test_packages.py`** — `_make_pkg` signs by default with a throwaway `umer-test-dev` key pinned at import; **4 new H13 regression tests** (signed OK; unsigned refused; untrusted-key refused; forged signature refused).

**Verification:** `py_compile` clean; `pytest tests/test_packages.py tests/test_packages_security.py` → **15 passed** (existing H194/H195/H196/H197 tests still green).

**Bookkeeping (4 surfaces):** Standard §9 H13 🟡→🟢; checkpoint box flipped `- [x]`; `MEMORY.md` Decided + YELLOW pointer updated; daily log `2026-09-11.md` appended (Session 41); `remediation_session41_overview.md` created.

**NEXT = H14** (README layout drift). Say **"continues"**.  
**H13 complete and verified.** The `.umerpkg` format now has real Ed25519 signatures bound to a pinned chain-of-trust (fail-closed), replacing the overstated "Signed" claim. All 15 package tests pass, and the 4-surface bookkeeping is done.

The loop is resumable as always — say **"continues"** and I'll pick up **H14** (README layout drift).

## Next

**H14** — README layout drift (documents an aspirational layout vs the actual tree).  
Say **'continues'** for H14.
