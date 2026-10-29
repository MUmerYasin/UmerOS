"""UmerOS Unified Data Management Framework (UDMF) & Uniform Type Descriptors (UTD).

Standardized typed data exchange for cross-app and cross-device
drag-and-drop, clipboard, and IPC operations.
"""
from __future__ import annotations

from .utd_registry import UTDRegistry, UniformTypeDescriptor
from .unified_data import UnifiedData, DataRepresentation

__all__ = [
    "UTDRegistry",
    "UniformTypeDescriptor",
    "UnifiedData",
    "DataRepresentation",
]