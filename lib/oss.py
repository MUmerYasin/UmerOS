"""
UmerOS /lib/oss — Open Sound System Module Catalogue
======================================================
Implements the FHS subdirectory ``/lib/oss`` which historically holds
the Open Sound System driver modules.  Although OSS has largely been
replaced by ALSA + PulseAudio / PipeWire, the directory is still
referenced by older audio stacks.

Real ``/lib/oss`` contains (per vendor / card):

  oss_ali5455/       — ALi M5455
  oss_au8810/        — Aureal Vortex 8810
  oss_au8820/        — Aureal Vortex 8820
  oss_au8830/        — Aureal Vortex 8830
  oss_cs4280/        — Crystal CS4280
  oss_cs4281/        — Crystal CS4281
  oss_ct5880/        — Crystal CT5880
  oss_emu10k1/       — Creative EMU10K1 (SBLive!)
  oss_envy24/        — VIA Envy24
  oss_envy24ht/      — VIA Envy24HT
  oss_fmedia/        — FM801
  oss_geode/         — National Semiconductors Geode
  oss_ich/           — Intel ICH
  oss_neomagic/      — Neomagic
  oss_sblive/        — SBLive (legacy)
  oss_sbpci/         — SB PCI
  oss_sbxfi/         — SB X-Fi
  oss_solo/          — ESS Solo
  oss_trident/       — Trident
  oss_via82cxxx/     — VIA 82Cxxx
  oss_ymf7xx/        — Yamaha YMF7xx
  oss_ali5455/osscore/  — the OSS core module
  modules/           — shared OSS .o files

UmerOS models the catalogue so the audio subsystem can query which OSS
drivers are available, even though we don't load them.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set

log = logging.getLogger("UmerOS.Lib.Oss")


class OssBusType(str, Enum):
    PCI   = "pci"
    ISA   = "isa"
    USB   = "usb"
    AC97  = "ac97"
    BUILTIN = "builtin"


class OssDriverKind(str, Enum):
    SOUND      = "sound"         # actual audio device driver
    MIXER      = "mixer"         # mixer-only
    MIDI       = "midi"          # MIDI sequencer
    OSSCORE    = "osscore"       # the OSS core (mandatory)
    MPU401     = "mpu401"        # MIDI port
    USBMIDI    = "usbmidi"


@dataclass
class OssDriver:
    """One Open Sound System driver subdirectory under /lib/oss."""
    name: str
    path: str
    kind: OssDriverKind
    bus: OssBusType
    description: str
    vendor_id: str = "0x0000"
    device_id: str = "0x0000"
    size: int = 0
    version: str = "4.2"
    supported_cards: List[str] = field(default_factory=list)
    midi_ports: int = 0
    max_channels: int = 2           # 2 = stereo
    has_hardware_mixing: bool = False
    md5: str = ""


# Standard OSS driver directory map (driver name → (kind, bus, description))
_STOCK_DRIVERS: List[OssDriver] = [
    OssDriver("osscore",          "/lib/oss/osscore",      OssDriverKind.OSSCORE, OssBusType.BUILTIN,
        "OSS core module (mandatory)",
        size=2_457_600, version="4.2", supported_cards=["*"]),
    OssDriver("oss_ali5455",      "/lib/oss/oss_ali5455",  OssDriverKind.SOUND, OssBusType.PCI,
        "ALi M5455 AC'97 audio",
        vendor_id="0x10B9", device_id="0x5455",
        size=180_224, max_channels=2),
    OssDriver("oss_au8810",       "/lib/oss/oss_au8810",   OssDriverKind.SOUND, OssBusType.PCI,
        "Aureal Vortex 8810 (3D positional audio)",
        vendor_id="0x12EB", device_id="0x0001",
        size=204_800, max_channels=2, has_hardware_mixing=True),
    OssDriver("oss_au8820",       "/lib/oss/oss_au8820",   OssDriverKind.SOUND, OssBusType.PCI,
        "Aureal Vortex 8820",
        vendor_id="0x12EB", device_id="0x0002",
        size=212_992, max_channels=2, has_hardware_mixing=True),
    OssDriver("oss_au8830",       "/lib/oss/oss_au8830",   OssDriverKind.SOUND, OssBusType.PCI,
        "Aureal Vortex 8830 (A3D 2.0)",
        vendor_id="0x12EB", device_id="0x0003",
        size=229_376, max_channels=2, has_hardware_mixing=True),
    OssDriver("oss_cs4280",       "/lib/oss/oss_cs4280",   OssDriverKind.SOUND, OssBusType.PCI,
        "Crystal CS4280/4610",
        vendor_id="0x1013", device_id="0x6001",
        size=147_456),
    OssDriver("oss_cs4281",       "/lib/oss/oss_cs4281",   OssDriverKind.SOUND, OssBusType.PCI,
        "Crystal CS4281",
        vendor_id="0x1013", device_id="0x6003",
        size=155_648),
    OssDriver("oss_ct5880",       "/lib/oss/oss_ct5880",   OssDriverKind.SOUND, OssBusType.PCI,
        "Crystal CT5880 (Chips & Technologies)",
        vendor_id="0x10B9", device_id="0x5451",
        size=143_360),
    OssDriver("oss_emu10k1",      "/lib/oss/oss_emu10k1",  OssDriverKind.SOUND, OssBusType.PCI,
        "Creative EMU10K1 (Sound Blaster Live!)",
        vendor_id="0x1102", device_id="0x0002",
        size=327_680, max_channels=8, has_hardware_mixing=True, midi_ports=1),
    OssDriver("oss_envy24",       "/lib/oss/oss_envy24",   OssDriverKind.SOUND, OssBusType.PCI,
        "VIA Envy24 (ICE1712 / ICE1724)",
        vendor_id="0x1412", device_id="0x1712",
        size=270_336, max_channels=8, has_hardware_mixing=True, midi_ports=1),
    OssDriver("oss_envy24ht",     "/lib/oss/oss_envy24ht", OssDriverKind.SOUND, OssBusType.PCI,
        "VIA Envy24HT (VT1724)",
        vendor_id="0x1412", device_id="0x1724",
        size=294_912, max_channels=8, has_hardware_mixing=True, midi_ports=1),
    OssDriver("oss_fmedia",       "/lib/oss/oss_fmedia",   OssDriverKind.SOUND, OssBusType.PCI,
        "ForteMedia FM801",
        vendor_id="0x1319", device_id="0x0801",
        size=180_224),
    OssDriver("oss_geode",        "/lib/oss/oss_geode",    OssDriverKind.SOUND, OssBusType.BUILTIN,
        "AMD Geode CS5535/CS5536",
        size=155_648),
    OssDriver("oss_ich",          "/lib/oss/oss_ich",      OssDriverKind.SOUND, OssBusType.PCI,
        "Intel ICH (AC'97 / HDA)",
        vendor_id="0x8086", device_id="0x2415",
        size=196_608, has_hardware_mixing=True),
    OssDriver("oss_neomagic",     "/lib/oss/oss_neomagic", OssDriverKind.SOUND, OssBusType.PCI,
        "Neomagic MagicMedia 256",
        vendor_id="0x10C8", device_id="0x8005",
        size=147_456),
    OssDriver("oss_sbpci",        "/lib/oss/oss_sbpci",    OssDriverKind.SOUND, OssBusType.PCI,
        "Sound Blaster PCI 64/128",
        vendor_id="0x1274", device_id="0x1371",
        size=204_800, midi_ports=1),
    OssDriver("oss_sbxfi",        "/lib/oss/oss_sbxfi",    OssDriverKind.SOUND, OssBusType.PCI,
        "Sound Blaster X-Fi (EMU20K1)",
        vendor_id="0x1102", device_id="0x0005",
        size=409_600, max_channels=8, has_hardware_mixing=True, midi_ports=1),
    OssDriver("oss_solo",         "/lib/oss/oss_solo",     OssDriverKind.SOUND, OssBusType.PCI,
        "ESS Solo-1 (ES1938/ES1946)",
        vendor_id="0x125D", device_id="0x1969",
        size=155_648),
    OssDriver("oss_trident",      "/lib/oss/oss_trident",  OssDriverKind.SOUND, OssBusType.PCI,
        "Trident 4DWave / DX / NX",
        vendor_id="0x1023", device_id="0x2000",
        size=180_224, midi_ports=1),
    OssDriver("oss_via82cxxx",    "/lib/oss/oss_via82cxxx",OssDriverKind.SOUND, OssBusType.PCI,
        "VIA 82Cxxx AC'97",
        vendor_id="0x1106", device_id="0x3058",
        size=196_608, has_hardware_mixing=True),
    OssDriver("oss_ymf7xx",       "/lib/oss/oss_ymf7xx",   OssDriverKind.SOUND, OssBusType.PCI,
        "Yamaha YMF724/740/744/754",
        vendor_id="0x1073", device_id="0x0004",
        size=212_992, has_hardware_mixing=True, midi_ports=1),
    # USB
    OssDriver("oss_usb",          "/lib/oss/oss_usb",      OssDriverKind.SOUND, OssBusType.USB,
        "USB audio class driver",
        size=212_992),
    OssDriver("oss_usbmidi",      "/lib/oss/oss_usbmidi",  OssDriverKind.USBMIDI, OssBusType.USB,
        "USB MIDI class driver", midi_ports=1, size=131_072),
    # MPU401
    OssDriver("oss_mpu401",       "/lib/oss/oss_mpu401",   OssDriverKind.MPU401, OssBusType.ISA,
        "MPU401 MIDI port", midi_ports=1, size=49_152),
]


class OssManager:
    """Manages the ``/lib/oss`` directory tree."""

    def __init__(self, lib_path: str = "/lib", oss_path: str = "/lib/oss") -> None:
        self.lib_path = Path(lib_path)
        self.oss_path = Path(oss_path)
        self._drivers: Dict[str, OssDriver] = {d.name: d for d in _STOCK_DRIVERS}

    def list_drivers(self) -> List[OssDriver]:
        return list(self._drivers.values())

    def find_driver(self, name: str) -> Optional[OssDriver]:
        return self._drivers.get(name)

    def by_vendor_device(self, vendor: str, device: str) -> List[OssDriver]:
        v = vendor.lower()
        d = device.lower()
        return [
            drv for drv in self._drivers.values()
            if drv.vendor_id.lower() == v and drv.device_id.lower() == d
        ]

    def by_bus(self, bus: OssBusType) -> List[OssDriver]:
        return [d for d in self._drivers.values() if d.bus == bus]

    def by_kind(self, kind: OssDriverKind) -> List[OssDriver]:
        return [d for d in self._drivers.values() if d.kind == kind]

    def register_driver(self, driver: OssDriver) -> None:
        self._drivers[driver.name] = driver

    def materialise_stubs(self, root: str = "/") -> int:
        target = Path(root) / "lib" / "oss"
        target.mkdir(parents=True, exist_ok=True)
        written = 0
        for d in self._drivers.values():
            p = target / d.path[len("/lib/oss/"):]
            p.mkdir(parents=True, exist_ok=True)
            stub = p / "ossmodule.o"
            if not stub.exists():
                stub.write_bytes(
                    b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8
                    + f"UmerOS OSS stub for {d.name} ({d.description})\n".encode()
                )
                written += 1
        return written

    def get_summary(self) -> Dict:
        drivers = list(self._drivers.values())
        return {
            "total_drivers": len(drivers),
            "by_bus":   {b.value: len(self.by_bus(b))   for b in OssBusType},
            "by_kind":  {k.value: len(self.by_kind(k))  for k in OssDriverKind},
            "hardware_mixing_drivers": sum(1 for d in drivers if d.has_hardware_mixing),
            "midi_capable": sum(1 for d in drivers if d.midi_ports > 0),
            "total_size_bytes": sum(d.size for d in drivers),
            "directory": str(self.oss_path),
        }


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------

def _selftest():
    """Run a basic self-test for this module."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = OssManager(lib_path=tmpdir, oss_path=tmpdir)
        summary = mgr.get_summary()
        assert "total_drivers" in summary, "summary should have total_drivers"

    print("selftest OK")
    return True


if __name__ == "__main__":
    _selftest()
