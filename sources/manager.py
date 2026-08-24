# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
UmerOS /sources — Master Sources, Specifications & Standards Manager
====================================================================

Central coordinator for bibliography, System V signals,
architecture glossary, kernel documentation specifications, and source tree management.

Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3) 
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .bibliography import BibliographyRegistry, SourceCategory, SourceReference
from .glossary import GlossaryEntry, GlossaryRegistry
from .signals import SignalAction, SignalDispatcher, SignalSpec
from .specs_parser import KernelDocsRegistry
from .source_tree import SourceTreeManager

log = logging.getLogger("UmerOS.Sources.Manager")


class SourcesManager:
    """Master manager for Filesystem Hierarchy sources, signals, and specs."""

    def __init__(self) -> None:
        self.bibliography = BibliographyRegistry()
        self.signals = SignalDispatcher()
        self.glossary = GlossaryRegistry()
        self.kernel_docs = KernelDocsRegistry()
        self.source_tree = SourceTreeManager()

    def search_all(self, query: str) -> Dict[str, Any]:
        """
        Unified search across bibliography, glossary, signals, and kernel documentation.
        """
        bib_results = [s.to_dict() for s in self.bibliography.search(query)]
        gloss_results = [g.to_dict() for g in self.glossary.search(query)]
        doc_results = self.kernel_docs.search_docs(query)
        
        # Check signals
        sig_results = []
        sig_match = self.signals.get_signal(query)
        if sig_match:
            sig_results.append(sig_match.to_dict())
        else:
            for s in self.signals.list_signals():
                if query.lower() in s.name.lower() or query.lower() in s.description.lower():
                    sig_results.append(s.to_dict())

        return {
            "query": query,
            "total_matches": len(bib_results) + len(gloss_results) + len(doc_results) + len(sig_results),
            "bibliography": bib_results,
            "glossary": gloss_results,
            "kernel_docs": doc_results,
            "signals": sig_results,
        }

    def get_summary(self) -> Dict[str, Any]:
        """Returns statistical overview of sources, signals, and glossary."""
        return {
            "total_bibliography_sources": len(self.bibliography.list_all()),
            "total_glossary_terms": len(self.glossary.list_all()),
            "total_signals_defined": len(self.signals.list_signals()),
            "total_kernel_specs": len(self.kernel_docs.list_docs()),
            "source_tree_packages": len(self.source_tree.list_source_packages()),
        }


# ── Global Default Helper Functions ──────────────────────────────────────

_global_sources_mgr: Optional[SourcesManager] = None


def get_default_sources_manager() -> SourcesManager:
    global _global_sources_mgr
    if _global_sources_mgr is None:
        _global_sources_mgr = SourcesManager()
    return _global_sources_mgr
