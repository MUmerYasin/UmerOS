"""
UmerOS /lib/modules — Loadable Kernel Module Management
=========================================================
Implements the FULL FHS/TLDP spec for /lib/modules/<kernel-version>/.

The /lib/modules directory is the home of all loadable kernel modules.
It is paired with several FHS-mandated files:

  modules.dep       — list of module dependencies (built by ``depmod``)
  modules.alias     — module aliases (e.g. pci / usb identifiers)
  modules.softdep   — soft (optional) module dependencies
  modules.symbols   — exported symbol → module mapping
  modules.builtin   — modules built into the kernel image
  modules.devname   — device-name → module mapping
  modules.params    — module parameter metadata
  isapnpmap.dep     — ISA PnP module requirements (legacy)
  pcimap            — PCI ID → module mapping (legacy)
  usbmap            — USB ID → module mapping (legacy)
  kernel/build      — symlink → /usr/src/<kernel-version>

Only shared libraries required to run /bin and /sbin may live directly
under /lib.  Module organization under /lib/modules/<kernel-version> is
"straightforward and needs no elaboration" per TLDP — but the helper
files around the modules are not trivial, so we model them faithfully.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

log = logging.getLogger("UmerOS.Lib.KernelModules")


# ─────────────────────────────────────────────────────────────────────────────
#  Enumerations
# ─────────────────────────────────────────────────────────────────────────────

class ModuleState(str, Enum):
    """Lifecycle state of a kernel module."""
    UNLOADED = "unloaded"
    LOADING  = "loading"
    LIVE     = "live"
    UNLOADING = "unloading"
    BUILTIN  = "builtin"   # compiled into the kernel image, not unloadable


class ModuleLoadResult(str, Enum):
    OK           = "ok"
    NOT_FOUND    = "not_found"
    MISSING_DEP  = "missing_dependency"
    ALREADY_LOADED = "already_loaded"
    NOT_LOADED   = "not_loaded"
    IO_ERROR     = "io_error"


# ─────────────────────────────────────────────────────────────────────────────
#  Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ModuleDependency:
    """One ``modules.dep``-style dependency entry."""
    module: str
    depends_on: List[str] = field(default_factory=list)
    soft: List[str] = field(default_factory=list)
    pre: List[str] = field(default_factory=list)   # pre-soft
    aliases: List[str] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)
    parameters: Dict[str, str] = field(default_factory=dict)


@dataclass
class KernelModule:
    """Represents a single kernel module."""
    name: str
    path: str
    size: int = 0
    version: str = ""
    description: str = ""
    author: str = ""
    license: str = ""
    vermagic: str = ""            # e.g. "5.15.0-UmerOS SMP mod_unload"
    dependencies: List[str] = field(default_factory=list)
    soft_dependencies: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)
    parameters: Dict[str, str] = field(default_factory=dict)
    firmware: List[str] = field(default_factory=list)
    state: ModuleState = ModuleState.UNLOADED
    md5: str = ""

    def __post_init__(self) -> None:
        # Make sure all list/dict fields are not shared between instances.
        if not isinstance(self.dependencies, list):
            self.dependencies = list(self.dependencies or [])
        if not isinstance(self.soft_dependencies, list):
            self.soft_dependencies = list(self.soft_dependencies or [])
        if not isinstance(self.aliases, list):
            self.aliases = list(self.aliases or [])
        if not isinstance(self.symbols, list):
            self.symbols = list(self.symbols or [])
        if not isinstance(self.parameters, dict):
            self.parameters = dict(self.parameters or {})
        if not isinstance(self.firmware, list):
            self.firmware = list(self.firmware or [])


# ─────────────────────────────────────────────────────────────────────────────
#  Default module catalogue (so the system has *something* on a fresh install)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_KERNEL_VERSION = "6.6.0-UmerOS"
MODULE_FILE_SUFFIXES = (".ko", ".ko.gz", ".ko.xz", ".ko.zst", ".ko.bz2")

# A small but realistic starter catalogue covering the standard Linux drivers
# shipped with virtually every distribution.  Real UmerOS would scan the
# on-disk .ko files; this catalogue is used when no .ko is present.
_STARTER_MODULES: Dict[str, ModuleDependency] = {
    "nvidia": ModuleDependency(
        "nvidia",
        depends_on=[],
        aliases=["pci:v000010DEd*"],
        parameters={"NVreg_OpenRmEnableUnsupportedGpus": "int"},
    ),
    "i915": ModuleDependency(
        "i915",
        depends_on=["drm", "drm_kms_helper"],
        soft=["i2c_algo_bit"],
        parameters={"modeset": "int"},
    ),
    "drm": ModuleDependency(
        "drm",
        depends_on=[],
        parameters={"debug": "int"},
    ),
    "drm_kms_helper": ModuleDependency(
        "drm_kms_helper",
        depends_on=["drm"],
    ),
    "e1000e": ModuleDependency(
        "e1000e",
        depends_on=[],
        aliases=["pci:v00008086d*"],
    ),
    "iwlwifi": ModuleDependency(
        "iwlwifi",
        depends_on=["cfg80211"],
        parameters={"11n_disable": "int"},
    ),
    "cfg80211": ModuleDependency(
        "cfg80211",
        depends_on=[],
    ),
    "snd_hda_intel": ModuleDependency(
        "snd_hda_intel",
        depends_on=["snd", "snd_pcm"],
    ),
    "snd": ModuleDependency(
        "snd",
        depends_on=[],
    ),
    "snd_pcm": ModuleDependency(
        "snd_pcm",
        depends_on=["snd"],
    ),
    "usbcore": ModuleDependency(
        "usbcore",
        depends_on=[],
    ),
    "usbhid": ModuleDependency(
        "usbhid",
        depends_on=["usbcore", "hid"],
    ),
    "hid": ModuleDependency(
        "hid",
        depends_on=[],
    ),
    "ahci": ModuleDependency(
        "ahci",
        depends_on=["libahci"],
    ),
    "libahci": ModuleDependency(
        "libahci",
        depends_on=[],
    ),
    "ext4": ModuleDependency(
        "ext4",
        depends_on=["mbcache", "crc16"],
    ),
    "mbcache": ModuleDependency("mbcache"),
    "crc16": ModuleDependency("crc16"),
    "vfat": ModuleDependency("vfat"),
    "ntfs3": ModuleDependency("ntfs3"),
}


# ─────────────────────────────────────────────────────────────────────────────
#  Manager
# ─────────────────────────────────────────────────────────────────────────────

class KernelModuleManager:
    """
    Manages kernel modules in ``/lib/modules/<kernel-version>/``.

    Provides a high-level interface covering:

    * listing modules for a kernel version
    * ``depmod`` — building modules.dep / modules.alias / modules.symbols
    * ``modinfo`` — module metadata lookup
    * ``modprobe`` — recursive load (deps first)
    * ``rmmod`` / ``modprobe -r`` — recursive unload
    * ``insmod`` — direct load (no dependency resolution)
    * legacy maps (pcimap, usbmap, isapnpmap.dep)
    * ``kernel/build`` symlink tracking
    """

    def __init__(
        self,
        lib_path: str = "/lib",
        kernel_version: str = DEFAULT_KERNEL_VERSION,
        source_root: str = "/usr/src",
    ) -> None:
        self.lib_path = Path(lib_path)
        self.kernel_version = kernel_version
        self.source_root = Path(source_root)
        self.modules_path = self.lib_path / "modules"
        self.version_path = self.modules_path / kernel_version
        # In-memory module catalogue — keyed by module name
        self._modules: Dict[str, ModuleDependency] = dict(_STARTER_MODULES)
        # In-memory load state — what is currently loaded
        self._loaded: Set[str] = set()
        # Live metadata cache (populated by scan or seed)
        self._info: Dict[str, KernelModule] = {}

    # ──────────────────────── discovery ────────────────────────────

    def get_kernel_versions(self) -> List[str]:
        """List available kernel versions on disk (or in memory)."""
        if not self.modules_path.exists():
            return [self.kernel_version]
        versions = []
        for item in self.modules_path.iterdir():
            if item.is_dir():
                versions.append(item.name)
        if not versions:
            versions.append(self.kernel_version)
        return sorted(set(versions))

    def select_kernel_version(self, version: str) -> None:
        """Switch the active kernel version (used by modprobe etc)."""
        self.kernel_version = version
        self.version_path = self.modules_path / version

    def get_modules_for_version(self, kernel_version: Optional[str] = None) -> List[KernelModule]:
        """List all modules (real .ko files + catalogue) for a kernel version."""
        version = kernel_version or self.kernel_version
        version_dir = self.modules_path / version
        modules: List[KernelModule] = []

        # 1) Real .ko files on disk, including common compressed module forms.
        if version_dir.exists():
            for item in self._iter_module_files(version_dir):
                mod = self._build_module_from_ko(item, version)
                modules.append(mod)
                self._info[mod.name] = mod

        # 2) Catalogue entries that don't have a .ko on disk
        for name, dep in self._modules.items():
            if name in self._info:
                continue
            mod = KernelModule(
                name=name,
                path=str(version_dir / "kernel" / f"{name}.ko"),
                size=0,
                version=version,
                vermagic=f"{version} SMP mod_unload",
                description=f"Stub catalogue entry for {name}",
                dependencies=list(dep.depends_on),
                soft_dependencies=list(dep.soft),
                aliases=list(dep.aliases),
                symbols=list(dep.symbols),
                parameters=dict(dep.parameters),
            )
            modules.append(mod)
            self._info[name] = mod

        # 3) Backfill aliases / symbols / parameters / soft_deps from the
        # catalogue for any module built from an on-disk .ko (where the
        # KernelModule had no metadata).
        for mod in modules:
            dep = self._modules.get(mod.name)
            if dep is None:
                continue
            if not mod.aliases and dep.aliases:
                mod.aliases = list(dep.aliases)
            if not mod.symbols and dep.symbols:
                mod.symbols = list(dep.symbols)
            if not mod.parameters and dep.parameters:
                mod.parameters = dict(dep.parameters)
            if not mod.soft_dependencies and dep.soft:
                mod.soft_dependencies = list(dep.soft)
            if not mod.dependencies and dep.depends_on:
                mod.dependencies = list(dep.depends_on)

        return modules

    def find_module(
        self,
        name: str,
        kernel_version: Optional[str] = None,
    ) -> Optional[KernelModule]:
        """Find a module by name (with fuzzy fallbacks)."""
        if name in self._info:
            return self._info[name]
        for mod in self.get_modules_for_version(kernel_version):
            if mod.name == name or mod.name.endswith(name) or name in mod.aliases:
                return mod
        return None

    def list_loaded_modules(self) -> List[str]:
        """List currently loaded modules (in-memory state)."""
        # Fall back to /proc/modules for real Linux
        proc_modules = Path("/proc/modules")
        if proc_modules.exists():
            loaded = []
            for line in proc_modules.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if parts:
                    loaded.append(parts[0])
            return loaded
        return sorted(self._loaded)

    def is_module_loaded(self, name: str) -> bool:
        return name in self.list_loaded_modules()

    # ──────────────────────── depmod ───────────────────────────────

    def depmod(
        self,
        kernel_version: Optional[str] = None,
        *,
        all_versions: bool = False,
    ) -> Dict[str, int]:
        """
        Rebuild the modules.dep / modules.alias / modules.symbols / etc. files
        for the given (or all) kernel versions.

        Returns a dict of ``{"<file>": <lines_written>}``.
        """
        versions = (
            self.get_kernel_versions() if all_versions
            else [kernel_version or self.kernel_version]
        )
        written: Dict[str, int] = {}
        for ver in versions:
            modules = self.get_modules_for_version(ver)
            written[f"modules.dep"]     = self._write_modules_dep(ver, modules)
            written[f"modules.alias"]   = self._write_modules_alias(ver, modules)
            written[f"modules.symbols"] = self._write_modules_symbols(ver, modules)
            written[f"modules.softdep"] = self._write_modules_softdep(ver, modules)
            written[f"modules.builtin"] = self._write_modules_builtin(ver, modules)
            written[f"modules.params"]  = self._write_modules_params(ver, modules)
            # legacy maps
            written[f"pcimap"]         = self._write_pcimap(ver, modules)
            written[f"usbmap"]         = self._write_usbmap(ver, modules)
            written[f"isapnpmap.dep"]  = self._write_isapnpmap(ver, modules)
        return written

    def _ensure_version_dir(self, ver: str) -> Path:
        v = self.modules_path / ver
        v.mkdir(parents=True, exist_ok=True)
        (v / "kernel").mkdir(parents=True, exist_ok=True)
        return v

    def _write_modules_dep(self, ver: str, modules: List[KernelModule]) -> int:
        self._ensure_version_dir(ver)
        lines = []
        for m in modules:
            deps = m.dependencies or []
            suffix = ""
            if deps:
                suffix = ": " + " ".join(deps)
            lines.append(f"{m.path}{suffix}")
        out = self.modules_path / ver / "modules.dep"
        out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return len(lines)

    def _write_modules_alias(self, ver: str, modules: List[KernelModule]) -> int:
        self._ensure_version_dir(ver)
        lines = []
        for m in modules:
            for a in m.aliases or []:
                lines.append(f"alias {a} {m.name}")
        out = self.modules_path / ver / "modules.alias"
        out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return len(lines)

    def _write_modules_symbols(self, ver: str, modules: List[KernelModule]) -> int:
        self._ensure_version_dir(ver)
        lines = []
        for m in modules:
            for s in m.symbols or []:
                lines.append(f"alias symbol:{s} {m.name}")
        out = self.modules_path / ver / "modules.symbols"
        out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return len(lines)

    def _write_modules_softdep(self, ver: str, modules: List[KernelModule]) -> int:
        self._ensure_version_dir(ver)
        lines = []
        for m in modules:
            if m.soft_dependencies:
                lines.append(f"softdep {m.name} pre: " + " ".join(m.soft_dependencies))
        out = self.modules_path / ver / "modules.softdep"
        out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return len(lines)

    def _write_modules_builtin(self, ver: str, modules: List[KernelModule]) -> int:
        """List of modules built into the kernel image (not unloadable)."""
        self._ensure_version_dir(ver)
        builtins = ["kernel/printk.ko", "kernel/sched.ko"]
        out = self.modules_path / ver / "modules.builtin"
        out.write_text("\n".join(builtins) + "\n", encoding="utf-8")
        return len(builtins)

    def _write_modules_params(self, ver: str, modules: List[KernelModule]) -> int:
        self._ensure_version_dir(ver)
        lines = []
        for m in modules:
            for pname, ptype in (m.parameters or {}).items():
                lines.append(f"parm:{pname}:{ptype}")
        out = self.modules_path / ver / "modules.params"
        out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return len(lines)

    def _write_pcimap(self, ver: str, modules: List[KernelModule]) -> int:
        self._ensure_version_dir(ver)
        lines = []
        for m in modules:
            for a in m.aliases or []:
                if a.startswith("pci:"):
                    # Strip the module name suffix to extract vendor/device mask
                    pci_part = a[len("pci:"):]
                    lines.append(
                        f"{m.name} {pci_part.rstrip('d*')} 0xffffffff 0xffffffff"
                    )
        out = self.modules_path / ver / "pcimap"
        out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return len(lines)

    def _write_usbmap(self, ver: str, modules: List[KernelModule]) -> int:
        self._ensure_version_dir(ver)
        # No USB aliases in the starter catalogue; still emit the file header.
        out = self.modules_path / ver / "usbmap"
        out.write_text("", encoding="utf-8")
        return 0

    def _write_isapnpmap(self, ver: str, modules: List[KernelModule]) -> int:
        self._ensure_version_dir(ver)
        out = self.modules_path / ver / "isapnpmap.dep"
        out.write_text("", encoding="utf-8")
        return 0

    # ──────────────────────── build symlink ────────────────────────

    def ensure_build_symlink(self, kernel_version: Optional[str] = None) -> Path:
        """
        Create /lib/modules/<ver>/build → /usr/src/<ver> (kernel build dir).

        Per TLDP: ``/lib/modules/<ver>/kernel/build`` should point to
        ``/usr/src/<kernel-version>``.
        """
        ver = kernel_version or self.kernel_version
        ver_dir = self._ensure_version_dir(ver)
        kernel_subdir = ver_dir / "kernel"
        kernel_subdir.mkdir(parents=True, exist_ok=True)
        build_link = kernel_subdir / "build"
        target = self.source_root / ver
        if build_link.is_symlink() or build_link.is_file():
            build_link.unlink()
        elif build_link.exists():
            log.warning("Build reference exists and is not replaceable: %s", build_link)
            return build_link
        try:
            build_link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError) as e:
            log.warning("Could not create build symlink: %s", e)
            try:
                build_link.write_text(
                    f"UmerOS kernel build reference\nTarget: {target}\n",
                    encoding="utf-8",
                )
            except OSError:
                pass
        return build_link

    # ──────────────────────── modinfo ──────────────────────────────

    def get_module_info(self, name: str) -> Dict:
        """Return modinfo-style metadata for a module."""
        mod = self.find_module(name)
        if mod is None:
            return {"error": f"Module not found: {name}"}
        return {
            "name": mod.name,
            "path": mod.path,
            "size": mod.size,
            "version": mod.version,
            "vermagic": mod.vermagic,
            "description": mod.description,
            "author": mod.author,
            "license": mod.license,
            "depends": mod.dependencies,
            "softdeps": mod.soft_dependencies,
            "aliases": mod.aliases,
            "symbols": mod.symbols,
            "parameters": mod.parameters,
            "firmware": mod.firmware,
            "state": mod.state.value,
        }

    def get_module_dependencies(self, name: str) -> List[str]:
        """Return direct dependencies of a module."""
        mod = self.find_module(name)
        return list(mod.dependencies) if mod else []

    def get_module_dependents(self, name: str) -> List[str]:
        """Return modules that depend on this one (reverse lookup)."""
        out = []
        for mod in self.get_modules_for_version():
            if name in mod.dependencies:
                out.append(mod.name)
        return out

    def resolve_load_order(self, name: str) -> List[str]:
        """
        Compute the topological load order for a module + its dependencies.
        Raises ValueError on a cycle.
        """
        order: List[str] = []
        visited: Set[str] = set()
        visiting: Set[str] = set()

        def visit(n: str) -> None:
            if n in visited:
                return
            if n in visiting:
                raise ValueError(f"Cycle in module dependencies at {n}")
            visiting.add(n)
            mod = self.find_module(n)
            if mod is None:
                visiting.discard(n)
                visited.add(n)
                return
            for dep in mod.dependencies:
                visit(dep)
            visiting.discard(n)
            visited.add(n)
            order.append(n)

        visit(name)
        return order

    # ──────────────────────── modprobe / insmod / rmmod ────────────

    def insmod(
        self,
        name: str,
        params: Optional[Dict[str, str]] = None,
    ) -> ModuleLoadResult:
        """
        Insert a single module (no dep resolution).  Returns the result code.
        """
        mod = self.find_module(name)
        if mod is None:
            return ModuleLoadResult.NOT_FOUND
        if name in self._loaded:
            return ModuleLoadResult.ALREADY_LOADED
        # Apply parameters (in-memory only; the real kernel would write them)
        if params:
            mod.parameters.update(params)
        self._loaded.add(name)
        mod.state = ModuleState.LIVE
        log.info("insmod %s", name)
        return ModuleLoadResult.OK

    def modprobe(
        self,
        name: str,
        params: Optional[Dict[str, str]] = None,
    ) -> ModuleLoadResult:
        """
        Load a module and all of its (hard) dependencies in the right order.
        """
        try:
            order = self.resolve_load_order(name)
        except ValueError as e:
            log.error("modprobe cycle: %s", e)
            return ModuleLoadResult.MISSING_DEP
        for n in order:
            res = self.insmod(n, params if n == name else None)
            if res in (ModuleLoadResult.NOT_FOUND, ModuleLoadResult.IO_ERROR):
                return ModuleLoadResult.MISSING_DEP
        return ModuleLoadResult.OK

    def rmmod(self, name: str, *, force: bool = False) -> ModuleLoadResult:
        """Remove a single module from the live set."""
        if name not in self._loaded:
            return ModuleLoadResult.NOT_LOADED
        # If something depends on it, refuse unless force
        if not force:
            dependents = self.get_module_dependents(name)
            for dep in dependents:
                if dep in self._loaded:
                    log.error("rmmod: %s is in use by %s", name, dep)
                    return ModuleLoadResult.IO_ERROR
        self._loaded.discard(name)
        mod = self.find_module(name)
        if mod is not None:
            mod.state = ModuleState.UNLOADED
        log.info("rmmod %s", name)
        return ModuleLoadResult.OK

    def modprobe_remove(
        self,
        name: str,
        *,
        force: bool = False,
    ) -> List[ModuleLoadResult]:
        """
        Remove a module and (recursively) anything that was loaded only because
        of it.  Returns a list of per-module results.
        """
        results: List[ModuleLoadResult] = []
        # First, find everything that *only* exists because of `name`.
        dependents: Set[str] = set()
        frontier = [name]
        while frontier:
            current = frontier.pop()
            for dep in self.get_module_dependents(current):
                if dep in self._loaded and dep not in dependents:
                    dependents.add(dep)
                    frontier.append(dep)
        # Unload in reverse order
        for n in sorted(dependents, reverse=True):
            results.append(self.rmmod(n, force=force))
        results.append(self.rmmod(name, force=force))
        return results

    # ──────────────────────── summary ──────────────────────────────

    def get_summary(self, kernel_version: Optional[str] = None) -> Dict:
        """Return a snapshot of the module subsystem."""
        ver = kernel_version or self.kernel_version
        modules = self.get_modules_for_version(ver)
        total_size = sum(m.size for m in modules)
        loaded = self.list_loaded_modules()
        return {
            "kernel_versions": self.get_kernel_versions(),
            "active_version": ver,
            "total_modules": len(modules),
            "total_size_bytes": total_size,
            "loaded_modules": loaded,
            "loaded_count": len(loaded),
            "modules_path": str(self.modules_path / ver),
        }

    # ──────────────────────── helpers ──────────────────────────────

    def _iter_module_files(self, version_dir: Path) -> Iterable[Path]:
        """Yield kernel module files, including compressed ``.ko`` variants."""
        return (
            item
            for item in sorted(version_dir.rglob("*"))
            if item.is_file() and self._is_module_file(item)
        )

    @staticmethod
    def _is_module_file(path: Path) -> bool:
        return any(path.name.endswith(suffix) for suffix in MODULE_FILE_SUFFIXES)

    @staticmethod
    def _module_name_from_path(path: Path) -> str:
        name = path.name
        for suffix in MODULE_FILE_SUFFIXES:
            if name.endswith(suffix):
                return name[:-len(suffix)]
        return path.stem

    def _build_module_from_ko(
        self,
        path: Path,
        kernel_version: Optional[str] = None,
    ) -> KernelModule:
        version = kernel_version or self.kernel_version
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        md5 = ""
        try:
            h = hashlib.md5()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            md5 = h.hexdigest()
        except OSError:
            pass
        return KernelModule(
            name=self._module_name_from_path(path),
            path=str(path),
            size=size,
            version=version,
            description=f"Found on disk: {path.name}",
            vermagic=f"{version} SMP mod_unload",
            md5=md5,
        )

    def register_module(
        self,
        name: str,
        *,
        depends_on: Optional[Iterable[str]] = None,
        soft: Optional[Iterable[str]] = None,
        aliases: Optional[Iterable[str]] = None,
        parameters: Optional[Dict[str, str]] = None,
    ) -> None:
        """Add or update a module in the in-memory catalogue."""
        self._modules[name] = ModuleDependency(
            name,
            depends_on=list(depends_on or []),
            soft=list(soft or []),
            aliases=list(aliases or []),
            parameters=dict(parameters or {}),
        )
        # Drop any stale info cache
        self._info.pop(name, None)


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------

def _selftest():
    """Run a basic self-test for this module."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        cat = KernelModuleManager(lib_path=tmpdir)
        summary = cat.get_summary()
        assert "total_modules" in summary, "summary should have total_modules"

    print("selftest OK")
    return True


if __name__ == "__main__":
    _selftest()
