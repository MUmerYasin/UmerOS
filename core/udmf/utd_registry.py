"""Uniform Type Descriptor (UTD) Registry for UmerOS UDMF.

Defines hierarchical type descriptors for standardized data exchange.
Types are organized in a tree: general.entity -> general.text -> general.plain-text
"""
from __future__ import annotations

from typing import Dict, List, Set, Optional


# Built-in UTD type hierarchy
UTD_HIERARCHY: Dict[str, Optional[str]] = {
    # Root
    "general.entity": None,
    # Text branch
    "general.text": "general.entity",
    "general.plain-text": "general.text",
    "general.html": "general.text",
    "general.rich-text": "general.text",
    "general.markdown": "general.text",
    # Media branch
    "general.media": "general.entity",
    "general.image": "general.media",
    "general.audio": "general.media",
    "general.video": "general.media",
    # File branch
    "general.file": "general.entity",
    "general.document": "general.file",
    "general.archive": "general.file",
    # UmerOS-specific types
    "umeros.quantum-qasm": "general.text",
    "umeros.task-state": "general.entity",
    "umeros.app-state": "general.entity",
    "umeros.notification": "general.entity",
}


# MIME type to UTD mapping
MIME_TO_UTD: Dict[str, str] = {
    "text/plain": "general.plain-text",
    "text/html": "general.html",
    "text/markdown": "general.markdown",
    "image/png": "general.image",
    "image/jpeg": "general.image",
    "image/gif": "general.image",
    "image/webp": "general.image",
    "audio/mpeg": "general.audio",
    "audio/wav": "general.audio",
    "video/mp4": "general.video",
    "application/pdf": "general.document",
    "application/zip": "general.archive",
    "application/x-tar": "general.archive",
}

# File extension to UTD mapping
EXT_TO_UTD: Dict[str, str] = {
    ".txt": "general.plain-text",
    ".html": "general.html",
    ".htm": "general.html",
    ".md": "general.markdown",
    ".png": "general.image",
    ".jpg": "general.image",
    ".jpeg": "general.image",
    ".gif": "general.image",
    ".webp": "general.image",
    ".mp3": "general.audio",
    ".wav": "general.audio",
    ".mp4": "general.video",
    ".pdf": "general.document",
    ".zip": "general.archive",
    ".tar": "general.archive",
    ".gz": "general.archive",
    ".qasm": "umeros.quantum-qasm",
}


class UniformTypeDescriptor:
    """A single UTD type with hierarchy support."""

    def __init__(self, type_id: str) -> None:
        self.type_id = type_id

    def parent(self) -> Optional[str]:
        return UTD_HIERARCHY.get(self.type_id)

    def ancestors(self) -> List[str]:
        """Return all ancestor type IDs including self."""
        result = [self.type_id]
        current = self.type_id
        while True:
            parent = UTD_HIERARCHY.get(current)
            if parent is None:
                break
            result.append(parent)
            current = parent
        return result

    def conforms_to(self, target_type: str) -> bool:
        """Check if this type conforms to (is a subtype of) target_type."""
        return target_type in self.ancestors()

    def __eq__(self, other) -> bool:
        if isinstance(other, UniformTypeDescriptor):
            return self.type_id == other.type_id
        if isinstance(other, str):
            return self.type_id == other
        return False

    def __hash__(self) -> int:
        return hash(self.type_id)

    def __repr__(self) -> str:
        return f"UTD({self.type_id})"

    def __str__(self) -> str:
        return self.type_id


class UTDRegistry:
    """Registry for managing and querying UTD types."""

    def __init__(self) -> None:
        self._types: Dict[str, UniformTypeDescriptor] = {}
        self._register_builtins()

    def _register_builtins(self) -> None:
        for type_id in UTD_HIERARCHY:
            self._types[type_id] = UniformTypeDescriptor(type_id)

    def register(self, type_id: str, parent: Optional[str] = None) -> UniformTypeDescriptor:
        """Register a new UTD type."""
        if parent is not None and parent not in self._types:
            raise ValueError(f"Parent type '{parent}' not registered")
        UTD_HIERARCHY[type_id] = parent
        utd = UniformTypeDescriptor(type_id)
        self._types[type_id] = utd
        return utd

    def get(self, type_id: str) -> Optional[UniformTypeDescriptor]:
        return self._types.get(type_id)

    def exists(self, type_id: str) -> bool:
        return type_id in self._types

    def conforms(self, source_type: str, target_type: str) -> bool:
        """Check if source_type conforms to target_type."""
        source = self.get(source_type)
        if source is None:
            return False
        return source.conforms_to(target_type)

    def mime_to_utd(self, mime_type: str) -> Optional[str]:
        return MIME_TO_UTD.get(mime_type)

    def ext_to_utd(self, extension: str) -> Optional[str]:
        ext = extension.lower()
        if not ext.startswith("."):
            ext = "." + ext
        return EXT_TO_UTD.get(ext)

    def list_types(self) -> List[str]:
        return list(self._types.keys())

    def children_of(self, parent_type: str) -> List[str]:
        """Return direct children of a type."""
        return [t for t, p in UTD_HIERARCHY.items() if p == parent_type]

    def all_subtypes(self, type_id: str) -> Set[str]:
        """Return all subtypes (transitive) of a type."""
        result: Set[str] = set()
        for child in self.children_of(type_id):
            result.add(child)
            result.update(self.all_subtypes(child))
        return result