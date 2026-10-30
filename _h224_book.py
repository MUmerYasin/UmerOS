"""H224 bookkeeping -- replace the truncated H224 checkpoint line."""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path(".workbuddy-ai/memory/remediation_progress.md")
lines = TARGET.read_text(encoding="utf-8").splitlines(keepends=True)

idx = None
for i, line in enumerate(lines):
    if line.startswith("- [ ] H224"):
        idx = i
        break

if idx is None:
    print("ABORT: H224 pending line not found")
    sys.exit(1)

NEW = (
    "- [x] H224 | BLUE | `quantum/backend.py:304` `IBMBackend.__init__` | "
    "**Exception text may leak token/URL** - `print(f\"IBM Backend init warning: {e}\")` "
    "can surface token/endpoint detail in stdout. Contrast: `providers/base.py` already "
    "redacts tokens in `__repr__`. | Follow the providers/base redaction pattern; log at "
    "`logger.warning` without interpolating the exception's secret-bearing fields. "
    "**RESOLVED (session 211, REAL FIX + DRIFT-CORRECTED).** Drift-recon: premise **TRUE**, "
    "line ref stale -- the `print` was at **304**, not `:291`. The module had **no `logging` "
    "import at all** and no logger, so stdout was its only diagnostic channel; the exception "
    "text was interpolated verbatim, and a `HTTPError` raised deep inside `requests` (what the "
    "IBM SDK raises on bad credentials) carries the full request URL including its query "
    "string, while some SDKs format the auth token straight into the message. Fix, following "
    "the row's remedy: (1) added `import logging` + "
    "`log = logging.getLogger(\"UmerOS.Quantum.Backend\")`; (2) new "
    "`_redact_secrets(text, *secrets)` helper scrubbing every supplied secret to `***` "
    "(`_SECRET_PLACEHOLDER`), `None`/empty and sub-`_MIN_SECRET_LEN` (4) values skipped so a "
    "1-2 char token cannot shred the diagnostic text, non-string `text` coerced with `str()`, "
    "never raises; (3) the `except Exception` branch now emits `log.warning(...)` with the "
    "backend name, `type(exc).__name__` and the **scrubbed** message -- nothing is printed; "
    "(4) the silent `except ImportError: pass` became a `log.debug` note (the optional "
    "dependency is still optional -- offline mode, not an error); (5) `IBMBackend.__repr__` "
    "added mirroring `providers/base.py::BackendSession.__repr__` -> "
    "`IBMBackend(name='ibm_brisbane', token=***, online=False)`; (6) the module docstring "
    "gained the redaction paragraph plus the section 1 `Author:  Umer OS Project` / "
    "`License: GPL-3.0 (GNU General Public License v3)` trailer, which this module lacked. "
    "Pinned by `tests/test_quantum_backend_redaction_h224.py` (24 passed): source invariants "
    "(AST walk proves **zero** `print(...)` calls anywhere in the module, `import logging` + "
    "logger present, the old `\"IBM Backend init warning\"` string gone, `log.warning(` present "
    "with `type(exc).__name__` logged separately from the untrusted message, `_redact_secrets` "
    "defined, `__repr__` present in `IBMBackend.__dict__`); scrubber unit tests (replaces the "
    "token, replaces every occurrence, multiple secrets, `None`/empty/short secrets ignored, "
    "4-char secret scrubbed, `None` text -> `\"\"`, non-string coerced, no-secret identity); and "
    "behavioural tests with a stand-in `qiskit_ibm_runtime` injected into `sys.modules` -- "
    "missing dependency stays OFFLINE and logs below WARNING with **empty stdout**, a failing "
    "`QiskitRuntimeService(...)` produces exactly one WARNING whose `getMessage()` contains "
    "`***` and `RuntimeError` but **not** the token, the offline fallbacks survive "
    "(`num_qubits == 127`, `max_shots == 4000`, `name` preserved), `repr()` masks the token "
    "and says `token=None` when there is none, and a successful init logs nothing at all. "
    "Targeted quantum set 183 passed. Next: **H225** -- 💭 provider REST tokens sent in clear "
    "with no TLS pinning (`quantum/quantum_sim.py` + `quantum/cloud/session.py`; also the "
    "sibling `_http_request` copies in `quantum/cloud/job.py` and "
    "`quantum/providers/{ionq,rigetti}_provider.py` noted during H218).\n"
)

lines[idx] = NEW
TARGET.write_text("".join(lines), encoding="utf-8")
print(f"OK: replaced line {idx + 1} with the H224 resolved entry.")
