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
UmerOS /etc C Shell & Z Shell Configuration
=============================================
Manages C shell (csh/tcsh) and Z shell (zsh) system-wide configuration.

FHS 3.0 entries:
  /etc/csh.cshrc     — C shell system-wide initialization
  /etc/csh.login     — C shell system-wide login script
  /etc/csh.logout    — C shell system-wide logout script
  /etc/zsh/zshenv    — Z shell environment variables
  /etc/zsh/zprofile  — Z shell system-wide profile
  /etc/zsh/zshrc     — Z shell system-wide configuration
  /etc/zsh/zlogin    — Z shell login script
  /etc/zsh/zlogout   — Z shell logout script

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Etc.CshZshConfig")


@dataclass
class ShellConfigEntry:
    """Represents a shell configuration entry."""
    shell: str
    filename: str
    content: str
    description: str = ""


class CshZshConfigManager:
    """
    Manages C shell and Z shell system-wide configuration.

    Handles /etc/csh.cshrc, /etc/csh.login, /etc/csh.logout,
    and /etc/zsh/* files.
    """

    def __init__(self, etc_path: str = "/etc") -> None:
        self.etc_path = Path(etc_path)
        self.zsh_path = self.etc_path / "zsh"

    def initialize(self) -> bool:
        """Create all C shell and Z shell configuration files with defaults."""
        try:
            self._create_csh_files()
            self._create_zsh_files()
            log.info("Initialized C shell and Z shell configuration files")
            return True
        except Exception as e:
            log.error("Failed to initialize C shell/Z shell config: %s", e)
            return False

    # ── C Shell Files ────────────────────────────────────────────────────

    def _create_csh_files(self) -> None:
        """Create C shell configuration files."""
        files = {
            "csh.cshrc": """# /etc/csh.cshrc - C shell system-wide initialization
# UmerOS C Shell Configuration
# This file is sourced by csh and tcsh at startup.

# Set default umask
umask 022

# Set default path
setenv PATH "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Set default editor
setenv EDITOR "vi"
setenv VISUAL "vi"

# Set locale defaults
if ($?LANG == 0) setenv LANG en_US.UTF-8
if ($?LC_ALL == 0) setenv LC_ALL en_US.UTF-8

# Set terminal type
if ($?TERM == 0) setenv TERM xterm

# History settings
set history = 1000
set savehist = 1000

# Prompt settings
set prompt = "%n@%m:%~%# "

# Aliases
alias ls "ls --color=auto"
alias ll "ls -la"
alias la "ls -a"
""",
            "csh.login": """# /etc/csh.login - C shell system-wide login script
# UmerOS C Shell Login
# This file is sourced by csh and tcsh at login.

# Execute profile.d scripts
if (-d /etc/profile.d) then
    foreach script (/etc/profile.d/*.sh)
        if (-r $script) then
            source $script
        endif
    end
endif

# Set MAIL path
if ($?MAIL == 0) setenv MAIL /var/mail/$USER

# Message of the day
if (-f /etc/motd) then
    cat /etc/motd
endif
""",
            "csh.logout": """# /etc/csh.logout - C shell system-wide logout script
# UmerOS C Shell Logout
# This file is sourced by csh and tcsh at logout.

# Clear terminal
clear

# Print logout message
echo "Goodbye $USER"
""",
        }

        for filename, content in files.items():
            filepath = self.etc_path / filename
            if not filepath.exists():
                filepath.write_text(content, encoding="utf-8")
                log.debug("Created /etc/%s", filename)

    # ── Z Shell Files ────────────────────────────────────────────────────

    def _create_zsh_files(self) -> None:
        """Create Z shell configuration files."""
        self.zsh_path.mkdir(parents=True, exist_ok=True)

        files = {
            "zshenv": """# /etc/zsh/zshenv - Z shell environment variables
# UmerOS Z Shell Environment
# This file is sourced by all Z shell invocations.

# Set default path
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Set default editor
export EDITOR="vi"
export VISUAL="vi"

# Set locale defaults
export LANG="en_US.UTF-8"
export LANGUAGE="en_US:en"
export LC_ALL="en_US.UTF-8"

# History settings
export HISTSIZE=10000
export SAVEHIST=10000

# ZSH configuration directory
export ZSH=/etc/zsh
""",
            "zprofile": """# /etc/zsh/zprofile - Z shell system-wide profile
# UmerOS Z Shell Profile
# This file is sourced by login shells.

# Source profile.d scripts
if [ -d /etc/profile.d ]; then
    for script in /etc/profile.d/*.sh; do
        if [ -r "$script" ]; then
            . "$script"
        fi
    done
fi

# Set MAIL path
if [ -z "$MAIL" ]; then
    export MAIL="/var/mail/$USER"
fi
""",
            "zshrc": """# /etc/zsh/zshrc - Z shell system-wide configuration
# UmerOS Z Shell RC
# This file is sourced by interactive shells.

# Enable colors
autoload -U colors && colors

# Prompt configuration
PROMPT="%{$fg[green]%}%n@%m%{$reset_color%}:%{$fg[blue]%}%~%{$reset_color%}%# "

# History configuration
HISTFILE=~/.zsh_history
HISTSIZE=10000
SAVEHIST=10000
setopt HIST_IGNORE_DUPS
setopt HIST_IGNORE_SPACE
setopt HIST_VERIFY

# Completion system
autoload -Uz compinit
compinit

# Completion colors
zstyle ':completion:*' menu select
zstyle ':completion:*' list-colors ${(s.:.)LS_COLORS}

# Key bindings
bindkey -e

# Aliases
alias ls="ls --color=auto"
alias ll="ls -la"
alias la="ls -a"
alias grep="grep --color=auto"
alias rm="rm -i"
alias cp="cp -i"
alias mv="mv -i"

# Functions
mkcd() { mkdir -p "$1" && cd "$1" }
extract() {
    if [ -f "$1" ]; then
        case "$1" in
            *.tar.bz2) tar xjf "$1" ;;
            *.tar.gz) tar xzf "$1" ;;
            *.tar.xz) tar xJf "$1" ;;
            *.bz2) bunzip2 "$1" ;;
            *.rar) unrar x "$1" ;;
            *.gz) gunzip "$1" ;;
            *.tar) tar xf "$1" ;;
            *.tbz2) tar xjf "$1" ;;
            *.tgz) tar xzf "$1" ;;
            *.zip) unzip "$1" ;;
            *.Z) uncompress "$1" ;;
            *.7z) 7z x "$1" ;;
            *) echo "'$1' cannot be extracted" ;;
        esac
    else
        echo "'$1' is not a valid file"
    fi
}
""",
            "zlogin": """# /etc/zsh/zlogin - Z shell login script
# UmerOS Z Shell Login
# This file is sourced after zshrc on login.

# Display message of the day
if [ -f /etc/motd ]; then
    cat /etc/motd
fi

# Display last login time
if [ -f /var/log/lastlog ]; then
    last -1 "$USER" 2>/dev/null
fi
""",
            "zlogout": """# /etc/zsh/zlogout - Z shell logout script
# UmerOS Z Shell Logout
# This file is sourced before the shell exits.

# Clear terminal
clear

# Print logout message
echo "Goodbye $USER"
""",
        }

        for filename, content in files.items():
            filepath = self.zsh_path / filename
            if not filepath.exists():
                filepath.write_text(content, encoding="utf-8")
                log.debug("Created /etc/zsh/%s", filename)

    # ── Utility Methods ──────────────────────────────────────────────────

    def get_all_configs(self) -> List[ShellConfigEntry]:
        """Get all shell configuration files."""
        entries = []

        # C shell files
        for name in ["csh.cshrc", "csh.login", "csh.logout"]:
            filepath = self.etc_path / name
            if filepath.exists():
                entries.append(ShellConfigEntry(
                    shell="csh",
                    filename=name,
                    content=filepath.read_text(encoding="utf-8"),
                    description=f"C shell {name.split('.')[1]} configuration",
                ))

        # Z shell files
        for name in ["zshenv", "zprofile", "zshrc", "zlogin", "zlogout"]:
            filepath = self.zsh_path / name
            if filepath.exists():
                entries.append(ShellConfigEntry(
                    shell="zsh",
                    filename=name,
                    content=filepath.read_text(encoding="utf-8"),
                    description=f"Z shell {name[3:]} configuration",
                ))

        return entries

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of C shell/Z shell configuration."""
        return {
            "csh_cshrc_exists": (self.etc_path / "csh.cshrc").exists(),
            "csh_login_exists": (self.etc_path / "csh.login").exists(),
            "csh_logout_exists": (self.etc_path / "csh.logout").exists(),
            "zsh_dir_exists": self.zsh_path.exists(),
            "zsh_files": [f.name for f in self.zsh_path.glob("z*")] if self.zsh_path.exists() else [],
        }
