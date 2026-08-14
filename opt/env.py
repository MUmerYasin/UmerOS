"""
UmerOS /opt — PATH and Environment Integration
=================================================

Manages ``$PATH``, ``$MANPATH``, and other environment variables to
include ``/opt`` package binaries and documentation.

Per TLDP §3.11, each ``/opt/<pkg>/bin`` directory should be included
in ``$PATH`` so that installed programs are directly executable.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("UmerOS.Opt.Env")

# ── Constants ──────────────────────────────────────────────────────────

OPT_ROOT = Path("/opt")

# Standard /opt subdirectories that contribute to environment paths
PATH_DIRS: tuple[str, ...] = ("bin", "sbin")
MANPATH_DIRS: tuple[str, ...] = ("man", "share/man")
INCLUDE_DIRS: tuple[str, ...] = ("include",)
LIB_DIRS: tuple[str, ...] = ("lib", "lib64")


# ── Manager ────────────────────────────────────────────────────────────

class OptEnvManager:
    """
    Manages environment variable integration for ``/opt`` packages.

    Generates the correct ``$PATH``, ``$MANPATH``, ``$LD_LIBRARY_PATH``,
    and ``$C_INCLUDE_PATH`` entries so that installed programs, man pages,
    headers, and libraries are discoverable.

    Parameters
    ----------
    opt_root : str | Path
        Override the /opt root (default ``/opt``).
    """

    def __init__(self, opt_root: str | Path = OPT_ROOT) -> None:
        self.root = Path(opt_root)

    def discover_bin_dirs(self) -> List[str]:
        """
        Find all ``/opt/<pkg>/bin`` and ``/opt/<pkg>/sbin`` directories.

        Returns
        -------
        list[str]
            Absolute paths to bin directories, sorted.
        """
        dirs: List[str] = []
        if not self.root.exists():
            return dirs

        for item in sorted(self.root.iterdir()):
            if not item.is_dir() or item.name.startswith("."):
                continue

            # Check for provider/package layout
            sub_dirs = [d for d in item.iterdir() if d.is_dir() and not d.name.startswith(".")]
            if sub_dirs and all(
                d.name in ("bin", "sbin", "lib", "man", "share", "include", "etc", "state", "info", "libexec")
                for d in sub_dirs
            ):
                # Direct package
                for subdir_name in PATH_DIRS:
                    d = item / subdir_name
                    if d.is_dir():
                        dirs.append(str(d))
            else:
                # Provider directory
                for sub in sub_dirs:
                    if sub.name.startswith("."):
                        continue
                    for subdir_name in PATH_DIRS:
                        d = sub / subdir_name
                        if d.is_dir():
                            dirs.append(str(d))

        return sorted(dirs)

    def discover_man_dirs(self) -> List[str]:
        """Find all ``/opt/<pkg>/man`` and ``/opt/<pkg>/share/man`` directories."""
        dirs: List[str] = []
        if not self.root.exists():
            return dirs

        for item in sorted(self.root.iterdir()):
            if not item.is_dir() or item.name.startswith("."):
                continue

            sub_dirs = [d for d in item.iterdir() if d.is_dir() and not d.name.startswith(".")]
            if sub_dirs and all(
                d.name in ("bin", "sbin", "lib", "man", "share", "include", "etc", "state", "info", "libexec")
                for d in sub_dirs
            ):
                for subdir_name in MANPATH_DIRS:
                    d = item / subdir_name
                    if d.is_dir():
                        dirs.append(str(d))
            else:
                for sub in sub_dirs:
                    if sub.name.startswith("."):
                        continue
                    for subdir_name in MANPATH_DIRS:
                        d = sub / subdir_name
                        if d.is_dir():
                            dirs.append(str(d))

        return sorted(dirs)

    def discover_lib_dirs(self) -> List[str]:
        """Find all ``/opt/<pkg>/lib`` directories."""
        dirs: List[str] = []
        if not self.root.exists():
            return dirs

        for item in sorted(self.root.iterdir()):
            if not item.is_dir() or item.name.startswith("."):
                continue

            sub_dirs = [d for d in item.iterdir() if d.is_dir() and not d.name.startswith(".")]
            if sub_dirs and all(
                d.name in ("bin", "sbin", "lib", "man", "share", "include", "etc", "state", "info", "libexec")
                for d in sub_dirs
            ):
                for subdir_name in LIB_DIRS:
                    d = item / subdir_name
                    if d.is_dir():
                        dirs.append(str(d))
            else:
                for sub in sub_dirs:
                    if sub.name.startswith("."):
                        continue
                    for subdir_name in LIB_DIRS:
                        d = sub / subdir_name
                        if d.is_dir():
                            dirs.append(str(d))

        return sorted(dirs)

    def discover_include_dirs(self) -> List[str]:
        """Find all ``/opt/<pkg>/include`` directories."""
        dirs: List[str] = []
        if not self.root.exists():
            return dirs

        for item in sorted(self.root.iterdir()):
            if not item.is_dir() or item.name.startswith("."):
                continue

            sub_dirs = [d for d in item.iterdir() if d.is_dir() and not d.name.startswith(".")]
            if sub_dirs and all(
                d.name in ("bin", "sbin", "lib", "man", "share", "include", "etc", "state", "info", "libexec")
                for d in sub_dirs
            ):
                for subdir_name in INCLUDE_DIRS:
                    d = item / subdir_name
                    if d.is_dir():
                        dirs.append(str(d))
            else:
                for sub in sub_dirs:
                    if sub.name.startswith("."):
                        continue
                    for subdir_name in INCLUDE_DIRS:
                        d = sub / subdir_name
                        if d.is_dir():
                            dirs.append(str(d))

        return sorted(dirs)

    # ── Shell profile generation ───────────────────────────────────────

    def generate_path_export(self) -> str:
        """
        Generate a shell snippet that prepends /opt/<pkg>/bin to $PATH.

        Returns
        -------
        str
            A POSIX-compatible shell snippet.
        """
        bin_dirs = self.discover_bin_dirs()
        if not bin_dirs:
            return ""

        lines = ["# /opt package PATH entries (auto-generated by UmerOS)"]
        paths = ":".join(d.replace("\\", "/") for d in bin_dirs)
        lines.append(f'export PATH="{paths}:$PATH"')
        return "\n".join(lines) + "\n"

    def generate_manpath_export(self) -> str:
        """
        Generate a shell snippet that adds /opt/<pkg>/man to $MANPATH.

        Returns
        -------
        str
            A POSIX-compatible shell snippet.
        """
        man_dirs = self.discover_man_dirs()
        if not man_dirs:
            return ""

        lines = ["# /opt package MANPATH entries (auto-generated by UmerOS)"]
        paths = ":".join(d.replace("\\", "/") for d in man_dirs)
        lines.append(f'export MANPATH="{paths}:$MANPATH"')
        return "\n".join(lines) + "\n"

    def generate_ld_library_path(self) -> str:
        """
        Generate a shell snippet that adds /opt/<pkg>/lib to $LD_LIBRARY_PATH.

        Returns
        -------
        str
            A POSIX-compatible shell snippet.
        """
        lib_dirs = self.discover_lib_dirs()
        if not lib_dirs:
            return ""

        lines = ["# /opt package LD_LIBRARY_PATH entries (auto-generated by UmerOS)"]
        paths = ":".join(d.replace("\\", "/") for d in lib_dirs)
        lines.append(f'export LD_LIBRARY_PATH="{paths}:$LD_LIBRARY_PATH"')
        return "\n".join(lines) + "\n"

    def generate_all_exports(self) -> str:
        """Generate a combined shell snippet for all /opt environment variables."""
        parts = [
            self.generate_path_export(),
            self.generate_manpath_export(),
            self.generate_ld_library_path(),
        ]
        return "\n".join(p for p in parts if p)

    # ── /etc/profile.d integration ─────────────────────────────────────

    def write_profile_d(self, profile_d: str | Path = "/etc/profile.d") -> bool:
        """
        Write a ``/etc/profile.d/opt-paths.sh`` file that sets up
        all /opt environment variables on login.

        Returns
        -------
        bool
            True if the file was written successfully.
        """
        snippet = self.generate_all_exports()
        if not snippet:
            log.info("No /opt packages found, skipping profile.d")
            return False

        dest = Path(profile_d) / "opt-paths.sh"
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(snippet, encoding="utf-8")
            log.info("Wrote /etc/profile.d/opt-paths.sh")
            return True
        except OSError as exc:
            log.error("Failed to write %s: %s", dest, exc)
            return False

    # ── Current environment ────────────────────────────────────────────

    @staticmethod
    def get_current_path() -> List[str]:
        """Return the current $PATH as a list of directories."""
        path_str = os.environ.get("PATH", "")
        return [p for p in path_str.split(os.pathsep) if p]

    @staticmethod
    def get_current_manpath() -> List[str]:
        """Return the current $MANPATH as a list of directories."""
        manpath = os.environ.get("MANPATH", "")
        if not manpath:
            # If MANPATH is unset, man uses its own default
            return []
        return [p for p in manpath.split(os.pathsep) if p]

    def check_path_coverage(self) -> Dict[str, Any]:
        """
        Check which /opt bin directories are already in $PATH.

        Returns
        -------
        dict
            with keys ``in_path`` and ``missing``.
        """
        current = set(self.get_current_path())
        needed = self.discover_bin_dirs()
        in_path = [d for d in needed if d in current]
        missing = [d for d in needed if d not in current]
        return {
            "in_path": in_path,
            "missing": missing,
            "all_covered": len(missing) == 0,
        }

    # ── Summary ────────────────────────────────────────────────────────

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of /opt environment integration state."""
        return {
            "opt_root": str(self.root),
            "bin_dirs": self.discover_bin_dirs(),
            "man_dirs": self.discover_man_dirs(),
            "lib_dirs": self.discover_lib_dirs(),
            "include_dirs": self.discover_include_dirs(),
            "path_coverage": self.check_path_coverage(),
        }


# ── Selftest ───────────────────────────────────────────────────────────

def _selftest() -> bool:
    """Run basic self-tests for OptEnvManager."""
    import tempfile

    print("[opt/env] selftest …")
    ok = True

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "opt"
        mgr = OptEnvManager(opt_root=root)

        # 1  empty root — nothing discovered
        assert mgr.discover_bin_dirs() == []
        assert mgr.discover_man_dirs() == []
        print("  [PASS] empty root -> empty discoveries")

        # 2  create a package with standard layout
        pkg = root / "firefox"
        (pkg / "bin").mkdir(parents=True)
        (pkg / "bin" / "firefox").write_text("#!", encoding="utf-8")
        (pkg / "sbin").mkdir()
        (pkg / "sbin" / "firefox-admin").write_text("#!", encoding="utf-8")
        (pkg / "lib").mkdir()
        (pkg / "lib" / "libff.so").write_bytes(b"\x00")
        (pkg / "man").mkdir()
        (pkg / "man" / "man1").mkdir(parents=True)
        (pkg / "man" / "man1" / "firefox.1").write_text(".TH FIREFOX", encoding="utf-8")
        (pkg / "include").mkdir()
        (pkg / "include" / "ff.h").write_text("#pragma once", encoding="utf-8")

        # 3  discover dirs
        bins = mgr.discover_bin_dirs()
        assert str(root / "firefox" / "bin") in bins
        assert str(root / "firefox" / "sbin") in bins
        print("  [PASS] discover_bin_dirs")

        mans = mgr.discover_man_dirs()
        assert str(root / "firefox" / "man") in mans
        print("  [PASS] discover_man_dirs")

        libs = mgr.discover_lib_dirs()
        assert str(root / "firefox" / "lib") in libs
        print("  [PASS] discover_lib_dirs")

        incs = mgr.discover_include_dirs()
        assert str(root / "firefox" / "include") in incs
        print("  [PASS] discover_include_dirs")

        # 4  generate exports
        path_export = mgr.generate_path_export()
        assert "firefox/bin" in path_export
        assert "export PATH=" in path_export
        print("  [PASS] generate_path_export")

        man_export = mgr.generate_manpath_export()
        assert "firefox/man" in man_export
        print("  [PASS] generate_manpath_export")

        ld_export = mgr.generate_ld_library_path()
        assert "firefox/lib" in ld_export
        print("  [PASS] generate_ld_library_path")

        all_export = mgr.generate_all_exports()
        assert "PATH=" in all_export
        assert "MANPATH=" in all_export
        assert "LD_LIBRARY_PATH=" in all_export
        print("  [PASS] generate_all_exports")

        # 5  provider layout
        prov = root / "mozilla" / "thunderbird"
        (prov / "bin").mkdir(parents=True)
        (prov / "bin" / "thunderbird").write_text("#!", encoding="utf-8")
        bins = mgr.discover_bin_dirs()
        assert str(root / "mozilla" / "thunderbird" / "bin") in bins
        print("  [PASS] provider layout discovered")

        # 6  write_profile_d
        prof_dir = Path(td) / "profile.d"
        assert mgr.write_profile_d(prof_dir)
        script = (prof_dir / "opt-paths.sh").read_text(encoding="utf-8")
        assert "firefox/bin" in script
        assert "thunderbird/bin" in script
        print("  [PASS] write_profile_d")

        # 7  check_path_coverage
        cov = mgr.check_path_coverage()
        assert "in_path" in cov
        assert "missing" in cov
        assert "all_covered" in cov
        print("  [PASS] check_path_coverage")

        # 8  summary
        s = mgr.get_summary()
        assert "bin_dirs" in s
        assert len(s["bin_dirs"]) >= 3
        print("  [PASS] get_summary")

    print("[opt/env] selftest PASSED")
    return ok


if __name__ == "__main__":
    _selftest()
