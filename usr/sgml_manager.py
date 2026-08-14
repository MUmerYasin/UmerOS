"""
UmerOS SGML Manager (/usr/share/sgml)
======================================
SGML (Standard Generalized Markup Language) data and DTDs.

Reference: Filesystem Hierarchy - /usr/share/sgml
  /usr/share/sgml contains SGML document type definitions (DTDs),
  catalogs, and other SGML-related data files.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ─── Constants ───────────────────────────────────────────────────────────────

SGML_PATH = "/usr/share/sgml"

SGML_CATEGORIES = {
    "DTD": "Document Type Definitions",
    "CATALOG": "SGML catalogs",
    "DTDDECL": "DTD declarations",
    "ENTITIES": "Entity definitions",
    "STYLE": "Style sheets",
    "OTHER": "Other SGML resources",
}

COMMON_DTD = [
    ("DocBook", "DocBook XML/SGML DTD", "docbook"),
    ("HTML", "HTML DTD", "html"),
    ("XML", "XML DTD", "xml"),
    ("TEI", "TEI (Text Encoding Initiative) DTD", "tei"),
    ("DSSSL", "DSSSL (Document Style Semantics and Specification Language)", "dsssl"),
    ("SGML", "SGML declaration", "sgml"),
    ("ISO-8879", "ISO 8879 SGML standard", "iso-8879"),
    ("ISO-639", "ISO 639 language codes", "iso-639"),
    ("ISO-3166", "ISO 3166 country codes", "iso-3166"),
    ("ISO-4217", "ISO 4217 currency codes", "iso-4217"),
    ("MATHML", "Mathematical Markup Language", "mathml"),
    ("SVG", "Scalable Vector Graphics DTD", "svg"),
    ("XHTML", "XHTML DTD", "xhtml"),
]


# ─── Enums ───────────────────────────────────────────────────────────────────

class SgmlDtdType(IntEnum):
    """SGML DTD types."""
    DTD = 1
    CATALOG = 2
    DTDDECL = 3
    ENTITIES = 4
    STYLE = 5
    OTHER = 99


class SgmlStatus(IntEnum):
    """SGML data status."""
    ACTIVE = 1
    DEPRECATED = 2
    REMOVED = 3


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class SgmlDtd:
    """Represents an SGML DTD or resource."""
    name: str
    path: str
    dtd_type: SgmlDtdType = SgmlDtdType.DTD
    description: str = ""
    version: str = ""
    public_id: str = ""
    system_id: str = ""
    status: SgmlStatus = SgmlStatus.ACTIVE
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "dtd_type": self.dtd_type.name,
            "description": self.description,
            "version": self.version,
            "public_id": self.public_id,
            "system_id": self.system_id,
            "status": self.status.name,
            "dependencies": self.dependencies,
        }


@dataclass
class SgmlCatalog:
    """An SGML catalog entry."""
    name: str
    path: str
    entries: Dict[str, str] = field(default_factory=dict)
    description: str = ""
    status: SgmlStatus = SgmlStatus.ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "entries": self.entries,
            "description": self.description,
            "status": self.status.name,
        }


# ─── Global State ────────────────────────────────────────────────────────────

_global_sgml_manager: Optional["SgmlManager"] = None


# ─── Main Manager Class ─────────────────────────────────────────────────────

class SgmlManager:
    """Manages /usr/share/sgml - SGML data and DTDs."""

    def __init__(self) -> None:
        self._dtds: Dict[str, SgmlDtd] = {}
        self._catalogs: Dict[str, SgmlCatalog] = {}
        self._initialize_default_dtds()

    def _initialize_default_dtds(self) -> None:
        """Initialize with common DTDs."""
        for name, desc, folder in COMMON_DTD:
            dtd = SgmlDtd(
                name=name,
                path=f"/usr/share/sgml/{folder}",
                description=desc,
            )
            self._dtds[name] = dtd

    def get_dtd(self, name: str) -> Optional[SgmlDtd]:
        """Get a DTD by name."""
        return self._dtds.get(name)

    def list_dtds(self, dtd_type: Optional[SgmlDtdType] = None) -> List[SgmlDtd]:
        """List all DTDs, optionally filtered by type."""
        dtds = list(self._dtds.values())
        if dtd_type is not None:
            dtds = [d for d in dtds if d.dtd_type == dtd_type]
        return sorted(dtds, key=lambda d: d.name)

    def search_dtds(self, query: str) -> List[SgmlDtd]:
        """Search DTDs by name or description."""
        query_lower = query.lower()
        results = []
        for dtd in self._dtds.values():
            if (query_lower in dtd.name.lower() or
                query_lower in dtd.description.lower()):
                results.append(dtd)
        return results

    def register_dtd(self, dtd: SgmlDtd) -> None:
        """Register a new DTD."""
        self._dtds[dtd.name] = dtd

    def get_catalog(self, name: str) -> Optional[SgmlCatalog]:
        """Get a catalog by name."""
        return self._catalogs.get(name)

    def list_catalogs(self) -> List[SgmlCatalog]:
        """List all catalogs."""
        return sorted(self._catalogs.values(), key=lambda c: c.name)

    def register_catalog(self, catalog: SgmlCatalog) -> None:
        """Register a new catalog."""
        self._catalogs[catalog.name] = catalog

    def get_statistics(self) -> Dict[str, Any]:
        """Get SGML statistics."""
        by_type: Dict[str, int] = {}
        for dtd in self._dtds.values():
            t = dtd.dtd_type.name
            by_type[t] = by_type.get(t, 0) + 1
        return {
            "total_dtds": len(self._dtds),
            "total_catalogs": len(self._catalogs),
            "by_type": by_type,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize manager to dictionary."""
        return {
            "dtds": {k: v.to_dict() for k, v in self._dtds.items()},
            "catalogs": {k: v.to_dict() for k, v in self._catalogs.items()},
            "statistics": self.get_statistics(),
        }


# ─── Singleton Getter ────────────────────────────────────────────────────────

def get_global_sgml_manager() -> SgmlManager:
    """Get or create the global SgmlManager instance."""
    global _global_sgml_manager
    if _global_sgml_manager is None:
        _global_sgml_manager = SgmlManager()
    return _global_sgml_manager


def initialize() -> SgmlManager:
    """Initialize and return the global SgmlManager."""
    return get_global_sgml_manager()


def refresh() -> SgmlManager:
    """Refresh the global SgmlManager."""
    global _global_sgml_manager
    _global_sgml_manager = SgmlManager()
    return _global_sgml_manager
