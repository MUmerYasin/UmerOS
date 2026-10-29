"""Unified Data Object container for UmerOS UDMF.

Encapsulates multiple type representations of the same data
with access authorization checks.
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .utd_registry import UTDRegistry, UniformTypeDescriptor


@dataclass
class DataRepresentation:
    """A single representation of data in a specific UTD type."""
    utd_type: str
    data: Any
    mime_type: Optional[str] = None
    encoding: str = "utf-8"
    size_bytes: int = 0

    def __post_init__(self):
        if self.size_bytes == 0 and self.data is not None:
            if isinstance(self.data, bytes):
                self.size_bytes = len(self.data)
            elif isinstance(self.data, str):
                self.size_bytes = len(self.data.encode(self.encoding))
            else:
                self.size_bytes = len(str(self.data).encode(self.encoding))

    def to_dict(self) -> dict:
        return {
            "utd_type": self.utd_type,
            "mime_type": self.mime_type,
            "encoding": self.encoding,
            "size_bytes": self.size_bytes,
            "data": self.data if not isinstance(self.data, bytes) else base64.b64encode(self.data).decode("ascii"),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DataRepresentation":
        data = d["data"]
        if d.get("encoding") == "base64" or isinstance(data, str) and len(data) > 100:
            try:
                data = base64.b64decode(data)
            except Exception:
                pass
        return cls(
            utd_type=d["utd_type"],
            data=data,
            mime_type=d.get("mime_type"),
            encoding=d.get("encoding", "utf-8"),
            size_bytes=d.get("size_bytes", 0),
        )


@dataclass
class UnifiedData:
    """Unified Data Object containing multiple representations.

    Supports access authorization via scoped tokens.
    """
    representations: List[DataRepresentation] = field(default_factory=list)
    source_app: Optional[str] = None
    source_node: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    token: Optional[str] = None  # scoped access token
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_representation(self, rep: DataRepresentation) -> None:
        self.representations.append(rep)

    def get_representation(self, utd_type: str, registry: Optional[UTDRegistry] = None) -> Optional[DataRepresentation]:
        """Get the best matching representation for a UTD type."""
        reg = registry or UTDRegistry()
        # Exact match first
        for rep in self.representations:
            if rep.utd_type == utd_type:
                return rep
        # Conformance match
        for rep in self.representations:
            if reg.conforms(rep.utd_type, utd_type):
                return rep
        return None

    def has_type(self, utd_type: str, registry: Optional[UTDRegistry] = None) -> bool:
        return self.get_representation(utd_type, registry) is not None

    def primary_type(self) -> Optional[str]:
        if not self.representations:
            return None
        return self.representations[0].utd_type

    def total_size(self) -> int:
        return sum(r.size_bytes for r in self.representations)

    def content_hash(self) -> str:
        h = hashlib.sha256()
        for rep in self.representations:
            if isinstance(rep.data, bytes):
                h.update(rep.data)
            elif isinstance(rep.data, str):
                h.update(rep.data.encode(rep.encoding))
        return h.hexdigest()

    def to_dict(self) -> dict:
        return {
            "representations": [r.to_dict() for r in self.representations],
            "source_app": self.source_app,
            "source_node": self.source_node,
            "created_at": self.created_at,
            "token": self.token,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "UnifiedData":
        ud = cls(
            source_app=d.get("source_app"),
            source_node=d.get("source_node"),
            created_at=d.get("created_at", time.time()),
            token=d.get("token"),
            metadata=d.get("metadata", {}),
        )
        for r in d.get("representations", []):
            ud.add_representation(DataRepresentation.from_dict(r))
        return ud

    def __repr__(self) -> str:
        types = [r.utd_type for r in self.representations]
        return f"UnifiedData(types={types}, size={self.total_size()})"