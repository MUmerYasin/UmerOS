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
UmerOS /media/usb - lsusb Wrapper & Device Control
====================================================

Thin wrapper around the ``lsusb`` utility
(``usbutils`` package).  Read-only commands
(``lsusb``, ``lsusb -t``, ``lsusb -v``) run
unprivileged; state-changing device-control
operations - (de)authorizing a device,
triggering its removal and resetting it - are
gated behind the zero-trust capability bridge
(``CAP_SYS_ADMIN``).

Device control operates directly on sysfs:

* ``set_authorized(name, False)`` - deauthorize
  the device (the kernel ignores it until it is
  authorized again); this is the safe, supported
  way to disable a plugged-in device.
* ``remove_device(name)`` - write ``1`` to the
  ``remove`` attribute, triggering an unplug.
* ``reset_device(name)`` - authorized-toggle
  reset: deauthorize, wait, re-authorize.  This
  is the standard sysfs-level USB device reset.

Pure Python (standard library only).

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

from .device import (
    SYS_BUS_USB_DEVICES,
    classify_usb_name,
    parse_lsusb,
    parse_lsusb_tree,
    parse_lsusb_verbose,
)

log = logging.getLogger("UmerOS.Media.USB.CLI")

LSUSB_BIN = "lsusb"
DEFAULT_TIMEOUT = 10.0
RESET_DELAY = 0.05

# Gate privileged USB device-control operations
# behind the zero-trust capability bridge
# (core/capability_gate).  Authorizing,
# removing and resetting devices requires the
# `sys.admin` capability when a
# CapabilityManager is wired (fail-closed);
# when no manager is wired the gate stays
# permissive (warning) so existing flows keep
# working.
try:
    from core.capability_gate import CAP_SYS_ADMIN, gate
except Exception:  # pragma: no cover - standalone fallback
    import sys
    _proj = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    # A failed first attempt may have cached an
    # unrelated "core" package in sys.modules;
    # drop it so the retry resolves against the
    # project root.
    sys.modules.pop("core", None)
    sys.modules.pop("core.capability_gate", None)
    from core.capability_gate import CAP_SYS_ADMIN, gate


class UsbCLIError(RuntimeError):
    """Raised when lsusb is missing, times out,
    fails, or a device-control write fails."""


def _run(
    args: List[str],
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """Run lsusb and return stdout (text mode)."""
    if shutil.which(LSUSB_BIN) is None:
        raise UsbCLIError(
            "lsusb is not installed or not on PATH "
            "(install the usbutils package)"
        )
    try:
        result = subprocess.run(
            [LSUSB_BIN] + list(args),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise UsbCLIError(
            f"lsusb timed out after {timeout}s"
        ) from exc
    except OSError as exc:
        raise UsbCLIError(
            f"lsusb could not be executed: {exc}"
        ) from exc
    if result.returncode != 0:
        raise UsbCLIError(
            "lsusb exited with code "
            f"{result.returncode}: "
            f"{result.stderr.strip()}"
        )
    return result.stdout


# ---------------------------------------------------------------------------
# Read-only lsusb commands
# ---------------------------------------------------------------------------

def list_devices() -> List[Dict[str, str]]:
    """List all USB devices (plain ``lsusb``,
    parsed)."""
    return parse_lsusb(_run([]))


def list_tree() -> List[Dict[str, str]]:
    """List the USB topology tree
    (``lsusb -t``, parsed)."""
    return parse_lsusb_tree(_run(["-t"]))


def verbose_device(
    bus: int,
    device: int,
) -> List[Dict[str, str]]:
    """Full descriptor dump for one device
    (``lsusb -v -s bus:dev``, parsed)."""
    selector = f"{bus:03d}:{device:03d}"
    return parse_lsusb_verbose(
        _run(["-v", "-s", selector])
    )


# ---------------------------------------------------------------------------
# Device control (state-changing, gated)
# ---------------------------------------------------------------------------

def _control_entry(
    name: str,
    root: Path = SYS_BUS_USB_DEVICES,
) -> Path:
    """Validate *name* and return its sysfs
    directory, raising :class:`UsbCLIError` for
    invalid names or a missing sysfs tree."""
    if classify_usb_name(name) is None:
        raise UsbCLIError(
            f"not a USB sysfs entry name: {name!r}"
        )
    entry = root / name
    if not entry.is_dir():
        raise UsbCLIError(
            f"no such USB device: {name!r} "
            f"(expected {entry})"
        )
    return entry


def _write_attr(
    path: Path,
    value: str,
) -> None:
    try:
        path.write_text(value, encoding="utf-8")
    except OSError as exc:
        raise UsbCLIError(
            f"cannot write {path}: {exc}"
        ) from exc


def set_authorized(
    name: str,
    authorized: bool,
    root: Path = SYS_BUS_USB_DEVICES,
) -> None:
    """(De)authorize the USB device *name*.

    A deauthorized device is ignored by the
    kernel until it is authorized again.
    Requires the ``sys.admin`` capability when
    a capability manager is wired.
    """
    gate.require(CAP_SYS_ADMIN)
    entry = _control_entry(name, root)
    _write_attr(entry / "authorized", "1" if authorized else "0")
    log.info("USB device %s authorized=%s", name, authorized)


def remove_device(
    name: str,
    root: Path = SYS_BUS_USB_DEVICES,
) -> None:
    """Trigger an unplug of the USB device
    *name* by writing ``1`` to its ``remove``
    sysfs attribute.

    Requires the ``sys.admin`` capability when
    a capability manager is wired.
    """
    gate.require(CAP_SYS_ADMIN)
    entry = _control_entry(name, root)
    _write_attr(entry / "remove", "1")
    log.info("USB device %s remove triggered", name)


def reset_device(
    name: str,
    root: Path = SYS_BUS_USB_DEVICES,
    delay: float = RESET_DELAY,
) -> None:
    """Reset the USB device *name* via the
    authorized-toggle sequence (deauthorize,
    wait *delay* seconds, re-authorize).

    Requires the ``sys.admin`` capability when
    a capability manager is wired.
    """
    gate.require(CAP_SYS_ADMIN)
    entry = _control_entry(name, root)
    _write_attr(entry / "authorized", "0")
    if delay > 0:
        time.sleep(delay)
    _write_attr(entry / "authorized", "1")
    log.info("USB device %s reset", name)


def _selftest() -> bool:
    """Run a basic self-test for this module."""
    # Parsing through the wrapper's own imports
    parsed = parse_lsusb(
        "Bus 002 Device 004: ID 0781:5581 "
        "SanDisk Corp. Ultra Fit"
    )
    assert parsed[0]["vid"] == "0781", parsed

    print("selftest OK")
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
