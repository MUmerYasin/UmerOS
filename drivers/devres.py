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

#!/usr/bin/env python3
"""
Device managed resources (devres) utilities for UmerOS.
Mimics the  kernel devm_* helpers: resources are attached to a Device and
automatically released when the device is unregistered.
"""

from typing import Callable, Any
from .device import Device


def devm_alloc(dev: Device, resource: Any, cleanup: Callable[[Any], None]) -> Any:
    """Attach *resource* to *dev* with a *cleanup* callable.

    The *resource* is stored in ``dev._dev_resources`` as a tuple
    ``(resource, cleanup)``. When the device is unregistered, all registered
    clean up functions are invoked in LIFO order.
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
