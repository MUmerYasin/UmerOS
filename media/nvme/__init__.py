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
UmerOS /media/nvme - NVMe Support
=====================================

NVMe (Non-Volatile Memory Express) support for UmerOS,
including M.2 SSDs.  The package is self-contained
(standard library only) and exposes four sub-modules:

* :mod:`media.nvme.device`  - sysfs discovery of NVMe
  controllers (``nvmeN``), namespaces (``nvmeNnM``),
  partitions and alias namespaces, with a simulation
  mode for hosts without NVMe hardware.
* :mod:`media.nvme.identify` - parsers for the 4096-byte
  *Identify Controller* / *Identify Namespace* payloads
  (NVM Express 1.4 / 2.0 field layout).
* :mod:`media.nvme.smart`   - SMART/Health log (Log ID
  ``0x02``) parser with critical-warning decoding and
  threshold-based health assessment.
* :mod:`media.nvme.m2`      - M.2 form factor (2230 /
  2242 / 2260 / 2280 / 22110), edge-connector keying
  and PCIe link model.
* :mod:`media.nvme.cli`     - capability-gated wrapper
  around the ``nvme-cli`` utility (list / id-ctrl /
  id-ns / smart-log / self-test / reset / firmware).

Quick start::

    from media.nvme.device import discover
    from media.nvme.identify import parse_identify_controller
    from media.nvme.smart import parse_smart_log, assess_health

    for ctrl in discover():
        print(ctrl.name, ctrl.model, ctrl.namespaces)

This package is ``[REFERENCE-ONLY]`` - it is not
imported by ``main.py``.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

from .device import (
    KIND_ALIAS,
    KIND_CONTROLLER,
    KIND_NAMESPACE,
    KIND_PARTITION,
    NVMeControllerInfo,
    NVMeNamespaceInfo,
    NVMeSubsystemInfo,
    available,
    classify_nvme_name,
    clear_simulation,
    controller_of,
    discover,
    discover_namespaces,
    discover_subsystems,
    get_simulation,
    read_controller_info,
    read_namespace_info,
    read_subsystem_info,
    set_simulation,
)
from .identify import (
    IDENTIFY_SIZE,
    IdentifyController,
    IdentifyNamespace,
    LBFormat,
    parse_identify_controller,
    parse_identify_namespace,
    spec_version_str,
)
from .m2 import (
    M2DriveInfo,
    M2FormFactor,
    M2Keying,
    form_factor_from_dims,
    keying_supports_nvme,
    lanes_from_link_width,
    pcie_link_from_sysfs,
)
from .smart import (
    HealthLevel,
    HealthThresholds,
    NVMeHealthReport,
    SMART_LOG_ID,
    SMART_LOG_SIZE,
    SMARTHealthLog,
    assess_health,
    critical_warning_reasons,
    kelvin_to_celsius,
    parse_smart_log,
)

try:
    from .cli import (
        NVME_BIN,
        NvmeCLIError,
        identify_controller,
        identify_namespace,
        list_devices,
        self_test_log,
        self_test_start,
        smart_log,
    )
except Exception:  # pragma: no cover - keep package importable
    NvmeCLIError = RuntimeError

__all__ = [
    "HealthLevel",
    "HealthThresholds",
    "IDENTIFY_SIZE",
    "KIND_ALIAS",
    "KIND_CONTROLLER",
    "KIND_NAMESPACE",
    "KIND_PARTITION",
    "LBFormat",
    "M2DriveInfo",
    "M2FormFactor",
    "M2Keying",
    "NVME_BIN",
    "NVMeControllerInfo",
    "NVMeHealthReport",
    "NVMeNamespaceInfo",
    "NVMeSubsystemInfo",
    "NvmeCLIError",
    "SMART_LOG_ID",
    "SMART_LOG_SIZE",
    "SMARTHealthLog",
    "IdentifyController",
    "IdentifyNamespace",
    "assess_health",
    "available",
    "classify_nvme_name",
    "clear_simulation",
    "controller_of",
    "critical_warning_reasons",
    "discover",
    "discover_namespaces",
    "discover_subsystems",
    "form_factor_from_dims",
    "get_simulation",
    "identify_controller",
    "identify_namespace",
    "keying_supports_nvme",
    "kelvin_to_celsius",
    "lanes_from_link_width",
    "list_devices",
    "parse_identify_controller",
    "parse_identify_namespace",
    "parse_smart_log",
    "pcie_link_from_sysfs",
    "read_controller_info",
    "read_namespace_info",
    "read_subsystem_info",
    "self_test_log",
    "self_test_start",
    "set_simulation",
    "smart_log",
    "spec_version_str",
]


def _selftest() -> bool:
    """Run a basic self-test for this package (synthetic data only)."""
    from . import cli as _cli
    from . import device as _device
    from . import identify as _identify
    from . import m2 as _m2
    from . import smart as _smart

    assert classify_nvme_name("nvme0") == KIND_CONTROLLER
    assert classify_nvme_name("nvme0n1") == KIND_NAMESPACE
    assert classify_nvme_name("sda") is None
    assert controller_of("nvme2n5") == "nvme2"

    assert form_factor_from_dims(22, 80) == M2FormFactor.M2_2280
    assert keying_supports_nvme(M2Keying.KEY_M) is True
    assert keying_supports_nvme(M2Keying.KEY_B) is False
    assert lanes_from_link_width("x4") == 4

    ctrl_blob = bytearray(IDENTIFY_SIZE)
    ctrl_blob[80:84] = (0x00010400).to_bytes(4, "little")
    ctrl_blob[236:238] = (328).to_bytes(2, "little")
    ctrl_blob[238:240] = (343).to_bytes(2, "little")
    ctrl = parse_identify_controller(bytes(ctrl_blob))
    assert ctrl.spec_version == "1.4"

    ns_blob = bytearray(IDENTIFY_SIZE)
    ns_blob[0:8] = (100).to_bytes(8, "little")
    ns_blob[25] = 0
    ns_blob[26] = 0
    ns_blob[128:130] = (0).to_bytes(2, "little")
    ns_blob[130] = 9
    ns = parse_identify_namespace(bytes(ns_blob))
    assert ns.block_size == 512
    assert ns.capacity_bytes == 100 * 512

    smart_log_blob = bytearray(SMART_LOG_SIZE)
    smart_log_blob[1:3] = (300).to_bytes(2, "little")
    smart_log_blob[5] = 0
    smart = parse_smart_log(bytes(smart_log_blob))
    report = assess_health(
        smart, wctemp_k=343, cctemp_k=358
    )
    assert report.level == HealthLevel.OK

    assert _cli.NVME_BIN == "nvme"
    assert _device.SYS_CLASS_NVME.name == "nvme"
    assert _m2.M2FormFactor.M2_2280.name_mm == "2280"

    print("selftest OK")
    return True


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(0 if _selftest() else 1)
