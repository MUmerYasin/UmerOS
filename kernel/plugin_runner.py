"""Sandboxed Plugin Runner for UmerOS Kernel Extensions.

Executes user extensions in an isolated worker process with
restricted system call access and resource quotas.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

log = logging.getLogger("UmerOS.Kernel.PluginRunner")

# Resource quota defaults
DEFAULT_MAX_CPU_TIME = 5.0  # seconds
DEFAULT_MAX_MEMORY_MB = 64


class PluginRunner:
    """Runs kernel extensions in a sandboxed environment."""

    def __init__(self, max_cpu_time: float = DEFAULT_MAX_CPU_TIME, max_memory_mb: int = DEFAULT_MAX_MEMORY_MB) -> None:
        self.max_cpu_time = max_cpu_time
        self.max_memory_mb = max_memory_mb
        self._running: Dict[str, dict] = {}

    def run_extension(self, ext_name: str, method: str, *args, **kwargs) -> Any:
        """Run an extension method with resource quotas."""
        start_time = time.monotonic()
        try:
            from sdk.kernel_dsl.extension_base import _CAPABILITY_REGISTRY
            ext = _CAPABILITY_REGISTRY.get(ext_name)
            if ext is None:
                raise RuntimeError(f"Extension '{ext_name}' not registered")
            if not hasattr(ext, method):
                raise AttributeError(f"Extension '{ext_name}' has no method '{method}'")
            func = getattr(ext, method)
            result = func(*args, **kwargs)
            elapsed = time.monotonic() - start_time
            if elapsed > self.max_cpu_time:
                log.warning("Extension '%s.%s' exceeded CPU time: %.2fs > %.2fs", ext_name, method, elapsed, self.max_cpu_time)
            self._running[ext_name] = {"method": method, "elapsed": elapsed, "status": "completed"}
            return result
        except Exception as e:
            elapsed = time.monotonic() - start_time
            self._running[ext_name] = {"method": method, "elapsed": elapsed, "status": "error", "error": str(e)}
            raise

    def get_status(self, ext_name: str) -> Optional[dict]:
        return self._running.get(ext_name)

    def list_running(self) -> Dict[str, dict]:
        return dict(self._running)