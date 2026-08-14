#!/usr/bin/env python3
"""
Device link utilities for UmerOS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Flags – match kernel definitions (simplified)
DL_FLAG_STATELESS = 0x1  # No driver presence enforcement on supplier
DL_FLAG_PM_RUNTIME = 0x2  # Runtime PM integration flag

@dataclass
class DeviceLink:
    """Represents a dependency link between two devices.

    *supplier*: the device that provides resources or ordering guarantees.
    *consumer*: the device that depends on the supplier.
    *flags*: bitmask controlling behaviour (stateless, PM runtime, etc.).
    """

    supplier: "Device"
    consumer: "Device"
    flags: int = 0

    def is_stateless(self) -> bool:
        """Return True if the link does not enforce driver presence on the supplier."""
        return bool(self.flags & DL_FLAG_STATELESS)

    def has_pm_runtime(self) -> bool:
        """Return True if runtime PM integration is requested for this link."""
        return bool(self.flags & DL_FLAG_PM_RUNTIME)

    def __repr__(self) -> str:
        flag_names = []
        if self.is_stateless():
            flag_names.append("STATELESS")
        if self.has_pm_runtime():
            flag_names.append("PM_RUNTIME")
        flags_str = "|".join(flag_names) if flag_names else "0"
        return (
            f"<DeviceLink supplier={self.supplier.name} "
            f"consumer={self.consumer.name} flags={flags_str}>"
        )
