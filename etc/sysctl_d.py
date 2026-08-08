"""
UmerOS /etc/sysctl.d/ Configuration Manager
Manages kernel runtime parameters via sysctl.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class SysctlEntry:
    """A single sysctl parameter entry."""
    key: str
    value: str
    filename: str = "99-custom.conf"


class SysctlDManager:
    """Manages /etc/sysctl.d/ kernel parameter configuration."""

    def __init__(self, sysctl_path: str = "/etc/sysctl.d"):
        self.sysctl_path = Path(sysctl_path)
        self.entries: Dict[str, SysctlEntry] = {}
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create sysctl.d directory structure."""
        self.sysctl_path.mkdir(parents=True, exist_ok=True)

    def set_param(self, key: str, value: str, filename: str = "99-custom.conf") -> None:
        """Set a sysctl parameter."""
        entry = SysctlEntry(key=key, value=value, filename=filename)
        self.entries[key] = entry
        self._write_config_file(filename)

    def _write_config_file(self, filename: str) -> None:
        """Write a specific sysctl config file."""
        config_entries = [e for e in self.entries.values() if e.filename == filename]
        
        content = f"# UmerOS sysctl configuration: {filename}\n"
        for entry in config_entries:
            content += f"{entry.key} = {entry.value}\n"
        
        config_path = self.sysctl_path / filename
        config_path.write_text(content, encoding='utf-8')

    def get_param(self, key: str) -> Optional[str]:
        """Get a sysctl parameter value."""
        entry = self.entries.get(key)
        return entry.value if entry else None

    def list_params(self) -> List[str]:
        """List all configured sysctl parameters."""
        return list(self.entries.keys())

    def apply_config(self, filename: str) -> None:
        """Apply a sysctl configuration file (simulated)."""
        config_path = self.sysctl_path / filename
        if config_path.exists():
            print(f"[SYSCTL] Applied configuration: {filename}")
