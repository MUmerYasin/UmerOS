#!/usr/bin/env python3
"""
UmerOS /etc/locale and timezone manager.

Manages timezone, locale, and hardware clock settings.
Handles /etc/localtime (symlink), /etc/timezone, /etc/locale.conf,
/etc/locale.gen, /etc/default/locale, /etc/environment, and hwclock interaction.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

TIMEZONE_FILE: str = "/etc/timezone"
LOCALTIME_LINK: str = "/etc/localtime"
ZONEINFO_DIR: str = "/usr/share/zoneinfo"
LOCALE_CONF: str = "/etc/locale.conf"
LOCALE_GEN: str = "/etc/locale.gen"
DEFAULT_LOCALE: str = "/etc/default/locale"
ENVIRONMENT_FILE: str = "/etc/environment"


# ---------------------------------------------------------------------------
# Common reference data
# ---------------------------------------------------------------------------

COMMON_TIMEZONES: List[str] = [
    "UTC",
    "US/Eastern",
    "US/Central",
    "US/Mountain",
    "US/Pacific",
    "US/Alaska",
    "US/Hawaii",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Europe/Madrid",
    "Europe/Rome",
    "Europe/Amsterdam",
    "Europe/Moscow",
    "Asia/Tokyo",
    "Asia/Shanghai",
    "Asia/Kolkata",
    "Asia/Dubai",
    "Asia/Singapore",
    "Asia/Seoul",
    "Asia/Hong_Kong",
    "Australia/Sydney",
    "Australia/Melbourne",
    "Australia/Brisbane",
    "Australia/Perth",
    "Pacific/Auckland",
    "Pacific/Honolulu",
    "Africa/Cairo",
    "Africa/Lagos",
    "Africa/Johannesburg",
    "America/Sao_Paulo",
    "America/Argentina/Buenos_Aires",
    "America/Mexico_City",
    "America/Chicago",
    "America/Los_Angeles",
    "America/New_York",
    "Atlantic/Reykjavik",
    "Africa/Nairobi",
    "Africa/Casablanca",
    "Asia/Kathmandu",
    "Asia/Colombo",
    "Asia/Bangkok",
    "Asia/Jakarta",
    "Asia/Ho_Chi_Minh",
    "Asia/Taipei",
]

COMMON_LOCALES: List[str] = [
    "en_US.UTF-8",
    "en_GB.UTF-8",
    "fr_FR.UTF-8",
    "fr_CA.UTF-8",
    "de_DE.UTF-8",
    "de_AT.UTF-8",
    "de_CH.UTF-8",
    "es_ES.UTF-8",
    "es_MX.UTF-8",
    "it_IT.UTF-8",
    "pt_BR.UTF-8",
    "pt_PT.UTF-8",
    "nl_NL.UTF-8",
    "ru_RU.UTF-8",
    "ja_JP.UTF-8",
    "ko_KR.UTF-8",
    "zh_CN.UTF-8",
    "zh_TW.UTF-8",
    "ar_SA.UTF-8",
    "hi_IN.UTF-8",
    "th_TH.UTF-8",
    "pl_PL.UTF-8",
    "sv_SE.UTF-8",
    "da_DK.UTF-8",
    "fi_FI.UTF-8",
    "no_NO.UTF-8",
    "cs_CZ.UTF-8",
    "hu_HU.UTF-8",
    "tr_TR.UTF-8",
    "el_GR.UTF-8",
    "he_IL.UTF-8",
    "vi_VN.UTF-8",
    "id_ID.UTF-8",
    "ms_MY.UTF-8",
    "uk_UA.UTF-8",
    "ro_RO.UTF-8",
    "bg_BG.UTF-8",
    "hr_HR.UTF-8",
    "sk_SK.UTF-8",
    "sl_SI.UTF-8",
    "lt_LT.UTF-8",
    "lv_LV.UTF-8",
    "et_EE.UTF-8",
    "ca_ES.UTF-8",
    "gl_ES.UTF-8",
    "af_ZA.UTF-8",
    "zu_ZA.UTF-8",
    "en_AU.UTF-8",
    "en_CA.UTF-8",
    "en_IN.UTF-8",
    "en_IE.UTF-8",
    "en_ZA.UTF-8",
    "en_NZ.UTF-8",
]

# Map of region prefixes used by list_timezones(region)
_TIMEZONE_REGIONS: Dict[str, str] = {
    "africa": "Africa",
    "america": "America",
    "antarctica": "Antarctica",
    "arctic": "Arctic",
    "asia": "Asia",
    "atlantic": "Atlantic",
    "australia": "Australia",
    "brazil": "Brazil",
    "canada": "Canada",
    "europe": "Europe",
    "indian": "Indian",
    "mexico": "Mexico",
    "pacific": "Pacific",
    "us": "US",
    "utc": "Etc",
}


class LocaleTimezoneManager:
    """Manage timezone, locale, and hardware clock configuration on a system.

    All mutating methods return a status dictionary with at least a ``success``
    boolean and, on failure, an ``error`` key explaining what went wrong.
    """

    def __init__(
        self,
        timezone_file: str = TIMEZONE_FILE,
        localtime_link: str = LOCALTIME_LINK,
        zoneinfo_dir: str = ZONEINFO_DIR,
        locale_conf: str = LOCALE_CONF,
        locale_gen: str = LOCALE_GEN,
        default_locale: str = DEFAULT_LOCALE,
        environment_file: str = ENVIRONMENT_FILE,
    ) -> None:
        self.timezone_file = Path(timezone_file)
        self.localtime_link = Path(localtime_link)
        self.zoneinfo_dir = Path(zoneinfo_dir)
        self.locale_conf = Path(locale_conf)
        self.locale_gen = Path(locale_gen)
        self.default_locale = Path(default_locale)
        self.environment_file = Path(environment_file)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_file_lines(self, path: Path) -> List[str]:
        """Return the lines of *path*, or an empty list on any error."""
        try:
            if not path.exists():
                return []
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return fh.readlines()
        except OSError:
            return []

    def _write_file_lines(self, path: Path, lines: List[str]) -> bool:
        """Atomically replace *path* with *lines*. Returns True on success."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.writelines(lines)
            shutil.move(str(tmp), str(path))
            return True
        except OSError as exc:
            # Clean up partial write
            tmp_path = path.with_suffix(".tmp")
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            return False

    def _parse_key_value_file(self, path: Path) -> Dict[str, str]:
        """Parse a KEY=VALUE (optionally quoted) file.

        Supports ``export KEY=VALUE`` and ignores comment lines.
        """
        result: Dict[str, str] = {}
        for line in self._read_file_lines(path):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Strip optional leading "export "
            if line.startswith("export "):
                line = line[len("export "):]
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Remove surrounding quotes (single or double)
            if len(value) >= 2 and value[0] in ("'", '"') and value[-1] == value[0]:
                value = value[1:-1]
            result[key] = value
        return result

    def _run_command(
        self,
        args: List[str],
        *,
        check: bool = False,
        capture: bool = True,
    ) -> subprocess.CompletedProcess:
        """Run a subprocess, returning the CompletedProcess object."""
        try:
            return subprocess.run(
                args,
                check=check,
                capture_output=capture,
                text=True,
                timeout=30,
            )
        except FileNotFoundError:
            return subprocess.CompletedProcess(
                args, returncode=127, stdout="", stderr=f"Command not found: {args[0]}"
            )
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(
                args, returncode=124, stdout="", stderr="Command timed out"
            )
        except subprocess.CalledProcessError as exc:
            return subprocess.CompletedProcess(
                args,
                returncode=exc.returncode,
                stdout=exc.stdout,
                stderr=exc.stderr,
            )

    def _success(self, **extra: Any) -> Dict[str, Any]:
        """Return a standard success status dict."""
        return {"success": True, **extra}

    def _error(self, msg: str, **extra: Any) -> Dict[str, Any]:
        """Return a standard error status dict."""
        return {"success": False, "error": msg, **extra}

    def _ensure_parent(self, path: Path) -> bool:
        """Create parent directories for *path* if needed. Returns True on success."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            return True
        except OSError as exc:
            return False

    def _backup_path_for(self, path: Path, backup_dir: Path) -> Path:
        """Compute the backup destination for *path* inside *backup_dir*."""
        return backup_dir / path.lstrip("/")

    # ------------------------------------------------------------------
    # Timezone
    # ------------------------------------------------------------------

    def get_timezone(self) -> Dict[str, Any]:
        """Read the currently configured timezone.

        Returns:
            Dict with ``timezone``, ``source``, and ``abbreviation`` keys.
        """
        timezone: Optional[str] = None
        source: str = "unknown"

        # 1) Try /etc/timezone
        if self.timezone_file.exists():
            lines = self._read_file_lines(self.timezone_file)
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#"):
                    timezone = line
                    source = str(self.timezone_file)
                    break

        # 2) Fallback: resolve /etc/localtime symlink
        if timezone is None and self.localtime_link.exists():
            try:
                resolved = os.readlink(str(self.localtime_link))
                # e.g. /usr/share/zoneinfo/America/New_York
                zi = str(self.zoneinfo_dir) + "/"
                if resolved.startswith(zi):
                    timezone = resolved[len(zi):]
                elif "zoneinfo/" in resolved:
                    timezone = resolved.split("zoneinfo/")[-1]
                else:
                    timezone = resolved
                source = str(self.localtime_link)
            except OSError:
                pass

        # 3) Fallback: timedatectl
        if timezone is None:
            proc = self._run_command(["timedatectl", "show", "--property=Timezone"])
            if proc.returncode == 0:
                for line in proc.stdout.splitlines():
                    if line.startswith("Timezone="):
                        timezone = line.split("=", 1)[1].strip()
                        source = "timedatectl"
                        break

        # 4) Fallback: /etc/default/rcS
        if timezone is None:
            rcs = Path("/etc/default/rcS")
            if rcs.exists():
                kv = self._parse_key_value_file(rcs)
                if "TIMEZONE" in kv:
                    timezone = kv["TIMEZONE"]
                    source = str(rcs)

        # 5) Fallback: TZ env var
        if timezone is None:
            tz_env = os.environ.get("TZ")
            if tz_env:
                timezone = tz_env
                source = "TZ environment variable"

        # Compute abbreviation
        abbreviation: str = ""
        if timezone:
            abbrev_path = self.zoneinfo_dir / timezone
            if abbrev_path.exists():
                try:
                    proc = self._run_command(["date", "+%Z", f"--date=@0"])
                    abbreviation = proc.stdout.strip()
                except Exception:
                    abbreviation = timezone.split("/")[-1]

        return self._success(timezone=timezone, source=source, abbreviation=abbreviation)

    def set_timezone(self, zone: str) -> Dict[str, Any]:
        """Set the system timezone.

        Writes ``/etc/timezone``, updates the ``/etc/localtime`` symlink,
        and attempts to update the timezone via ``timedatectl`` as well.

        Args:
            zone: Timezone identifier, e.g. ``America/New_York``.

        Returns:
            Status dict with previous and new timezone values.
        """
        zone = zone.strip()
        if not zone:
            return self._error("Timezone must not be empty.")

        # Validate zone exists in zoneinfo
        zone_path = self.zoneinfo_dir / zone
        if not zone_path.exists():
            return self._error(f"Timezone '{zone}' not found in {self.zoneinfo_dir}.")

        # Capture previous value
        prev = self.get_timezone()
        previous_tz = prev.get("timezone", "unknown")

        # 1) Write /etc/timezone
        if not self._ensure_parent(self.timezone_file):
            return self._error("Failed to create parent directory for /etc/timezone.")
        lines = [f"{zone}\n"]
        if not self._write_file_lines(self.timezone_file, lines):
            return self._error("Failed to write /etc/timezone.")

        # 2) Update /etc/localtime symlink
        try:
            self.localtime_link.unlink(missing_ok=True)
            os.symlink(str(zone_path), str(self.localtime_link))
        except OSError as exc:
            return self._error(f"Failed to update /etc/localtime symlink: {exc}")

        # 3) Try timedatectl
        self._run_command(["timedatectl", "set-timezone", zone])

        # 4) Update /etc/default/locale if it references timezone (rare but possible)
        # Not done here — users manage locale.conf separately.

        return self._success(
            timezone=zone,
            previous_timezone=previous_tz,
            message=f"Timezone changed from '{previous_tz}' to '{zone}'.",
        )

    def list_timezones(self, region: Optional[str] = None) -> Dict[str, Any]:
        """List available timezone identifiers from the zoneinfo directory.

        Args:
            region: Optional region filter (e.g. ``"us"``, ``"europe"``,
                ``"asia"``, ``"america"``).  Case-insensitive.  ``None``
                returns all zones.

        Returns:
            Dict with ``timezones`` (sorted list) and ``count``.
        """
        if not self.zoneinfo_dir.exists():
            return self._error(f"Zoneinfo directory not found: {self.zoneinfo_dir}")

        # Determine top-level directory to scan
        scan_dir = self.zoneinfo_dir
        if region:
            key = region.lower().strip()
            if key in _TIMEZONE_REGIONS:
                scan_dir = self.zoneinfo_dir / _TIMEZONE_REGIONS[key]
            else:
                # Try direct directory match
                candidate = self.zoneinfo_dir / region
                if candidate.is_dir():
                    scan_dir = candidate
                else:
                    return self._error(
                        f"Unknown region '{region}'. "
                        f"Available regions: {', '.join(sorted(_TIMEZONE_REGIONS.keys()))}"
                    )

        zones: List[str] = []
        skip_dirs = {"posix", "right", "Etc", "Canada", "Brazil", "Mexico", "US"}

        for root, dirs, files in os.walk(scan_dir):
            # Skip "right" leap-second databases and Etc/UTC offsets
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            rel = os.path.relpath(root, self.zoneinfo_dir)
            # Ignore top-level POSIX/special dirs
            if rel.startswith("posix") or rel.startswith("right") or rel.startswith("Etc"):
                continue

            for fname in files:
                full_path = os.path.join(root, fname)
                if not os.path.isfile(full_path):
                    continue
                # Skip compiled zoneinfo data files like posixrules
                if fname in ("posixrules", "leap-seconds.list", "leapseconds", "tab"):
                    continue
                # Skip files starting with .
                if fname.startswith("."):
                    continue
                zone_id = os.path.relpath(full_path, self.zoneinfo_dir)
                zones.append(zone_id)

        zones.sort()
        return self._success(timezones=zones, count=len(zones))

    # ------------------------------------------------------------------
    # Locale
    # ------------------------------------------------------------------

    def get_locale(self) -> Dict[str, Any]:
        """Read current locale settings from /etc/locale.conf.

        Also reads /etc/default/locale if present and merges values (with
        /etc/default/locale taking precedence).

        Returns:
            Dict with ``locale_settings``, ``source``, and ``lang`` keys.
        """
        settings: Dict[str, str] = {}
        sources: List[str] = []

        # /etc/locale.conf (primary)
        if self.locale_conf.exists():
            settings.update(self._parse_key_value_file(self.locale_conf))
            sources.append(str(self.locale_conf))

        # /etc/default/locale (Debian/Ubuntu override)
        if self.default_locale.exists():
            settings.update(self._parse_key_value_file(self.default_locale))
            sources.append(str(self.default_locale))

        return self._success(
            locale_settings=settings,
            sources=sources,
            lang=settings.get("LANG", settings.get("LC_ALL", "C")),
        )

    def set_locale(self, settings: Dict[str, str]) -> Dict[str, Any]:
        """Write locale settings to /etc/locale.conf.

        Each key-value pair is written as ``KEY=VALUE``.  Existing keys not
        present in *settings* are preserved.  If the caller wishes to set
        ``LANG`` the file will also be updated.

        Args:
            settings: Mapping of locale variables, e.g.
                ``{"LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8"}``.

        Returns:
            Status dict.
        """
        if not settings:
            return self._error("Settings must not be empty.")

        # Read current settings to preserve extras
        existing: Dict[str, str] = {}
        if self.locale_conf.exists():
            existing = self._parse_key_value_file(self.locale_conf)

        # Merge: caller values override existing
        existing.update(settings)

        if not self._ensure_parent(self.locale_conf):
            return self._error("Failed to create parent directory for /etc/locale.conf.")

        lines: List[str] = []
        for key, value in sorted(existing.items()):
            lines.append(f"{key}=\"{value}\"\n")

        if not self._write_file_lines(self.locale_conf, lines):
            return self._error("Failed to write /etc/locale.conf.")

        # Also write /etc/default/locale for compatibility
        if self.default_locale.parent.exists():
            default_lines: List[str] = []
            existing_default: Dict[str, str] = {}
            if self.default_locale.exists():
                existing_default = self._parse_key_value_file(self.default_locale)
            existing_default.update(settings)
            for key, value in sorted(existing_default.items()):
                default_lines.append(f'{key}="{value}"\n')
            self._write_file_lines(self.default_locale, default_lines)

        return self._success(
            locale_settings=existing,
            message="Locale settings updated.",
        )

    def list_available_locales(self) -> Dict[str, Any]:
        """Parse /etc/locale.gen and return available and enabled locales.

        Returns:
            Dict with ``all_locales``, ``enabled_locales``, and ``disabled_locales``.
        """
        all_locales: List[str] = []
        enabled_locales: List[str] = []

        if not self.locale_gen.exists():
            return self._error(f"Locale file not found: {self.locale_gen}")

        for line in self._read_file_lines(self.locale_gen):
            line = line.strip()
            if not line or line.startswith("#"):
                # Strip comment marker to extract the locale name
                stripped = line.lstrip("#").strip()
                if stripped and not stripped.startswith(" "):
                    all_locales.append(stripped)
                continue
            all_locales.append(line)
            enabled_locales.append(line)

        all_locales.sort()
        enabled_locales.sort()
        disabled = [loc for loc in all_locales if loc not in enabled_locales]

        return self._success(
            all_locales=all_locales,
            enabled_locales=enabled_locales,
            disabled_locales=disabled,
            count=len(all_locales),
            enabled_count=len(enabled_locales),
        )

    def enable_locale(self, locale_str: str) -> Dict[str, Any]:
        """Enable a locale by uncommenting it in /etc/locale.gen.

        Args:
            locale_str: Locale string, e.g. ``fr_FR.UTF-8``.

        Returns:
            Status dict.
        """
        locale_str = locale_str.strip()
        if not locale_str:
            return self._error("Locale string must not be empty.")

        if not self.locale_gen.exists():
            return self._error(f"Locale file not found: {self.locale_gen}")

        lines = self._read_file_lines(self.locale_gen)
        found = False
        already_enabled = False
        new_lines: List[str] = []

        for line in lines:
            stripped = line.strip()
            # Match commented version like "# fr_FR.UTF-8 UTF-8"
            if stripped.lstrip("#").strip().startswith(locale_str):
                # Check if it was commented out
                if stripped.startswith("#"):
                    new_lines.append(stripped.lstrip("#").lstrip() + "\n")
                    found = True
                else:
                    already_enabled = True
                    new_lines.append(line)
            else:
                new_lines.append(line)

        if not found and not already_enabled:
            return self._error(
                f"Locale '{locale_str}' not found in {self.locale_gen}."
            )

        if already_enabled:
            return self._success(
                locale=locale_str,
                message=f"Locale '{locale_str}' is already enabled.",
                already_enabled=True,
            )

        if not self._write_file_lines(self.locale_gen, new_lines):
            return self._error("Failed to write locale.gen.")

        return self._success(
            locale=locale_str,
            message=f"Locale '{locale_str}' enabled.",
        )

    def disable_locale(self, locale_str: str) -> Dict[str, Any]:
        """Disable a locale by commenting it out in /etc/locale.gen.

        Args:
            locale_str: Locale string, e.g. ``fr_FR.UTF-8``.

        Returns:
            Status dict.
        """
        locale_str = locale_str.strip()
        if not locale_str:
            return self._error("Locale string must not be empty.")

        if not self.locale_gen.exists():
            return self._error(f"Locale file not found: {self.locale_gen}")

        lines = self._read_file_lines(self.locale_gen)
        found = False
        already_disabled = False
        new_lines: List[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.lstrip("#").strip().startswith(locale_str):
                if stripped.startswith("#"):
                    already_disabled = True
                    new_lines.append(line)
                else:
                    new_lines.append(f"#{line.lstrip()}")
                    found = True
            else:
                new_lines.append(line)

        if not found and not already_disabled:
            return self._error(
                f"Locale '{locale_str}' not found in {self.locale_gen}."
            )

        if already_disabled:
            return self._success(
                locale=locale_str,
                message=f"Locale '{locale_str}' is already disabled.",
                already_disabled=True,
            )

        if not self._write_file_lines(self.locale_gen, new_lines):
            return self._error("Failed to write locale.gen.")

        return self._success(
            locale=locale_str,
            message=f"Locale '{locale_str}' disabled.",
        )

    # ------------------------------------------------------------------
    # Hardware clock
    # ------------------------------------------------------------------

    def get_hwclock(self) -> Dict[str, Any]:
        """Determine the hardware clock mode.

        Checks ``/etc/adjtime`` (third field), then falls back to
        ``hwclock --show`` and ``timedatectl``.

        Returns:
            Dict with ``mode`` (``"utc"`` or ``"localtime"``) and ``source``.
        """
        # 1) /etc/adjtime — third field: "UTC" or "LOCAL"
        adjtime = Path("/etc/adjtime")
        if adjtime.exists():
            for line in self._read_file_lines(adjtime):
                parts = line.strip().split()
                if len(parts) >= 3 and parts[2] in ("UTC", "LOCAL"):
                    mode = "utc" if parts[2] == "UTC" else "localtime"
                    return self._success(mode=mode, source=str(adjtime))

        # 2) hwclock --show
        proc = self._run_command(["hwclock", "--show"])
        if proc.returncode == 0 and proc.stdout.strip():
            output = proc.stdout.strip().lower()
            if "utc" in output:
                return self._success(mode="utc", source="hwclock")
            elif "local" in output:
                return self._success(mode="localtime", source="hwclock")

        # 3) timedatectl
        proc = self._run_command(["timedatectl", "show", "--property=LocalRTC"])
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if line.startswith("LocalRTC="):
                    val = line.split("=", 1)[1].strip().lower()
                    mode = "localtime" if val == "yes" else "utc"
                    return self._success(mode=mode, source="timedatectl")

        return self._success(mode="utc", source="default_assumption")

    def set_hwclock(self, mode: str) -> Dict[str, Any]:
        """Set the hardware clock mode.

        Args:
            mode: ``"utc"`` or ``"localtime"``.

        Returns:
            Status dict.
        """
        mode = mode.strip().lower()
        if mode not in ("utc", "localtime"):
            return self._error(
                f"Invalid hwclock mode '{mode}'. Must be 'utc' or 'localtime'."
            )

        prev = self.get_hwclock()
        previous_mode = prev.get("mode", "unknown")

        # 1) Try timedatectl
        local_rtc = "True" if mode == "localtime" else "False"
        proc = self._run_command(["timedatectl", "set-local-rtc", local_rtc])

        # 2) Update /etc/adjtime directly as backup
        adjtime = Path("/etc/adjtime")
        if adjtime.exists():
            lines = self._read_file_lines(adjtime)
            new_lines: List[str] = []
            replaced = False
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 3 and parts[2] in ("UTC", "LOCAL"):
                    new_line = line.replace(
                        "UTC" if parts[2] == "UTC" else "LOCAL",
                        "UTC" if mode == "utc" else "LOCAL",
                    )
                    new_lines.append(new_line)
                    replaced = True
                else:
                    new_lines.append(line)
            if replaced:
                self._write_file_lines(adjtime, new_lines)

        return self._success(
            mode=mode,
            previous_mode=previous_mode,
            message=f"Hardware clock changed from '{previous_mode}' to '{mode}'.",
        )

    # ------------------------------------------------------------------
    # /etc/environment
    # ------------------------------------------------------------------

    def get_environment(self) -> Dict[str, Any]:
        """Parse /etc/environment and return all KEY=VALUE variables.

        Returns:
            Dict with ``variables`` mapping and ``count``.
        """
        variables = self._parse_key_value_file(self.environment_file)
        return self._success(variables=variables, count=len(variables))

    def set_environment(self, variables: Dict[str, str]) -> Dict[str, Any]:
        """Overwrite /etc/environment with the given variables.

        Existing entries are replaced; keys not in *variables* are removed.

        Args:
            variables: Mapping of variable names to values.

        Returns:
            Status dict.
        """
        if not variables:
            return self._error("Variables must not be empty.")

        if not self._ensure_parent(self.environment_file):
            return self._error("Failed to create parent directory for /etc/environment.")

        lines: List[str] = []
        for key, value in sorted(variables.items()):
            key = key.strip()
            if not key:
                continue
            # Quote values that contain spaces or special characters
            needs_quote = any(c in value for c in " \t\n\"'\\")
            if needs_quote:
                escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{key}="{escaped}"\n')
            else:
                lines.append(f"{key}={value}\n")

        if not self._write_file_lines(self.environment_file, lines):
            return self._error("Failed to write /etc/environment.")

        return self._success(
            variables=variables,
            message="/etc/environment updated.",
        )

    def add_environment(self, variable: str, value: str) -> Dict[str, Any]:
        """Add or update a single variable in /etc/environment.

        Preserves existing entries.

        Args:
            variable: Variable name (e.g. ``JAVA_HOME``).
            value: Variable value.

        Returns:
            Status dict.
        """
        variable = variable.strip()
        if not variable:
            return self._error("Variable name must not be empty.")

        current = self._parse_key_value_file(self.environment_file)
        previous_value = current.get(variable)

        current[variable] = value

        if not self._ensure_parent(self.environment_file):
            return self._error("Failed to create parent directory for /etc/environment.")

        lines: List[str] = []
        for key, val in sorted(current.items()):
            needs_quote = any(c in val for c in " \t\n\"'\\")
            if needs_quote:
                escaped = val.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{key}="{escaped}"\n')
            else:
                lines.append(f"{key}={val}\n")

        if not self._write_file_lines(self.environment_file, lines):
            return self._error("Failed to write /etc/environment.")

        action = "updated" if previous_value is not None else "added"
        return self._success(
            variable=variable,
            value=value,
            previous_value=previous_value,
            message=f"Variable '{variable}' {action}.",
        )

    def remove_environment(self, variable: str) -> Dict[str, Any]:
        """Remove a variable from /etc/environment.

        Args:
            variable: Variable name to remove.

        Returns:
            Status dict.
        """
        variable = variable.strip()
        if not variable:
            return self._error("Variable name must not be empty.")

        current = self._parse_key_value_file(self.environment_file)
        if variable not in current:
            return self._error(
                f"Variable '{variable}' not found in {self.environment_file}."
            )

        removed_value = current.pop(variable)

        lines: List[str] = []
        for key, val in sorted(current.items()):
            needs_quote = any(c in val for c in " \t\n\"'\\")
            if needs_quote:
                escaped = val.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{key}="{escaped}"\n')
            else:
                lines.append(f"{key}={val}\n")

        if not self._write_file_lines(self.environment_file, lines):
            return self._error("Failed to write /etc/environment.")

        return self._success(
            variable=variable,
            removed_value=removed_value,
            message=f"Variable '{variable}' removed.",
        )

    # ------------------------------------------------------------------
    # /etc/default/locale (Debian/Ubuntu convenience)
    # ------------------------------------------------------------------

    def get_default_locale(self) -> Dict[str, Any]:
        """Read /etc/default/locale (Debian/Ubuntu style).

        Returns:
            Dict with ``settings`` and ``lang``.
        """
        settings = self._parse_key_value_file(self.default_locale)
        return self._success(
            settings=settings,
            lang=settings.get("LANG", settings.get("LC_ALL", "C")),
        )

    def set_default_locale(self, settings: Dict[str, str]) -> Dict[str, Any]:
        """Write /etc/default/locale (Debian/Ubuntu style).

        Args:
            settings: Mapping of locale variables.

        Returns:
            Status dict.
        """
        if not settings:
            return self._error("Settings must not be empty.")

        existing = self._parse_key_value_file(self.default_locale)
        existing.update(settings)

        if not self._ensure_parent(self.default_locale):
            return self._error(
                "Failed to create parent directory for /etc/default/locale."
            )

        lines: List[str] = []
        for key, value in sorted(existing.items()):
            lines.append(f'{key}="{value}"\n')

        if not self._write_file_lines(self.default_locale, lines):
            return self._error("Failed to write /etc/default/locale.")

        return self._success(
            settings=existing,
            message="/etc/default/locale updated.",
        )

    # ------------------------------------------------------------------
    # Export full status
    # ------------------------------------------------------------------

    def export_status(self) -> Dict[str, Any]:
        """Export the combined locale/timezone/hwclock/environment status.

        Returns a dict containing all current settings.
        """
        tz = self.get_timezone()
        locale_info = self.get_locale()
        hw = self.get_hwclock()
        env = self.get_environment()
        default_loc = self.get_default_locale()

        return self._success(
            timezone=tz.get("timezone"),
            timezone_source=tz.get("source"),
            timezone_abbreviation=tz.get("abbreviation"),
            locale_settings=locale_info.get("locale_settings", {}),
            locale_lang=locale_info.get("lang"),
            locale_sources=locale_info.get("sources", []),
            hwclock_mode=hw.get("mode"),
            hwclock_source=hw.get("source"),
            environment_variables=env.get("variables", {}),
            default_locale_settings=default_loc.get("settings", {}),
            exported_at=datetime.now().isoformat(),
        )

    # ------------------------------------------------------------------
    # Backup
    # ------------------------------------------------------------------

    def backup_all(self, backup_path: str) -> Dict[str, Any]:
        """Create a backup of all managed configuration files.

        Args:
            backup_path: Destination directory path.  Subdirectories are
                created automatically.

        Returns:
            Status dict listing which files were backed up and any failures.
        """
        dest = Path(backup_path)
        files_to_backup = [
            self.timezone_file,
            self.localtime_link,
            self.locale_conf,
            self.locale_gen,
            self.default_locale,
            self.environment_file,
        ]

        backed_up: List[str] = []
        failures: List[str] = []

        for src in files_to_backup:
            if not src.exists():
                # Skip non-existent files — not an error
                continue

            # Compute destination preserving absolute path
            backup_dest = self._backup_path_for(str(src), dest)
            backup_dest.parent.mkdir(parents=True, exist_ok=True)

            try:
                if src.is_symlink() and not src.is_file():
                    # Copy the symlink itself
                    link_target = os.readlink(str(src))
                    if backup_dest.exists() or backup_dest.is_symlink():
                        backup_dest.unlink()
                    os.symlink(link_target, str(backup_dest))
                else:
                    shutil.copy2(str(src), str(backup_dest))
                backed_up.append(str(src))
            except OSError as exc:
                failures.append(f"{src}: {exc}")

        # Also backup /etc/adjtime if it exists (hwclock config)
        adjtime = Path("/etc/adjtime")
        if adjtime.exists():
            backup_dest = self._backup_path_for(str(adjtime), dest)
            backup_dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(str(adjtime), str(backup_dest))
                backed_up.append(str(adjtime))
            except OSError as exc:
                failures.append(f"{adjtime}: {exc}")

        return self._success(
            backup_path=str(dest),
            files_backed_up=backed_up,
            failures=failures,
            count=len(backed_up),
        )

    # ------------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------------

    def restore_from_backup(self, backup_path: str) -> Dict[str, Any]:
        """Restore configuration files from a backup directory.

        Only files that exist in the backup are restored.  Each file is
        copied back to its original location.

        Args:
            backup_path: Directory containing the backup created by
                ``backup_all``.

        Returns:
            Status dict listing restored files and failures.
        """
        src = Path(backup_path)
        if not src.exists() or not src.is_dir():
            return self._error(f"Backup directory not found: {backup_path}")

        files_to_restore = [
            self.timezone_file,
            self.locale_conf,
            self.locale_gen,
            self.default_locale,
            self.environment_file,
        ]

        restored: List[str] = []
        failures: List[str] = []

        for dest in files_to_restore:
            backup_file = self._backup_path_for(str(dest), src)
            if not backup_file.exists():
                continue

            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(str(backup_file), str(dest))
                restored.append(str(dest))
            except OSError as exc:
                failures.append(f"{dest}: {exc}")

        # Restore /etc/adjtime
        adjtime = Path("/etc/adjtime")
        backup_adjtime = self._backup_path_for(str(adjtime), src)
        if backup_adjtime.exists():
            adjtime.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(str(backup_adjtime), str(adjtime))
                restored.append(str(adjtime))
            except OSError as exc:
                failures.append(f"{adjtime}: {exc}")

        return self._success(
            restored_files=restored,
            failures=failures,
            count=len(restored),
            message=f"Restored {len(restored)} file(s) from backup.",
        )

    # ------------------------------------------------------------------
    # Utility: generate locale
    # ------------------------------------------------------------------

    def generate_locales(self, locales: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run locale-gen to compile locale definitions.

        If *locales* is provided, only those specific locales are generated.
        Otherwise all enabled locales in /etc/locale.gen are compiled.

        Returns:
            Status dict with stdout/stderr from the command.
        """
        if locales:
            # Ensure each requested locale is enabled
            already_enabled: List[str] = []
            newly_enabled: List[str] = []
            errors: List[str] = []

            for loc in locales:
                result = self.enable_locale(loc)
                if result.get("success"):
                    if result.get("already_enabled"):
                        already_enabled.append(loc)
                    else:
                        newly_enabled.append(loc)
                else:
                    errors.append(result.get("error", f"Failed to enable {loc}"))

            if errors:
                return self._error(
                    "Failed to enable some locales.",
                    already_enabled=already_enabled,
                    newly_enabled=newly_enabled,
                    errors=errors,
                )

        # Run locale-gen
        proc = self._run_command(["locale-gen"])
        output = proc.stdout.strip() if proc.stdout else ""
        error_out = proc.stderr.strip() if proc.stderr else ""

        if proc.returncode != 0:
            return self._error(
                "locale-gen failed.",
                returncode=proc.returncode,
                stdout=output,
                stderr=error_out,
            )

        return self._success(
            message="Locales generated successfully.",
            locales=locales,
            stdout=output,
            stderr=error_out,
        )

    def set_system_timezone(self, zone: str) -> Dict[str, Any]:
        """Convenience: apply full timezone configuration.

        This is a higher-level wrapper that sets /etc/timezone, updates
        the symlink, runs ``timedatectl``, and updates /etc/default/locale
        if it references a timezone.

        Args:
            zone: Timezone identifier, e.g. ``Asia/Tokyo``.

        Returns:
            Status dict with combined results.
        """
        tz_result = self.set_timezone(zone)
        if not tz_result.get("success"):
            return tz_result

        return self._success(
            timezone=zone,
            message=f"System timezone set to '{zone}'.",
            details=tz_result,
        )

    # ------------------------------------------------------------------
    # Repr / str
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            "LocaleTimezoneManager("
            f"timezone_file={self.timezone_file!r}, "
            f"locale_conf={self.locale_conf!r}, "
            f"zoneinfo_dir={self.zoneinfo_dir!r})"
        )


# ---------------------------------------------------------------------------
# Standalone CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    def _print_json(data: Any) -> None:
        """Pretty-print a result dict as JSON."""
        print(json.dumps(data, indent=2, default=str))

    mgr = LocaleTimezoneManager()
    usage = """\
Usage: python locale_timezone.py <command> [arguments...]

Commands:
  get-timezone                     Show current timezone
  set-timezone <zone>              Set timezone (e.g. America/New_York)
  list-timezones [region]          List available timezones
  get-locale                       Show current locale settings
  set-locale KEY VALUE [KEY VALUE ...]   Set locale settings
  list-locales                     List locales in /etc/locale.gen
  enable-locale <locale>           Enable a locale
  disable-locale <locale>          Disable a locale
  get-hwclock                      Show hardware clock mode
  set-hwclock <utc|localtime>      Set hardware clock mode
  get-environment                  Show /etc/environment variables
  add-env <var> <value>            Add a variable to /etc/environment
  remove-env <var>                 Remove a variable from /etc/environment
  set-env KEY VALUE [KEY VALUE ...] Overwrite /etc/environment
  status                           Export full system status
  backup <dir>                     Backup all config files
  restore <dir>                    Restore from backup
  generate-locales [locale ...]    Run locale-gen
"""

    args = sys.argv[1:]
    if not args:
        print(usage)
        sys.exit(0)

    cmd = args[0].lower().replace("-", "_")

    try:
        if cmd == "get_timezone":
            _print_json(mgr.get_timezone())

        elif cmd == "set_timezone":
            if len(args) < 2:
                print("Error: set-timezone requires a timezone argument.")
                sys.exit(1)
            _print_json(mgr.set_timezone(args[1]))

        elif cmd == "list_timezones":
            region = args[1] if len(args) > 1 else None
            _print_json(mgr.list_timezones(region))

        elif cmd == "get_locale":
            _print_json(mgr.get_locale())

        elif cmd == "set_locale":
            if len(args) < 3 or len(args[1:]) % 2 != 0:
                print("Error: set-locale requires KEY VALUE pairs.")
                sys.exit(1)
            settings = {}
            kv_args = args[1:]
            for i in range(0, len(kv_args), 2):
                settings[kv_args[i]] = kv_args[i + 1]
            _print_json(mgr.set_locale(settings))

        elif cmd == "list_locales":
            _print_json(mgr.list_available_locales())

        elif cmd == "enable_locale":
            if len(args) < 2:
                print("Error: enable-locale requires a locale argument.")
                sys.exit(1)
            _print_json(mgr.enable_locale(args[1]))

        elif cmd == "disable_locale":
            if len(args) < 2:
                print("Error: disable-locale requires a locale argument.")
                sys.exit(1)
            _print_json(mgr.disable_locale(args[1]))

        elif cmd == "get_hwclock":
            _print_json(mgr.get_hwclock())

        elif cmd == "set_hwclock":
            if len(args) < 2:
                print("Error: set-hwclock requires 'utc' or 'localtime'.")
                sys.exit(1)
            _print_json(mgr.set_hwclock(args[1]))

        elif cmd == "get_environment":
            _print_json(mgr.get_environment())

        elif cmd == "add_env":
            if len(args) < 3:
                print("Error: add-env requires <variable> <value>.")
                sys.exit(1)
            _print_json(mgr.add_environment(args[1], args[2]))

        elif cmd == "remove_env":
            if len(args) < 2:
                print("Error: remove-env requires a variable name.")
                sys.exit(1)
            _print_json(mgr.remove_environment(args[1]))

        elif cmd == "set_env":
            if len(args) < 3 or len(args[1:]) % 2 != 0:
                print("Error: set-env requires KEY VALUE pairs.")
                sys.exit(1)
            variables = {}
            kv_args = args[1:]
            for i in range(0, len(kv_args), 2):
                variables[kv_args[i]] = kv_args[i + 1]
            _print_json(mgr.set_environment(variables))

        elif cmd == "status":
            _print_json(mgr.export_status())

        elif cmd == "backup":
            if len(args) < 2:
                print("Error: backup requires a destination directory.")
                sys.exit(1)
            _print_json(mgr.backup_all(args[1]))

        elif cmd == "restore":
            if len(args) < 2:
                print("Error: restore requires a backup directory path.")
                sys.exit(1)
            _print_json(mgr.restore_from_backup(args[1]))

        elif cmd == "generate_locales":
            locales = args[1:] if len(args) > 1 else None
            _print_json(mgr.generate_locales(locales))

        else:
            print(f"Unknown command: {args[0]}")
            print(usage)
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(130)
    except Exception as exc:
        _print_json({"success": False, "error": str(exc)})
        sys.exit(1)
