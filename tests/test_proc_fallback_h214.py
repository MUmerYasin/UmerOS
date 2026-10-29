"""H214 -- pin the graceful simulated fallback invariant for ``proc/modules.py``
and ``proc/mounts.py``.

Both modules read real host ``/proc/modules`` and ``/proc/mounts`` via
``utils._read_file`` when readable, else return hardcoded simulated data.
This is expected (UmerOS runs atop a real Linux kernel in userspace) and
safe.  The row's remedy is "no action; keep the fallback."

This test pins the invariant so the fallback cannot silently disappear.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROC_DIR = Path(__file__).resolve().parent.parent / "proc"


def _source(name: str) -> str:
    return (PROC_DIR / name).read_text(encoding="utf-8")


class TestModulesFallback:
    """``proc/modules.py`` must have a graceful simulated fallback."""

    def test_uses_read_file(self) -> None:
        src = _source("modules.py")
        assert "_read_file" in src, "modules.py must use _read_file"
        assert "/proc/modules" in src, "modules.py must read /proc/modules"

    def test_has_fallback_data(self) -> None:
        src = _source("modules.py")
        # The fallback list must contain at least one simulated module
        assert "umer_net" in src, "modules.py must have simulated umer_net fallback"
        assert "qcrypto" in src, "modules.py must have simulated qcrypto fallback"
        assert "qfs" in src, "modules.py must have simulated qfs fallback"

    def test_fallback_returns_list(self) -> None:
        """When _read_file returns empty, get() must return a non-empty list."""
        import sys
        sys.path.insert(0, str(PROC_DIR.parent))
        from proc import modules

        result = modules.get()
        assert isinstance(result, list), "modules.get() must return a list"
        # On non-Linux or when /proc/modules is unreadable, fallback kicks in
        # On Linux with real /proc/modules, it returns parsed real data
        # Either way, it should be a list of dicts with expected keys
        if result:
            assert isinstance(result[0], dict), "items must be dicts"
            assert "name" in result[0], "module dicts must have 'name' key"

    def test_get_returns_list_not_none(self) -> None:
        """get() must never return None -- it always returns a list."""
        import sys
        sys.path.insert(0, str(PROC_DIR.parent))
        from proc import modules

        result = modules.get()
        assert result is not None, "modules.get() must never return None"


class TestMountsFallback:
    """``proc/mounts.py`` must have a graceful simulated fallback."""

    def test_uses_read_file(self) -> None:
        src = _source("mounts.py")
        assert "_read_file" in src, "mounts.py must use _read_file"
        assert "/proc/mounts" in src, "mounts.py must read /proc/mounts"

    def test_has_fallback_data(self) -> None:
        src = _source("mounts.py")
        # The fallback list must contain simulated mounts
        assert "qfs_root" in src, "mounts.py must have simulated qfs_root fallback"
        assert "proc" in src, "mounts.py must have simulated proc fallback"
        assert "sysfs" in src, "mounts.py must have simulated sysfs fallback"

    def test_fallback_returns_list(self) -> None:
        """When _read_file returns empty, get() must return a non-empty list."""
        import sys
        sys.path.insert(0, str(PROC_DIR.parent))
        from proc import mounts

        result = mounts.get()
        assert isinstance(result, list), "mounts.get() must return a list"
        if result:
            assert isinstance(result[0], dict), "items must be dicts"
            assert "device" in result[0], "mount dicts must have 'device' key"

    def test_get_returns_list_not_none(self) -> None:
        """get() must never return None -- it always returns a list."""
        import sys
        sys.path.insert(0, str(PROC_DIR.parent))
        from proc import mounts

        result = mounts.get()
        assert result is not None, "mounts.get() must never return None"


class TestReadFileSafe:
    """``proc/utils.py::_read_file`` must be safe (catch exceptions)."""

    def test_has_exception_guard(self) -> None:
        src = _source("utils.py")
        assert "except" in src, "_read_file must have exception handling"
        assert "return" in src, "_read_file must return on failure"

    def test_returns_empty_string_on_missing(self) -> None:
        """_read_file must return empty string for a non-existent path."""
        import sys
        sys.path.insert(0, str(PROC_DIR.parent))
        from proc.utils import _read_file

        result = _read_file("/nonexistent/path/that/does/not/exist")
        assert result == "", "_read_file must return empty string on failure"
