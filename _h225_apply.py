"""H225 applier -- route every provider REST call through quantum.tls."""
from __future__ import annotations

import re
import sys
from pathlib import Path

PROVIDERS = Path("quantum/providers")
SIM = Path("quantum/quantum_sim.py")

IMPORT_ANCHOR = "from .base import ("


def _patch(path: Path, edits: list[tuple[str, str, str]], *, regex: bool = False) -> None:
    src = path.read_text(encoding="utf-8")
    for old, new, label in edits:
        if regex:
            src, n = re.subn(old, new, src)
        else:
            n = src.count(old)
            src = src.replace(old, new)
        if n != 1:
            print(f"ABORT [{path.name} / {label}]: expected 1 occurrence, found {n}")
            sys.exit(1)
        print(f"OK   [{path.name}] {label}")
    path.write_text(src, encoding="utf-8")


# ---------------------------------------------------------------------------
# braket_provider.py -- one urlopen, uses the from-import form
# ---------------------------------------------------------------------------
_patch(
    PROVIDERS / "braket_provider.py",
    [
        (
            IMPORT_ANCHOR,
            "from ..tls import tls_context\n\n" + IMPORT_ANCHOR,
            "import tls_context",
        ),
        (
            "with urlopen(req, timeout=30) as resp:",
            "with urlopen(req, timeout=30, context=tls_context()) as resp:",
            "urlopen context",
        ),
    ],
)

# ---------------------------------------------------------------------------
# ionq_provider.py -- two urlopen sites
# ---------------------------------------------------------------------------
_patch(
    PROVIDERS / "ionq_provider.py",
    [
        (
            IMPORT_ANCHOR,
            "from ..tls import tls_context\n\n" + IMPORT_ANCHOR,
            "import tls_context",
        ),
        (
            "with urllib.request.urlopen(req, timeout=timeout) as resp:",
            "with urllib.request.urlopen(\n"
            "            req, timeout=timeout, context=tls_context()\n"
            "        ) as resp:",
            "urlopen context (submit)",
        ),
        (
            "with urllib.request.urlopen(req, timeout=15) as resp:",
            "with urllib.request.urlopen(\n"
            "                req, timeout=15, context=tls_context()\n"
            "            ) as resp:",
            "urlopen context (cancel)",
        ),
    ],
)

# ---------------------------------------------------------------------------
# rigetti_provider.py -- one urlopen
# ---------------------------------------------------------------------------
_patch(
    PROVIDERS / "rigetti_provider.py",
    [
        (
            IMPORT_ANCHOR,
            "from ..tls import tls_context\n\n" + IMPORT_ANCHOR,
            "import tls_context",
        ),
        (
            "with urllib.request.urlopen(req, timeout=timeout) as resp:",
            "with urllib.request.urlopen(\n"
            "            req, timeout=timeout, context=tls_context()\n"
            "        ) as resp:",
            "urlopen context",
        ),
    ],
)

# ---------------------------------------------------------------------------
# quantum_sim.py -- 16 identical urlopen sites, all `req, timeout=<int>`
# ---------------------------------------------------------------------------
sim_src = SIM.read_text(encoding="utf-8")
sim_src, n = re.subn(
    r"urllib\.request\.urlopen\(req, timeout=(\d+)\)",
    r"urllib.request.urlopen(req, timeout=\1, context=tls_context())",
    sim_src,
)
if n != 16:
    print(f"ABORT [quantum_sim.py]: expected 16 urlopen rewrites, did {n}")
    sys.exit(1)
print(f"OK   [quantum_sim.py] {n} urlopen rewrites")

anchor = "import numpy as np\n\nlog = logging.getLogger(\"UmerOS.QuantumSim\")"
if sim_src.count(anchor) != 1:
    print("ABORT [quantum_sim.py]: import anchor not unique")
    sys.exit(1)
sim_src = sim_src.replace(
    anchor,
    "import numpy as np\n\nfrom .tls import tls_context\n\n"
    "log = logging.getLogger(\"UmerOS.QuantumSim\")",
)
print("OK   [quantum_sim.py] import tls_context")
SIM.write_text(sim_src, encoding="utf-8")

# ---------------------------------------------------------------------------
# Post-conditions: no bare urlopen left anywhere in quantum/
# ---------------------------------------------------------------------------
import py_compile

targets = [
    Path("quantum/tls.py"),
    Path("quantum/cloud/auth.py"),
    Path("quantum/cloud/job.py"),
    Path("quantum/cloud/session.py"),
    Path("quantum/providers/braket_provider.py"),
    Path("quantum/providers/ionq_provider.py"),
    Path("quantum/providers/rigetti_provider.py"),
    Path("quantum/quantum_sim.py"),
]
for t in targets:
    py_compile.compile(str(t), doraise=True)
print("all targets compile clean")

bad = []
for t in targets:
    text = t.read_text(encoding="utf-8")
    for m in re.finditer(r"urlopen\(([^)]*)\)", text):
        if "context=" not in m.group(1):
            bad.append(f"{t}: {m.group(0)[:60]}")
if bad:
    print("ABORT: bare urlopen remains:")
    for b in bad:
        print("  ", b)
    sys.exit(1)
print("post-conditions OK: every urlopen passes context=")
