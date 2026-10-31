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
UmerOS — dependency installer
=============================
Installs the repository's Python dependencies, preferring the hash-pinned lock
when one exists.

``requirements.txt`` is a *range* spec by policy (H15): it declares bounded
``>=MIN,<MAX`` versions so a fresh install cannot silently pull a breaking
major.  That is reproducible in the "same major" sense but **not**
integrity-verified — anything able to edit the file, or to compromise the index
it resolves against, gets arbitrary code installed as the invoking user.  The
repository's own documented hardening path is a generated lock::

    pip-compile --generate-hashes --output-file=requirements.lock requirements.txt
    pip install -r requirements.lock

This script follows that policy instead of inventing a second one:

* when ``requirements.lock`` exists it is installed **with ``--require-hashes``**,
  so every wheel must match a recorded hash before it is unpacked;
* otherwise ``requirements.txt`` is installed and a notice says the install is
  not integrity-verified, naming the command that would make it so;
* ``--require-hashes`` forces the strict path and fails when no lock exists, so
  a hardened CI job can refuse the loose file outright.

Output is **inherited, never captured**.  An install log can run to megabytes
and ``capture_output=True`` holds all of it in memory before anything is shown,
so a long install looks hung.  ``--dry-run`` prints the exact pip command.

Paths resolve against the repository root, not the process working directory:
running the script from elsewhere used to pick up whatever ``requirements.txt``
happened to sit in the cwd, or none at all.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional

PROJ = Path(__file__).resolve().parent.parent

REQ_NAME = "requirements.txt"
LOCK_NAME = "requirements.lock"

HASH_MARKER = "--hash="


class SetupError(RuntimeError):
    """Raised when there is nothing sensible to install."""


def resolve_requirements(explicit: Optional[str] = None,
                         root: Optional[Path] = None) -> Path:
    """Return the requirements file to install from.

    An explicit path wins.  Otherwise the hash-pinned lock is preferred when it
    exists, then the range spec.  Relative paths are resolved against ``root``,
    never the caller's working directory.
    """
    root = PROJ if root is None else Path(root)
    if explicit:
        candidate = Path(explicit)
        if not candidate.is_absolute():
            candidate = root / candidate
        if not candidate.is_file():
            raise SetupError(f"requirements file not found: {candidate}")
        return candidate

    for name in (LOCK_NAME, REQ_NAME):
        candidate = root / name
        if candidate.is_file():
            return candidate
    raise SetupError(f"neither {LOCK_NAME} nor {REQ_NAME} exists in {root}")


def is_hash_pinned(path: Path) -> bool:
    """True when ``path`` records hashes, so ``--require-hashes`` is meaningful.

    pip needs *every* requirement to carry a hash, so a single ``--hash=`` is
    not proof — but a file with none at all certainly cannot be verified, which
    is the case this guard exists to catch.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SetupError(f"cannot read {path}: {exc}") from exc
    return HASH_MARKER in text


def build_pip_argv(requirements: Path, *, require_hashes: bool) -> list[str]:
    """Assemble the pip command line (argv list — never a shell string)."""
    argv = [
        sys.executable, "-m", "pip", "install",
        "--no-input",                    # never block on a prompt
        "--disable-pip-version-check",   # no network call just to nag
    ]
    if require_hashes:
        argv.append("--require-hashes")
    argv.extend(["-r", str(requirements)])
    return argv


def main(argv: Optional[list] = None, *, stream=None) -> int:
    """Return 0 on success, pip's exit code on failure, 2 on a setup problem."""
    parser = argparse.ArgumentParser(
        prog="install_deps.py",
        description="Install UmerOS Python dependencies (prefers requirements.lock).",
    )
    parser.add_argument(
        "-r", "--requirements", default=None, metavar="FILE",
        help=f"explicit requirements file (default: {LOCK_NAME} if present, else {REQ_NAME})",
    )
    parser.add_argument(
        "--require-hashes", action="store_true",
        help="refuse to install unless every requirement is hash-pinned",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="print the pip command instead of running it",
    )
    args = parser.parse_args(argv)

    try:
        requirements = resolve_requirements(args.requirements)
        pinned = is_hash_pinned(requirements)
    except SetupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.require_hashes and not pinned:
        print(
            f"error: --require-hashes was given but {requirements.name} records no "
            f"hashes. Generate one with: pip-compile --generate-hashes "
            f"--output-file={LOCK_NAME} {REQ_NAME}",
            file=sys.stderr,
        )
        return 2

    if not pinned:
        print(
            f"warning: installing from {requirements.name} without hash verification — "
            "an edited file or a compromised index would install arbitrary code. "
            f"For a verified install: pip-compile --generate-hashes "
            f"--output-file={LOCK_NAME} {REQ_NAME}",
            file=sys.stderr,
        )

    pip_argv = build_pip_argv(requirements, require_hashes=pinned or args.require_hashes)
    print(
        f"installing from {requirements.name}"
        + (" (hash-verified)" if pinned else " (unverified)")
    )

    if args.dry_run:
        print("would run:", " ".join(pip_argv))
        return 0

    # Inherit stdout/stderr: streaming, not buffering. No capture_output.
    result = subprocess.run(pip_argv, stdout=stream, stderr=stream)
    if result.returncode != 0:
        print(f"error: pip exited with {result.returncode}", file=sys.stderr)
        return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
