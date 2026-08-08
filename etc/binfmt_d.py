"""
UmerOS /etc/binfmt.d/ Configuration Manager
Manages kernel binary format handlers.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class BinFmtConfig:
    """Binary format handler configuration."""
    name: str
    magic: str = ""
    offset: int = 0
    interpreter: str = ""
    flags: str = "FP"
    extension: str = ""


class BinFmtManager:
    """Manages /etc/binfmt.d/ binary format configurations."""

    def __init__(self, binfmt_path: str = "/etc/binfmt.d"):
        self.binfmt_path = Path(binfmt_path)
        self.configs: Dict[str, BinFmtConfig] = {}
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create binfmt.d directory."""
        self.binfmt_path.mkdir(parents=True, exist_ok=True)

    def add_config(self, config: BinFmtConfig) -> None:
        """Add a binary format configuration."""
        self.configs[config.name] = config
        self._write_config(config)

    def _write_config(self, config: BinFmtConfig) -> None:
        """Write a binfmt config file."""
        content = f"# Binary format: {config.name}\n"
        if config.magic:
            content += f":{config.name}:M::{config.magic}::{config.interpreter}:{config.flags}\n"
        filepath = self.binfmt_path / f"{config.name}.conf"
        filepath.write_text(content, encoding='utf-8')

    def remove_config(self, name: str) -> bool:
        """Remove a binary format configuration."""
        if name in self.configs:
            filepath = self.binfmt_path / f"{name}.conf"
            filepath.unlink(missing_ok=True)
            del self.configs[name]
            return True
        return False

    def list_configs(self) -> List[str]:
        """List all binary format configurations."""
        return list(self.configs.keys())

    def get_config(self, name: str) -> Optional[BinFmtConfig]:
        """Get a specific binary format configuration."""
        return self.configs.get(name)
