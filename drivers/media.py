"""
UmerOS Media Subsystem
======================
Linux kernel-like Media subsystem for V4L2, DVB, and camera interfaces.
Implements media device topology, entities, pads, and links.

Reference: Documentation/driver-api/media/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional


# ============================================================================
# Media Constants
# ============================================================================

MEDIA_SUCCESS: int = 0
MEDIA_ERROR: int = 1
MEDIA_INVALID: int = 2
MEDIA_NOT_FOUND: int = 3

MEDIA_ENTITY_MAX_PADS: int = 64
MEDIA_MAX_LINKS: int = 256


class MediaType(IntEnum):
    """Media device type."""
    UNKNOWN: int = 0
    V4L2: int = 1
    V4L2_SUBDEV: int = 2
    FB: int = 3
    DVB: int = 4
    I2C: int = 5
    ALSA: int = 6
    CAMERA: int = 7
    SENSOR: int = 8
    ISP: int = 9
    CSI: int = 10
    DISPLAY: int = 11


class MediaPadType(IntEnum):
    """Media pad type."""
    SINK: int = 0
    SOURCE: int = 1


# ============================================================================
# Media Link
# ============================================================================

@dataclass
class MediaLink:
    """Media link between two pads."""
    source_entity: str = ""
    source_pad: int = 0
    sink_entity: str = ""
    sink_pad: int = 0
    flags: int = 0
    enabled: bool = True

    @property
    def is_active(self) -> bool:
        return self.enabled


# ============================================================================
# Media Pad
# ============================================================================

@dataclass
class MediaPad:
    """Media pad (mirrors struct media_pad)."""
    entity_name: str = ""
    index: int = 0
    pad_type: MediaPadType = MediaPadType.SINK
    flags: int = 0
    enabled: bool = True
    link: Optional[MediaLink] = None


# ============================================================================
# Media Entity
# ============================================================================

@dataclass
class MediaEntity:
    """Media entity (mirrors struct media_entity)."""
    name: str
    index: int
    entity_type: MediaType = MediaType.UNKNOWN
    num_pads: int = 0
    num_links: int = 0
    pads: List[MediaPad] = field(default_factory=list)
    links: List[MediaLink] = field(default_factory=list)
    flags: int = 0
    internal: bool = False
    registered: bool = False
    _ops: Dict[str, Callable] = field(default_factory=dict, repr=False)

    def add_pad(self, pad: MediaPad) -> int:
        pad.entity_name = self.name
        pad.index = len(self.pads)
        self.pads.append(pad)
        self.num_pads = len(self.pads)
        return 0

    def remove_pad(self, index: int) -> bool:
        if 0 <= index < len(self.pads):
            self.pads.pop(index)
            self.num_pads = len(self.pads)
            return True
        return False

    def add_link(self, link: MediaLink) -> int:
        self.links.append(link)
        self.num_links = len(self.links)
        return 0

    def enable_pad(self, index: int, enable: bool) -> int:
        if 0 <= index < len(self.pads):
            self.pads[index].enabled = enable
            return 0
        return MEDIA_INVALID

    def get_pad(self, index: int) -> Optional[MediaPad]:
        if 0 <= index < len(self.pads):
            return self.pads[index]
        return None

    def get_source_pads(self) -> List[MediaPad]:
        return [p for p in self.pads if p.pad_type == MediaPadType.SOURCE]

    def get_sink_pads(self) -> List[MediaPad]:
        return [p for p in self.pads if p.pad_type == MediaPadType.SINK]

    def register_ops(self, ops: Dict[str, Callable]) -> None:
        self._ops.update(ops)

    def call_op(self, op_name: str, *args: Any) -> Any:
        if op_name in self._ops:
            return self._ops[op_name](*args)
        return MEDIA_ERROR

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.entity_type.name,
            "pads": self.num_pads,
            "links": self.num_links,
            "flags": self.flags,
        }


# ============================================================================
# Media Device
# ============================================================================

@dataclass
class MediaDevice:
    """Media device (mirrors struct media_device)."""
    name: str
    index: int
    model: str = ""
    serial: str = ""
    bus_info: str = ""
    driver_version: str = "1.0.0"
    media_version: int = 0x050000
    entities: Dict[str, MediaEntity] = field(default_factory=dict)
    links: List[MediaLink] = field(default_factory=list)
    registered: bool = False
    _next_entity_id: int = 0

    def add_entity(self, entity: MediaEntity) -> int:
        entity.index = self._next_entity_id
        entity.registered = True
        self.entities[entity.name] = entity
        self._next_entity_id += 1
        return 0

    def remove_entity(self, name: str) -> int:
        self.entities.pop(name, None)
        return 0

    def get_entity(self, name: str) -> Optional[MediaEntity]:
        return self.entities.get(name)

    def enumerate_entities(self) -> List[MediaEntity]:
        return list(self.entities.values())

    def create_link(self, src_entity: str, src_pad: int, sink_entity: str, sink_pad: int, flags: int = 0) -> int:
        src = self.entities.get(src_entity)
        sink = self.entities.get(sink_entity)
        if not src or not sink:
            return MEDIA_INVALID
        link = MediaLink(source_entity=src_entity, source_pad=src_pad, sink_entity=sink_entity, sink_pad=sink_pad, flags=flags)
        self.links.append(link)
        src.add_link(link)
        sink.add_link(link)
        return 0

    def enable_link(self, index: int, enable: bool) -> int:
        if 0 <= index < len(self.links):
            self.links[index].enabled = enable
            return MEDIA_INVALID
        return MEDIA_INVALID

    def get_topology(self) -> Dict[str, Any]:
        return {
            "device": self.name,
            "model": self.model,
            "entities": len(self.entities),
            "links": len(self.links),
            "entity_list": [e.get_info() for e in self.entities.values()],
        }

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "model": self.model,
            "driver_version": self.driver_version,
            "entities": len(self.entities),
        }


# ============================================================================
# Media Subsystem Manager
# ============================================================================

class MediaSubsystem:
    """Central media subsystem managing media devices."""

    def __init__(self) -> None:
        self._devices: Dict[str, MediaDevice] = {}
        self._next_index: int = 0

    def register_device(self, device: MediaDevice) -> int:
        device.index = self._next_index
        device.registered = True
        self._devices[device.name] = device
        self._next_index += 1
        return 0

    def unregister_device(self, name: str) -> int:
        self._devices.pop(name, None)
        return 0

    def get_device(self, name: str) -> Optional[MediaDevice]:
        return self._devices.get(name)

    def enumerate_devices(self) -> List[MediaDevice]:
        return list(self._devices.values())

    def get_all_entities(self) -> List[MediaEntity]:
        entities = []
        for dev in self._devices.values():
            entities.extend(dev.enumerate_entities())
        return entities


# ============================================================================
# Global Media Instance
# ============================================================================

_global_media: Optional[MediaSubsystem] = None


def get_global_media() -> MediaSubsystem:
    global _global_media
    if _global_media is None:
        _global_media = MediaSubsystem()
    return _global_media


def register_media_device(device: MediaDevice) -> int:
    return get_global_media().register_device(device)


def media_enumerate_entities() -> List[MediaEntity]:
    return get_global_media().get_all_entities()
