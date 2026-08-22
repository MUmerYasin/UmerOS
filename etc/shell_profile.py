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
UmerOS /etc Shell Profile Configuration
=========================================
Manages shell initialization profiles and completion scripts.

FHS 3.0 entries:
  /etc/profile      — System-wide shell profile
  /etc/profile.d/   — System-wide shell profile snippets
  /etc/bash_completion  — Bash completion scripts
  /etc/inputrc      — Readline input configuration

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Etc.ShellProfile")


@dataclass
class ProfileEntry:
    """Represents a shell profile configuration entry."""
    key: str
    value: str
    description: str = ""


class ShellProfileManager:
    """
    Manages shell initialization profiles and completion scripts.

    Handles /etc/profile, /etc/profile.d/, /etc/bash_completion, and /etc/inputrc.
    """

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.profile_d_path = self.etc_path / "profile.d"

    def initialize(self) -> bool:
        """Create all shell profile files with defaults."""
        try:
            self._create_profile()
            self._create_profile_d_scripts()
            self._create_bash_completion()
            self._create_inputrc()
            log.info("Initialized shell profile files")
            return True
        except Exception as e:
            log.error("Failed to initialize shell profile files: %s", e)
            return False

    # ── /etc/profile ─────────────────────────────────────────────────────

    def _create_profile(self) -> None:
        """Create /etc/profile (system-wide shell profile)."""
        filepath = self.etc_path / "profile"
        if filepath.exists():
            return
        content = """# /etc/profile - System-wide shell profile
# UmerOS System Profile
# This file is sourced by login shells on startup.

# Set default PATH
PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PATH

# Set default umask
umask 022

# Set system-wide environment variables
HOSTNAME=$(hostname 2>/dev/null || echo "umeros")
export HOSTNAME

# Set default editor
export EDITOR="vi"
export VISUAL="vi"

# Set locale defaults
if [ -f /etc/locale_timezone ]; then
    . /etc/locale_timezone
fi

# Source profile.d scripts
if [ -d /etc/profile.d ]; then
    for script in /etc/profile.d/*.sh; do
        if [ -r "$script" ]; then
            . "$script"
        fi
    done
fi

# Set PATH for local installations
if [ -d /usr/local/bin ]; then
    PATH="/usr/local/bin:$PATH"
fi

# Set PATH for user-specific binaries
if [ -d "$HOME/.local/bin" ]; then
    PATH="$HOME/.local/bin:$PATH"
fi

# Source bash completion if available
if [ -f /etc/bash_completion ]; then
    . /etc/bash_completion
fi

# Set terminal title
case "$TERM" in
xterm*|rxvt*)
    PS1="\\[\\033]0;${USER}@${HOSTNAME}: ${PWD}\\007\\]$PS1"
    ;;
esac
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/profile")

    # ── /etc/profile.d/ ──────────────────────────────────────────────────

    def _create_profile_d_scripts(self) -> None:
        """Create /etc/profile.d/ directory with common scripts."""
        self.profile_d_path.mkdir(parents=True, exist_ok=True)

        scripts = {
            "bash_completion.sh": """# /etc/profile.d/bash_completion.sh
# Enable bash completion

if [ -f /etc/bash_completion ] && ! shopt -oq posix; then
    . /etc/bash_completion
fi
""",
            "color_prompt.sh": """# /etc/profile.d/color_prompt.sh
# Colorful prompt configuration

if [ "$TERM" = "xterm-256color" ]; then
    PS1='\\[\\033[01;32m\\]\\u@\\h\\[\\033[00m\\]:\\[\\033[01;34m\\]\\w\\[\\033[00m\\]\\$ '
else
    PS1='\\u@\\h:\\w\\$ '
fi
""",
            "path.sh": """# /etc/profile.d/path.sh
# PATH configuration

# Add /usr/local/sbin to PATH
if ! echo "$PATH" | grep -q "/usr/local/sbin"; then
    PATH="/usr/local/sbin:$PATH"
fi

# Add /usr/local/bin to PATH
if ! echo "$PATH" | grep -q "/usr/local/bin"; then
    PATH="/usr/local/bin:$PATH"
fi
""",
            "lang.sh": """# /etc/profile.d/lang.sh
# Language and locale configuration

# Set default language
export LANG="en_US.UTF-8"
export LANGUAGE="en_US:en"
export LC_ALL="en_US.UTF-8"
""",
        }

        for filename, content in scripts.items():
            filepath = self.profile_d_path / filename
            if not filepath.exists():
                filepath.write_text(content, encoding="utf-8")
                log.debug("Created /etc/profile.d/%s", filename)

    # ── /etc/bash_completion ─────────────────────────────────────────────

    def _create_bash_completion(self) -> None:
        """Create /etc/bash_completion (Bash completion scripts)."""
        filepath = self.etc_path / "bash_completion"
        if filepath.exists():
            return
        content = """# /etc/bash_completion - Bash completion scripts
# UmerOS Bash Completion
# This file is sourced by bash for command-line completion.

# Enable programmable completion features
if ! shopt -oq posix; then
    if [ -f /usr/share/bash-completion/bash_completion ]; then
        . /usr/share/bash-completion/bash_completion
    elif [ -f /etc/bash_completion ]; then
        . /etc/bash_completion
    fi
fi

# Custom completion functions
_complete_umeros_commands() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Complete with commands from /usr/bin
    if [[ ${cur} == -* ]]; then
        COMPREPLY=( $(compgen -W "--help --version --verbose" -- ${cur}) )
        return 0
    fi

    COMPREPLY=( $(compgen -f -- ${cur}) )
    return 0
}

# Register completions
complete -F _complete_umeros_commands ls cat rm mv cp
"""
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/bash_completion")

    # ── /etc/inputrc ─────────────────────────────────────────────────────

    def _create_inputrc(self) -> None:
        """Create /etc/inputrc (Readline input configuration)."""
        filepath = self.etc_path / "inputrc"
        if filepath.exists():
            return
        content = "# /etc/inputrc - Readline input configuration\n# UmerOS Input Configuration\n# See inputrc(5) for details.\n\n# Enable 8-bit output/input\nset input-meta on\nset output-meta on\nset convert-meta off\n\n# Show partial completions immediately\nset show-all-if-ambiguous on\n\n# Display completions in a column if there are too many\nset colored-stats on\n\n# Enable colors for completion\nset colored-stats on\n\n# Case-insensitive completion\nset completion-ignore-case on\n\n# Show common prefix first, then sort\nset completion-map-case on\n\n# Don't ring the bell\nset bell-style none\n\n# Use vi mode if EDITOR is vi\n# set editing-mode vi\n\n# Arrow keys for history search\n\"\\e[A\": history-search-backward\n\"\\e[B\": history-search-forward\n\n# Home and End keys\n\"\\e[H\": beginning-of-line\n\"\\e[F\": end-of-line\n\n# Delete key\n\"\\e[3~\": delete-char\n\n# Ctrl-Left/Right for word movement\n\"\\eOC\": forward-word\n\"\\eOD\": backward-word\n"
        filepath.write_text(content, encoding="utf-8")
        log.debug("Created /etc/inputrc")

    # ── Utility Methods ──────────────────────────────────────────────────

    def parse_profile(self) -> List[ProfileEntry]:
        """Parse /etc/profile into a list of entries."""
        filepath = self.etc_path / "profile"
        if not filepath.exists():
            return []
        entries = []
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "export" in line:
                parts = line.split("export", 1)
                if len(parts) == 2:
                    var = parts[1].strip()
                    if "=" in var:
                        key, value = var.split("=", 1)
                        entries.append(ProfileEntry(key=key.strip(), value=value.strip()))
        return entries

    def list_profile_d_scripts(self) -> List[str]:
        """List scripts in /etc/profile.d/."""
        if not self.profile_d_path.exists():
            return []
        return [f.name for f in self.profile_d_path.glob("*.sh") if f.is_file()]

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of shell profile configuration."""
        return {
            "profile_exists": (self.etc_path / "profile").exists(),
            "profile_d_exists": self.profile_d_path.exists(),
            "profile_d_scripts": self.list_profile_d_scripts(),
            "bash_completion_exists": (self.etc_path / "bash_completion").exists(),
            "inputrc_exists": (self.etc_path / "inputrc").exists(),
        }
