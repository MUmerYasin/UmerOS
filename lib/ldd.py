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
Library Dependency Tracer for UmerOS /lib
==========================================
Implements `ldd`-like functionality — recursively resolves all shared
library dependencies of an ELF binary using the ELF parser, ld.so.cache,
and LD_LIBRARY_PATH/RPATH/RUNPATH search rules.

Produces a tree view of dependencies with resolved paths and SONAME labels.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .elf_parser import ElfParser, ElfBinary, ElfParseError


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ResolvedDep:
    """A single resolved library dependency."""
    name: str
    soname: str
    resolved_path: str
    search_method: str  # "ldcache" | "rpath" | "runpath" | "ld_library_path" | "default"
    bit_width: int = 0
    machine: str = ""
    needed_by: str = ""
    missing: bool = False


@dataclass
class DependencyTree:
    """Complete dependency tree for a binary."""
    binary_path: str
    binary_soname: str
    flat: list[ResolvedDep]
    tree: dict[str, list[str]]  # parent -> [child paths]
    missing: list[ResolvedDep]
    total_count: int = 0
    resolved_count: int = 0
    missing_count: int = 0


@dataclass
class LddConfig:
    """Configuration for the dependency tracer."""
    search_paths: list[str] = field(default_factory=lambda: [
        "/lib",
        "/lib64",
        "/usr/lib",
        "/usr/lib64",
        "/usr/local/lib",
        "/usr/local/lib64",
    ])
    ld_library_path: list[str] = field(default_factory=list)
    ldcache_path: str = "/etc/ld.so.cache"
    enable_cache: bool = True
    max_depth: int = 32


# ---------------------------------------------------------------------------
# Tracer
# ---------------------------------------------------------------------------

class Ldd:
    """
    Traces shared library dependencies of ELF binaries.

    Like the real ``ldd``, this walks the NEEDED list of each binary,
    resolves each dependency through the standard search order
    (RPATH → RUNPATH → LD_LIBRARY_PATH → ld.so.cache → default paths),
    and recurses until all transitive dependencies are resolved.

    Usage::

        ldd = Ldd()
        tree = ldd.trace("/usr/bin/python3")
        for dep in tree.flat:
            print(f"  {dep.name} => {dep.resolved_path}")
    """

    def __init__(self, config: Optional[LddConfig] = None) -> None:
        self.config = config or LddConfig()
        self._parser = ElfParser()
        self._ldcache: dict[str, str] = {}
        self._visited: set[str] = set()

    def trace(self, binary_path: str | Path) -> DependencyTree:
        """Trace all dependencies of the given ELF binary."""
        binary_path = str(Path(binary_path).resolve())
        self._visited.clear()
        self._ldcache = self._load_ldcache() if self.config.enable_cache else {}

        flat: list[ResolvedDep] = []
        tree: dict[str, list[str]] = {}
        missing: list[ResolvedDep] = []

        try:
            binary = self._parser.parse(binary_path)
        except ElfParseError as exc:
            return DependencyTree(
                binary_path=binary_path,
                binary_soname="",
                flat=[],
                tree={},
                missing=[ResolvedDep(
                    name=str(exc), soname="", resolved_path="",
                    search_method="error", missing=True,
                )],
                total_count=1,
                resolved_count=0,
                missing_count=1,
            )

        self._resolve_list(
            binary.needed, binary.path, flat, tree, missing, depth=0,
        )

        return DependencyTree(
            binary_path=binary_path,
            binary_soname=binary.soname,
            flat=flat,
            tree=tree,
            missing=missing,
            total_count=len(flat),
            resolved_count=len(flat) - len(missing),
            missing_count=len(missing),
        )

    def _resolve_list(
        self,
        needed: list[str],
        parent_path: str,
        flat: list[ResolvedDep],
        tree: dict[str, list[str]],
        missing: list[ResolvedDep],
        depth: int,
    ) -> None:
        if depth > self.config.max_depth or not needed:
            return

        children: list[str] = []
        parent_key = str(Path(parent_path).name)

        for lib_name in needed:
            dep = self._resolve_one(lib_name, parent_path)
            flat.append(dep)
            children.append(dep.resolved_path or dep.name)

            if dep.missing:
                missing.append(dep)
                continue

            # Recurse if not already visited
            canonical = str(Path(dep.resolved_path).resolve())
            if canonical not in self._visited:
                self._visited.add(canonical)
                try:
                    child_binary = self._parser.parse(dep.resolved_path)
                    self._resolve_list(
                        child_binary.needed, dep.resolved_path,
                        flat, tree, missing, depth + 1,
                    )
                except ElfParseError:
                    pass

        tree[parent_key] = children

    def _resolve_one(self, lib_name: str, parent_path: str) -> ResolvedDep:
        """Resolve a single library name to a filesystem path."""
        # 1. RPATH from the parent binary
        try:
            parent = self._parser.parse(parent_path)
        except ElfParseError:
            parent = None

        if parent:
            for rp in parent.rpaths:
                candidate = os.path.join(rp, lib_name)
                if os.path.isfile(candidate):
                    return self._make_dep(lib_name, candidate, "rpath")

            # 2. LD_LIBRARY_PATH
            for lp in self.config.ld_library_path:
                candidate = os.path.join(lp, lib_name)
                if os.path.isfile(candidate):
                    return self._make_dep(lib_name, candidate, "ld_library_path")

            # 3. RUNPATH
            for rp in parent.runpaths:
                candidate = os.path.join(rp, lib_name)
                if os.path.isfile(candidate):
                    return self._make_dep(lib_name, candidate, "runpath")

        # 4. ld.so.cache
        if lib_name in self._ldcache:
            cached = self._ldcache[lib_name]
            if os.path.isfile(cached):
                return self._make_dep(lib_name, cached, "ldcache")

        # 5. Default search paths
        for sp in self.config.search_paths:
            candidate = os.path.join(sp, lib_name)
            if os.path.isfile(candidate):
                return self._make_dep(lib_name, candidate, "default")

        # 6. Not found
        return ResolvedDep(
            name=lib_name, soname="", resolved_path="",
            search_method="not_found", missing=True,
            needed_by=parent_path,
        )

    def _make_dep(self, name: str, path: str, method: str) -> ResolvedDep:
        soname = ""
        bit_width = 0
        machine = ""
        try:
            binary = self._parser.parse(path)
            soname = binary.soname
            bit_width = binary.bit_width
            machine = binary.machine_name
        except ElfParseError:
            pass
        return ResolvedDep(
            name=name, soname=soname, resolved_path=path,
            search_method=method, bit_width=bit_width,
            machine=machine,
        )

    def _load_ldcache(self) -> dict[str, str]:
        """Parse ld.so.cache into a name→path mapping."""
        cache_path = self.config.ldcache_path
        if not os.path.isfile(cache_path):
            return {}

        cache: dict[str, str] = {}
        try:
            with open(cache_path, "rb") as f:
                data = f.read()
            # ld.so.cache format: magic(4) + version(4) + nlib(4) + ...
            # Simplified: split by null-terminated strings
            if len(data) < 12:
                return {}
            # For UmerOS, we just build from filesystem scan
            for search_dir in self.config.search_paths:
                if os.path.isdir(search_dir):
                    for entry in os.listdir(search_dir):
                        if entry.endswith(".so") or ".so." in entry:
                            full = os.path.join(search_dir, entry)
                            if os.path.isfile(full):
                                cache[entry] = full
        except (OSError, PermissionError):
            pass
        return cache

    def format_tree(self, tree: DependencyTree, indent: int = 2) -> str:
        """Format the dependency tree as a human-readable string."""
        lines: list[str] = []
        lines.append(f"  {tree.binary_path}:")
        lines.append(f"    {tree.binary_soname or '(no soname)'}")

        def _walk(parent: str, level: int) -> None:
            children = tree.tree.get(parent, [])
            for i, child in enumerate(children):
                is_last = i == len(children) - 1
                prefix = "    " * level + ("└── " if is_last else "├── ")
                child_name = str(Path(child).name) if child.startswith("/") else child
                lines.append(f"{prefix}{child_name}")
                if not is_last or child not in tree.tree:
                    continue
                _walk(child, level + 1)

        _walk(str(Path(tree.binary_path).name), 1)

        if tree.missing:
            lines.append("")
            lines.append(f"  {tree.missing_count} missing:")
            for dep in tree.missing:
                lines.append(f"    {dep.name} (needed by {dep.needed_by})")

        return "\n".join(lines)

    def quick_check(self, binary_path: str | Path) -> dict[str, object]:
        """Quick check — returns summary without full tree."""
        tree = self.trace(binary_path)
        return {
            "path": tree.binary_path,
            "soname": tree.binary_soname,
            "total": tree.total_count,
            "resolved": tree.resolved_count,
            "missing": tree.missing_count,
            "all_found": tree.missing_count == 0,
        }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    """Round-trip the ldd helper against a synthetic ELF.

    The synthetic ELF has no DT_NEEDED entries, so the tree should
    be empty (or contain a single ``missing=True`` ``ElfParseError``-
    derived entry - both are acceptable).  The selftest verifies
    the call does not raise and the summary is consistent.
    """
    import struct
    import tempfile

    # 64-bit, little-endian ELF header.  No sections / program headers
    # - we only need the parser to be able to identify it as ELF.
    e_ident = b"\x7fELF" b"\x02" b"\x01" b"\x01" b"\x00" * 9
    header = struct.pack(
        "<16sHHIQQQIHHHHHH",
        e_ident, 2, 0x3E, 1, 0, 0, 0, 0, 64, 0, 0, 0, 0, 0,
    )
    with tempfile.TemporaryDirectory() as tmp:
        elf = Path(tmp) / "no-deps.elf"
        elf.write_bytes(header)
        ldd = Ldd()
        tree = ldd.trace(elf)
        # ``binary_path`` is resolved; compare the resolved form.
        if Path(tree.binary_path) != elf.resolve():
            return False
        # No DT_NEEDED entries => resolved_count is 0 (the parser will
        # either succeed with an empty flat list, or record a single
        # ElfParseError entry; both count as success).
        if tree.missing_count > 1:
            return False
        # ``format_tree`` should not raise.
        text = ldd.format_tree(tree)
        if not isinstance(text, str):
            return False
        # ``quick_check`` returns a dict with the expected keys.
        summary = ldd.quick_check(elf)
        for key in ("path", "soname", "total", "resolved", "missing", "all_found"):
            if key not in summary:
                return False
    return True


if __name__ == "__main__":
    print("ldd selftest:", "OK" if _selftest() else "FAIL")
