#!/usr/bin/env python3
"""
Runner for the Umer OS ``/root`` test suite.

Usage::

    python tests/run_root_tests.py
    python tests/run_root_tests.py TestRootHome
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "tests"))

import test_root  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    loader = unittest.TestLoader()
    if argv:
        names = [f"test_root.{arg}" for arg in argv]
        suite = loader.loadTestsFromNames(names)
    else:
        suite = loader.loadTestsFromModule(test_root)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
