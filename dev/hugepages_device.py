"""
UmerOS /dev/hugepages* — Huge page directories.

/dev/hugepages:
  /dev/hugepages/          — Default hugepage pool (2MB pages on x86_64)
  /dev/hugepages-1GB/      — 1GB hugepage pool
  /dev/hugepages-2MB/      — 2MB hugepage pool (alias)
  /dev/hugepages-16MB/     — 16MB hugepage pool (ARM64)
  /dev/hugepages-32MB/     — 32MB hugepage pool (ARM64)
  /dev/hugepages-64MB/     — 64MB hugepage pool (ARM64)
  /dev/hugepages-512MB/    — 512MB hugepage pool (ARM64)

  Huge pages reduce TLB misses by using larger page sizes.
  Mounted via: mount -t hugetlbfs nodev /dev/hugepages

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.HugePagesDevice")


class HugePagesDevice:
    """/dev/hugepages* — Huge page filesystem mount points.

    Provides the directory structure for hugetlbfs mounts.
    Each huge page size gets its own subdirectory.

    Usage:
        mount -t hugetlbfs -o pagesize=2M nodev /dev/hugepages
        mount -t hugetlbfs -o pagesize=1G nodev /dev/hugepages-1GB
    """

    HUGEPAGE_SIZES = {
        "": 2 * 1024 * 1024,           # Default = 2MB
        "-1GB": 1024 * 1024 * 1024,    # 1GB
        "-2MB": 2 * 1024 * 1024,       # 2MB
        "-16MB": 16 * 1024 * 1024,     # 16MB (ARM64)
        "-32MB": 32 * 1024 * 1024,     # 32MB (ARM64)
        "-64MB": 64 * 1024 * 1024,     # 64MB (ARM64)
        "-512MB": 512 * 1024 * 1024,   # 512MB (ARM64)
    }

    def __init__(self):
        self._mounted: Dict[str, bool] = {}
        self._pages: Dict[str, List[int]] = {}
        self._register_directories()
        log.info("HugePagesDevice: created %d hugepage directories",
                 len(self.HUGEPAGE_SIZES))

    def _register_directories(self) -> None:
        mgr = DeviceManager.get_instance()
        for suffix, page_size in self.HUGEPAGE_SIZES.items():
            name = f"hugepages{suffix}" if suffix else "hugepages"
            path = f"/dev/{name}"
            mgr.create_node(DeviceNode(
                name=name, path=path, dev_type=DeviceType.DIRECTORY,
                description=f"Hugepage mount point ({page_size // (1024*1024)}MB)",
            ))
            self._mounted[path] = False
            self._pages[path] = []

    def mount(self, suffix: str = "", pagesize: int = 0) -> bool:
        path = f"/dev/hugepages{suffix}"
        if path not in self._mounted:
            return False
        self._mounted[path] = True
        log.info("hugepages: mounted %s", path)
        return True

    def unmount(self, suffix: str = "") -> bool:
        path = f"/dev/hugepages{suffix}"
        if path not in self._mounted:
            return False
        self._mounted[path] = False
        self._pages[path] = []
        log.info("hugepages: unmounted %s", path)
        return True

    def alloc_page(self, suffix: str = "") -> Optional[int]:
        path = f"/dev/hugepages{suffix}"
        if not self._mounted.get(path):
            return None
        page_id = len(self._pages[path])
        self._pages[path].append(page_id)
        return page_id

    def free_page(self, suffix: str = "", page_id: int = 0) -> bool:
        path = f"/dev/hugepages{suffix}"
        if page_id in self._pages.get(path, []):
            self._pages[path].remove(page_id)
            return True
        return False

    def get_info(self) -> Dict[str, Any]:
        return {
            "directories": list(self.HUGEPAGE_SIZES.keys()),
            "mounted": {k: v for k, v in self._mounted.items() if v},
            "pages_allocated": {k: len(v) for k, v in self._pages.items()},
        }
