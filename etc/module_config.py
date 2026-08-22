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

#!/usr/bin/env python3
"""
UmerOS Kernel Module Configuration Manager
==========================================

Manages kernel module configurations across multiple locations:
- /etc/modprobe.d/*        (module options, blacklist, aliases)
- /etc/modules-load.d/*    (modules to load at boot)
- /etc/modules             (legacy modules to load)
- /etc/modprobe.conf       (legacy modprobe configuration)
- /proc/modules            (currently loaded modules)

Provides tools for listing, adding, removing, and validating
kernel module configurations with common presets and safety checks.
"""

import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union


# ============================================================================
# Path Constants
# ============================================================================

# Directory containing modprobe configuration snippets
MODPROBE_D: Path = Path("/etc/modprobe.d")

# Directory for modules to load at boot (systemd-style)
MODULES_LOAD_D: Path = Path("/etc/modules-load.d")

# Legacy file listing modules to load at boot
MODULES_FILE: Path = Path("/etc/modules")

# Legacy modprobe configuration file
MODPROBE_CONF: Path = Path("/etc/modprobe.conf")

# Virtual file showing currently loaded modules
PROC_MODULES: Path = Path("/proc/modules")


# ============================================================================
# Common Module Presets
# ============================================================================

COMMON_MODULES: List[str] = [
    # Filesystem modules
    "ext4", "btrfs", "xfs", "vfat", "ntfs3", "fuse",
    # Network modules
    "e1000e", "igb", "r8169", "tg3", "bnx2x",
    # USB modules
    "usb_storage", "usbhid", "ehci_hcd", "xhci_hcd",
    # Storage modules
    "ahci", "libata", "sd_mod", "sr_mod",
    # Input modules
    "evdev", "joydev", "mousedev",
    # Sound modules
    "snd_hda_intel", "snd_usb_audio", "snd_pcm", "snd_timer",
    # GPU modules
    "nvidia", "nvidia_drm", "nvidia_modeset", "nouveau", "amdgpu", "i915",
    # Virtualization
    "kvm", "kvm_intel", "kvm_amd", "vhost_net",
    # Security modules
    "apparmor", "lockdown",
]

COMMON_MODULE_OPTIONS: Dict[str, Dict[str, str]] = {
    # NVIDIA options
    "nvidia": {
        "NVreg_PreserveVideoMemoryAllocations": "1",
        "NVreg_TempFilePath": "/tmp/nvidia",
    },
    "nvidia_drm": {
        "modeset": "1",
    },
    # Sound options
    "snd_hda_intel": {
        "power_save": "1",
        "power_save_controller": "Y",
    },
    # Network options
    "r8169": {
        "AspmL1": "1",
    },
    # USB autosuspend
    "usb_storage": {
        "autosuspend": "1",
    },
    # Power management
    "i915": {
        "enable_dc": "4",
        "enable_fbc": "1",
    },
    "amdgpu": {
        "powergate_display": "1",
        "ppfeaturemask": "0xffffffff",
    },
}


# ============================================================================
# ModuleConfigManager Class
# ============================================================================

class ModuleConfigManager:
    """
    Comprehensive manager for kernel module configurations.

    Handles reading, writing, and validating module configurations
    across all standard configuration locations.
    """

    def __init__(
        self,
        modprobe_d: Optional[Path] = None,
        modules_load_d: Optional[Path] = None,
        modules_file: Optional[Path] = None,
        modprobe_conf: Optional[Path] = None,
        proc_modules: Optional[Path] = None,
        dry_run: bool = False,
    ) -> None:
        """
        Initialize the ModuleConfigManager.

        Args:
            modprobe_d: Path to modprobe.d directory (default: /etc/modprobe.d)
            modules_load_d: Path to modules-load.d directory (default: /etc/modules-load.d)
            modules_file: Path to legacy modules file (default: /etc/modules)
            modprobe_conf: Path to legacy modprobe.conf (default: /etc/modprobe.conf)
            proc_modules: Path to /proc/modules (default: /proc/modules)
            dry_run: If True, don't write any files
        """
        self.modprobe_d = modprobe_d or MODPROBE_D
        self.modules_load_d = modules_load_d or MODULES_LOAD_D
        self.modules_file = modules_file or MODULES_FILE
        self.modprobe_conf = modprobe_conf or MODPROBE_CONF
        self.proc_modules = proc_modules or PROC_MODULES
        self.dry_run = dry_run
        self._backup_dir: Optional[Path] = None

    # ------------------------------------------------------------------
    # Loaded Modules
    # ------------------------------------------------------------------

    def list_loaded_modules(self) -> List[Dict[str, Any]]:
        """
        List currently loaded modules from /proc/modules.

        Returns:
            List of dicts with keys: name, size, used_by (list), state
        """
        modules: List[Dict[str, Any]] = []

        if not self.proc_modules.exists():
            raise FileNotFoundError(
                f"Cannot read {self.proc_modules} - are you on_____?"
            )

        with open(self.proc_modules, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                parts = line.split()
                if len(parts) < 3:
                    continue

                name = parts[0]
                size = int(parts[1])
                used_by_count = int(parts[2])
                if used_by_count == 0:
                    used_by = []
                else:
                    used_by = [u.rstrip(",") for u in parts[3:3 + used_by_count]]
                state = parts[3 + used_by_count] if len(parts) > 3 + used_by_count else "live"

                modules.append({
                    "name": name,
                    "size": size,
                    "used_by": used_by,
                    "state": state,
                })

        return modules

    def get_loaded_module_names(self) -> Set[str]:
        """Return set of currently loaded module names."""
        return {m["name"] for m in self.list_loaded_modules()}

    # ------------------------------------------------------------------
    # Configured Modules (modules-load.d)
    # ------------------------------------------------------------------

    def list_configured_modules(self) -> List[Dict[str, str]]:
        """
        List modules configured to load at boot from modules-load.d.

        Returns:
            List of dicts with keys: module, source_file
        """
        modules: List[Dict[str, str]] = []
        seen: Set[str] = set()

        if self.modules_load_d.exists():
            for cfg_file in sorted(self.modules_load_d.glob("*.conf")):
                try:
                    with open(cfg_file, "r") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#"):
                                if line not in seen:
                                    modules.append({
                                        "module": line,
                                        "source_file": str(cfg_file),
                                    })
                                    seen.add(line)
                except (PermissionError, OSError) as e:
                    print(f"Warning: Cannot read {cfg_file}: {e}")

        # Check legacy modules file
        if self.modules_file.exists():
            try:
                with open(self.modules_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            if line not in seen:
                                modules.append({
                                    "module": line,
                                    "source_file": str(self.modules_file),
                                })
                                seen.add(line)
            except (PermissionError, OSError) as e:
                print(f"Warning: Cannot read {self.modules_file}: {e}")

        return modules

    def get_configured_module_names(self) -> Set[str]:
        """Return set of module names configured to load at boot."""
        return {m["module"] for m in self.list_configured_modules()}

    # ------------------------------------------------------------------
    # Add/Remove Modules
    # ------------------------------------------------------------------

    def add_module(
        self,
        module_name: str,
        target: str = "boot",
        options: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Add a module configuration.

        Args:
            module_name: Name of the kernel module
            target: Where to add - "boot" (modules-load.d), "blacklist",
                   "options", or specific modprobe.d filename
            options: Optional dict of module options (e.g., {"opt": "val"})

        Returns:
            True if successfully added, False otherwise
        """
        if not self.validate_module(module_name):
            print(f"Invalid module name: {module_name}")
            return False

        if target == "boot":
            return self._add_to_modules_load_d(module_name)
        elif target == "blacklist":
            return self.add_blacklist(module_name)
        elif target == "options" and options:
            return self.add_options(module_name, options)
        else:
            # Treat target as a modprobe.d filename
            entries = [module_name]
            if options:
                for key, val in options.items():
                    entries.append(f"options {module_name} {key}={val}")
            return self.set_modprobe_d_config(target, entries)

    def remove_module(
        self,
        module_name: str,
        target: str = "boot",
    ) -> bool:
        """
        Remove a module from configuration.

        Args:
            module_name: Name of the kernel module
            target: Where to remove from - "boot", "blacklist", "options",
                   or specific modprobe.d filename

        Returns:
            True if successfully removed, False otherwise
        """
        if target == "boot":
            return self._remove_from_modules_load_d(module_name)
        elif target == "blacklist":
            return self.remove_modprobe_d_entry(
                self.modprobe_d / "blacklist.conf",
                f"blacklist {module_name}",
            )
        elif target == "all":
            return self._remove_from_all(module_name)
        else:
            # Remove from specific modprobe.d file
            cfg_path = self.modprobe_d / target
            if cfg_path.exists():
                return self.remove_modprobe_d_entry(
                    cfg_path, module_name
                )
            return False

    def _add_to_modules_load_d(self, module_name: str) -> bool:
        """Add module to modules-load.d for boot loading."""
        self.modules_load_d.mkdir(parents=True, exist_ok=True)
        target_file = self.modules_load_d / "10-umeros.conf"

        # Read existing entries
        existing: List[str] = []
        if target_file.exists():
            with open(target_file, "r") as f:
                existing = [
                    line.strip()
                    for line in f
                    if line.strip() and not line.strip().startswith("#")
                ]

        if module_name in existing:
            print(f"Module {module_name} already configured for boot")
            return True

        if self.dry_run:
            print(f"[DRY RUN] Would add {module_name} to {target_file}")
            return True

        try:
            with open(target_file, "a") as f:
                f.write(f"{module_name}\n")
            print(f"Added {module_name} to {target_file}")
            return True
        except (PermissionError, OSError) as e:
            print(f"Error writing to {target_file}: {e}")
            return False

    def _remove_from_modules_load_d(self, module_name: str) -> bool:
        """Remove module from modules-load.d files."""
        removed = False

        for cfg_file in self.modules_load_d.glob("*.conf"):
            try:
                with open(cfg_file, "r") as f:
                    lines = f.readlines()

                new_lines = [
                    line for line in lines
                    if line.strip() != module_name
                ]

                if len(new_lines) != len(lines):
                    if self.dry_run:
                        print(
                            f"[DRY RUN] Would remove {module_name} from {cfg_file}"
                        )
                    else:
                        with open(cfg_file, "w") as f:
                            f.writelines(new_lines)
                        print(f"Removed {module_name} from {cfg_file}")
                    removed = True

            except (PermissionError, OSError) as e:
                print(f"Error processing {cfg_file}: {e}")

        return removed

    def _remove_from_all(self, module_name: str) -> bool:
        """Remove module from all configuration locations."""
        results = [
            self._remove_from_modules_load_d(module_name),
            self.remove_modprobe_d_entry(
                self.modprobe_d / "blacklist.conf",
                f"blacklist {module_name}",
            ),
            self.remove_modprobe_d_entry(
                self.modprobe_d / f"{module_name}.conf",
                module_name,
            ),
        ]
        return any(results)

    def get_module_info(self, module_name: str) -> Dict[str, Any]:
        """
        Get comprehensive information about a module.

        Returns:
            Dict with keys: name, loaded, size, configured, options,
            blacklisted, alias, sources
        """
        loaded_modules = self.list_loaded_modules()
        configured = self.get_configured_module_names()
        modprobe_info = self._get_modprobe_info(module_name)

        info: Dict[str, Any] = {
            "name": module_name,
            "loaded": False,
            "size": 0,
            "used_by": [],
            "state": "unknown",
            "configured_for_boot": module_name in configured,
            "blacklisted": False,
            "options": {},
            "alias": None,
            "sources": [],
        }

        # Check loaded status
        for mod in loaded_modules:
            if mod["name"] == module_name:
                info["loaded"] = True
                info["size"] = mod["size"]
                info["used_by"] = mod["used_by"]
                info["state"] = mod["state"]
                break

        # Merge modprobe info
        info.update(modprobe_info)

        return info

    # ------------------------------------------------------------------
    # Modprobe.d Management
    # ------------------------------------------------------------------

    def list_modprobe_d_files(self) -> List[Dict[str, Any]]:
        """
        List all files in modprobe.d directory.

        Returns:
            List of dicts with keys: name, path, entries (list), size
        """
        files: List[Dict[str, Any]] = []

        if not self.modprobe_d.exists():
            return files

        for cfg_file in sorted(self.modprobe_d.iterdir()):
            if cfg_file.is_file():
                entries = self._read_modprobe_file(cfg_file)
                files.append({
                    "name": cfg_file.name,
                    "path": str(cfg_file),
                    "entries": entries,
                    "size": cfg_file.stat().st_size,
                })

        return files

    def get_modprobe_d_config(self, filename: str) -> List[str]:
        """
        Read a modprobe.d configuration file.

        Args:
            filename: Name of the configuration file

        Returns:
            List of non-comment, non-empty lines
        """
        cfg_path = self.modprobe_d / filename
        return self._read_modprobe_file(cfg_path)

    def set_modprobe_d_config(
        self,
        filename: str,
        entries: List[str],
        backup: bool = True,
    ) -> bool:
        """
        Write entries to a modprobe.d configuration file.

        Args:
            filename: Name of the configuration file
            entries: List of configuration lines
            backup: If True, create backup before writing

        Returns:
            True if successfully written, False otherwise
        """
        cfg_path = self.modprobe_d / filename

        if backup and cfg_path.exists():
            self._backup_file(cfg_path)

        if self.dry_run:
            print(f"[DRY RUN] Would write {len(entries)} entries to {cfg_path}")
            return True

        try:
            self.modprobe_d.mkdir(parents=True, exist_ok=True)

            with open(cfg_path, "w") as f:
                f.write(f"# UmerOS Module Configuration - {filename}\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
                for entry in entries:
                    f.write(f"{entry}\n")

            print(f"Written {len(entries)} entries to {cfg_path}")
            return True

        except (PermissionError, OSError) as e:
            print(f"Error writing to {cfg_path}: {e}")
            return False

    def add_modprobe_d_entry(
        self,
        filename: str,
        entry: str,
        position: str = "end",
    ) -> bool:
        """
        Add a single entry to a modprobe.d file.

        Args:
            filename: Target file
            entry: Line to add
            position: "end" or "begin"

        Returns:
            True if entry was added, False otherwise
        """
        cfg_path = self.modprobe_d / filename
        existing = self._read_modprobe_file(cfg_path)

        if entry in existing:
            print(f"Entry already exists: {entry}")
            return True

        self._backup_file(cfg_path) if cfg_path.exists() else None

        if self.dry_run:
            print(f"[DRY RUN] Would add '{entry}' to {cfg_path}")
            return True

        try:
            self.modprobe_d.mkdir(parents=True, exist_ok=True)

            if position == "begin":
                new_content = f"{entry}\n"
                if cfg_path.exists():
                    with open(cfg_path, "r") as f:
                        new_content += f.read()
                with open(cfg_path, "w") as f:
                    f.write(new_content)
            else:
                with open(cfg_path, "a") as f:
                    f.write(f"{entry}\n")

            print(f"Added '{entry}' to {cfg_path}")
            return True

        except (PermissionError, OSError) as e:
            print(f"Error writing to {cfg_path}: {e}")
            return False

    def add_blacklist(
        self,
        module_name: str,
        comment: Optional[str] = None,
    ) -> bool:
        """
        Blacklist a module to prevent automatic loading.

        Args:
            module_name: Module to blacklist
            comment: Optional comment explaining why

        Returns:
            True if successfully blacklisted, False otherwise
        """
        blacklist_file = self.modprobe_d / "blacklist.conf"
        existing = self._read_modprobe_file(blacklist_file)

        blacklist_entry = f"blacklist {module_name}"

        if blacklist_entry in existing:
            print(f"Module {module_name} is already blacklisted")
            return True

        entries: List[str] = []
        if comment:
            entries.append(f"# {comment}")
        entries.append(blacklist_entry)

        # Also add install line to prevent manual loading
        install_entry = f"install {module_name} /bin/true"
        if install_entry not in existing:
            entries.append(install_entry)

        for entry in entries:
            self.add_modprobe_d_entry("blacklist.conf", entry)

        return True

    def add_alias(
        self,
        alias_name: str,
        module_name: str,
    ) -> bool:
        """
        Add a module alias.

        Args:
            alias_name: The alias name
            module_name: The actual module name

        Returns:
            True if successfully added, False otherwise
        """
        entry = f"alias {alias_name} {module_name}"

        # Check if alias already exists with different module
        existing = self.get_modprobe_d_config("aliases.conf")
        for line in existing:
            if line.startswith(f"alias {alias_name}"):
                if line == entry:
                    print(f"Alias already exists: {entry}")
                    return True
                else:
                    print(
                        f"Warning: Alias {alias_name} already maps to "
                        f"{line.split()[-1]}"
                    )

        return self.add_modprobe_d_entry("aliases.conf", entry)

    def add_options(
        self,
        module_name: str,
        options: Dict[str, str],
    ) -> bool:
        """
        Add options for a module.

        Args:
            module_name: Module name
            options: Dict of option_name -> value

        Returns:
            True if successfully added, False otherwise
        """
        options_parts = [f"{k}={v}" for k, v in options.items()]
        entry = f"options {module_name} {' '.join(options_parts)}"

        return self.add_modprobe_d_entry(
            f"{module_name}-options.conf",
            entry,
        )

    def remove_modprobe_d_entry(
        self,
        file_path: Union[str, Path],
        pattern: str,
    ) -> bool:
        """
        Remove entries matching pattern from a modprobe.d file.

        Args:
            file_path: Path to configuration file
            pattern: String pattern to match for removal

        Returns:
            True if entries were removed, False otherwise
        """
        file_path = Path(file_path)

        if not file_path.exists():
            return False

        try:
            with open(file_path, "r") as f:
                lines = f.readlines()

            new_lines = [
                line for line in lines
                if line.strip() != pattern
            ]

            if len(new_lines) == len(lines):
                print(f"Pattern not found: {pattern}")
                return False

            if self.dry_run:
                print(f"[DRY RUN] Would remove '{pattern}' from {file_path}")
                return True

            self._backup_file(file_path)

            with open(file_path, "w") as f:
                f.writelines(new_lines)

            print(f"Removed '{pattern}' from {file_path}")
            return True

        except (PermissionError, OSError) as e:
            print(f"Error processing {file_path}: {e}")
            return False

    # ------------------------------------------------------------------
    # Legacy Configuration
    # ------------------------------------------------------------------

    def set_modprobe_conf(
        self,
        entries: List[str],
        backup: bool = True,
    ) -> bool:
        """
        Write to legacy /etc/modprobe.conf.

        Args:
            entries: List of configuration lines
            backup: If True, create backup before writing

        Returns:
            True if successfully written, False otherwise
        """
        if backup and self.modprobe_conf.exists():
            self._backup_file(self.modprobe_conf)

        if self.dry_run:
            print(
                f"[DRY RUN] Would write {len(entries)} entries to "
                f"{self.modprobe_conf}"
            )
            return True

        try:
            with open(self.modprobe_conf, "w") as f:
                f.write("# UmerOS Legacy Modprobe Configuration\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
                for entry in entries:
                    f.write(f"{entry}\n")

            print(f"Written {len(entries)} entries to {self.modprobe_conf}")
            return True

        except (PermissionError, OSError) as e:
            print(f"Error writing to {self.modprobe_conf}: {e}")
            return False

    def get_modprobe_conf(self) -> List[str]:
        """
        Read legacy /etc/modprobe.conf.

        Returns:
            List of non-comment, non-empty lines
        """
        return self._read_modprobe_file(self.modprobe_conf)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_module(self, module_name: str) -> bool:
        """
        Validate a module name.

        Checks:
        - Not empty
        - Only contains valid characters (alphanumeric, underscore, hyphen)
        - Not too long

        Returns:
            True if valid, False otherwise
        """
        if not module_name:
            return False

        if len(module_name) > 56:
            return False

        if not re.match(r"^[a-zA-Z0-9_-]+$", module_name):
            return False

        return True

    def check_module_exists(self, module_name: str) -> bool:
        """
        Check if a module exists on the system.

        Returns:
            True if module exists, False otherwise
        """
        try:
            result = subprocess.run(
                ["modinfo", module_name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def get_module_presets(self) -> Dict[str, Dict[str, Any]]:
        """
        Get preset configurations for common module types.

        Returns:
            Dict of preset_name -> config dict
        """
        return {
            "nvidia": {
                "description": "NVIDIA GPU driver configuration",
                "modules": ["nvidia", "nvidia_drm", "nvidia_modeset", "nvidia_uvm"],
                "options": COMMON_MODULE_OPTIONS.get("nvidia", {}),
                "blacklist": ["nouveau"],
            },
            "amd_gpu": {
                "description": "AMD GPU driver configuration",
                "modules": ["amdgpu", "radeon"],
                "options": COMMON_MODULE_OPTIONS.get("amdgpu", {}),
                "blacklist": [],
            },
            "intel_gpu": {
                "description": "Intel GPU driver configuration",
                "modules": ["i915"],
                "options": COMMON_MODULE_OPTIONS.get("i915", {}),
                "blacklist": [],
            },
            "virtualbox": {
                "description": "VirtualBox guest modules",
                "modules": ["vboxguest", "vboxsf", "vboxvideo"],
                "options": {},
                "blacklist": [],
            },
            "vmware": {
                "description": "VMware guest modules",
                "modules": ["vmw_balloon", "vmw_vmci", "vmwgfx"],
                "options": {},
                "blacklist": [],
            },
            "docker": {
                "description": "Modules needed for Docker",
                "modules": ["overlay", "br_netfilter", "ip_tables", "veth"],
                "options": {
                    "br_netfilter": {"nf_call_netfilter": "1"},
                },
                "blacklist": [],
            },
            "audio": {
                "description": "Common audio modules",
                "modules": ["snd_hda_intel", "snd_usb_audio", "snd_pcm", "snd_timer"],
                "options": COMMON_MODULE_OPTIONS.get("snd_hda_intel", {}),
                "blacklist": [],
            },
            "usb": {
                "description": "USB support modules",
                "modules": ["usb_storage", "usbhid", "ehci_hcd", "xhci_hcd"],
                "options": {},
                "blacklist": [],
            },
        }

    # ------------------------------------------------------------------
    # Import/Export
    # ------------------------------------------------------------------

    def export_status(self, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Export complete module status.

        Args:
            output_path: Optional path to write JSON output

        Returns:
            Dict with complete module status
        """
        status = {
            "timestamp": datetime.now().isoformat(),
            "loaded_modules": self.list_loaded_modules(),
            "configured_modules": self.list_configured_modules(),
            "modprobe_d_files": self.list_modprobe_d_files(),
            "legacy_modprobe_conf": self.get_modprobe_conf(),
        }

        if output_path:
            import json
            try:
                with open(output_path, "w") as f:
                    json.dump(status, f, indent=2, default=str)
                print(f"Status exported to {output_path}")
            except (PermissionError, OSError) as e:
                print(f"Error exporting status: {e}")

        return status

    # ------------------------------------------------------------------
    # Backup
    # ------------------------------------------------------------------

    def backup_all(self, backup_dir: Optional[Path] = None) -> Path:
        """
        Create backup of all module configurations.

        Args:
            backup_dir: Directory to store backup (auto-generated if None)

        Returns:
            Path to backup directory
        """
        if backup_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = Path(tempfile.gettempdir()) / f"umeros_modules_backup_{timestamp}"

        backup_dir.mkdir(parents=True, exist_ok=True)
        self._backup_dir = backup_dir

        backed_up = 0

        # Backup modprobe.d
        if self.modprobe_d.exists():
            modprobe_backup = backup_dir / "modprobe.d"
            modprobe_backup.mkdir(exist_ok=True)
            for cfg_file in self.modprobe_d.glob("*"):
                if cfg_file.is_file():
                    try:
                        shutil.copy2(cfg_file, modprobe_backup / cfg_file.name)
                        backed_up += 1
                    except (PermissionError, OSError) as e:
                        print(f"Warning: Could not backup {cfg_file}: {e}")

        # Backup modules-load.d
        if self.modules_load_d.exists():
            modules_backup = backup_dir / "modules-load.d"
            modules_backup.mkdir(exist_ok=True)
            for cfg_file in self.modules_load_d.glob("*"):
                if cfg_file.is_file():
                    try:
                        shutil.copy2(cfg_file, modules_backup / cfg_file.name)
                        backed_up += 1
                    except (PermissionError, OSError) as e:
                        print(f"Warning: Could not backup {cfg_file}: {e}")

        # Backup legacy files
        for legacy_file in [self.modules_file, self.modprobe_conf]:
            if legacy_file.exists():
                try:
                    shutil.copy2(legacy_file, backup_dir / legacy_file.name)
                    backed_up += 1
                except (PermissionError, OSError) as e:
                    print(f"Warning: Could not backup {legacy_file}: {e}")

        print(f"Backed up {backed_up} files to {backup_dir}")
        return backup_dir

    def restore_backup(self, backup_dir: Path) -> bool:
        """
        Restore module configurations from backup.

        Args:
            backup_dir: Path to backup directory

        Returns:
            True if restore was successful, False otherwise
        """
        if not backup_dir.exists():
            print(f"Backup directory not found: {backup_dir}")
            return False

        restored = 0

        # Restore modprobe.d
        modprobe_backup = backup_dir / "modprobe.d"
        if modprobe_backup.exists():
            for cfg_file in modprobe_backup.glob("*"):
                if cfg_file.is_file():
                    target = self.modprobe_d / cfg_file.name
                    try:
                        self.modprobe_d.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(cfg_file, target)
                        restored += 1
                    except (PermissionError, OSError) as e:
                        print(f"Warning: Could not restore {cfg_file}: {e}")

        # Restore modules-load.d
        modules_backup = backup_dir / "modules-load.d"
        if modules_backup.exists():
            for cfg_file in modules_backup.glob("*"):
                if cfg_file.is_file():
                    target = self.modules_load_d / cfg_file.name
                    try:
                        self.modules_load_d.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(cfg_file, target)
                        restored += 1
                    except (PermissionError, OSError) as e:
                        print(f"Warning: Could not restore {cfg_file}: {e}")

        # Restore legacy files
        for legacy_file in [self.modules_file, self.modprobe_conf]:
            backup_file = backup_dir / legacy_file.name
            if backup_file.exists():
                try:
                    shutil.copy2(backup_file, legacy_file)
                    restored += 1
                except (PermissionError, OSError) as e:
                    print(f"Warning: Could not restore {legacy_file}: {e}")

        print(f"Restored {restored} files from {backup_dir}")
        return restored > 0

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _read_modprobe_file(self, file_path: Path) -> List[str]:
        """
        Read a modprobe configuration file.

        Returns:
            List of non-comment, non-empty lines
        """
        entries: List[str] = []

        if not file_path.exists():
            return entries

        try:
            with open(file_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        entries.append(line)
        except (PermissionError, OSError):
            pass

        return entries

    def _get_modprobe_info(self, module_name: str) -> Dict[str, Any]:
        """
        Get module info from modprobe.d configurations.

        Returns:
            Dict with keys: options, blacklisted, alias, sources
        """
        info: Dict[str, Any] = {
            "options": {},
            "blacklisted": False,
            "alias": None,
            "sources": [],
        }

        if not self.modprobe_d.exists():
            return info

        for cfg_file in self.modprobe_d.glob("*"):
            if not cfg_file.is_file():
                continue

            try:
                with open(cfg_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue

                        parts = line.split()
                        if len(parts) < 2:
                            continue

                        directive = parts[0]

                        if directive == "blacklist" and parts[1] == module_name:
                            info["blacklisted"] = True
                            info["sources"].append(str(cfg_file))

                        elif directive == "options" and parts[1] == module_name:
                            for opt in parts[2:]:
                                if "=" in opt:
                                    key, val = opt.split("=", 1)
                                    info["options"][key] = val
                            info["sources"].append(str(cfg_file))

                        elif directive == "alias" and parts[1] == module_name:
                            info["alias"] = parts[2] if len(parts) > 2 else None
                            info["sources"].append(str(cfg_file))

            except (PermissionError, OSError):
                continue

        return info

    def _backup_file(self, file_path: Path) -> Optional[Path]:
        """
        Create a backup of a single file.

        Returns:
            Path to backup file, or None if backup failed
        """
        if not file_path.exists():
            return None

        backup_dir = self._backup_dir or Path(tempfile.gettempdir())
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.name}.{timestamp}.bak"
        backup_path = backup_dir / backup_name

        try:
            shutil.copy2(file_path, backup_path)
            return backup_path
        except (PermissionError, OSError) as e:
            print(f"Warning: Could not backup {file_path}: {e}")
            return None

    def _apply_preset(self, preset_name: str) -> bool:
        """
        Apply a module preset configuration.

        Returns:
            True if successfully applied, False otherwise
        """
        presets = self.get_module_presets()

        if preset_name not in presets:
            print(f"Unknown preset: {preset_name}")
            print(f"Available presets: {', '.join(presets.keys())}")
            return False

        preset = presets[preset_name]
        success = True

        # Add modules to boot
        for module in preset.get("modules", []):
            if not self._add_to_modules_load_d(module):
                success = False

        # Apply options
        for module, options in preset.get("options", {}).items():
            if not self.add_options(module, options):
                success = False

        # Blacklist conflicting modules
        for module in preset.get("blacklist", []):
            if not self.add_blacklist(module):
                success = False

        return success


# ============================================================================
# Helper Functions
# ============================================================================

def quick_status() -> None:
    """Print quick module status summary."""
    manager = ModuleConfigManager()

    print("=" * 60)
    print("UmerOS Module Status")
    print("=" * 60)

    # Loaded modules count
    try:
        loaded = manager.list_loaded_modules()
        print(f"\nLoaded modules: {len(loaded)}")
    except FileNotFoundError:
        print("\nLoaded modules: Unable to read /proc/modules")

    # Configured for boot
    configured = manager.list_configured_modules()
    print(f"Configured for boot: {len(configured)}")

    # Modprobe.d files
    modprobe_files = manager.list_modprobe_d_files()
    print(f"Modprobe.d files: {len(modprobe_files)}")

    # Blacklisted count
    blacklisted = 0
    for mf in modprobe_files:
        for entry in mf["entries"]:
            if entry.startswith("blacklist "):
                blacklisted += 1
    print(f"Blacklisted modules: {blacklisted}")


def apply_common_config(
    include_nvidia: bool = False,
    include_amd: bool = False,
    include_intel: bool = False,
    include_docker: bool = False,
) -> None:
    """
    Apply common module configurations.

    Args:
        include_nvidia: Include NVIDIA GPU configuration
        include_amd: Include AMD GPU configuration
        include_intel: Include Intel GPU configuration
        include_docker: Include Docker-required modules
    """
    manager = ModuleConfigManager()

    print("Applying common UmerOS module configuration...")

    # Always apply audio and USB
    manager._apply_preset("audio")
    manager._apply_preset("usb")

    if include_nvidia:
        manager._apply_preset("nvidia")
        print("Applied NVIDIA preset")

    if include_amd:
        manager._apply_preset("amd_gpu")
        print("Applied AMD GPU preset")

    if include_intel:
        manager._apply_preset("intel_gpu")
        print("Applied Intel GPU preset")

    if include_docker:
        manager._apply_preset("docker")
        print("Applied Docker preset")

    print("\nConfiguration complete!")
    print("Note: Changes require reboot to take effect for boot modules.")


# ============================================================================
# CLI Entry Point
# ============================================================================

def main() -> None:
    """Command-line interface for module configuration management."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="UmerOS Kernel Module Configuration Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  loaded                 List currently loaded modules
  configured             List modules configured for boot
  info <module>          Get detailed module information
  add <module> [target]  Add module (target: boot/blacklist/options)
  remove <module>        Remove module from configuration
  blacklist <module>     Blacklist a module
  list-files             List modprobe.d files
  status                 Show quick status summary
  backup [dir]           Backup all configurations
  validate <module>      Validate module name
  presets                List available presets
  preset <name>          Apply a preset configuration
  export [file]          Export complete status
        """,
    )

    parser.add_argument(
        "command",
        choices=[
            "loaded", "configured", "info", "add", "remove",
            "blacklist", "list-files", "status", "backup",
            "validate", "presets", "preset", "export",
        ],
        help="Command to execute",
    )
    parser.add_argument("args", nargs="*", help="Command arguments")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()
    manager = ModuleConfigManager(dry_run=args.dry_run)

    try:
        if args.command == "loaded":
            modules = manager.list_loaded_modules()
            print(f"{'Name':<30} {'Size':<12} {'State':<10} {'Used By'}")
            print("-" * 80)
            for mod in modules:
                used = ", ".join(mod["used_by"][:3]) if mod["used_by"] else "-"
                print(
                    f"{mod['name']:<30} {mod['size']:<12,} "
                    f"{mod['state']:<10} {used}"
                )

        elif args.command == "configured":
            modules = manager.list_configured_modules()
            print(f"{'Module':<30} {'Source File'}")
            print("-" * 60)
            for mod in modules:
                print(f"{mod['module']:<30} {mod['source_file']}")

        elif args.command == "info":
            if not args.args:
                print("Error: Module name required")
                sys.exit(1)
            info = manager.get_module_info(args.args[0])
            print(f"Module: {info['name']}")
            print(f"  Loaded: {info['loaded']}")
            if info["loaded"]:
                print(f"  Size: {info['size']:,} bytes")
                print(f"  State: {info['state']}")
                print(f"  Used by: {', '.join(info['used_by']) or 'none'}")
            print(f"  Configured for boot: {info['configured_for_boot']}")
            print(f"  Blacklisted: {info['blacklisted']}")
            if info["options"]:
                print(f"  Options: {info['options']}")
            if info["alias"]:
                print(f"  Alias for: {info['alias']}")

        elif args.command == "add":
            if not args.args:
                print("Error: Module name required")
                sys.exit(1)
            target = args.args[1] if len(args.args) > 1 else "boot"
            success = manager.add_module(args.args[0], target)
            sys.exit(0 if success else 1)

        elif args.command == "remove":
            if not args.args:
                print("Error: Module name required")
                sys.exit(1)
            success = manager.remove_module(args.args[0])
            sys.exit(0 if success else 1)

        elif args.command == "blacklist":
            if not args.args:
                print("Error: Module name required")
                sys.exit(1)
            success = manager.add_blacklist(args.args[0])
            sys.exit(0 if success else 1)

        elif args.command == "list-files":
            files = manager.list_modprobe_d_files()
            print(f"{'File':<30} {'Size':<10} {'Entries'}")
            print("-" * 50)
            for f in files:
                print(f"{f['name']:<30} {f['size']:<10,} {len(f['entries'])}")

        elif args.command == "status":
            quick_status()

        elif args.command == "backup":
            backup_dir = Path(args.args[0]) if args.args else None
            manager.backup_all(backup_dir)

        elif args.command == "validate":
            if not args.args:
                print("Error: Module name required")
                sys.exit(1)
            valid = manager.validate_module(args.args[0])
            print(f"Module name '{args.args[0]}': {'valid' if valid else 'invalid'}")
            sys.exit(0 if valid else 1)

        elif args.command == "presets":
            presets = manager.get_module_presets()
            print(f"{'Preset':<15} {'Description'}")
            print("-" * 60)
            for name, preset in presets.items():
                print(f"{name:<15} {preset['description']}")

        elif args.command == "preset":
            if not args.args:
                print("Error: Preset name required")
                sys.exit(1)
            success = manager._apply_preset(args.args[0])
            sys.exit(0 if success else 1)

        elif args.command == "export":
            output = Path(args.args[0]) if args.args else None
            manager.export_status(output)

    except KeyboardInterrupt:
        print("\nOperation cancelled")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
