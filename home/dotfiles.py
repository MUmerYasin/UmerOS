"""
UmerOS Dotfiles Manager
Manages default dotfiles in ~/.bashrc, ~/.profile, ~/.xsession, etc.
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import shutil


@dataclass
class DotfileTemplate:
    """Default dotfile template."""
    name: str
    content: str
    executable: bool = False
    description: str = ""


class DotfilesManager:
    """Manages dotfile templates and installation."""

    TEMPLATES: Dict[str, DotfileTemplate] = {
        ".bashrc": DotfileTemplate(
            name=".bashrc",
            content="""# ~/.bashrc: executed by bash for non-login shells.

# If not running interactively, don't do anything
[[ $- != *i* ]] && return

# History settings
HISTSIZE=1000
HISTFILESIZE=2000
HISTCONTROL=ignoreboth

# Append to history, don't overwrite
shopt -s histappend

# Check window size after each command
shopt -s checkwinsize

# Enable color support of ls
alias ls='ls --color=auto'
alias ll='ls -la'
alias la='ls -A'
alias l='ls -CF'

# Alias definitions
if [ -f ~/.bash_aliases ]; then
    . ~/.bash_aliases
fi

# Enable programmable completion
if ! shopt -oq posix; then
  if [ -f /usr/share/bash-completion/bash_completion ]; then
    . /usr/share/bash-completion/bash_completion
  fi
fi

# Prompt
PS1='\\[\\033[01;32m\\]\\u@\\h\\[\\033[00m\\]:\\[\\033[01;34m\\]\\w\\[\\033[00m\\]\\$ '
""",
            description="Bash initialization for non-login shells",
        ),
        ".profile": DotfileTemplate(
            name=".profile",
            content="""# ~/.profile: executed by the command interpreter for login shells.

# Set default umask
umask 022

# Set PATH if it doesn't already exist
if [ -d "$HOME/bin" ] ; then
    PATH="$HOME/bin:$PATH"
fi

if [ -d "$HOME/.local/bin" ] ; then
    PATH="$HOME/.local/bin:$PATH"
fi

# Set MANPATH if it doesn't already exist
if [ -d "$HOME/man" ] && [ -z "$MANPATH" ]; then
    MANPATH="$HOME/man:$MANPATH"
fi

# Set XDG base directories
export XDG_DATA_HOME="$HOME/.local/share"
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_STATE_HOME="$HOME/.local/state"
export XDG_CACHE_HOME="$HOME/.cache"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
""",
            description="Login shell initialization",
        ),
        ".bash_profile": DotfileTemplate(
            name=".bash_profile",
            content="""# ~/.bash_profile: executed by bash for login shells.

# Source ~/.profile if it exists
if [ -f ~/.profile ]; then
    . ~/.profile
fi

# Source ~/.bashrc if it exists
if [ -f ~/.bashrc ]; then
    . ~/.bashrc
fi
""",
            description="Login shell profile",
        ),
        ".bash_logout": DotfileTemplate(
            name=".bash_logout",
            content="""# ~/.bash_logout: executed by bash when login shell exits.

# Clear terminal on logout
if [ "$SHLVL" = 1 ]; then
    [ -x /usr/bin/clear_console ] && /usr/bin/clear_console -q
fi
""",
            description="Login shell cleanup",
        ),
        ".xsession": DotfileTemplate(
            name=".xsession",
            content="""#!/bin/bash
# ~/.xsession: executed by X session manager.

# Source user profile
if [ -f ~/.profile ]; then
    . ~/.profile
fi

# Set DPI
xrdb -merge ~/.Xresources 2>/dev/null

# Start window manager
if command -v openbox &> /dev/null; then
    exec openbox
elif command -v fluxbox &> /dev/null; then
    exec fluxbox
elif command -v i3 &> /dev/null; then
    exec i3
else
    exec xterm
fi
""",
            description="X session startup script",
            executable=True,
        ),
        ".xinitrc": DotfileTemplate(
            name=".xinitrc",
            content="""#!/bin/bash
# ~/.xinitrc: executed by xinit.

# Source user profile
if [ -f ~/.profile ]; then
    . ~/.profile
fi

# Load X resources
[ -f ~/.Xresources ] && xrdb -merge ~/.Xresources

# Start window manager
if [ -f ~/.xsession ]; then
    exec ~/.xsession
fi

exec openbox
""",
            description="X initialization script",
            executable=True,
        ),
        ".Xresources": DotfileTemplate(
            name=".Xresources",
            content="""! ~/.Xresources: X resource settings.

! Cursor
XTerm*cursorColor: #ffffff
XTerm*cursorBlink: true

! Scrollbar
XTerm*-scrollbar: false

! Font
XTerm*font: xft:Mono:size=12
XTerm*boldFont: xft:Mono:bold:size=12

! Colors
XTerm*foreground: #d0d0d0
XTerm*background: #1a1a2e

! URxvt
URxvt.scrollBar: false
URxvt.font: xft:Mono:size=12
URxvt.foreground: #d0d0d0
URxvt.background: #1a1a2e
""",
            description="X resource database settings",
        ),
        ".inputrc": DotfileTemplate(
            name=".inputrc",
            content="""# ~/.inputrc: Readline configuration.

# Enable completion ignoring case
set completion-ignore-case on

# Show all matches if ambiguous
set show-all-if-ambiguous on

# Color completion by type
set colored-stats on

# Show type indicator
set visible-stats on

# Tab complete without listing if only one match
set menu-complete-display-prefix on

# Arrow keys for history search
"\\e[A": history-search-backward
"\\e[B": history-search-forward

# Enable 8-bit input/output
set input-meta on
set output-meta on
set convert-meta off
""",
            description="Readline configuration",
        ),
    }

    def __init__(self, home_path: str = "/home"):
        self.home_path = Path(home_path)

    def install_dotfiles(self, username: str, overwrite: bool = False) -> List[str]:
        """Install default dotfiles to a user's home directory."""
        user_home = self.home_path / username
        if not user_home.exists():
            user_home.mkdir(parents=True, exist_ok=True)

        installed = []
        for name, template in self.TEMPLATES.items():
            dest = user_home / name
            if dest.exists() and not overwrite:
                continue
            dest.write_text(template.content, encoding='utf-8')
            if template.executable:
                dest.chmod(0o755)
            else:
                dest.chmod(0o644)
            installed.append(name)
        return installed

    def get_template(self, name: str) -> Optional[DotfileTemplate]:
        """Get a dotfile template by name."""
        return self.TEMPLATES.get(name)

    def list_templates(self) -> List[str]:
        """List available dotfile templates."""
        return list(self.TEMPLATES.keys())

    def create_custom(self, username: str, filename: str, content: str) -> bool:
        """Create a custom dotfile for a user."""
        user_home = self.home_path / username
        if not user_home.exists():
            return False
        dest = user_home / filename
        dest.write_text(content, encoding='utf-8')
        dest.chmod(0o644)
        return True

    def remove_dotfile(self, username: str, filename: str) -> bool:
        """Remove a dotfile from a user's home."""
        user_home = self.home_path / username
        target = user_home / filename
        if target.exists() and target.is_file():
            target.unlink()
            return True
        return False
