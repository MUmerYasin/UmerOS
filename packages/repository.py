#!/usr/bin/env python3
"""
Umer OS Package Repository

Simulated local package catalog. In production this would fetch from
a remote repository server; for now it provides a built-in catalog
of available packages with version metadata and dependency info.

Equivalent to /etc/apt/sources.list + package index in Debian.
"""


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
        print(f"[REPO] Package repository loaded ({len(self._catalog)} packages available).")

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
