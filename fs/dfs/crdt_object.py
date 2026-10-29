"""CRDT Distributed Data Object (DDO) — Last-Write-Wins with Hybrid Logical Clocks."""
from __future__ import annotations

import time
import threading
from typing import Any, Dict, Optional, Callable


class HybridLogicalClock:
    """Hybrid Logical Clock for distributed event ordering."""

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        self.physical = time.time()
        self.logical = 0

    def tick(self) -> tuple[float, int, str]:
        """Increment clock and return (physical, logical, node_id)."""
        now = time.time()
        if now > self.physical:
            self.physical = now
            self.logical = 0
        else:
            self.logical += 1
        return (self.physical, self.logical, self.node_id)

    def update(self, remote_physical: float, remote_logical: int) -> None:
        """Update clock based on remote event."""
        now = time.time()
        if now > self.physical and now > remote_physical:
            self.physical = now
            self.logical = 0
        elif self.physical == remote_physical:
            self.logical = max(self.logical, remote_logical) + 1
        elif remote_physical > self.physical:
            self.physical = remote_physical
            self.logical = remote_logical + 1
        else:
            self.logical += 1

    def compare(self, other_physical: float, other_logical: int, other_node: str) -> int:
        """Compare two HLC timestamps. Returns -1/0/1."""
        if self.physical != other_physical:
            return -1 if self.physical < other_physical else 1
        if self.logical != other_logical:
            return -1 if self.logical < other_logical else 1
        if self.node_id != other_node:
            return -1 if self.node_id < other_node else 1
        return 0


class LWWRegister:
    """Last-Write-Wins Register using HLC for conflict resolution."""

    def __init__(self, node_id: str, initial_value: Any = None) -> None:
        self.node_id = node_id
        self.clock = HybridLogicalClock(node_id)
        self._value = initial_value
        self._timestamp: tuple[float, int, str] = (0.0, 0, "")

    @property
    def value(self) -> Any:
        return self._value

    def set(self, value: Any) -> tuple[float, int, str]:
        """Set value and return HLC timestamp."""
        ts = self.clock.tick()
        self._value = value
        self._timestamp = ts
        return ts

    def merge(self, remote_value: Any, remote_ts: tuple[float, int, str]) -> bool:
        """Merge remote update. Returns True if applied."""
        remote_physical, remote_logical, remote_node = remote_ts
        local_physical, local_logical, local_node = self._timestamp
        # Compare remote against stored timestamp
        if local_physical == 0.0 and local_logical == 0 and local_node == "":
            # No local value set yet, accept remote
            self._value = remote_value
            self._timestamp = remote_ts
            self.clock.update(remote_physical, remote_logical)
            return True
        if remote_physical > local_physical:
            self._value = remote_value
            self._timestamp = remote_ts
            self.clock.update(remote_physical, remote_logical)
            return True
        if remote_physical == local_physical:
            if remote_logical > local_logical:
                self._value = remote_value
                self._timestamp = remote_ts
                self.clock.update(remote_physical, remote_logical)
                return True
            if remote_logical == local_logical and remote_node > local_node:
                self._value = remote_value
                self._timestamp = remote_ts
                self.clock.update(remote_physical, remote_logical)
                return True
        return False

    @property
    def timestamp(self) -> tuple[float, int, str]:
        return self._timestamp


class DistributedDataObject:
    """CRDT-backed distributed data object with reactive listeners."""

    def __init__(self, node_id: str, object_id: str = "default") -> None:
        self.node_id = node_id
        self.object_id = object_id
        self.clock = HybridLogicalClock(node_id)
        self._registers: Dict[str, LWWRegister] = {}
        self._listeners: List[Callable[[str, Any], None]] = []
        self._lock = threading.Lock()

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            reg = self._registers.get(key)
            return reg.value if reg is not None else default

    def set(self, key: str, value: Any) -> tuple[float, int, str]:
        with self._lock:
            if key not in self._registers:
                self._registers[key] = LWWRegister(self.node_id)
            reg = self._registers[key]
            ts = reg.set(value)
            self._notify(key, value)
            return ts

    def merge_remote(self, key: str, value: Any, timestamp: tuple[float, int, str]) -> bool:
        """Merge a remote update. Returns True if applied."""
        with self._lock:
            if key not in self._registers:
                self._registers[key] = LWWRegister(self.node_id)
            reg = self._registers[key]
            applied = reg.merge(value, timestamp)
            if applied:
                self._notify(key, value)
            return applied

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return {k: v.value for k, v in self._registers.items()}

    def get_timestamps(self) -> Dict[str, tuple]:
        with self._lock:
            return {k: v.timestamp for k, v in self._registers.items()}

    def add_listener(self, callback: Callable[[str, Any], None]) -> None:
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str, Any], None]) -> None:
        self._listeners = [l for l in self._listeners if l is not callback]

    def _notify(self, key: str, value: Any) -> None:
        for listener in self._listeners:
            try:
                listener(key, value)
            except Exception:
                pass

    def __repr__(self) -> str:
        return f"DistributedDataObject(id={self.object_id}, keys={list(self._registers.keys())})"