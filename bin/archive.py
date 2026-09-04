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

"""Archive operations: tar."""

from __future__ import annotations

import json
import os
import sys
import logging
from typing import Any, List, Optional

log = logging.getLogger("UmerOS.archive")


class TarCommand:
    """Tape Archiver -- create/extract archives."""

    name = "tar"
    description = "GNU tar archiving utility"

    def execute(self, args: Optional[List[str]] = None, stdin: Any = None, stdout: Any = None) -> int:
        if args is None:
            args = []
        if "--help" in args or "-h" in args:
            print(self._usage(), file=stdout or sys.stdout)
            return 0
        if "--version" in args:
            print("tar (UmerOS) 1.0", file=stdout or sys.stdout)
            return 0
        if not args:
            print("tar: missing operand", file=sys.stderr)
            print("Try 'tar --help' for more information.", file=sys.stderr)
            return 1
        flags = args[0]
        archive = args[1] if len(args) > 1 else ""
        files = args[2:] if len(args) > 2 else []
        if not archive:
            print("tar: archive file required", file=sys.stderr)
            return 1
        if "c" in flags:
            return self._create(archive, files, flags, stdout)
        elif "x" in flags:
            return self._extract(archive, flags, stdout)
        elif "t" in flags:
            return self._list(archive, flags, stdout)
        elif "u" in flags:
            return self._update(archive, files, flags, stdout)
        else:
            print(f"tar: unknown operation: {flags}", file=sys.stderr)
            return 1

    def _create(self, archive: str, files: List[str], flags: str, stdout: Any = None) -> int:
        manifest = {"files": {}}
        for fp in files:
            try:
                with open(fp, "rb") as f:
                    data = f.read()
                manifest["files"][fp] = {
                    "size": len(data),
                    "data_hex": data.hex(),
                }
            except FileNotFoundError:
                print(f"tar: {fp}: No such file or directory", file=sys.stderr)
                return 1
        try:
            with open(archive, "w") as f:
                json.dump(manifest, f, indent=2)
            if "v" in flags:
                out = stdout or sys.stdout
                for fp in files:
                    print(fp, file=out)
            return 0
        except (OSError, ValueError) as e:  # [FIX H8]
            print(f"tar: {archive}: {e}", file=sys.stderr)
            return 1

    def _extract(self, archive: str, flags: str, stdout: Any = None) -> int:
        try:
            with open(archive, "r") as f:
                manifest = json.load(f)
        except FileNotFoundError:
            print(f"tar: {archive}: No such file or directory", file=sys.stderr)
            return 1
        except json.JSONDecodeError:
            print(f"tar: {archive}: Invalid archive format", file=sys.stderr)
            return 1
        for fp, info in manifest.get("files", {}).items():
            data = bytes.fromhex(info["data_hex"])
            os.makedirs(os.path.dirname(fp) or ".", exist_ok=True)
            with open(fp, "wb") as f:
                f.write(data)
            if "v" in flags:
                out = stdout or sys.stdout
                print(fp, file=out)
        return 0

    def _list(self, archive: str, flags: str, stdout: Any = None) -> int:
        try:
            with open(archive, "r") as f:
                manifest = json.load(f)
        except FileNotFoundError:
            print(f"tar: {archive}: No such file or directory", file=sys.stderr)
            return 1
        except json.JSONDecodeError:
            print(f"tar: {archive}: Invalid archive format", file=sys.stderr)
            return 1
        out = stdout or sys.stdout
        for fp in manifest.get("files", {}):
            print(fp, file=out)
        return 0

    def _update(self, archive: str, files: List[str], flags: str, stdout: Any = None) -> int:
        manifest = {"files": {}}
        if os.path.exists(archive):
            try:
                with open(archive, "r") as f:
                    manifest = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        for fp in files:
            try:
                st = os.stat(fp)
                existing = manifest.get("files", {}).get(fp)
                if existing and existing.get("mtime", 0) >= st.st_mtime:
                    continue
                with open(fp, "rb") as f:
                    data = f.read()
                manifest.setdefault("files", {})[fp] = {
                    "size": len(data),
                    "data_hex": data.hex(),
                    "mtime": st.st_mtime,
                }
            except FileNotFoundError:
                print(f"tar: {fp}: No such file or directory", file=sys.stderr)
                return 1
        try:
            with open(archive, "w") as f:
                json.dump(manifest, f, indent=2)
            if "v" in flags:
                out = stdout or sys.stdout
                for fp in files:
                    print(fp, file=out)
            return 0
        except (OSError, ValueError) as e:  # [FIX H8] json.dump + print I/O
            print(f"tar: {archive}: {e}", file=sys.stderr)
            return 1

    def _usage(self) -> str:
        return (
            "Usage: tar [cxutfv] ARCHIVE [FILE...]\n"
            "\n"
            "GNU tar archiving utility.\n"
            "\n"
            "Operations:\n"
            "  c    create archive\n"
            "  x    extract archive\n"
            "  t    list archive contents\n"
            "  u    update archive\n"
            "\n"
            "Options:\n"
            "  f    archive file\n"
            "  v    verbose output\n"
            "  -h, --help    display this help"
        )


def _selftest() -> bool:
    """Run self-tests for archive module."""
    try:
        import tempfile, os

        tc = TarCommand()
        # --help
        assert tc.execute(["--help"]) == 0
        # --version
        assert tc.execute(["--version"]) == 0
        # no-args returns 1 (missing operand)
        assert tc.execute([]) == 1
        # missing archive file
        assert tc.execute(["cf"]) == 1

        # Create and extract round-trip
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("archive test content\n")
            src = f.name
        archive_path = src + ".tar"
        try:
            assert tc.execute(["cvf", archive_path, src]) == 0
            assert os.path.exists(archive_path)
            # List
            assert tc.execute(["tvf", archive_path]) == 0
            # Extract
            os.unlink(src)
            assert tc.execute(["xvf", archive_path]) == 0
            assert os.path.exists(src)
        finally:
            for p in [src, archive_path]:
                if os.path.exists(p):
                    os.unlink(p)

        return True
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"_selftest FAILED: {e}")
        return False
