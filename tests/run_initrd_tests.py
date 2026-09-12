#!/usr/bin/env python3
"""
DEPRECATED subset-runner shim — UmerOS H16.

pytest is the canonical test runner for the whole project (see
``pyproject.toml`` ``[tool.pytest.ini_options]`` and
``.github/workflows/ci.yml``). These legacy ``unittest`` subset runners only
exercised a couple of modules and gave a false "green" signal.

Run the full suite with::

    pytest tests/

This script now delegates to that canonical command so there is a single
framework and a single source of truth for "is the suite green?".
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    cmd = [sys.executable, "-m", "pytest", str(_ROOT / "tests"), *sys.argv[1:]]
    return subprocess.run(cmd, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
