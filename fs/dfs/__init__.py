"""UmerOS Distributed File System (UmerDFS) & CRDT Distributed Data Objects."""
from __future__ import annotations

from .distributed_vfs import DistributedVFS
from .crdt_object import DistributedDataObject, LWWRegister

__all__ = ["DistributedVFS", "DistributedDataObject", "LWWRegister"]