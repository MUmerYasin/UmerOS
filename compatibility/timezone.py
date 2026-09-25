"""
Umer OS /compatibility/timezone — Win32 SYSTEMTIME + TimeZoneInformation
========================================================================

Pure-Python implementation of the Win32 time surfaces used by every
installer and clock-aware application:

* ``GetSystemTime`` / ``GetLocalTime`` / ``SetSystemTime``
* ``SystemTimeToFileTime`` / ``FileTimeToSystemTime``
* ``GetTimeZoneInformation`` / ``SetTimeZoneInformation``
* ``GetTickCount`` (re-exported from :mod:`compatibility.win_kernel32`)
* ``FileTimeToDosDateTime`` / ``DosDateTimeToFileTime``

The key records:

* :class:`SystemTime` — 16-byte packed ``SYSTEMTIME`` (year, month,
  day, hour, minute, second, millisecond, weekday).
* :class:`FileTime` — 64-bit count of 100-nanosecond intervals since
  the Win32 epoch (1601-01-01).
* :class:`TimeZoneInformation` — full Win32 ``TIME_ZONE_INFORMATION``
  (bias + standard + daylight rule).

This module has *no* host-side dependencies beyond the standard
library: it computes the Win32 epoch from a hard-coded base
1601-01-01 UTC.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/api/minwinbase/ns-minwinbase-systemtime
* https://learn.microsoft.com/en-us/windows/win32/api/timezoneapi/

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import datetime as _dt
import logging
import struct
import time as _time
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("UmerOS.Compat.Timezone")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Win32 FILETIME epoch = 1601-01-01 00:00:00 UTC
_FILETIME_EPOCH = _dt.datetime(1601, 1, 1, tzinfo=_dt.timezone.utc)
_UNIX_EPOCH = _dt.datetime(1970, 1, 1, tzinfo=_dt.timezone.utc)
_100NS_PER_MS = 10_000
_100NS_PER_S  = 10_000_000     # 10^7 ticks per second

# Win32 error / return codes.
ERROR_SUCCESS              = 0
ERROR_INVALID_PARAMETER    = 87
TIME_ZONE_ID_INVALID       = 0xFFFFFFFF
TIME_ZONE_ID_STANDARD      = 1
TIME_ZONE_ID_DAYLIGHT      = 2
TIME_ZONE_ID_UNKNOWN       = 0

# Conversion factors.
_SECS_PER_DAY = 86400


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SystemTime:
    """Win32 ``SYSTEMTIME`` (16 bytes packed)."""

    year: int = 1970
    month: int = 1              # 1..12
    day_of_week: int = 0        # 0..6 (Sunday = 0)
    day: int = 1                # 1..31
    hour: int = 0               # 0..23
    minute: int = 0             # 0..59
    second: int = 0             # 0..59
    millisecond: int = 0        # 0..999

    def to_datetime(self) -> _dt.datetime:
        return _dt.datetime(self.year, self.month, self.day,
                            self.hour, self.minute, self.second,
                            self.millisecond * 1000)

    @classmethod
    def from_datetime(cls, dt: _dt.datetime) -> "SystemTime":
        return cls(
            year=dt.year, month=dt.month,
            day=dt.day, day_of_week=(dt.weekday() + 1) % 7,
            hour=dt.hour, minute=dt.minute,
            second=dt.second, millisecond=dt.microsecond // 1000,
        )

    def to_bytes(self) -> bytes:
        return struct.pack("<HHHHHHHH",
                           self.year, self.month,
                           self.day_of_week, self.day,
                           self.hour, self.minute,
                           self.second, self.millisecond)

    @classmethod
    def from_bytes(cls, data: bytes) -> "SystemTime":
        (y, m, dow, d, h, mi, s, ms) = struct.unpack_from(
            "<HHHHHHHH", data, 0)
        return cls(y, m, dow, d, h, mi, s, ms)


@dataclass(frozen=True)
class FileTime:
    """Win32 ``FILETIME`` (64-bit 100-ns count since 1601-01-01)."""

    value: int

    @classmethod
    def now(cls) -> "FileTime":
        delta = _dt.datetime.now(_dt.timezone.utc) - _FILETIME_EPOCH
        ticks = int(delta.total_seconds() * _100NS_PER_S)
        return cls(ticks + _dt.datetime.now(_dt.timezone.utc).microsecond
                   * 10)

    @classmethod
    def from_datetime(cls, dt: _dt.datetime) -> "FileTime":
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.timezone.utc)
        delta = dt - _FILETIME_EPOCH
        return cls(int(delta.total_seconds() * _100NS_PER_S))

    def to_datetime(self) -> _dt.datetime:
        seconds, ns = divmod(self.value, _100NS_PER_S)
        return _FILETIME_EPOCH + _dt.timedelta(seconds=seconds,
                                                microseconds=ns // 10)

    def to_dword_pair(self) -> tuple:
        """Split into the (low, high) DWORDs the Win32 API exposes."""
        return (self.value & 0xFFFFFFFF, (self.value >> 32) & 0xFFFFFFFF)

    @classmethod
    def from_dword_pair(cls, low: int, high: int) -> "FileTime":
        return cls((high << 32) | (low & 0xFFFFFFFF))

    def to_bytes(self) -> bytes:
        lo, hi = self.to_dword_pair()
        return struct.pack("<II", lo, hi)

    @classmethod
    def from_bytes(cls, data: bytes) -> "FileTime":
        lo, hi = struct.unpack_from("<II", data, 0)
        return cls.from_dword_pair(lo, hi)


@dataclass(frozen=True)
class TimeZoneInformation:
    """Win32 ``TIME_ZONE_INFORMATION``.

    The structure holds a fixed ``Bias`` (whole-minutes offset for
    standard time) plus two ``SystemTime`` rules for the transitions
    into and out of daylight saving time.  Real Win32 also embeds a
    fixed-length display-name string; we keep that as a simple
    Python ``str``.
    """

    bias: int = 0                   # minutes west of UTC (standard)
    standard_name: str = ""
    standard: SystemTime = field(default_factory=SystemTime)
    standard_bias: int = 0
    daylight_name: str = ""
    daylight: SystemTime = field(default_factory=SystemTime)
    daylight_bias: int = -60

    def bias_seconds(self) -> int:
        return self.bias * 60

    def current_offset_minutes(self) -> int:
        now = _dt.datetime.utcnow()
        in_dst = self._is_in_daylight(now)
        return self.bias + (self.daylight_bias if in_dst else self.standard_bias)

    def _is_in_daylight(self, now: _dt.datetime) -> bool:
        # Crude heuristic: treat the standard rule as a no-op and
        # assume the local offset is just the bias + daylight_bias
        # for the months 3..10 (March to October in the northern
        # hemisphere).  A real implementation walks the rule.
        return 3 <= now.month <= 10

    def to_bytes(self) -> bytes:
        b = struct.pack("<l", self.bias)
        b += _wide_str(self.standard_name) + b"\x00\x00"
        b += self.standard.to_bytes()
        b += struct.pack("<l", self.standard_bias)
        b += _wide_str(self.daylight_name) + b"\x00\x00"
        b += self.daylight.to_bytes()
        b += struct.pack("<l", self.daylight_bias)
        return b

    @classmethod
    def from_bytes(cls, data: bytes) -> "TimeZoneInformation":
        bias = struct.unpack_from("<l", data, 0)[0]
        sn, after = _read_wide_str(data, 4)
        std = SystemTime.from_bytes(data[after:after + 16])
        std_bias = struct.unpack_from("<l", data, after + 16)[0]
        dn, after2 = _read_wide_str(data, after + 20)
        dl = SystemTime.from_bytes(data[after2:after2 + 16])
        dl_bias = struct.unpack_from("<l", data, after2 + 16)[0]
        return cls(bias=bias, standard_name=sn, standard=std,
                   standard_bias=std_bias, daylight_name=dn,
                   daylight=dl, daylight_bias=dl_bias)


# ---------------------------------------------------------------------------
# Helpers for the wide-string fields inside TIME_ZONE_INFORMATION.
# ---------------------------------------------------------------------------

def _wide_str(s: str, length: int = 32) -> bytes:
    """Encode a name field as a fixed-width WCHAR buffer (terminated)."""
    encoded = s.encode("utf-16-le")
    if len(encoded) >= length * 2:
        encoded = encoded[:length * 2 - 2]
    encoded += b"\x00\x00"
    encoded += b"\x00" * (length * 2 - len(encoded))
    return encoded


def _read_wide_str(data: bytes, off: int) -> tuple:
    """Read a 32-WCHAR terminated string starting at ``off``."""
    end = off
    while end + 1 < len(data):
        if data[end] == 0 and data[end + 1] == 0:
            break
        end += 2
    text = data[off:end].decode("utf-16-le", errors="replace")
    return text, end + 2


# ---------------------------------------------------------------------------
# Win32 API surface
# ---------------------------------------------------------------------------

def GetSystemTime() -> SystemTime:
    return SystemTime.from_datetime(
        _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0))


def GetLocalTime() -> SystemTime:
    return SystemTime.from_datetime(_dt.datetime.now().replace(microsecond=0))


def SetSystemTime(st: SystemTime) -> bool:
    """Setting the system clock is privileged; we accept any input."""
    log.info("SetSystemTime(%s)", st)
    return True


def GetTickCount() -> int:
    """Return the number of milliseconds since an arbitrary origin.

    Implemented via :func:`win_kernel32.GetTickCount` if available,
    otherwise falls back to :func:`time.monotonic`.
    """
    try:
        from .win_kernel32 import GetTickCount as _g
        return _g()
    except Exception:
        return int(_time.monotonic() * 1000) & 0xFFFFFFFF


def SystemTimeToFileTime(st: SystemTime) -> Optional[FileTime]:
    try:
        dt = st.to_datetime().replace(tzinfo=_dt.timezone.utc)
        return FileTime.from_datetime(dt)
    except ValueError:
        return None


def FileTimeToSystemTime(ft: FileTime) -> SystemTime:
    return SystemTime.from_datetime(ft.to_datetime())


def GetTimeZoneInformation() -> TimeZoneInformation:
    """Return the local time zone as a Win32 ``TIME_ZONE_INFORMATION``.

    We derive an approximation from the offset encoded in
    :data:`time.timezone` and the rule that Windows put in place for
    most US/EU systems.  Tests can construct other values
    explicitly.
    """
    bias_minutes = -_time.timezone // 60
    return TimeZoneInformation(bias=bias_minutes,
                               standard_name="Standard Time",
                               standard=SystemTime(month=11, day=1),
                               standard_bias=0,
                               daylight_name="Daylight Time",
                               daylight=SystemTime(month=3, day=2),
                               daylight_bias=-60)


def SetTimeZoneInformation(tz: TimeZoneInformation) -> bool:
    log.info("SetTimeZoneInformation(%s)", tz)
    return True


def FileTimeToDosDateTime(ft: FileTime) -> tuple:
    """Convert a Win32 ``FILETIME`` to a packed MS-DOS date/time pair."""
    dt = ft.to_datetime()
    if dt.year < 1980 or dt.year > 2107:
        return (0, 0)
    dos_date = ((dt.year - 1980) << 9) | (dt.month << 5) | dt.day
    dos_time = (dt.hour << 11) | (dt.minute << 5) | (dt.second // 2)
    return (dos_date, dos_time)


def DosDateTimeToFileTime(dos_date: int, dos_time: int) -> FileTime:
    """Inverse of :func:`FileTimeToDosDateTime`.

    MS-DOS encodes the year as ``(year - 1980) & 0x7F``, so the
    7-bit field covers 1980..2107.
    """
    year = (dos_date >> 9) & 0x7F
    year += 1980
    month = (dos_date >> 5) & 0x0F
    day = dos_date & 0x1F
    hour = (dos_time >> 11) & 0x1F
    minute = (dos_time >> 5) & 0x3F
    second = (dos_time & 0x1F) * 2
    dt = _dt.datetime(year, month, day, hour, minute, second,
                       tzinfo=_dt.timezone.utc)
    return FileTime.from_datetime(dt)


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

EXPORTS = {
    "GetSystemTime": GetSystemTime,
    "GetLocalTime": GetLocalTime,
    "SetSystemTime": SetSystemTime,
    "GetTickCount": GetTickCount,
    "SystemTimeToFileTime": SystemTimeToFileTime,
    "FileTimeToSystemTime": FileTimeToSystemTime,
    "GetTimeZoneInformation": GetTimeZoneInformation,
    "SetTimeZoneInformation": SetTimeZoneInformation,
    "FileTimeToDosDateTime": FileTimeToDosDateTime,
    "DosDateTimeToFileTime": DosDateTimeToFileTime,
}


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    st = GetSystemTime()
    if st.year < 2024:
        return False
    ft = SystemTimeToFileTime(st)
    if ft is None:
        return False
    st2 = FileTimeToSystemTime(ft)
    if (st2.year, st2.month, st2.day, st2.hour, st2.minute, st2.second) != \
       (st.year, st.month, st.day, st.hour, st.minute, st.second):
        return False
    # FileTime <-> datetime symmetry.
    dt = _dt.datetime(2025, 6, 15, 12, 34, 56, tzinfo=_dt.timezone.utc)
    ft = FileTime.from_datetime(dt)
    if ft.to_datetime() != dt:
        return False
    # DOS round-trip.
    ft = FileTime.from_datetime(_dt.datetime(2024, 12, 31, 23, 59, 58,
                                            tzinfo=_dt.timezone.utc))
    dos_date, dos_time = FileTimeToDosDateTime(ft)
    ft2 = DosDateTimeToFileTime(dos_date, dos_time)
    if ft2.to_datetime().year != 2024:
        return False
    # TimeZoneInformation round-trip.
    tz = GetTimeZoneInformation()
    raw = tz.to_bytes()
    tz2 = TimeZoneInformation.from_bytes(raw)
    if tz2.bias != tz.bias:
        return False
    if tz2.standard_name != tz.standard_name:
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
