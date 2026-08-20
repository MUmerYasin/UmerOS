"""
UmerOS Boot Splash Manager
============================
Manages boot splash screen and framebuffer graphics during boot.

Boot splash technologies:
    - Plymouth (most common, supports theme-based splash)
    - FBSplash (Gentoo)
    - console-setup (framebuffer console setup)
    - GRUB themes (bootloader splash)
    - systemd-boot splash (bootloader level)

Standard paths:
    /usr/share/plymouth/     Plymouth themes
    /usr/share/pixmaps/       Splash images
    /boot/splash/             Boot splash images
    /etc/plymouth/            Plymouth configuration
    /etc/initramfs-tools/     Initramfs splash config
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class SplashTechnology(Enum):
    PLYMOUTH = "plymouth"
    FBSPLASH = "fbsplash"
    CONSOLE = "console"
    NONE = "none"


class SplashTheme(Enum):
    UMEROS_DEFAULT = "umeros-default"
    UMEROS_MINIMAL = "umeros-minimal"
    UMEROS_ANIMATED = "umeros-animated"
    UMEROS_TEXT = "umeros-text"
    UMEROS_Hidden = "umeros-hidden"
    NONE = "none"


@dataclass
class SplashImage:
    name: str
    path: Path
    width: int = 0
    height: int = 0
    format: str = "png"  # png, jpg, tga, ppm
    file_size: int = 0
    hash_sha256: str = ""

    def compute_hash(self) -> str:
        if not self.path.exists():
            return ""
        h = hashlib.sha256()
        with open(self.path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        self.hash_sha256 = h.hexdigest()
        return self.hash_sha256


@dataclass
class SplashThemeConfig:
    name: str
    description: str = ""
    technology: SplashTechnology = SplashTechnology.PLYMOUTH
    background_color: str = "#000000"
    foreground_color: str = "#FFFFFF"
    font: str = "monospace"
    font_size: int = 24
    logo_path: Optional[Path] = None
    background_path: Optional[Path] = None
    progress_bar: bool = True
    progress_bar_color: str = "#0078D7"
    progress_bar_width: int = 400
    progress_bar_height: int = 8
    show_messages: bool = True
    show_quit_button: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "technology": self.technology.value,
            "background_color": self.background_color,
            "foreground_color": self.foreground_color,
            "font": self.font,
            "font_size": self.font_size,
            "logo_path": str(self.logo_path) if self.logo_path else None,
            "background_path": str(self.background_path) if self.background_path else None,
            "progress_bar": self.progress_bar,
            "progress_bar_color": self.progress_bar_color,
            "progress_bar_width": self.progress_bar_width,
            "progress_bar_height": self.progress_bar_height,
            "show_messages": self.show_messages,
        }


@dataclass
class FramebufferConfig:
    resolution: str = "1920x1080"
    depth: int = 32  # bits per pixel
    refresh_rate: int = 60  # Hz
    framebuffer_device: str = "/dev/fb0"
    vesa_mode: int = 0
    efi_gop: bool = True
    efi_uga: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resolution": self.resolution,
            "depth": self.depth,
            "refresh_rate": self.refresh_rate,
            "framebuffer_device": self.framebuffer_device,
            "vesa_mode": self.vesa_mode,
            "efi_gop": self.efi_gop,
            "efi_uga": self.efi_uga,
        }


class PlymouthManager:
    """Manages Plymouth boot splash."""

    def __init__(
        self,
        theme_dir: Path = Path("/usr/share/plymouth/themes"),
        config_dir: Path = Path("/etc/plymouth"),
        pixmaps_dir: Path = Path("/usr/share/pixmaps"),
    ):
        self.theme_dir = Path(theme_dir)
        self.config_dir = Path(config_dir)
        self.pixmaps_dir = Path(pixmaps_dir)
        self._themes: Dict[str, SplashThemeConfig] = {}
        self._init_default_themes()

    def _init_default_themes(self) -> None:
        """Initialize default Plymouth themes."""
        self._themes["umeros-default"] = SplashThemeConfig(
            name="umeros-default",
            description="Default UmerOS boot splash with animated progress",
            technology=SplashTechnology.PLYMOUTH,
            background_color="#000000",
            foreground_color="#FFFFFF",
            font="Ubuntu",
            font_size=20,
            progress_bar=True,
            progress_bar_color="#E95420",
            progress_bar_width=500,
        )

        self._themes["umeros-text"] = SplashThemeConfig(
            name="umeros-text",
            description="Text-only boot splash (no graphics)",
            technology=SplashTechnology.PLYMOUTH,
            progress_bar=False,
            show_messages=True,
        )

        self._themes["umeros-minimal"] = SplashThemeConfig(
            name="umeros-minimal",
            description="Minimal boot splash with logo only",
            technology=SplashTechnology.PLYMOUTH,
            background_color="#1A1A2E",
            foreground_color="#EAEAEA",
            progress_bar=True,
            progress_bar_color="#16213E",
            progress_bar_width=300,
        )

    def list_themes(self) -> List[SplashThemeConfig]:
        """List available Plymouth themes."""
        return list(self._themes.values())

    def get_theme(self, name: str) -> Optional[SplashThemeConfig]:
        return self._themes.get(name)

    def create_theme(
        self,
        name: str,
        description: str = "",
        background_color: str = "#000000",
        foreground_color: str = "#FFFFFF",
        progress_bar_color: str = "#0078D7",
        **kwargs,
    ) -> SplashThemeConfig:
        theme = SplashThemeConfig(
            name=name,
            description=description,
            background_color=background_color,
            foreground_color=foreground_color,
            progress_bar_color=progress_bar_color,
            **kwargs,
        )
        self._themes[name] = theme
        return theme

    def generate_plymouthd_conf(self, theme_name: str) -> str:
        """Generate /etc/plymouth/plymouthd.conf content."""
        return (
            "[Daemon]\n"
            f"Theme={theme_name}\n"
            "ShowDelay=0\n"
            "DeviceTimeout=8\n"
        )

    def generate_plymouth_theme(self, theme: SplashThemeConfig) -> str:
        """Generate Plymouth .plymouth theme file content."""
        return (
            "[Plymouth Theme]\n"
            f"Name={theme.name}\n"
            f"Description={theme.description}\n"
            "ModuleName=script\n\n"
            "[script]\n"
            f"ImageDir=/usr/share/plymouth/themes/{theme.name}\n"
            f"ScriptFile=/usr/share/plymouth/themes/{theme.name}/{theme.name}.script\n"
        )

    def generate_script(self, theme: SplashThemeConfig) -> str:
        """Generate Plymouth .script file content."""
        width, height = 1920, 1080  # Default resolution
        if theme.progress_bar:
            bar_y = height - 200
            bar_width = theme.progress_bar_width
            bar_height = theme.progress_bar_height
            bar_x = (width - bar_width) // 2

            script = f"""
# UmerOS Plymouth boot splash script
# Generated for theme: {theme.name}

# Progress bar
progress_bar = Image ({theme.progress_bar_color});
progress_bar.SetPosition({bar_x}, {bar_y}, 1);
progress_bar.SetSize({bar_width}, {bar_height});

# Logo placeholder (replace with actual logo path if available)
logo = Image ("umeros-logo.png");
logo.SetPosition((1920 - logo.GetWidth()) / 2, 200, 1);
"""
        else:
            script = f"""
# UmerOS Plymouth boot splash script (text only)
# Generated for theme: {theme.name}

# No graphical elements - text mode only
"""
        return script

    def install_theme(self, theme: SplashThemeConfig) -> bool:
        """Install a theme to the theme directory."""
        theme_dir = self.theme_dir / theme.name
        theme_dir.mkdir(parents=True, exist_ok=True)

        # Write theme config
        theme_file = theme_dir / f"{theme.name}.plymouth"
        theme_file.write_text(self.generate_plymouth_theme(theme))

        # Write script
        script_file = theme_dir / f"{theme.name}.script"
        script_file.write_text(self.generate_script(theme))

        return True

    def set_default(self, theme_name: str) -> bool:
        """Set the default Plymouth theme."""
        config_dir = self.config_dir
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "plymouthd.conf"
        config_file.write_text(self.generate_plymouthd_conf(theme_name))
        return True

    def get_cmdline_option(self) -> str:
        """Get kernel command line option for Plymouth."""
        return "splash"

    def status(self) -> Dict[str, Any]:
        active_theme = "unknown"
        config_file = self.config_dir / "plymouthd.conf"
        if config_file.exists():
            content = config_file.read_text()
            for line in content.splitlines():
                if line.startswith("Theme="):
                    active_theme = line.split("=", 1)[1].strip()
                    break

        return {
            "technology": "plymouth",
            "active_theme": active_theme,
            "available_themes": list(self._themes.keys()),
            "theme_dir": str(self.theme_dir),
            "config_dir": str(self.config_dir),
        }


class FramebufferManager:
    """Manages framebuffer console and splash graphics."""

    # Common VESA modes
    VESA_MODES: Dict[int, Tuple[int, int, int]] = {
        0x101: (640, 480, 8),
        0x103: (800, 600, 8),
        0x105: (1024, 768, 8),
        0x107: (1280, 1024, 8),
        0x110: (640, 480, 16),
        0x111: (800, 600, 16),
        0x112: (1024, 768, 16),
        0x113: (1280, 1024, 16),
        0x114: (1600, 1200, 16),
        0x115: (640, 480, 32),
        0x116: (800, 600, 32),
        0x117: (1024, 768, 32),
        0x118: (1280, 1024, 32),
        0x119: (1600, 1200, 32),
        0x11A: (1920, 1200, 32),
    }

    def __init__(self):
        self._config = FramebufferConfig()
        self._available_resolutions: List[Tuple[int, int, int]] = []

    def detect_framebuffer(self) -> FramebufferConfig:
        """Detect current framebuffer configuration."""
        # Try to read from /sys/class/graphics
        fb_path = Path("/sys/class/graphics/fb0")
        if fb_path.exists():
            try:
                # Read virtual size
                vsize = (fb_path / "virtual_size").read_text().strip()
                if "," in vsize:
                    w, h = vsize.split(",")
                    self._config.resolution = f"{w.strip()}x{h.strip()}"
            except (OSError, IOError):
                pass

            try:
                # Read bits per pixel
                bpp = (fb_path / "bits_per_pixel").read_text().strip()
                self._config.depth = int(bpp)
            except (OSError, IOError, ValueError):
                pass

        return self._config

    def get_available_resolutions(self) -> List[Tuple[int, int, int]]:
        """Get available framebuffer resolutions."""
        resolutions = []
        for mode, (w, h, bpp) in self.VESA_MODES.items():
            resolutions.append((w, h, bpp))
        return resolutions

    def set_resolution(self, width: int, height: int, depth: int = 32) -> bool:
        """Set framebuffer resolution."""
        self._config.resolution = f"{width}x{height}"
        self._config.depth = depth
        return True

    def get_kernel_cmdline_options(self) -> List[str]:
        """Get kernel command line options for framebuffer."""
        options = []
        w, h = self._get_resolution_parts()
        if w and h:
            options.append(f"video={w}x{h}@{self._config.depth}")
        if self._config.efi_gop:
            options.append("efifb")
        return options

    def _get_resolution_parts(self) -> Tuple[Optional[int], Optional[int]]:
        parts = self._config.resolution.split("x")
        if len(parts) == 2:
            try:
                return int(parts[0]), int(parts[1])
            except ValueError:
                pass
        return None, None

    def generate_grub_video_config(self) -> str:
        """Generate GRUB video configuration."""
        return (
            "set gfxmode=auto\n"
            "set gfxpayload=keep\n"
            "insmod all_video\n"
            "insmod gfxterm\n"
        )

    def generate_systemd_boot_config(self) -> str:
        """Generate systemd-boot splash configuration."""
        return (
            "# Framebuffer splash\n"
            "splash\n"
        )

    def status(self) -> Dict[str, Any]:
        w, h = self._get_resolution_parts()
        return {
            "config": self._config.to_dict(),
            "resolution": self._config.resolution,
            "depth": self._config.depth,
            "device": self._config.framebuffer_device,
            "efi_gop": self._config.efi_gop,
        }


class BootSplashManager:
    """Top-level boot splash manager."""

    def __init__(self):
        self.plymouth = PlymouthManager()
        self.framebuffer = FramebufferManager()
        self._technology = SplashTechnology.PLYMOUTH
        self._active_theme = "umeros-default"

    def set_technology(self, tech: SplashTechnology) -> None:
        self._technology = tech

    def get_technology(self) -> SplashTechnology:
        return self._technology

    def set_theme(self, theme_name: str) -> bool:
        self._active_theme = theme_name
        if self._technology == SplashTechnology.PLYMOUTH:
            return self.plymouth.set_default(theme_name)
        return True

    def get_theme(self) -> Optional[SplashThemeConfig]:
        return self.plymouth.get_theme(self._active_theme)

    def generate_boot_config(self) -> Dict[str, str]:
        """Generate boot configuration for all technologies."""
        configs = {}

        if self._technology == SplashTechnology.PLYMOUTH:
            configs["plymouthd.conf"] = self.plymouth.generate_plymouthd_conf(
                self._active_theme
            )
            configs["cmdline"] = self.plymouth.get_cmdline_option()

        configs["framebuffer"] = self.framebuffer.generate_grub_video_config()

        return configs

    def generate_grub_entry(self) -> str:
        """Generate GRUB menuentry with splash support."""
        theme = self.get_theme()
        splash_opts = "splash quiet"
        fb_opts = self.framebuffer.get_kernel_cmdline_options()
        all_opts = [splash_opts] + fb_opts

        return (
            "menuentry 'UmerOS' {\n"
            "    insmod all_video\n"
            f"    {self.framebuffer.generate_grub_video_config().strip()}\n"
            f"          /boot/vmlinuz {' '.join(all_opts)}\n"
            "    initrd /boot/initrd.img\n"
            "}"
        )

    def generate_plymouth_theme_package(self, name: str) -> Dict[str, str]:
        """Generate all files for a Plymouth theme package."""
        theme = self.plymouth.get_theme(name)
        if not theme:
            return {}

        return {
            f"{name}.plymouth": self.plymouth.generate_plymouth_theme(theme),
            f"{name}.script": self.plymouth.generate_script(theme),
            "plymouthd.conf": self.plymouth.generate_plymouthd_conf(name),
        }

    def create_hidden_theme(self) -> SplashThemeConfig:
        """Create a hidden/quiet splash theme."""
        return self.plymouth.create_theme(
            name="umeros-hidden",
            description="Hidden splash - no visible progress",
            background_color="#000000",
            foreground_color="#000000",
            progress_bar=False,
            show_messages=False,
        )

    def status(self) -> Dict[str, Any]:
        return {
            "technology": self._technology.value,
            "active_theme": self._active_theme,
            "plymouth": self.plymouth.status(),
            "framebuffer": self.framebuffer.status(),
        }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    """Round-trip the boot-splash managers against a temp /boot."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        from pathlib import Path
        bd = Path(tmp) / "boot"
        bd.mkdir()

        # PlymouthManager: install a stub theme and verify status.
        pm = PlymouthManager(theme_dir=bd / "plymouth" / "themes" / "umeros")
        pm.theme_dir.mkdir(parents=True, exist_ok=True)
        (pm.theme_dir / "umeros.plymouth").write_text(
            "[Plymouth Theme]\nName=Umeros\nDescription=stub\n"
        )
        if not pm.install_theme():
            return False
        if not pm.set_active_theme("umeros"):
            return False
        st = pm.status()
        if st["active_theme"] != "umeros":
            return False

        # FramebufferManager: configure a 1024x768x32 mode and read it back.
        fb = FramebufferManager()
        fb.set_mode(1024, 768, 32)
        if fb.current_mode() is None:
            return False

        # BootSplashManager: full integration.
        bsm = BootSplashManager(
            technology=SplashTechnology.PLYMOUTH,
            active_theme="umeros",
        )
        bsm.plymouth = pm
        st = bsm.status()
        if "plymouth" not in st:
            return False
    return True
