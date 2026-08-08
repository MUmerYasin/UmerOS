"""
UmerOS /etc/inputrc Configuration Manager
Manages readline input configuration.
"""

from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass, field


@dataclass
class ReadlineConfig:
    """Readline/inputrc configuration."""
    key_bindings: Dict[str, str] = field(default_factory=dict)
    variables: Dict[str, str] = field(default_factory=dict)


class InputRCManager:
    """Manages /etc/inputrc - readline configuration."""

    DEFAULTS = {
        "set editing-mode": "emacs",
        "set input-meta": "on",
        "set output-meta": "on",
        "set convert-meta": "on",
        "set show-all-if-ambiguous": "on",
        "set completion-ignore-case": "on",
        "set colored-stats": "on",
        "set mark-symlinked-directories": "on",
        "set visible-stats": "on",
    }

    def __init__(self, inputrc_path: str = "/etc/inputrc"):
        self.inputrc_path = Path(inputrc_path)
        self.config = ReadlineConfig(variables=dict(self.DEFAULTS))
        self._write_config()

    def set_variable(self, name: str, value: str) -> None:
        """Set a readline variable."""
        self.config.variables[f"set {name}"] = value
        self._write_config()

    def add_key_binding(self, key: str, action: str) -> None:
        """Add a key binding."""
        self.config.key_bindings[key] = action
        self._write_config()

    def remove_key_binding(self, key: str) -> bool:
        """Remove a key binding."""
        if key in self.config.key_bindings:
            del self.config.key_bindings[key]
            self._write_config()
            return True
        return False

    def get_variable(self, name: str) -> Optional[str]:
        """Get a readline variable value."""
        return self.config.variables.get(f"set {name}")

    def _write_config(self) -> None:
        """Write inputrc file."""
        content = "# /etc/inputrc - readline configuration\n"
        content += "# Managed by UmerOS\n\n"
        for var, value in self.config.variables.items():
            content += f'{var} {value}\n'
        if self.config.key_bindings:
            content += "\n# Key bindings\n"
            for key, action in self.config.key_bindings.items():
                content += f'"{key}": {action}\n'
        self.inputrc_path.write_text(content, encoding='utf-8')
