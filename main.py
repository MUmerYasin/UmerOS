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

"""UmerOS entry point.

``boot.init.boot()`` fails closed unless it can collect explicit consent to the
liability waiver — interactively at a TTY, or via ``accept_eula=True``.  The
previous 17-line version of this module called ``boot()`` with no arguments, so
the flag was unreachable from the documented entry point::

    python main.py               # aborts: "non-interactive boot requires explicit consent"
    python main.py --accept-eula # was ignored (and previously, an immediate abort)

This module now parses the command line and forwards consent, which makes
``python main.py`` usable from CI, containers and service managers.

Usage::

    python main.py                        # interactive: prompts for "I AGREE"
    python main.py --accept-eula          # explicit non-interactive consent
    python main.py --accept-eula --exit-after-boot   # boot then exit (CI)
    python main.py --version
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from boot.init import boot  # re-exported: `umeros` console script uses main:main

# Kept in step with pyproject.toml / setup.py.
__version__ = "2.0.0"


def build_parser() -> argparse.ArgumentParser:
    """Return the ``main.py`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description=(
            "Boot UmerOS. Interactive runs prompt for the liability waiver; "
            "non-interactive runs require --accept-eula."
        ),
    )
    parser.add_argument(
        "--accept-eula",
        action="store_true",
        help=(
            "record explicit consent to the liability waiver and boot without "
            "prompting (required when stdin is not a TTY)"
        ),
    )
    parser.add_argument(
        "--exit-after-boot",
        action="store_true",
        help=(
            "shut down once boot completes instead of idling — use for CI and "
            "verification runs that need a deterministic exit"
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"UmerOS {__version__}",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Boot UmerOS.

    Args:
        argv: Argument vector without the program name; defaults to
            ``sys.argv[1:]``.

    Returns:
        Process exit status.  ``boot()`` exits the process itself when consent
        is refused (fail-closed), so a return here means the kernel ran and shut
        down cleanly.
    """
    args = build_parser().parse_args(argv)
    boot(accept_eula=args.accept_eula, exit_after_boot=args.exit_after_boot)
    return 0


if __name__ == "__main__":
    sys.exit(main())
