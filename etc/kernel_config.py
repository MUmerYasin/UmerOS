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
UmerOS - /etc/kernel manager
FHS 3.0: /etc/kernel/ contains kernel-related configuration.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, List

KERNEL_DIR = Path(os.environ.get("UMEROS_KERNEL", "/etc/kernel"))

DEFAULT_CONFIG = {
    "panic": "10",
    "hung_task_timeout_secs": "120",
}


class KernelConfigManager:
    """Manages /etc/kernel/ configuration files."""

    def __init__(self, path: str = None):
        self.path = Path(path) if path else KERNEL_DIR

    def _ensure_dir(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)

    def list_files(self) -> List[str]:
        self._ensure_dir()
        return sorted(f.name for f in self.path.iterdir() if f.is_file())

    def read_file(self, name: str) -> str:
        p = self.path / name
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def write_file(self, name: str, content: str) -> None:
        self._ensure_dir()
        (self.path / name).write_text(content, encoding="utf-8")
