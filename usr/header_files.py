"""
UmerOS Header Files Manager
============================
C/C++ header file parsing and management under /usr/include.

The /usr/include hierarchy contains C and C++ header files used by
the system and locally installed software:
  - /usr/include           : Standard C headers
  - /usr/include/sys       : System-specific headers
  - /usr/include/linux     : Kernel headers
  - /usr/include/glib-*    : GLib headers
  - /usr/include/X11       : X11 headers
  - /usr/local/include     : Locally installed headers

This module provides parsing, indexing, and dependency tracking
for header files including include guards, macro definitions,
type declarations, and function prototypes.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import (
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)


# ============================================================================
# Constants
# ============================================================================

INCLUDE_PATHS: List[str] = [
    "/usr/include",
    "/usr/local/include",
    "/usr/src/linux-headers/include",
]

HEADER_EXTENSIONS: Set[str] = {".h", ".hpp", ".hxx", ".hh", ".h++"}


# ============================================================================
# Enums
# ============================================================================

class HeaderType(IntEnum):
    """Types of header declarations."""
    INCLUDE_GUARD = 0
    MACRO = 1
    TYPEDEF = 2
    STRUCT = 3
    UNION = 4
    ENUM = 5
    FUNCTION = 6
    VARIABLE = 7
    TEMPLATE = 8
    CLASS = 9
    NAMESPACE = 10
    USING = 11
    EXTERN = 12
    DEFINE = 13
    UNDEF = 14
    IFDEF = 15
    IFndef = 16


class HeaderCategory(IntEnum):
    """Categories of header files."""
    STANDARD_C = 0
    POSIX = 1
    SYSTEM = 2
    LINUX_KERNEL = 3
    GLIB = 4
    X11 = 5
    LOCAL = 6
    THIRD_PARTY = 7
    UNKNOWN = 8


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class IncludeGuard:
    """An include guard (ifndef/define pattern)."""
    guard_macro: str = ""
    ifndef_line: int = 0
    define_line: int = 0
    endif_line: int = 0

    def is_complete(self) -> bool:
        """Check if guard is complete."""
        return bool(self.guard_macro) and self.endif_line > 0


@dataclass
class MacroDefinition:
    """A preprocessor macro definition."""
    name: str = ""
    value: str = ""
    parameters: List[str] = field(default_factory=list)
    line_number: int = 0
    is_function_like: bool = False

    def to_string(self) -> str:
        """Reconstruct the macro definition."""
        if self.is_function_like and self.parameters:
            params = ", ".join(self.parameters)
            return f"#define {self.name}({params}) {self.value}"
        return f"#define {self.name} {self.value}"


@dataclass
class TypeDefinition:
    """A typedef or type alias."""
    original_type: str = ""
    alias_name: str = ""
    line_number: int = 0
    is_const: bool = False
    is_pointer: bool = False
    is_struct: bool = False
    is_enum: bool = False


@dataclass
class StructDefinition:
    """A struct or class definition."""
    name: str = ""
    kind: str = "struct"
    fields: List[Tuple[str, str]] = field(default_factory=list)
    line_number: int = 0
    is_forward_declaration: bool = False
    base_classes: List[str] = field(default_factory=list)

    def field_count(self) -> int:
        """Get the number of fields."""
        return len(self.fields)


@dataclass
class FunctionPrototype:
    """A function prototype declaration."""
    return_type: str = ""
    name: str = ""
    parameters: List[Tuple[str, str]] = field(default_factory=list)
    line_number: int = 0
    is_inline: bool = False
    is_static: bool = False
    is_extern: bool = False
    is_variadic: bool = False

    def signature(self) -> str:
        """Get the full function signature."""
        params = ", ".join(f"{t} {n}" for t, n in self.parameters)
        qualifiers = []
        if self.is_inline:
            qualifiers.append("inline")
        if self.is_static:
            qualifiers.append("static")
        if self.is_extern:
            qualifiers.append("extern")
        prefix = " ".join(qualifiers) + " " if qualifiers else ""
        return f"{prefix}{self.return_type} {self.name}({params})"


@dataclass
class HeaderInclude:
    """An #include directive."""
    included_file: str = ""
    line_number: int = 0
    is_system_include: bool = True
    is_relative: bool = False


@dataclass
class HeaderFile:
    """A parsed header file."""
    name: str = ""
    path: str = ""
    category: HeaderCategory = HeaderCategory.UNKNOWN
    include_guard: Optional[IncludeGuard] = None
    macros: List[MacroDefinition] = field(default_factory=list)
    typedefs: List[TypeDefinition] = field(default_factory=list)
    structs: List[StructDefinition] = field(default_factory=list)
    functions: List[FunctionPrototype] = field(default_factory=list)
    includes: List[HeaderInclude] = field(default_factory=list)
    raw_content: str = ""
    size_bytes: int = 0
    modified_at: float = 0.0

    def get_public_macros(self) -> List[MacroDefinition]:
        """Get macros that are not include guards."""
        return [
            m for m in self.macros
            if self.include_guard is None
            or m.name != self.include_guard.guard_macro
        ]

    def get_includes(self, system_only: bool = False) -> List[HeaderInclude]:
        """Get include directives."""
        if system_only:
            return [inc for inc in self.includes if inc.is_system_include]
        return list(self.includes)

    def get_exported_types(self) -> List[str]:
        """Get names of all exported types."""
        types: List[str] = []
        for td in self.typedefs:
            types.append(td.alias_name)
        for sd in self.structs:
            if not sd.is_forward_declaration:
                types.append(f"{sd.kind} {sd.name}")
        return types

    def get_exported_functions(self) -> List[str]:
        """Get names of all exported functions."""
        return [f.name for f in self.functions]

    def dependency_count(self) -> int:
        """Count direct dependencies (included files)."""
        return len(self.includes)


# ============================================================================
# Header File Parser
# ============================================================================

class HeaderFileParser:
    """Parser for C/C++ header files."""

    RE_INCLUDE_GUARD_IFNDEF = re.compile(
        r"^\s*#\s*ifndef\s+(\w+)\s*$"
    )
    RE_INCLUDE_GUARD_DEFINE = re.compile(
        r"^\s*#\s*define\s+(\w+)\s*$"
    )
    RE_INCLUDE_GUARD_ENDIF = re.compile(
        r"^\s*#\s*endif\s*$"
    )
    RE_INCLUDE_SYSTEM = re.compile(
        r"^\s*#\s*include\s*<(.+?)>"
    )
    RE_INCLUDE_LOCAL = re.compile(
        r'^\s*#\s*include\s*"(.+?)"'
    )
    RE_MACRO_DEFINE = re.compile(
        r"^\s*#\s*define\s+(\w+)(?:\(([^)]*)\))?\s*(.*)"
    )
    RE_TYPEDEF = re.compile(
        r"^\s*typedef\s+(.+?)\s+(\w+)\s*;"
    )
    RE_STRUCT = re.compile(
        r"^\s*(struct|class|union)\s+(\w+)\s*(?:\:\s*(.+))?\s*\{"
    )
    RE_STRUCT_DECL = re.compile(
        r"^\s*(struct|class|union)\s+(\w+)\s*;"
    )
    RE_FUNCTION = re.compile(
        r"^\s*(?:static\s+|extern\s+|inline\s+)*"
        r"(\w[\w\s\*]*?)\s+"
        r"(\w+)\s*\(([^)]*)\)\s*;"
    )
    RE_EXTERN_VAR = re.compile(
        r"^\s*extern\s+(\w[\w\s\*]*?)\s+(\w+)\s*;"
    )

    def parse(self, filepath: str) -> Optional[HeaderFile]:
        """Parse a header file."""
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except (OSError, IOError):
            return None

        header = HeaderFile(
            name=os.path.basename(filepath),
            path=filepath,
            raw_content=content,
        )

        try:
            stat = os.stat(filepath)
            header.size_bytes = stat.st_size
            header.modified_at = stat.st_mtime
        except OSError:
            pass

        lines = content.split("\n")
        guard_ifndef: Optional[str] = None
        guard_define: Optional[str] = None
        guard_ifndef_line = 0
        guard_define_line = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            m = self.RE_INCLUDE_GUARD_IFNDEF.match(stripped)
            if m and guard_ifndef is None:
                guard_ifndef = m.group(1)
                guard_ifndef_line = i
                continue

            m = self.RE_INCLUDE_GUARD_DEFINE.match(stripped)
            if m and guard_ifndef and guard_define is None:
                guard_define = m.group(1)
                guard_define_line = i
                continue

            m = self.RE_INCLUDE_GUARD_ENDIF.match(stripped)
            if m and guard_ifndef and guard_define:
                header.include_guard = IncludeGuard(
                    guard_macro=guard_define,
                    ifndef_line=guard_ifndef_line,
                    define_line=guard_define_line,
                    endif_line=i,
                )
                guard_ifndef = None
                guard_define = None
                continue

            m = self.RE_INCLUDE_SYSTEM.match(stripped)
            if m:
                header.includes.append(HeaderInclude(
                    included_file=m.group(1),
                    line_number=i,
                    is_system_include=True,
                ))
                continue

            m = self.RE_INCLUDE_LOCAL.match(stripped)
            if m:
                header.includes.append(HeaderInclude(
                    included_file=m.group(1),
                    line_number=i,
                    is_system_include=False,
                    is_relative=True,
                ))
                continue

            m = self.RE_MACRO_DEFINE.match(stripped)
            if m:
                name = m.group(1)
                params_str = m.group(2)
                value = m.group(3).strip()
                params = [
                    p.strip() for p in params_str.split(",")
                ] if params_str else []
                header.macros.append(MacroDefinition(
                    name=name,
                    value=value,
                    parameters=params,
                    line_number=i,
                    is_function_like=bool(params_str),
                ))
                continue

            m = self.RE_TYPEDEF.match(stripped)
            if m:
                header.typedefs.append(TypeDefinition(
                    original_type=m.group(1).strip(),
                    alias_name=m.group(2),
                    line_number=i,
                ))
                continue

            m = self.RE_STRUCT.match(stripped)
            if m:
                kind = m.group(1)
                name = m.group(2)
                bases = [
                    b.strip() for b in m.group(3).split(",")
                ] if m.group(3) else []
                header.structs.append(StructDefinition(
                    name=name,
                    kind=kind,
                    line_number=i,
                    base_classes=bases,
                ))
                continue

            m = self.RE_STRUCT_DECL.match(stripped)
            if m:
                header.structs.append(StructDefinition(
                    name=m.group(2),
                    kind=m.group(1),
                    line_number=i,
                    is_forward_declaration=True,
                ))
                continue

            m = self.RE_FUNCTION.match(stripped)
            if m:
                ret_type = m.group(1).strip()
                func_name = m.group(2)
                params_raw = m.group(3).strip()
                params: List[Tuple[str, str]] = []
                if params_raw and params_raw != "void":
                    for param in params_raw.split(","):
                        param = param.strip()
                        parts = param.rsplit(None, 1)
                        if len(parts) == 2:
                            params.append((parts[0], parts[1]))
                        else:
                            params.append(("", param))
                is_inline = "inline" in ret_type
                is_static = "static" in ret_type
                is_extern = "extern" in ret_type
                clean_ret = ret_type.replace("inline", "").replace(
                    "static", ""
                ).replace("extern", "").strip()
                header.functions.append(FunctionPrototype(
                    return_type=clean_ret,
                    name=func_name,
                    parameters=params,
                    line_number=i,
                    is_inline=is_inline,
                    is_static=is_static,
                    is_extern=is_extern,
                ))
                continue

            m = self.RE_EXTERN_VAR.match(stripped)
            if m:
                header.typedefs.append(TypeDefinition(
                    original_type=m.group(1).strip(),
                    alias_name=m.group(2),
                    line_number=i,
                ))

        header.category = self._detect_category(filepath)
        return header

    def _detect_category(self, filepath: str) -> HeaderCategory:
        """Detect header file category from path."""
        path_lower = filepath.lower()
        if "/usr/include/sys" in path_lower:
            return HeaderCategory.SYSTEM
        if "/usr/include/linux" in path_lower:
            return HeaderCategory.LINUX_KERNEL
        if "/usr/include/x11" in path_lower or "/usr/include/xorg" in path_lower:
            return HeaderCategory.X11
        if "/usr/include/glib" in path_lower:
            return HeaderCategory.GLIB
        if "/usr/local/include" in path_lower:
            return HeaderCategory.LOCAL
        if "/usr/include" in path_lower:
            return HeaderCategory.STANDARD_C
        return HeaderCategory.UNKNOWN

    def parse_content(self, content: str) -> Optional[HeaderFile]:
        """Parse header content from a string."""
        header = HeaderFile(raw_content=content)
        # Simplified parsing for inline content
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            m = self.RE_MACRO_DEFINE.match(stripped)
            if m:
                header.macros.append(MacroDefinition(
                    name=m.group(1),
                    value=m.group(3).strip() if m.group(3) else "",
                    line_number=i,
                ))
        return header


# ============================================================================
# Header Files Manager
# ============================================================================

class HeaderFilesManager:
    """
    Manages C/C++ header files under /usr/include.

    Provides indexing, search, and dependency analysis for header files.
    """

    def __init__(self) -> None:
        self._include_paths: List[str] = list(INCLUDE_PATHS)
        self._headers: Dict[str, HeaderFile] = {}
        self._category_index: Dict[HeaderCategory, List[str]] = {}
        self._parser = HeaderFileParser()

    # -- Path Management --

    def add_include_path(self, path: str) -> None:
        """Add a header search path."""
        if path not in self._include_paths:
            self._include_paths.append(path)

    def get_include_paths(self) -> List[str]:
        """Get all configured include paths."""
        return list(self._include_paths)

    # -- Scanning --

    def scan_headers(self) -> int:
        """Scan include directories for header files."""
        count = 0
        for include_path in self._include_paths:
            if not os.path.isdir(include_path):
                continue
            count += self._scan_directory(include_path)
        return count

    def _scan_directory(self, dirpath: str) -> int:
        """Recursively scan a directory for header files."""
        count = 0
        try:
            for entry in os.scandir(dirpath):
                if entry.is_file() and self._is_header_file(entry.name):
                    header = self._parser.parse(entry.path)
                    if header:
                        self._headers[entry.path] = header
                        self._category_index.setdefault(
                            header.category, []
                        ).append(entry.path)
                        count += 1
                elif entry.is_dir():
                    count += self._scan_directory(entry.path)
        except (OSError, PermissionError):
            pass
        return count

    def _is_header_file(self, filename: str) -> bool:
        """Check if a filename is a header file."""
        _, ext = os.path.splitext(filename)
        return ext in HEADER_EXTENSIONS

    # -- Header Access --

    def get_header(self, path: str) -> Optional[HeaderFile]:
        """Get a header file by path."""
        return self._headers.get(path)

    def find_header(self, name: str) -> List[HeaderFile]:
        """Find header files by name."""
        results: List[HeaderFile] = []
        for header in self._headers.values():
            if header.name == name:
                results.append(header)
        return results

    def list_headers(self, category: Optional[HeaderCategory] = None) -> List[HeaderFile]:
        """List all header files, optionally filtered by category."""
        if category is None:
            return list(self._headers.values())
        paths = self._category_index.get(category, [])
        return [self._headers[p] for p in paths if p in self._headers]

    # -- Search --

    def search_by_guard(self, guard_macro: str) -> List[HeaderFile]:
        """Find headers by include guard macro."""
        results: List[HeaderFile] = []
        for header in self._headers.values():
            if header.include_guard and header.include_guard.guard_macro == guard_macro:
                results.append(header)
        return results

    def search_by_macro(self, macro_name: str) -> List[HeaderFile]:
        """Find headers that define a specific macro."""
        results: List[HeaderFile] = []
        for header in self._headers.values():
            for macro in header.macros:
                if macro.name == macro_name:
                    results.append(header)
                    break
        return results

    def search_by_type(self, type_name: str) -> List[HeaderFile]:
        """Find headers that define a specific type."""
        results: List[HeaderFile] = []
        for header in self._headers.values():
            for td in header.typedefs:
                if td.alias_name == type_name:
                    results.append(header)
                    break
            for sd in header.structs:
                if sd.name == type_name:
                    results.append(header)
                    break
        return results

    def search_by_function(self, func_name: str) -> List[HeaderFile]:
        """Find headers that declare a specific function."""
        results: List[HeaderFile] = []
        for header in self._headers.values():
            for func in header.functions:
                if func.name == func_name:
                    results.append(header)
                    break
        return results

    def search_text(self, query: str) -> List[HeaderFile]:
        """Search header files by text content."""
        query_lower = query.lower()
        results: List[HeaderFile] = []
        for header in self._headers.values():
            if query_lower in header.raw_content.lower():
                results.append(header)
        return results

    # -- Dependency Analysis --

    def get_dependencies(self, filepath: str) -> List[str]:
        """Get direct dependencies of a header file."""
        header = self._headers.get(filepath)
        if header is None:
            return []
        return [inc.included_file for inc in header.includes]

    def resolve_dependency_path(
        self, include_name: str, source_dir: str = ""
    ) -> Optional[str]:
        """Resolve an include name to a file path."""
        if include_name.startswith("/"):
            if os.path.isfile(include_name):
                return include_name
        if source_dir:
            rel_path = os.path.join(source_dir, include_name)
            if os.path.isfile(rel_path):
                return rel_path
        for include_path in self._include_paths:
            full_path = os.path.join(include_path, include_name)
            if os.path.isfile(full_path):
                return full_path
        return None

    def get_reverse_dependencies(self, filepath: str) -> List[str]:
        """Find headers that include the given file."""
        header = self._headers.get(filepath)
        if header is None:
            return []
        name = header.name
        results: List[str] = []
        for hpath, h in self._headers.items():
            for inc in h.includes:
                if inc.included_file == name or inc.included_file == filepath:
                    results.append(hpath)
                    break
        return results

    # -- Utility --

    def header_count(self) -> int:
        """Get total number of indexed headers."""
        return len(self._headers)

    def get_statistics(self) -> Dict[str, int]:
        """Get statistics about indexed headers."""
        stats: Dict[str, int] = {
            "total_headers": self.header_count(),
        }
        for cat in HeaderCategory:
            stats[f"category_{cat.name}"] = len(
                self._category_index.get(cat, [])
            )
        return stats

    def clear(self) -> None:
        """Clear all indexed data."""
        self._headers.clear()
        self._category_index.clear()


# ============================================================================
# Global Singleton
# ============================================================================

_global_header_files: Optional[HeaderFilesManager] = None


def get_global_header_files() -> HeaderFilesManager:
    """Get or create the global HeaderFilesManager instance."""
    global _global_header_files
    if _global_header_files is None:
        _global_header_files = HeaderFilesManager()
    return _global_header_files
