"""
Wayland Protocol Manager - /usr/share/wayland

Manages Wayland protocol definitions:
- Core Wayland protocol
- Stable protocol extensions
- Unstable protocol extensions
- Protocol XML files
"""
from __future__ import annotations
from enum import IntEnum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List, Any
import uuid


class ProtocolStability(IntEnum):
    """Protocol stability level"""
    CORE = 0
    STABLE = 1
    UNSTABLE = 2
    LEGACY = 3


@dataclass
class WaylandProtocol:
    """A Wayland protocol definition"""
    protocol_id: str
    name: str
    stability: ProtocolStability
    xml_path: str
    version: int = 1
    description: str = ""
    interfaces: List[str] = field(default_factory=list)
    file_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "protocol_id": self.protocol_id,
            "name": self.name,
            "stability": self.stability,
            "xml_path": self.xml_path,
            "version": self.version,
            "description": self.description,
            "interfaces": self.interfaces,
            "file_path": self.file_path,
        }


WAYLAND_PATH = "/usr/share/wayland"
WAYLAND_PROTOCOLS_PATH = "/usr/share/wayland-protocols"

PROTOCOL_DIRS = {
    ProtocolStability.CORE: ["core"],
    ProtocolStability.STABLE: ["stable"],
    ProtocolStability.UNSTABLE: ["unstable", "staging"],
    ProtocolStability.LEGACY: ["legacy"],
}

KNOWN_PROTOCOLS = {
    "wl_compositor": "Core compositor protocol",
    "wl_shm": "Shared memory buffers",
    "wl_data_device": "Drag and drop / clipboard",
    "wl_output": "Output/display management",
    "wl_seat": "Input device abstraction",
    "wl_keyboard": "Keyboard input",
    "wl_pointer": "Pointer/mouse input",
    "wl_touch": "Touch input",
    "wl_surface": "Surface management",
    "wl_buffer": "Buffer management",
    "wl_registry": "Object registry",
    "wl_subcompositor": "Sub-surface compositing",
    "xdg_wm_base": "XDG shell stable",
    "xdg_shell": "XDG shell (base)",
    "xdg_surface": "XDG surface",
    "xdg_toplevel": "XDG toplevel window",
    "xdg_popup": "XDG popup window",
    "xdg_positioner": "XDG popup positioning",
    "zwlr_layer_shell": "Layer shell (unstable)",
    "zwlr_output_manager": "Output management (unstable)",
    "zxdg_decoration_manager": "Server-side decorations (unstable)",
    "zwp_relative_pointer": "Relative pointer (unstable)",
    "zwp_pointer_constraints": "Pointer constraints (unstable)",
    "zwp_input_method": "Input method (unstable)",
    "zwp_text_input": "Text input (unstable)",
}


class WaylandProtocolManager:
    """Manages /usr/share/wayland and /usr/share/wayland-protocols"""

    def __init__(self):
        self._protocols: Dict[str, WaylandProtocol] = {}
        self._wayland_path = Path(WAYLAND_PATH)
        self._protocols_path = Path(WAYLAND_PROTOCOLS_PATH)
        self._initialized = False

    def initialize(self) -> bool:
        if self._initialized:
            return True
        self._wayland_path.mkdir(parents=True, exist_ok=True)
        self._protocols_path.mkdir(parents=True, exist_ok=True)
        self._initialized = True
        return True

    def refresh(self) -> bool:
        self._protocols.clear()

        # Load known protocols
        for name, desc in KNOWN_PROTOCOLS.items():
            proto = self._categorize_protocol(name, desc)
            self._protocols[proto.protocol_id] = proto

        # Scan filesystem for actual XML files
        self._scan_protocols(self._protocols_path)

        return True

    def _categorize_protocol(self, name: str, description: str) -> WaylandProtocol:
        """Determine protocol stability from name"""
        if name.startswith("wl_") or name.startswith("wl-"):
            stability = ProtocolStability.CORE
        elif name.startswith("xdg_") or name.startswith("xdg-"):
            stability = ProtocolStability.STABLE
        elif name.startswith("zwlr_") or name.startswith("zwp_") or name.startswith("zxdg_"):
            stability = ProtocolStability.UNSTABLE
        else:
            stability = ProtocolStability.STABLE

        return WaylandProtocol(
            protocol_id=str(uuid.uuid4()),
            name=name,
            stability=stability,
            xml_path=f"{name}.xml",
            description=description,
        )

    def _scan_protocols(self, path: Path):
        """Scan filesystem for protocol XML files"""
        if not path.exists():
            return

        for xml_file in path.rglob("*.xml"):
            name = xml_file.stem
            if name not in [p.name for p in self._protocols.values()]:
                proto = WaylandProtocol(
                    protocol_id=str(uuid.uuid4()),
                    name=name,
                    stability=self._detect_stability(xml_file),
                    xml_path=str(xml_file),
                    file_path=str(xml_file),
                )
                self._protocols[proto.protocol_id] = proto

    def _detect_stability(self, path: Path) -> ProtocolStability:
        """Detect stability from file path"""
        parts = [p.lower() for p in path.parts]
        if "unstable" in parts or "staging" in parts:
            return ProtocolStability.UNSTABLE
        if "stable" in parts:
            return ProtocolStability.STABLE
        if "core" in parts:
            return ProtocolStability.CORE
        return ProtocolStability.STABLE

    def list_protocols(self, stability: Optional[ProtocolStability] = None) -> List[Dict[str, Any]]:
        if stability is None:
            return [p.to_dict() for p in self._protocols.values()]
        return [p.to_dict() for p in self._protocols.values() if p.stability == stability]

    def get_protocol(self, protocol_id: str) -> Optional[Dict[str, Any]]:
        proto = self._protocols.get(protocol_id)
        return proto.to_dict() if proto else None

    def get_protocol_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        for proto in self._protocols.values():
            if proto.name == name:
                return proto.to_dict()
        return None

    def search_protocols(self, query: str) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        return [
            p.to_dict() for p in self._protocols.values()
            if query_lower in p.name.lower() or query_lower in p.description.lower()
        ]

    def get_wayland_path(self) -> Path:
        return self._wayland_path

    def get_protocols_path(self) -> Path:
        return self._protocols_path

    def get_stats(self) -> Dict[str, int]:
        stability_counts = {}
        for proto in self._protocols.values():
            s = proto.stability.name
            stability_counts[s] = stability_counts.get(s, 0) + 1

        return {
            "total_protocols": len(self._protocols),
            "by_stability": stability_counts,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wayland_path": str(self._wayland_path),
            "protocols_path": str(self._protocols_path),
            "stats": self.get_stats(),
        }


_manager: Optional[WaylandProtocolManager] = None


def get_global_wayland_protocol_manager() -> WaylandProtocolManager:
    global _manager
    if _manager is None:
        _manager = WaylandProtocolManager()
    return _manager


def initialize() -> bool:
    return get_global_wayland_protocol_manager().initialize()


def refresh() -> bool:
    return get_global_wayland_protocol_manager().refresh()
