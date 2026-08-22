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
UmerOS /sources — Standards, Bibliography, Signals & Kernel Documentation
==========================================================================

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
License: GPL-3.0 (GNU General Public License Version 3) 
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
