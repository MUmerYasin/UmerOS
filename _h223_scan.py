"""Scan quantum/ for License trailer forms."""
from __future__ import annotations

import re
from pathlib import Path

CANON = "License: GPL-3.0 (GNU General Public License v3)"
PAT = re.compile(r"^\s*(?:#\s*)?Licen[cs]e:\s*(.+?)\s*$", re.MULTILINE)

for p in sorted(Path("quantum").rglob("*.py")):
    if "__pycache__" in str(p):
        continue
    src = p.read_text(encoding="utf-8")
    found = PAT.findall(src)
    if not found:
        print(f"{str(p):55s} NO-TRAILER")
    else:
        for v in found:
            tag = "CANON" if v == CANON.split(": ", 1)[1] else "OTHER"
            print(f"{str(p):55s} {tag}: {v[:62]}")
