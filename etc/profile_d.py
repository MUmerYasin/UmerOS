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
UmerOS /etc/profile.d/ Configuration Manager
Manages shell profile scripts.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ProfileScript:
    """A profile.d script entry."""
    name: str
    content: str
    executable: bool = True
    extension: str = ".sh"


class ProfileDManager:
    """Manages /etc/profile.d/ shell initialization scripts."""

    def __init__(self, profiled_path: str = "/etc/profile.d"):
        self.profiled_path = Path(profiled_path)
        self.scripts: Dict[str, ProfileScript] = {}
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create profile.d directory."""
        self.profiled_path.mkdir(parents=True, exist_ok=True)

    def add_script(self, script: ProfileScript) -> None:
        """Add a profile.d script."""
        self.scripts[script.name] = script
        self._write_script(script)

    def _write_script(self, script: ProfileScript) -> None:
        """Write a profile.d script file."""
        filename = script.name
        if not filename.endswith(script.extension):
            filename += script.extension
        filepath = self.profiled_path / filename
        filepath.write_text(script.content, encoding='utf-8')
        if script.executable:
            filepath.chmod(0o755)

    def remove_script(self, name: str) -> bool:
        """Remove a profile.d script."""
        if name in self.scripts:
            script = self.scripts[name]
            filename = name + script.extension
            filepath = self.profiled_path / filename
            filepath.unlink(missing_ok=True)
            del self.scripts[name]
            return True
        return False

    def list_scripts(self) -> List[str]:
        """List all profile.d scripts."""
        return list(self.scripts.keys())

    def get_script(self, name: str) -> Optional[ProfileScript]:
        """Get a profile.d script."""
        return self.scripts.get(name)

    def add_env_variable(self, name: str, value: str, script_name: str = "custom_env.sh") -> None:
        """Add an environment variable export to a profile.d script."""
        existing = self.scripts.get(script_name)
        content = existing.content if existing else "#!/bin/bash\n# Custom environment variables\n"
        content += f'export {name}="{value}"\n'
        script = ProfileScript(name=script_name, content=content)
        self.add_script(script)
