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
Umer OS Universal Compatibility Layer 
=====================================================
Provides containerised execution environments for applications built
for other operating systems.

ContainerEngine  — top-level launcher / manager.
ContainerInstance — represents one running foreign application.
WineShim         — Windows .exe runner via Wine (LGPL).
AndroidContainer — Android APK runner via QEMU/ADB stub.
LinuxCompat      — Linux ELF runner (native chroot).
SyscallTranslator — Win32 / Android Binder → POSIX translation table.

TODAY:
  - ContainerEngine with process launching via subprocess.
  - WineShim that detects Wine and launches .exe files.
  - LinuxCompat that runs Linux ELF binaries directly.
  - Syscall translation table (data structure, no kernel hooks).

EXPERIMENTAL:
  - AndroidContainer via ADB / QEMU user-mode.
  - DirectX → Vulkan translation (DXVK/VKD3D stubs).

FUTURE:
  - Full kernel-level namespace + cgroup isolation.
  - iOS/macOS: BLOCKED (Apple Secure Enclave; not supported).
  - TODO: QPU integration — quantum-secure container attestation.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import threading
import time
import uuid
from typing import Dict, List, Optional

try:
    import resource  # POSIX only; unavailable on Windows
except ImportError:  # pragma: no cover - non-POSIX host
    resource = None

from core.capability_gate import gate  # zero-trust capability gate (H52)

log = logging.getLogger("UmerOS.Compatibility")

# Supported application types
APP_TYPE_LINUX   = "linux"
APP_TYPE_WINDOWS = "windows"
APP_TYPE_ANDROID = "android"
APP_TYPE_GAME    = "game"

# ---------------------------------------------------------------------------
# Foreign-binary launch sandbox  [zero-trust; H52]
# ---------------------------------------------------------------------------
# Capability required to launch any foreign binary (ELF/.exe/APK). Fail-closed
# when a CapabilityManager is wired (or strict mode); permissive (warn + allow)
# otherwise - matching the rest of the cap-gate cluster.
CAP_FOREIGN_EXEC = "container.launch"

# Default sandbox posture. Full namespace/seccomp isolation is the module's
# FUTURE note; it is EXPERIMENTAL and OFF by default so existing host-tool
# launches (wine/adb) keep working. Enable per-launch via sandbox=True or
# repo-wide via UMEROS_COMPAT_SANDBOX=1.
_SANDBOX_DEFAULT = os.environ.get("UMEROS_COMPAT_SANDBOX", "0") == "1"

# Env vars a foreign binary may inherit when no explicit env is supplied.
_SAFE_ENV_ALLOW = (
    "PATH", "HOME", "USER", "LOGNAME", "SHELL", "TERM",
    "LANG", "LC_ALL", "DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR",
    "TMPDIR", "TEMP", "TMP",
)


def _sanitize_env(explicit_env: Optional[dict]) -> Optional[dict]:
    """Build a minimal, secret-safe environment for a foreign binary.

    An explicit ``env`` is always honoured (caller intent). When ``env`` is None
    we no longer blindly inherit the *full* parent environment (which would leak
    trust material such as UMEROS_OTA_* keys / OPENROUTER_API_KEY into an
    untrusted foreign process); we pass an allow-listed subset instead.
    """
    if explicit_env is not None:
        return explicit_env
    safe: dict = {}
    for key in _SAFE_ENV_ALLOW:
        val = os.environ.get(key)
        if val is not None:
            safe[key] = val
    return safe


def _sandbox_preexec(drop_uid: Optional[int] = None,
                     drop_gid: Optional[int] = None,
                     mem_mb: int = 512,
                     cpu_seconds: int = 300) -> None:
    """Best-effort privilege drop + resource quotas (POSIX; runs in the child).

    Intended as ``preexec_fn`` for subprocess.Popen. Raises on any step so a
    launch that *asked* to be sandboxed never silently runs unsandboxed.
    Namespace isolation (unshare) is applied when available; the module's FUTURE
    note is full chroot/OCI/seccomp-bpf.

    Raises:
        RuntimeError: If a requested isolation primitive is unavailable.
    """
    if resource is not None:
        try:
            resource.setrlimit(resource.RLIMIT_AS,
                               (mem_mb * 1024 * 1024, mem_mb * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
            resource.setrlimit(resource.RLIMIT_NPROC, (256, 256))
            resource.setrlimit(resource.RLIMIT_FSIZE,
                               (1024 * 1024 * 1024, 1024 * 1024 * 1024))
        except (ValueError, OSError) as exc:
            raise RuntimeError(f"sandbox: rlimit apply failed: {exc}") from exc
    if hasattr(os, "unshare"):
        try:
            # New mount + PID + network namespace (Linux). Best-effort isolation.
            os.unshare(0x00020000 | 0x01000000 | 0x02000000)
        except OSError as exc:
            raise RuntimeError(f"sandbox: unshare failed: {exc}") from exc
    if drop_gid is not None and hasattr(os, "setgid"):
        try:
            os.setgid(drop_gid)
        except OSError as exc:
            raise RuntimeError(f"sandbox: setgid failed: {exc}") from exc
    if drop_uid is not None and hasattr(os, "setuid"):
        try:
            os.setuid(drop_uid)
        except OSError as exc:
            raise RuntimeError(f"sandbox: setuid failed: {exc}") from exc


def _require_launch_capability(sandbox: bool) -> None:
    """Zero-trust gate for foreign-binary launches (H52).

    Fail-closed when a trust source is active (CapabilityManager wired or strict
    mode): the launch capability must be granted. In a hard zero-trust posture
    (gate.enforcing) an *unsandboxed* launch is refused outright - running
    untrusted foreign code with the launcher's privileges is not permitted.
    """
    gate.require(CAP_FOREIGN_EXEC)
    if gate.enforcing and not sandbox:
        raise RuntimeError(
            "Refusing to launch foreign binary UNSANDBOXED while the zero-trust "
            "posture is active (gate.enforcing). Enable sandbox=True or relax "
            "strict mode."
        )


# ---------------------------------------------------------------------------
# ContainerInstance
# ---------------------------------------------------------------------------

class ContainerInstance:
    """Represents a running foreign application inside a Umer OS container.

    Attributes:
        container_id: Unique identifier (UUID4 hex).
        app_type:     One of linux/windows/android/game.
        app_path:     Path to the launched binary or APK.
        pid:          OS-level PID of the host process (None if not started).
        status:       One of "running", "stopped", "error".
    """

    def __init__(
        self,
        app_path:  str,
        app_type:  str = APP_TYPE_LINUX,
        process:   Optional[subprocess.Popen] = None,
    ) -> None:
        self.container_id = uuid.uuid4().hex
        self.app_type     = app_type
        self.app_path     = app_path
        self._process     = process
        self.status       = "running" if process else "stopped"
        self._started_at  = time.monotonic()
        log.info("ContainerInstance %s started: type=%s path='%s'",
                 self.container_id[:8], app_type, app_path)

    @property
    def pid(self) -> Optional[int]:
        """Return OS PID of the host process, or None."""
        return self._process.pid if self._process else None

    def is_alive(self) -> bool:
        """Return True if the underlying host process is still running."""
        if self._process is None:
            return False
        return self._process.poll() is None

    def wait(self, timeout: Optional[float] = None) -> int:
        """Wait for the process to complete and return its exit code.

        Args:
            timeout: Optional seconds to wait; None = wait forever.

        Returns:
            Exit code integer.
        """
        if self._process is None:
            return -1
        try:
            return self._process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return -1

    def terminate(self) -> None:
        """Send SIGTERM to the container process."""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            self.status = "stopped"
            log.info("Container %s terminated.", self.container_id[:8])

    def kill(self) -> None:
        """Send SIGKILL to the container process."""
        if self._process and self._process.poll() is None:
            self._process.kill()
            self.status = "stopped"

    def resource_usage(self) -> dict:
        """Return resource usage snapshot.

        TODAY: Returns placeholder values; real implementation would
        read /proc/<pid>/status on Linux.

        Returns:
            Dict with pid, status, uptime_seconds, cpu_pct, ram_mb keys.
        """
        uptime = round(time.monotonic() - self._started_at, 1)
        alive  = self.is_alive()
        return {
            "container_id": self.container_id[:8],
            "pid":          self.pid,
            "status":       "running" if alive else "stopped",
            "uptime_seconds": uptime,
            "cpu_pct":      0.0,   # TODO: read from /proc/<pid>/stat
            "ram_mb":       0.0,   # TODO: read from /proc/<pid>/status
        }

    def __repr__(self) -> str:
        return (f"ContainerInstance(id={self.container_id[:8]}, "
                f"type={self.app_type}, pid={self.pid})")


# ---------------------------------------------------------------------------
# SyscallTranslator
# ---------------------------------------------------------------------------

class SyscallTranslator:
    """Translates foreign syscalls to POSIX equivalents (data table, no hooks).

    TODAY: In-memory translation tables for Win32 and Android Binder.
    FUTURE: Kernel-level syscall interception via seccomp-bpf.

    The tables map foreign-OS syscall names to their POSIX counterparts.
    """

    WIN32_TO_POSIX: Dict[str, str] = {
        "CreateFile":       "open",
        "ReadFile":         "read",
        "WriteFile":        "write",
        "CloseHandle":      "close",
        "VirtualAlloc":     "mmap",
        "VirtualFree":      "munmap",
        "CreateThread":     "pthread_create",
        "ExitThread":       "pthread_exit",
        "WaitForSingleObject": "pthread_join",
        "CreateProcess":    "fork+exec",
        "TerminateProcess": "kill",
        "GetSystemTime":    "clock_gettime",
        "Sleep":            "nanosleep",
        "HeapAlloc":        "malloc",
        "HeapFree":         "free",
        "WSAStartup":       "socket_init",
        "connect":          "connect",
        "send":             "send",
        "recv":             "recv",
        "closesocket":      "close",
    }

    ANDROID_BINDER_TO_POSIX: Dict[str, str] = {
        "startActivity":    "exec",
        "startService":     "fork",
        "sendBroadcast":    "kill+signal",
        "openFile":         "open",
        "query":            "ioctl",
        "getSystemService": "dlopen",
        "PowerManager.goToSleep": "suspend_hint",
        "Camera.open":      "open(/dev/video0)",
        "SensorManager.registerListener": "ioctl(IIO)",
    }

    def translate_win32(self, syscall: str, args: Optional[dict] = None) -> tuple:
        """Translate a Win32 API call to its POSIX equivalent.

        Args:
            syscall: Win32 function name.
            args:    Optional argument dict for logging.

        Returns:
            Tuple of (posix_name, args_dict).
        """
        posix = self.WIN32_TO_POSIX.get(syscall, "UNKNOWN")
        log.debug("Win32→POSIX: %s → %s", syscall, posix)
        return (posix, args or {})

    def translate_android(
        self, binder_call: str, args: Optional[dict] = None
    ) -> tuple:
        """Translate an Android Binder call to its POSIX equivalent.

        Args:
            binder_call: Android API/Binder call name.
            args:        Optional argument dict.

        Returns:
            Tuple of (posix_name, args_dict).
        """
        posix = self.ANDROID_BINDER_TO_POSIX.get(binder_call, "UNKNOWN")
        log.debug("Android→POSIX: %s → %s", binder_call, posix)
        return (posix, args or {})

    def list_win32_mappings(self) -> dict:
        """Return the full Win32 → POSIX translation table."""
        return dict(self.WIN32_TO_POSIX)

    def list_android_mappings(self) -> dict:
        """Return the full Android Binder → POSIX translation table."""
        return dict(self.ANDROID_BINDER_TO_POSIX)


# ---------------------------------------------------------------------------
# LinuxCompat
# ---------------------------------------------------------------------------

class LinuxCompat:
    """Runs Linux ELF binaries natively on Umer OS.

    TODAY: Direct subprocess execution (Umer OS runs on a Linux kernel today).
    FUTURE: Isolated chroot namespace with resource quotas.
    """

    def launch(
        self,
        exe_path: str,
        args: Optional[List[str]] = None,
        env: Optional[dict] = None,
        sandbox: bool = _SANDBOX_DEFAULT,
    ) -> ContainerInstance:
        """Launch a Linux ELF binary.

        Args:
            exe_path: Path to the ELF binary.
            args:     Command-line arguments.
            env:      Environment variables (None = inherit current env).

        Returns:
            ContainerInstance wrapping the running process.

        Raises:
            FileNotFoundError: If exe_path does not exist.
        """
        _require_launch_capability(sandbox)
        if not os.path.isfile(exe_path):
            raise FileNotFoundError(f"ELF binary not found: '{exe_path}'.")
        cmd = [exe_path] + (args or [])
        safe_env = _sanitize_env(env)
        preexec = _sandbox_preexec() if (sandbox and os.name == "posix") else None
        if sandbox and os.name != "posix":
            raise RuntimeError(
                "sandbox=True requested but POSIX namespace/quota isolation is "
                "unavailable on this platform; refusing unsandboxed launch."
            )
        proc = subprocess.Popen(
            cmd,
            env=safe_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=preexec,
        )
        return ContainerInstance(app_path=exe_path, app_type=APP_TYPE_LINUX, process=proc)


# ---------------------------------------------------------------------------
# WineShim
# ---------------------------------------------------------------------------

class WineShim:
    """Runs Windows PE binaries via Wine (LGPL).

    TODAY: Checks Wine availability and launches via subprocess.
    EXPERIMENTAL: Per-app wineprefix isolation.
    FUTURE: DirectX → Vulkan (DXVK) integration.
    """

    def __init__(self, wineprefix_base: str = "~/.umer/wine") -> None:
        self._base = os.path.expanduser(wineprefix_base)
        self._wine = shutil.which("wine")
        if self._wine:
            log.info("WineShim: Wine found at '%s'.", self._wine)
        else:
            log.warning("WineShim: Wine not installed. "
                        "Install with: sudo apt install wine64")

    @property
    def wine_available(self) -> bool:
        """Return True if Wine is installed on the host."""
        return self._wine is not None

    def setup_prefix(self, app_id: str) -> str:
        """Create (or return existing) wineprefix for an application.

        Args:
            app_id: Unique application identifier (used as subdirectory name).

        Returns:
            Path to the wineprefix directory.
        """
        prefix = os.path.join(self._base, app_id)
        os.makedirs(prefix, exist_ok=True)
        return prefix

    def run(
        self,
        exe_path:  str,
        app_id:    str = "default",
        args:      Optional[List[str]] = None,
        sandbox:   bool = _SANDBOX_DEFAULT,
    ) -> ContainerInstance:
        """Run a Windows .exe via Wine.

        Args:
            exe_path: Path to the .exe file.
            app_id:   Application ID (determines wineprefix).
            args:     Extra arguments for the executable.

        Returns:
            ContainerInstance wrapping the Wine process.

        Raises:
            EnvironmentError: If Wine is not installed.
            FileNotFoundError: If exe_path does not exist.
        """
        if not self.wine_available:
            raise EnvironmentError(
                "Wine is not installed. Cannot run Windows applications."
            )
        if not os.path.isfile(exe_path):
            raise FileNotFoundError(f"Windows executable not found: '{exe_path}'.")

        _require_launch_capability(sandbox)
        prefix = self.setup_prefix(app_id)
        env    = {**_sanitize_env(None), "WINEPREFIX": prefix}
        cmd    = [self._wine, exe_path] + (args or [])
        preexec = _sandbox_preexec() if (sandbox and os.name == "posix") else None
        if sandbox and os.name != "posix":
            raise RuntimeError(
                "sandbox=True requested but POSIX namespace/quota isolation is "
                "unavailable on this platform; refusing unsandboxed Wine launch."
            )

        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=preexec,
        )
        log.info("WineShim: launched '%s' (prefix=%s).", exe_path, prefix)
        return ContainerInstance(app_path=exe_path, app_type=APP_TYPE_WINDOWS, process=proc)

    def list_installed_apps(self) -> List[str]:
        """Return list of app IDs with existing wineprefixes."""
        try:
            return [d for d in os.listdir(self._base)
                    if os.path.isdir(os.path.join(self._base, d))]
        except OSError:
            return []


# ---------------------------------------------------------------------------
# AndroidContainer
# ---------------------------------------------------------------------------

class AndroidContainer:
    """Runs Android APKs via ADB / QEMU stub.

    TODAY:   Stub that simulates APK installation records.
    EXPERIMENTAL: Real QEMU user-mode or ADB adb push / am start.
    FUTURE:  Full Waydroid-style LXC container with Android image.
    """

    def __init__(self, adb_path: Optional[str] = None) -> None:
        self._adb = adb_path or shutil.which("adb")
        self._installed: Dict[str, str] = {}  # package_name → apk_path
        if self._adb:
            log.info("AndroidContainer: ADB found at '%s'.", self._adb)
        else:
            log.warning("AndroidContainer: ADB not found — running in stub mode.")

    @property
    def adb_available(self) -> bool:
        """Return True if ADB is available on the host."""
        return self._adb is not None

    def install_apk(self, apk_path: str) -> str:
        """Register an APK for installation (stub).

        Args:
            apk_path: Path to the .apk file.

        Returns:
            Simulated package name derived from the APK filename.

        Raises:
            FileNotFoundError: If apk_path does not exist.
        """
        if not os.path.isfile(apk_path):
            raise FileNotFoundError(f"APK not found: '{apk_path}'.")
        pkg = os.path.splitext(os.path.basename(apk_path))[0].replace(" ", ".")
        self._installed[pkg] = apk_path
        log.info("AndroidContainer: APK '%s' registered as '%s'.", apk_path, pkg)
        return pkg

    def launch_app(self, package_name: str, sandbox: bool = _SANDBOX_DEFAULT) -> ContainerInstance:
        """Launch an installed Android application.

        TODAY: Returns a stub ContainerInstance (no real process).
        EXPERIMENTAL: Use ADB `adb shell am start` when ADB is available.

        Args:
            package_name: Package name returned by ``install_apk()``.

        Returns:
            ContainerInstance representing the running app.

        Raises:
            RuntimeError: If the package is not installed.
        """
        if package_name not in self._installed:
            raise RuntimeError(
                f"Package '{package_name}' not installed. "
                "Call install_apk() first."
            )
        apk_path = self._installed[package_name]

        if self._adb:
            # EXPERIMENTAL: real ADB launch
            _require_launch_capability(sandbox)
            safe_env = _sanitize_env(None)
            preexec = _sandbox_preexec() if (sandbox and os.name == "posix") else None
            if sandbox and os.name != "posix":
                raise RuntimeError(
                    "sandbox=True requested but POSIX namespace/quota isolation "
                    "is unavailable; refusing unsandboxed ADB launch."
                )
            try:
                proc = subprocess.Popen(
                    [self._adb, "shell", "am", "start", "-n",
                     f"{package_name}/.MainActivity"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=safe_env,
                    preexec_fn=preexec,
                )
                return ContainerInstance(
                    app_path=apk_path,
                    app_type=APP_TYPE_ANDROID,
                    process=proc,
                )
            except Exception as exc:
                log.error("ADB launch failed: %s", exc)

        # Stub mode
        log.info("AndroidContainer: launching '%s' (stub — no real process).",
                 package_name)
        return ContainerInstance(app_path=apk_path, app_type=APP_TYPE_ANDROID)

    def list_installed(self) -> List[str]:
        """Return list of installed package names."""
        return list(self._installed.keys())

    def bridge_notification(self, package: str, message: str) -> None:
        """Simulate an Android notification bridge to Umer OS notification center.

        EXPERIMENTAL: Would forward to Umer OS notification daemon via IPC.

        Args:
            package: Package name sending the notification.
            message: Notification text.
        """
        log.info("Notification from '%s': %s", package, message)


# ---------------------------------------------------------------------------
# ContainerEngine
# ---------------------------------------------------------------------------

class ContainerEngine:
    """Top-level universal application container manager.

    Detects application type from file extension and routes to the
    appropriate sub-system (WineShim, AndroidContainer, LinuxCompat).

    Args:
        wineprefix_base: Base directory for per-app Wine prefixes.
    """

    _TYPE_MAP = {
        ".exe":  APP_TYPE_WINDOWS,
        ".msi":  APP_TYPE_WINDOWS,
        ".apk":  APP_TYPE_ANDROID,
        ".xapk": APP_TYPE_ANDROID,
    }

    def __init__(self, wineprefix_base: str = "~/.umer/wine") -> None:
        self._wine    = WineShim(wineprefix_base)
        self._android = AndroidContainer()
        self._linux   = LinuxCompat()
        self._translator = SyscallTranslator()
        self._containers: Dict[str, ContainerInstance] = {}
        self._lock = threading.Lock()
        log.info("ContainerEngine initialised.")

    def detect_type(self, app_path: str) -> str:
        """Detect application type from file extension.

        Args:
            app_path: Path to the application binary or package.

        Returns:
            APP_TYPE_* string.
        """
        ext = os.path.splitext(app_path)[1].lower()
        return self._TYPE_MAP.get(ext, APP_TYPE_LINUX)

    def launch(
        self,
        app_path:  str,
        app_type:  Optional[str] = None,
        args:      Optional[List[str]] = None,
        sandbox:   bool = _SANDBOX_DEFAULT,
    ) -> ContainerInstance:
        """Launch an application in the appropriate container.

        Args:
            app_path: Path to the binary, .exe, or .apk.
            app_type: Override auto-detection (APP_TYPE_* constant).
            args:     Extra CLI arguments (Linux/Windows only).

        Returns:
            ContainerInstance representing the running application.

        Raises:
            FileNotFoundError: If the application file does not exist.
            RuntimeError:      If the app type is unsupported.
        """
        atype = app_type or self.detect_type(app_path)

        if atype == APP_TYPE_WINDOWS:
            inst = self._wine.run(app_path, args=args, sandbox=sandbox)
        elif atype == APP_TYPE_ANDROID:
            pkg  = self._android.install_apk(app_path)
            inst = self._android.launch_app(pkg, sandbox=sandbox)
        elif atype in (APP_TYPE_LINUX, APP_TYPE_GAME):
            inst = self._linux.launch(app_path, args=args, sandbox=sandbox)
        else:
            raise RuntimeError(f"Unsupported application type: '{atype}'.")

        with self._lock:
            self._containers[inst.container_id] = inst
        return inst

    def list_containers(self) -> List[dict]:
        """Return status info for all running containers.

        Returns:
            List of resource usage dicts.
        """
        with self._lock:
            containers = list(self._containers.values())
        return [c.resource_usage() for c in containers]

    def stop(self, container_id: str) -> bool:
        """Stop a container by its ID.

        Args:
            container_id: ContainerInstance.container_id value.

        Returns:
            True if found and stopped, False otherwise.
        """
        with self._lock:
            inst = self._containers.get(container_id)
        if inst is None:
            return False
        inst.terminate()
        return True

    def get_status(self, container_id: str) -> Optional[dict]:
        """Return status dict for a container, or None if not found."""
        with self._lock:
            inst = self._containers.get(container_id)
        return inst.resource_usage() if inst else None

    @property
    def wine(self) -> WineShim:
        """Access the WineShim sub-system directly."""
        return self._wine

    @property
    def android(self) -> AndroidContainer:
        """Access the AndroidContainer sub-system directly."""
        return self._android

    @property
    def translator(self) -> SyscallTranslator:
        """Access the SyscallTranslator."""
        return self._translator
