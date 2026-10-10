# -*- coding: utf-8 -*-
"""H152 (Session 88) bookkeeping — assert-first, one pass per file."""
from pathlib import Path

R = "\U0001F534"; G = "\U0001F7E2"; Y = "\U0001F7E1"
OK = "\u2705"; ARR = "\u2192"; EM = "\u2014"; S9 = "\u00a79"

ROOT = Path(r"UmerOS")


def replace_pairs(path, pairs):
    p = ROOT / path
    t = p.read_text(encoding="utf-8")
    for old, new in pairs:
        c = t.count(old)
        if c != 1:
            raise SystemExit(f"ABORT {path}: anchor count={c} for {old[:70]!r}")
        t = t.replace(old, new)
    p.write_text(t, encoding="utf-8")
    print("OK", path, "| edits:", len(pairs))


# ---- 1. RED Loop Prompt.md ------------------------------------------------
red_pairs = [
    (
        f'Next: **H152** {EM} `quantum/crypto_pqc.py:36-46` silent classical-crypto fallback '
        f'when `liboqs-python` is missing. Say **"continues"** for H152.',
        f'Next: **H156** {EM} `media/mount_ops.py`, `media/auto_mount.py`, `media/udisks2.py` '
        f'no `CapabilityManager` gate on the privileged mount path. Say **"continues"** for H156.',
    ),
    (
        f"- [ ] **H152** | {R} |",
        f"- [x] **H152** | {R} |",
    ),
    (
        f"\n- [ ] **H156** | {R} |",
        f"\n      - {OK} RESOLVED (session 88, drift): H152 addressed {EM} the fallback is no longer "
        f"silent. `PostQuantumCrypto.__init__` logs a WARNING when liboqs is absent, exposes "
        f"`is_post_quantum` (False under fallback), and provides `assert_post_quantum()` which "
        f"**raises RuntimeError** so security-critical callers refuse non-PQC operation "
        f"(`quantum/crypto_pqc.py:273-297`). Verified in-process: backend=fallback, "
        f"is_post_quantum=False, assert_post_quantum {ARR} RuntimeError, sign/verify round-trip OK, "
        f"tampered {ARR} False. Dedicated regression suite `tests/test_pqc.py` (H152) + "
        f"`tests/test_quantum_security.py`. No code change needed.\n- [ ] **H156** | {R} |",
    ),
]
replace_pairs("MainTask/Raw Data/RED Loop Prompt.md", red_pairs)


# ---- 2. Standard §9 H152 row ---------------------------------------------
std = ROOT / "MainTask/Raw Data/Code Review Standards and Process.md"
lines = std.read_text(encoding="utf-8").split("\n")
idx = None
for i, ln in enumerate(lines):
    if ln.startswith("| H152 |") and R in ln[:40]:
        idx = i
        break
if idx is None:
    raise SystemExit("ABORT standard: H152 red row not found")
old = lines[idx]
note = (
    f" {OK} RESOLVED (session 88, drift): fallback no longer silent {EM} `PostQuantumCrypto` logs a "
    f"WARNING, exposes `is_post_quantum` (False under fallback) and `assert_post_quantum()` which "
    f"raises RuntimeError for security-critical callers (`quantum/crypto_pqc.py:273-297`). Verified "
    f"in-process + covered by `tests/test_pqc.py` (H152). |"
)
lines[idx] = old.rstrip()[:-1] + note
std.write_text("\n".join(lines), encoding="utf-8")
print("OK standard H152 row L", idx + 1)


# ---- 3. MEMORY.md ---------------------------------------------------------
mem_pairs = [
    (
        f"- **RED loop progress (session 87):** H1, H3, H12, H18, H46, H51, H146, H147 ALL RESOLVED "
        f"(all drift {EM} already fixed + tested earlier; standard {S9} colours were stale). Next {R} "
        f"**H152** (`quantum/crypto_pqc.py:36-46` silent classical-crypto fallback).",
        f"- **RED loop progress (session 88):** H1, H3, H12, H18, H46, H51, H146, H147, H152 ALL "
        f"RESOLVED (all drift {EM} already fixed + tested earlier; standard {S9} colours were stale). "
        f"Next {R} **H156** (`media/*` no CapabilityManager gate on the privileged mount path).",
    ),
]
replace_pairs(".workbuddy-ai/memory/MEMORY.md", mem_pairs)


# ---- 4. Daily log ---------------------------------------------------------
log_pairs = [
    (
        f"## Next\n**\"continues\"** resumes the {R} RED loop at **H152** {EM} "
        f"`quantum/crypto_pqc.py:36-46` silent classical-crypto fallback when `liboqs-python` is "
        f"missing. (The separate {Y} loop pointer is unchanged: H66.)",
        f"## Session 88 {EM} {R} H152 resolved (drift)\n"
        f"- **H152 ({R}, `quantum/crypto_pqc.py` silent classical-crypto fallback): DRIFT {EM} "
        f"addressed.** The fallback is no longer silent: `PostQuantumCrypto.__init__` logs a WARNING "
        f"when liboqs is absent, exposes `is_post_quantum` (False under fallback), and provides "
        f"`assert_post_quantum()` which **raises RuntimeError** so security-critical callers refuse "
        f"non-PQC operation (`quantum/crypto_pqc.py:273-297`). Verified in-process: backend=fallback, "
        f"is_post_quantum=False, assert_post_quantum {ARR} RuntimeError, sign/verify round-trip OK, "
        f"tampered {ARR} False. Dedicated regression suite `tests/test_pqc.py` (H152) + "
        f"`tests/test_quantum_security.py`. No code change needed.\n"
        f"- **Bookkeeping:** RED loop H152 {ARR} `[x]` + RESOLVED note; NEXT {ARR} **H156**; standard "
        f"{S9} H152 row RESOLVED note; MEMORY RED-loop progress {ARR} session 88.\n"
        f"- **Note:** **9/9** {R} items so far (H1, H3, H12, H18, H46, H51, H146, H147, H152) were "
        f"drift {EM} already fixed in earlier sessions, never reflected in the standard's {S9} colours.\n"
        f"\n"
        f"## Next\n**\"continues\"** resumes the {R} RED loop at **H156** {EM} "
        f"`media/mount_ops.py`, `media/auto_mount.py`, `media/udisks2.py` no `CapabilityManager` gate "
        f"on the privileged mount path. (The separate {Y} loop pointer is unchanged: H66.)",
    ),
]
replace_pairs(".workbuddy-ai/memory/2026-10-09.md", log_pairs)

print("ALL BOOKKEEPING DONE")
