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

#!/usr/bin/env python3
"""
Umer OS Package Repository

Simulated local package catalog. In production this would fetch from
a remote repository server; for now it provides a built-in catalog
of available packages with version metadata and dependency info.

Equivalent to /etc/apt/sources.list + package index in Debian.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging

log = logging.getLogger("UmerOS.PackageRepository")


class PackageInfo:
    """Metadata for a single package."""
    __slots__ = ('name', 'version', 'description', 'size_kb', 'dependencies')

    def __init__(self, name, version, description, size_kb=0, dependencies=None):
        self.name = name
        self.version = version
        self.description = description
        self.size_kb = size_kb
        self.dependencies = dependencies or []

    def __repr__(self):
        return f"{self.name} ({self.version})"


class PackageRepository:
    """Simulated package repository with a built-in catalog."""

    def __init__(self):
        self._catalog = self._build_catalog()
        log.info(
            "Package repository loaded (%d packages available).",
            len(self._catalog),
        )

    def _build_catalog(self) -> dict:
        pkgs = [
            PackageInfo("umer-core", "2.0.0", "Core OS libraries and utilities", 2048),
            PackageInfo("umer-quantum", "1.2.0", "Quantum simulation toolkit", 4096, ["umer-core"]),
            PackageInfo("umer-ai", "1.0.0", "AI assistant and resource predictor", 8192, ["umer-core"]),
            PackageInfo("umer-crypto", "1.1.0", "Post-quantum cryptography engine", 1024, ["umer-core"]),
            PackageInfo("umer-net", "1.0.0", "Networking stack (TCP, DNS, HTTP, VPN)", 1536, ["umer-core"]),
            PackageInfo("umer-ui", "1.0.0", "Fluidic Shell and theme engine", 512, ["umer-core"]),
            PackageInfo("umer-compat", "1.0.0", "Legacy app compatibility containers", 3072, ["umer-core", "umer-crypto"]),
            PackageInfo("umer-chat", "1.0.0", "AI Chat App built with Umer SDK", 512, ["umer-core", "umer-ai"]),
            PackageInfo("python-stdlib", "3.12.0", "Python standard library", 16384),
            PackageInfo("numpy", "1.26.4", "Numerical computing library", 12288),
            PackageInfo("qiskit", "1.1.0", "IBM Quantum SDK", 20480, ["numpy"]),
            PackageInfo("vim", "9.1.0", "Terminal text editor", 4096),
            PackageInfo("htop", "3.3.0", "Interactive process viewer", 256),
            PackageInfo("curl", "8.7.0", "URL transfer tool", 512, ["umer-net"]),
            PackageInfo("git", "2.45.0", "Distributed version control", 8192),
            PackageInfo("gcc", "14.1.0", "GNU C/C++ compiler", 32768),
        ]
        return {p.name: p for p in pkgs}

    def search(self, query: str) -> list:
        query_lower = query.lower()
        return [p for p in self._catalog.values()
                if query_lower in p.name.lower() or query_lower in p.description.lower()]

    def get(self, name: str):
        return self._catalog.get(name)

    def list_all(self) -> list:
        return list(self._catalog.values())


# ── Selftest ──────────────────────────────────────────────────────────────────────────

def _selftest() -> bool:
    """Run basic self-tests for the package catalog.

    Exercises the catalog surface end-to-end: build, search (by name
    and by description), get (hit and miss), list_all, and repr.
    Returns True when every check passes; raises AssertionError
    otherwise.
    """
    print("[packages/repository] selftest …")
    ok = True

    repo = PackageRepository()

    # 1  catalog is non-empty with unique names
    entries = repo.list_all()
    assert entries, "catalog is empty"
    names = [p.name for p in entries]
    assert len(names) == len(set(names)), "duplicate package names in catalog"
    print("  [PASS] catalog is non-empty with unique names")

    # 2  search matches by name
    hits = repo.search("umer-core")
    assert any(p.name == "umer-core" for p in hits)
    print("  [PASS] search matches by name")

    # 3  search matches by description, case-insensitively
    hits = repo.search("QUANTUM")
    assert any(p.name == "umer-quantum" for p in hits), "description search failed"
    print("  [PASS] search matches by description")

    # 4  get returns the entry, None for an unknown package
    assert repo.get("git") is not None
    assert repo.get("no-such-package") is None
    print("  [PASS] get returns the entry, None for unknown")

    # 5  every entry carries a version and a list of dependencies
    assert all(p.version for p in entries)
    assert all(isinstance(p.dependencies, list) for p in entries)
    print("  [PASS] every entry carries a version and dependency list")

    # 6  repr round-trips name and version
    shown = repr(repo.get("vim"))
    assert shown.startswith("vim (") and shown.endswith(")")
    print("  [PASS] PackageInfo repr")

    print("[packages/repository] selftest PASSED")
    return ok


if __name__ == "__main__":
    _selftest()
