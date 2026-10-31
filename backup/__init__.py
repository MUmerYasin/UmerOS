# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# [REFERENCE-ONLY] Not reachable from main.py — see docs/reference_corpus.md

"""
UmerOS Backup & Factory Reset Subsystem
=======================================

Provides incremental filesystem snapshotting,
restore capabilities, and factory reset mechanisms. 

Snapshots use hardlinks to minimize disk usage (rsync mode paradigm).
"""

from .models import Snapshot, SnapshotLevel
from .snapshot_engine import SnapshotEngine
from .restore import RestoreEngine
from .factory_reset import FactoryResetManager
from .filters import PathFilter

__all__ = [
    "Snapshot",
    "SnapshotLevel",
    "SnapshotEngine",
    "RestoreEngine",
    "FactoryResetManager",
    "PathFilter",
]


def _selftest() -> bool:
    """Verify the public surface is importable."""
    import importlib
    import sys

    pkg = importlib.import_module(__name__)
    missing = [n for n in __all__ if not hasattr(pkg, n)]
    if missing:
        print(f"backup selftest FAIL: missing {missing}", file=sys.stderr)
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
