"""
UmerOS GRUB2 Manager
=====================
Complete GRUB2 bootloader management:
    - Menu entry generation
    - Module management (modprobe, insmod equivalents)
    - grubenv read/write (saved_entry, next_entry, boot_count)
    - Theme/background configuration
    - GRUB configuration file generation (grub.cfg)
    - Backup/restore of GRUB config
    - GRUB scriptlets (grub-mkconfig emulation)

Standard files:
    /boot/grub/grub.cfg           Main config
    /boot/grub/grubenv            Persistent env (saved_entry, etc.)
    /boot/grub/themes/            Theme definitions
    /boot/grub/i386-pc/           BIOS modules
    /boot/grub/x86_64-efi/        EFI modules
    /boot/grub/fonts/             Font files
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# GRUB environment block format: fixed 1024 bytes, first line is "# GRUB
# Environment Block", then KEY=VALUE lines, padded with '#' to fill 1024.
# ---------------------------------------------------------------------------
GRUB_ENV_SIZE = 1024


class GrubPlatform(Enum):
    BIOS = "i386-pc"
    EFI_X86_64 = "x86_64-efi"
    EFI_I386 = "i386-efi"
    ARM64_EFI = "arm64-efi"
    PPC64_EFI = "powerpc-ieee1275"


class GrubModuleType(Enum):
    NORMAL = "normal"
    LINUX = "linux"
    LVM = "lvm"
    RAID = "raid"
    CRYPTO = "cryptodisk"
    FILESYSTEM = "fs"
    PARTITION = "part"
    VIDEO = "video"
    TERMINAL = "terminal"
    NET = "net"
    SEARCH = "search"


@dataclass
class GrubModule:
    name: str
    module_type: GrubModuleType = GrubModuleType.NORMAL
    description: str = ""
    loaded: bool = False
    required_by: List[str] = field(default_factory=list)


@dataclass
class GrubMenuEntry:
    title: str
    linux_path: str
    initrd_path: Optional[str] = None
    options: str = ""
    root: str = ""
    uuid: Optional[str] = None
    submenu: Optional[str] = None
    hidden: bool = False
    disabled: bool = False

    def to_grub_script(self) -> str:
        lines = []
        lines.append(f'set default="${{saved_entry}}"')
        if self.submenu:
            lines.append(f'menuentry "{self.title}" --class umeros {{')
            lines.append(f'    set root="{self.root}"')
            if self.uuid:
                lines.append(f'    search --no-floppy --fs-uuid --set=root {self.uuid}')
            lines.append(f'    linux {self.linux_path} {self.options}')
            if self.initrd_path:
                lines.append(f'    initrd {self.initrd_path}')
            lines.append('}')
        else:
            lines.append(f'menuentry "{self.title}" {{')
            lines.append(f'    set root="{self.root}"')
            if self.uuid:
                lines.append(f'    search --no-floppy --fs-uuid --set=root {self.uuid}')
            lines.append(f'    linux {self.linux_path} {self.options}')
            if self.initrd_path:
                lines.append(f'    initrd {self.initrd_path}')
            lines.append('}')
        return '\n'.join(lines)


@dataclass
class GrubTheme:
    name: str
    background: Optional[str] = None
    wallpaper: Optional[str] = None
    title_color: str = "#ffffff"
    title_font: str = "/boot/grub/fonts/DejaVuSans-Bold14.pf2"
    message_color: str = "#cccccc"
    menu_color_normal: str = "#ffffff"
    menu_color_highlight: str = "#ff9900"
    selected_color: str = "#ff9900"
    terminal_color: str = "#ffffff"
    desktop_color: str = "#000000"
    font: str = "/boot/grub/fonts/DejaVuSans12.pf2"
    timeout: int = 5
    width: int = 640
    height: int = 480

    def to_theme_text(self) -> str:
        lines = [
            f'UmerOS Theme "{self.name}"',
            '{',
        ]
        if self.background:
            lines.append(f'    desktop-color = "{self.desktop_color}";')
            lines.append(f'    terminal-left = "0";')
            lines.append(f'    terminal-top = "0";')
            lines.append(f'    terminal-width = "100%";')
            lines.append(f'    terminal-height = "100%";')
        lines.append(f'    title-color = "{self.title_color}";')
        lines.append(f'    title-font = "{self.title_font}";')
        lines.append(f'    message-color = "{self.message_color}";')
        lines.append(f'    message-font = "{self.font}";')
        lines.append(f'    menu-color-normal = "{self.menu_color_normal}";')
        lines.append(f'    menu-color-highlight = "{self.menu_color_highlight}";')
        lines.append(f'    selected-color = "{self.selected_color}";')
        lines.append(f'    terminal-color = "{self.terminal_color}";')
        lines.append('}')
        return '\n'.join(lines)


@dataclass
class GrubConfig:
    default_entry: str = "0"
    timeout: int = 5
    hidden_timeout: Optional[int] = None
    gfxmode: str = "auto"
    gfxpayload: str = "keep"
    terminal_input: str = "console"
    terminal_output: str = "gfxterm"
    theme: Optional[str] = None
    dco_root: Optional[str] = None
    dco_uuid: Optional[str] = None
    dco_splash: Optional[str] = None
    dco_verbose: bool = True
    dco_quiet: bool = False
    dco_reboot: str = "warm"
    dco_halt: str = "poweroff"
    menu_entries: List[GrubMenuEntry] = field(default_factory=list)
    custom_commands: List[str] = field(default_factory=list)


class GrubEnv:
    """Read/write the GRUB environment block (1024-byte fixed file)."""

    def __init__(self, path: Path):
        self.path = path
        self._vars: Dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            content = self.path.read_text(errors="replace")
            for line in content.splitlines():
                if line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip('"')
                    self._vars[key] = val
        except (OSError, IOError):
            pass

    def get(self, key: str, default: str = "") -> str:
        return self._vars.get(key, default)

    def set(self, key: str, value: str) -> None:
        self._vars[key] = value

    def delete(self, key: str) -> bool:
        if key in self._vars:
            del self._vars[key]
            return True
        return False

    def items(self) -> Dict[str, str]:
        return dict(self._vars)

    def save(self) -> None:
        lines = ["# GRUB Environment Block"]
        for key in sorted(self._vars.keys()):
            val = self._vars[key]
            lines.append(f'{key}="{val}"')
        # Pad to exactly GRUB_ENV_SIZE with '#'
        content = "\n".join(lines) + "\n"
        if len(content) > GRUB_ENV_SIZE:
            content = content[:GRUB_ENV_SIZE]
        else:
            content = content.ljust(GRUB_ENV_SIZE, "#")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(content)

    def get_saved_entry(self) -> str:
        return self.get("saved_entry", "0")

    def set_saved_entry(self, entry: str) -> None:
        self.set("saved_entry", entry)
        self.save()

    def get_next_entry(self) -> Optional[str]:
        val = self.get("next_entry", "")
        return val if val else None

    def set_next_entry(self, entry: str) -> None:
        self.set("next_entry", entry)
        self.save()

    def clear_next_entry(self) -> None:
        self.delete("next_entry")
        self.save()

    def increment_boot_count(self) -> int:
        count = int(self.get("boot_count", "0")) + 1
        self.set("boot_count", str(count))
        self.set("last_boot_time", str(int(time.time())))
        self.save()
        return count


class GrubModuleManager:
    """Manages GRUB modules (loading, listing, dependencies)."""

    # Common GRUB module dependencies
    DEPENDENCIES = {
        "ext2": ["part_msdos", "part_gpt"],
        "ext4": ["part_msdos", "part_gpt"],
        "btrfs": ["part_msdos", "part_gpt"],
        "xfs": ["part_msdos", "part_gpt"],
        "fat": ["part_msdos", "part_gpt"],
        "iso9660": ["part_msdos", "part_gpt"],
        "luks": ["cryptodisk"],
        "lvm": ["part_msdos", "part_gpt"],
        "mdraid": ["part_msdos", "part_gpt"],
        "video_bochs": ["video"],
        "video_cirrus": ["video"],
        "video_efi_gop": ["video"],
        "video_fbdev": ["video"],
        "video_vesafb": ["video"],
        "video_vbe": ["video"],
        "gfxterm": ["video", "terminal"],
        "normal": ["boot", "echo", "ls", "test", "search"],
        "linux": ["normal"],
        " chainloader": ["normal"],
        "boot": ["normal"],
    }

    def __init__(self, platform: GrubPlatform = GrubPlatform.BIOS):
        self.platform = platform
        self._modules: Dict[str, GrubModule] = {}
        self._loaded: List[str] = []
        self._init_modules()

    def _init_modules(self) -> None:
        common_modules = [
            ("normal", GrubModuleType.NORMAL, "GRUB normal mode"),
            ("boot", GrubModuleType.NORMAL, "Boot loader"),
            ("linux", GrubModuleType.LINUX, "Linux kernel support"),
            ("echo", GrubModuleType.NORMAL, "Echo command"),
            ("ls", GrubModuleType.NORMAL, "List files"),
            ("test", GrubModuleType.NORMAL, "Conditional test"),
            ("search", GrubModuleType.SEARCH, "Search for devices"),
            ("search_fs_uuid", GrubModuleType.SEARCH, "Search by UUID"),
            ("search_label", GrubModuleType.SEARCH, "Search by label"),
            ("search_fs_label", GrubModuleType.SEARCH, "Search by filesystem label"),
            ("configfile", GrubModuleType.NORMAL, "Load config file"),
            ("loadenv", GrubModuleType.NORMAL, "Load environment"),
            ("saveenv", GrubModuleType.NORMAL, "Save environment"),
            ("set", GrubModuleType.NORMAL, "Set variables"),
            ("unset", GrubModuleType.NORMAL, "Unset variables"),
            ("export", GrubModuleType.NORMAL, "Export variables"),
            ("insmod", GrubModuleType.NORMAL, "Load module"),
            ("rmmod", GrubModuleType.NORMAL, "Unload module"),
            ("probe", GrubModuleType.NORMAL, "Probe devices"),
            ("blocklist", GrubModuleType.NORMAL, "Block list"),
            ("minicmd", GrubModuleType.NORMAL, "Minimal commands"),
        ]

        fs_modules = [
            ("ext2", GrubModuleType.FILESYSTEM, "ext2/ext3/ext4"),
            ("ext4", GrubModuleType.FILESYSTEM, "ext4 filesystem"),
            ("btrfs", GrubModuleType.FILESYSTEM, "Btrfs filesystem"),
            ("xfs", GrubModuleType.FILESYSTEM, "XFS filesystem"),
            ("fat", GrubModuleType.FILESYSTEM, "FAT filesystem"),
            ("iso9660", GrubModuleType.FILESYSTEM, "ISO 9660"),
            ("ntfs", GrubModuleType.FILESYSTEM, "NTFS filesystem"),
            ("udf", GrubModuleType.FILESYSTEM, "UDF filesystem"),
            ("reiserfs", GrubModuleType.FILESYSTEM, "ReiserFS"),
            ("jfs", GrubModuleType.FILESYSTEM, "JFS"),
            ("nilfs2", GrubModuleType.FILESYSTEM, "NILFS2"),
            ("hfs", GrubModuleType.FILESYSTEM, "HFS"),
            ("hfsplus", GrubModuleType.FILESYSTEM, "HFS+"),
            ("apfs", GrubModuleType.FILESYSTEM, "APFS"),
        ]

        part_modules = [
            ("part_msdos", GrubModuleType.PARTITION, "MSDOS partition table"),
            ("part_gpt", GrubModuleType.PARTITION, "GPT partition table"),
            ("part_apple", GrubModuleType.PARTITION, "Apple partition map"),
            ("part_sun", GrubModuleType.PARTITION, "Sun partition table"),
            ("part_bsd", GrubModuleType.PARTITION, "BSD disklabel"),
        ]

        video_modules = [
            ("video", GrubModuleType.VIDEO, "Video output core"),
            ("video_bochs", GrubModuleType.VIDEO, "Bochs video"),
            ("video_cirrus", GrubModuleType.VIDEO, "Cirrus video"),
            ("video_efi_gop", GrubModuleType.VIDEO, "EFI GOP video"),
            ("video_fbdev", GrubModuleType.VIDEO, "Framebuffer video"),
            ("video_vesafb", GrubModuleType.VIDEO, "VESA framebuffer"),
            ("video_vbe", GrubModuleType.VIDEO, "VBE video"),
            ("video_all_video", GrubModuleType.VIDEO, "All video drivers"),
        ]

        terminal_modules = [
            ("terminal", GrubModuleType.TERMINAL, "Terminal support"),
            ("console", GrubModuleType.TERMINAL, "Console terminal"),
            ("serial", GrubModuleType.TERMINAL, "Serial terminal"),
            ("gfxterm", GrubModuleType.TERMINAL, "Graphics terminal"),
            ("vga_text", GrubModuleType.TERMINAL, "VGA text terminal"),
            ("memdisk", GrubModuleType.TERMINAL, "Memory disk"),
        ]

        crypto_modules = [
            ("cryptodisk", GrubModuleType.CRYPTO, "Crypto disk support"),
            ("luks", GrubModuleType.CRYPTO, "LUKS encryption"),
            ("geli", GrubModuleType.CRYPTO, "GELI encryption"),
            ("gcry_rijndael", GrubModuleType.CRYPTO, "AES cipher"),
            ("gcry_sha256", GrubModuleType.CRYPTO, "SHA256 hash"),
            ("gcry_sha512", GrubModuleType.CRYPTO, "SHA512 hash"),
            ("gcry_whirlpool", GrubModuleType.CRYPTO, "Whirlpool hash"),
        ]

        net_modules = [
            ("net", GrubModuleType.NET, "Network core"),
            ("http", GrubModuleType.NET, "HTTP protocol"),
            ("tftp", GrubModuleType.NET, "TFTP protocol"),
            ("pxe", GrubModuleType.NET, "PXE network boot"),
            ("efinet", GrubModuleType.NET, "EFI network stack"),
            ("ipxe", GrubModuleType.NET, "iPXE"),
        ]

        lvm_modules = [
            ("lvm", GrubModuleType.LVM, "Logical Volume Manager"),
            ("mdraid", GrubModuleType.RAID, "Software RAID"),
            ("mdraid09", GrubModuleType.RAID, "MD RAID 0.9"),
            ("mdraid1x", GrubModuleType.RAID, "MD RAID 1.x"),
            ("dm_nvme", GrubModuleType.LVM, "Device-mapper NVMe"),
        ]

        all_modules = (
            common_modules + fs_modules + part_modules + video_modules
            + terminal_modules + crypto_modules + net_modules + lvm_modules
        )

        for name, mtype, desc in all_modules:
            self._modules[name] = GrubModule(
                name=name, module_type=mtype, description=desc
            )

    def list_modules(self, module_type: Optional[GrubModuleType] = None) -> List[GrubModule]:
        modules = list(self._modules.values())
        if module_type:
            modules = [m for m in modules if m.module_type == module_type]
        return sorted(modules, key=lambda m: m.name)

    def get_module(self, name: str) -> Optional[GrubModule]:
        return self._modules.get(name)

    def load_module(self, name: str) -> bool:
        mod = self._modules.get(name)
        if not mod:
            return False
        if name not in self._loaded:
            self._loaded.append(name)
            mod.loaded = True
        return True

    def unload_module(self, name: str) -> bool:
        if name in self._loaded:
            self._loaded.remove(name)
            mod = self._modules.get(name)
            if mod:
                mod.loaded = False
            return True
        return False

    def get_dependencies(self, name: str) -> List[str]:
        return list(self.DEPENDENCIES.get(name, []))

    def get_loaded(self) -> List[str]:
        return list(self._loaded)

    def resolve_all_deps(self, names: List[str]) -> List[str]:
        resolved = []
        visited = set()
        stack = list(names)
        while stack:
            n = stack.pop()
            if n in visited:
                continue
            visited.add(n)
            deps = self.DEPENDENCIES.get(n, [])
            for d in deps:
                if d not in visited:
                    stack.append(d)
            resolved.append(n)
        return resolved


class GrubManager:
    """Complete GRUB2 bootloader manager."""

    def __init__(self, boot_dir: Path, platform: GrubPlatform = GrubPlatform.BIOS):
        self.boot_dir = Path(boot_dir)
        self.grub_dir = self.boot_dir / "grub"
        self.platform = platform
        self.config = GrubConfig()
        self.env = GrubEnv(self.grub_dir / "grubenv")
        self.module_manager = GrubModuleManager(platform)
        self.theme: Optional[GrubTheme] = None
        self._init_dirs()

    def _init_dirs(self) -> None:
        for d in [
            self.grub_dir,
            self.grub_dir / "themes",
            self.grub_dir / "fonts",
            self.grub_dir / "i386-pc",
            self.grub_dir / "x86_64-efi",
            self.grub_dir / "arm64-efi",
        ]:
            d.mkdir(parents=True, exist_ok=True)

    # --- Menu Entries ---

    def add_menu_entry(
        self,
        title: str,
        linux_path: str,
        initrd_path: Optional[str] = None,
        options: str = "ro quiet",
        root: str = "(hd0,msdos1)",
        uuid: Optional[str] = None,
        submenu: Optional[str] = None,
    ) -> GrubMenuEntry:
        entry = GrubMenuEntry(
            title=title,
            linux_path=linux_path,
            initrd_path=initrd_path,
            options=options,
            root=root,
            uuid=uuid,
            submenu=submenu,
        )
        self.config.menu_entries.append(entry)
        return entry

    def remove_menu_entry(self, title: str) -> bool:
        for i, entry in enumerate(self.config.menu_entries):
            if entry.title == title:
                self.config.menu_entries.pop(i)
                return True
        return False

    def get_menu_entries(self) -> List[GrubMenuEntry]:
        return list(self.config.menu_entries)

    def generate_menu_from_kernels(self, kernels: Dict[str, Any]) -> None:
        """Auto-generate menu entries from detected kernel images."""
        self.config.menu_entries.clear()
        sorted_versions = sorted(kernels.keys())
        for i, ver in enumerate(sorted_versions):
            ki = kernels[ver]
            initrd = f"/boot/initrd.img-{ver}"
            initrd_alt = f"/boot/initrd-{ver}.img"
            initrd_found = None
            if Path(initrd).exists():
                initrd_found = initrd
            elif Path(initrd_alt).exists():
                initrd_found = initrd_alt

            title = f"UmerOS {ver}"
            if ki.is_default:
                title += " (default)"

            self.add_menu_entry(
                title=title,
                linux_path=f"/boot/vmlinuz-{ver}",
                initrd_path=initrd_found,
                options="ro quiet splash",
                root="(hd0,msdos1)",
            )

    # --- Configuration Generation ---

    def generate_grub_cfg(self) -> str:
        """Generate the full grub.cfg content."""
        lines = []

        # Header
        lines.append("# UmerOS GRUB2 Configuration")
        lines.append(f"# Generated: {datetime.now().isoformat()}")
        lines.append(f"# Platform: {self.platform.value}")
        lines.append("")

        # Global settings
        lines.append(f"set default={self.config.default_entry}")
        lines.append(f"set timeout={self.config.timeout}")
        if self.config.hidden_timeout is not None:
            lines.append(f"set hidden_timeout={self.config.hidden_timeout}")
        lines.append(f"set gfxmode={self.config.gfxmode}")
        lines.append(f"set gfxpayload={self.config.gfxpayload}")
        lines.append("")

        # Terminal
        lines.append(f"set terminal_input={self.config.terminal_input}")
        lines.append(f"set terminal_output={self.config.terminal_output}")
        lines.append("")

        # Theme
        if self.config.theme:
            lines.append(f'set theme="{self.config.theme}"')
            lines.append("")

        # Insmod required modules
        loaded = self.module_manager.get_loaded()
        for mod_name in loaded:
            lines.append(f"insmod {mod_name}")
        lines.append("")

        # Load boot count
        boot_count = self.env.increment_boot_count()
        lines.append(f'set boot_count="{boot_count}"')
        lines.append("")

        # Splash image
        if self.config.dco_splash:
            lines.append(f'insmod png')
            lines.append(f'insmod jpeg')
            lines.append(f'background_image {self.config.dco_splash}')
            lines.append("")

        # Quiet mode
        if self.config.dco_quiet:
            lines.append('set quiet=1')
        lines.append("")

        # DCO root
        if self.config.dco_uuid:
            lines.append(f'search --no-floppy --fs-uuid --set=root {self.config.dco_uuid}')
        elif self.config.dco_root:
            lines.append(f'set root={self.config.dco_root}')
        lines.append("")

        # Custom commands
        for cmd in self.config.custom_commands:
            lines.append(cmd)
        lines.append("")

        # Menu entries
        if self.config.menu_entries:
            lines.append("menuentry 'UmerOS Boot Menu' {")
            lines.append("    echo 'Loading UmerOS...'")
            lines.append("}")
            lines.append("")

            for i, entry in enumerate(self.config.menu_entries):
                if entry.hidden:
                    continue
                if entry.submenu:
                    lines.append(f'submenu "{entry.title}" {{')
                    lines.append(f'    set root="{entry.root}"')
                    if entry.uuid:
                        lines.append(f'    search --no-floppy --fs-uuid --set=root {entry.uuid}')
                    lines.append(f'    menuentry "{entry.title}" {{')
                else:
                    if entry.disabled:
                        lines.append(f'# menuentry "{entry.title}" {{')
                    else:
                        lines.append(f'menuentry "{entry.title}" {{')

                lines.append(f'    set root="{entry.root}"')
                if entry.uuid:
                    lines.append(f'    search --no-floppy --fs-uuid --set=root {entry.uuid}')
                lines.append(f'    linux {entry.linux_path} {entry.options}')
                if entry.initrd_path:
                    lines.append(f'    initrd {entry.initrd_path}')

                if entry.disabled:
                    lines.append(f'# }}')
                else:
                    lines.append(f'}}')

                if entry.submenu:
                    lines.append(f'}}')
                lines.append("")

        # Recovery entries
        if self.config.menu_entries:
            lines.append("menuentry 'UmerOS Recovery Mode' {")
            lines.append('    set root="(hd0,msdos1)"')
            if self.config.menu_entries:
                first = self.config.menu_entries[0]
                lines.append(f'    linux {first.linux_path} recovery nomodeset')
                if first.initrd_path:
                    lines.append(f'    initrd {first.initrd_path}')
            lines.append('}')
            lines.append("")

        # UEFI shell (if EFI)
        if "efi" in self.platform.value:
            lines.append("menuentry 'UEFI Firmware Settings' {")
            lines.append("    fwsetup")
            lines.append("}")
            lines.append("")

            lines.append("menuentry 'UEFI Shell' {")
            lines.append("    chainloader /efi/shell/shellx64.efi")
            lines.append("}")
            lines.append("")

        return "\n".join(lines)

    def write_grub_cfg(self) -> Path:
        grub_cfg = self.grub_dir / "grub.cfg"
        content = self.generate_grub_cfg()
        grub_cfg.write_text(content)
        return grub_cfg

    def read_grub_cfg(self) -> Optional[str]:
        grub_cfg = self.grub_dir / "grub.cfg"
        if grub_cfg.exists():
            return grub_cfg.read_text()
        return None

    # --- Theme ---

    def set_theme(
        self,
        name: str = "UmerOS Dark",
        background: Optional[str] = None,
        title_color: str = "#ffffff",
        menu_color_normal: str = "#ffffff",
        menu_color_highlight: str = "#ff9900",
        timeout: int = 5,
    ) -> GrubTheme:
        self.theme = GrubTheme(
            name=name,
            background=background,
            title_color=title_color,
            menu_color_normal=menu_color_normal,
            menu_color_highlight=menu_color_highlight,
            timeout=timeout,
        )
        self.config.theme = f"/boot/grub/themes/{name.lower().replace(' ', '-')}/theme.txt"
        return self.theme

    def write_theme(self) -> Optional[Path]:
        if not self.theme:
            return None
        theme_dir_name = self.theme.name.lower().replace(" ", "-")
        theme_dir = self.grub_dir / "themes" / theme_dir_name
        theme_dir.mkdir(parents=True, exist_ok=True)
        theme_file = theme_dir / "theme.txt"
        theme_file.write_text(self.theme.to_theme_text())
        return theme_file

    # --- Backup / Restore ---

    def backup_config(self, backup_name: Optional[str] = None) -> Path:
        name = backup_name or f"grub.cfg.bak.{int(time.time())}"
        backup_path = self.grub_dir / "backups" / name
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        grub_cfg = self.grub_dir / "grub.cfg"
        if grub_cfg.exists():
            shutil.copy2(str(grub_cfg), str(backup_path))
        # Also backup grubenv
        grubenv = self.grub_dir / "grubenv"
        env_backup = self.grub_dir / "backups" / f"grubenv.{name}"
        if grubenv.exists():
            shutil.copy2(str(grubenv), str(env_backup))
        return backup_path

    def restore_config(self, backup_name: str) -> bool:
        backup_path = self.grub_dir / "backups" / backup_name
        if not backup_path.exists():
            return False
        grub_cfg = self.grub_dir / "grub.cfg"
        shutil.copy2(str(backup_path), str(grub_cfg))
        return True

    def list_backups(self) -> List[str]:
        backups_dir = self.grub_dir / "backups"
        if not backups_dir.exists():
            return []
        return sorted([f.name for f in backups_dir.iterdir()
                        if f.name.startswith("grub.cfg.bak.")])

    # --- Save / Load ---

    def save_environment(self) -> None:
        self.env.save()

    def get_saved_entry(self) -> str:
        return self.env.get_saved_entry()

    def set_saved_entry(self, entry: str) -> None:
        self.env.set_saved_entry(entry)

    def get_next_entry(self) -> Optional[str]:
        return self.env.get_next_entry()

    def set_next_entry(self, entry: str) -> None:
        self.env.set_next_entry(entry)

    # --- Module loading helpers ---

    def load_modules_for_fs(self, fs_type: str) -> List[str]:
        """Load the right modules for a given filesystem type."""
        deps = self.module_manager.get_dependencies(fs_type)
        all_deps = self.module_manager.resolve_all_deps([fs_type] + deps)
        for m in all_deps:
            self.module_manager.load_module(m)
        return all_deps

    def load_modules_for_lvm(self) -> List[str]:
        deps = self.module_manager.resolve_all_deps(["lvm"])
        for m in deps:
            self.module_manager.load_module(m)
        return deps

    def load_modules_for_crypto(self, cipher: str = "luks") -> List[str]:
        deps = self.module_manager.resolve_all_deps([cipher])
        for m in deps:
            self.module_manager.load_module(m)
        return deps

    # --- Status ---

    def status(self) -> Dict[str, Any]:
        return {
            "platform": self.platform.value,
            "grub_dir": str(self.grub_dir),
            "config_exists": (self.grub_dir / "grub.cfg").exists(),
            "env_exists": (self.grub_dir / "grubenv").exists(),
            "saved_entry": self.env.get_saved_entry(),
            "next_entry": self.env.get_next_entry(),
            "boot_count": self.env.get("boot_count", "0"),
            "menu_entries": len(self.config.menu_entries),
            "loaded_modules": self.module_manager.get_loaded(),
            "theme": self.theme.name if self.theme else None,
            "timeout": self.config.timeout,
        }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    """Run built-in self-test for grub_manager."""
    import shutil
    import tempfile

    td = tempfile.mkdtemp(prefix="umeros_grub_test_")
    try:
        boot_dir = Path(td) / "boot"

        # GrubEnv
        env = GrubEnv(boot_dir / "grub" / "grubenv")
        env.set("key1", "value1")
        assert env.get("key1") == "value1"
        env.delete("key1")
        assert env.get("key1") is None

        # GrubConfig defaults
        cfg = GrubConfig()
        assert cfg.timeout == 5
        assert isinstance(cfg.menu_entries, list)

        # GrubMenuEntry
        entry = GrubMenuEntry(title="Linux", linux_path="/boot/vmlinuz")
        assert entry.title == "Linux"
        assert entry.linux_path == "/boot/vmlinuz"

        # GrubModule
        mod = GrubModule(name="normal", module_type="command")
        assert mod.name == "normal"
        assert mod.module_type == "command"

        # GrubTheme
        thm = GrubTheme(name="default")
        assert thm.name == "default"

        # GrubModuleManager
        mm = GrubModuleManager(boot_dir / "grub")
        mod2 = mm.load_module("normal")
        assert mod2 is not None
        assert mod2.loaded is True
        loaded = mm.get_loaded()
        assert "normal" in loaded

        # GrubManager
        mgr = GrubManager(boot_dir)
        s = mgr.status()
        assert "platform" in s
        assert "timeout" in s

        return True
    except Exception as exc:  # noqa: BLE001
        import sys
        print(f"grub_manager selftest FAILED: {exc}", file=sys.stderr)
        return False
    finally:
        shutil.rmtree(td, ignore_errors=True)
