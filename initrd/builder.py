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
Umer OS Initrd Builder
======================
Build a real, bootable initramfs image from a Python description.

Pipeline::

    BuildRequest
        |
        v
    +------------------+
    | collect entries  |  <-- mandatory base + scenario extras + caller extras
    +------------------+
        |
        v
    +------------------+
    | pack cpio (newc) |
    +------------------+
        |
        v
    +------------------+
    | compress         |  <-- gzip / xz / lz4 / zstd / none
    +------------------+
        |
        v
    +------------------+
    | write to disk    |  <-- .img, .img.gz, .img.xz, .img.zst, ...
    +------------------+

The :class:`BuildRequest` is a pure dataclass, so it can be filled in
from CLI args, a JSON config, or the UmerOS ``ai_config.json`` file.
The :class:`InitrdBuilder` runs the pipeline and returns a
:class:`BuildResult` with sizes, hashes and the entries that were
included.

This module is the host-side companion to the runtime
:mod:`initrd.linuxrc`.  In production you would run it once on the
build server, hand the resulting blob to the bootloader
(:mod:`boot.grub_manager`) and let the kernel pick it up at next
boot.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from initrd.archivers import Archiver, detect_archiver, get_archiver
from initrd.cpio import (
    CpioEntry,
    newc_dir,
    newc_file,
    newc_symlink,
    pack_archive,
)
from initrd.module_resolver import ModuleResolver
from initrd.scenarios import InitrdScenario, ScenarioId, get_scenario

log = logging.getLogger("UmerOS.Initrd.Builder")


# ---------------------------------------------------------------------------
# Output formats
# ---------------------------------------------------------------------------

class OutputFormat(str, Enum):
    """How the resulting image is written to disk."""

    CPIO_RAW  = "cpio"        # raw newc, no compression
    CPIO_GZ   = "cpio.gz"
    CPIO_XZ   = "cpio.xz"
    CPIO_LZ4  = "cpio.lz4"
    CPIO_ZSTD = "cpio.zst"
    DIRECTORY = "directory"   # unpacked tree, useful for inspection


# ---------------------------------------------------------------------------
# Request dataclass
# ---------------------------------------------------------------------------

@dataclass
class BuildRequest:
    """Inputs to :meth:`InitrdBuilder.build`."""

    kernel_version: str
    scenario: ScenarioId = ScenarioId.NORMAL
    output_format: OutputFormat = OutputFormat.CPIO_GZ
    output_path: str = "initramfs-umeros.img"
    compression_level: int = 6
    extra_files: Dict[str, bytes] = field(default_factory=dict)
    extra_directories: List[str] = field(default_factory=list)
    extra_symlinks: Dict[str, str] = field(default_factory=dict)
    modules: List[str] = field(default_factory=list)
    hooks: Dict[str, List[str]] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kernel_version":    self.kernel_version,
            "scenario":          self.scenario.value,
            "output_format":     self.output_format.value,
            "output_path":       self.output_path,
            "compression_level": self.compression_level,
            "extra_files":       {k: v.decode("utf-8", "replace") for k, v in self.extra_files.items()},
            "extra_directories": list(self.extra_directories),
            "extra_symlinks":    dict(self.extra_symlinks),
            "modules":           list(self.modules),
            "hooks":             {k: list(v) for k, v in self.hooks.items()},
            "metadata":          dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BuildRequest":
        return cls(
            kernel_version    = data["kernel_version"],
            scenario          = ScenarioId(data.get("scenario", "normal")),
            output_format     = OutputFormat(data.get("output_format", "cpio.gz")),
            output_path       = data.get("output_path", "initramfs-umeros.img"),
            compression_level = int(data.get("compression_level", 6)),
            extra_files       = {k: v.encode("utf-8") for k, v in data.get("extra_files", {}).items()},
            extra_directories = list(data.get("extra_directories", [])),
            extra_symlinks    = dict(data.get("extra_symlinks", {})),
            modules           = list(data.get("modules", [])),
            hooks             = {k: list(v) for k, v in data.get("hooks", {}).items()},
            metadata          = dict(data.get("metadata", {})),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, text: str) -> "BuildRequest":
        return cls.from_dict(json.loads(text))


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class BuildResult:
    """Outputs of :meth:`InitrdBuilder.build`."""

    request: BuildRequest
    output_path: str
    raw_size: int
    compressed_size: int
    entry_count: int
    duration_seconds: float
    sha256_raw: str
    sha256_final: str
    archiver: str
    scenario: str
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "output_path":      self.output_path,
            "raw_size":         self.raw_size,
            "compressed_size":  self.compressed_size,
            "entry_count":      self.entry_count,
            "duration_seconds": round(self.duration_seconds, 6),
            "sha256_raw":       self.sha256_raw,
            "sha256_final":     self.sha256_final,
            "archiver":         self.archiver,
            "scenario":         self.scenario,
            "notes":            list(self.notes),
        }


# ---------------------------------------------------------------------------
# Mandatory base entries
# ---------------------------------------------------------------------------

def _base_entries(kernel_version: str, scenario: InitrdScenario) -> List[CpioEntry]:
    """The minimum set of files every Umer OS initrd ships with."""
    init_script = (
        "#!/bin/sh\n"
        "# Umer OS initrd /init - the modern name for /linuxrc.\n"
        "# Invoked by the kernel as PID 1 in the freshly-mounted tmpfs.\n"
        "echo UmerOS initrd v2 - kernel ${KVER:-unknown}\n"
        "exec /usr/lib/umeros/initrd/linuxrc_main.py\n"
    ).encode("utf-8")
    linuxrc = (
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "sys.path.insert(0, '/usr/lib/umeros')\n"
        "from initrd.linuxrc import run\n"
        "run()\n"
    ).encode("utf-8")

    entries: List[CpioEntry] = [
        newc_dir("."),
        newc_dir("bin"),
        newc_dir("dev"),
        newc_dir("etc"),
        newc_dir("etc/umeros"),
        newc_dir("lib"),
        newc_dir("lib/modules", mode=0o755),
        newc_dir(f"lib/modules/{kernel_version}", mode=0o755),
        newc_dir("proc"),
        newc_dir("run"),
        newc_dir("sbin"),
        newc_dir("sys"),
        newc_dir("tmp"),
        newc_dir("usr"),
        newc_dir("usr/bin"),
        newc_dir("usr/lib"),
        newc_dir("usr/lib/umeros"),
        newc_dir("usr/lib/umeros/initrd"),
        newc_dir("var"),
        newc_dir("var/log"),
        # Init entry point
        newc_file("init", init_script, mode=0o755),
        # The /linuxrc compatibility symlink (TLDP still mentions it).
        newc_symlink("linuxrc", "init"),
        # The actual linuxrc_main.py runtime
        newc_file(
            "usr/lib/umeros/initrd/linuxrc_main.py",
            linuxrc,
            mode=0o755,
        ),
        # /etc/issue for the getty
        newc_file("etc/issue", f"Umer OS {kernel_version} \\n \\l\n".encode("utf-8")),
        # /etc/motd
        newc_file("etc/motd", b"Welcome to Umer OS initrd\n"),
    ]
    return entries


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class InitrdBuilder:
    """Compiles a :class:`BuildRequest` into a real on-disk image."""

    def __init__(self, resolver: Optional[ModuleResolver] = None) -> None:
        self.resolver = resolver or ModuleResolver()

    # -- public -----------------------------------------------------------

    def build(self, request: BuildRequest) -> BuildResult:
        start = time.time()
        scenario = get_scenario(request.scenario)
        log.info(
            "building initrd: kernel=%s scenario=%s format=%s out=%s",
            request.kernel_version, request.scenario.value,
            request.output_format.value, request.output_path,
        )

        # 1. Resolve modules.
        specs = self.resolver.from_user_config(request.modules)
        specs += scenario.resolve_modules(self.resolver)
        module_names = sorted({s.name for s in specs})

        # 2. Build cpio entries.
        entries = _base_entries(request.kernel_version, scenario)
        entries = scenario.build_entries(entries)
        # Append caller-supplied extras.
        ino = 9000
        for d in request.extra_directories:
            entries.append(newc_dir(d, ino=ino)); ino += 1
        for path, data in request.extra_files.items():
            entries.append(newc_file(path, data=data, ino=ino)); ino += 1
        for src, target in request.extra_symlinks.items():
            entries.append(newc_symlink(src, target, ino=ino)); ino += 1

        # 3. Write a modules file so the runtime can see what was built.
        modules_manifest = "\n".join(["# Umer OS initrd module manifest"] + module_names)
        entries.append(newc_file(
            "etc/umeros/modules.txt",
            modules_manifest.encode("utf-8"),
            ino=ino,
        ))

        # 4. Pack + compress.
        raw = pack_archive(entries)
        raw_sha = hashlib.sha256(raw).hexdigest()

        out_path = Path(request.output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        notes: List[str] = []
        if request.output_format == OutputFormat.DIRECTORY:
            self._unpack_to_dir(raw, out_path)
            final_bytes = raw
            archiver_name = "raw"
        else:
            archiver_name = self._archiver_name(request.output_format)
            archiver = get_archiver(archiver_name)
            final_bytes = archiver.compress(raw, level=request.compression_level)
            out_path.write_bytes(final_bytes)
        final_sha = hashlib.sha256(final_bytes).hexdigest()
        notes.append(f"scenario={scenario.id.value} modules={len(module_names)}")

        # 5. Optionally write the request next to the image for auditing.
        try:
            out_path.with_suffix(out_path.suffix + ".json").write_text(
                request.to_json(), encoding="utf-8"
            )
        except OSError:
            pass

        duration = time.time() - start
        return BuildResult(
            request=request,
            output_path=str(out_path),
            raw_size=len(raw),
            compressed_size=len(final_bytes),
            entry_count=len(entries),
            duration_seconds=duration,
            sha256_raw=raw_sha,
            sha256_final=final_sha,
            archiver=archiver_name,
            scenario=scenario.id.value,
            notes=notes,
        )

    # -- helpers ----------------------------------------------------------

    def _archiver_name(self, fmt: OutputFormat) -> str:
        return {
            OutputFormat.CPIO_RAW:  "raw",
            OutputFormat.CPIO_GZ:   "gzip",
            OutputFormat.CPIO_XZ:   "xz",
            OutputFormat.CPIO_LZ4:  "lz4",
            OutputFormat.CPIO_ZSTD: "zstd",
        }[fmt]

    def _unpack_to_dir(self, raw: bytes, target: Path) -> None:
        """Write a raw cpio stream out as a directory tree on disk."""
        from initrd.cpio import unpack_archive
        target.mkdir(parents=True, exist_ok=True)
        for entry in unpack_archive(raw):
            rel = entry.name.lstrip("/")
            if not rel:
                continue
            dest = target / rel
            if entry.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            elif entry.is_symlink():
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists() or dest.is_symlink():
                    dest.unlink()
                dest.symlink_to(entry.target or "")
            elif entry.is_regular():
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(entry.data)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest(tmp: Optional[Path] = None) -> bool:
    import tempfile
    if tmp is None:
        tmp = Path(tempfile.mkdtemp(prefix="initrd-selftest-"))
    builder = InitrdBuilder()
    req = BuildRequest(
        kernel_version="6.6.0-umeros",
        scenario=ScenarioId.NORMAL,
        output_format=OutputFormat.CPIO_GZ,
        output_path=str(tmp / "initramfs-selftest.img.gz"),
        extra_files={"/etc/umeros/greeting": b"hello from selftest\n"},
        extra_directories=["/data"],
    )
    result = builder.build(req)
    if not Path(result.output_path).is_file():
        return False
    if result.entry_count == 0:
        return False
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("builder selftest:", "OK" if _selftest() else "FAIL")
