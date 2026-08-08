"""
UmerOS /etc/securetty Configuration Manager
Manages terminals allowed for root login.
"""

from pathlib import Path
from typing import List


class SecureTTYManager:
    """Manages /etc/securetty - root login terminal restrictions."""

    DEFAULT_TTYS = [
        "console", "tty1", "tty2", "tty3", "tty4", "tty5", "tty6",
        "pts/0", "pts/1", "pts/2", "pts/3",
    ]

    def __init__(self, securetty_path: str = "/etc/securetty"):
        self.securetty_path = Path(securetty_path)
        self.allowed_ttys: List[str] = list(self.DEFAULT_TTYS)
        self.enabled = True
        self._write_file()

    def allow_tty(self, tty: str) -> None:
        """Allow root login on a terminal."""
        if tty not in self.allowed_ttys:
            self.allowed_ttys.append(tty)
            self._write_file()

    def deny_tty(self, tty: str) -> bool:
        """Deny root login on a terminal."""
        if tty in self.allowed_ttys:
            self.allowed_ttys.remove(tty)
            self._write_file()
            return True
        return False

    def is_allowed(self, tty: str) -> bool:
        """Check if root login is allowed on a terminal."""
        if not self.enabled:
            return True
        return tty in self.allowed_ttys

    def enable_check(self) -> None:
        """Enable securetty checking."""
        self.enabled = True
        self._write_file()

    def disable_check(self) -> None:
        """Disable securetty checking (allow all)."""
        self.enabled = False
        self._write_file()

    def get_allowed(self) -> List[str]:
        """Get list of allowed terminals."""
        return list(self.allowed_ttys)

    def _write_file(self) -> None:
        """Write securetty file."""
        if not self.enabled:
            self.securetty_path.write_text(
                "# /etc/securetty - root login check disabled\n",
                encoding='utf-8'
            )
            return
        content = "# /etc/securetty - allowed terminals for root login\n"
        content += "# Managed by UmerOS\n\n"
        for tty in sorted(self.allowed_ttys):
            content += f"{tty}\n"
        self.securetty_path.write_text(content, encoding='utf-8')
