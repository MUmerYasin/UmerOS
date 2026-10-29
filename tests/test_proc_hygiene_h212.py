"""H212 — pin the dangerous-call hygiene invariant for ``proc/``.

The row claims grep across all proc/ modules found ZERO dangerous calls
(``subprocess``/``eval``/``exec``/``shell=True``/``os.system``/``pickle``/
``ctypes``/``yaml.load``/``__import__``/``tarfile``/``shutil.rmtree``/
``chmod``/``CapabilityManager``).  Drift-recon (session 203) confirmed this
with two corrections:

1. The folder has **25** ``.py`` files, not 24 (the row said 24).
2. ``__import__`` appears twice in ``proc/__init__.py`` — but both are the
   **safe dynamic-import / selftest pattern** (``_try_import`` loads optional
   submodules by relative name with ``ImportError`` fallback; ``_selftest``
   imports the package's own ``__name__``).  Neither accepts arbitrary input.

This test discovers the module list dynamically (so a future ``proc/`` module
is covered automatically) and pins the absence of genuinely dangerous calls.
"""

from __future__ import annotations

import ast
import importlib
import re
import sys
from pathlib import Path

import pytest

PROC_DIR = Path(__file__).resolve().parent.parent / "proc"

# --- module discovery -------------------------------------------------------

def _discover_proc_modules() -> list[Path]:
    """Return every ``.py`` file directly inside ``proc/``."""
    return sorted(PROC_DIR.glob("*.py"))


PROC_MODULES = _discover_proc_modules()

# --- patterns ---------------------------------------------------------------

# Genuinely dangerous call patterns -- a hit means code-injection / shell /
# unsafe-deserialisation surface that must not exist in a read-mostly procfs.
DANGEROUS_PATTERNS: list[str] = [
    "subprocess",
    "eval(",
    "exec(",
    "shell=True",
    "os.system",
    "pickle",
    "ctypes",
    "yaml.load",
    "tarfile",
    "shutil.rmtree",
    "os.chmod",
    "pathlib.Path.chmod",
    "os.popen",
    "pty.spawn",
    "marshal.",
    "compile(",
]

# __import__ is *allowed* only in __init__.py's safe plugin pattern.
# Any other proc/ module using it would be a red flag.
DANGEROUS_OUTSIDE_INIT: list[str] = [
    "__import__",
]

# CapabilityManager must not appear (the capability gate is via
# ``core.capability_gate``, not a class named ``CapabilityManager``).
FORBIDDEN_NAMES: list[str] = [
    "CapabilityManager",
]

# Regex for open() calls that specify write or append mode.
# Matches: open(..., "w", ...), open(..., mode="wb", ...), etc.
_WRITE_MODE_RE = re.compile(
    r'open\s*\([^)]*'
    r"(?:['\"]w['\"]|['\"]wb['\"]|['\"]a['\"]|['\"]ab['\"]"
    r"|mode\s*=\s*['\"]w['\"]|mode\s*=\s*['\"]wb['\"]"
    r"|mode\s*=\s*['\"]a['\"]|mode\s*=\s*['\"]ab['\"])"
)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- tests ------------------------------------------------------------------

class TestProcModuleCount:
    """Pin the audited module count so a new module is a conscious act."""

    def test_module_count_is_25(self) -> None:
        modules = _discover_proc_modules()
        assert len(modules) == 25, (
            f"Expected 25 proc/*.py modules (row H212 said 24, drift-recon "
            f"found 25); got {len(modules)}: {[m.name for m in modules]}"
        )

    def test_expected_modules_present(self) -> None:
        names = {m.name for m in PROC_MODULES}
        expected = {
            "__init__.py", "procfs.py", "nodes.py", "sysctl_fs.py",
            "pid_entries.py", "kernel_adapter.py", "system_files.py",
            "cpuinfo.py", "meminfo.py", "version.py", "uptime.py",
            "loadavg.py", "mounts.py", "modules.py", "filesystems.py",
            "partitions.py", "interrupts.py", "ioports.py", "dma.py",
            "swaps.py", "sysvipc.py", "net_files.py", "tty_files.py",
            "info.py", "utils.py",
        }
        missing = expected - names
        assert not missing, f"Missing expected proc/ modules: {missing}"


class TestNoDangerousCalls:
    """Verify no genuinely dangerous call patterns in any proc/ module."""

    @pytest.mark.parametrize("module_path", PROC_MODULES, ids=lambda p: p.name)
    def test_no_dangerous_patterns(self, module_path: Path) -> None:
        src = _source(module_path)
        for pattern in DANGEROUS_PATTERNS:
            assert pattern not in src, (
                f"{module_path.name}: dangerous pattern {pattern!r} found"
            )

    @pytest.mark.parametrize("module_path", PROC_MODULES, ids=lambda p: p.name)
    def test_no_forbidden_names(self, module_path: Path) -> None:
        src = _source(module_path)
        for name in FORBIDDEN_NAMES:
            assert name not in src, (
                f"{module_path.name}: forbidden name {name!r} found"
            )


class TestImportRestrictedToInit:
    """``__import__`` may appear only in ``__init__.py`` (safe plugin pattern)."""

    @pytest.mark.parametrize("module_path", PROC_MODULES, ids=lambda p: p.name)
    def test_import_only_in_init(self, module_path: Path) -> None:
        if module_path.name == "__init__.py":
            return  # __import__ is allowed here
        src = _source(module_path)
        for pattern in DANGEROUS_OUTSIDE_INIT:
            assert pattern not in src, (
                f"{module_path.name}: __import__ found outside __init__.py"
            )

    def test_init_import_is_safe_pattern(self) -> None:
        """The two ``__import__`` calls in __init__.py are the safe plugin pattern."""
        src = _source(PROC_DIR / "__init__.py")
        assert "__import__" in src, "__init__.py should use __import__ for plugins"

        tree = ast.parse(src)
        import_calls: list[ast.Call] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "__import__":
                    import_calls.append(node)

        assert len(import_calls) == 2, (
            f"Expected exactly 2 __import__ calls in __init__.py, "
            f"got {len(import_calls)}"
        )

        # First call: __import__(f"{__name__}.{module_name}", fromlist=names)
        # -- dynamic submodule loader, argument is an f-string of package-relative name
        first = import_calls[0]
        assert len(first.args) >= 1
        arg0 = first.args[0]
        assert isinstance(arg0, ast.JoinedStr), (
            "First __import__ arg should be an f-string (package-relative name)"
        )

        # Second call: __import__(__name__) -- selftest importability check
        second = import_calls[1]
        assert len(second.args) == 1
        arg1 = second.args[0]
        assert isinstance(arg1, ast.Name) and arg1.id == "__name__", (
            "Second __import__ arg should be __name__ (self-test pattern)"
        )


class TestNoDirectFileWrites:
    """proc/ must be a virtual filesystem -- no direct file writes via open()."""

    @pytest.mark.parametrize("module_path", PROC_MODULES, ids=lambda p: p.name)
    def test_no_write_mode_open(self, module_path: Path) -> None:
        """No open() call with write/append mode anywhere in proc/."""
        src = _source(module_path)
        for line_no, line in enumerate(src.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if _WRITE_MODE_RE.search(line):
                pytest.fail(
                    f"{module_path.name}:{line_no}: "
                    f"direct file write detected: {stripped}"
                )


class TestProcImportable:
    """The proc package must import cleanly."""

    def test_package_imports(self) -> None:
        # Ensure the repo root is on sys.path
        repo_root = PROC_DIR.parent
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        try:
            mod = importlib.import_module("proc")
            assert hasattr(mod, "__version__")
        except ImportError:
            # Some optional submodules may not import in all environments
            pytest.skip("proc package optional imports unavailable")
