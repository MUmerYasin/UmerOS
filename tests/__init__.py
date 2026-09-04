# UmerOS /tests — Test-suite package marker
# ==========================================
# GPL-3.0 — see LICENSE and README for details.
#
# This file is intentionally a minimal package marker.  Individual
# tests live in sibling files (``test_*.py``) and ``run_*_tests.py``
# drivers; the test runner discovers them via ``unittest`` /
# explicit invocation, not via package import.
#
# The presence of an empty / minimal ``__init__.py`` lets editors and
# IDEs treat ``tests`` as a Python package and provides a single place
# to add shared fixtures, a custom ``TestCase`` base class, or a
# coverage helper should they be needed in the future.
#
# Author: UmerOS Project
# License: GPL-3.0 (GNU General Public License Version 3)
"""
UmerOS /tests — Test-suite package marker.

The individual ``test_*.py`` files contain the actual test cases;
this package marker exists only so that ``import tests`` is a no-op
rather than an error.
"""

from __future__ import annotations

__version__ = "1.0.0"
__all__: list[str] = []

# Intentionally empty.  See module docstring.
