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

"""
UmerOS /etc/sane.d/ Configuration Manager
Manages scanner (SANE) backend configurations.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class SANEBackend:
    """Configuration for a SANE scanner backend."""
    name: str
    device_type: str = "usb"
    vendor_id: Optional[str] = None
    product_id: Optional[str] = None
    enabled: bool = True


class SANEConfigManager:
    """Manages /etc/sane.d/ scanner configuration."""

    def __init__(self, sane_path: str = "/etc/sane.d"):
        self.sane_path = Path(sane_path)
        self.backends: Dict[str, SANEBackend] = {}
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create sane.d directory structure."""
        self.sane_path.mkdir(parents=True, exist_ok=True)

    def add_backend(self, backend: SANEBackend) -> None:
        """Add a SANE backend configuration."""
        self.backends[backend.name] = backend
        self._write_backend_file(backend)

    def _write_backend_file(self, backend: SANEBackend) -> None:
        """Write a backend configuration file."""
        content = f"# SANE backend: {backend.name}\n"
        content += f"# Device type: {backend.device_type}\n"
        
        if backend.vendor_id:
            content += f"option vendor-id 0x{backend.vendor_id}\n"
        if backend.product_id:
            content += f"option product-id 0x{backend.product_id}\n"
        
        if not backend.enabled:
            content += "# Backend disabled\n"
        
        config_file = self.sane_path / f"{backend.name}.conf"
        config_file.write_text(content, encoding='utf-8')

    def get_backend(self, name: str) -> Optional[SANEBackend]:
        """Get a SANE backend configuration."""
        return self.backends.get(name)

    def list_backends(self) -> List[str]:
        """List all configured SANE backends."""
        return list(self.backends.keys())

    def enable_backend(self, name: str) -> bool:
        """Enable a SANE backend."""
        backend = self.backends.get(name)
        if backend:
            backend.enabled = True
            self._write_backend_file(backend)
            return True
        return False

    def disable_backend(self, name: str) -> bool:
        """Disable a SANE backend."""
        backend = self.backends.get(name)
        if backend:
            backend.enabled = False
            self._write_backend_file(backend)
            return True
        return False
