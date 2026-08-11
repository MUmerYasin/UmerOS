#!/usr/bin/env python3
"""
Runner for the Umer OS ``initrd`` test suite.

The project uses plain stdlib :mod:`unittest` so the tests work on any
Python 3.12+ install without depending on pytest (the bundled pytest
on this machine still imports the removed ``imp`` module).

Usage::

    python tests/run_initrd_tests.py               # run everything
    python tests/run_initrd_tests.py TestArchivers # one class
    python tests/run_initrd_tests.py TestBuilder.test_build_gz
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "tests"))

import test_initrd  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    loader = unittest.TestLoader()
    if argv:
        suite = loader.loadTestsFromNames(
            f"test_initrd.{name}" for name in argv
        )
    else:
        suite = loader.loadTestsFromModule(test_initrd)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
