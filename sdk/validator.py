# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
UmerOS SDK - App Validator
===========================

Validates UmerOS application manifests and code structure.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.SDK.Validator")


@dataclass
class ValidationResult:
    """Result of app validation."""
    valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)


class AppValidator:
    """Validates UmerOS application structure and manifest."""

    REQUIRED_MANIFEST_FIELDS = ["name", "version", "author", "description", "entry_point"]
    REQUIRED_FILES = ["manifest.json", "src/main.py"]

    def validate_manifest(self, manifest: dict) -> ValidationResult:
        """Validate a manifest dictionary."""
        result = ValidationResult()
        for field in self.REQUIRED_MANIFEST_FIELDS:
            if field not in manifest:
                result.errors.append(f"Missing required field: {field}")
                result.valid = False
        # Version format check
        version = manifest.get("version", "")
        if version and not self._valid_version(version):
            result.warnings.append(f"Version '{version}' doesn't follow semver (x.y.z)")
        # Name check
        name = manifest.get("name", "")
        if name and not name.isidentifier():
            result.warnings.append(f"App name '{name}' is not a valid Python identifier")
        if not result.errors:
            result.info.append("Manifest is valid")
        return result

    def _valid_version(self, version: str) -> bool:
        parts = version.split(".")
        return len(parts) == 3 and all(p.isdigit() for p in parts)

    def validate_structure(self, app_dir: str) -> ValidationResult:
        """Validate an app directory structure."""
        result = ValidationResult()
        base = os.path.abspath(app_dir)
        if not os.path.exists(base):
            result.errors.append(f"Directory not found: {base}")
            result.valid = False
            return result
        for req_file in self.REQUIRED_FILES:
            path = os.path.join(base, req_file)
            if not os.path.exists(path):
                result.errors.append(f"Missing required file: {req_file}")
                result.valid = False
        # Check manifest content
        manifest_path = os.path.join(base, "manifest.json")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path) as f:
                    manifest = json.load(f)
                mr = self.validate_manifest(manifest)
                result.errors.extend(mr.errors)
                result.warnings.extend(mr.warnings)
                result.info.extend(mr.info)
                if mr.errors:
                    result.valid = False
            except json.JSONDecodeError as e:
                result.errors.append(f"Invalid JSON in manifest: {e}")
                result.valid = False
        if not result.errors:
            result.info.append("App structure is valid")
        return result

    def validate_code(self, code: str) -> ValidationResult:
        """Basic static analysis of app code."""
        result = ValidationResult()
        if "class " not in code:
            result.warnings.append("No class definition found")
        if "UmerApp" not in code and "UmerApp" not in code:
            result.warnings.append("Does not appear to subclass UmerApp")
        if "def on_start" not in code:
            result.warnings.append("Missing on_start lifecycle hook")
        if "def on_stop" not in code:
            result.warnings.append("Missing on_stop lifecycle hook")
        if not result.warnings:
            result.info.append("Code structure looks good")
        return result