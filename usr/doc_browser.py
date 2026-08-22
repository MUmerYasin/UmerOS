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
UmerOS Documentation Browser (/usr/share/doc)
==============================================
Package documentation browsing and management.

  Filesystem Hierarchy - /usr/share/doc
  /usr/share/doc contains package-specific documentation files.
  These directories often contain useful information not found in
  man pages, including templates, configuration examples, and
  detailed guides.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


# ─── Constants ───────────────────────────────────────────────────────────────

DOC_PATHS = [
    "/usr/share/doc",
    "/usr/local/share/doc",
    "/usr/doc",
]

DOC_INDEX_FILES = [
    "README",
    "README.md",
    "README.txt",
    "README.rst",
    "README.Debian",
    "README.debian",
    "README.gz",
    "README.Debian.gz",
    "README.manpages",
    "README.security",
    "changelog.Debian",
    "changelog.Debian.gz",
    "changelog.gz",
    "changelog",
    "NEWS",
    "NEWS.gz",
    "NEWS.Debian",
    "TODO",
    "TODO.Debian",
    "AUTHORS",
    "AUTHORS.gz",
    "COPYING",
    "LICENSE",
    "INSTALL",
    "BUGS",
    "HACKING",
    "CONTRIBUTING",
    "CONTRIBUTING.md",
    "CREDITS",
    "CREDITS.gz",
]

DOC_SECTIONS = {
    "examples": ["examples", "example", "demo", "demos"],
    "api": ["api", "api-docs", "apidoc"],
    "tutorials": ["tutorials", "tutorial", "howto", "how-to"],
    "faq": ["faq", "faqs"],
    "changelog": ["changelog", "changelogs", "changes", "whatsnew"],
    "license": ["license", "licenses", "copying", "legal"],
    "credits": ["credits", "authors", "contributors", "maintainers"],
    "readme": ["readme", "readmes"],
    "bugs": ["bugs", "known-issues", "limitations"],
}


# ─── Enums ───────────────────────────────────────────────────────────────────

class DocFormat(IntEnum):
    """Documentation file formats."""
    PLAIN_TEXT = 1
    MARKDOWN = 2
    RST = 3
    HTML = 4
    PDF = 5
    MAN = 6
    TEXINFO = 7
    XML = 8
    DOCBOOK = 9
    COMPRESSED = 10
    UNKNOWN = 11


class DocCategory(IntEnum):
    """Documentation categories."""
    README = 1
    API = 2
    TUTORIAL = 3
    CHANGELOG = 4
    LICENSE = 5
    CREDITS = 6
    FAQ = 7
    EXAMPLES = 8
    BUGS = 9
    GENERAL = 10
    CONFIG = 11
    SECURITY = 12


class DocStatus(IntEnum):
    """Documentation status."""
    CURRENT = 1
    OUTDATED = 2
    DEPRECATED = 3
    INCOMPLETE = 4
    MAINTAINED = 5


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class DocFile:
    """Represents a documentation file."""
    path: str
    name: str
    format: DocFormat = DocFormat.UNKNOWN
    category: DocCategory = DocCategory.GENERAL
    size: int = 0
    description: str = ""
    language: str = "en"
    compressed: bool = False
    encoding: str = "utf-8"
    last_modified: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "format": self.format.name,
            "category": self.category.name,
            "size": self.size,
            "description": self.description,
            "language": self.language,
            "compressed": self.compressed,
            "encoding": self.encoding,
        }


@dataclass
class DocPackage:
    """Documentation for a specific package."""
    name: str
    path: str
    description: str = ""
    version: str = ""
    status: DocStatus = DocStatus.CURRENT
    files: List[DocFile] = field(default_factory=list)
    sections: Dict[str, List[DocFile]] = field(default_factory=dict)
    total_size: int = 0
    languages: Set[str] = field(default_factory=set)
    has_changelog: bool = False
    has_readme: bool = False
    has_license: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "description": self.description,
            "version": self.version,
            "status": self.status.name,
            "file_count": len(self.files),
            "sections": list(self.sections.keys()),
            "total_size": self.total_size,
            "languages": sorted(self.languages),
            "has_changelog": self.has_changelog,
            "has_readme": self.has_readme,
            "has_license": self.has_license,
        }


@dataclass
class DocIndex:
    """Searchable index entry for documentation."""
    package: str
    file: str
    path: str
    category: DocCategory
    format: DocFormat
    keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package": self.package,
            "file": self.file,
            "path": self.path,
            "category": self.category.name,
            "format": self.format.name,
            "keywords": self.keywords,
        }


@dataclass
class DocSearchResult:
    """Search result from documentation."""
    package: str
    file_path: str
    title: str = ""
    snippet: str = ""
    score: float = 0.0
    category: DocCategory = DocCategory.GENERAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package": self.package,
            "file_path": self.file_path,
            "title": self.title,
            "snippet": self.snippet,
            "score": self.score,
            "category": self.category.name,
        }


# ─── Documentation Browser ──────────────────────────────────────────────────

class DocBrowser:
    """
    Manages /usr/share/doc - package documentation browsing.

    Responsibilities:
        - Discover and catalog documentation packages
        - Parse documentation files and extract metadata
        - Provide search across documentation
        - Organize docs by category and format
        - Track documentation completeness
        - Handle compressed documentation files
        - Provide browsing by package or topic
    """

    def __init__(self) -> None:
        self._packages: Dict[str, DocPackage] = {}
        self._index: List[DocIndex] = []
        self._search_paths: List[str] = list(DOC_PATHS)
        self._initialized = False

    def initialize(self) -> None:
        """Initialize documentation browser and scan paths."""
        if self._initialized:
            return
        self._scan_all_paths()
        self._initialized = True

    def _scan_all_paths(self) -> None:
        """Scan all documentation paths."""
        for path in self._search_paths:
            self._scan_directory(path)

    def _scan_directory(self, directory: str) -> None:
        """Scan a directory for documentation packages."""
        dir_path = Path(directory)
        if not dir_path.exists():
            return

        for entry in dir_path.iterdir():
            if entry.is_dir():
                self._analyze_doc_package(entry)

    def _analyze_doc_package(self, path: Path) -> None:
        """Analyze a documentation package directory."""
        name = path.name
        files = []
        sections: Dict[str, List[DocFile]] = {}
        total_size = 0
        languages: Set[str] = set()
        has_changelog = False
        has_readme = False
        has_license = False

        for file_path in path.rglob("*"):
            if file_path.is_file():
                doc_file = self._parse_doc_file(file_path, name)
                if doc_file:
                    files.append(doc_file)
                    total_size += doc_file.size
                    languages.add(doc_file.language)

                    cat_name = doc_file.category.name.lower()
                    if cat_name not in sections:
                        sections[cat_name] = []
                    sections[cat_name].append(doc_file)

                    if doc_file.category == DocCategory.CHANGELOG:
                        has_changelog = True
                    elif doc_file.category == DocCategory.README:
                        has_readme = True
                    elif doc_file.category == DocCategory.LICENSE:
                        has_license = True

        pkg = DocPackage(
            name=name,
            path=str(path),
            files=files,
            sections=sections,
            total_size=total_size,
            languages=languages,
            has_changelog=has_changelog,
            has_readme=has_readme,
            has_license=has_license,
        )

        readme_file = path / "README"
        if readme_file.exists():
            try:
                lines = readme_file.read_text(errors="replace").splitlines()[:5]
                pkg.description = " ".join(lines).strip()[:200]
            except OSError:
                pass

        self._packages[name] = pkg
        self._add_to_index(pkg)

    def _parse_doc_file(self, path: Path, package: str) -> Optional[DocFile]:
        """Parse a documentation file."""
        try:
            stat = path.stat()
            name = path.name
            fmt = self._detect_format(name)
            cat = self._detect_category(name)
            compressed = name.endswith(".gz") or name.endswith(".bz2") or name.endswith(".xz")
            lang = self._detect_language(name, path.parent.name)

            return DocFile(
                path=str(path),
                name=name,
                format=fmt,
                category=cat,
                size=stat.st_size,
                language=lang,
                compressed=compressed,
            )
        except OSError:
            return None

    def _detect_format(self, filename: str) -> DocFormat:
        """Detect documentation format from filename."""
        if filename.endswith((".gz", ".bz2", ".xz")):
            return DocFormat.COMPRESSED
        if filename.endswith((".md", ".markdown")):
            return DocFormat.MARKDOWN
        if filename.endswith((".rst", ".rest")):
            return DocFormat.RST
        if filename.endswith((".html", ".htm")):
            return DocFormat.HTML
        if filename.endswith(".pdf"):
            return DocFormat.PDF
        if filename.endswith((".1", ".2", ".3", ".4", ".5", ".6", ".7", ".8", ".9")):
            return DocFormat.MAN
        if filename.endswith((".texi", ".texinfo")):
            return DocFormat.TEXINFO
        if filename.endswith((".xml", ".sgml")):
            return DocFormat.XML
        if filename.endswith((".txt", ".text")):
            return DocFormat.PLAIN_TEXT
        return DocFormat.UNKNOWN

    def _detect_category(self, filename: str) -> DocCategory:
        """Detect documentation category from filename."""
        name_lower = filename.lower()
        for cat_name, keywords in DOC_SECTIONS.items():
            for kw in keywords:
                if kw in name_lower:
                    try:
                        return DocCategory[cat_name.upper()]
                    except KeyError:
                        pass
        if name_lower.startswith("readme"):
            return DocCategory.README
        if "changelog" in name_lower or "change" in name_lower:
            return DocCategory.CHANGELOG
        if "license" in name_lower or "copying" in name_lower:
            return DocCategory.LICENSE
        if "author" in name_lower or "credit" in name_lower:
            return DocCategory.CREDITS
        if "bug" in name_lower:
            return DocCategory.BUGS
        if "security" in name_lower:
            return DocCategory.SECURITY
        if "config" in name_lower:
            return DocCategory.CONFIG
        return DocCategory.GENERAL

    def _detect_language(self, filename: str, parent_name: str) -> str:
        """Detect documentation language."""
        lang_codes = ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh",
                      "nl", "sv", "da", "no", "fi", "pl", "cs", "hu", "ro", "tr"]
        for code in lang_codes:
            if filename.endswith(f".{code}") or filename.endswith(f".{code}.gz"):
                return code
            if parent_name.endswith(f".{code}"):
                return code
        return "en"

    def _add_to_index(self, pkg: DocPackage) -> None:
        """Add package documentation to search index."""
        for doc_file in pkg.files:
            keywords = self._extract_keywords(doc_file)
            self._index.append(DocIndex(
                package=pkg.name,
                file=doc_file.name,
                path=doc_file.path,
                category=doc_file.category,
                format=doc_file.format,
                keywords=keywords,
            ))

    def _extract_keywords(self, doc_file: DocFile) -> List[str]:
        """Extract search keywords from a doc file."""
        keywords = []
        name = doc_file.name.lower()
        for part in name.replace(".", " ").replace("-", " ").replace("_", " ").split():
            if len(part) > 2:
                keywords.append(part)
        return keywords

    # ─── Public API ──────────────────────────────────────────────────────

    def get_package(self, name: str) -> Optional[DocPackage]:
        """Get documentation for a package."""
        return self._packages.get(name)

    def list_packages(self) -> List[DocPackage]:
        """List all documentation packages."""
        return list(self._packages.values())

    def find_packages(self, query: str) -> List[DocPackage]:
        """Find documentation packages by name."""
        results = []
        query_lower = query.lower()
        for pkg in self._packages.values():
            if query_lower in pkg.name.lower() or query_lower in pkg.description.lower():
                results.append(pkg)
        return results

    def search(self, query: str) -> List[DocSearchResult]:
        """Search documentation content."""
        results = []
        query_lower = query.lower()
        for entry in self._index:
            score = 0.0
            if query_lower in entry.package.lower():
                score += 2.0
            if query_lower in entry.file.lower():
                score += 1.5
            if any(query_lower in kw for kw in entry.keywords):
                score += 1.0
            if score > 0:
                results.append(DocSearchResult(
                    package=entry.package,
                    file_path=entry.path,
                    title=entry.file,
                    score=score,
                    category=entry.category,
                ))
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def list_by_category(self, category: DocCategory) -> List[DocFile]:
        """List all files of a specific category."""
        results = []
        for pkg in self._packages.values():
            cat_name = category.name.lower()
            if cat_name in pkg.sections:
                results.extend(pkg.sections[cat_name])
        return results

    def get_readmes(self) -> List[DocFile]:
        """Get all README files."""
        return self.list_by_category(DocCategory.README)

    def get_changelogs(self) -> List[DocFile]:
        """Get all changelog files."""
        return self.list_by_category(DocCategory.CHANGELOG)

    def get_licenses(self) -> List[DocFile]:
        """Get all license files."""
        return self.list_by_category(DocCategory.LICENSE)

    def get_statistics(self) -> Dict[str, Any]:
        """Get documentation statistics."""
        total_packages = len(self._packages)
        total_files = sum(len(p.files) for p in self._packages.values())
        total_size = sum(p.total_size for p in self._packages.values())
        by_format = {}
        for fmt in DocFormat:
            count = sum(
                1 for p in self._packages.values()
                for f in p.files if f.format == fmt
            )
            if count > 0:
                by_format[fmt.name] = count
        by_category = {}
        for cat in DocCategory:
            count = sum(
                1 for p in self._packages.values()
                for f in p.files if f.category == cat
            )
            if count > 0:
                by_category[cat.name] = count
        return {
            "total_packages": total_packages,
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "by_format": by_format,
            "by_category": by_category,
            "search_paths": len(self._search_paths),
        }

    def refresh(self) -> None:
        """Refresh documentation cache."""
        self._packages.clear()
        self._index.clear()
        self._initialized = False
        self.initialize()


# ─── Global Singleton ────────────────────────────────────────────────────────

_global_doc_browser: Optional[DocBrowser] = None


def get_global_doc_browser() -> DocBrowser:
    """Get or create the global documentation browser."""
    global _global_doc_browser
    if _global_doc_browser is None:
        _global_doc_browser = DocBrowser()
        _global_doc_browser.initialize()
    return _global_doc_browser
