"""
UmerOS /lib/firmware — Firmware Blob Manager
==============================================
Implements the FHS subdirectory ``/lib/firmware`` which holds the
firmware blobs loaded by the kernel at runtime via ``request_firmware()``.

Although TLDP's 1990s-era description of /lib does not mention firmware
explicitly, it is universally expected on modern systems
(distributions split firmware out of /lib to allow /usr to be read-only).
The directory typically contains tens of thousands of blobs grouped by
vendor / subsystem.

The structure is::

    /lib/firmware/
        <subsystem>/<vendor>/<device>.fw       (binary)
        .../LICENSE*                            (licence text)
        WHENCE                                  (manifest)

UmerOS models the catalogue so the hotplug subsystem can answer
"is firmware X available for device Y?" without shipping the blobs.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

log = logging.getLogger("UmerOS.Lib.Firmware")


class FirmwareSubsystem(str, Enum):
    WIFI        = "wifi"
    BLUETOOTH   = "bluetooth"
    GPU         = "gpu"
    AUDIO       = "audio"
    NIC         = "nic"
    SATA        = "sata"
    USB         = "usb"
    DSP         = "dsp"
    SCSI        = "scsi"
    INPUT       = "input"
    SENSOR      = "sensor"
    RADIO       = "radio"
    OTHER       = "other"


class FirmwareLicense(str, Enum):
    PROPRIETARY    = "proprietary"
    GPL2            = "GPL-2.0"
    GPL3            = "GPL-3.0"
    MIT             = "MIT"
    BSD2            = "BSD-2-Clause"
    BSD3            = "BSD-3-Clause"
    APACHE2         = "Apache-2.0"
    ISC             = "ISC"
    BINARY_DIST     = "Binary redistribution only"
    DUAL_GPL        = "Dual GPL/proprietary"
    PUBLIC_DOMAIN   = "Public domain"
    UNKNOWN         = "unknown"


@dataclass
class FirmwareBlob:
    """A single firmware file."""
    name: str                        # the filename inside /lib/firmware/...
    path: str                        # full /lib/firmware/... path
    subsystem: FirmwareSubsystem
    vendor: str
    device: str                      # the device ID / product ID
    version: str = ""
    size: int = 0
    md5: str = ""
    sha256: str = ""
    license: FirmwareLicense = FirmwareLicense.UNKNOWN
    compression: str = ""            # e.g. "zstd" — may be embedded in the .fw
    signed: bool = False             # cryptographically signed by vendor
    description: str = ""
    request_alias: str = ""          # the kernel request_firmware() name

    def __hash__(self) -> int:
        return hash((self.name, self.vendor, self.device))

    def matches_request(self, request: str) -> bool:
        """
        Does this blob match a kernel ``request_firmware()`` call?
        The kernel sends a string like ``"iwlwifi-7265-26.ucode"``; we
        match on either the exact name or a substring.
        """
        if self.request_alias and self.request_alias == request:
            return True
        return request == self.name or request in self.name


# A representative starter catalogue of firmware files that any modern system
# would have available.  Real distributions ship ~10× more; this set is the
# "table of contents" the kernel module manager would consult.
_STOCK_FIRMWARE: List[FirmwareBlob] = [
    # Intel Wireless
    FirmwareBlob("iwlwifi-100-5.ucode", "/lib/firmware/iwlwifi-100-5.ucode",
        FirmwareSubsystem.WIFI, vendor="Intel", device="WiFi Link 100",
        version="39.31.5.1", size=345_768, license=FirmwareLicense.DUAL_GPL,
        request_alias="iwlwifi-100-5.ucode",
        description="Intel Wireless 100 series ucode"),
    FirmwareBlob("iwlwifi-3160-17.ucode", "/lib/firmware/iwlwifi-3160-17.ucode",
        FirmwareSubsystem.WIFI, vendor="Intel", device="Wireless 3160",
        version="17.3216344376.0", size=675_452, license=FirmwareLicense.DUAL_GPL),
    FirmwareBlob("iwlwifi-7260-17.ucode", "/lib/firmware/iwlwifi-7260-17.ucode",
        FirmwareSubsystem.WIFI, vendor="Intel", device="Wireless 7260",
        version="17.3216344376.0", size=675_452, license=FirmwareLicense.DUAL_GPL),
    FirmwareBlob("iwlwifi-7265-26.ucode", "/lib/firmware/iwlwifi-7265-26.ucode",
        FirmwareSubsystem.WIFI, vendor="Intel", device="Wireless 7265",
        version="26.7c580c5.0", size=1_017_216, license=FirmwareLicense.DUAL_GPL),
    FirmwareBlob("iwlwifi-8265-36.ucode", "/lib/firmware/iwlwifi-8265-36.ucode",
        FirmwareSubsystem.WIFI, vendor="Intel", device="Wireless 8265",
        version="36.ca7b901d.0", size=1_152_800, license=FirmwareLicense.DUAL_GPL),
    FirmwareBlob("iwlwifi-9000-pu-b0-jf-b0-46.ucode", "/lib/firmware/iwlwifi-9000-pu-b0-jf-b0-46.ucode",
        FirmwareSubsystem.WIFI, vendor="Intel", device="Wireless 9000",
        version="46.7a2871b7.0", size=1_352_336, license=FirmwareLicense.DUAL_GPL),
    # Qualcomm Atheros
    FirmwareBlob("ath10k/QCA988X/hw2.0/ct-2.0/firmware-5.bin",
        "/lib/firmware/ath10k/QCA988X/hw2.0/ct-2.0/firmware-5.bin",
        FirmwareSubsystem.WIFI, vendor="Qualcomm Atheros", device="QCA988X",
        version="10.2.4", size=124_928, license=FirmwareLicense.DUAL_GPL),
    FirmwareBlob("ath10k/QCA6174/hw3.0/board-2.bin",
        "/lib/firmware/ath10k/QCA6174/hw3.0/board-2.bin",
        FirmwareSubsystem.WIFI, vendor="Qualcomm Atheros", device="QCA6174",
        version="2.0", size=12_288, license=FirmwareLicense.DUAL_GPL),
    FirmwareBlob("ath10k/QCA6174/hw3.0/firmware-6.bin",
        "/lib/firmware/ath10k/QCA6174/hw3.0/firmware-6.bin",
        FirmwareSubsystem.WIFI, vendor="Qualcomm Atheros", device="QCA6174",
        version="6.0", size=524_288, license=FirmwareLicense.DUAL_GPL),
    # Realtek
    FirmwareBlob("rtw88/rtw8821c_fw.bin", "/lib/firmware/rtw88/rtw8821c_fw.bin",
        FirmwareSubsystem.WIFI, vendor="Realtek", device="RTL8821C",
        version="1.0", size=155_648, license=FirmwareLicense.DUAL_GPL),
    FirmwareBlob("rtw89/rtw8852c_fw.bin", "/lib/firmware/rtw89/rtw8852c_fw.bin",
        FirmwareSubsystem.WIFI, vendor="Realtek", device="RTL8852C",
        version="1.0", size=458_752, license=FirmwareLicense.DUAL_GPL),
    # Broadcom
    FirmwareBlob("brcm/brcmfmac43455-sdio.bin", "/lib/firmware/brcm/brcmfmac43455-sdio.bin",
        FirmwareSubsystem.WIFI, vendor="Broadcom", device="BCM43455",
        version="7.45.18.0", size=419_088, license=FirmwareLicense.DUAL_GPL),
    FirmwareBlob("brcm/brcmfmac43602-pcie.bin", "/lib/firmware/brcm/brcmfmac43602-pcie.bin",
        FirmwareSubsystem.WIFI, vendor="Broadcom", device="BCM43602",
        version="7.35.349.4", size=524_288, license=FirmwareLicense.DUAL_GPL),
    # Bluetooth
    FirmwareBlob("intel/ibt-11-5.sfi", "/lib/firmware/intel/ibt-11-5.sfi",
        FirmwareSubsystem.BLUETOOTH, vendor="Intel", device="AX201 BT",
        version="11.5.0.0", size=524_288, license=FirmwareLicense.DUAL_GPL),
    FirmwareBlob("intel/ibt-12-16.sfi", "/lib/firmware/intel/ibt-12-16.sfi",
        FirmwareSubsystem.BLUETOOTH, vendor="Intel", device="AX211 BT",
        version="12.16.0.0", size=557_056, license=FirmwareLicense.DUAL_GPL),
    # GPU
    FirmwareBlob("nvidia/ga107/acr/bl.bin", "/lib/firmware/nvidia/ga107/acr/bl.bin",
        FirmwareSubsystem.GPU, vendor="NVIDIA", device="GA107",
        version="535.86.10", size=131_072, license=FirmwareLicense.PROPRIETARY, signed=True),
    FirmwareBlob("nvidia/ga107/acr/ucode_ahesasc.bin",
        "/lib/firmware/nvidia/ga107/acr/ucode_ahesasc.bin",
        FirmwareSubsystem.GPU, vendor="NVIDIA", device="GA107",
        version="535.86.10", size=8_192, license=FirmwareLicense.PROPRIETARY, signed=True),
    FirmwareBlob("amdgpu/navy_kicker_smc.bin", "/lib/firmware/amdgpu/navy_kicker_smc.bin",
        FirmwareSubsystem.GPU, vendor="AMD", device="Navy Flounder",
        version="1.0", size=4_096, license=FirmwareLicense.DUAL_GPL, signed=True),
    FirmwareBlob("i915/kbl_dmc_ver1_04.bin", "/lib/firmware/i915/kbl_dmc_ver1_04.bin",
        FirmwareSubsystem.GPU, vendor="Intel", device="Kaby Lake",
        version="1.04", size=4_096, license=FirmwareLicense.GPL2),
    FirmwareBlob("i915/tgl_dmc_ver2_12.bin", "/lib/firmware/i915/tgl_dmc_ver2_12.bin",
        FirmwareSubsystem.GPU, vendor="Intel", device="Tiger Lake",
        version="2.12", size=16_384, license=FirmwareLicense.GPL2),
    # Audio
    FirmwareBlob("cirrus/cs35l41-dsp1-spk-prot.wmfw",
        "/lib/firmware/cirrus/cs35l41-dsp1-spk-prot.wmfw",
        FirmwareSubsystem.AUDIO, vendor="Cirrus Logic", device="CS35L41",
        version="1.0", size=28_672, license=FirmwareLicense.PROPRIETARY, signed=True),
    FirmwareBlob("cirrus/cs35l41-dsp1-spk-prot.bin",
        "/lib/firmware/cirrus/cs35l41-dsp1-spk-prot.bin",
        FirmwareSubsystem.AUDIO, vendor="Cirrus Logic", device="CS35L41",
        version="1.0", size=81_920, license=FirmwareLicense.PROPRIETARY, signed=True),
    # NIC
    FirmwareBlob("bnx2x/bnx2x-e2-7.13.1.0.fw",
        "/lib/firmware/bnx2x/bnx2x-e2-7.13.1.0.fw",
        FirmwareSubsystem.NIC, vendor="Broadcom", device="NetXtreme II 10G",
        version="7.13.1.0", size=458_752, license=FirmwareLicense.PROPRIETARY),
    FirmwareBlob("e100/d101m_ucode.bin", "/lib/firmware/e100/d101m_ucode.bin",
        FirmwareSubsystem.NIC, vendor="Intel", device="PRO/100",
        version="1.0", size=8_192, license=FirmwareLicense.GPL2),
    # Storage
    FirmwareBlob("mpt3sas/mpt3sas_fw.28000000.rom",
        "/lib/firmware/mpt3sas/mpt3sas_fw.28000000.rom",
        FirmwareSubsystem.SCSI, vendor="Broadcom", device="SAS3008",
        version="28.0.0.0", size=98_304, license=FirmwareLicense.PROPRIETARY),
    # TV / Radio tuner
    FirmwareBlob("tda7706-om2514.fw", "/lib/firmware/tda7706-om2514.fw",
        FirmwareSubsystem.RADIO, vendor="ST Microelectronics", device="TDA7706",
        version="2.1", size=16_384, license=FirmwareLicense.PROPRIETARY),
    # Sensor
    FirmwareBlob("scm/boxer-soc.dtb", "/lib/firmware/scm/boxer-soc.dtb",
        FirmwareSubsystem.SENSOR, vendor="generic", device="dtb",
        size=8_192, license=FirmwareLicense.GPL2, description="Device tree"),
    # DSP
    FirmwareBlob("mediatek/mt8183/dsp.bin", "/lib/firmware/mediatek/mt8183/dsp.bin",
        FirmwareSubsystem.DSP, vendor="MediaTek", device="MT8183",
        version="1.0", size=147_456, license=FirmwareLicense.GPL2),
    # USB
    FirmwareBlob("whiteheat.fw", "/lib/firmware/whiteheat.fw",
        FirmwareSubsystem.USB, vendor="Inside Out Networks", device="WhiteHeat",
        version="1.0", size=2_048, license=FirmwareLicense.GPL2),
]


class FirmwareManager:
    """
    Manages the firmware catalogue and the ``request_firmware()`` resolution
    algorithm used by the kernel.
    """

    WHENCE_HEADER = """\
# UmerOS firmware WHENCE — file: this manifest describes the firmware
# files in this directory.  Each `File:` line points at a blob, followed by
# the `Licence:` line, `Version:` line, and any device bindings.
#
# Format is based on the upstream  WHENCE file.
"""

    def __init__(self, lib_path: str = "/lib", firmware_path: str = "/lib/firmware") -> None:
        self.lib_path = Path(lib_path)
        self.firmware_path = Path(firmware_path)
        self._firmware: Dict[str, FirmwareBlob] = {f.name: f for f in _STOCK_FIRMWARE}

    # ── queries ───────────────────────────────────────────────────

    def list_firmware(self) -> List[FirmwareBlob]:
        return list(self._firmware.values())

    def find(self, name: str) -> Optional[FirmwareBlob]:
        return self._firmware.get(name)

    def by_subsystem(self, subsystem: FirmwareSubsystem) -> List[FirmwareBlob]:
        return [f for f in self._firmware.values() if f.subsystem == subsystem]

    def by_vendor(self, vendor: str) -> List[FirmwareBlob]:
        return [f for f in self._firmware.values() if f.vendor.lower() == vendor.lower()]

    def by_device(self, vendor: str, device: str) -> List[FirmwareBlob]:
        v = vendor.lower(); d = device.lower()
        return [
            f for f in self._firmware.values()
            if f.vendor.lower() == v and f.device.lower() == d
        ]

    def by_license(self, license: FirmwareLicense) -> List[FirmwareBlob]:
        return [f for f in self._firmware.values() if f.license == license]

    def resolve_request(self, request: str) -> List[FirmwareBlob]:
        """Find every firmware blob that satisfies a kernel request."""
        return [f for f in self._firmware.values() if f.matches_request(request)]

    def register(self, blob: FirmwareBlob) -> None:
        self._firmware[blob.name] = blob

    def unregister(self, name: str) -> bool:
        return self._firmware.pop(name, None) is not None

    # ── on-disk materialisation ───────────────────────────────────

    def materialise_stubs(self, root: str = "/") -> int:
        target = Path(root) / "lib" / "firmware"
        target.mkdir(parents=True, exist_ok=True)
        written = 0
        for blob in self._firmware.values():
            p = target / blob.path[len("/lib/firmware/"):]
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists():
                p.write_bytes(b"UmerOS firmware stub: " + blob.name.encode() + b"\n")
                written += 1
        # Emit a WHENCE manifest
        whence = target / "WHENCE"
        if not whence.exists():
            whence.write_text(self.render_whence(), encoding="utf-8")
        return written

    def render_whence(self) -> str:
        lines: List[str] = [self.WHENCE_HEADER]
        for blob in self._firmware.values():
            lines.append(f"File: {blob.path[len('/lib/firmware/'):]}")
            lines.append(f"Licence: {blob.license.value}")
            if blob.version:
                lines.append(f"Version: {blob.version}")
            if blob.vendor and blob.device:
                lines.append(f"Device: {blob.vendor} {blob.device}")
            if blob.description:
                lines.append(f"Description: {blob.description}")
            lines.append("")  # blank line between entries
        return "\n".join(lines)

    # ── summary ───────────────────────────────────────────────────

    def get_summary(self) -> Dict:
        blobs = list(self._firmware.values())
        return {
            "total_blobs": len(blobs),
            "by_subsystem": {
                s.value: len(self.by_subsystem(s)) for s in FirmwareSubsystem
            },
            "by_license": {
                lic.value: len(self.by_license(lic)) for lic in FirmwareLicense
            },
            "signed": sum(1 for b in blobs if b.signed),
            "total_size_bytes": sum(b.size for b in blobs),
            "directory": str(self.firmware_path),
        }


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------

def _selftest():
    """Run a basic self-test for this module."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = FirmwareManager(lib_path=tmpdir, firmware_path=tmpdir)
        summary = mgr.get_summary()
        assert "total_blobs" in summary, "summary should have total_blobs"

    print("selftest OK")
    return True


if __name__ == "__main__":
    _selftest()
