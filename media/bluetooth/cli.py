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
UmerOS /media/bluetooth - bluetoothctl Wrapper
====================================================

Thin wrapper around the ``bluetoothctl`` utility
(``https://git.kernel.org/pub/scm/bluetooth/bluez.git``).
Read-only commands (``list``, ``show``, ``devices``,
``info``, ``paired-devices``) run unprivileged;
state-changing commands (power, scan, pair, trust,
remove, connect, disconnect) are gated behind the
zero-trust capability bridge (``CAP_NET_ADMIN`` -
a Bluetooth adapter is a network-class device).

The wrapper parses ``bluetoothctl``'s text output
and raises :class:`BluetoothctlError` for a missing
binary, timeouts and non-zero exits.

Pure Python (standard library only).

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Media.Bluetooth.CLI")

BLUETOOTHCTL_BIN = "bluetoothctl"
DEFAULT_TIMEOUT = 10.0

# Gate privileged Bluetooth admin commands behind the
# zero-trust capability bridge (core/capability_gate).
# Power / scan / pair / trust / remove / connect /
# disconnect reconfigure a network-class device and
# require the `net.admin` capability when a
# CapabilityManager is wired (fail-closed); when no
# manager is wired the gate stays permissive
# (warning) so existing flows keep working.
try:
    from core.capability_gate import CAP_NET_ADMIN, gate
except Exception:  # pragma: no cover - standalone fallback
    import sys
    _proj = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    # A failed first attempt may have cached an unrelated "core"
    # package in sys.modules; drop it so the retry resolves
    # against the project root.
    sys.modules.pop("core", None)
    sys.modules.pop("core.capability_gate", None)
    from core.capability_gate import CAP_NET_ADMIN, gate


class BluetoothctlError(RuntimeError):
    """Raised when bluetoothctl is missing, times out or fails."""


def _run(args: List[str], timeout: float = DEFAULT_TIMEOUT) -> str:
    """Run bluetoothctl and return stdout (text mode)."""
    if shutil.which(BLUETOOTHCTL_BIN) is None:
        raise BluetoothctlError(
            "bluetoothctl is not installed or not on PATH"
        )
    command = [BLUETOOTHCTL_BIN] + list(args)
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise BluetoothctlError(
            f"bluetoothctl timed out after {timeout}s: "
            f"{' '.join(command)}"
        ) from exc
    except OSError as exc:
        raise BluetoothctlError(
            f"failed to execute bluetoothctl: {exc}"
        ) from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise BluetoothctlError(
            f"bluetoothctl failed (exit {result.returncode}): {detail}"
        )
    return result.stdout


# ---------------------------------------------------------------------------
# Output parsing
# ---------------------------------------------------------------------------


def parse_controller_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse ``Controller <addr> <name> [default]``."""
    parts = line.split(None, 2)
    if len(parts) < 2 or parts[0] != "Controller":
        return None
    remainder = parts[2] if len(parts) > 2 else ""
    default = "[default]" in remainder
    name = remainder.replace("[default]", "").strip()
    return {
        "address": parts[1].strip(),
        "name": name or None,
        "default": default,
    }


def parse_device_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse ``Device <addr> <name>``."""
    parts = line.split(None, 2)
    if len(parts) < 2 or parts[0] != "Device":
        return None
    name = parts[2].strip() if len(parts) > 2 else ""
    return {
        "address": parts[1].strip(),
        "name": name or None,
    }


def parse_list_output(text: str) -> List[Dict[str, Any]]:
    """Parse ``bluetoothctl list`` output."""
    controllers: List[Dict[str, Any]] = []
    for line in text.splitlines():
        parsed = parse_controller_line(line.strip())
        if parsed is not None:
            controllers.append(parsed)
    return controllers


def parse_devices_output(text: str) -> List[Dict[str, Any]]:
    """Parse ``bluetoothctl devices`` output."""
    devices: List[Dict[str, Any]] = []
    for line in text.splitlines():
        parsed = parse_device_line(line.strip())
        if parsed is not None:
            devices.append(parsed)
    return devices


def parse_show_output(text: str) -> Dict[str, Any]:
    """Parse ``bluetoothctl show [dev]`` output.

    Returns a dict with the header fields
    (``address``, ``name``, ``default``) plus the
    indented ``Key value`` properties.
    """
    result: Dict[str, Any] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        header = parse_controller_line(stripped)
        if header is not None:
            result["address"] = header["address"]
            result["name"] = header["name"]
            result["default"] = header["default"]
            continue
        if stripped.startswith("["):
            # Agent / Manager banners such as
            # "[NEW] Controller ..." - skip.
            continue
        key_value = stripped.split(None, 1)
        if len(key_value) == 2:
            result[key_value[0].strip()] = key_value[1].strip()
        elif len(key_value) == 1:
            result[key_value[0].strip()] = None
    return result


def parse_info_output(text: str) -> Dict[str, Any]:
    """Parse ``bluetoothctl info <dev>`` output.

    Returns a dict with the header fields
    (``address``, ``name``) plus the indented
    ``Key value`` properties.
    """
    result: Dict[str, Any] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        header = parse_device_line(stripped)
        if header is not None:
            result["address"] = header["address"]
            result["name"] = header["name"]
            continue
        if stripped.startswith("["):
            continue
        key_value = stripped.split(None, 1)
        if len(key_value) == 2:
            result[key_value[0].strip()] = key_value[1].strip()
        elif len(key_value) == 1:
            result[key_value[0].strip()] = None
    return result


# ---------------------------------------------------------------------------
# Read-only commands
# ---------------------------------------------------------------------------


def list_controllers(timeout: float = DEFAULT_TIMEOUT) -> List[Dict[str, Any]]:
    """List Bluetooth controllers (``bluetoothctl list``)."""
    return parse_list_output(_run(["list"], timeout=timeout))


def show(
    device: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """Show controller or device info (``bluetoothctl show [dev]``)."""
    args = ["show"]
    if device is not None:
        args.append(device)
    return parse_show_output(_run(args, timeout=timeout))


def devices(timeout: float = DEFAULT_TIMEOUT) -> List[Dict[str, Any]]:
    """List known remote devices (``bluetoothctl devices``)."""
    return parse_devices_output(_run(["devices"], timeout=timeout))


def info(device: str, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """Show device info (``bluetoothctl info <dev>``)."""
    return parse_info_output(_run(["info", device], timeout=timeout))


def paired_devices(timeout: float = DEFAULT_TIMEOUT) -> List[Dict[str, Any]]:
    """List paired devices (``bluetoothctl paired-devices``)."""
    return parse_devices_output(
        _run(["paired-devices"], timeout=timeout)
    )


# ---------------------------------------------------------------------------
# Privileged admin commands (gated)
# ---------------------------------------------------------------------------


def power(
    on: bool = True, timeout: float = DEFAULT_TIMEOUT
) -> str:
    """Power a controller on/off (``bluetoothctl power on|off``).

    Requires the ``net.admin`` capability when the gate
    is enforcing.
    """
    gate.require(CAP_NET_ADMIN)
    return _run(["power", "on" if on else "off"], timeout=timeout)


def scan(
    on: bool = True, timeout: float = DEFAULT_TIMEOUT
) -> str:
    """Start/stop discovery (``bluetoothctl scan on|off``).

    Requires the ``net.admin`` capability when the gate
    is enforcing.
    """
    gate.require(CAP_NET_ADMIN)
    return _run(["scan", "on" if on else "off"], timeout=timeout)


def pair(device: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Pair with a device (``bluetoothctl pair <dev>``).

    Requires the ``net.admin`` capability when the gate
    is enforcing.
    """
    gate.require(CAP_NET_ADMIN)
    return _run(["pair", device], timeout=timeout)


def trust(device: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Trust a device (``bluetoothctl trust <dev>``).

    Requires the ``net.admin`` capability when the gate
    is enforcing.
    """
    gate.require(CAP_NET_ADMIN)
    return _run(["trust", device], timeout=timeout)


def untrust(device: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Remove trust from a device (``bluetoothctl untrust <dev>``).

    Requires the ``net.admin`` capability when the gate
    is enforcing.
    """
    gate.require(CAP_NET_ADMIN)
    return _run(["untrust", device], timeout=timeout)


def remove(device: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Remove a device (``bluetoothctl remove <dev>``).

    Requires the ``net.admin`` capability when the gate
    is enforcing.
    """
    gate.require(CAP_NET_ADMIN)
    return _run(["remove", device], timeout=timeout)


def connect(device: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Connect to a device (``bluetoothctl connect <dev>``).

    Requires the ``net.admin`` capability when the gate
    is enforcing.
    """
    gate.require(CAP_NET_ADMIN)
    return _run(["connect", device], timeout=timeout)


def disconnect(device: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Disconnect from a device (``bluetoothctl disconnect <dev>``).

    Requires the ``net.admin`` capability when the gate
    is enforcing.
    """
    gate.require(CAP_NET_ADMIN)
    return _run(["disconnect", device], timeout=timeout)


def _selftest() -> bool:
    """Run a basic self-test for this module (no bluetoothctl needed)."""
    assert BLUETOOTHCTL_BIN == "bluetoothctl"
    assert issubclass(BluetoothctlError, RuntimeError)

    # Controller / device line parsing
    ctrl = parse_controller_line(
        "Controller 00:1A:7D:DA:71:13 MyHost [default]"
    )
    assert ctrl == {
        "address": "00:1A:7D:DA:71:13",
        "name": "MyHost",
        "default": True,
    }
    ctrl2 = parse_controller_line("Controller A4:50:46:99:11:22 Second")
    assert ctrl2 == {
        "address": "A4:50:46:99:11:22",
        "name": "Second",
        "default": False,
    }
    assert parse_controller_line("Device 00:11:22:33:44:55 Phone") is None
    assert parse_controller_line("") is None

    dev = parse_device_line("Device 00:11:22:33:44:55 MyPhone")
    assert dev == {
        "address": "00:11:22:33:44:55",
        "name": "MyPhone",
    }
    assert parse_device_line("Controller 00:1A:7D:DA:71:13") is None

    listing = parse_list_output(
        "Controller 00:1A:7D:DA:71:13 MyHost [default]\n"
        "Controller A4:50:46:99:11:22 Second\n"
    )
    assert len(listing) == 2
    assert listing[0]["default"] is True
    assert listing[1]["default"] is False

    devs = parse_devices_output(
        "Device 00:11:22:33:44:55 MyPhone\n"
        "Device 11:22:33:44:55:66 Headphones\n"
    )
    assert len(devs) == 2
    assert devs[1]["name"] == "Headphones"

    show_out = parse_show_output(
        "Controller 00:1A:7D:DA:71:13 MyHost [default]\n"
        "\tPowered yes\n"
        "\tDiscoverable no\n"
        "\tUUIDs 0000110a-0000-1000-8000-00805f9b34fb\n"
        "\tModalias usb:v1D6Bp0246d0539\n"
    )
    assert show_out["address"] == "00:1A:7D:DA:71:13"
    assert show_out["name"] == "MyHost"
    assert show_out["Powered"] == "yes"
    assert show_out["Discoverable"] == "no"
    assert (
        show_out["UUIDs"]
        == "0000110a-0000-1000-8000-00805f9b34fb"
    )
    assert show_out["Modalias"] == "usb:v1D6Bp0246d0539"

    info_out = parse_info_output(
        "Device 00:11:22:33:44:55 MyPhone\n"
        "\tPaired yes\n"
        "\tTrusted yes\n"
        "\tConnected no\n"
        "\tUUIDs 0000110a-0000-1000-8000-00805f9b34fb\n"
    )
    assert info_out["address"] == "00:11:22:33:44:55"
    assert info_out["Paired"] == "yes"
    assert info_out["Connected"] == "no"

    # Missing binary path (or real run if bluetoothctl exists)
    if shutil.which(BLUETOOTHCTL_BIN) is None:
        for call in (
            lambda: list_controllers(),
            lambda: show(),
            lambda: devices(),
            lambda: info("00:11:22:33:44:55"),
            lambda: paired_devices(),
        ):
            try:
                call()
            except BluetoothctlError:
                pass
            else:
                raise AssertionError(
                    "missing bluetoothctl must raise BluetoothctlError"
                )

    # Gating: strict gate must deny before any subprocess work.
    state = gate.snapshot()
    gate.set_strict(True)
    try:
        for call in (
            lambda: power(True),
            lambda: scan(True),
            lambda: pair("00:11:22:33:44:55"),
            lambda: trust("00:11:22:33:44:55"),
            lambda: untrust("00:11:22:33:44:55"),
            lambda: remove("00:11:22:33:44:55"),
            lambda: connect("00:11:22:33:44:55"),
            lambda: disconnect("00:11:22:33:44:55"),
        ):
            try:
                call()
            except PermissionError:
                pass
            else:
                raise AssertionError(
                    "strict gate must deny privileged operations"
                )
    finally:
        gate.restore(state)

    print("selftest OK")
    return True


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(0 if _selftest() else 1)
