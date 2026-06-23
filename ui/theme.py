#!/usr/bin/env python3
"""
Umer OS Terminal Theme

Color codes and formatting constants for the Fluidic Shell.
Uses ANSI escape sequences for cross-platform terminal coloring.
"""


class Theme:
    """ANSI color constants for the Umer OS shell."""

    # Reset
    RESET = "\033[0m"

    # Regular colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bold
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    # Bright colors
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_RED = "\033[91m"

    # OS-specific
    PROMPT_COLOR = "\033[1;96m"     # Bold Cyan
    PATH_COLOR = "\033[1;93m"       # Bold Yellow
    ERROR_COLOR = "\033[1;91m"      # Bold Red
    SUCCESS_COLOR = "\033[1;92m"    # Bold Green
    SYSTEM_COLOR = "\033[1;35m"     # Bold Magenta
    HEADER_COLOR = "\033[1;36m"     # Bold Cyan

    @staticmethod
    def styled(text: str, color: str) -> str:
        return f"{color}{text}{Theme.RESET}"

    @staticmethod
    def banner() -> str:
        return f"""
{Theme.BRIGHT_CYAN}{Theme.BOLD}╔══════════════════════════════════════════════════════╗
║                                                      ║
║     ██╗   ██╗███╗   ███╗███████╗██████╗              ║
║     ██║   ██║████╗ ████║██╔════╝██╔══██╗             ║
║     ██║   ██║██╔████╔██║█████╗  ██████╔╝             ║
║     ██║   ██║██║╚██╔╝██║██╔══╝  ██╔══██╗             ║
║     ╚██████╔╝██║ ╚═╝ ██║███████╗██║  ██║             ║
║      ╚═════╝ ╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝             ║
║                                                      ║
║          Quantum-Hybrid Operating System v2.0         ║
║                                                      ║
╚══════════════════════════════════════════════════════╝{Theme.RESET}
"""
