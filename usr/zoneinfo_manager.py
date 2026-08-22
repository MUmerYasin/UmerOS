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
UmerOS Timezone Manager (/usr/share/zoneinfo)
==============================================
Timezone data and definitions.

Reference: Filesystem Hierarchy - /usr/share/zoneinfo
  /usr/share/zoneinfo contains timezone data compiled from the
  IANA tz database. It includes timezone rules for all regions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ─── Constants ───────────────────────────────────────────────────────────────

ZONEINFO_PATH = "/usr/share/zoneinfo"

CONTINENTS = [
    "Africa", "America", "Antarctica", "Arctic", "Asia",
    "Atlantic", "Australia", "Europe", "Indian", "Pacific",
]

TIMEZONE_CATEGORIES = {
    "CONTINENTAL": "Regional timezone definitions",
    "POSIX": "POSIX timezone strings",
    "LEAP": "Leap second data",
    "TAB": "Timezone abbreviation tables",
    "RIGHT": "Leap-second-aware timezone data",
}

COMMON_TIMEZONES = {
    "America/New_York": "Eastern Time (US & Canada)",
    "America/Chicago": "Central Time (US & Canada)",
    "America/Denver": "Mountain Time (US & Canada)",
    "America/Los_Angeles": "Pacific Time (US & Canada)",
    "America/Anchorage": "Alaska Time",
    "Pacific/Honolulu": "Hawaii Time",
    "Europe/London": "Greenwich Mean Time",
    "Europe/Paris": "Central European Time",
    "Europe/Berlin": "Central European Time",
    "Europe/Moscow": "Moscow Time",
    "Asia/Tokyo": "Japan Standard Time",
    "Asia/Shanghai": "China Standard Time",
    "Asia/Kolkata": "India Standard Time",
    "Asia/Dubai": "Gulf Standard Time",
    "Asia/Singapore": "Singapore Time",
    "Asia/Seoul": "Korea Standard Time",
    "Australia/Sydney": "Australian Eastern Time",
    "Australia/Perth": "Australian Western Time",
    "Pacific/Auckland": "New Zealand Time",
    "Pacific/Fiji": "Fiji Time",
    "Africa/Cairo": "Eastern European Time",
    "Africa/Lagos": "West Africa Time",
    "Africa/Johannesburg": "South Africa Standard Time",
    "America/Sao_Paulo": "Brasilia Time",
    "America/Argentina/Buenos_Aires": "Argentina Time",
    "America/Mexico_City": "Central Time (Mexico)",
    "America/Toronto": "Eastern Time (Canada)",
    "Europe/Istanbul": "Turkey Time",
    "Asia/Hong_Kong": "Hong Kong Time",
    "Asia/Taipei": "Taipei Time",
    "Asia/Bangkok": "Indochina Time",
}


# ─── Enums ───────────────────────────────────────────────────────────────────

class ZoneCategory(IntEnum):
    """Timezone categories."""
    CONTINENTAL = 1
    POSIX = 2
    LEAP = 3
    TAB = 4
    RIGHT = 5


class DSTRule(IntEnum):
    """Daylight saving time rules."""
    US = 1
    EU = 2
    GB = 3
    AUS = 4
    NONE = 5


class ZoneStatus(IntEnum):
    """Timezone status."""
    ACTIVE = 1
    DEPRECATED = 2
    REMOVED = 3


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class TimezoneEntry:
    """Represents a timezone definition."""
    name: str
    path: str
    description: str = ""
    utc_offset: int = 0
    dst_offset: int = 0
    dst_rule: DSTRule = DSTRule.NONE
    status: ZoneStatus = ZoneStatus.ACTIVE
    continent: str = ""
    country: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "description": self.description,
            "utc_offset": self.utc_offset,
            "dst_offset": self.dst_offset,
            "dst_rule": self.dst_rule.name,
            "status": self.status.name,
            "continent": self.continent,
            "country": self.country,
        }


@dataclass
class LeapSecond:
    """A leap second entry."""
    timestamp: int
    offset: int
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "offset": self.offset,
            "description": self.description,
        }


@dataclass
class ZoneAbbreviation:
    """A timezone abbreviation."""
    abbreviation: str
    timezone: str
    utc_offset: int = 0
    dst: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "abbreviation": self.abbreviation,
            "timezone": self.timezone,
            "utc_offset": self.utc_offset,
            "dst": self.dst,
        }


# ─── Global State ────────────────────────────────────────────────────────────

_global_zoneinfo_manager: Optional["ZoneinfoManager"] = None


# ─── Main Manager Class ─────────────────────────────────────────────────────

class ZoneinfoManager:
    """Manages /usr/share/zoneinfo - timezone data."""

    def __init__(self) -> None:
        self._timezones: Dict[str, TimezoneEntry] = {}
        self._leap_seconds: List[LeapSecond] = []
        self._abbreviations: Dict[str, ZoneAbbreviation] = {}
        self._default_timezone: str = "UTC"
        self._initialize_default_timezones()
        self._initialize_default_abbreviations()

    def _initialize_default_timezones(self) -> None:
        """Initialize with common timezones."""
        for tz_name, desc in COMMON_TIMEZONES.items():
            parts = tz_name.split("/")
            continent = parts[0] if len(parts) > 0 else ""
            country = parts[1] if len(parts) > 1 else tz_name
            entry = TimezoneEntry(
                name=tz_name,
                path=f"/usr/share/zoneinfo/{tz_name}",
                description=desc,
                continent=continent,
                country=country,
            )
            self._timezones[tz_name] = entry

    def _initialize_default_abbreviations(self) -> None:
        """Initialize common timezone abbreviations."""
        abbrevs = [
            ("UTC", "UTC", 0, False),
            ("GMT", "GMT", 0, False),
            ("EST", "America/New_York", -5, False),
            ("EDT", "America/New_York", -4, True),
            ("CST", "America/Chicago", -6, False),
            ("CDT", "America/Chicago", -5, True),
            ("MST", "America/Denver", -7, False),
            ("MDT", "America/Denver", -6, True),
            ("PST", "America/Los_Angeles", -8, False),
            ("PDT", "America/Los_Angeles", -7, True),
            ("CET", "Europe/Berlin", 1, False),
            ("CEST", "Europe/Berlin", 2, True),
            ("JST", "Asia/Tokyo", 9, False),
            ("IST", "Asia/Kolkata", 5.5, False),
            ("AEST", "Australia/Sydney", 10, False),
            ("AEDT", "Australia/Sydney", 11, True),
        ]
        for abbr, tz, offset, dst in abbrevs:
            self._abbreviations[abbr] = ZoneAbbreviation(
                abbreviation=abbr, timezone=tz, utc_offset=offset, dst=dst
            )

    def get_timezone(self, name: str) -> Optional[TimezoneEntry]:
        """Get a timezone by name."""
        return self._timezones.get(name)

    def list_timezones(self, continent: Optional[str] = None) -> List[TimezoneEntry]:
        """List all timezones, optionally filtered by continent."""
        zones = list(self._timezones.values())
        if continent is not None:
            zones = [z for z in zones if z.continent == continent]
        return sorted(zones, key=lambda z: z.name)

    def search_timezones(self, query: str) -> List[TimezoneEntry]:
        """Search timezones by name or description."""
        query_lower = query.lower()
        results = []
        for tz in self._timezones.values():
            if (query_lower in tz.name.lower() or
                query_lower in tz.description.lower()):
                results.append(tz)
        return results

    def set_default_timezone(self, name: str) -> bool:
        """Set the default system timezone."""
        if name in self._timezones:
            self._default_timezone = name
            return True
        return False

    def get_default_timezone(self) -> str:
        """Get the default system timezone."""
        return self._default_timezone

    def get_abbreviation(self, abbr: str) -> Optional[ZoneAbbreviation]:
        """Get a timezone abbreviation."""
        return self._abbreviations.get(abbr)

    def list_abbreviations(self) -> List[ZoneAbbreviation]:
        """List all timezone abbreviations."""
        return sorted(self._abbreviations.values(), key=lambda a: a.abbreviation)

    def get_leap_seconds(self) -> List[LeapSecond]:
        """Get all leap seconds."""
        return self._leap_seconds.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """Get zoneinfo statistics."""
        by_continent: Dict[str, int] = {}
        for tz in self._timezones.values():
            cont = tz.continent or "other"
            by_continent[cont] = by_continent.get(cont, 0) + 1
        return {
            "total_timezones": len(self._timezones),
            "total_abbreviations": len(self._abbreviations),
            "total_leap_seconds": len(self._leap_seconds),
            "by_continent": by_continent,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize manager to dictionary."""
        return {
            "timezones": {k: v.to_dict() for k, v in self._timezones.items()},
            "abbreviations": {k: v.to_dict() for k, v in self._abbreviations.items()},
            "leap_seconds": [ls.to_dict() for ls in self._leap_seconds],
            "default_timezone": self._default_timezone,
            "statistics": self.get_statistics(),
        }


# ─── Singleton Getter ────────────────────────────────────────────────────────

def get_global_zoneinfo_manager() -> ZoneinfoManager:
    """Get or create the global ZoneinfoManager instance."""
    global _global_zoneinfo_manager
    if _global_zoneinfo_manager is None:
        _global_zoneinfo_manager = ZoneinfoManager()
    return _global_zoneinfo_manager


def initialize() -> ZoneinfoManager:
    """Initialize and return the global ZoneinfoManager."""
    return get_global_zoneinfo_manager()


def refresh() -> ZoneinfoManager:
    """Refresh the global ZoneinfoManager."""
    global _global_zoneinfo_manager
    _global_zoneinfo_manager = ZoneinfoManager()
    return _global_zoneinfo_manager
