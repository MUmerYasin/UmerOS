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
UmerOS Man Page System
======================
Manual page system implementation based on /usr/share/man.

The man page system organizes documentation into 8 sections:
  man1 - User programs (publicly accessible commands)
  man2 - System calls (kernel operation requests)
  man3 - Library functions and subroutines
  man4 - Special files (device files, kernel interfaces)
  man5 - File formats
  man6 - Games
  man7 - Miscellaneous (difficult to classify)
  man8 - System administration programs

This module provides parsing, searching, and rendering of man pages
in groff/troff format, section management, and cross-reference resolution.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import (
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
)


# ============================================================================
# Constants
# ============================================================================

MAN_PATHS: List[str] = [
    "/usr/share/man",
    "/usr/local/share/man",
    "/usr/man",
    "/usr/local/man",
]

MAN_SECTIONS: List[str] = [
    "man1", "man2", "man3", "man4",
    "man5", "man6", "man7", "man8",
]

MAN_EXTENSIONS: List[str] = ["", ".gz", ".bz2", ".xz", ".zst"]

NROFF_COMMANDS: Set[str] = {
    ".TH", ".SH", ".SS", ".TP", ".IP", ".PP", ".LP",
    ".BR", ".BI", ".IB", ".IR", ".B", ".I", ".SB",
    ".SM", ".RS", ".RE", ".nf", ".fi", ".sp", ".br",
    ".na", ".ad", ".in", ".ti", ".nf", ".fi",
}


# ============================================================================
# Enums
# ============================================================================

class ManSection(IntEnum):
    """Manual page sections per FHS/ convention."""
    USER_PROGRAMS = 1
    SYSTEM_CALLS = 2
    LIBRARY_FUNCTIONS = 3
    SPECIAL_FILES = 4
    FILE_FORMATS = 5
    GAMES = 6
    MISCELLANEOUS = 7
    SYS_ADMIN = 8


class ManPageFormat(IntEnum):
    """Man page source formats."""
    GROFF = 0
    NROFF = 1
    TROFF = 2
    MAN = 3
    HTML = 4
    CAT = 5


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class ManHeader:
    """Parsed man page header from .TH directive."""
    title: str = ""
    section: int = 0
    date: str = ""
    source: str = ""
    manual: str = ""


@dataclass
class ManSectionNode:
    """A parsed section within a man page."""
    heading: str = ""
    content: str = ""
    subsections: List[ManSectionNode] = field(default_factory=list)
    indent_level: int = 0


@dataclass
class ManPage:
    """Complete parsed man page."""
    name: str = ""
    section: int = 0
    header: ManHeader = field(default_factory=ManHeader)
    format: ManPageFormat = ManPageFormat.GROFF
    source_path: str = ""
    sections: List[ManSectionNode] = field(default_factory=list)
    raw_content: str = ""
    see_also: List[str] = field(default_factory=list)
    description: str = ""
    synopsis: str = ""

    def get_section(self, heading: str) -> Optional[ManSectionNode]:
        """Find a section by heading (case-insensitive)."""
        heading_lower = heading.lower()
        for sec in self.sections:
            if sec.heading.lower() == heading_lower:
                return sec
        return None

    def get_description(self) -> str:
        """Get the NAME/DESCRIPTION section content."""
        for sec in self.sections:
            if sec.heading.upper() in ("NAME", "DESCRIPTION"):
                return sec.content
        return self.description

    def get_synopsis(self) -> str:
        """Get the SYNOPSIS section content."""
        for sec in self.sections:
            if sec.heading.upper() == "SYNOPSIS":
                return sec.content
        return self.synopsis

    def get_see_also(self) -> List[str]:
        """Get SEE ALSO references."""
        return self.see_also

    def to_text(self) -> str:
        """Render man page to plain text."""
        lines: List[str] = []
        if self.header.title:
            lines.append(
                f"{self.header.title.upper()}({self.header.section})"
                f"                    User Manual                    "
                f"{self.header.title.upper()}({self.header.section})"
            )
            lines.append("")
        for sec in self.sections:
            lines.append(sec.heading.upper())
            lines.append("-" * len(sec.heading))
            lines.append(sec.content)
            for subsec in sec.subsections:
                lines.append(f"  {subsec.heading}")
                lines.append(f"  {subsec.content}")
            lines.append("")
        return "\n".join(lines)


@dataclass
class ManSearchResult:
    """Result from a man page search."""
    page: ManPage
    relevance: float = 0.0
    match_field: str = ""


@dataclass
class ManEntry:
    """An entry in the man page database (whatis database)."""
    name: str = ""
    section: int = 0
    description: str = ""
    source_path: str = ""


class ManPageStatus(IntEnum):
    """Lifecycle status of a (pre-formatted) cat page.

    [FIX import-time NameError] This enum was referenced by ``CatPage.status``
    (and used when building parse results) but never defined, which crashed
    ``import usr.man_page`` (and therefore ``import usr``) with a NameError.
    """
    MISSING = 0
    PARSED = 1


@dataclass
class CatPage:
    """Represents a pre-formatted (cat) page.

    FHS 3.0 Section 4.4: Cat pages are pre-compiled man pages stored
    in /usr/share/man/<section>/cat<name>.n.<section> for fast display
    without re-running groff/nroff.

    Cat pages SHOULD be generated at install time by the package manager
    and SHOULD be in the same section directory as the source man page.
    """
    name: str = ""
    section: int = 1
    path: Optional[str] = None
    status: ManPageStatus = ManPageStatus.MISSING
    file_size: int = 0
    source_man_page: Optional[str] = None
    last_modified: float = 0.0
    encoding: str = "utf-8"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "section": self.section,
            "path": self.path,
            "status": self.status.value,
            "file_size": self.file_size,
            "source_man_page": self.source_man_page,
            "last_modified": self.last_modified,
            "encoding": self.encoding,
        }


# ============================================================================
# Parser
# ============================================================================

class ManPageParser:
    """Parser for groff/nroff man page format."""

    @staticmethod
    def parse_th(line: str) -> Optional[ManHeader]:
        """Parse .TH directive: .TH title section date source manual."""
        parts = line.split(None, 4)
        if len(parts) < 2:
            return None
        header = ManHeader()
        header.title = parts[1].strip('"')
        try:
            header.section = int(parts[2]) if len(parts) > 2 else 0
        except (ValueError, IndexError):
            header.section = 0
        header.date = parts[3].strip('"') if len(parts) > 3 else ""
        header.source = parts[4].strip('"') if len(parts) > 4 else ""
        return header

    @staticmethod
    def parse_section(content: str) -> List[ManSectionNode]:
        """Parse content into section nodes."""
        sections: List[ManSectionNode] = []
        current: Optional[ManSectionNode] = None
        lines = content.split("\n")

        for line in lines:
            stripped = line.strip()
            if stripped.startswith(".SH"):
                heading = stripped[3:].strip().strip('"')
                current = ManSectionNode(heading=heading)
                sections.append(current)
            elif stripped.startswith(".SS"):
                heading = stripped[3:].strip().strip('"')
                subsec = ManSectionNode(heading=heading)
                if current is not None:
                    current.subsections.append(subsec)
            elif stripped.startswith(".TP"):
                pass  # Tagged paragraph - next line is the tag
            elif stripped.startswith(".IP"):
                pass  # Indented paragraph
            elif stripped.startswith(".PP") or stripped.startswith(".LP"):
                pass  # Paragraph
            elif stripped.startswith(".BR"):
                pass  # Bold/Roman alternating
            elif stripped.startswith(".BI"):
                pass  # Bold/Italic alternating
            elif stripped.startswith(".IB"):
                pass  # Italic/Bold alternating
            elif stripped.startswith(".IR"):
                pass  # Italic/Roman alternating
            elif stripped.startswith(".B "):
                pass  # Bold text
            elif stripped.startswith(".I "):
                pass  # Italic text
            elif stripped.startswith(".RS"):
                pass  # Right margin start
            elif stripped.startswith(".RE"):
                pass  # Right margin end
            elif stripped.startswith(".nf"):
                pass  # No fill mode
            elif stripped.startswith(".fi"):
                pass  # Fill mode
            elif stripped.startswith(".sp"):
                pass  # Vertical space
            elif stripped.startswith(".br"):
                pass  # Break
            elif not stripped.startswith("."):
                if current is not None:
                    current.content += stripped + "\n"

        return sections

    @staticmethod
    def strip_groff(text: str) -> str:
        """Strip groff formatting commands from text."""
        lines = text.split("\n")
        result: List[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("."):
                continue
            # Remove inline formatting
            cleaned = re.sub(r"\\f[BI]", "", stripped)
            cleaned = re.sub(r"\\fR", "", cleaned)
            cleaned = re.sub(r"\\[a-zA-Z]+", "", cleaned)
            cleaned = re.sub(r"\*\*[^*]+\*\*", "", cleaned)
            result.append(cleaned)
        return "\n".join(result)


# ============================================================================
# Man Page Manager
# ============================================================================

class ManPageManager:
    """
    Manages the manual page system for UmerOS.

    Handles loading, parsing, searching, and rendering of man pages
    from /usr/share/man and related directories.
    """

    def __init__(self) -> None:
        self._man_paths: List[str] = list(MAN_PATHS)
        self._pages: Dict[str, ManPage] = {}
        self._entries: Dict[str, List[ManEntry]] = {}
        self._section_index: Dict[int, List[str]] = {}
        self._aliases: Dict[str, str] = {}
        self._cache_enabled: bool = True
        self._raw_cache: Dict[str, str] = {}

    # -- Path Management --

    def add_man_path(self, path: str) -> None:
        """Add a man page search path."""
        if path not in self._man_paths:
            self._man_paths.append(path)

    def get_man_paths(self) -> List[str]:
        """Get all configured man page paths."""
        return list(self._man_paths)

    # -- Loading --

    def load_page(self, name: str, section: Optional[int] = None) -> Optional[ManPage]:
        """Load a man page by name and optional section."""
        search_sections = [section] if section else list(ManSection)
        for sec in search_sections:
            for path in self._man_paths:
                for ext in MAN_EXTENSIONS:
                    filename = f"man{sec}/{name}.{sec}{ext}"
                    full_path = os.path.join(path, filename)
                    if os.path.exists(full_path):
                        return self._load_from_file(full_path, name, sec)
        return None

    def _load_from_file(
        self, filepath: str, name: str, section: int
    ) -> ManPage:
        """Load a man page from a file."""
        content = ""
        try:
            if filepath.endswith(".gz"):
                import gzip
                with gzip.open(filepath, "rt", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            elif filepath.endswith(".bz2"):
                import bz2
                with bz2.open(filepath, "rt", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            elif filepath.endswith(".xz"):
                import lzma
                with lzma.open(filepath, "rt", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            else:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
        except (OSError, IOError):
            pass

        return self._parse_content(content, name, section, filepath)

    def _parse_content(
        self, content: str, name: str, section: int, source_path: str
    ) -> ManPage:
        """Parse man page content."""
        page = ManPage(
            name=name,
            section=section,
            source_path=source_path,
            raw_content=content,
        )

        parser = ManPageParser()
        header = parser.parse_th(content)
        if header:
            page.header = header

        sections = parser.parse_section(content)
        page.sections = sections

        for sec in sections:
            if sec.heading.upper() == "SEE ALSO":
                refs = re.findall(r"(\w+)\(\d\)", sec.content)
                page.see_also = refs
            elif sec.heading.upper() == "NAME":
                page.description = sec.content.strip()
            elif sec.heading.upper() == "SYNOPSIS":
                page.synopsis = sec.content.strip()

        return page

    def load_all(self) -> int:
        """Load all available man pages. Returns count loaded."""
        count = 0
        for path in self._man_paths:
            for section in ManSection:
                sec_dir = os.path.join(path, f"man{section}")
                if not os.path.isdir(sec_dir):
                    continue
                for filename in os.listdir(sec_dir):
                    name = filename.split(".")[0]
                    full_path = os.path.join(sec_dir, filename)
                    if os.path.isfile(full_path):
                        page = self._load_from_file(full_path, name, section)
                        key = f"{name}({section})"
                        self._pages[key] = page
                        count += 1
        return count

    # -- Searching --

    def search(
        self, query: str, section: Optional[int] = None
    ) -> List[ManSearchResult]:
        """Search man pages by name or description."""
        results: List[ManSearchResult] = []
        query_lower = query.lower()

        for key, page in self._pages.items():
            if section is not None and page.section != section:
                continue
            relevance = 0.0
            field_name = ""

            if query_lower == page.name.lower():
                relevance = 1.0
                field_name = "name"
            elif query_lower in page.name.lower():
                relevance = 0.8
                field_name = "name"
            elif query_lower in page.description.lower():
                relevance = 0.5
                field_name = "description"
            elif query_lower in page.raw_content.lower():
                relevance = 0.3
                field_name = "content"

            if relevance > 0:
                results.append(
                    ManSearchResult(
                        page=page,
                        relevance=relevance,
                        match_field=field_name,
                    )
                )

        results.sort(key=lambda r: r.relevance, reverse=True)
        return results

    def lookup(self, name: str, section: Optional[int] = None) -> List[ManPage]:
        """Look up man pages by exact name."""
        results: List[ManPage] = []
        for key, page in self._pages.items():
            if page.name == name:
                if section is None or page.section == section:
                    results.append(page)
        return results

    def whatis(self, name: str) -> List[ManEntry]:
        """Query the whatis database for a name."""
        entries: List[ManEntry] = []
        for key, page in self._pages.items():
            if page.name == name:
                entries.append(
                    ManEntry(
                        name=page.name,
                        section=page.section,
                        description=page.description,
                        source_path=page.source_path,
                    )
                )
        return entries

    def apropos(self, keyword: str) -> List[ManEntry]:
        """Search all man page descriptions for a keyword."""
        entries: List[ManEntry] = []
        keyword_lower = keyword.lower()
        for key, page in self._pages.items():
            if keyword_lower in page.description.lower():
                entries.append(
                    ManEntry(
                        name=page.name,
                        section=section,
                        description=page.description,
                        source_path=page.source_path,
                    )
                )
        return entries

    # -- Section Management --

    def get_pages_in_section(self, section: int) -> List[ManPage]:
        """Get all man pages in a specific section."""
        return [
            page for page in self._pages.values()
            if page.section == section
        ]

    def get_section_list(self) -> Dict[int, int]:
        """Get section numbers and their page counts."""
        counts: Dict[int, int] = {}
        for page in self._pages.values():
            counts[page.section] = counts.get(page.section, 0) + 1
        return counts

    # -- Rendering --

    def render_text(self, name: str, section: Optional[int] = None) -> str:
        """Render a man page to plain text."""
        pages = self.lookup(name, section)
        if not pages:
            return f"No manual entry for {name}"
        return pages[0].to_text()

    def render_section(self, name: str, section: int, heading: str) -> str:
        """Render a specific section of a man page."""
        pages = self.lookup(name, section)
        if not pages:
            return f"No manual entry for {name} in section {section}"
        page = pages[0]
        sec = page.get_section(heading)
        if sec is None:
            return f"No {heading} section in {name}({section})"
        return sec.content

    # -- Cat Page Management (FHS 3.0 Section 4.4) --

    def _cat_path(self, name: str, section: int) -> str:
        """Compute cat page path per FHS 3.0 naming convention.

        Pattern: <man_path>/<section>/cat<name>.<section>
        """
        return os.path.join(self._base_path, str(section), f"cat{name}.{section}")

    def generate_cat_page(self, name: str, section: int,
                          force: bool = False) -> Optional[CatPage]:
        """Generate a cat page from a source man page.

        FHS 3.0: Cat pages are pre-compiled man pages for fast display.
        They should be generated at install time and stored alongside
        the source man page in the section directory.

        Args:
            name: Man page name (e.g., "ls")
            section: Section number (1-8)
            force: Regenerate even if cat page exists

        Returns:
            CatPage if generated/exists, None if source missing
        """
        # Find the source man page
        pages = self.lookup(name, section)
        if not pages:
            return None

        source_page = pages[0]
        cat_path = self._cat_path(name, section)

        # Check if cat page already exists
        if os.path.exists(cat_path) and not force:
            stat = os.stat(cat_path)
            return CatPage(
                name=name,
                section=section,
                path=cat_path,
                status=ManPageStatus.PARSED,
                file_size=stat.st_size,
                source_man_page=source_page.source_path,
                last_modified=stat.st_mtime,
            )

        # Generate cat content from source
        try:
            content = source_page.to_text()
            os.makedirs(os.path.dirname(cat_path), exist_ok=True)
            with open(cat_path, 'w', encoding='utf-8') as f:
                f.write(content)
            stat = os.stat(cat_path)
            return CatPage(
                name=name,
                section=section,
                path=cat_path,
                status=ManPageStatus.PARSED,
                file_size=stat.st_size,
                source_man_page=source_page.source_path,
                last_modified=stat.st_mtime,
            )
        except Exception:
            return None

    def read_cat_page(self, name: str, section: int) -> Optional[CatPage]:
        """Read an existing cat page without regeneration.

        Returns:
            CatPage if found, None otherwise
        """
        cat_path = self._cat_path(name, section)
        if not os.path.exists(cat_path):
            return None
        try:
            stat = os.stat(cat_path)
            return CatPage(
                name=name,
                section=section,
                path=cat_path,
                status=ManPageStatus.PARSED,
                file_size=stat.st_size,
                last_modified=stat.st_mtime,
            )
        except Exception:
            return None

    def get_all_cat_pages(self) -> List[CatPage]:
        """List all cat pages across all sections."""
        results: List[CatPage] = []
        for subdir in os.listdir(self._base_path):
            section_path = os.path.join(self._base_path, subdir)
            if not os.path.isdir(section_path):
                continue
            for fname in os.listdir(section_path):
                if fname.startswith("cat") and "." in fname:
                    full_path = os.path.join(section_path, fname)
                    stat = os.stat(full_path)
                    # Parse name and section from cat<name>.<section>
                    base = fname[3:]  # strip "cat"
                    parts = base.rsplit(".", 1)
                    if len(parts) == 2:
                        page_name, sec_str = parts
                        try:
                            sec = int(sec_str)
                        except ValueError:
                            sec = 0
                    else:
                        page_name = base
                        sec = 0
                    results.append(CatPage(
                        name=page_name,
                        section=sec,
                        path=full_path,
                        status=ManPageStatus.PARSED,
                        file_size=stat.st_size,
                        last_modified=stat.st_mtime,
                    ))
        return results

    def remove_cat_page(self, name: str, section: int) -> bool:
        """Remove a cat page."""
        cat_path = self._cat_path(name, section)
        if os.path.exists(cat_path):
            try:
                os.remove(cat_path)
                return True
            except Exception:
                return False
        return False

    # -- Aliases --

    def add_alias(self, alias: str, target: str) -> None:
        """Add a man page alias."""
        self._aliases[alias] = target

    def resolve_alias(self, name: str) -> str:
        """Resolve a man page alias."""
        return self._aliases.get(name, name)

    # -- Cache --

    def enable_cache(self, enabled: bool) -> None:
        """Enable or disable page caching."""
        self._cache_enabled = enabled

    def clear_cache(self) -> None:
        """Clear the page cache."""
        self._raw_cache.clear()
        self._pages.clear()

    # -- Utility --

    def list_pages(self) -> List[Tuple[str, int]]:
        """List all loaded man pages as (name, section) tuples."""
        return [(page.name, page.section) for page in self._pages.values()]

    def page_count(self) -> int:
        """Get the total number of loaded man pages."""
        return len(self._pages)

    def section_count(self) -> int:
        """Get the number of sections with pages."""
        return len(set(p.section for p in self._pages.values()))


# ============================================================================
# Global Singleton
# ============================================================================

_global_man: Optional[ManPageManager] = None


def get_global_man() -> ManPageManager:
    """Get or create the global ManPageManager instance."""
    global _global_man
    if _global_man is None:
        _global_man = ManPageManager()
    return _global_man
