"""
UmerOS /var/lib — State Information Manager
=============================================
Implements the FHS ``/var/lib`` directory which holds *state
information* — data that programs modify while they run and that
pertains to one specific host.

Per FHS:

  /var/lib/<app>     — per-application state
  /var/lib/misc      — state files that don't need their own subdirectory
  /var/lib/<name>    — distribution package manager database (rpm, dpkg)
  /var/lib/locate    — updatedb database for ``locate``
  /var/lib/games     — game state (scores, etc.)
  /var/lib/<editor>  — editor state (vim, emacs)
  /var/lib/alternatives — the Debian/Ubuntu alternatives system
  /var/lib/dpkg      — dpkg package database
  /var/lib/rpm       — rpm package database
  /var/lib/systemd   — systemd state (random seed, etc.)
  /var/lib/apt       — apt state (lists, extended_states)
  /var/lib/dhcp      — DHCP client leases
  /var/lib/chrony    — chrony NTP drift
  /var/lib/mlocate   — mlocate database
  /var/lib/plymouth  — plymouth boot splash state
  /var/lib/sudo      — sudo timestamp database
  /var/lib/logrotate — logrotate state
  /var/lib/alsa      — ALSA state
  /var/lib/dbus      — D-Bus machine ID
  /var/lib/AccountsService — user account info cache
  /var/lib/NetworkManager — NM state
  /var/lib/private   — systemd-private tmpfs
  /var/lib/rkhunter  — rkhunter state

LD-specific (the dynamic linker state files also live here):
  /var/lib/ld.so.cache is /etc/ld.so.cache on most distros.

This module is *not* a copy of the kernel_state; it is the on-disk
companion to /etc configuration.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

log = logging.getLogger("UmerOS.Lib.VarLib")


class StateKind(str, Enum):
    PACKAGE_DB   = "package_db"
    GAME_SCORES  = "game_scores"
    LOCATE_DB    = "locate_db"
    ALTERNATIVES  = "alternatives"
    DPKG         = "dpkg"
    RPM          = "rpm"
    APT          = "apt"
    DNF          = "dnf"
    SYSTEMD      = "systemd"
    DHCP         = "dhcp"
    CHRONY       = "chrony"
    NTP          = "ntp"
    NETWORK      = "network"
    DBUS         = "dbus"
    PLYMOUTH     = "plymouth"
    SUDO         = "sudo"
    LOGROTATE    = "logrotate"
    ALSA         = "alsa"
    ACCOUNTS     = "accounts"
    MACHINE_ID   = "machine_id"
    PRIVATE      = "private"
    MISC         = "misc"
    APP_GENERIC  = "app_generic"


@dataclass
class VarLibEntry:
    """One /var/lib directory or file."""
    name: str
    path: str
    kind: StateKind
    description: str
    is_directory: bool = True
    size: int = 0
    owner: str = "root"            # user:group
    mode: int = 0o755
    backing_format: str = ""        # e.g. "Berkeley DB", "SQLite", "binary"
    read_only: bool = False
    persistent_across_reboot: bool = True
    version: str = ""
    depends_on: List[str] = field(default_factory=list)


# Stock /var/lib entries
_STOCK_VARLIB: List[VarLibEntry] = [
    VarLibEntry("misc",     "/var/lib/misc", StateKind.MISC,
        "Per-host state files that don't need a subdir",
        is_directory=True, owner="root:root", mode=0o755, persistent_across_reboot=True,
        backing_format=""),
    VarLibEntry("locate",   "/var/lib/locate", StateKind.LOCATE_DB,
        "mlocate / locate database",
        is_directory=True, owner="root:mlocate", mode=0o2755,
        backing_format="binary inverted index"),
    VarLibEntry("mlocate",  "/var/lib/mlocate", StateKind.LOCATE_DB,
        "mlocate working copy of /var/lib/locate",
        is_directory=True, owner="root:mlocate", mode=0o2755,
        backing_format="binary inverted index"),
    VarLibEntry("dpkg",     "/var/lib/dpkg", StateKind.DPKG,
        "dpkg package database (status, available, diversions, etc.)",
        is_directory=True, owner="root:root", mode=0o755,
        backing_format="Debian package format",
        depends_on=["/var/lib/dpkg/status", "/var/lib/dpkg/available"]),
    VarLibEntry("dpkg/status",  "/var/lib/dpkg/status", StateKind.DPKG,
        "Installed package list (text file)",
        is_directory=False, owner="root:root", mode=0o644,
        backing_format="Debian control file"),
    VarLibEntry("dpkg/available", "/var/lib/dpkg/available", StateKind.DPKG,
        "Available package list",
        is_directory=False, owner="root:root", mode=0o644,
        backing_format="Debian control file"),
    VarLibEntry("rpm",      "/var/lib/rpm", StateKind.RPM,
        "rpm package database (Berkeley DB / SQLite)",
        is_directory=True, owner="root:root", mode=0o755,
        backing_format="Berkeley DB or SQLite",
        depends_on=["/var/lib/rpm/Packages", "/var/lib/rpm/rpmdb.sqlite"]),
    VarLibEntry("rpm/Packages", "/var/lib/rpm/Packages", StateKind.RPM,
        "rpm Berkeley DB index",
        is_directory=False, owner="root:root", mode=0o644,
        backing_format="Berkeley DB"),
    VarLibEntry("rpm/rpmdb.sqlite", "/var/lib/rpm/rpmdb.sqlite", StateKind.RPM,
        "rpm SQLite index (modern)",
        is_directory=False, owner="root:root", mode=0o644,
        backing_format="SQLite3"),
    VarLibEntry("apt",      "/var/lib/apt", StateKind.APT,
        "apt package manager state",
        is_directory=True, owner="root:root", mode=0o755,
        backing_format="debian control files",
        depends_on=["/var/lib/apt/lists", "/var/lib/apt/extended_states"]),
    VarLibEntry("apt/lists",     "/var/lib/apt/lists", StateKind.APT,
        "apt download cache of repo metadata",
        is_directory=True, owner="root:root", mode=0o755,
        backing_format="debian control files"),
    VarLibEntry("apt/extended_states", "/var/lib/apt/extended_states", StateKind.APT,
        "apt auto-installed/auto-removed tracking",
        is_directory=False, owner="root:root", mode=0o644,
        backing_format="debian extended_states"),
    VarLibEntry("dnf",      "/var/lib/dnf", StateKind.DNF,
        "dnf package manager state",
        is_directory=True, owner="root:root", mode=0o755,
        backing_format="hawkey/solv"),
    VarLibEntry("systemd",  "/var/lib/systemd", StateKind.SYSTEMD,
        "systemd persistent state (random-seed, timesync, etc.)",
        is_directory=True, owner="root:root", mode=0o755),
    VarLibEntry("systemd/random-seed", "/var/lib/systemd/random-seed", StateKind.SYSTEMD,
        "Entropy seed for early-boot RNG",
        is_directory=False, owner="root:root", mode=0o600,
        backing_format="binary"),
    VarLibEntry("systemd/timesync", "/var/lib/systemd/timesync", StateKind.SYSTEMD,
        "systemd-timesyncd state",
        is_directory=True, owner="systemd-timesync:systemd-timesync", mode=0o755,
        backing_format="INI"),
    VarLibEntry("dhcp",     "/var/lib/dhcp", StateKind.DHCP,
        "DHCP client lease files",
        is_directory=True, owner="root:root", mode=0o755,
        backing_format="ISC dhclient lease format"),
    VarLibEntry("dhclient", "/var/lib/dhclient", StateKind.DHCP,
        "dhclient lease database",
        is_directory=True, owner="root:root", mode=0o755),
    VarLibEntry("chrony",   "/var/lib/chrony", StateKind.CHRONY,
        "chrony drift / tracking state",
        is_directory=True, owner="root:chrony", mode=0o750,
        backing_format="custom binary"),
    VarLibEntry("ntp",      "/var/lib/ntp", StateKind.NTP,
        "ntpd drift / leap-second state",
        is_directory=True, owner="ntp:ntp", mode=0o755),
    VarLibEntry("ntp/ntp.drift", "/var/lib/ntp/ntp.drift", StateKind.NTP,
        "NTP frequency drift file",
        is_directory=False, owner="ntp:ntp", mode=0o644,
        backing_format="ASCII ppm"),
    VarLibEntry("NetworkManager", "/var/lib/NetworkManager", StateKind.NETWORK,
        "NetworkManager state (timestamps, secrets tokens)",
        is_directory=True, owner="root:root", mode=0o755),
    VarLibEntry("sudo",     "/var/lib/sudo", StateKind.SUDO,
        "sudo timestamp database (lecture, tty tickets)",
        is_directory=True, owner="root:root", mode=0o700,
        backing_format="custom binary"),
    VarLibEntry("sudo/ts",  "/var/lib/sudo/ts", StateKind.SUDO,
        "sudo timestamped ticket cache",
        is_directory=True, owner="root:root", mode=0o700,
        backing_format="custom binary"),
    VarLibEntry("logrotate.status", "/var/lib/logrotate.status", StateKind.LOGROTATE,
        "logrotate per-log last-rotation timestamp",
        is_directory=False, owner="root:root", mode=0o644,
        backing_format="key=value lines"),
    VarLibEntry("alsa",     "/var/lib/alsa", StateKind.ALSA,
        "ALSA persistent state (asound.state)",
        is_directory=True, owner="root:audio", mode=0o755),
    VarLibEntry("alsa/asound.state", "/var/lib/alsa/asound.state", StateKind.ALSA,
        "ALSA mixer state (saved by alsactl)",
        is_directory=False, owner="root:audio", mode=0o644,
        backing_format="custom binary"),
    VarLibEntry("dbus",     "/var/lib/dbus", StateKind.DBUS,
        "D-Bus machine id & state",
        is_directory=True, owner="root:root", mode=0o755),
    VarLibEntry("dbus/machine-id", "/var/lib/dbus/machine-id", StateKind.MACHINE_ID,
        "D-Bus per-machine UUID (used by systemd too)",
        is_directory=False, owner="root:root", mode=0o444,
        backing_format="32-char hex UUID, no newline"),
    VarLibEntry("AccountsService", "/var/lib/AccountsService", StateKind.ACCOUNTS,
        "AccountsService user icons + cached account data",
        is_directory=True, owner="root:root", mode=0o755),
    VarLibEntry("plymouth", "/var/lib/plymouth", StateKind.PLYMOUTH,
        "plymouth boot-splash state",
        is_directory=True, owner="root:root", mode=0o755),
    VarLibEntry("private",  "/var/lib/private", StateKind.PRIVATE,
        "systemd-private per-service namespaces",
        is_directory=True, owner="root:root", mode=0o755,
        persistent_across_reboot=False,
        backing_format="tmpfs"),
    VarLibEntry("games",    "/var/lib/games", StateKind.GAME_SCORES,
        "Game state (scores, saved games)",
        is_directory=True, owner="root:games", mode=0o775,
        backing_format=""),
    VarLibEntry("vim",      "/var/lib/vim", StateKind.APP_GENERIC,
        "vim persistent undo / plugin state",
        is_directory=True, owner="root:root", mode=0o755),
    VarLibEntry("emacs",    "/var/lib/emacs", StateKind.APP_GENERIC,
        "Emacs site-wide package state",
        is_directory=True, owner="root:root", mode=0o755),
    VarLibEntry("rkhunter", "/var/lib/rkhunter", StateKind.APP_GENERIC,
        "rkhunter baseline + database",
        is_directory=True, owner="root:root", mode=0o755),
]


# ─────────────────────────────────────────────────────────────────────────────
#  Alternatives system
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Alternative:
    """
    One row of the Debian/Ubuntu alternatives system.

    Example::
        /usr/bin/python  -> /usr/bin/python3.11  (priority 100)
    """
    name: str                              # the generic name, e.g. "editor"
    link: str                              # the symlink, e.g. "/usr/bin/editor"
    candidates: Dict[str, int] = field(default_factory=dict)
    """{candidate path: priority}"""
    current: str = ""                      # currently-selected candidate
    auto_mode: bool = True

    def select(self, candidate: str) -> bool:
        if candidate not in self.candidates:
            return False
        self.current = candidate
        return True

    def best_candidate(self) -> Optional[str]:
        if not self.candidates:
            return None
        return max(self.candidates.items(), key=lambda kv: kv[1])[0]


_STOCK_ALTERNATIVES: List[Alternative] = [
    Alternative(
        "editor", "/usr/bin/editor",
        candidates={
            "/usr/bin/vim.basic":  50,
            "/usr/bin/vim.tiny":   30,
            "/usr/bin/nano":       40,
            "/usr/bin/ed":         10,
        },
        current="/usr/bin/vim.basic",
    ),
    Alternative(
        "awk", "/usr/bin/awk",
        candidates={
            "/usr/bin/gawk":    10,
            "/usr/bin/mawk":    20,
            "/usr/bin/original-awk":  5,
        },
        current="/usr/bin/mawk",
    ),
    Alternative(
        "pager", "/usr/bin/pager",
        candidates={
            "/usr/bin/less":  10,
            "/usr/bin/more":   5,
            "/usr/bin/most":  15,
        },
        current="/usr/bin/less",
    ),
    Alternative(
        "python", "/usr/bin/python",
        candidates={
            "/usr/bin/python3.10": 10,
            "/usr/bin/python3.11": 20,
            "/usr/bin/python3.12": 30,
            "/usr/bin/python2.7":   5,
        },
        current="/usr/bin/python3.12",
    ),
    Alternative(
        "c++", "/usr/bin/c++",
        candidates={
            "/usr/bin/g++": 20,
            "/usr/bin/clang++": 10,
        },
        current="/usr/bin/g++",
    ),
    Alternative(
        "cc", "/usr/bin/cc",
        candidates={
            "/usr/bin/gcc":  20,
            "/usr/bin/clang": 10,
        },
        current="/usr/bin/gcc",
    ),
    Alternative(
        "java", "/usr/bin/java",
        candidates={
            "/usr/lib/jvm/java-17-openjdk-amd64/bin/java": 1700,
            "/usr/lib/jvm/java-21-openjdk-amd64/bin/java": 2100,
        },
        current="/usr/lib/jvm/java-21-openjdk-amd64/bin/java",
    ),
]


class AlternativesManager:
    """
    Manages ``/var/lib/dpkg/alternatives`` (the Debian alternatives DB).
    """

    def __init__(self) -> None:
        self._alts: Dict[str, Alternative] = {
            a.name: a for a in _STOCK_ALTERNATIVES
        }

    def list_alternatives(self) -> List[Alternative]:
        return list(self._alts.values())

    def get(self, name: str) -> Optional[Alternative]:
        return self._alts.get(name)

    def add(self, alternative: Alternative) -> None:
        self._alts[alternative.name] = alternative

    def remove(self, name: str) -> bool:
        return self._alts.pop(name, None) is not None

    def set_candidate(self, name: str, candidate: str) -> bool:
        alt = self._alts.get(name)
        if alt is None:
            return False
        return alt.select(candidate)

    def auto_select(self, name: str) -> bool:
        alt = self._alts.get(name)
        if alt is None:
            return False
        best = alt.best_candidate()
        if best is None:
            return False
        alt.current = best
        alt.auto_mode = True
        return True

    def export_state(self) -> str:
        """Serialise to a flat text format (similar to alternatives DB)."""
        lines: List[str] = []
        for a in self._alts.values():
            lines.append(f"auto/{a.name}")
            lines.append(f"link={a.link}")
            for cand, prio in a.candidates.items():
                lines.append(f"  {cand} {prio}")
            lines.append(f"current={a.current}")
            lines.append("")
        return "\n".join(lines)

    def get_summary(self) -> Dict:
        return {
            "total_alternatives": len(self._alts),
            "links": [a.link for a in self._alts.values()],
            "auto_mode": sum(1 for a in self._alts.values() if a.auto_mode),
        }


class VarLibManager:
    """
    Manages the ``/var/lib`` directory tree and per-application state.
    """

    def __init__(self, var_path: str = "/var") -> None:
        self.var_path = Path(var_path)
        self.lib_path = self.var_path / "lib"
        self._entries: Dict[str, VarLibEntry] = {e.name: e for e in _STOCK_VARLIB}
        self.alternatives = AlternativesManager()

    # ── directory layout ──────────────────────────────────────────

    def list_entries(self) -> List[VarLibEntry]:
        return list(self._entries.values())

    def get_entry(self, name: str) -> Optional[VarLibEntry]:
        return self._entries.get(name)

    def by_kind(self, kind: StateKind) -> List[VarLibEntry]:
        return [e for e in self._entries.values() if e.kind == kind]

    def subdirectories(self) -> List[VarLibEntry]:
        return [e for e in self._entries.values() if e.is_directory]

    def register_entry(self, entry: VarLibEntry) -> None:
        self._entries[entry.name] = entry

    # ── on-disk materialisation ───────────────────────────────────

    def materialise_stubs(self, root: str = "/") -> int:
        target = Path(root) / "var" / "lib"
        target.mkdir(parents=True, exist_ok=True)
        written = 0
        for entry in self._entries.values():
            p = target / entry.path[len("/var/lib/"):]
            if entry.is_directory:
                p.mkdir(parents=True, exist_ok=True)
            elif not p.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(
                    f"UmerOS /var/lib stub for {entry.name}\n".encode()
                )
                written += 1
        # Write alternatives DB
        alt_path = target / "dpkg" / "alternatives"
        alt_path.parent.mkdir(parents=True, exist_ok=True)
        alt_path.write_text(self.alternatives.export_state(), encoding="utf-8")
        return written

    # ── summary ───────────────────────────────────────────────────

    def get_summary(self) -> Dict:
        return {
            "total_entries": len(self._entries),
            "directories": len(self.subdirectories()),
            "files": len(self._entries) - len(self.subdirectories()),
            "by_kind": {k.value: len(self.by_kind(k)) for k in StateKind},
            "alternatives": self.alternatives.get_summary(),
            "directory": str(self.lib_path),
        }


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------

def _selftest():
    """Run a basic self-test for this module."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = VarLibManager(var_path=tmpdir)
        summary = mgr.get_summary()
        assert "total_entries" in summary, "summary should have total_entries"

    print("selftest OK")
    return True


if __name__ == "__main__":
    _selftest()
