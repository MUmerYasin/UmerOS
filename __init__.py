# UmerOS — top-level package marker
# =================================
# GPL-3.0 — see LICENSE and README for details.
#
# This file exists to make the repository root a Python package
# (so ``import umeros`` or any absolute cross-package import works
# in the test suite) but it does **not** itself import any
# sub-package.  Importing the root package is intentionally cheap
# and side-effect free.
#
# The application entry point lives in ``main.py`` at the repo
# root; individual subsystems are imported as their own packages
# (e.g. ``import boot``, ``import initrd``, ``import quantum``).
#
# Author: UmerOS Project
# License: GPL-3.0 (GNU General Public License Version 3)
"""UmerOS — a Python-based hybrid classical + quantum OS simulation."""

from __future__ import annotations

__version__ = "2.0.0"
__author__ = "UmerOS Development Team"
__all__: list[str] = []
