"""
UmerOS Component Framework
==========================
Kernel component (glue layer) subsystem.
Implements component binding for multi-function devices
that need multiple sub-drivers to be ready before probing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Component Constants
# ---------------------------------------------------------------------------
COMP_MATCH_ANY: str = "*"
COMP_MATCH_NAME: str = "name"
COMP_MATCH_TYPE: str = "type"
COMP_MATCH_MASTER: str = "master"

# ---------------------------------------------------------------------------
# Global Registries
# ---------------------------------------------------------------------------
_master_groups: Dict[str, MasterComponent] = {}
_master_clients: Dict[str, List[ComponentMatch]] = {}
_components: Dict[str, Component] = {}
_pending_masters: Dict[str, bool] = {}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class ComponentMatch:
    """Component match criteria"""
    name: str = COMP_MATCH_ANY
    match_type: str = COMP_MATCH_ANY
    master_name: str = ""
    data: Any = None


@dataclass
class Component:
    """A sub-device that is part of a composite device"""
    name: str
    master_name: str = ""
    match_data: Any = None
    is_bound: bool = False
    is_registered: bool = False
    _ops: Dict[str, Callable] = field(default_factory=dict)


@dataclass
class MasterComponent:
    """Master device that aggregates components"""
    name: str
    min_count: int = 1
    max_count: int = 256
    is_bound: bool = False
    is_registered: bool = False
    _components: List[str] = field(default_factory=list)
    _ops: Dict[str, Callable] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Registration Functions
# ---------------------------------------------------------------------------
def register_master(name: str, min_count: int = 1,
                    max_count: int = 256) -> MasterComponent:
    """Register a master device"""
    if name in _master_groups:
        log.warning("Master %s already registered", name)
        return _master_groups[name]

    master = MasterComponent(
        name=name,
        min_count=min_count,
        max_count=max_count,
        is_registered=True,
    )
    _master_groups[name] = master
    _master_clients[name] = []
    log.info("Registered master: %s (min=%d, max=%d)", name, min_count, max_count)
    return master


def register_component(name: str, master_name: str,
                       match_data: Any = None) -> Component:
    """Register a component"""
    if name in _components:
        log.warning("Component %s already registered", name)
        return _components[name]

    comp = Component(
        name=name,
        master_name=master_name,
        match_data=match_data,
        is_registered=True,
    )
    _components[name] = comp
    log.info("Registered component: %s (master=%s)", name, master_name)
    return comp


def add_match(master_name: str, name: str = COMP_MATCH_ANY,
              match_type: str = COMP_MATCH_ANY) -> bool:
    """Add a match rule for a master"""
    if master_name not in _master_clients:
        _master_clients[master_name] = []

    match = ComponentMatch(name=name, match_type=match_type, master_name=master_name)
    _master_clients[master_name].append(match)
    log.info("Added match for %s: name=%s, type=%s", master_name, name, match_type)
    return True


def unregister_component(name: str) -> bool:
    """Unregister a component"""
    if name not in _components:
        log.warning("Component %s not found", name)
        return False

    comp = _components[name]
    if comp.is_bound:
        log.warning("Cannot unregister bound component %s", name)
        return False

    del _components[name]
    log.info("Unregistered component: %s", name)
    return True


def unregister_master(name: str) -> bool:
    """Unregister a master device"""
    if name not in _master_groups:
        log.warning("Master %s not found", name)
        return False

    master = _master_groups[name]
    if master.is_bound:
        log.warning("Cannot unregister bound master %s", name)
        return False

    del _master_groups[name]
    if name in _master_clients:
        del _master_clients[name]
    log.info("Unregistered master: %s", name)
    return True


def get_master(name: str) -> Optional[MasterComponent]:
    """Get a registered master"""
    return _master_groups.get(name)


def get_component(name: str) -> Optional[Component]:
    """Get a registered component"""
    return _components.get(name)


def list_masters() -> List[str]:
    """List all registered masters"""
    return list(_master_groups.keys())


def list_components() -> List[str]:
    """List all registered components"""
    return list(_components.keys())


# ---------------------------------------------------------------------------
# Binding Operations
# ---------------------------------------------------------------------------
def match_component(master_name: str, comp_name: str) -> bool:
    """Check if a component matches a master's requirements"""
    if master_name not in _master_clients:
        return False

    comp = get_component(comp_name)
    if comp is None:
        return False

    matches = _master_clients[master_name]
    for m in matches:
        if m.name == COMP_MATCH_ANY or m.name == comp_name:
            if m.match_type == COMP_MATCH_ANY or m.match_type == comp.match_data:
                return True
    return False


def bind_master(master_name: str) -> bool:
    """Bind all matching components to a master"""
    master = get_master(master_name)
    if master is None:
        log.error("Master %s not found", master_name)
        return False

    if master.is_bound:
        log.warning("Master %s already bound", master_name)
        return True

    bound_count = 0
    for comp_name, comp in _components.items():
        if comp.master_name == master_name and not comp.is_bound:
            if match_component(master_name, comp_name):
                comp.is_bound = True
                master._components.append(comp_name)
                bound_count += 1
                log.info("Bound component %s to master %s", comp_name, master_name)

    if bound_count >= master.min_count:
        master.is_bound = True
        log.info("Master %s bound with %d components", master_name, bound_count)
        return True
    else:
        log.warning("Master %s needs %d components, only %d bound",
                     master_name, master.min_count, bound_count)
        return False


def unbind_master(master_name: str) -> bool:
    """Unbind all components from a master"""
    master = get_master(master_name)
    if master is None:
        log.error("Master %s not found", master_name)
        return False

    if not master.is_bound:
        return True

    for comp_name in master._components[:]:
        comp = get_component(comp_name)
        if comp is not None:
            comp.is_bound = False
            log.info("Unbound component %s from master %s", comp_name, master_name)

    master._components.clear()
    master.is_bound = False
    log.info("Unbound master %s", master_name)
    return True


def get_master_components(master_name: str) -> List[str]:
    """Get list of components bound to a master"""
    master = get_master(master_name)
    if master is None:
        return []
    return master._components.copy()


def get_pending_masters() -> List[str]:
    """Get masters waiting for enough components"""
    pending = []
    for name, master in _master_groups.items():
        if not master.is_bound:
            bound = len(master._components)
            if bound < master.min_count:
                pending.append(name)
    return pending


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== UmerOS Component Framework Demo ===\n")

    # Register masters
    register_master("display", min_count=2, max_count=4)
    register_master("audio", min_count=1, max_count=2)

    # Register components
    register_component("drm_panel", master_name="display", match_data="panel")
    register_component("drm_bridge", master_name="display", match_data="bridge")
    register_component("hdmi_tx", master_name="display", match_data="hdmi")
    register_component("codec", master_name="audio", match_data="codec")

    print(f"Masters: {list_masters()}")
    print(f"Components: {list_components()}")

    # Add match rules
    add_match("display", match_type="panel")
    add_match("display", match_type="bridge")
    add_match("audio", match_type="codec")

    # Bind
    print("\n--- Binding ---")
    bind_master("display")
    bind_master("audio")

    print(f"\nDisplay components: {get_master_components('display')}")
    print(f"Audio components: {get_master_components('audio')}")
    print(f"Pending: {get_pending_masters()}")
