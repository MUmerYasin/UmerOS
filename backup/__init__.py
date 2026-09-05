# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

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
