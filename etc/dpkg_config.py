#!/usr/bin/env python3
"""
UmerOS - /etc/dpkg manager
FHS 3.0: /etc/dpkg/ contains dpkg configuration and status.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, List

DPKG_DIR = Path(os.environ.get("UMEROS_DPKG", "/etc/dpkg"))
DPKG_STATUS = DPKG_DIR / "status"
DPKG_ORIGINS = DPKG_DIR / "origins"
DPKG_CFG = DPKG_DIR / "dpkg.cfg"

DEFAULT_DPKG_CFG = """# /etc/dpkg/dpkg.cfg - UmerOS dpkg options
#paths
#path-exclude /usr/share/doc/*
"""


class DpkgConfigManager:
    """Manages /etc/dpkg/ configuration for Debian package management."""

    def __init__(self):
        DPKG_DIR.mkdir(parents=True, exist_ok=True)
        DPKG_ORIGINS.mkdir(parents=True, exist_ok=True)
        if not DPKG_CFG.exists():
            DPKG_CFG.write_text(DEFAULT_DPKG_CFG, encoding="utf-8")
        if not DPKG_STATUS.exists():
            DPKG_STATUS.write_text("Status: install ok installed\nPackage: dpkg\nVersion: 1.21.21\n", encoding="utf-8")

    def read_dpkg_cfg(self) -> str:
        return DPKG_CFG.read_text(encoding="utf-8") if DPKG_CFG.exists() else ""

    def list_packages(self) -> List[str]:
        if not DPKG_STATUS.exists():
            return []
        packages = []
        current = {}
        for line in DPKG_STATUS.read_text(encoding="utf-8").splitlines():
            if line == "" and current.get("Package"):
                packages.append(current["Package"])
                current = {}
            elif ": " in line:
                key, _, val = line.partition(": ")
                current[key] = val
        if current.get("Package"):
            packages.append(current["Package"])
        return packages

    def status_path(self) -> Path:
        return DPKG_STATUS
