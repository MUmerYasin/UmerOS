#!/usr/bin/env python3
"""
UmerOS - /etc/exports manager
FHS 3.0: /etc/exports defines NFS exported filesystems.
/etc/exports.d/ directory contains additional export files.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, List, Optional

EXPORTS_PATH = Path(os.environ.get("UMEROS_EXPORTS", "/etc/exports"))
EXPORTS_D_PATH = Path(os.environ.get("UMEROS_EXPORTS_D", "/etc/exports.d"))

DEFAULT_EXPORTS = """# /etc/exports - UmerOS NFS exports
# Format: directory client(options) client(options) ...
# /home/shared  192.168.1.0/24(rw,sync,no_subtree_check)
"""


class NFSExportsManager:
    """Manages NFS export definitions in /etc/exports."""

    def __init__(self, exports_path: str = None, exports_d: str = None):
        self.path = Path(exports_path) if exports_path else EXPORTS_PATH
        self.dir_path = Path(exports_d) if exports_d else EXPORTS_D_PATH

    def _ensure_files(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.dir_path.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(DEFAULT_EXPORTS, encoding="utf-8")

    def read_exports(self) -> List[Dict]:
        self._ensure_files()
        entries = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            entries.append({"raw": line, "source": str(self.path)})
        return entries

    def add_export(self, directory: str, clients: str) -> None:
        line = f"{directory} {clients}"
        with self.path.open("a", encoding="utf-8") as f:
            f.write(f"\n{line}")

    def remove_export(self, directory: str) -> bool:
        lines = self.path.read_text(encoding="utf-8").splitlines()
        new_lines = [l for l in lines if not l.strip().startswith(directory + " ")]
        if len(new_lines) != len(lines):
            self.path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            return True
        return False

    def reload(self) -> List[str]:
        """Simulate 'exportfs -r' — reload exports."""
        exports = self.read_exports()
        return [e["raw"] for e in exports]
