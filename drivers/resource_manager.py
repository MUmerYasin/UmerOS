#!/usr/bin/env python3
"""
Umer OS Resource Manager

Provides a simple managed resource system analogous to devres.
Drivers can register resources with cleanup callbacks; when a device is
unbound, all registered resources are released automatically.
"""

from typing import Callable, Any, List, Tuple

class ResourceManager:
    """Track resources and their cleanup functions.

    Example usage in a driver::
        res = allocate_memory(...)
        device.resources.add(res, lambda r: free_memory(r))
    When the device is unbound, ``release_all`` is called, invoking all
    cleanup callbacks.
    """

    def __init__(self) -> None:
        self._resources: List[Tuple[Any, Callable[[Any], None]]] = []

    def add(self, resource: Any, cleanup: Callable[[Any], None]) -> None:
        """Register a *resource* with a *cleanup* callable.

        The *cleanup* function receives the *resource* as its sole argument.
        """
        self._resources.append((resource, cleanup))

    def release_all(self) -> None:
        """Execute cleanup for all registered resources.

        Resources are released in reverse order of registration, mirroring
        devres behaviour.
        """
        while self._resources:
            resource, cleanup = self._resources.pop()
            try:
                cleanup(resource)
            except Exception as exc:
                print(f"[RES-MGR] Cleanup error for {resource}: {exc}")

    def __repr__(self) -> str:
        return f"<ResourceManager {len(self._resources)} pending>"
