import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class CompatibilityResult:
    success: bool
    message: str


class CompatibilityLayer:
    def run_linux_binary(self, path: str) -> CompatibilityResult:
        if not Path(path).exists():
            return CompatibilityResult(False, "Binary not found.")
        return CompatibilityResult(True, f"Linux binary simulated: {path}")

    def run_windows_exe(self, path: str) -> CompatibilityResult:
        if not Path(path).exists():
            return CompatibilityResult(False, "EXE not found.")
        return CompatibilityResult(True, f"Windows executable simulated: {path}")

    def run_android_apk(self, path: str) -> CompatibilityResult:
        if not Path(path).exists():
            return CompatibilityResult(False, "APK not found.")
        return CompatibilityResult(True, f"Android APK simulated: {path}")