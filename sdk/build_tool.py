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
from typing import Optional

try:
    from core.path_guard import PathTraversalError
except Exception:  # pragma: no cover - standalone fallback
    import os as _os
    import sys as _sys
    _proj = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if _proj not in _sys.path:
        _sys.path.insert(0, _proj)
    from core.path_guard import PathTraversalError

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


class BuildTool:
    """SDK build tool for Umer OS application development."""

    def __init__(self, vfs=None):
        self.vfs = vfs

    def scaffold(self, app_name: str, custom_app_code: Optional[str] = None) -> str:
        """Generate a new app project skeleton.

        Raises:
            PathTraversalError: if ``app_name`` is not a safe path segment.
                Nothing is written to the VFS in that case.
        """
        base = project_path(app_name)

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
