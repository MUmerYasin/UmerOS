"""
UmerOS /etc Hardware Configuration
====================================
Manages hardware-related system configuration files.

FHS 3.0 entries:
  /etc/adjtime      — Hardware clock adjustment time
  /etc/sensors.conf  — Hardware sensors configuration
  /etc/serial.conf   — Serial port configuration
  /etc/fdprm         — Floppy disk parameter definitions
  /etc/isapnp.conf   — ISA PnP device configuration
  /etc/modules.conf  — Kernel module aliases
  /etc/modprobe.d/   — Modprobe configuration directory
  /etc/modprobe.conf — Modprobe configuration

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Etc.HardwareConfig")


@dataclass
class ModuleAlias:
    """Represents a kernel module alias."""
    alias: str
    module: str
    options: str = ""
    comments: List[str] = field(default_factory=list)


@dataclass
class SerialPortConfig:
    """Represents a serial port configuration."""
    port: str
    speed: int = 9600
    data_bits: int = 8
    stop_bits: int = 1
    parity: str = "none"


class HardwareConfigManager:
    """
    Manages hardware-related system configuration.

    Handles /etc/adjtime, /etc/sensors.conf, /etc/serial.conf,
    /etc/modules.conf, /etc/modprobe.d/, and /etc/modprobe.conf.
    """

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.modprobe_d_path = self.etc_path / "modprobe.d"

    def initialize(self) -> bool:
        """Create all hardware configuration files with defaults."""
        try:
            self._create_adjtime()
            self._create_sensors_conf()
            self._create_serial_conf()
            self._create_fdprm()
            self._create_isapnp_conf()
            self._create_modules_conf()
            self._create_modprobe_conf()
            self._create_modprobe_d()
            log.info("Initialized hardware configuration files")
            return True
        except Exception as e:
            log.error("Failed to initialize hardware config: %s", e)
            return False

    # ── /etc/adjtime ─────────────────────────────────────────────────────

    def _create_adjtime(self) -> None:
        """Create /etc/adjtime (hardware clock adjustment time)."""
        filepath = self.etc_path / "adjtime"
        if filepath.exists():
            return
        content = """# /etc/adjtime - Hardware clock adjustment time
# UmerOS Hardware Clock Configuration
# This file is used by hwclock to determine the hardware clock mode.
#
# Format:
#   line 1: current hardware clock time (seconds since epoch)
#   line 2: last calculated drift (seconds)
#   line 3: "UTC" or "LOCAL" (clock mode)

0 0 0.0
0 0 0.0
UTC
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/adjtime")

    # ── /etc/sensors.conf ────────────────────────────────────────────────

    def _create_sensors_conf(self) -> None:
        """Create /etc/sensors.conf (hardware sensors configuration)."""
        filepath = self.etc_path / "sensors.conf"
        if filepath.exists():
            return
        content = """# /etc/sensors.conf - Hardware sensors configuration
# UmerOS Sensors Configuration
# See sensors.conf(5) for details.

# Chip configuration
# chip "coretemp-isa-0000"
#     label temp1 "CPU Core"

# Chip configuration
# chip "it8718-isa-0290"
#     label temp1 "System"
#     label temp2 "CPU"
#     label temp3 "AUX"

# Voltage configuration
# chip "coretemp-isa-0000"
#     label in0 "Vcore"
#     set in0_min 0.8
#     set in0_max 1.4

# Fan configuration
# chip "coretemp-isa-0000"
#     label fan1 "CPU Fan"
#     set fan1_min 1000
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/sensors.conf")

    # ── /etc/serial.conf ─────────────────────────────────────────────────

    def _create_serial_conf(self) -> None:
        """Create /etc/serial.conf (serial port configuration)."""
        filepath = self.etc_path / "serial.conf"
        if filepath.exists():
            return
        content = """# /etc/serial.conf - Serial port configuration
# UmerOS Serial Port Configuration
# See setserial(8) for details.
#
# Format: port uart irq flags baud_base close_delay closing_wait
#
# Port 0 (COM1)
ttyS0 uart 16550 port 0x3F8 irq 4 baud_base 115200

# Port 1 (COM2)
ttyS1 uart 16550 port 0x2F8 irq 3 baud_base 115200

# Port 2 (COM3)
ttyS2 uart 16550 port 0x3E8 irq 4 baud_base 115200

# Port 3 (COM4)
ttyS3 uart 16550 port 0x2E8 irq 3 baud_base 115200
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/serial.conf")

    # ── /etc/fdprm ───────────────────────────────────────────────────────

    def _create_fdprm(self) -> None:
        """Create /etc/fdprm (floppy disk parameter definitions)."""
        filepath = self.etc_path / "fdprm"
        if filepath.exists():
            return
        content = """# /etc/fdprm - Floppy disk parameter definitions
# UmerOS Floppy Disk Parameters
# Format: name tracks head sect率 gap
#
# 360KB 5.25"
360,40,2,9,0x2C,0x0B,0x65,0x30,0

# 720KB 3.5"
720,80,2,9,0x2C,0x16,0x65,0x30,0

# 1.2MB 5.25"
1200,80,2,15,0x2C,0x23,0x71,0x30,0

# 1.44MB 3.5"
1440,80,2,18,0x2C,0x1B,0x6B,0x50,0

# 2.88MB 3.5"
2880,80,2,36,0x2C,0x1B,0x53,0x50,0
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/fdprm")

    # ── /etc/isapnp.conf ─────────────────────────────────────────────────

    def _create_isapnp_conf(self) -> None:
        """Create /etc/isapnp.conf (ISA PnP device configuration)."""
        filepath = self.etc_path / "isapnp.conf"
        if filepath.exists():
            return
        content = """# /etc/isapnp.conf - ISA PnP device configuration
# UmerOS ISA PnP Configuration
# See isapnp.conf(5) for details.

# Card 1: Sound card
#(SETUP 0x100
#  (IO 0x220-0x22F)
#  (IO 0x300-0x301)
#  (IRQ 5)
#  (DMA 1)
#  (DMA 5)
#)

# Card 2: Modem
#(SETUP 0x200
#  (IO 0x2F8-0x2FF)
#  (IRQ 3)
#)
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/isapnp.conf")

    # ── /etc/modules.conf ────────────────────────────────────────────────

    def _create_modules_conf(self) -> None:
        """Create /etc/modules.conf (kernel module aliases)."""
        filepath = self.etc_path / "modules.conf"
        if filepath.exists():
            return
        content = """# /etc/modules.conf - Kernel module aliases
# UmerOS Module Configuration
# See modules.conf(5) for details.

# Sound module aliases
alias sound-slot-0 snd-intel8x0
alias sound-slot-1 snd-intel8x0

# Network module aliases
alias eth0 e1000
alias eth1 rtl8139

# USB module aliases
alias usb-controller ehci-hcd
alias usb-controller1 uhci-hcd

# SCSI module aliases
alias scsi_hostadapter mptspi

# Parallel port module aliases
alias parport_lowlevel parport_pc
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/modules.conf")

    # ── /etc/modprobe.conf ───────────────────────────────────────────────

    def _create_modprobe_conf(self) -> None:
        """Create /etc/modprobe.conf (modprobe configuration)."""
        filepath = self.etc_path / "modprobe.conf"
        if filepath.exists():
            return
        content = """# /etc/modprobe.conf - Modprobe configuration
# UmerOS Modprobe Configuration
# See modprobe.conf(5) for details.

# Sound module options
options snd-intel8x0 index=0

# Network module options
options e1000 IntMode=0

# USB module options
options ehci-hcd log2_irq_thresh=0

# SCSI module options
options mptspi max_sectors=8192

# Blacklist modules (prevent loading)
#blacklist nouveau
#blacklist nvidia
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/modprobe.conf")

    # ── /etc/modprobe.d/ ─────────────────────────────────────────────────

    def _create_modprobe_d(self) -> None:
        """Create /etc/modprobe.d/ directory with common configurations."""
        self.modprobe_d_path.mkdir(parents=True, exist_ok=True)

        configs = {
            "aliases.conf": """# /etc/modprobe.d/aliases.conf
# Module aliases

alias eth0 e1000
alias eth1 rtl8139
alias sound-slot-0 snd-intel8x0
""",
            "blacklist.conf": """# /etc/modprobe.d/blacklist.conf
# Blacklisted modules

# Blacklist firewire
blacklist firewire-ohci
blacklist firewire-sbp2

# Blacklist iSCSI
blacklist iscsi_tcp

# Blacklist USB storage (optional)
#blacklist usb-storage
""",
            "options.conf": """# /etc/modprobe.d/options.conf
# Module options

options snd-intel8x0 index=0
options e1000 IntMode=0
""",
        }

        for filename, content in configs.items():
            filepath = self.modprobe_d_path / filename
            if not filepath.exists():
                filepath.write_text(content, encoding="utf-8")
                log.debug("Created /etc/modprobe.d/%s", filename)

    # ── Utility Methods ──────────────────────────────────────────────────

    def parse_modules_conf(self) -> List[ModuleAlias]:
        """Parse /etc/modules.conf into a list of aliases."""
        filepath = self.etc_path / "modules.conf"
        if not filepath.exists():
            return []
        aliases = []
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 3 and parts[0] == "alias":
                aliases.append(ModuleAlias(
                    alias=parts[1],
                    module=parts[2],
                ))
        return aliases

    def parse_serial_conf(self) -> List[SerialPortConfig]:
        """Parse /etc/serial.conf into a list of port configurations."""
        filepath = self.etc_path / "serial.conf"
        if not filepath.exists():
            return []
        configs = []
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                port = parts[0]
                speed = 9600
                for i, part in enumerate(parts):
                    if part == "baud_base" and i + 1 < len(parts):
                        try:
                            speed = int(parts[i + 1])
                        except ValueError:
                            pass
                configs.append(SerialPortConfig(port=port, speed=speed))
        return configs

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of hardware configuration."""
        return {
            "adjtime_exists": (self.etc_path / "adjtime").exists(),
            "sensors_conf_exists": (self.etc_path / "sensors.conf").exists(),
            "serial_conf_exists": (self.etc_path / "serial.conf").exists(),
            "fdprm_exists": (self.etc_path / "fdprm").exists(),
            "isapnp_conf_exists": (self.etc_path / "isapnp.conf").exists(),
            "modules_conf_exists": (self.etc_path / "modules.conf").exists(),
            "modprobe_conf_exists": (self.etc_path / "modprobe.conf").exists(),
            "modprobe_d_exists": self.modprobe_d_path.exists(),
        }
