"""
UmerOS /sources — Standards, Bibliography, Signals & Kernel Documentation
==========================================================================

FHS & TLDP-compliant implementation of the reference standards, System V
signals specification, architecture glossary, kernel specifications, and
source code repositories.

TLDP Reference:
https://tldp.org/LDP/Linux-Filesystem-Hierarchy/html/sources.html
https://tldp.org/LDP/Linux-Filesystem-Hierarchy/html/signals.html
https://tldp.org/LDP/Linux-Filesystem-Hierarchy/html/glossary.html

Modules:
--------
bibliography - BibliographyRegistry, SourceReference, SourceCategory, BibTeX export
signals      - SignalDispatcher, SignalSpec, SignalAction, System V signals (1-31)
glossary     - GlossaryRegistry, GlossaryEntry, term definitions
specs_parser - KernelDocsRegistry, proc.txt, initrd.txt, runlevels parser
source_tree  - SourceTreeManager, /usr/src kernel source hierarchy
manager      - SourcesManager (master unified query & controller)
cli          - sources_ctl command line utility

Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import sys as _sys
from os import path as _p

_this_dir = _p.dirname(_p.abspath(__file__))
if _this_dir not in _sys.path:
    _sys.path.insert(0, _this_dir)

from bibliography import (
    TLDP_SOURCES,
    BibliographyRegistry,
    SourceCategory,
    SourceReference,
)
from signals import (
    SIGNALS_BY_NAME,
    SYSTEM_V_SIGNALS,
    SignalAction,
    SignalDispatcher,
    SignalSpec,
)
from glossary import (
    GLOSSARY_DATA,
    GlossaryEntry,
    GlossaryRegistry,
)
from specs_parser import (
    KernelDocSection,
    KernelDocsRegistry,
)
from source_tree import (
    DEFAULT_SRC_ROOT,
    SourcePackageMeta,
    SourceTreeManager,
)
from manager import (
    SourcesManager,
    get_default_sources_manager,
)

__version__ = "1.0.0"

__all__ = [
    # Bibliography
    "TLDP_SOURCES",
    "SourceCategory",
    "SourceReference",
    "BibliographyRegistry",
    # Signals
    "SYSTEM_V_SIGNALS",
    "SIGNALS_BY_NAME",
    "SignalAction",
    "SignalSpec",
    "SignalDispatcher",
    # Glossary
    "GLOSSARY_DATA",
    "GlossaryEntry",
    "GlossaryRegistry",
    # Kernel Specs
    "KernelDocSection",
    "KernelDocsRegistry",
    # Source Tree
    "DEFAULT_SRC_ROOT",
    "SourcePackageMeta",
    "SourceTreeManager",
    # Manager
    "SourcesManager",
    "get_default_sources_manager",
]
