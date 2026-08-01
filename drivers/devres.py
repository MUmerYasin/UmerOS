#!/usr/bin/env python3
"""
Device‑managed resources (devres) utilities for UmerOS.
Mimics the Linux kernel devm_* helpers: resources are attached to a Device and
automatically released when the device is unregistered.
"""

from typing import Callable, Any
from .device import Device


def devm_alloc(dev: Device, resource: Any, cleanup: Callable[[Any], None]) -> Any:
    """Attach *resource* to *dev* with a *cleanup* callable.

    The *resource* is stored in ``dev._dev_resources`` as a tuple
    ``(resource, cleanup)``. When the device is unregistered, all registered
    clean‑up functions are invoked in LIFO order.
    """
    if not hasattr(dev, "_dev_resources"):
        dev._dev_resources = []
    dev._dev_resources.append((resource, cleanup))
    return resource


def devm_release_all(dev: Device) -> None:
    """Run all cleanup callbacks for resources attached to *dev*.

    This mirrors the kernel's ``devm_release_all`` which is called from the
    device's ``release`` method. It is safe to call multiple times – the list is
    cleared after execution.
    """
    resources = getattr(dev, "_dev_resources", [])
    while resources:
        res, cleanup = resources.pop()
        try:
            cleanup(res)
        except Exception as exc:
            print(f"[DEVRES] Cleanup error for {res}: {exc}")
