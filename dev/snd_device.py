"""
UmerOS /dev/snd — ALSA sound devices.

FHS 3.0 /dev/snd:
  /dev/snd/cardN    — ALSA card device
  /dev/snd/controlC — Control interface

Linux major:minor:
  card0 = 116:0, card1 = 116:1, ...
  controlC0 = 116:256, ...

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.SndDevice")


class SndDevice:
    """ALSA sound device manager — /dev/snd/.

    Provides:
      /dev/snd/card0-card3    — ALSA card devices
      /dev/snd/controlC0      — Control interface
    """

    ALSA_MAJOR = 116
    CARD_COUNT = 4
    CONTROL_MINOR_START = 256

    def __init__(self):
        self._cards: Dict[int, Dict[str, Any]] = {}
        self._register_directory()
        self._register_devices()
        log.info("SndDevice created")

    def _register_directory(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="snd", path="/dev/snd", dev_type=DeviceType.DIRECTORY,
            description="ALSA sound devices",
        ))

    def _register_devices(self) -> None:
        mgr = DeviceManager.get_instance()
        for i in range(self.CARD_COUNT):
            # Card device
            path = f"/dev/snd/card{i}"
            mgr.create_node(DeviceNode(
                name=f"card{i}", path=path, dev_type=DeviceType.CHAR,
                major=self.ALSA_MAJOR, minor=i, mode=0o660,
                description=f"ALSA card {i}",
                ioctl_callback=lambda cmd, arg, n=i: self._on_card_ioctl(cmd, arg, n),
            ))
            # Control interface
            ctrl_path = f"/dev/snd/controlC{i}"
            ctrl_minor = self.CONTROL_MINOR_START + i
            mgr.create_node(DeviceNode(
                name=f"controlC{i}", path=ctrl_path, dev_type=DeviceType.CHAR,
                major=self.ALSA_MAJOR, minor=ctrl_minor, mode=0o660,
                description=f"ALSA control C{i}",
            ))
            self._cards[i] = {
                "card_path": path,
                "control_path": ctrl_path,
                "name": f"ALSA Card {i}",
                "active": True,
            }

    def _on_card_ioctl(self, cmd: int, arg: Any, card_num: int) -> int:
        return 0

    def get_card_info(self, card_num: int) -> Optional[Dict[str, Any]]:
        return self._cards.get(card_num)

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/snd",
            "card_count": len(self._cards),
            "cards": {k: v["name"] for k, v in self._cards.items()},
        }

    def __repr__(self) -> str:
        return f"<SndDevice cards={len(self._cards)}>"
