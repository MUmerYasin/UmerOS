"""
UmerOS Info Pages Manager (/usr/share/info)
============================================
GNU Info documentation system integration.

Reference: Linux Filesystem Hierarchy - /usr/share/info
  /usr/share/info contains GNU Info documentation files.
  These are part of the GNU documentation system, providing
  hypertext navigation through documentation via info readers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


# ─── Constants ───────────────────────────────────────────────────────────────

INFO_PATHS = [
    "/usr/share/info",
    "/usr/local/share/info",
]

INFO_EXTENSIONS = {".info", ".info.gz", ".info.bz2", ".info.xz", ".texinfo"}

# Texinfo node markers
NODE_MARKER = "* "
NODE_START = "@node"
MENU_START = "@menu"
MENU_END = "@end menu"
CHAPTER_MARKERS = ["@chapter", "@unnumbered", "@appendix"]
SECTION_MARKERS = ["@section", "@unnumberedsec", "@appendixsec"]


# ─── Enums ───────────────────────────────────────────────────────────────────

class InfoFormat(IntEnum):
    """Info file formats."""
    PLAIN_TEXT = 1
    TEXINFO = 2
    COMPRESSED_GZ = 3
    COMPRESSED_BZ2 = 4
    COMPRESSED_XZ = 5
    UNKNOWN = 10


class InfoNodeType(IntEnum):
    """Types of info nodes."""
    TOP = 1
    CHAPTER = 2
    SECTION = 3
    SUBSECTION = 4
    ENTRY = 5
    CONCEPT = 6
    FUNCTION = 7
    VARIABLE = 8
    KEY = 9
    COMMAND = 10
    PROGRAM = 11


class InfoRelation(IntEnum):
    """Node relationship types."""
    NEXT = 1
    PREVIOUS = 2
    UP = 3
    FIRST = 4
    LAST = 5


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class InfoNode:
    """Represents a node in an info document."""
    name: str
    file: str
    node_type: InfoNodeType = InfoNodeType.ENTRY
    next_node: str = ""
    previous_node: str = ""
    up_node: str = ""
    content: str = ""
    line_count: int = 0
    menu_items: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "file": self.file,
            "type": self.node_type.name,
            "next": self.next_node,
            "previous": self.previous_node,
            "up": self.up_node,
            "line_count": self.line_count,
            "menu_items": self.menu_items,
        }


@dataclass
class InfoFile:
    """Represents an info file."""
    path: str
    name: str
    format: InfoFormat = InfoFormat.UNKNOWN
    title: str = ""
    language: str = "en"
    size: int = 0
    node_count: int = 0
    top_node: Optional[InfoNode] = None
    nodes: List[InfoNode] = field(default_factory=list)
    encoding: str = "utf-8"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "format": self.format.name,
            "title": self.title,
            "language": self.language,
            "size": self.size,
            "node_count": self.node_count,
            "has_top_node": self.top_node is not None,
        }


@dataclass
class InfoEntry:
    """An info documentation entry (menu item)."""
    name: str
    description: str = ""
    file: str = ""
    node: str = ""
    category: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "file": self.file,
            "node": self.node,
            "category": self.category,
        }


@dataclass
class InfoSearchResult:
    """Search result from info pages."""
    file: str
    node: str
    title: str
    snippet: str = ""
    score: float = 0.0
    line_number: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "node": self.node,
            "title": self.title,
            "snippet": self.snippet,
            "score": self.score,
            "line_number": self.line_number,
        }


@dataclass
class InfoTOC:
    """Table of contents for an info file."""
    title: str
    nodes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "nodes": self.nodes,
        }


# ─── Info Pages Manager ─────────────────────────────────────────────────────

class InfoPagesManager:
    """
    Manages /usr/share/info - GNU Info documentation.

    Responsibilities:
        - Discover and parse Texinfo/info files
        - Parse node structure from info files
        - Navigate between info nodes
        - Provide search across info content
        - Handle compressed info files
        - Build table of contents for documents
        - Support cross-references between info files
    """

    def __init__(self) -> None:
        self._files: Dict[str, InfoFile] = {}
        self._nodes: Dict[str, List[InfoNode]] = {}
        self._search_paths: List[str] = list(INFO_PATHS)
        self._initialized = False

    def initialize(self) -> None:
        """Initialize info pages manager and scan paths."""
        if self._initialized:
            return
        self._scan_all_paths()
        self._initialized = True

    def _scan_all_paths(self) -> None:
        """Scan all info paths."""
        for path in self._search_paths:
            self._scan_directory(path)

    def _scan_directory(self, directory: str) -> None:
        """Scan a directory for info files."""
        dir_path = Path(directory)
        if not dir_path.exists():
            return

        for entry in dir_path.iterdir():
            if entry.is_file() and self._is_info_file(entry.name):
                self._parse_info_file(entry)

    def _is_info_file(self, filename: str) -> bool:
        """Check if file is an info file."""
        if filename in ("dir", "DIR"):
            return False
        for ext in INFO_EXTENSIONS:
            if filename.endswith(ext):
                return True
        return False

    def _parse_info_file(self, path: Path) -> None:
        """Parse an info file."""
        try:
            stat = path.stat()
            name = path.name
            fmt = self._detect_format(name)
            title = self._extract_title(path, fmt)
            nodes = self._extract_nodes(path, fmt)
            top_node = next((n for n in nodes if n.node_type == InfoNodeType.TOP), None)

            info_file = InfoFile(
                path=str(path),
                name=name,
                format=fmt,
                title=title,
                size=stat.st_size,
                node_count=len(nodes),
                top_node=top_node,
                nodes=nodes,
            )

            self._files[name] = info_file
            self._nodes[name] = nodes
        except OSError:
            pass

    def _detect_format(self, filename: str) -> InfoFormat:
        """Detect info file format."""
        if filename.endswith(".info.gz"):
            return InfoFormat.COMPRESSED_GZ
        if filename.endswith(".info.bz2"):
            return InfoFormat.COMPRESSED_BZ2
        if filename.endswith(".info.xz"):
            return InfoFormat.COMPRESSED_XZ
        if filename.endswith(".texinfo") or filename.endswith(".texi"):
            return InfoFormat.TEXINFO
        if filename.endswith(".info"):
            return InfoFormat.PLAIN_TEXT
        return InfoFormat.UNKNOWN

    def _extract_title(self, path: Path, fmt: InfoFormat) -> str:
        """Extract document title from info file."""
        try:
            content = path.read_text(errors="replace")
            match = re.search(r"^\\input\s+texinfo\s*\n.*?@title\s+(.+)", content, re.MULTILINE)
            if match:
                return match.group(1).strip()
            for line in content.splitlines()[:20]:
                if line.startswith("* "):
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        return parts[1].strip()
        except OSError:
            pass
        return path.stem

    def _extract_nodes(self, path: Path, fmt: InfoFormat) -> List[InfoNode]:
        """Extract nodes from info file."""
        nodes = []
        try:
            content = path.read_text(errors="replace")
            lines = content.splitlines()

            current_node = None
            in_menu = False
            current_content = []

            for i, line in enumerate(lines):
                if line.startswith("@node"):
                    if current_node:
                        current_node.content = "\n".join(current_content).strip()
                        current_node.line_count = len(current_content)
                    parts = line[5:].split(",", 3)
                    node_name = parts[0].strip() if parts else ""
                    next_node = parts[1].strip() if len(parts) > 1 else ""
                    prev_node = parts[2].strip() if len(parts) > 2 else ""
                    up_node = parts[3].strip() if len(parts) > 3 else ""

                    node_type = self._classify_node(node_name)
                    current_node = InfoNode(
                        name=node_name,
                        file=path.name,
                        node_type=node_type,
                        next_node=next_node,
                        previous_node=prev_node,
                        up_node=up_node,
                    )
                    nodes.append(current_node)
                    current_content = []
                    in_menu = False
                elif line.startswith(MENU_START):
                    in_menu = True
                elif line.startswith(MENU_END):
                    in_menu = False
                elif in_menu and line.startswith("* "):
                    if current_node:
                        item = line[2:].split("::", 1)[0].strip()
                        current_node.menu_items.append(item)
                elif current_node:
                    current_content.append(line)

            if current_node:
                current_node.content = "\n".join(current_content).strip()
                current_node.line_count = len(current_content)
        except OSError:
            pass
        return nodes

    def _classify_node(self, name: str) -> InfoNodeType:
        """Classify a node name into a type."""
        name_lower = name.lower()
        if name_lower in ("top", "introduction", "overview"):
            return InfoNodeType.TOP
        if any(kw in name_lower for kw in ["function", "func", "subroutine"]):
            return InfoNodeType.FUNCTION
        if any(kw in name_lower for kw in ["variable", "var", "option"]):
            return InfoNodeType.VARIABLE
        if any(kw in name_lower for kw in ["key", "keystroke", "binding"]):
            return InfoNodeType.KEY
        if any(kw in name_lower for kw in ["command", "cmd", "program"]):
            return InfoNodeType.COMMAND
        if any(kw in name_lower for kw in ["concept", "glossary", "index"]):
            return InfoNodeType.CONCEPT
        return InfoNodeType.ENTRY

    # ─── Public API ──────────────────────────────────────────────────────

    def get_file(self, name: str) -> Optional[InfoFile]:
        """Get info file by name."""
        return self._files.get(name)

    def list_files(self) -> List[InfoFile]:
        """List all info files."""
        return list(self._files.values())

    def find_files(self, query: str) -> List[InfoFile]:
        """Find info files matching query."""
        results = []
        query_lower = query.lower()
        for f in self._files.values():
            if (query_lower in f.name.lower() or query_lower in f.title.lower()):
                results.append(f)
        return results

    def get_toc(self, file_name: str) -> Optional[InfoTOC]:
        """Get table of contents for an info file."""
        info_file = self._files.get(file_name)
        if not info_file:
            return None
        toc_nodes = []
        for node in info_file.nodes:
            toc_nodes.append({
                "name": node.name,
                "type": node.node_type.name,
                "line_count": node.line_count,
            })
        return InfoTOC(title=info_file.title, nodes=toc_nodes)

    def get_node(self, file_name: str, node_name: str) -> Optional[InfoNode]:
        """Get a specific node from an info file."""
        nodes = self._nodes.get(file_name, [])
        for node in nodes:
            if node.name.lower() == node_name.lower():
                return node
        return None

    def navigate(self, file_name: str, node_name: str, direction: InfoRelation) -> Optional[InfoNode]:
        """Navigate to a related node."""
        node = self.get_node(file_name, node_name)
        if not node:
            return None
        target = ""
        if direction == InfoRelation.NEXT:
            target = node.next_node
        elif direction == InfoRelation.PREVIOUS:
            target = node.previous_node
        elif direction == InfoRelation.UP:
            target = node.up_node
        if target:
            return self.get_node(file_name, target)
        return None

    def search(self, query: str) -> List[InfoSearchResult]:
        """Search across all info files."""
        results = []
        query_lower = query.lower()
        for file_name, nodes in self._nodes.items():
            for node in nodes:
                score = 0.0
                if query_lower in node.name.lower():
                    score += 2.0
                if query_lower in node.content.lower():
                    score += 1.0
                    content_lower = node.content.lower()
                    idx = content_lower.find(query_lower)
                    start = max(0, idx - 40)
                    end = min(len(node.content), idx + len(query) + 40)
                    snippet = node.content[start:end].strip()
                else:
                    snippet = node.content[:80].strip()
                if score > 0:
                    results.append(InfoSearchResult(
                        file=file_name,
                        node=node.name,
                        title=node.name,
                        snippet=snippet,
                        score=score,
                    ))
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def list_all_nodes(self, file_name: str) -> List[InfoNode]:
        """List all nodes in an info file."""
        return self._nodes.get(file_name, [])

    def get_statistics(self) -> Dict[str, Any]:
        """Get info pages statistics."""
        total_files = len(self._files)
        total_nodes = sum(len(nodes) for nodes in self._nodes.values())
        total_size = sum(f.size for f in self._files.values())
        by_format = {}
        for fmt in InfoFormat:
            count = sum(1 for f in self._files.values() if f.format == fmt)
            if count > 0:
                by_format[fmt.name] = count
        return {
            "total_files": total_files,
            "total_nodes": total_nodes,
            "total_size_bytes": total_size,
            "total_size_kb": total_size / 1024,
            "by_format": by_format,
            "search_paths": len(self._search_paths),
        }

    def refresh(self) -> None:
        """Refresh info pages cache."""
        self._files.clear()
        self._nodes.clear()
        self._initialized = False
        self.initialize()


# ─── Global Singleton ────────────────────────────────────────────────────────

_global_info_manager: Optional[InfoPagesManager] = None


def get_global_info_manager() -> InfoPagesManager:
    """Get or create the global info pages manager."""
    global _global_info_manager
    if _global_info_manager is None:
        _global_info_manager = InfoPagesManager()
        _global_info_manager.initialize()
    return _global_info_manager
