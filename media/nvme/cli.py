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
UmerOS /media/nvme - nvme-cli Wrapper
=======================================

Thin wrapper around the ``nvme-cli`` utility
(``https://github.com/linux-nvme/nvme-cli``).  Read-only
commands (``nvme list``, ``id-ctrl``, ``id-ns``,
``smart-log``) run unprivileged; state-changing admin
commands (self-test start, controller / subsystem reset,
firmware download and commit) are gated behind the
zero-trust capability bridge (``CAP_SYS_ADMIN``).

The wrapper prefers JSON output and raises
:class:`NvmeCLIError` for a missing binary, timeouts,
non-zero exits and malformed JSON.

Pure Python (standard library only).

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Media.NVMe.CLI")

NVME_BIN = "nvme"
DEFAULT_TIMEOUT = 10.0

# Gate privileged NVMe admin commands behind the zero-trust
# capability bridge (core/capability_gate).  Controller /
# subsystem resets and firmware operations require the
# `sys.admin` capability when a CapabilityManager is wired
# (fail-closed); when no manager is wired the gate stays
# permissive (warning) so existing flows keep working.
try:
    from core.capability_gate import CAP_SYS_ADMIN, gate
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
    from core.capability_gate import CAP_SYS_ADMIN, gate


class NvmeCLIError(RuntimeError):
    """Raised when nvme-cli is missing, times out, fails or emits bad JSON."""


def _build_args(args: List[str], json_output: bool) -> List[str]:
    command = [NVME_BIN] + list(args)
    if json_output:
        command.append("--output-format=json")
    return command


def _run(args: List[str], timeout: float = DEFAULT_TIMEOUT) -> str:
    """Run nvme-cli and return stdout (text mode)."""
    if shutil.which(NVME_BIN) is None:
        raise NvmeCLIError(
            "nvme-cli is not installed or not on PATH"
        )
    command = _build_args(args, json_output=False)
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise NvmeCLIError(
            f"nvme-cli timed out after {timeout}s: {' '.join(command)}"
        ) from exc
    except OSError as exc:
        raise NvmeCLIError(f"failed to execute nvme-cli: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise NvmeCLIError(
            f"nvme-cli failed (exit {result.returncode}): {detail}"
        )
    return result.stdout


def _run_json(
    args: List[str], timeout: float = DEFAULT_TIMEOUT
) -> Any:
    """Run nvme-cli with JSON output and parse the result."""
    if shutil.which(NVME_BIN) is None:
        raise NvmeCLIError(
            "nvme-cli is not installed or not on PATH"
        )
    command = _build_args(args, json_output=True)
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise NvmeCLIError(
            f"nvme-cli timed out after {timeout}s: {' '.join(command)}"
        ) from exc
    except OSError as exc:
        raise NvmeCLIError(f"failed to execute nvme-cli: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise NvmeCLIError(
            f"nvme-cli failed (exit {result.returncode}): {detail}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise NvmeCLIError(
            f"nvme-cli returned malformed JSON: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Read-only commands
# ---------------------------------------------------------------------------


def list_devices() -> List[Dict[str, Any]]:
    """List NVMe devices (``nvme list``)."""
    payload = _run_json(["list"])
    devices = payload.get("devices", []) if isinstance(payload, dict) else []
    return [_normalize_device(device) for device in devices]


def _normalize_device(device: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a ``nvme list`` entry to lowercase keys."""
    normalized: Dict[str, Any] = {}
    for key, value in device.items():
        normalized[str(key).lower()] = value
    return normalized


def identify_controller(
    device: str, timeout: float = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    """Identify controller data as JSON (``nvme id-ctrl <dev>``)."""
    return _run_json(["id-ctrl", device], timeout=timeout)


def identify_namespace(
    device: str,
    nsid: Optional[int] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """Identify namespace data as JSON (``nvme id-ns <dev> [-n NSID]``)."""
    args = ["id-ns", device]
    if nsid is not None:
        args += ["-n", str(nsid)]
    return _run_json(args, timeout=timeout)


def smart_log(
    device: str,
    namespace: Optional[int] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """SMART/Health log as JSON (``nvme smart-log <dev> [-n NSID]``)."""
    args = ["smart-log", device]
    if namespace is not None:
        args += ["-n", str(namespace)]
    return _run_json(args, timeout=timeout)


def self_test_log(
    device: str, timeout: float = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    """Device self-test log as JSON (``nvme device-self-test <dev>``)."""
    return _run_json(["device-self-test", device], timeout=timeout)


def get_log(
    device: str,
    log_id: int,
    log_len: int = 512,
    timeout: float = DEFAULT_TIMEOUT,
) -> bytes:
    """Fetch a raw log page in binary (``nvme get-log -b``)."""
    if shutil.which(NVME_BIN) is None:
        raise NvmeCLIError(
            "nvme-cli is not installed or not on PATH"
        )
    command = [
        NVME_BIN,
        "get-log",
        device,
        f"--log-id={log_id}",
        f"--log-len={log_len}",
        "--output-format=binary",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise NvmeCLIError(
            f"nvme-cli timed out after {timeout}s: {' '.join(command)}"
        ) from exc
    except OSError as exc:
        raise NvmeCLIError(f"failed to execute nvme-cli: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or b"").decode(
            "utf-8", errors="replace"
        ).strip()
        raise NvmeCLIError(
            f"nvme-cli failed (exit {result.returncode}): {detail}"
        )
    return result.stdout


# ---------------------------------------------------------------------------
# Privileged admin commands (gated)
# ---------------------------------------------------------------------------


def self_test_start(
    device: str,
    test: str = "short",
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """Start a device self-test (``nvme device-self-test --start``).

    Args:
        device: Device path (e.g. ``/dev/nvme0``).
        test:   ``"short"`` or ``"long"``.

    Requires the ``sys.admin`` capability when the gate
    is enforcing.  Older nvme-cli (< 2.0) exposes the same
    operation as ``nvme self-test start``.
    """
    gate.require(CAP_SYS_ADMIN)
    if test not in ("short", "long"):
        raise ValueError('test must be "short" or "long"')
    return _run(
        ["device-self-test", device, "--start", f"--test={test}"],
        timeout=timeout,
    )


def reset_controller(
    device: str, timeout: float = DEFAULT_TIMEOUT
) -> str:
    """Reset an NVMe controller (``nvme reset <dev>``).

    Requires the ``sys.admin`` capability when the gate
    is enforcing.
    """
    gate.require(CAP_SYS_ADMIN)
    return _run(["reset", device], timeout=timeout)


def subsystem_reset(
    device: str, timeout: float = DEFAULT_TIMEOUT
) -> str:
    """Reset an NVMe subsystem (``nvme subsystem-reset <dev>``).

    Requires the ``sys.admin`` capability when the gate
    is enforcing.
    """
    gate.require(CAP_SYS_ADMIN)
    return _run(["subsystem-reset", device], timeout=timeout)


def fw_download(
    device: str,
    firmware_file: str,
    slot: int = 0,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """Download firmware (``nvme fw-download <dev> --fw=<file>``).

    Requires the ``sys.admin`` capability when the gate
    is enforcing.
    """
    gate.require(CAP_SYS_ADMIN)
    if not os.path.isfile(firmware_file):
        raise NvmeCLIError(f"firmware file not found: {firmware_file}")
    return _run(
        ["fw-download", device, f"--fw={firmware_file}", f"--slot={slot}"],
        timeout=timeout,
    )


def fw_commit(
    device: str,
    slot: int,
    action: str = "activate",
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """Commit a firmware slot (``nvme fw-commit <dev>``).

    Args:
        device: Device path (e.g. ``/dev/nvme0``).
        slot:   Firmware slot number.
        action: ``activate``, ``save``, ``replace`` or
            ``replace-save``.

    Requires the ``sys.admin`` capability when the gate
    is enforcing.
    """
    gate.require(CAP_SYS_ADMIN)
    if action not in ("activate", "save", "replace", "replace-save"):
        raise ValueError(
            'action must be "activate", "save", "replace" '
            'or "replace-save"'
        )
    return _run(
        ["fw-commit", device, f"--slot={slot}", f"--action={action}"],
        timeout=timeout,
    )


def _selftest() -> bool:
    """Run a basic self-test for this module (no nvme-cli needed)."""
    assert NVME_BIN == "nvme"
    assert issubclass(NvmeCLIError, RuntimeError)

    # _build_args / normalization logic
    assert _build_args(["list"], json_output=True) == [
        "nvme", "list", "--output-format=json"
    ]
    assert _build_args(["id-ctrl", "/dev/nvme0"], json_output=False) == [
        "nvme", "id-ctrl", "/dev/nvme0"
    ]
    assert _normalize_device({"DevicePath": "/dev/nvme0"}) == {
        "devicepath": "/dev/nvme0"
    }

    # Missing binary path (or real list if nvme-cli happens to exist)
    if shutil.which(NVME_BIN) is None:
        for call in (
            lambda: list_devices(),
            lambda: identify_controller("/dev/nvme0"),
            lambda: identify_namespace("/dev/nvme0"),
            lambda: smart_log("/dev/nvme0"),
            lambda: self_test_log("/dev/nvme0"),
            lambda: get_log("/dev/nvme0", 2),
        ):
            try:
                call()
            except NvmeCLIError:
                pass
            else:
                raise AssertionError(
                    "missing nvme-cli must raise NvmeCLIError"
                )

    # Argument validation
    try:
        self_test_start("/dev/nvme0", test="bogus")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid self-test type must raise ValueError")
    try:
        fw_commit("/dev/nvme0", slot=1, action="bogus")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid fw-commit action must raise ValueError")

    print("selftest OK")
    return True


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(0 if _selftest() else 1)
