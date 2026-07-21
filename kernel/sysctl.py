"""
Umer OS Sysctl Runtime Parameters  [TODAY]
============================================
Runtime-tunable kernel parameters inspired by Linux kernel/sysctl.c.

    Linux reference: kernel/sysctl.c — provides a hierarchical namespace
    (kernel.panic_timeout, kernel.hung_task_timeout_secs, etc.) of runtime-
    tunable parameters exposed via /proc/sys/.  Writes are validated by
    type and range.

Design:
    - Parameters are stored as a nested dict ``{"kernel": {"panic_timeout": 5}}``.
    - Each parameter has metadata: type (int/str/bool), min, max, permissions.
    - ``sysctl.get("kernel.panic_timeout")`` and ``sysctl.set("kernel.panic_timeout", 10)``.
    - Invalid writes raise ``ValueError``.
    - Dot-separated key paths navigate the hierarchy.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple, Union

log = logging.getLogger("UmerOS.Sysctl")

# ── Parameter types ─────────────────────────────────────────────────────────────

TYPE_INT: str = "int"
TYPE_STR: str = "str"
TYPE_BOOL: str = "bool"

TypeVal = Union[int, str, bool]


# ── Sysctl Registry ─────────────────────────────────────────────────────────────

class SysctlRegistry:
    """Hierarchical runtime-tunable parameter store.

    Inspired by Linux ``/proc/sys/``: dot-separated paths navigate a
    nested dict.  Every parameter has metadata for type, range, and
    write-permission enforcement.

    Usage::

        sysctl = SysctlRegistry()
        sysctl.register("kernel.panic_timeout", 5,
                         ptype=TYPE_INT, min_val=0, max_val=300,
                         desc="Seconds before auto-reboot after panic")
        sysctl.register("kernel.hung_task_timeout", 120,
                         ptype=TYPE_INT, min_val=1, max_val=3600,
                         desc="Seconds before declaring a task hung")
        val = sysctl.get("kernel.panic_timeout")
        sysctl.set("kernel.panic_timeout", 10)
    """

    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}
        self._meta: Dict[str, dict] = {}
        log.debug("SysctlRegistry initialised.")

    # ── Registration ───────────────────────────────────────────────────────────

    def register(
        self,
        path: str,
        default: TypeVal,
        ptype: str = TYPE_INT,
        min_val: Optional[Union[int, float]] = None,
        max_val: Optional[Union[int, float]] = None,
        desc: str = "",
        writable: bool = True,
    ) -> None:
        """Register a tunable parameter.

        Args:
            path:     Dot-separated key path (e.g. ``"kernel.panic_timeout"``).
            default:  Default value.
            ptype:    One of TYPE_INT, TYPE_STR, TYPE_BOOL.
            min_val:  Minimum allowed value (for int/float).
            max_val:  Maximum allowed value (for int/float).
            desc:     Human-readable description.
            writable: Whether the parameter can be changed at runtime.

        Raises:
            ValueError: If the path is empty or ptype is unknown.
        """
        if not path or not path.replace(".", "").replace("_", "").isalnum():
            raise ValueError(f"Invalid sysctl path: {path!r}")
        if ptype not in (TYPE_INT, TYPE_STR, TYPE_BOOL):
            raise ValueError(f"Unknown sysctl type: {ptype!r}")

        # Set the value in the nested dict
        self._set_nested(path, default)

        # Store metadata
        self._meta[path] = {
            "type": ptype,
            "min": min_val,
            "max": max_val,
            "writable": writable,
            "desc": desc,
        }
        log.debug("Sysctl registered: %s = %s (%s)", path, default, ptype)

    # ── Get / Set ──────────────────────────────────────────────────────────────

    def get(self, path: str, default: Any = None) -> TypeVal:
        """Read a parameter value.

        Args:
            path:    Dot-separated key path.
            default: Returned if the path does not exist.

        Returns:
            The parameter value, or *default*.
        """
        return self._get_nested(path, default)

    def set(self, path: str, value: TypeVal) -> None:
        """Write a parameter value with validation.

        Args:
            path:  Dot-separated key path.
            value: New value.

        Raises:
            PermissionError: If the parameter is read-only.
            ValueError:      If the value fails type or range checks.
            KeyError:        If the path is not registered.
        """
        meta = self._meta.get(path)
        if meta is None:
            raise KeyError(f"Unregistered sysctl parameter: {path!r}")

        if not meta["writable"]:
            raise PermissionError(f"sysctl {path!r} is read-only.")

        # Type validation
        expected = meta["type"]
        if expected == TYPE_INT:
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"sysctl {path!r} requires int, got {type(value).__name__}")
            if meta["min"] is not None and value < meta["min"]:
                raise ValueError(f"sysctl {path!r} = {value} < min {meta['min']}")
            if meta["max"] is not None and value > meta["max"]:
                raise ValueError(f"sysctl {path!r} = {value} > max {meta['max']}")
        elif expected == TYPE_BOOL:
            if not isinstance(value, bool):
                raise ValueError(f"sysctl {path!r} requires bool, got {type(value).__name__}")
        elif expected == TYPE_STR:
            if not isinstance(value, str):
                raise ValueError(f"sysctl {path!r} requires str, got {type(value).__name__}")

        old = self._get_nested(path)
        self._set_nested(path, value)
        if old != value:
            log.info("Sysctl changed: %s = %s (was %s)", path, value, old)

    # ── Queries ─────────────────────────────────────────────────────────────────

    def exists(self, path: str) -> bool:
        """Check whether a parameter is registered.

        Returns:
            True if the path exists.
        """
        return path in self._meta

    def list_all(self, prefix: str = "") -> Dict[str, TypeVal]:
        """Return all parameters (optionally filtered by prefix).

        Returns:
            Dict mapping path → current value.
        """
        result = {}
        for path in self._meta:
            if path.startswith(prefix):
                result[path] = self._get_nested(path)
        return result

    def meta(self, path: str) -> Optional[dict]:
        """Return metadata for a parameter, or None if unregistered."""
        return self._meta.get(path)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_nested(self, path: str, default: Any = None) -> Any:
        """Navigate the dot-separated path through the nested dict."""
        keys = path.split(".")
        node = self._data
        for key in keys[:-1]:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        if isinstance(node, dict) and keys[-1] in node:
            return node[keys[-1]]
        return default

    def _set_nested(self, path: str, value: Any) -> None:
        """Set a value at the dot-separated path, creating dicts as needed."""
        keys = path.split(".")
        node = self._data
        for key in keys[:-1]:
            if key not in node:
                node[key] = {}
            node = node[key]
        node[keys[-1]] = value
