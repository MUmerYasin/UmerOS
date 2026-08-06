"""
UmerOS /usr/games - Games Hierarchy
====================================
TLDP /usr: Once contained network games files. Rarely used now.
"""

from __future__ import annotations

from core.command import Command


class FortuneCommand(Command):
    """Display a random fortune/quote."""

    name = "fortune"
    description = "Display a random fortune cookie"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        import random
        fortunes = [
            "The best way to predict the future is to invent it.",
            "Code is like humor. When you have to explain it, it's bad.",
            "First, solve the problem. Then, write the code.",
            "Simplicity is the soul of efficiency.",
            "Talk is cheap. Show me the code. - Linus Torvalds",
            "Any sufficiently advanced technology is indistinguishable from magic.",
            "There are only two hard things in Computer Science: cache invalidation and naming things.",
            "It works on my machine.",
        ]
        return random.choice(fortunes) + "\n"


class CowsayCommand(Command):
    """Generate an ASCII art cow with a message."""

    name = "cowsay"
    description = "Generate an ASCII art cow with a message"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        msg = " ".join(args) if args else "Moo!"
        border = "-" * (len(msg) + 2)
        return (
            f" {border}\n"
            f"< {msg} >\n"
            f" {border}\n"
            f"        \\   ^__^\n"
            f"         \\  (oo)\\_______\n"
            f"            (__)\\       )\\/\\\n"
            f"                ||----w |\n"
            f"                ||     ||\n"
        )


class SlCommand(Command):
    """Steam Locomotive - a fun Easter egg."""

    name = "sl"
    description = "Steam Locomotive - fun Easter egg"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "   (@@) (  @(@)\n"
            "   /    o  @ ( (  /---)____\n"
            "  \\___/$$$|@L @@ / @@      )\n"
            "          \\    \\ @ __ /  @@\n"
            "           \\____\\(@  @)/   @@\n"
            "             (@  (@ /@@   @@\n"
            "                  @@  @  @@@\n"
            "                    @@@\n"
        )


class XeyesCommand(Command):
    """X11 eyes that follow the mouse."""

    name = "xeyes"
    description = "X11 eyes that follow the mouse cursor"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return "xeyes: X display not available in headless UmerOS\n"


class XclockCommand(Command):
    """X11 clock display."""

    name = "xclock"
    description = "X11 clock display"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return "xclock: X display not available in headless UmerOS\n"


class XtermCommand(Command):
    """X11 terminal emulator."""

    name = "xterm"
    description = "X11 terminal emulator"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return "xterm: X display not available in headless UmerOS\n"


class NcursesDemoCommand(Command):
    """ncurses terminal demo."""

    name = "ncurses-demo"
    description = "ncurses terminal display demo"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return "ncurses-demo: ncurses demo not available in UmerOS\n"
