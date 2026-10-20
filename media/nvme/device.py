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

"""
UmerOS /media/nvme - NVMe Device Discovery (sysfs)
==================================================

Discovers NVMe controllers, namespaces, partitions and alias
namespaces through ``/sys/class/nvme`` (Linux sysfs).  Pure
Python (standard library only) - no third-party packages.

The module works in two modes, mirroring the rest of the
``media`` package:

1. **Real-system mode** - reads sysfs attributes from
   ``/sys/class/nvme`` (controllers ``nvmeN``, namespaces
   ``nvmeNnM``) and ``/sys/devices/virtual/nvme-subsystem``.
2. **Simulated mode** - ``set_simulation()`` installs an
   in-memory device table so UmerOS can exercise the NVMe
   subsystem on any host (Windows/macOS CI, unit tests)
   without physical hardware.

Device naming follows the kernel convention:

* ``nvme0``        controller
* ``nvme0n1``      namespace
* ``nvme0n1p1``    partition
* ``nvme0c1n1``    alias namespace

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Media.NVMe.Device")

SYS_CLASS_NVME = Path("/sys/class/nvme")
SYS_NVM_SUBSYSTEM = Path("/sys/devices/virtual/nvme-subsystem")

KIND_CONTROLLER = "controller"
KIND_NAMESPACE = "namespace"
KIND_PARTITION = "partition"
KIND_ALIAS = "alias"

_CTRL_RE = re.compile(r"^nvme[0-9]+$")
_NS_RE = re.compile(r"^nvme[0-9]+n[0-9]+$")
_PART_RE = re.compile(r"^nvme[0-9]+n[0-9]+p[0-9]+$")
_ALIAS_RE = re.compile(r"^nvme[0-9]+c[0-9]+n[0-9]+$")
_CTRL_PREFIX_RE = re.compile(r"^(nvme[0-9]+)n[0-9]+(?:p[0-9]+)?$")


def classify_nvme_name(name: str) -> Optional[str]:
    """Classify a kernel NVMe device name.

    Returns ``"controller"``, ``"namespace"``, ``"partition"`` or
    ``"alias"`` - or ``None`` when *name* is not an NVMe name.
    """
    name = name.strip()
    if _PART_RE.match(name):
        return KIND_PARTITION
    if _ALIAS_RE.match(name):
        return KIND_ALIAS
    if _NS_RE.match(name):
        return KIND_NAMESPACE
    if _CTRL_RE.match(name):
        return KIND_CONTROLLER
    return None


def controller_of(namespace_name: str) -> Optional[str]:
    """Return the controller name (``nvme0``) owning *namespace_name*."""
    match = _CTRL_PREFIX_RE.match(namespace_name.strip())
    return match.group(1) if match else None


@dataclass
class NVMeControllerInfo:
    """A single NVMe controller (``/sys/class/nvme/nvmeN``)."""

    name: str
    model: Optional[str] = None
    serial: Optional[str] = None
    firmware: Optional[str] = None
    transport: Optional[str] = None
    pci_address: Optional[str] = None
    cntlid: Optional[int] = None
    state: Optional[str] = None
    numa_node: Optional[int] = None
    queue_count: Optional[int] = None
    sqsize: Optional[int] = None
    subsysnqn: Optional[str] = None
    namespaces: List[str] = field(default_factory=list)

    @property
    def device_path(self) -> str:
        return f"/dev/{self.name}"


@dataclass
class NVMeNamespaceInfo:
    """An NVMe namespace (``/sys/class/nvme/nvmeNnM``)."""

    name: str
    controller: Optional[str] = None
    nsid: Optional[int] = None
    size_bytes: Optional[int] = None
    uuid: Optional[str] = None
    eui64: Optional[str] = None
    wwid: Optional[str] = None
    fmt_lba_size: Optional[int] = None

    @property
    def device_path(self) -> str:
        return f"/dev/{self.name}"


@dataclass
class NVMeSubsystemInfo:
    """An NVMe subsystem (``/sys/devices/virtual/nvme-subsystem``)."""

    name: str
    nqn: Optional[str] = None
    model: Optional[str] = None
    serial: Optional[str] = None
    firmware: Optional[str] = None
    iopolicy: Optional[str] = None


def _read_attr(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except (OSError, IOError):
        return None


def _read_int(path: Path) -> Optional[int]:
    raw = _read_attr(path)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _read_str(path: Path) -> Optional[str]:
    raw = _read_attr(path)
    return raw if raw else None


def read_controller_info(
    name: str, root: Path = SYS_CLASS_NVME
) -> Optional[NVMeControllerInfo]:
    """Read sysfs attributes for controller *name* (e.g. ``nvme0``)."""
    base = Path(root) / name
    if not base.exists():
        return None
    info = NVMeControllerInfo(name=name)
    info.model = _read_str(base / "model")
    info.serial = _read_str(base / "serial")
    info.firmware = _read_str(base / "firmware_rev")
    info.transport = _read_str(base / "transport")
    info.pci_address = _read_str(base / "address")
    info.cntlid = _read_int(base / "cntlid")
    info.state = _read_str(base / "state")
    info.numa_node = _read_int(base / "numa_node")
    info.queue_count = _read_int(base / "queue_count")
    info.sqsize = _read_int(base / "sqsize")
    info.subsysnqn = _read_str(base / "subsysnqn")
    return info


def read_namespace_info(
    name: str, root: Path = SYS_CLASS_NVME
) -> Optional[NVMeNamespaceInfo]:
    """Read sysfs attributes for namespace *name* (e.g. ``nvme0n1``).

    The sysfs ``size`` attribute is expressed in 512-byte sectors,
    so :attr:`NVMeNamespaceInfo.size_bytes` is ``size * 512``.
    """
    base = Path(root) / name
    if not base.exists():
        return None
    info = NVMeNamespaceInfo(name=name, controller=controller_of(name))
    info.nsid = _read_int(base / "nsid")
    info.uuid = _read_str(base / "uuid")
    info.eui64 = _read_str(base / "eui64")
    info.wwid = _read_str(base / "wwid")
    info.fmt_lba_size = _read_int(base / "fmt_lba_size")
    sectors = _read_int(base / "size")
    if sectors is not None:
        info.size_bytes = sectors * 512
    return info


def read_subsystem_info(
    name: str, root: Path = SYS_NVM_SUBSYSTEM
) -> Optional[NVMeSubsystemInfo]:
    """Read sysfs attributes for subsystem *name* (``nvme-subsysN``)."""
    base = Path(root) / name
    if not base.exists():
        return None
    info = NVMeSubsystemInfo(name=name)
    info.nqn = _read_str(base / "subsysnqn")
    info.model = _read_str(base / "model")
    info.serial = _read_str(base / "serial")
    info.firmware = _read_str(base / "firmware_rev")
    info.iopolicy = _read_str(base / "iopolicy")
    return info


_SIM_DEVICES: Optional[Dict[str, Dict[str, str]]] = None


def set_simulation(devices: Optional[Dict[str, Dict[str, str]]]) -> None:
    """Install an in-memory device table for simulated discovery.

    *devices* maps device names (``nvme0``, ``nvme0n1``) to a dict of
    sysfs attribute names to string values, e.g.::

        set_simulation({"nvme0": {"model": "WD SN770", ...}})

    Pass ``None`` (or use :func:`clear_simulation`) to return to
    real sysfs discovery.
    """
    global _SIM_DEVICES
    _SIM_DEVICES = devices
    if devices:
        log.info("NVMe discovery simulation active with %d device(s)", len(devices))
    else:
        log.info("NVMe discovery simulation cleared")


def get_simulation() -> Optional[Dict[str, Dict[str, str]]]:
    """Return the active simulation table, or ``None``."""
    return _SIM_DEVICES


def clear_simulation() -> None:
    """Clear the simulation table (back to real sysfs)."""
    set_simulation(None)


def _sim_read(name: str, attr: str) -> Optional[str]:
    if _SIM_DEVICES is None:
        return None
    raw = _SIM_DEVICES.get(name, {}).get(attr)
    return raw if raw not in (None, "") else None


def _sim_read_int(name: str, attr: str) -> Optional[int]:
    raw = _sim_read(name, attr)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _read_ctrl_sim(name: str) -> Optional[NVMeControllerInfo]:
    if _SIM_DEVICES is None or name not in _SIM_DEVICES:
        return None
    info = NVMeControllerInfo(name=name)
    info.model = _sim_read(name, "model")
    info.serial = _sim_read(name, "serial")
    info.firmware = _sim_read(name, "firmware_rev")
    info.transport = _sim_read(name, "transport")
    info.pci_address = _sim_read(name, "address")
    info.cntlid = _sim_read_int(name, "cntlid")
    info.state = _sim_read(name, "state")
    info.numa_node = _sim_read_int(name, "numa_node")
    info.queue_count = _sim_read_int(name, "queue_count")
    info.sqsize = _sim_read_int(name, "sqsize")
    info.subsysnqn = _sim_read(name, "subsysnqn")
    return info


def _read_ns_sim(name: str) -> Optional[NVMeNamespaceInfo]:
    if _SIM_DEVICES is None or name not in _SIM_DEVICES:
        return None
    if classify_nvme_name(name) not in (KIND_NAMESPACE, KIND_ALIAS):
        return None
    info = NVMeNamespaceInfo(name=name, controller=controller_of(name))
    info.nsid = _sim_read_int(name, "nsid")
    info.uuid = _sim_read(name, "uuid")
    info.eui64 = _sim_read(name, "eui64")
    info.wwid = _sim_read(name, "wwid")
    info.fmt_lba_size = _sim_read_int(name, "fmt_lba_size")
    sectors = _sim_read_int(name, "size")
    if sectors is not None:
        info.size_bytes = sectors * 512
    return info


def _attach(
    controllers: Dict[str, NVMeControllerInfo],
    namespaces: Dict[str, NVMeNamespaceInfo],
) -> None:
    for ns_name, ns_info in namespaces.items():
        ctrl_name = ns_info.controller
        if ctrl_name in controllers:
            controllers[ctrl_name].namespaces.append(ns_name)
        else:
            log.warning(
                "namespace %s has no visible controller %s", ns_name, ctrl_name
            )


def discover(root: Path = SYS_CLASS_NVME) -> List[NVMeControllerInfo]:
    """Discover all NVMe controllers with their namespaces.

    Args:
        root: sysfs directory holding ``nvmeN`` / ``nvmeNnM`` entries.

    Returns:
        A list of :class:`NVMeControllerInfo` sorted by name.  Empty
        when the host has no NVMe controllers (or on non-Linux hosts
        without simulation).
    """
    if _SIM_DEVICES is not None:
        return _discover_sim()
    if not root.exists():
        log.debug("no NVMe sysfs at %s", root)
        return []

    controllers: Dict[str, NVMeControllerInfo] = {}
    namespaces: Dict[str, NVMeNamespaceInfo] = {}

    for entry in sorted(os.listdir(root)):
        kind = classify_nvme_name(entry)
        if kind == KIND_CONTROLLER:
            info = read_controller_info(entry, root)
            if info is not None:
                controllers[entry] = info
        elif kind in (KIND_NAMESPACE, KIND_ALIAS):
            info = read_namespace_info(entry, root)
            if info is not None:
                namespaces[entry] = info

    _attach(controllers, namespaces)
    return [controllers[name] for name in sorted(controllers)]


def _discover_sim() -> List[NVMeControllerInfo]:
    assert _SIM_DEVICES is not None
    controllers: Dict[str, NVMeControllerInfo] = {}
    namespaces: Dict[str, NVMeNamespaceInfo] = {}
    for name in sorted(_SIM_DEVICES):
        kind = classify_nvme_name(name)
        if kind == KIND_CONTROLLER:
            info = _read_ctrl_sim(name)
            if info is not None:
                controllers[name] = info
        elif kind in (KIND_NAMESPACE, KIND_ALIAS):
            info = _read_ns_sim(name)
            if info is not None:
                namespaces[name] = info
    _attach(controllers, namespaces)
    return [controllers[name] for name in sorted(controllers)]


def discover_namespaces(root: Path = SYS_CLASS_NVME) -> List[NVMeNamespaceInfo]:
    """Discover all NVMe namespaces (``nvmeNnM``) regardless of controller."""
    if _SIM_DEVICES is not None:
        return sorted(
            (
                info
                for info in (
                    _read_ns_sim(n) for n in _SIM_DEVICES
                )
                if info is not None
            ),
            key=lambda ns: ns.name,
        )
    if not root.exists():
        return []
    namespaces: List[NVMeNamespaceInfo] = []
    for entry in sorted(os.listdir(root)):
        if classify_nvme_name(entry) in (KIND_NAMESPACE, KIND_ALIAS):
            info = read_namespace_info(entry, root)
            if info is not None:
                namespaces.append(info)
    return namespaces


def discover_subsystems(
    root: Path = SYS_NVM_SUBSYSTEM,
) -> List[NVMeSubsystemInfo]:
    """Discover NVMe subsystems (``nvme-subsysN`` groupings)."""
    if _SIM_DEVICES is not None or not root.exists():
        return []
    subsystems: List[NVMeSubsystemInfo] = []
    for entry in sorted(os.listdir(root)):
        if not entry.startswith("nvme-subsys"):
            continue
        info = read_subsystem_info(entry, root)
        if info is not None:
            subsystems.append(info)
    return subsystems


def available() -> bool:
    """True when NVMe discovery can run (sysfs present or simulation active)."""
    return _SIM_DEVICES is not None or SYS_CLASS_NVME.exists()


def _selftest() -> bool:
    """Run a basic self-test for this module (simulation based)."""
    sim = {
        "nvme0": {
            "model": "WDC WD SN770 1TB",
            "serial": "20234A805352",
            "firmware_rev": "111070WD",
            "transport": "pcie",
            "address": "0000:01:00.0",
            "cntlid": "1",
            "state": "live",
            "numa_node": "0",
            "queue_count": "64",
            "sqsize": "1023",
        },
        "nvme0n1": {
            "nsid": "1",
            "size": str(1024 * 1024 * 1024 // 512),
            "uuid": "00000000-0000-0000-0000-000000000001",
            "fmt_lba_size": "512",
        },
    }
    set_simulation(sim)
    try:
        ctrls = discover()
        assert len(ctrls) == 1, f"expected 1 controller, got {len(ctrls)}"
        ctrl = ctrls[0]
        assert ctrl.name == "nvme0"
        assert ctrl.transport == "pcie"
        assert ctrl.pci_address == "0000:01:00.0"
        assert ctrl.namespaces == ["nvme0n1"], ctrl.namespaces
        assert ctrl.sqsize == 1023
        assert ctrl.cntlid == 1

        ns_list = discover_namespaces()
        assert len(ns_list) == 1, f"expected 1 namespace, got {len(ns_list)}"
        ns = ns_list[0]
        assert ns.controller == "nvme0"
        assert ns.nsid == 1
        assert ns.size_bytes == 1024 ** 3, ns.size_bytes
        assert ns.fmt_lba_size == 512
        assert ns.device_path == "/dev/nvme0n1"

        assert discover_subsystems() == []

        assert classify_nvme_name("nvme0") == KIND_CONTROLLER
        assert classify_nvme_name("nvme0n1") == KIND_NAMESPACE
        assert classify_nvme_name("nvme0n1p2") == KIND_PARTITION
        assert classify_nvme_name("nvme0c1n1") == KIND_ALIAS
        assert classify_nvme_name("sda") is None
        assert controller_of("nvme3n42") == "nvme3"
        assert controller_of("sda") is None
        assert available() is True
        assert get_simulation() is sim
    finally:
        clear_simulation()
    assert get_simulation() is None
    print("selftest OK")
    return True


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(0 if _selftest() else 1)
