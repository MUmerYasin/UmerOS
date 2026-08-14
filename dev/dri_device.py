"""
UmerOS /dev/dri — Direct Rendering Interface (GPU).

FHS 3.0 /dev/dri:
  /dev/dri/cardN    — DRM card device
  /dev/dri/renderDN — DRM render node

major:minor:
  card0 = 226:0, card1 = 226:1, ...
  renderD128 = 226:128, renderD129 = 226:129, ...

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.DriDevice")


class DriDevice:
    """DRI/DRM device manager — /dev/dri/.

    Provides:
      /dev/dri/card0-card3   — DRM card devices
      /dev/dri/renderD128-renderD131 — DRM render nodes
    """

    DRM_MAJOR = 226
    CARD_COUNT = 4
    RENDER_COUNT = 4
    RENDER_MINOR_START = 128

    def __init__(self):
        self._cards: Dict[int, Dict[str, Any]] = {}
        self._renders: Dict[int, Dict[str, Any]] = {}
        self._register_directory()
        self._register_devices()
        log.info("DriDevice created")

    def _register_directory(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="dri", path="/dev/dri", dev_type=DeviceType.DIRECTORY,
            description="Direct Rendering Interface",
        ))

    def _register_devices(self) -> None:
        mgr = DeviceManager.get_instance()
        # Card devices
        for i in range(self.CARD_COUNT):
            path = f"/dev/dri/card{i}"
            mgr.create_node(DeviceNode(
                name=f"card{i}", path=path, dev_type=DeviceType.CHAR,
                major=self.DRM_MAJOR, minor=i, mode=0o660,
                description=f"DRI card {i}",
                ioctl_callback=lambda cmd, arg, n=i: self._on_card_ioctl(cmd, arg, n),
            ))
            self._cards[i] = {"path": path, "vendor": "Intel", "active": True}
        # Render nodes
        for i in range(self.RENDER_COUNT):
            minor = self.RENDER_MINOR_START + i
            path = f"/dev/dri/renderD{minor}"
            mgr.create_node(DeviceNode(
                name=f"renderD{minor}", path=path, dev_type=DeviceType.CHAR,
                major=self.DRM_MAJOR, minor=minor, mode=0o660,
                description=f"DRM render node {minor}",
            ))
            self._renders[i] = {"path": path, "minor": minor}

    def _on_card_ioctl(self, cmd: int, arg: Any, card_num: int) -> int:
        return 0

    def get_card_info(self, card_num: int) -> Optional[Dict[str, Any]]:
        return self._cards.get(card_num)

    def get_render_info(self, render_num: int) -> Optional[Dict[str, Any]]:
        return self._renders.get(render_num)

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/dri",
            "card_count": len(self._cards),
            "render_count": len(self._renders),
            "cards": {k: v["vendor"] for k, v in self._cards.items()},
        }

    def __repr__(self) -> str:
        return f"<DriDevice cards={len(self._cards)}>"
