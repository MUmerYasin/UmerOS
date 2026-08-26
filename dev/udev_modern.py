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
UmerOS Modern Udev — next-generation userspace device management.

Techniques adopted from systemd-udevd / modern mainline practice that
were previously absent from UmerOS:

  UeventNetlinkMonitor   netlink-style uevent stream with a processing
                         queue, coalescing (debounce) and settle support.
  DeviceTagRegistry      udev properties and tags per device node:
                         TAGS=="uaccess" seat ACLs, ID_INPUT_* classes.
  PredictableNamingPolicy persistent by-id / by-path aliases plus
                         predictable network interface naming.
  SystemdDeviceUnits     on-demand .device unit synthesis for init.
  MknodPolicy            container-oriented device allowlist enforced at
                         create time (cgroup-v2 BPF style).
"""

from __future__ import annotations

import logging
import re
import time
import uuid as uuid_mod
from collections import deque
from typing import Any, Deque, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.UdevModern")


class Uevent:
    """One kernel uevent message (add/change/remove/bind)."""

    __slots__ = ("action", "devpath", "subsystem", "seqnum", "ts")

    def __init__(self, action: str, devpath: str, subsystem: str):
        self.action = action
        self.devpath = devpath
        self.subsystem = subsystem
        self.seqnum = 0
        self.ts = time.time()

    def to_json(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "devpath": self.devpath,
            "subsystem": self.subsystem,
            "seqnum": self.seqnum,
        }

    def __repr__(self) -> str:
        return f"UEVENT[{self.seqnum}] {self.action} @{self.devpath} ({self.subsystem})"


class UeventNetlinkMonitor:
    """Netlink uevent consumer with queue, coalescing and settle.

    Modern kernels multicast uevents over NETLINK_KOBJECT_UEVENT;
    systemd-udevd serialises them through one worker with a rule engine.
    This class models that pipeline: events are queued in order,
    duplicates for the same devpath are coalesced within the debounce
    window, and `settle()` blocks until the queue drains.
    """

    DEBOUNCE_SECONDS = 0.05
    MAX_QUEUE = 512

    def __init__(self) -> None:
        self._queue: Deque[Uevent] = deque()
        self._last_seq = 0
        self._processed: List[Dict[str, Any]] = []
        self._listeners = 0

    # ── socket lifecycle ──────────────────────────────────────────────
    def attach(self) -> int:
        """Subscribe a netlink group listener; returns listener id."""
        self._listeners += 1
        return self._listeners

    # ── ingestion ─────────────────────────────────────────────────────
    def feed(self, action: str, devpath: str, subsystem: str) -> Optional[Uevent]:
        if len(self._queue) >= self.MAX_QUEUE:
            dropped = self._queue.popleft()
            log.warning("uevent queue overflow, dropped %r", dropped)
        evt = Uevent(action, devpath, subsystem)
        self._last_seq += 1
        evt.seqnum = self._last_seq

        for queued in self._queue:
            if (queued.devpath == devpath
                    and (evt.ts - queued.ts) < self.DEBOUNCE_SECONDS):
                queued.action = action
                queued.ts = evt.ts
                log.debug("coalesced uevent for %s", devpath)
                return None
        self._queue.append(evt)
        return evt

    # ── processing ────────────────────────────────────────────────────
    def process_one(self) -> Optional[Dict[str, Any]]:
        if not self._queue:
            return None
        evt = self._queue.popleft()
        record = {**evt.to_json(), "processed_at": time.time()}
        self._processed.append(record)
        mgr = DeviceManager.get_instance()
        node = mgr.get_node(evt.devpath)
        record["node_exists"] = node is not None
        return record

    def drain(self, limit: int = 64) -> List[Dict[str, Any]]:
        out = []
        while self._queue and len(out) < limit:
            rec = self.process_one()
            if rec:
                out.append(rec)
        return out

    def settle(self, timeout: float = 2.0) -> bool:
        deadline = time.time() + timeout
        while self._queue and time.time() < deadline:
            self.process_one()
        return not self._queue

    def get_info(self) -> Dict[str, Any]:
        return {
            "listeners": self._listeners,
            "queued": len(self._queue),
            "processed": len(self._processed),
            "last_seq": self._last_seq,
        }


class DeviceTagRegistry:
    """udev properties & tags per device node.

    Tags drive modern desktop policy:
      'uaccess'           — logind grants the active seat user an ACL
      'seat'              — device belongs to a logind seat
      'ID_INPUT_KEYBOARD' etc — libinput classification hints
    """

    SEAT_TAGS = ("uaccess", "seat", "master-of-seat")
    INPUT_TAGS = ("ID_INPUT", "ID_INPUT_KEYBOARD", "ID_INPUT_MOUSE", "ID_INPUT_JOYSTICK")

    def __init__(self) -> None:
        self._props: Dict[str, Dict[str, str]] = {}
        self._tags: Dict[str, set] = {}

    def set_property(self, devpath: str, key: str, value: str) -> None:
        self._props.setdefault(devpath, {})[key] = value

    def add_tag(self, devpath: str, tag: str) -> None:
        self._tags.setdefault(devpath, set()).add(tag)

    def tag_input_device(self, devpath: str, kinds: tuple = ("keyboard",)) -> None:
        self.add_tag(devpath, "seat")
        self.add_tag(devpath, "uaccess")
        self.set_property(devpath, "ID_INPUT", "1")
        for kind in kinds:
            self.set_property(devpath, f"ID_INPUT_{kind.upper()}", "1")
            self.add_tag(devpath, f"ID_INPUT_{kind.upper()}")

    def grant_uaccess(self, devpath: str) -> bool:
        if devpath not in self._tags:
            return False
        self.add_tag(devpath, "uaccess")
        return True

    def query(self, devpath: str) -> Dict[str, Any]:
        return {
            "properties": dict(self._props.get(devpath, {})),
            "tags": sorted(self._tags.get(devpath, set())),
        }

    def devices_with_tag(self, tag: str) -> List[str]:
        return sorted(p for p, t in self._tags.items() if tag in t)

    def get_info(self) -> Dict[str, Any]:
        return {"tagged_devices": len(self._tags), "property_devices": len(self._props)}


class PredictableNamingPolicy:
    """Persistent aliases + predictable interface names.

    - Persistent disk links under /dev/disk/by-id|by-path|by-uuid derived
      from hardware identity, immune to probe order.
    - Predictable NIC names (enp3s0f0 style): firmware/topology based so
      enumeration races never rename ports across reboots.
    """

    DISK_BY_DIR = "/dev/disk"

    @staticmethod
    def disk_by_id(model: str, serial: str) -> str:
        slug = f"{model}_{serial}".lower().replace(" ", "_")
        return f"{PredictableNamingPolicy.DISK_BY_DIR}/by-id/{slug}"

    @staticmethod
    def disk_by_path(pci_slot: str, port: int) -> str:
        return f"{PredictableNamingPolicy.DISK_BY_DIR}/by-path/pci-{pci_slot}-scsi-0:0:{port}:0"

    @staticmethod
    def disk_by_uuid(fs_uuid: Optional[str] = None) -> str:
        fs_uuid = fs_uuid or str(uuid_mod.uuid4())
        return f"{PredictableNamingPolicy.DISK_BY_DIR}/by-uuid/{fs_uuid}"

    @staticmethod
    def predictable_nic(pci_domain: int, bus: int, slot: int, func: int, port: int = 0) -> str:
        base = f"enp{bus}s{slot}f{func}"
        return base if port == 0 else f"{base}d{port}"

    @staticmethod
    def alias_disk(devpath: str, model: str, serial: str, pci_slot: str, port: int) -> Dict[str, str]:
        mgr = DeviceManager.get_instance()
        aliases = {
            "by-id": PredictableNamingPolicy.disk_by_id(model, serial),
            "by-path": PredictableNamingPolicy.disk_by_path(pci_slot, port),
        }
        created = {}
        for kind, link_path in aliases.items():
            ok = mgr.create_node(DeviceNode(
                name=link_path.rsplit("/", 1)[-1],
                path=link_path,
                dev_type=DeviceType.SYMLINK,
                symlink_target=devpath,
                description=f"Persistent disk alias ({kind})",
            ))
            created[kind] = {"path": link_path, "created": ok}
        return created


class SystemdDeviceUnits:
    """Synthesises systemd .device unit state from the registry.

    Every registered node maps to `dev-<escaped>.device`; dependency
    ordering (WANTS after sys-subsystem paths) mirrors modern init.
    """

    @staticmethod
    def escape_unit(devpath: str) -> str:
        escaped = devpath.lstrip("/")
        escaped = re.sub(r"([^\w.]+)", lambda m: "\\x%02x" % ord(m.group(1)[0]), escaped)
        return f"dev-{escaped}.device"

    @staticmethod
    def unit_state(devpath: str) -> Dict[str, Any]:
        mgr = DeviceManager.get_instance()
        exists = mgr.get_node(devpath) is not None
        return {
            "unit": SystemdDeviceUnits.escape_unit(devpath),
            "load": "loaded" if exists else "not-found",
            "active": "active" if exists else "inactive",
            "sub": "plugged" if exists else "dead",
        }

    @staticmethod
    def list_units(limit: int = 20) -> List[Dict[str, Any]]:
        mgr = DeviceManager.get_instance()
        return [SystemdDeviceUnits.unit_state(n.path) for n in mgr.list_all()[:limit]]


class MknodPolicy:
    """Container-oriented device allowlist (cgroup-v2/BPF style).

    Rules are evaluated newest-first; unmatched requests fall through to
    the default policy ('deny' for sandboxes). Each rule covers a type
    char ('c','b','p','a') and optional major:minor ranges.
    """

    def __init__(self, default: str = "deny"):
        self.default = default
        self._rules: List[Dict[str, Any]] = []

    def allow(self, type_char: str, major: Optional[int] = None,
              minor: Optional[int] = None) -> None:
        self._rules.append({"allow": True, "type": type_char, "major": major, "minor": minor})

    def deny(self, type_char: str, major: Optional[int] = None,
             minor: Optional[int] = None) -> None:
        self._rules.append({"allow": False, "type": type_char, "major": major, "minor": minor})

    def evaluate(self, type_char: str, major: int, minor: int) -> Dict[str, Any]:
        wildcard_match = None
        for rule in reversed(self._rules):
            if rule["type"] not in ("a", type_char):
                continue
            if rule["major"] is not None and rule["major"] != major:
                continue
            if rule["minor"] is not None and rule["minor"] != minor:
                continue
            if rule["type"] == "a":
                if wildcard_match is None:
                    wildcard_match = rule
                continue
            return {"verdict": "allow" if rule["allow"] else "deny",
                    "matched_rule": rule, "default": False}
        if wildcard_match is not None:
            return {"verdict": "allow" if wildcard_match["allow"] else "deny",
                    "matched_rule": wildcard_match, "default": False}
        return {"verdict": self.default, "matched_rule": None, "default": True}

    def sandbox_profile(self) -> None:
        """Typical container profile: stdio + tty + null-family only."""
        self._rules.clear()
        self.allow("c", 5, 0)          # /dev/tty
        self.allow("c", 5, 1)          # /dev/console
        self.allow("c", 1, 3)          # null
        self.allow("c", 1, 5)          # zero
        self.allow("c", 1, 7)          # full
        self.allow("c", 1, 8)          # random
        self.allow("c", 1, 9)          # urandom
        self.deny("a")

    def get_info(self) -> Dict[str, Any]:
        return {"rules": len(self._rules), "default": self.default}
