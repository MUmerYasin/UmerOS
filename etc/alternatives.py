#!/usr/bin/env python3
"""
UmerOS - /etc/alternatives manager
Alternatives system: manages symlink farms for program version switching.
Mimics /etc/alternatives, /var/lib/alternatives for master and per-alternative files.
Based on Debian 'update-alternatives' and Red Hat 'alternatives' systems.
"""
import os, json, shutil, subprocess, hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

ALTERNATIVES_DIR = Path(os.environ.get("UMEROS_ALTERNATIVES_DIR", "/etc/alternatives"))
VAR_ALTERNATIVES_DIR = Path(os.environ.get("UMEROS_VAR_ALTERNATIVES_DIR", "/var/lib/alternatives"))
SLAVES_DIR = Path(os.environ.get("UMEROS_SLAVES_DIR", "/etc/alternatives/slaves"))

# Standard alternatives groups (from Debian/Red Hat systems)
STANDARD_GROUPS = {
    "editor": "/usr/bin/editor",
    "x-www-browser": "/usr/bin/x-www-browser",
    "x-session-manager": "/usr/bin/x-session-manager",
    "x-window-manager": "/usr/bin/x-window-manager",
    "x-terminal-emulator": "/usr/bin/x-terminal-emulator",
    "x-cursor-theme": "/usr/share/icons/default/cursors",
    "x-cursor-theme-size": "/usr/share/icons/default/cursors",
    "x-cursor-theme-name": "/usr/share/icons/default/cursors",
    "x-inputres": "/usr/share/X11/locale",
    "python": "/usr/bin/python",
    "python3": "/usr/bin/python3",
    "node": "/usr/bin/node",
    "nodejs": "/usr/bin/nodejs",
    "java": "/usr/bin/java",
    "javac": "/usr/bin/javac",
    "gcc": "/usr/bin/gcc",
    "g++": "/usr/bin/g++",
    "make": "/usr/bin/make",
    "awk": "/usr/bin/awk",
    "sed": "/usr/bin/sed",
    "grep": "/usr/bin/grep",
    "tar": "/usr/bin/tar",
    "gzip": "/usr/bin/gzip",
    "bzip2": "/usr/bin/bzip2",
    "xz": "/usr/bin/xz",
    "ssh": "/usr/bin/ssh",
    "scp": "/usr/bin/scp",
    "sftp": "/usr/bin/sftp",
    "rsync": "/usr/bin/rsync",
    "git": "/usr/bin/git",
    "git-cvs": "/usr/bin/git-cvs",
    "git-email": "/usr/bin/git-email",
    "git-shell": "/usr/bin/git-shell",
    "gitk": "/usr/bin/gitk",
    "git-gui": "/usr/bin/git-gui",
    "cvs": "/usr/bin/cvs",
    "svn": "/usr/bin/svn",
    "hg": "/usr/bin/hg",
    "bzr": "/usr/bin/bzr",
    "mawk": "/usr/bin/mawk",
    "nawk": "/usr/bin/nawk",
    "gawk": "/usr/bin/gawk",
    "pico": "/usr/bin/pico",
    "nano": "/usr/bin/nano",
    "vim": "/usr/bin/vim",
    "vi": "/usr/bin/vi",
    "view": "/usr/bin/view",
    "rvim": "/usr/bin/rvim",
    "rview": "/usr/bin/rview",
    "xim": "/usr/bin/xim",
    "exim4": "/usr/sbin/exim4",
    "mailx": "/usr/bin/mailx",
    "mta": "/usr/sbin/mta",
    "mpack": "/usr/bin/mpack",
    "alpine": "/usr/bin/alpine",
    "pine": "/usr/bin/pine",
    "rsh": "/usr/bin/rsh",
    "rcp": "/usr/bin/rcp",
    "rlogin": "/usr/bin/rlogin",
    "whois": "/usr/bin/whois",
    "traceroute": "/usr/bin/traceroute",
    "route": "/usr/sbin/route",
    "ifconfig": "/usr/sbin/ifconfig",
    "ip": "/usr/bin/ip",
    "netstat": "/usr/bin/netstat",
    "ping": "/usr/bin/ping",
    "ping6": "/usr/bin/ping6",
    "hostname": "/bin/hostname",
    "dnsdomainname": "/bin/dnsdomainname",
    "domainname": "/bin/domainname",
    "nisdomainname": "/bin/nisdomainname",
    "ypdomainname": "/bin/ypdomainname",
    "xev": "/usr/bin/xev",
    "xdg-open": "/usr/bin/xdg-open",
    "xrandr": "/usr/bin/xrandr",
    "xrdb": "/usr/bin/xrdb",
    "xdpyinfo": "/usr/bin/xdpyinfo",
    "xprop": "/usr/bin/xprop",
    "xset": "/usr/bin/xset",
    "xlsatoms": "/usr/bin/xlsatoms",
    "xlsclients": "/usr/bin/xlsclients",
    "xwininfo": "/usr/bin/xwininfo",
    "xman": "/usr/bin/xman",
    "xdg-desktop-menu": "/usr/bin/xdg-desktop-menu",
    "xdg-desktop-icon": "/usr/bin/xdg-desktop-icon",
    "xdg-mime": "/usr/bin/xdg-mime",
    "xdg-icon-resource": "/usr/bin/xdg-icon-resource",
    "xdg-settings": "/usr/bin/xdg-settings",
    "desktop-menu": "/usr/bin/desktop-menu",
    "desktop-icon": "/usr/bin/desktop-icon",
    "cups": "/usr/sbin/cups",
    "lpr": "/usr/bin/lpr",
    "lprng": "/usr/bin/lprng",
    "mplayer": "/usr/bin/mplayer",
    "mencoder": "/usr/bin/mencoder",
    "x-www-browser": "/usr/bin/x-www-browser",
    "www-browser": "/usr/bin/www-browser",
    "www-text": "/usr/bin/www-text",
    "www-w3m": "/usr/bin/www-w3m",
    "www-links": "/usr/bin/www-links",
    "wwwlynx": "/usr/bin/wwwlynx",
    "lynx": "/usr/bin/lynx",
    "w3m": "/usr/bin/w3m",
    "links": "/usr/bin/links",
    "elinks": "/usr/bin/elinks",
    "opera": "/usr/bin/opera",
    "firefox": "/usr/bin/firefox",
    "iceweasel": "/usr/bin/iceweasel",
    "chromium-browser": "/usr/bin/chromium-browser",
    "google-chrome": "/usr/bin/google-chrome",
    "gconf2": "/usr/bin/gconftool-2",
    "gconf2-merge": "/usr/bin/gconf-merge",
    "gimp": "/usr/bin/gimp",
    "gimp-composite": "/usr/bin/gimp-composite",
    "gimp-console": "/usr/bin/gimp-console",
    "gvim": "/usr/bin/gvim",
    "gview": "/usr/bin/gview",
    "grub": "/usr/sbin/grub",
    "lilo": "/usr/sbin/lilo",
    "xloadimage": "/usr/bin/xloadimage",
    "xv": "/usr/bin/xv",
    "imagemagick": "/usr/bin/magick",
    "display-im6.q16": "/usr/bin/display-im6.q16",
    "compare-im6.q16": "/usr/bin/compare-im6.q16",
    "convert-im6.q16": "/usr/bin/convert-im6.q16",
    "composite-im6.q16": "/usr/bin/composite-im6.q16",
    "identify-im6.q16": "/usr/bin/identify-im6.q16",
    "import-im6.q16": "/usr/bin/import-im6.q16",
    "mogrify-im6.q16": "/usr/bin/mogrify-im6.q16",
    "montage-im6.q16": "/usr/bin/montage-im6.q16",
    "stream-im6.q16": "/usr/bin/stream-im6.q16",
}


class AlternativesManager:
    """Manages the alternatives system — symlink farm manager for program versions."""

    def __init__(self, alternatives_dir: Path = ALTERNATIVES_DIR,
                 var_dir: Path = VAR_ALTERNATIVES_DIR,
                 slaves_dir: Path = SLAVES_DIR):
        self.dir = Path(alternatives_dir)
        self.var_dir = Path(var_dir)
        self.slaves_dir = Path(slaves_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.var_dir.mkdir(parents=True, exist_ok=True)
        self.slaves_dir.mkdir(parents=True, exist_ok=True)

    # ── core operations ──────────────────────────────────────────────
    def list_all(self) -> Dict[str, Any]:
        """List all registered alternatives with their status."""
        alternatives = {}
        for item in self.var_dir.iterdir():
            if item.is_file():
                try:
                    data = json.loads(item.read_text())
                    alternatives[item.name] = self._parse_alternative_status(item.name, data)
                except Exception:
                    alternatives[item.name] = {"status": "corrupted", "path": str(item)}
        return alternatives

    def register(self, name: str, path: str, priority: int = 0,
                 slaves: Optional[List[Dict[str, str]]] = None, mode: str = "auto",
                 family: str = "") -> Dict[str, Any]:
        """Register a new alternative or update an existing one."""
        name = name.strip("/")
        alt_data = {
            "name": name,
            "path": path,
            "priority": priority,
            "slaves": slaves or [],
            "mode": mode,
            "family": family,
            "timestamp": datetime.now().isoformat(),
        }
        var_file = self.var_dir / name
        # preserve existing data if any
        if var_file.exists():
            try:
                existing = json.loads(var_file.read_text())
                alt_data["timestamp"] = existing.get("timestamp", alt_data["timestamp"])
            except Exception:
                pass
        var_file.write_text(json.dumps(alt_data, indent=2))
        # update symlink if auto mode
        if mode == "auto":
            self._update_symlink_auto(name, path, priority, slaves)
        elif mode == "manual":
            self._set_symlink(name, path, slaves)
        return {"action": "registered", "name": name, "path": path, "priority": priority}

    def unregister(self, name: str) -> Dict[str, Any]:
        """Remove an alternative registration."""
        name = name.strip("/")
        var_file = self.var_dir / name
        link = self.dir / name
        removed = []
        if link.exists() or link.is_symlink():
            link.unlink(missing_ok=True)
            removed.append(str(link))
        if var_file.exists():
            data = json.loads(var_file.read_text())
            for slave in data.get("slaves", []):
                slave_link = self.dir / slave["name"]
                if slave_link.exists() or slave_link.is_symlink():
                    slave_link.unlink(missing_ok=True)
                    removed.append(str(slave_link))
            var_file.unlink()
            removed.append(str(var_file))
        return {"action": "unregistered", "name": name, "removed": removed}

    def get_current(self, name: str) -> Optional[Dict[str, Any]]:
        """Get the currently active alternative for a group."""
        name = name.strip("/")
        var_file = self.var_dir / name
        if not var_file.exists():
            return None
        data = json.loads(var_file.read_text())
        return self._parse_alternative_status(name, data)

    def set_manual(self, name: str, path: str) -> Dict[str, Any]:
        """Manually set an alternative as the chosen one."""
        name = name.strip("/")
        var_file = self.var_dir / name
        if not var_file.exists():
            return {"error": f"Alternative '{name}' not registered", "action": "failed"}
        data = json.loads(var_file.read_text())
        data["mode"] = "manual"
        data["path"] = path
        data["timestamp"] = datetime.now().isoformat()
        var_file.write_text(json.dumps(data, indent=2))
        slaves = data.get("slaves", [])
        self._set_symlink(name, path, slaves)
        return {"action": "set_manual", "name": name, "path": path}

    def set_auto(self, name: str) -> Dict[str, Any]:
        """Switch an alternative back to automatic mode."""
        name = name.strip("/")
        var_file = self.var_dir / name
        if not var_file.exists():
            return {"error": f"Alternative '{name}' not registered", "action": "failed"}
        data = json.loads(var_file.read_text())
        data["mode"] = "auto"
        data["timestamp"] = datetime.now().isoformat()
        var_file.write_text(json.dumps(data, indent=2))
        self._update_symlink_auto(name, data["path"], data.get("priority", 0), data.get("slaves", []))
        return {"action": "set_auto", "name": name}

    def install(self, name: str, path: str, priority: int = 0,
                slaves: Optional[List[Dict[str, str]]] = None,
                force: bool = False, family: str = "") -> Dict[str, Any]:
        """Install an alternative — register and create the symlink."""
        name = name.strip("/")
        link = self.dir / name
        if link.exists() and not force:
            var_file = self.var_dir / name
            if var_file.exists():
                existing = json.loads(var_file.read_text())
                if existing.get("path") == path:
                    return {"action": "already_installed", "name": name, "path": path}
        return self.register(name, path, priority, slaves, "auto", family)

    def remove(self, name: str, path: str) -> Dict[str, Any]:
        """Remove a specific path from an alternative group."""
        name = name.strip("/")
        var_file = self.var_dir / name
        if not var_file.exists():
            return {"error": f"Alternative '{name}' not registered", "action": "failed"}
        data = json.loads(var_file.read_text())
        if data["path"] != path:
            return {"error": f"Path '{path}' is not the current alternative for '{name}'", "action": "failed"}
        # remove the entry
        var_file.unlink()
        link = self.dir / name
        if link.exists() or link.is_symlink():
            link.unlink()
        # remove slaves
        for slave in data.get("slaves", []):
            slave_link = self.dir / slave["name"]
            if slave_link.exists() or slave_link.is_symlink():
                slave_link.unlink()
        return {"action": "removed", "name": name, "path": path}

    def query(self, name: str) -> Optional[Dict[str, Any]]:
        """Query details about an alternative group."""
        name = name.strip("/")
        var_file = self.var_dir / name
        if not var_file.exists():
            return None
        data = json.loads(var_file.read_text())
        link = self.dir / name
        current_target = None
        if link.is_symlink():
            current_target = str(link.readlink())
        elif link.exists():
            current_target = str(link)
        return {
            "name": name,
            "path": data.get("path"),
            "priority": data.get("priority", 0),
            "mode": data.get("mode", "auto"),
            "family": data.get("family", ""),
            "slaves": data.get("slaves", []),
            "current_target": current_target,
            "timestamp": data.get("timestamp"),
        }

    def config_check(self, name: str) -> Dict[str, Any]:
        """Check if the current symlink matches the expected alternative."""
        name = name.strip("/")
        result = self.query(name)
        if result is None:
            return {"status": "not_found", "name": name}
        link = self.dir / name
        expected = result["path"]
        actual = None
        if link.is_symlink():
            actual = str(link.readlink())
        elif link.exists():
            actual = str(link)
        return {
            "status": "ok" if actual == expected else "mismatch",
            "name": name,
            "expected": expected,
            "actual": actual,
        }

    def list_slaves(self, name: str) -> List[Dict[str, str]]:
        """List all slaves for a given alternative group."""
        name = name.strip("/")
        result = self.query(name)
        if result is None:
            return []
        return result.get("slaves", [])

    def get_standard_groups(self) -> Dict[str, str]:
        """Return the list of standard alternatives groups."""
        return dict(STANDARD_GROUPS)

    def batch_register(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Register multiple alternatives in one call."""
        results = []
        for entry in entries:
            name = entry.get("name", "")
            path = entry.get("path", "")
            priority = entry.get("priority", 0)
            slaves = entry.get("slaves", [])
            mode = entry.get("mode", "auto")
            family = entry.get("family", "")
            if name and path:
                results.append(self.register(name, path, priority, slaves, mode, family))
            else:
                results.append({"error": "missing name or path", "entry": entry})
        return results

    # ── internal helpers ──────────────────────────────────────────────
    def _set_symlink(self, name: str, path: str, slaves: Optional[List[Dict[str, str]]] = None) -> None:
        """Create the master symlink and slave symlinks."""
        link = self.dir / name
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            link.unlink()
        link.symlink_to(path)
        for slave in (slaves or []):
            slave_link = self.dir / slave["name"]
            slave_link.parent.mkdir(parents=True, exist_ok=True)
            if slave_link.is_symlink():
                slave_link.unlink()
            elif slave_link.exists():
                slave_link.unlink()
            slave_link.symlink_to(slave.get("path", ""))

    def _update_symlink_auto(self, name: str, path: str, priority: int,
                             slaves: Optional[List[Dict[str, str]]] = None) -> None:
        """Update symlink automatically based on priority."""
        var_file = self.var_dir / name
        if not var_file.exists():
            return
        data = json.loads(var_file.read_text())
        current_priority = data.get("priority", 0)
        link = self.dir / name
        if link.is_symlink():
            current_target = str(link.readlink())
            if current_target == path:
                return
        self._set_symlink(name, path, slaves)

    def _parse_alternative_status(self, name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse an alternative entry and return human-readable status."""
        link = self.dir / name
        current_target = None
        if link.is_symlink():
            current_target = str(link.readlink())
        elif link.exists():
            current_target = str(link)
        return {
            "name": name,
            "path": data.get("path"),
            "priority": data.get("priority", 0),
            "mode": data.get("mode", "auto"),
            "family": data.get("family", ""),
            "slaves_count": len(data.get("slaves", [])),
            "current_target": current_target,
            "timestamp": data.get("timestamp"),
        }

    def export_status(self) -> Dict[str, Any]:
        """Export full alternatives status as JSON."""
        return {"alternatives": self.list_all(), "standard_groups": self.get_standard_groups()}

    def import_entries(self, entries: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Import alternatives from a dictionary."""
        results = []
        for name, data in entries.items():
            if isinstance(data, dict):
                results.append(self.register(
                    name=name,
                    path=data.get("path", ""),
                    priority=data.get("priority", 0),
                    slaves=data.get("slaves", []),
                    mode=data.get("mode", "auto"),
                    family=data.get("family", ""),
                ))
        return results

    def cleanup(self) -> Dict[str, Any]:
        """Remove dangling symlinks and orphaned var files."""
        removed_links = []
        removed_vars = []
        for item in self.dir.iterdir():
            if item.is_symlink() and not item.exists():
                item.unlink()
                removed_links.append(str(item))
        for item in self.var_dir.iterdir():
            if item.is_file():
                try:
                    data = json.loads(item.read_text())
                    name = data.get("name", item.name)
                    expected_path = data.get("path", "")
                    if expected_path and not os.path.exists(expected_path):
                        pass
                except Exception:
                    pass
        return {"removed_links": removed_links, "removed_vars": removed_vars}

    def backup(self, backup_path: Optional[Path] = None) -> Path:
        """Backup alternatives state."""
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = Path(f"/var/backups/alternatives_{timestamp}.json")
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_data = {
            "timestamp": datetime.now().isoformat(),
            "alternatives": self.list_all(),
            "standard_groups": self.get_standard_groups(),
        }
        backup_path.write_text(json.dumps(backup_data, indent=2))
        return backup_path
