#!/usr/bin/env python3
"""
Umer OS SDK - Build Tool

CLI tool to scaffold, build, and package new Umer OS applications.
Generates a project directory with the correct structure and a
manifest file ready for distribution via umer-pkg.

Usage:
    python -m sdk.build_tool scaffold MyApp
    python -m sdk.build_tool package MyApp
"""

import json


class BuildTool:
    """SDK build tool for Umer OS application development."""

    def __init__(self, vfs=None):
        self.vfs = vfs

    def scaffold(self, app_name: str, custom_app_code: str = None) -> str:
        """Generate a new app project skeleton."""
        base = f"/sdk/projects/{app_name}"

        if self.vfs:
            self.vfs.mkdir(base)
            self.vfs.mkdir(f"{base}/src")
            self.vfs.mkdir(f"{base}/tests")

            # Main app file
            if custom_app_code:
                app_code = custom_app_code
            else:
                app_code = f'''from sdk.app_template import UmerApp

class {app_name}(UmerApp):
    def __init__(self):
        super().__init__("{app_name}", "1.0.0")

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
        """Package an app for distribution via umer-pkg."""
        base = f"/sdk/projects/{app_name}"
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
