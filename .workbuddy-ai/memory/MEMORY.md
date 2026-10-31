# UmerOS — Long-term Project Memory

## Conventions
- Python only; GPL-3.0 canonical (`Licence`→`License`, `Version 3`→`v3`). §1 baseline: 12-line GPL block; docstring ending `Author:  Umer OS Project` (2 spaces) + `License: GPL-3.0 (GNU General Public License v3)`; `from __future__ import annotations` first.
- **Drift-recon first** — verify the premise against live state before editing; most are stale or overstated (H232, H236, H238, H240 all were). Trust `Read` over `Grep`.
- Never batch `Edit` on one file; use assert-first appliers. Bookkeeping (5): checkpoint box + RESOLVED + NEXT, standard §9 note, this file, daily `YYYY-MM-DD.md`, delete scratch scripts.

## Loop mechanics
- Source of truth: standard §9 rows (🔴/🟡/💭). **🔴 COMPLETE** (s112, 39/39).
- Checkpoint `.workbuddy-ai/memory/remediation_progress.md` (307 items; flip `- [ ]`→`- [x]`, append RESOLVED + `Next: **Hxxx**`, **never regenerate**). Pre-truncated lines (~190 chars) must be replaced wholesale.
- **Revert-prone:** `RED Loop Prompt.md`, standard §9. Write standard §9 + this file **first**.
- External re-saves strip `[FIX Hxxx]` tags **and `(Hxxx)` docstring markers** — pin *substance* in tests (code facts, documented behaviour), never the tag. Don't re-add.
- H1 (user action): rotate the leaked OpenRouter key + purge git history.

## Test runner
- `"…/envs/default/Scripts/python.exe" -m pytest tests/ legal/ opt/ sources/ srv/ tmp/ --junitxml=… -q` (quote the venv path — it has a space).
- **`mkdir -p /f/umeros_tmp` FIRST**, then `TMP=F:/umeros_tmp TEMP=F:/umeros_tmp`. A TMP inside the project → 15 false failures. Parse `--junitxml` — basetemp cleanup trips the safe-delete guard and eats the summary.
- Collapse to **1 node** ⇒ check `import requests` (`quantum/providers/ibm_provider.py`).
- Baseline (s232): **6176 nodes / 0 errors / 95 skipped / 6 failed** = 5 known `test_legal_pii_h137` + 1 external (see below).
- Guards: `core/path_guard.py`, `core/capability_gate.py`. ~735 modules; `Old Linux Code/` out of scope. `home` shadow: load `home_backup.py` by path under a unique name.

## Lessons
- **A gate on a façade is not a gate on the classes behind it.** H233: 7 duplicated `SbinCommand` bases × 45 commands bypassed `SbinManager.execute`; fixed via `__init_subclass__ = install_guard`.
- **The repo's own audit is the authority, not a grep for "GPL".** `scan_directory` accepts 3 forms and reads only the top 2 KB — so it passes a **4-line stub** (H240), while a case-sensitive `GPL` grep misses the block.
- **Applier pitfalls:** heredocs mangle `\r\n` into `/r/n` (use Write); an applier that `read()`s without `write()`ing back loses the edit. Assert each write landed, and that a mutant **differs** from the original (H240's `stub + rest` rebuilt it byte-for-byte).
- **`gate.require()` inside a loop ⇒ warning spam** (63 PERMISSIVE lines). Call it only when `gate.enforcing`, else `log.debug`.
- **Windows traps:** `os.write` is text-mode → corrupts CRLF backups, use `O_BINARY` (H229); `os.access(..., os.X_OK)` answers "readable", so POSIX-only tests need `os.name == "nt"` skips.
- **Substring scans trip on legitimate docstring prose** (H236: `Author: Umer OS Project` inside a docstring *describing* the convention). Prefer AST or line-anchored checks.
- **A harness that prints instead of asserting cannot fail** (H237 — the masking mechanism was the missing assertion, not the shared secret). **Prefer the existing auth contract to a new test-only bypass.**
- **Probe for the *gated* response, not a 200** (H238): a 401 proves the route is mounted *and* the gate is on. `stdout=subprocess.PIPE` with nobody draining it **deadlocks the child** — use a temp file.
- **A name safe as a path may still be unsafe as code** (H241: `my-app` → `class my-app(...)`, unparseable; 4/4 plausible names failed). Validate the charset, *then* derive an identifier + quote the literal for any code sink.
- **`safe_child`/`safe_join` are for real filesystem paths** (`Path.resolve()`). For a logical VFS path use name validation + `posixpath.normpath` containment, still raising `PathTraversalError`.
- **Check the repo's own documented policy before applying a row's remedy.** H239's row said "hash-pin `requirements.txt`", but its header defines it as a bounded *range* spec (H15) with hashes in a generated lock — honour the policy.
- **A documented API plus its tests decide the remedy, not the row.** H247 said "re-enable the commented-out nonce design", but that design returns a `dict` and breaks `developer_guide.md` + a determinism test — so replay defence went into the *verifier* (seen-MAC cache) and the envelope became opt-in.
- **Authenticate before you remember.** A replay cache must be keyed on *verified* input: record first and a flood of distinct forged MACs evicts genuine entries under the memory cap, re-enabling replay of exactly those.
- **`inspect.getsource` runs to EOF when only comments follow** (H248): `tokenize` skips comment tokens, so no DEDENT arrives and the "class source" swallows the dead code below. Slice the file region explicitly instead.
- **A "quarantine" that only logs is not a quarantine** — and check it is *sticky*: H248's returned `True` on the next innocuous call. Give it observable state (`is_quarantined`/`release`) and revoke through the real `SecuritySandbox`, saying so in the record when nothing could be revoked.
- **A keyless hash is integrity, not authenticity** (H249). Prove the distinction with one forgery: rewriting payload *and* digest satisfies `verify_hash` and fails `verify_hmac`. When renaming a lying API, keep the old name as a `DeprecationWarning` alias that names its replacements, so no caller breaks silently.
- **A mutation harness that crashes in `finally` leaves the mutant in the file.** H249's `write()` was called without its path, so the restore never ran. Always assert the restore against a pre-recorded sha256, and repair from the baseline before re-running — never assume "it crashed, so nothing changed".

## Status
- **Pointer: `security/` — H247 ✅, H248 ✅, H249 ✅, next H250.** H250 = `security/firewall.py` `AIFirewall`: blocks only `dst_port==22`, `add_rule` feeds a list nothing reads.
- H244/H245/H246 already ticked (🔴 done). Checkpoint ticks are **not** in row order — scan tick state, not row numbers.
- Done: every folder alphabetically before `security`; `sdk/` H240–H243 complete.
- Remaining: `security` H250–258, `sources` H259–264, `srv` H265–277, `tmp` H278–287, `tools` H288–295, `ui` H90, `usr` H296–302, `var` H303–307.

## Known-unrelated failures (do NOT re-investigate)
- 5 × `tests/test_legal_pii_h137` (external re-save put PII in `legal/creator_accounts.example.json`; flip-flops).
- ⚠ **`examples/` became an importable package** (external, 15:05 s228): `__init__.py` + `run_demo.py` appeared, so `test_layer_reachability` exits 1 — `reference_corpus.md:77` says "plain scripts, not importable packages". Untouched; fix by deleting it or moving `examples`→`REFERENCE` + marker.
- **External additions land mid-session.** If scanner-compliant, bump the pinned count + timestamp; don't "fix" the folder (seen: `media/network/`, `network/softbus/`, `test_cloud_server.py` +4).
- Order-dependent flakes: `test_compatibility.py::test_selftest_passes`, `test_opt_selftest_h192.py::test_package_selftests_run_their_children`. ⚠ H62: `drivers/` 0/75 `[TODAY]` labels — re-apply on request.
