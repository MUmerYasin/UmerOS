"""
UmerOS /etc/e2fsck.conf Configuration Manager
Manages ext2/3/4 filesystem check configuration.
"""

from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class E2fsckConfig:
    """e2fsck configuration options."""
    journal_data_datetime_change: bool = True
    journal_async_commit: bool = False
    check_normal_dirs: bool = True
    check_symlinks: bool = True
    check_bad_blocks: bool = True
    max_lost_found: int = 0


class E2fsckConfigManager:
    """Manages /etc/e2fsck.conf - ext2/3/4 fsck configuration."""

    def __init__(self, e2fsck_path: str = "/etc/e2fsck.conf"):
        self.e2fsck_path = Path(e2fsck_path)
        self.config = E2fsckConfig()
        self._write_config()

    def set_option(self, option: str, value) -> None:
        """Set an e2fsck option."""
        if hasattr(self.config, option):
            setattr(self.config, option, value)
            self._write_config()

    def get_option(self, option: str):
        """Get an e2fsck option."""
        return getattr(self.config, option, None)

    def _write_config(self) -> None:
        """Write e2fsck.conf file."""
        content = "# /etc/e2fsck.conf - ext2/3/4 filesystem check config\n"
        content += "# Managed by UmerOS\n\n[options]\n"
        content += f"journal_data_datetime_change = {'yes' if self.config.journal_data_datetime_change else 'no'}\n"
        content += f"journal_async_commit = {'yes' if self.config.journal_async_commit else 'no'}\n\n"
        content += "[problems]\n"
        content += f"check_normal_dirs = {'yes' if self.config.check_normal_dirs else 'no'}\n"
        content += f"check_symlinks = {'yes' if self.config.check_symlinks else 'no'}\n"
        self.e2fsck_path.write_text(content, encoding='utf-8')
