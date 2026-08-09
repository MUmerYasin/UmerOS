"""
UmerOS /dev — Media framework devices.

Linux media device files:
  /dev/media0-31  — Media Controller API (V4L2 pipeline)
  /dev/dvb0-7     — DVB (Digital Video Broadcasting)
  /dev/video0-31  — Video4Linux2 capture devices

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.MediaDevice")


class MediaDevice:
    """Media framework devices — /dev/media*, /dev/dvb*, /dev/video*.

    Linux Media Controller API and V4L2/DVB devices:

    /dev/media*  — Media Controller (major 249)
      Manages complex media pipelines (ISP, codec, capture chains)

    /dev/dvb*    — DVB devices (major 212)
      Digital TV receiver: demux, DVR, frontend, net

    /dev/video*  — Video4Linux2 (major 81)
      Webcam, capture cards, V4L2 devices

    Major numbers:
      81  = video* (V4L2)
      212 = dvb*   (DVB)
      249 = media* (Media Controller)
    """

    VIDEO_MAJOR = 81
    DVB_MAJOR = 212
    MEDIA_MAJOR = 249

    MAX_VIDEO = 16
    MAX_DVB = 8
    MAX_MEDIA = 8

    def __init__(self):
        self._device_info: Dict[str, Dict[str, Any]] = {}
        self._create_devices()
        log.info("MediaDevice created (%d video, %d dvb, %d media)",
                 self.MAX_VIDEO, self.MAX_DVB, self.MAX_MEDIA)

    def _create_devices(self) -> None:
        mgr = DeviceManager.get_instance()

        # /dev/video0-15 (V4L2)
        for i in range(self.MAX_VIDEO):
            name = f"video{i}"
            path = f"/dev/{name}"
            mgr.create_node(DeviceNode(
                name=name, path=path, dev_type=DeviceType.CHAR,
                major=self.VIDEO_MAJOR, minor=i * 2,
                mode=0o660,
                description=f"Video4Linux2 device {i}",
                ioctl_callback=lambda req, arg, n=name: self._on_ioctl(n, req, arg),
            ))
            self._device_info[name] = {
                "type": "v4l2", "card": f"UmerOS Video {i}",
                "bus": "platform:", "capabilities": 0x05010000,
            }

        # /dev/dvb0-7 (DVB)
        for i in range(self.MAX_DVB):
            for suffix in ("demux", "dvr", "frontend", "net"):
                name = f"dvb{i}.{suffix}"
                path = f"/dev/{name}"
                minor = i * 4 + {"demux": 0, "dvr": 1, "frontend": 2, "net": 3}[suffix]
                mgr.create_node(DeviceNode(
                    name=name, path=path, dev_type=DeviceType.CHAR,
                    major=self.DVB_MAJOR, minor=minor,
                    mode=0o660,
                    description=f"DVB adapter {i} {suffix}",
                ))

        # /dev/media0-7 (Media Controller)
        for i in range(self.MAX_MEDIA):
            name = f"media{i}"
            path = f"/dev/{name}"
            mgr.create_node(DeviceNode(
                name=name, path=path, dev_type=DeviceType.CHAR,
                major=self.MEDIA_MAJOR, minor=i,
                mode=0o444,
                description=f"Media Controller {i}",
                ioctl_callback=lambda req, arg, n=name: self._on_ioctl(n, req, arg),
            ))
            self._device_info[name] = {
                "driver": "umeros-media",
                "model": f"UmerOS Media Controller {i}",
            }

    def _on_ioctl(self, device: str, request: int, arg: Any) -> int:
        """Handle media/v4l2 ioctl commands."""
        MEDIA_IOC_DEVICE_INFO = 0xc06c7c00
        MEDIA_IOC_G_TOPOLOGY = 0xc0487c03
        if request == MEDIA_IOC_DEVICE_INFO:
            return 0
        elif request == MEDIA_IOC_G_TOPOLOGY:
            return 0
        return 0

    def get_info(self) -> Dict[str, Any]:
        return {
            "video_major": self.VIDEO_MAJOR,
            "dvb_major": self.DVB_MAJOR,
            "media_major": self.MEDIA_MAJOR,
            "video_count": self.MAX_VIDEO,
            "dvb_count": self.MAX_DVB,
            "media_count": self.MAX_MEDIA,
        }

    def __repr__(self) -> str:
        return f"<MediaDevice video={self.MAX_VIDEO} dvb={self.MAX_DVB} media={self.MAX_MEDIA}>"
