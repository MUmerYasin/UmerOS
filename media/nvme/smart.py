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
UmerOS /media/nvme - NVMe SMART/Health Log
==========================================

Parses the NVMe SMART/Health log page (Log ID ``0x02``, 512
bytes per NVM Express 1.4/2.0 - layout of ``struct nvme_smart_log``
in ``linux/nvme.h``), decodes the critical-warning bitmap and
assesses drive health against configurable thresholds.

Layout highlights (little-endian):

* byte 0        critical warning bitmap
* bytes 1-2     composite temperature (Kelvin)
* byte 3        available spare (%)
* byte 4        available spare threshold (%)
* byte 5        percentage used (0-100)
* bytes 6-31    reserved
* bytes 32-47   data units read (512-byte units x 1000)
* bytes 48-63   data units written
* bytes 64-79   host read commands
* bytes 80-95   host write commands
* bytes 96-111  controller busy time (minutes)
* bytes 112-127 power cycles
* bytes 128-143 power on hours
* bytes 144-159 unsafe shutdowns
* bytes 160-175 media and data integrity errors
* bytes 176-191 number of error information log entries
* bytes 192-207 warning composite temperature time (minutes)
* bytes 208-223 critical composite temperature time (minutes)
* bytes 224-239 temperature sensors 1-8 (8 x uint16 Kelvin)
* bytes 240-303 thermal management transitions / total time

Pure Python, no third-party packages.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

SMART_LOG_SIZE = 512
SMART_LOG_ID = 0x02


def kelvin_to_celsius(kelvin: float) -> float:
    """Convert a NVMe Kelvin temperature to Celsius."""
    return kelvin - 273.15


def _u16(data: bytes, off: int) -> int:
    return int.from_bytes(data[off:off + 2], "little")


def _u128(data: bytes, off: int) -> int:
    return int.from_bytes(data[off:off + 16], "little")


@dataclass
class SMARTHealthLog:
    """Parsed SMART/Health log page (Log ID 0x02)."""

    critical_warning: int = 0
    temperature_k: int = 0
    available_spare: int = 100
    available_spare_threshold: int = 10
    percent_used: int = 0
    data_units_read: int = 0
    data_units_written: int = 0
    host_reads: int = 0
    host_writes: int = 0
    controller_busy_time_min: int = 0
    power_cycles: int = 0
    power_on_hours: int = 0
    unsafe_shutdowns: int = 0
    media_errors: int = 0
    num_err_log_entries: int = 0
    warning_temp_time_min: int = 0
    critical_temp_time_min: int = 0
    temperature_sensors_k: List[int] = field(default_factory=list)
    thm_temp1_trans_count: int = 0
    thm_temp2_trans_count: int = 0
    thm_total_time1_min: int = 0
    thm_total_time2_min: int = 0

    @property
    def temperature_c(self) -> float:
        return kelvin_to_celsius(self.temperature_k)

    @property
    def remaining_life_pct(self) -> int:
        return 100 - self.percent_used


def parse_smart_log(data: bytes) -> SMARTHealthLog:
    """Parse a raw SMART/Health log page (exactly 512 bytes)."""
    if len(data) < SMART_LOG_SIZE:
        raise ValueError(
            f"SMART/Health log must be at least {SMART_LOG_SIZE} bytes, "
            f"got {len(data)}"
        )
    smart = SMARTHealthLog()
    smart.critical_warning = data[0]
    smart.temperature_k = _u16(data, 1)
    smart.available_spare = data[3]
    smart.available_spare_threshold = data[4]
    smart.percent_used = data[5]
    smart.data_units_read = _u128(data, 32)
    smart.data_units_written = _u128(data, 48)
    smart.host_reads = _u128(data, 64)
    smart.host_writes = _u128(data, 80)
    smart.controller_busy_time_min = _u128(data, 96)
    smart.power_cycles = _u128(data, 112)
    smart.power_on_hours = _u128(data, 128)
    smart.unsafe_shutdowns = _u128(data, 144)
    smart.media_errors = _u128(data, 160)
    smart.num_err_log_entries = _u128(data, 176)
    smart.warning_temp_time_min = _u128(data, 192)
    smart.critical_temp_time_min = _u128(data, 208)
    smart.temperature_sensors_k = list(
        struct.unpack_from("<8H", data, 224)
    )
    smart.thm_temp1_trans_count = _u128(data, 240)
    smart.thm_temp2_trans_count = _u128(data, 256)
    smart.thm_total_time1_min = _u128(data, 272)
    smart.thm_total_time2_min = _u128(data, 288)
    return smart


def critical_warning_reasons(critical_warning: int) -> List[str]:
    """Decode the critical-warning bitmap (byte 0) into human reasons."""
    reasons: List[str] = []
    if critical_warning & 0x01:
        reasons.append("available spare below threshold")
    if critical_warning & 0x02:
        reasons.append("temperature above threshold")
    if critical_warning & 0x04:
        reasons.append("NVM subsystem reliability degraded")
    if critical_warning & 0x08:
        reasons.append("media in read-only mode")
    if critical_warning & 0x10:
        reasons.append("volatile memory backup failed")
    return reasons


class HealthLevel(Enum):
    """Overall NVMe health assessment."""

    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class HealthThresholds:
    """Thresholds for :func:`assess_health`."""

    remaining_life_warn_pct: int = 20
    remaining_life_critical_pct: int = 10


@dataclass
class NVMeHealthReport:
    """Result of a health assessment."""

    level: HealthLevel
    remaining_life_pct: int
    temperature_c: float
    reasons: List[str] = field(default_factory=list)


def assess_health(
    smart: SMARTHealthLog,
    wctemp_k: Optional[int] = None,
    cctemp_k: Optional[int] = None,
    thresholds: Optional[HealthThresholds] = None,
) -> NVMeHealthReport:
    """Assess drive health from a SMART/Health log.

    Args:
        smart:    Parsed SMART/Health log page.
        wctemp_k: Warning composite temperature threshold (Kelvin),
            typically from Identify Controller byte 236.
        cctemp_k: Critical composite temperature threshold (Kelvin),
            typically from Identify Controller byte 238.
        thresholds: Remaining-life thresholds (default 20% warn / 10% critical).

    Returns:
        An :class:`NVMeHealthReport` with a health level and reasons.
    """
    th = thresholds if thresholds is not None else HealthThresholds()
    reasons: List[str] = []
    level = HealthLevel.OK

    if smart.available_spare < smart.available_spare_threshold or (
        smart.critical_warning & 0x01
    ):
        level = HealthLevel.CRITICAL
        reasons.append(
            f"available spare {smart.available_spare}% below threshold "
            f"{smart.available_spare_threshold}%"
        )
    if cctemp_k is not None and smart.temperature_k >= cctemp_k:
        level = HealthLevel.CRITICAL
        reasons.append(
            f"temperature {smart.temperature_c:.1f} C at or above critical "
            f"threshold {kelvin_to_celsius(cctemp_k):.1f} C"
        )
    if smart.remaining_life_pct <= th.remaining_life_critical_pct:
        level = HealthLevel.CRITICAL
        reasons.append(
            f"remaining life {smart.remaining_life_pct}% at or below critical "
            f"threshold {th.remaining_life_critical_pct}%"
        )

    if level != HealthLevel.CRITICAL:
        if smart.critical_warning:
            level = HealthLevel.WARNING
            reasons.extend(critical_warning_reasons(smart.critical_warning))
        if wctemp_k is not None and smart.temperature_k >= wctemp_k:
            level = HealthLevel.WARNING
            reasons.append(
                f"temperature {smart.temperature_c:.1f} C at or above warning "
                f"threshold {kelvin_to_celsius(wctemp_k):.1f} C"
            )
        if smart.media_errors:
            level = HealthLevel.WARNING
            reasons.append(f"{smart.media_errors} media and data integrity errors")
        if smart.unsafe_shutdowns:
            level = HealthLevel.WARNING
            reasons.append(f"{smart.unsafe_shutdowns} unsafe shutdowns")
        if smart.remaining_life_pct <= th.remaining_life_warn_pct:
            level = HealthLevel.WARNING
            reasons.append(
                f"remaining life {smart.remaining_life_pct}% at or below warning "
                f"threshold {th.remaining_life_warn_pct}%"
            )

    reasons = list(dict.fromkeys(reasons))
    return NVMeHealthReport(
        level=level,
        remaining_life_pct=smart.remaining_life_pct,
        temperature_c=smart.temperature_c,
        reasons=reasons,
    )


def _selftest() -> bool:
    """Run a basic self-test for this module (synthetic log pages)."""
    log = bytearray(SMART_LOG_SIZE)
    log[0] = 0
    log[1:3] = (300).to_bytes(2, "little")
    log[3] = 100
    log[4] = 10
    log[5] = 0
    log[32:48] = (12345).to_bytes(16, "little")
    log[128:144] = (9999).to_bytes(16, "little")

    smart = parse_smart_log(bytes(log))
    assert smart.critical_warning == 0
    assert smart.temperature_k == 300
    assert abs(smart.temperature_c - 26.85) < 0.01, smart.temperature_c
    assert smart.available_spare == 100
    assert smart.percent_used == 0
    assert smart.data_units_read == 12345
    assert smart.power_on_hours == 9999
    assert smart.remaining_life_pct == 100
    assert len(smart.temperature_sensors_k) == 8
    assert critical_warning_reasons(0) == []
    assert critical_warning_reasons(0x1F) == [
        "available spare below threshold",
        "temperature above threshold",
        "NVM subsystem reliability degraded",
        "media in read-only mode",
        "volatile memory backup failed",
    ]

    report = assess_health(smart)
    assert report.level == HealthLevel.OK, report

    warn_log = bytearray(log)
    warn_log[5] = 85
    warn_log[160:176] = (3).to_bytes(16, "little")
    warn_smart = parse_smart_log(bytes(warn_log))
    warn_report = assess_health(warn_smart)
    assert warn_report.level == HealthLevel.WARNING, warn_report
    assert warn_report.remaining_life_pct == 15
    assert any("media" in r for r in warn_report.reasons)

    crit_log = bytearray(log)
    crit_log[0] = 0x01
    crit_log[3] = 5
    crit_log[4] = 10
    crit_smart = parse_smart_log(bytes(crit_log))
    crit_report = assess_health(crit_smart)
    assert crit_report.level == HealthLevel.CRITICAL, crit_report

    hot_log = bytearray(log)
    hot_log[1:3] = (353).to_bytes(2, "little")
    hot_smart = parse_smart_log(bytes(hot_log))
    hot_report = assess_health(hot_smart, wctemp_k=343, cctemp_k=358)
    assert hot_report.level == HealthLevel.WARNING, hot_report
    assert any("temperature" in r for r in hot_report.reasons)

    critical_temp_log = bytearray(log)
    critical_temp_log[1:3] = (360).to_bytes(2, "little")
    critical_temp_smart = parse_smart_log(bytes(critical_temp_log))
    critical_temp_report = assess_health(
        critical_temp_smart, wctemp_k=343, cctemp_k=358
    )
    assert critical_temp_report.level == HealthLevel.CRITICAL

    try:
        parse_smart_log(b"short")
    except ValueError:
        pass
    else:
        raise AssertionError("short SMART log must raise ValueError")

    print("selftest OK")
    return True


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(0 if _selftest() else 1)
