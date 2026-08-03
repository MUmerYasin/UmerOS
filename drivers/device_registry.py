#!/usr/bin/env python3
"""
Umer OS Device Registry – core registration helpers used by the driver model.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from .device import Device

# Global registry mapping a unique device identifier to the Device instance
DEVICE_REGISTRY: Dict[str, Device] = {}


def device_register(dev: Device) -> None:
    """Register a Device with the global registry.

    * Assigns ``dev.dev_id`` as the key (defaults to ``dev.name``).
    * Raises ``ValueError`` if the identifier is already present.
    """
    dev_id = getattr(dev, "dev_id", dev.name)
    if dev_id in DEVICE_REGISTRY:
        raise ValueError(f"Device id '{dev_id}' is already registered")
    DEVICE_REGISTRY[dev_id] = dev
    # Optionally, you could expose the device to the bus here, but the bus
    # registration is performed by the Device constructor already.


def device_unregister(dev: Device) -> None:
    """Unregister a Device from the global registry and trigger its release hook.

    The function removes the device from ``DEVICE_REGISTRY`` and then calls the
    device's ``release`` method so that any device‑managed resources are cleaned
    up.
    """
    dev_id = getattr(dev, "dev_id", dev.name)
    if dev_id not in DEVICE_REGISTRY:
        raise KeyError(f"Device id '{dev_id}' not found in registry")
    # Call the release hook before removal – mirrors Linux's ``release``
    dev.release()
    del DEVICE_REGISTRY[dev_id]


def get_device(dev_id: str) -> Optional[Device]:
    """Retrieve a registered device by its identifier, or ``None`` if missing."""
    return DEVICE_REGISTRY.get(dev_id)
