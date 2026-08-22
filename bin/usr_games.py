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
    """X11 eyes that follow the mouse (ASCII art fallback)."""

    name = "xeyes"
    description = "X11 eyes that follow the mouse cursor"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        if args and args[0] in ("-version", "--version", "-v"):
            return "xeyes 1.2.1 (UmerOS ASCII fallback)\n"
        eyes = r"""
    __________
   /          \
  |  .____.  .____.  |
  |  |    |  |    |  |
  |  '----'  '----'  |
  |        __        |
  \________|________/
"""
        return "xeyes: displaying ASCII eyes (no X11 in headless UmerOS)\n" + eyes


class XclockCommand(Command):
    """X11 clock display (ASCII art fallback)."""

    name = "xclock"
    description = "X11 clock display"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        if args and args[0] in ("-version", "--version", "-v"):
            return "xclock 1.1.1 (UmerOS ASCII fallback)\n"
        from datetime import datetime
        now = datetime.now()
        h, m = now.hour % 12, now.minute
        clock_art = f"""
         _______
        /       \\
       /  {h:2d}:{m:2d}   \\
      |         |
      |    |    |
       \\       /
        \\_____/
"""
        return "xclock: displaying ASCII clock (no X11 in headless UmerOS)\n" + clock_art


class XtermCommand(Command):
    """X11 terminal emulator (stub)."""

    name = "xterm"
    description = "X11 terminal emulator"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        if args and args[0] in ("-version", "--version", "-v"):
            return "xterm 388 (UmerOS stub)\n"
        return "xterm: X display not available in headless UmerOS\n"


class NcursesDemoCommand(Command):
    """ncurses terminal demo (ASCII widget showcase)."""

    name = "ncurses-demo"
    description = "ncurses terminal display demo"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        if args and args[0] in ("-version", "--version", "-v"):
            return "ncurses-demo 6.4 (UmerOS ASCII demo)\n"
        demo = (
            "+--- ncurses Widget Demo ---+\n"
            "| Progress: [=========>    ] 75%\n"
            "| Status:   RUNNING           \n"
            "| Items:                     \n"
            "|   [*] Item 1 (selected)    \n"
            "|   [ ] Item 2               \n"
            "|   [*] Item 3 (selected)    \n"
            "|   [ ] Item 4               \n"
            "| Slider:  [=====>          ] \n"
            "| Input:   [Hello World    ] \n"
            "+----------------------------+\n"
        )
        return "ncurses-demo: ASCII widget demo (no ncurses in headless UmerOS)\n" + demo
