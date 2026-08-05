"""
UmerOS /bin Archive Commands
==============================
Implements the tar archiving utility.

TLDP Optional / Recommended:
  tar - The GNU tar archiving utility
"""

from __future__ import annotations

import json
import os
from typing import List, Tuple, Any


class TarCommand:
    """
    Tape Archiver — create/extract archives.

    Supports common tar operations: create (c), extract (x), list (t), update (u).
    """

    description = "GNU tar archiving utility"

    def execute(self, args: List[str], stdin: Any = None, stdout: Any = None) -> Tuple[int, str]:
        if not args or not args[0]:
            return 2, "tar: missing operand"

        flags = args[0]
        archive = args[1] if len(args) > 1 else ""
        files = args[2:] if len(args) > 2 else []

        if not archive:
            return 2, "tar: archive file required"

        if "c" in flags:
            return self._create(archive, files, flags)
        elif "x" in flags:
            return self._extract(archive, flags)
        elif "t" in flags:
            return self._list(archive, flags)
        elif "u" in flags:
            return self._update(archive, files, flags)
        else:
            return 2, f"tar: unknown operation: {flags}"

    def _create(self, archive: str, files: List[str], flags: str) -> Tuple[int, str]:
        manifest = {"files": {}}
        for fp in files:
            try:
                with open(fp, "rb") as f:
                    data = f.read()
                manifest["files"][fp] = {
                    "size": len(data),
                    "data_hex": data.hex()
                }
            except FileNotFoundError:
                return 1, f"tar: {fp}: No such file or directory"
        try:
            with open(archive, "w") as f:
                json.dump(manifest, f, indent=2)
            if "v" in flags:
                return 0, "\n".join(files)
            return 0, ""
        except Exception as e:
            return 1, f"tar: {archive}: {e}"

    def _extract(self, archive: str, flags: str) -> Tuple[int, str]:
        try:
            with open(archive, "r") as f:
                manifest = json.load(f)
            extracted = []
            for fp, info in manifest.get("files", {}).items():
                data = bytes.fromhex(info["data_hex"])
                os.makedirs(os.path.dirname(fp) or ".", exist_ok=True)
                with open(fp, "wb") as f:
                    f.write(data)
                extracted.append(fp)
            if "v" in flags:
                return 0, "\n".join(extracted)
            return 0, ""
        except FileNotFoundError:
            return 1, f"tar: {archive}: No such file or directory"
        except Exception as e:
            return 1, f"tar: {e}"

    def _list(self, archive: str, flags: str) -> Tuple[int, str]:
        try:
            with open(archive, "r") as f:
                manifest = json.load(f)
            names = list(manifest.get("files", {}).keys())
            return 0, "\n".join(names)
        except FileNotFoundError:
            return 1, f"tar: {archive}: No such file or directory"

    def _update(self, archive: str, files: List[str], flags: str) -> Tuple[int, str]:
        return self._create(archive, files, flags)
