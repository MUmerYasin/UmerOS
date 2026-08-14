"""
UmerOS Init System Configuration Manager

Manages init system configuration files:
  - /etc/inittab (SysV init default runlevel and actions)
  - /etc/init.d/ (service scripts)
  - /etc/rc?.d/ (rc0.d through rc6.d, symlinks for enable/disable)
  - /etc/systemd/ (systemd units: services, timers, mounts, sockets, targets)

Conventions:
  - All paths are constructed relative to a configurable base_path (default "/")
  - All I/O uses pathlib.Path
  - Data is persisted as JSON where appropriate
  - Methods return Dict[str, Any] with "success" key and optional "data"/"error"

UmerOS 2026
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INITTAB_PATH = "/etc/inittab"
INIT_D_DIR = "/etc/init.d"
RC_DIRS = [f"/etc/rc{rl}.d" for rl in range(7)]
SYSTEMD_DIR = "/etc/systemd"
SYSTEMD_SYSTEM_DIR = "/etc/systemd/system"
SYSTEMD_USER_DIR = "/etc/systemd/user"
SYSTEMD_WANTS_DIR = "/etc/systemd/system/multi-user.target.wants"
DEFAULT_RUNLEVEL = 3
SYSTEMD_SERVICE_EXAMPLE: Dict[str, str] = {
    "Unit": "Description=UmerOS Service\nAfter=network.target",
    "Service": "Type=simple\nExecStart=/usr/bin/example\nRestart=on-failure",
    "Install": "WantedBy=multi-user.target",
}
LSB_HEADER_TEMPLATE = (
    "### BEGIN INIT INFO\n"
    "# {name}\n"
    "# Required-Start:    $remote_fs $syslog\n"
    "# Required-Stop:     $remote_fs $syslog\n"
    "# Default-Start:     {default_start}\n"
    "# Default-Stop:      {default_stop}\n"
    "# Short-Description: {name} init script\n"
    "### END INIT INFO\n"
)


class InitSystemManager:
    """Manages SysV init, rc directories, and systemd configuration files.

    Parameters
    ----------
    base_path : str, optional
        Root directory prefix for all filesystem operations (default ``"/"``).
        Useful for chroot or test environments.

    Example
    -------
    >>> mgr = InitSystemManager(base_path="/tmp/testroot")
    >>> mgr.list_all()
    {"success": True, "data": {"inittab": ..., "init_scripts": ..., ...}}
    """

    # ------------------------------------------------------------------
    # Construction / initialisation
    # ------------------------------------------------------------------

    def __init__(self, base_path: str = "/") -> None:
        self._base = Path(base_path).resolve()

        # Ensure directory tree exists
        self._init_d = self._base / INIT_D_DIR.lstrip("/")
        self._inittab = self._base / INITTAB_PATH.lstrip("/")
        self._systemd = self._base / SYSTEMD_DIR.lstrip("/")
        self._systemd_system = self._base / SYSTEMD_SYSTEM_DIR.lstrip("/")
        self._systemd_user = self._base / SYSTEMD_USER_DIR.lstrip("/")
        self._systemd_wants = self._base / SYSTEMD_WANTS_DIR.lstrip("/")

        for d in [
            self._init_d,
            self._systemd_system,
            self._systemd_user,
            self._systemd_wants,
        ]:
            d.mkdir(parents=True, exist_ok=True)

        # Create rc0.d through rc6.d
        for rl_dir in [Path(self._base) / d.lstrip("/") for d in RC_DIRS]:
            rl_dir.mkdir(parents=True, exist_ok=True)

        # Create inittab with default runlevel if absent
        if not self._inittab.exists():
            self._write_inittab(
                default_runlevel=DEFAULT_RUNLEVEL,
                actions=[],
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ok(self, data: Any = None) -> Dict[str, Any]:
        """Return a success envelope."""
        result: Dict[str, Any] = {"success": True}
        if data is not None:
            result["data"] = data
        return result

    def _err(self, message: str) -> Dict[str, Any]:
        """Return a failure envelope."""
        return {"success": False, "error": message}

    # -- inittab helpers -------------------------------------------------

    def _write_inittab(
        self,
        default_runlevel: int = DEFAULT_RUNLEVEL,
        actions: Optional[List[Tuple[str, str, str]]] = None,
    ) -> None:
        """Persist /etc/inittab from structured data."""
        lines: List[str] = [
            "# /etc/inittab  --  UmerOS init configuration",
            "",
            "# Default runlevel",
            f"id:{default_runlevel}:initdefault:",
            "",
        ]
        if actions:
            lines.append("# Custom actions")
            for aid, rlv, act in actions:
                lines.append(f"{aid}:{rlv}:{act}:")
            lines.append("")
        self._inittab.parent.mkdir(parents=True, exist_ok=True)
        self._inittab.write_text("\n".join(lines), encoding="utf-8")

    def _parse_inittab(self) -> Dict[str, Any]:
        """Parse the inittab file into structured data."""
        default_runlevel = DEFAULT_RUNLEVEL
        actions: List[Dict[str, str]] = []
        if not self._inittab.exists():
            return {
                "default_runlevel": default_runlevel,
                "actions": actions,
                "raw": "",
            }
        raw = self._inittab.read_text(encoding="utf-8")
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) < 3:
                continue
            action_id, runlevels, action = parts[0], parts[1], parts[2]
            if action_id == "id" and action == "initdefault":
                try:
                    default_runlevel = int(runlevels)
                except ValueError:
                    pass
            else:
                actions.append(
                    {"id": action_id, "runlevels": runlevels, "action": action}
                )
        return {
            "default_runlevel": default_runlevel,
            "actions": actions,
            "raw": raw,
        }

    def _rc_dir(self, runlevel: int) -> Path:
        """Return the rc directory path for a given runlevel."""
        return self._base / f"etc/rc{runlevel}.d"

    # ------------------------------------------------------------------
    # 1. inittab operations
    # ------------------------------------------------------------------

    def get_inittab(self) -> Dict[str, Any]:
        """Read the current /etc/inittab contents.

        Returns
        -------
        dict
            ``{"success": True, "data": {"default_runlevel": int,
            "actions": [...], "raw": str}}``
        """
        try:
            return self._ok(self._parse_inittab())
        except Exception as exc:
            return self._err(f"Failed to read inittab: {exc}")

    def set_inittab_runlevel(self, runlevel: int) -> Dict[str, Any]:
        """Set the default runlevel in /etc/inittab.

        Parameters
        ----------
        runlevel : int
            Target runlevel (0-6).

        Returns
        -------
        dict
            Success/failure envelope.
        """
        try:
            parsed = self._parse_inittab()
            actions = [
                (a["id"], a["runlevels"], a["action"]) for a in parsed["actions"]
            ]
            self._write_inittab(default_runlevel=runlevel, actions=actions)
            return self._ok({"default_runlevel": runlevel})
        except Exception as exc:
            return self._err(f"Failed to set runlevel: {exc}")

    def set_inittab_action(
        self, action_id: str, runlevels: str, action: str
    ) -> Dict[str, Any]:
        """Add or modify an action line in /etc/inittab.

        Parameters
        ----------
        action_id : str
            Action identifier (e.g. ``"ca"``, ``"kb"``).
        runlevels : str
            Runlevels this action applies to (e.g. ``"12345"``).
        action : str
            Action to execute (e.g. ``"ctrlaltdel"``).

        Returns
        -------
        dict
            Success/failure envelope.
        """
        try:
            parsed = self._parse_inittab()
            updated = False
            for i, a in enumerate(parsed["actions"]):
                if a["id"] == action_id:
                    parsed["actions"][i] = {
                        "id": action_id,
                        "runlevels": runlevels,
                        "action": action,
                    }
                    updated = True
                    break
            if not updated:
                parsed["actions"].append(
                    {"id": action_id, "runlevels": runlevels, "action": action}
                )
            actions = [
                (a["id"], a["runlevels"], a["action"]) for a in parsed["actions"]
            ]
            self._write_inittab(
                default_runlevel=parsed["default_runlevel"],
                actions=actions,
            )
            return self._ok({"action_id": action_id, "runlevels": runlevels, "action": action})
        except Exception as exc:
            return self._err(f"Failed to set inittab action: {exc}")

    # ------------------------------------------------------------------
    # 2. init.d script management
    # ------------------------------------------------------------------

    def list_init_scripts(self) -> Dict[str, Any]:
        """List scripts in /etc/init.d/.

        Returns
        -------
        dict
            ``{"success": True, "data": [{"name": str, "size": int,
            "permissions": str, "is_executable": bool}, ...]}``
        """
        try:
            scripts: List[Dict[str, Any]] = []
            if self._init_d.exists():
                for p in sorted(self._init_d.iterdir()):
                    if p.is_file():
                        st = p.stat()
                        scripts.append(
                            {
                                "name": p.name,
                                "size": st.st_size,
                                "permissions": stat.filemode(st.st_mode),
                                "is_executable": os.access(p, os.X_OK),
                            }
                        )
            return self._ok(scripts)
        except Exception as exc:
            return self._err(f"Failed to list init scripts: {exc}")

    def add_init_script(self, name: str, content: str) -> Dict[str, Any]:
        """Write a new init script to /etc/init.d/.

        Parameters
        ----------
        name : str
            Script filename (without path).
        content : str
            Full script content including shebang.

        Returns
        -------
        dict
            Success/failure envelope.
        """
        try:
            target = self._init_d / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            target.chmod(0o755)
            return self._ok({"name": name, "path": str(target), "permissions": "0755"})
        except Exception as exc:
            return self._err(f"Failed to add init script '{name}': {exc}")

    def remove_init_script(self, name: str) -> Dict[str, Any]:
        """Remove an init script from /etc/init.d/.

        Parameters
        ----------
        name : str
            Script filename.

        Returns
        -------
        dict
            Success/failure envelope.
        """
        try:
            target = self._init_d / name
            if not target.exists():
                return self._err(f"Init script '{name}' does not exist")
            target.unlink()
            return self._ok({"removed": name})
        except Exception as exc:
            return self._err(f"Failed to remove init script '{name}': {exc}")

    # ------------------------------------------------------------------
    # 3. rc?.d enable / disable
    # ------------------------------------------------------------------

    def enable_init_script(self, name: str, runlevels: List[int]) -> Dict[str, Any]:
        """Enable an init script for the given runlevels by creating S-symlinks.

        Parameters
        ----------
        name : str
            Script name in /etc/init.d/.
        runlevels : list of int
            Runlevels to enable (e.g. ``[2, 3, 4, 5]``).

        Returns
        -------
        dict
            Success/failure envelope.
        """
        try:
            source = self._init_d / name
            if not source.exists():
                return self._err(f"Init script '{name}' does not exist in {self._init_d}")
            created: List[Dict[str, str]] = []
            for rl in runlevels:
                rc_dir = self._rc_dir(rl)
                rc_dir.mkdir(parents=True, exist_ok=True)
                link_path = rc_dir / f"S099{name}"
                if link_path.is_symlink():
                    link_path.unlink()
                link_path.symlink_to(f"/etc/init.d/{name}")
                created.append({"runlevel": rl, "link": str(link_path)})
            return self._ok({"script": name, "enabled_for": runlevels, "links": created})
        except Exception as exc:
            return self._err(f"Failed to enable init script '{name}': {exc}")

    def disable_init_script(self, name: str, runlevels: List[int]) -> Dict[str, Any]:
        """Disable an init script for the given runlevels by removing S/K symlinks.

        Parameters
        ----------
        name : str
            Script name.
        runlevels : list of int
            Runlevels to disable.

        Returns
        -------
        dict
            Success/failure envelope.
        """
        try:
            removed: List[Dict[str, str]] = []
            for rl in runlevels:
                rc_dir = self._rc_dir(rl)
                for prefix in ("S", "K"):
                    link_path = rc_dir / f"{prefix}099{name}"
                    if link_path.is_symlink():
                        link_path.unlink()
                        removed.append({"runlevel": rl, "link": str(link_path)})
            return self._ok({"script": name, "disabled_for": runlevels, "removed_links": removed})
        except Exception as exc:
            return self._err(f"Failed to disable init script '{name}': {exc}")

    def list_enabled_scripts(self, runlevel: int) -> Dict[str, Any]:
        """List enabled scripts (S-symlinks) for a given runlevel.

        Parameters
        ----------
        runlevel : int
            Runlevel to inspect.

        Returns
        -------
        dict
            ``{"success": True, "data": [{"name": str, "target": str,
            "priority": int}, ...]}``
        """
        try:
            rc_dir = self._rc_dir(runlevel)
            scripts: List[Dict[str, Any]] = []
            if rc_dir.exists():
                for p in sorted(rc_dir.iterdir()):
                    name = p.name
                    if name.startswith("S") and p.is_symlink():
                        try:
                            priority = int(name[1:4])
                        except (ValueError, IndexError):
                            priority = 0
                        scripts.append(
                            {
                                "name": name[4:],
                                "target": str(p.resolve()),
                                "priority": priority,
                            }
                        )
            return self._ok(scripts)
        except Exception as exc:
            return self._err(f"Failed to list enabled scripts for runlevel {runlevel}: {exc}")

    # ------------------------------------------------------------------
    # 4. systemd services
    # ------------------------------------------------------------------

    def _systemd_unit_path(self, name: str, suffix: str = ".service") -> Path:
        """Return the filesystem path for a systemd unit."""
        return self._systemd_system / f"{name}{suffix}"

    def create_systemd_service(
        self, name: str, unit_config: Dict[str, str]
    ) -> Dict[str, Any]:
        """Create a systemd service unit file.

        Parameters
        ----------
        name : str
            Service name (without ``.service`` suffix).
        unit_config : dict
            Section content mapping.  Recognised keys: ``"Unit"``,
            ``"Service"``, ``"Install"``.  Each value is a multi-line string
            with ``key=value`` pairs for that section.

        Returns
        -------
        dict
            Success/failure envelope.
        """
        try:
            path = self._systemd_unit_path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            lines: List[str] = []
            for section in ("Unit", "Service", "Install"):
                content = unit_config.get(section, "")
                if content:
                    lines.append(f"[{section}]")
                    lines.extend(content.strip().splitlines())
                    lines.append("")
            path.write_text("\n".join(lines), encoding="utf-8")
            return self._ok({"name": name, "path": str(path)})
        except Exception as exc:
            return self._err(f"Failed to create systemd service '{name}': {exc}")

    def list_systemd_services(self) -> Dict[str, Any]:
        """List all .service files in the system systemd directory.

        Returns
        -------
        dict
            ``{"success": True, "data": [{"name": str, "path": str,
            "size": int}, ...]}``
        """
        try:
            services: List[Dict[str, Any]] = []
            if self._systemd_system.exists():
                for p in sorted(self._systemd_system.iterdir()):
                    if p.is_file() and p.suffix == ".service":
                        st = p.stat()
                        services.append(
                            {"name": p.stem, "path": str(p), "size": st.st_size}
                        )
            return self._ok(services)
        except Exception as exc:
            return self._err(f"Failed to list systemd services: {exc}")

    def get_systemd_service(self, name: str) -> Dict[str, Any]:
        """Read a systemd service unit file.

        Parameters
        ----------
        name : str
            Service name (without ``.service`` suffix).

        Returns
        -------
        dict
            ``{"success": True, "data": {"name": str, "content": str,
            "sections": dict}}``
        """
        try:
            path = self._systemd_unit_path(name)
            if not path.exists():
                return self._err(f"Service '{name}' does not exist at {path}")
            content = path.read_text(encoding="utf-8")
            sections: Dict[str, List[str]] = {}
            current_section = ""
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    current_section = stripped[1:-1]
                    sections[current_section] = []
                elif current_section:
                    if stripped and not stripped.startswith("#"):
                        sections[current_section].append(stripped)
            return self._ok({"name": name, "content": content, "sections": sections})
        except Exception as exc:
            return self._err(f"Failed to read systemd service '{name}': {exc}")

    def enable_systemd_service(self, name: str) -> Dict[str, Any]:
        """Enable a systemd service by symlinking into multi-user.target.wants.

        Parameters
        ----------
        name : str
            Service name.

        Returns
        -------
        dict
            Success/failure envelope.
        """
        try:
            unit_path = self._systemd_unit_path(name)
            if not unit_path.exists():
                return self._err(f"Service '{name}' does not exist")
            self._systemd_wants.mkdir(parents=True, exist_ok=True)
            link = self._systemd_wants / f"{name}.service"
            if link.exists():
                link.unlink()
            link.symlink_to(unit_path)
            return self._ok({"name": name, "link": str(link)})
        except Exception as exc:
            return self._err(f"Failed to enable systemd service '{name}': {exc}")

    def disable_systemd_service(self, name: str) -> Dict[str, Any]:
        """Disable a systemd service by removing its symlink from wants/.

        Parameters
        ----------
        name : str
            Service name.

        Returns
        -------
        dict
            Success/failure envelope.
        """
        try:
            link = self._systemd_wants / f"{name}.service"
            if link.exists():
                link.unlink()
            return self._ok({"name": name, "disabled": True})
        except Exception as exc:
            return self._err(f"Failed to disable systemd service '{name}': {exc}")

    # ------------------------------------------------------------------
    # 5. systemd timers
    # ------------------------------------------------------------------

    def create_systemd_timer(
        self, name: str, timer_config: Dict[str, str]
    ) -> Dict[str, Any]:
        """Create a systemd timer unit file.

        Parameters
        ----------
        name : str
            Timer name (without ``.timer`` suffix).
        timer_config : dict
            Section content mapping.  Recognised keys: ``"Unit"``,
            ``"Timer"``, ``"Install"``.

        Returns
        -------
        dict
            Success/failure envelope.
        """
        try:
            path = self._systemd_system / f"{name}.timer"
            path.parent.mkdir(parents=True, exist_ok=True)
            lines: List[str] = []
            for section in ("Unit", "Timer", "Install"):
                content = timer_config.get(section, "")
                if content:
                    lines.append(f"[{section}]")
                    lines.extend(content.strip().splitlines())
                    lines.append("")
            path.write_text("\n".join(lines), encoding="utf-8")
            return self._ok({"name": name, "path": str(path)})
        except Exception as exc:
            return self._err(f"Failed to create systemd timer '{name}': {exc}")

    def list_systemd_timers(self) -> Dict[str, Any]:
        """List all .timer files in the system systemd directory.

        Returns
        -------
        dict
            ``{"success": True, "data": [{"name": str, "path": str,
            "size": int}, ...]}``
        """
        try:
            timers: List[Dict[str, Any]] = []
            if self._systemd_system.exists():
                for p in sorted(self._systemd_system.iterdir()):
                    if p.is_file() and p.suffix == ".timer":
                        st = p.stat()
                        timers.append(
                            {"name": p.stem, "path": str(p), "size": st.st_size}
                        )
            return self._ok(timers)
        except Exception as exc:
            return self._err(f"Failed to list systemd timers: {exc}")

    # ------------------------------------------------------------------
    # 6. systemd mounts
    # ------------------------------------------------------------------

    def create_systemd_mount(
        self, name: str, mount_config: Dict[str, str]
    ) -> Dict[str, Any]:
        """Create a systemd mount unit file.

        Parameters
        ----------
        name : str
            Mount name (without ``.mount`` suffix).
        mount_config : dict
            Section content mapping.  Recognised keys: ``"Unit"``,
            ``"Mount"``, ``"Install"``.

        Returns
        -------
        dict
            Success/failure envelope.
        """
        try:
            path = self._systemd_system / f"{name}.mount"
            path.parent.mkdir(parents=True, exist_ok=True)
            lines: List[str] = []
            for section in ("Unit", "Mount", "Install"):
                content = mount_config.get(section, "")
                if content:
                    lines.append(f"[{section}]")
                    lines.extend(content.strip().splitlines())
                    lines.append("")
            path.write_text("\n".join(lines), encoding="utf-8")
            return self._ok({"name": name, "path": str(path)})
        except Exception as exc:
            return self._err(f"Failed to create systemd mount '{name}': {exc}")

    # ------------------------------------------------------------------
    # 7. systemd sockets
    # ------------------------------------------------------------------

    def create_systemd_socket(
        self, name: str, socket_config: Dict[str, str]
    ) -> Dict[str, Any]:
        """Create a systemd socket unit file.

        Parameters
        ----------
        name : str
            Socket name (without ``.socket`` suffix).
        socket_config : dict
            Section content mapping.  Recognised keys: ``"Unit"``,
            ``"Socket"``, ``"Install"``.

        Returns
        -------
        dict
            Success/failure envelope.
        """
        try:
            path = self._systemd_system / f"{name}.socket"
            path.parent.mkdir(parents=True, exist_ok=True)
            lines: List[str] = []
            for section in ("Unit", "Socket", "Install"):
                content = socket_config.get(section, "")
                if content:
                    lines.append(f"[{section}]")
                    lines.extend(content.strip().splitlines())
                    lines.append("")
            path.write_text("\n".join(lines), encoding="utf-8")
            return self._ok({"name": name, "path": str(path)})
        except Exception as exc:
            return self._err(f"Failed to create systemd socket '{name}': {exc}")

    # ------------------------------------------------------------------
    # 8. systemd targets
    # ------------------------------------------------------------------

    def get_systemd_target(self, name: str) -> Dict[str, Any]:
        """Read a systemd target unit file.

        Parameters
        ----------
        name : str
            Target name (without ``.target`` suffix).

        Returns
        -------
        dict
            ``{"success": True, "data": {"name": str, "content": str,
            "sections": dict}}``
        """
        try:
            path = self._systemd_system / f"{name}.target"
            if not path.exists():
                return self._err(f"Target '{name}' does not exist at {path}")
            content = path.read_text(encoding="utf-8")
            sections: Dict[str, List[str]] = {}
            current_section = ""
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    current_section = stripped[1:-1]
                    sections[current_section] = []
                elif current_section:
                    if stripped and not stripped.startswith("#"):
                        sections[current_section].append(stripped)
            return self._ok({"name": name, "content": content, "sections": sections})
        except Exception as exc:
            return self._err(f"Failed to read systemd target '{name}': {exc}")

    def set_default_target(self, target: str) -> Dict[str, Any]:
        """Set the default systemd boot target.

        Creates /etc/systemd/system/default.target as a symlink to the
        requested target unit.

        Parameters
        ----------
        target : str
            Target name (e.g. ``"multi-user"`` or ``"graphical"``).

        Returns
        -------
        dict
            Success/failure envelope.
        """
        try:
            target_path = self._systemd_system / f"{target}.target"
            if not target_path.exists():
                return self._err(f"Target unit '{target}.target' does not exist")
            default = self._systemd_system / "default.target"
            if default.exists() or default.is_symlink():
                default.unlink()
            default.symlink_to(target_path)
            return self._ok({"default_target": target, "link": str(default)})
        except Exception as exc:
            return self._err(f"Failed to set default target to '{target}': {exc}")

    def list_systemd_targets(self) -> Dict[str, Any]:
        """List all .target files in the system systemd directory.

        Returns
        -------
        dict
            ``{"success": True, "data": [{"name": str, "path": str,
            "size": int}, ...]}``
        """
        try:
            targets: List[Dict[str, Any]] = []
            if self._systemd_system.exists():
                for p in sorted(self._systemd_system.iterdir()):
                    if p.is_file() and p.suffix == ".target":
                        st = p.stat()
                        targets.append(
                            {"name": p.stem, "path": str(p), "size": st.st_size}
                        )
            return self._ok(targets)
        except Exception as exc:
            return self._err(f"Failed to list systemd targets: {exc}")

    # ------------------------------------------------------------------
    # 9. SysV init script with LSB header
    # ------------------------------------------------------------------

    def add_sysvinit_script(
        self,
        name: str,
        header: str,
        start_cmd: str,
        stop_cmd: str,
    ) -> Dict[str, Any]:
        """Create a full SysV init script with LSB header.

        Parameters
        ----------
        name : str
            Script filename.
        header : str
            Brief description for the LSB header ``Short-Description``.
        start_cmd : str
            Shell command(s) to start the service.
        stop_cmd : str
            Shell command(s) to stop the service.

        Returns
        -------
        dict
            Success/failure envelope.
        """
        try:
            lsb = LSB_HEADER_TEMPLATE.format(
                name=header,
                default_start="2 3 4 5",
                default_stop="0 1 6",
            )
            script = (
                "#!/bin/sh\n"
                f"{lsb}\n"
                f'case "$1" in\n'
                f"  start)\n"
                f"    {start_cmd}\n"
                f"    ;;\n"
                f"  stop)\n"
                f"    {stop_cmd}\n"
                f"    ;;\n"
                f"  restart)\n"
                f"    $0 stop\n"
                f"    $0 start\n"
                f"    ;;\n"
                f"  status)\n"
                f'    echo "Status of {header}"\n'
                f"    ;;\n"
                f"  *)\n"
                f'    echo "Usage: $0 {{start|stop|restart|status}}"\n'
                f"    exit 1\n"
                f"    ;;\n"
                f"esac\n"
                f"exit 0\n"
            )
            return self.add_init_script(name, script)
        except Exception as exc:
            return self._err(f"Failed to create SysV init script '{name}': {exc}")

    # ------------------------------------------------------------------
    # 10. rc runlevel info
    # ------------------------------------------------------------------

    def get_rc_runlevel_info(self, runlevel: int) -> Dict[str, Any]:
        """Get counts of S (start) and K (stop) symlinks for a runlevel.

        Parameters
        ----------
        runlevel : int
            Runlevel (0-6).

        Returns
        -------
        dict
            ``{"success": True, "data": {"runlevel": int, "start_count": int,
            "stop_count": int, "scripts": [...]}}``
        """
        try:
            rc_dir = self._rc_dir(runlevel)
            start_count = 0
            stop_count = 0
            scripts: List[Dict[str, str]] = []
            if rc_dir.exists():
                for p in rc_dir.iterdir():
                    name = p.name
                    if name.startswith("S") and p.is_symlink():
                        start_count += 1
                        scripts.append({"name": name, "type": "start"})
                    elif name.startswith("K") and p.is_symlink():
                        stop_count += 1
                        scripts.append({"name": name, "type": "stop"})
            return self._ok(
                {
                    "runlevel": runlevel,
                    "start_count": start_count,
                    "stop_count": stop_count,
                    "scripts": scripts,
                }
            )
        except Exception as exc:
            return self._err(f"Failed to get rc info for runlevel {runlevel}: {exc}")

    # ------------------------------------------------------------------
    # 11. aggregate operations
    # ------------------------------------------------------------------

    def list_all(self) -> Dict[str, Any]:
        """Return an overview of the entire init system state.

        Returns
        -------
        dict
            Aggregate data from inittab, init.d scripts, systemd
            services/timers/targets, and rc directory summaries.
        """
        try:
            data: Dict[str, Any] = {
                "inittab": self.get_inittab().get("data", {}),
                "init_scripts": self.list_init_scripts().get("data", []),
                "systemd_services": self.list_systemd_services().get("data", []),
                "systemd_timers": self.list_systemd_timers().get("data", []),
                "systemd_targets": self.list_systemd_targets().get("data", []),
                "rc_runlevels": {},
            }
            for rl in range(7):
                data["rc_runlevels"][rl] = self.get_rc_runlevel_info(rl).get(
                    "data", {}
                )
            return self._ok(data)
        except Exception as exc:
            return self._err(f"Failed to list init system state: {exc}")

    def backup_all(self) -> Dict[str, Any]:
        """Backup all init system configuration to a timestamped JSON file.

        The backup is written next to the base_path under a ``backups/``
        directory.

        Returns
        -------
        dict
            ``{"success": True, "data": {"backup_path": str,
            "timestamp": str, "components_backed_up": [...]}}``
        """
        try:
            from datetime import datetime, timezone

            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_dir = self._base / "backups" / "init_system"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_file = backup_dir / f"init_backup_{ts}.json"

            state = self.list_all().get("data", {})
            backup_payload = {
                "timestamp": ts,
                "base_path": str(self._base),
                "state": state,
            }
            backup_file.write_text(
                json.dumps(backup_payload, indent=2, default=str),
                encoding="utf-8",
            )
            return self._ok(
                {
                    "backup_path": str(backup_file),
                    "timestamp": ts,
                    "components_backed_up": [
                        "inittab",
                        "init_scripts",
                        "systemd_services",
                        "systemd_timers",
                        "systemd_targets",
                        "rc_runlevels",
                    ],
                }
            )
        except Exception as exc:
            return self._err(f"Failed to backup init system: {exc}")

    def export_status(self) -> Dict[str, Any]:
        """Export a full status dictionary of the init system.

        Includes inittab, init scripts, systemd units, rc directories,
        and a summary of enabled/disabled state.

        Returns
        -------
        dict
            ``{"success": True, "data": {...}}``
        """
        try:
            all_state = self.list_all().get("data", {})
            default_rl = all_state.get("inittab", {}).get(
                "default_runlevel", DEFAULT_RUNLEVEL
            )
            enabled = self.list_enabled_scripts(default_rl).get("data", [])
            systemd_svc = all_state.get("systemd_services", [])
            systemd_tim = all_state.get("systemd_timers", [])
            systemd_tgt = all_state.get("systemd_targets", [])

            summary = {
                "base_path": str(self._base),
                "default_runlevel": default_rl,
                "inittab": all_state.get("inittab", {}),
                "init_scripts_count": len(all_state.get("init_scripts", [])),
                "enabled_scripts_runlevel": default_rl,
                "enabled_scripts_count": len(enabled),
                "systemd_services_count": len(systemd_svc),
                "systemd_timers_count": len(systemd_tim),
                "systemd_targets_count": len(systemd_tgt),
                "rc_runlevels": {
                    str(rl): {
                        "start": v.get("start_count", 0),
                        "stop": v.get("stop_count", 0),
                    }
                    for rl, v in all_state.get("rc_runlevels", {}).items()
                },
            }
            return self._ok(summary)
        except Exception as exc:
            return self._err(f"Failed to export init system status: {exc}")


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

def get_manager(base_path: str = "/") -> InitSystemManager:
    """Factory function to obtain an InitSystemManager instance."""
    return InitSystemManager(base_path=base_path)


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "/tmp/umeros_init_test"
    mgr = InitSystemManager(base_path=target)
    status = mgr.export_status()
    print(json.dumps(status, indent=2))
