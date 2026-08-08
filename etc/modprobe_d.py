"""
UmerOS /etc/modprobe.d/ Configuration Manager
Manages kernel module configuration files.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ModprobeConfig:
    """Configuration for a single modprobe.d file."""
    module: str
    options: Dict[str, str] = field(default_factory=dict)
    blacklist: bool = False
    install: Optional[str] = None
    remove: Optional[str] = None
    softdep: Optional[str] = None


class ModprobeDManager:
    """Manages /etc/modprobe.d/ kernel module configuration."""

    def __init__(self, modprobe_path: str = "/etc/modprobe.d"):
        self.modprobe_path = Path(modprobe_path)
        self.configs: Dict[str, ModprobeConfig] = {}
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create modprobe.d directory structure."""
        self.modprobe_path.mkdir(parents=True, exist_ok=True)

    def load_config(self, config: ModprobeConfig) -> None:
        """Load a modprobe configuration."""
        self.configs[config.module] = config

    def create_blacklist_file(self, modules: List[str], filename: str = "blacklist.conf") -> None:
        """Create a blacklist configuration file."""
        content = "# Blacklist configuration\n"
        for module in modules:
            content += f"blacklist {module}\n"
        
        config_path = self.modprobe_path / filename
        config_path.write_text(content, encoding='utf-8')

    def create_options_file(self, module: str, options: Dict[str, str], filename: Optional[str] = None) -> None:
        """Create an options configuration file."""
        if not filename:
            filename = f"{module}-options.conf"
        
        content = f"# Options for {module}\n"
        content += f"options {module}"
        for key, value in options.items():
            content += f" {key}={value}"
        content += "\n"
        
        config_path = self.modprobe_path / filename
        config_path.write_text(content, encoding='utf-8')

    def get_config(self, module: str) -> Optional[ModprobeConfig]:
        """Get configuration for a specific module."""
        return self.configs.get(module)

    def list_configs(self) -> List[str]:
        """List all configured modules."""
        return list(self.configs.keys())
