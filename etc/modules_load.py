"""
UmerOS /etc/modules-load.d/ Configuration Manager
Manages kernel modules to load at boot.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ModuleLoadConfig:
    """Configuration for module loading."""
    module: str
    options: Dict[str, str] = field(default_factory=dict)
    filename: str = "modules-load.conf"


class ModulesLoadManager:
    """Manages /etc/modules-load.d/ kernel module loading configuration."""

    def __init__(self, modules_path: str = "/etc/modules-load.d"):
        self.modules_path = Path(modules_path)
        self.configs: Dict[str, ModuleLoadConfig] = {}
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create modules-load.d directory structure."""
        self.modules_path.mkdir(parents=True, exist_ok=True)

    def add_module(self, module: str, options: Optional[Dict[str, str]] = None, filename: str = "modules-load.conf") -> None:
        """Add a module to load at boot."""
        config = ModuleLoadConfig(module=module, options=options or {}, filename=filename)
        self.configs[module] = config
        self._write_config_file(filename)

    def _write_config_file(self, filename: str) -> None:
        """Write a modules-load config file."""
        config_entries = [c for c in self.configs.values() if c.filename == filename]
        
        content = "# UmerOS modules to load at boot\n"
        for config in config_entries:
            content += config.module
            if config.options:
                for key, value in config.options.items():
                    content += f" {key}={value}"
            content += "\n"
        
        config_path = self.modules_path / filename
        config_path.write_text(content, encoding='utf-8')

    def remove_module(self, module: str) -> bool:
        """Remove a module from the load list."""
        if module in self.configs:
            config = self.configs[module]
            filename = config.filename
            del self.configs[module]
            self._write_config_file(filename)
            return True
        return False

    def list_modules(self) -> List[str]:
        """List all modules configured to load at boot."""
        return list(self.configs.keys())

    def get_config(self, module: str) -> Optional[ModuleLoadConfig]:
        """Get configuration for a specific module."""
        return self.configs.get(module)
