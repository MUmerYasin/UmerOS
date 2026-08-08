"""
UmerOS /etc/os-release Configuration Manager
Manages OS identification information.
"""

from pathlib import Path
from typing import Dict
from dataclasses import dataclass


@dataclass
class OSRelease:
    """OS identification information."""
    name: str = "UmerOS"
    version: str = "2.0.0"
    codename: str = "pre-alpha"
    id: str = "umeros"
    id_like: str = "python"
    pretty_name: str = "UmerOS 2.0.0 Pre-Alpha"
    version_id: str = "2.0.0"
    home_url: str = "https://github.com/umer-os/umeros"
    bug_report_url: str = ""
    privacy_policy_url: str = ""
    cpe_name: str = ""
    build_id: str = ""
    image_id: str = ""
    image_version: str = ""
    variant: str = ""
    variant_id: str = ""
    platform_family: str = "python"
    logo: str = "umeros-logo"
    ansi_color: str = "1;34"


class OSReleaseManager:
    """Manages /etc/os-release OS identification."""

    def __init__(self, os_release_path: str = "/etc/os-release"):
        self.os_release_path = Path(os_release_path)
        self.data = OSRelease()

    def get_value(self, key: str) -> str:
        """Get an os-release value."""
        return getattr(self.data, key.lower(), "")

    def set_value(self, key: str, value: str) -> None:
        """Set an os-release value."""
        if hasattr(self.data, key.lower()):
            setattr(self.data, key.lower(), value)
            self._write_os_release()

    def get_all(self) -> Dict[str, str]:
        """Get all os-release values as a dict."""
        return {k: v for k, v in vars(self.data).items() if v and not k.startswith('_')}

    def _write_os_release(self) -> None:
        """Write /etc/os-release file."""
        content = "# /etc/os-release - OS identification\n"
        content += "# Managed by UmerOS\n\n"
        for key, value in vars(self.data).items():
            if key.startswith('_'):
                continue
            value = value.replace('"', '\\"')
            content += f'{key.upper()}="{value}"\n'
        self.os_release_path.write_text(content, encoding='utf-8')

    def get_pretty_name(self) -> str:
        """Get the pretty OS name."""
        return self.data.pretty_name

    def to_shell_variables(self) -> str:
        """Generate shell variable assignments."""
        lines = []
        for key, value in vars(self.data).items():
            if key.startswith('_') or not value:
                continue
            var_name = f"NAME" if key == "name" else key.upper()
            lines.append(f'{var_name}="{value}"')
        return "\n".join(lines)
