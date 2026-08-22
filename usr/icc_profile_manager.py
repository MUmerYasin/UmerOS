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
ICC Profile Manager — ICC Color Profiles (/usr/share/color/icc)

FHS 3.0 Section 4.11.4: ICC color profiles.

Manages:
- ICC profile directories
- Profile file management
- Color space validation
- Profile metadata extraction
"""

import os
import struct
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from pathlib import Path


class ColorSpace(Enum):
    """ICC color space types."""
    CMYK = "CMYK"
    RGB = "RGB"
    GRAY = "GRAY"
    LAB = "LAB"
    XYZ = "XYZ"
    HSV = "HSV"
    HSL = "HSL"
    LUV = "LUV"
    YXY = "Yxy"
    UNKNOWN = "unknown"


class ProfileClass(Enum):
    """ICC profile class types."""
    INPUT = "scnr"
    DISPLAY = "mntr"
    OUTPUT = "prtr"
    LINKED = "link"
    ABSTRACT = "abst"
    NAMED_COLOR = "nmcl"
    UNKNOWN = "unknown"


class ICCStatus(IntEnum):
    """Status of ICC profiles."""
    MISSING = 0
    PRESENT = 1
    VALID = 2
    CORRUPTED = 3


@dataclass
class ICCProfile:
    """Represents an ICC color profile."""
    name: str
    path: Path
    color_space: ColorSpace = ColorSpace.UNKNOWN
    profile_class: ProfileClass = ProfileClass.UNKNOWN
    status: ICCStatus = ICCStatus.MISSING
    file_size: int = 0
    version: str = ""
    device_name: str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": str(self.path),
            "color_space": self.color_space.value,
            "profile_class": self.profile_class.value,
            "status": self.status.value,
            "file_size": self.file_size,
            "version": self.version,
            "device_name": self.device_name,
            "description": self.description
        }


class ICCProfileManager:
    """Manages /usr/share/color/icc profiles per FHS 3.0.

    FHS 3.0 Section 4.11.4 requires:
    - /usr/share/color must not contain files directly
    - All files go in subdirectories
    - /usr/share/color/icc contains ICC color profiles
    """

    BASE_DIR = Path("/usr/share/color")
    ICC_DIR = Path("/usr/share/color/icc")

    # Common ICC profile directories
    COMMON_DIRS = [
        "icc",
        "profiles",
        "devices",
        "standard",
    ]

    # ICC magic bytes
    ICC_MAGIC = b'iccp'

    def __init__(self):
        self._profiles: Dict[str, ICCProfile] = {}
        self._refresh()

    def _refresh(self):
        """Refresh ICC profile cache."""
        self._profiles.clear()
        self.BASE_DIR.mkdir(parents=True, exist_ok=True)
        self.ICC_DIR.mkdir(parents=True, exist_ok=True)

        self._scan_directory(self.ICC_DIR)

    def _scan_directory(self, directory: Path, depth: int = 0):
        """Recursively scan for ICC profiles."""
        if depth > 5:
            return

        try:
            for entry_path in sorted(directory.iterdir()):
                if entry_path.is_dir():
                    self._scan_directory(entry_path, depth + 1)
                elif entry_path.is_file() or entry_path.is_symlink():
                    if entry_path.suffix.lower() in ('.icc', '.icm', '.prof'):
                        profile = self._create_profile(entry_path)
                        self._profiles[entry.name] = profile
        except PermissionError:
            pass

    def _create_profile(self, path: Path) -> ICCProfile:
        """Create an ICCProfile for a path."""
        name = path.name
        color_space = ColorSpace.UNKNOWN
        profile_class = ProfileClass.UNKNOWN
        status = ICCStatus.MISSING
        file_size = 0
        version = ""
        device_name = ""

        if path.is_symlink():
            status = ICCStatus.PRESENT
        elif path.exists():
            file_size = path.stat().st_size
            if file_size >= 128:
                try:
                    with open(path, 'rb') as f:
                        header = f.read(128)
                    if header[:4] == self.ICC_MAGIC:
                        status = ICCStatus.VALID
                        version = self._extract_version(header)
                        color_space = self._extract_color_space(header)
                        profile_class = self._extract_profile_class(header)
                    else:
                        status = ICCStatus.PRESENT
                except Exception:
                    status = ICCStatus.CORRUPTED
            elif file_size > 0:
                status = ICCStatus.PRESENT

        descriptions = {
            ColorSpace.CMYK: "CMYK color profile",
            ColorSpace.RGB: "RGB color profile",
            ColorSpace.GRAY: "Grayscale color profile",
            ColorSpace.LAB: "LAB color profile",
            ColorSpace.XYZ: "XYZ color profile",
        }

        return ICCProfile(
            name=name,
            path=path,
            color_space=color_space,
            profile_class=profile_class,
            status=status,
            file_size=file_size,
            version=version,
            device_name=device_name,
            description=descriptions.get(color_space, "ICC color profile")
        )

    def _extract_version(self, header: bytes) -> str:
        """Extract ICC version from header."""
        try:
            major = header[0]
            minor = header[1] >> 4
            patch = header[1] & 0x0F
            return f"{major}.{minor}.{patch}"
        except Exception:
            return ""

    def _extract_color_space(self, header: bytes) -> ColorSpace:
        """Extract color space from header."""
        try:
            cs = header[16:20].decode('ascii', errors='ignore')
            cs_map = {
                'CMYK': ColorSpace.CMYK,
                'RGB ': ColorSpace.RGB,
                'GRAY': ColorSpace.GRAY,
                'Lab ': ColorSpace.LAB,
                'XYZ ': ColorSpace.XYZ,
            }
            return cs_map.get(cs, ColorSpace.UNKNOWN)
        except Exception:
            return ColorSpace.UNKNOWN

    def _extract_profile_class(self, header: bytes) -> ProfileClass:
        """Extract profile class from header."""
        try:
            pc = header[12:16].decode('ascii', errors='ignore')
            pc_map = {
                'scnr': ProfileClass.INPUT,
                'mntr': ProfileClass.DISPLAY,
                'prtr': ProfileClass.OUTPUT,
                'link': ProfileClass.LINKED,
                'abst': ProfileClass.ABSTRACT,
                'nmcl': ProfileClass.NAMED_COLOR,
            }
            return pc_map.get(pc, ProfileClass.UNKNOWN)
        except Exception:
            return ProfileClass.UNKNOWN

    def list_profiles(self) -> List[ICCProfile]:
        """List all ICC profiles."""
        return list(self._profiles.values())

    def get_profile(self, name: str) -> Optional[ICCProfile]:
        """Get a specific ICC profile."""
        return self._profiles.get(name)

    def has_profile(self, name: str) -> bool:
        """Check if an ICC profile exists."""
        return name in self._profiles

    def get_profiles_by_color_space(self, color_space: ColorSpace) -> List[ICCProfile]:
        """Get all profiles for a color space."""
        return [p for p in self._profiles.values()
                if p.color_space == color_space]

    def get_profiles_by_class(self, profile_class: ProfileClass) -> List[ICCProfile]:
        """Get all profiles of a class."""
        return [p for p in self._profiles.values()
                if p.profile_class == profile_class]

    def add_profile(self, name: str, content: bytes = b"") -> bool:
        """Add a new ICC profile."""
        try:
            path = self.ICC_DIR / name
            with open(path, 'wb') as f:
                f.write(content)
            self._refresh()
            return True
        except Exception:
            return False

    def remove_profile(self, name: str) -> bool:
        """Remove an ICC profile."""
        try:
            profile = self.get_profile(name)
            if profile and profile.path.exists():
                profile.path.unlink()
            self._refresh()
            return True
        except Exception:
            return False

    def validate_directory_structure(self) -> Dict[str, bool]:
        """Validate FHS 3.0 directory structure."""
        return {
            "base_dir_exists": self.BASE_DIR.exists(),
            "icc_dir_exists": self.ICC_DIR.exists(),
            "base_dir_has_no_files": self._dir_has_no_files(self.BASE_DIR),
        }

    def _dir_has_no_files(self, path: Path) -> bool:
        """Check if directory has no files (only subdirectories)."""
        if not path.exists():
            return True
        return all(entry.is_dir() for entry in path.iterdir())

    def get_status(self) -> Dict[str, Any]:
        """Get ICC profile manager status."""
        valid = sum(1 for p in self._profiles.values()
                    if p.status == ICCStatus.VALID)
        total_size = sum(p.file_size for p in self._profiles.values())
        color_spaces = {}
        for p in self._profiles.values():
            cs = p.color_space.value
            color_spaces[cs] = color_spaces.get(cs, 0) + 1

        return {
            "base_dir": str(self.BASE_DIR),
            "icc_dir": str(self.ICC_DIR),
            "base_dir_exists": self.BASE_DIR.exists(),
            "icc_dir_exists": self.ICC_DIR.exists(),
            "total_profiles": len(self._profiles),
            "valid": valid,
            "total_size": total_size,
            "color_spaces": color_spaces,
            "fhs_valid": self.validate_directory_structure()
        }


# Singleton instance
icc_profile_manager = ICCProfileManager()
