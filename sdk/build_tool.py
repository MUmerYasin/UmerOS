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

#!/usr/bin/env python3
"""
Umer OS SDK - Build Tool

CLI tool to scaffold, build, and package new Umer OS applications.
Generates a project directory with the correct structure and a
manifest file ready for distribution via umer-pkg.

Usage:
    python -m sdk.build_tool scaffold MyApp
    python -m sdk.build_tool package MyApp

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import json
import keyword
import posixpath
import re
import unicodedata
from typing import List, Optional

try:
    from core.path_guard import PathTraversalError
except Exception:  # pragma: no cover - standalone fallback
    import os as _os
    import sys as _sys
    _proj = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if _proj not in _sys.path:
        _sys.path.insert(0, _proj)
    from core.path_guard import PathTraversalError

try:
    from .validator import AppValidator
except ImportError:  # pragma: no cover - direct execution
    from validator import AppValidator

#: Every scaffolded project lives directly beneath this VFS root.
PROJECTS_ROOT = "/sdk/projects"

#: Longest accepted app name, in characters.
MAX_APP_NAME = 64

#: One path segment: starts alphanumeric, then alphanumerics/underscore/hyphen.
#: Deliberately excludes ``/``, ``\``, ``.`` and whitespace, which makes ``..``
#: and absolute paths *unrepresentable* rather than merely rejected afterwards.
APP_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def validate_app_name(app_name: str) -> str:
    """Return ``app_name`` unchanged if it is a safe single path segment.

    Args:
        app_name: caller-supplied project name.

    Returns:
        The validated name.

    Raises:
        PathTraversalError: on traversal, a path separator, an empty or
            non-string name, or a name outside the permitted alphabet.
            This is a *security* refusal: the caller must not touch the VFS.
    """
    if not isinstance(app_name, str):
        raise PathTraversalError(
            f"App name must be a string, got {type(app_name).__name__}"
        )
    if not app_name:
        raise PathTraversalError("Refusing empty app name")
    if app_name in (".", ".."):
        raise PathTraversalError(f"Refusing {app_name!r} as app name")
    if "/" in app_name or "\\" in app_name:
        raise PathTraversalError(
            f"Refusing path separator in app name: {app_name!r}"
        )
    if not APP_NAME_RE.match(app_name):
        raise PathTraversalError(
            f"Invalid app name {app_name!r}: expected 1-{MAX_APP_NAME} characters "
            "from [A-Za-z0-9_-], starting with a letter or digit"
        )
    return app_name


def project_path(app_name: str) -> str:
    """Build the VFS path for a project, proving it stays under the root.

    The name is validated first, then the joined path is normalised and
    checked against :data:`PROJECTS_ROOT` so a future change to the regex
    cannot silently widen the blast radius.

    Raises:
        PathTraversalError: if the resulting path is not a direct child of
            :data:`PROJECTS_ROOT`.
    """
    name = validate_app_name(app_name)
    expected = f"{PROJECTS_ROOT}/{name}"
    path = posixpath.normpath(expected)
    if path != expected or not path.startswith(PROJECTS_ROOT + "/"):
        raise PathTraversalError(
            f"Project path escapes {PROJECTS_ROOT}: {path!r}"
        )
    return path


def class_identifier(app_name: str) -> str:
    """Derive a valid Python class name from an app name.

    An app name may legitimately contain hyphens (``my-app``), which cannot
    appear in an identifier.  Rather than reject such names, map the illegal
    characters to underscores and repair the leading-character and keyword
    cases, so the generated module always parses.
    """
    ident = re.sub(r"[^0-9A-Za-z_]", "_", app_name)
    if not ident or ident[0].isdigit():
        ident = f"_{ident}"
    if keyword.iskeyword(ident):
        ident = f"{ident}_app"
    return ident


def _py_literal(value: str) -> str:
    """Quote ``value`` so it cannot terminate the literal it is embedded in."""
    return json.dumps(value)


#: Control characters that are legitimate in source text.  Everything else in
#: the Unicode ``Cc`` category (NUL, ESC, DEL, ...) is rejected: such a byte is
#: never intentional in a hand-written module and corrupts the written file.
_ALLOWED_CONTROL = frozenset("\n\r\t")


def validate_custom_code(code: str) -> List[str]:
    """Screen caller-supplied app source before it is written to the VFS.

    ``custom_app_code`` is **trusted developer input**.  This function does not
    sandbox it -- it cannot, and no amount of screening would make it safe to
    accept code from an untrusted party.  What it does is catch the accidents
    that would otherwise leave a silently broken project on disk: control
    characters that corrupt the file, and source that cannot even be parsed.

    Args:
        code: the source the caller wants written to ``src/main.py``.

    Returns:
        Advisory warnings from :class:`sdk.validator.AppValidator` -- a missing
        ``UmerApp`` subclass, missing lifecycle hooks, and so on.  Warnings are
        reported but do **not** block the write, because a partial fragment is a
        legitimate thing to scaffold.

    Raises:
        ValueError: if ``code`` is not a string, contains a disallowed control
            character, or does not compile.  Nothing is written in that case.
    """
    if not isinstance(code, str):
        raise ValueError(
            f"custom_app_code must be a string, got {type(code).__name__}"
        )
    for index, char in enumerate(code):
        if char in _ALLOWED_CONTROL:
            continue
        if unicodedata.category(char) == "Cc":
            raise ValueError(
                f"custom_app_code contains a control character "
                f"{char!r} at offset {index}"
            )
    try:
        compile(code, "<custom_app_code>", "exec")
    except SyntaxError as exc:
        raise ValueError(
            f"custom_app_code does not parse: {exc.msg} (line {exc.lineno})"
        ) from exc
    return list(AppValidator().validate_code(code).warnings)


class BuildTool:
    """SDK build tool for Umer OS application development."""

    def __init__(self, vfs=None):
        self.vfs = vfs

    def scaffold(self, app_name: str, custom_app_code: Optional[str] = None) -> str:
        """Generate a new app project skeleton.

        Args:
            app_name: project name; must be a safe single path segment.
            custom_app_code: **trusted developer input**, written verbatim to
                ``src/main.py`` in place of the generated template.  It is
                screened for control characters and parse errors, but it is
                *not* sandboxed -- never pass data from an untrusted source
                here, because the resulting file is imported by the packaging
                flow.  A partial fragment is acceptable: advisory warnings are
                reported, not enforced.

        Raises:
            PathTraversalError: if ``app_name`` is not a safe path segment.
            ValueError: if ``custom_app_code`` is unusable (see
                :func:`validate_custom_code`).

        In either failure case nothing is written to the VFS.
        """
        base = project_path(app_name)
        warnings = validate_custom_code(custom_app_code) if custom_app_code else []
        for warning in warnings:
            print(f"[SDK] Warning: {warning}")

        if self.vfs:
            self.vfs.mkdir(base)
            self.vfs.mkdir(f"{base}/src")
            self.vfs.mkdir(f"{base}/tests")

            # Main app file
            if custom_app_code:
                app_code = custom_app_code
            else:
                app_code = f'''from sdk.app_template import UmerApp

class {class_identifier(app_name)}(UmerApp):
    def __init__(self):
        super().__init__({_py_literal(app_name)}, "1.0.0")

    def on_start(self):
        super().on_start()
        # Your app logic here
        pass
'''
            self.vfs.write_file(f"{base}/src/main.py", app_code.encode())

            # Manifest
            manifest = {
                "name": app_name.lower(),
                "version": "1.0.0",
                "author": "Developer",
                "description": f"A {app_name} app for Umer OS",
                "entry_point": "src/main.py",
                "dependencies": ["umer-core", "umer-ai"],
            }
            self.vfs.write_file(
                f"{base}/manifest.json",
                json.dumps(manifest, indent=2).encode()
            )

            print(f"[SDK] Scaffolded project '{app_name}' at {base}/")
        else:
            print(f"[SDK] Scaffold '{app_name}' (VFS not available, dry-run)")

        return base

    def package(self, app_name: str) -> dict:
        """Package an app for distribution via umer-pkg.

        Raises:
            PathTraversalError: if ``app_name`` is not a safe path segment.
        """
        base = project_path(app_name)
        print(f"[SDK] Packaging '{app_name}' from {base}/...")

        pkg_info = {
            "name": app_name.lower(),
            "version": "1.0.0",
            "archive": f"{app_name.lower()}-1.0.0.umer.pkg",
            "status": "packaged",
        }

        if self.vfs:
            self.vfs.write_file(
                f"{base}/{pkg_info['archive']}",
                json.dumps(pkg_info).encode()
            )

        print(f"[SDK] Package created: {pkg_info['archive']}")
        return pkg_info


def _selftest() -> bool:
    """Run self-tests for name validation, scaffolding and packaging."""
    print("[sdk/build_tool] selftest …")
    ok = True

    def check(condition: bool, label: str) -> None:
        nonlocal ok
        if condition:
            print(f"  [PASS] {label}")
        else:
            ok = False
            print(f"  [FAIL] {label}")

    check(
        project_path("MyApp") == "/sdk/projects/MyApp",
        "project_path builds a child of the root",
    )
    check(class_identifier("my-app") == "my_app", "hyphenated name maps to an identifier")
    check(class_identifier("1Bad") == "_1Bad", "leading digit is repaired")

    for bad in ("../../evil", "a/b", "..", ""):
        try:
            project_path(bad)
        except PathTraversalError:
            check(True, f"project_path refuses {bad!r}")
        else:
            check(False, f"project_path accepted {bad!r}")

    class _VFS:
        def __init__(self) -> None:
            self.files: dict = {}
            self.dirs: list = []

        def mkdir(self, path: str) -> None:
            self.dirs.append(path)

        def write_file(self, path: str, data: bytes) -> None:
            self.files[path] = data

    vfs = _VFS()
    tool = BuildTool(vfs=vfs)
    base = tool.scaffold("Selftest")
    check(base == "/sdk/projects/Selftest", "scaffold returns the project path")
    check(f"{base}/src/main.py" in vfs.files, "scaffold writes src/main.py")
    check(f"{base}/manifest.json" in vfs.files, "scaffold writes manifest.json")
    compile(vfs.files[f"{base}/src/main.py"].decode(), "<generated>", "exec")
    check(True, "generated source parses")

    info = tool.package("Selftest")
    check(info["name"] == "selftest", "package lower-cases the name")
    check(info["status"] == "packaged", "package reports status")

    check(validate_custom_code("x = 1\n") != [], "a fragment warns but is not refused")
    try:
        validate_custom_code("x = 1\x00\n")
    except ValueError:
        check(True, "control character refused")
    else:
        check(False, "control character should be refused")

    print("[sdk/build_tool] selftest " + ("PASSED" if ok else "FAILED"))
    return ok


if __name__ == "__main__":
    _selftest()
