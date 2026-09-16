"""H52 remediation: zero-trust gate + secret-safe env + opt-in POSIX sandbox for
foreign-binary launchers in compatibility/container_engine.py.

Assert-first: every anchor is checked for an exact expected count before writing.
"""
from pathlib import Path

F = Path(r"UmerOS/compatibility/container_engine.py")
text = F.read_text(encoding="utf-8")


def rep(old, new, n=1):
    global text
    assert text.count(old) == n, f"expected {n}x of anchor, found {text.count(old)}:\n{old!r}"
    text = text.replace(old, new, n)


# 1) imports (after the typing import)
rep(
    "from typing import Dict, List, Optional\n",
    "from typing import Dict, List, Optional\n\n"
    "try:\n"
    "    import resource  # POSIX only; unavailable on Windows\n"
    "except ImportError:  # pragma: no cover - non-POSIX host\n"
    "    resource = None\n\n"
    "from core.capability_gate import gate  # zero-trust capability gate (H52)\n",
)

# 2) sandbox section (after APP_TYPE_GAME declaration)
rep(
    'APP_TYPE_GAME    = "game"\n',
    'APP_TYPE_GAME    = "game"\n\n'
    "# ---------------------------------------------------------------------------\n"
    "# Foreign-binary launch sandbox  [zero-trust; H52]\n"
    "# ---------------------------------------------------------------------------\n"
    "# Capability required to launch any foreign binary (ELF/.exe/APK). Fail-closed\n"
    "# when a CapabilityManager is wired (or strict mode); permissive (warn + allow)\n"
    "# otherwise - matching the rest of the cap-gate cluster.\n"
    'CAP_FOREIGN_EXEC = "container.launch"\n\n'
    "# Default sandbox posture. Full namespace/seccomp isolation is the module's\n"
    "# FUTURE note; it is OFF by default so existing host-tool\n"
    "# launches (wine/adb) keep working. Enable per-launch via sandbox=True or\n"
    "# repo-wide via UMEROS_COMPAT_SANDBOX=1.\n"
    '_SANDBOX_DEFAULT = os.environ.get("UMEROS_COMPAT_SANDBOX", "0") == "1"\n\n'
    "# Env vars a foreign binary may inherit when no explicit env is supplied.\n"
    "_SAFE_ENV_ALLOW = (\n"
    '    "PATH", "HOME", "USER", "LOGNAME", "SHELL", "TERM",\n'
    '    "LANG", "LC_ALL", "DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR",\n'
    '    "TMPDIR", "TEMP", "TMP",\n'
    ")\n\n"
    "\n"
    "def _sanitize_env(explicit_env: Optional[dict]) -> Optional[dict]:\n"
    '    """Build a minimal, secret-safe environment for a foreign binary.\n\n'
    "    An explicit ``env`` is always honoured (caller intent). When ``env`` is None\n"
    "    we no longer blindly inherit the *full* parent environment (which would leak\n"
    "    trust material such as UMEROS_OTA_* keys / OPENROUTER_API_KEY into an\n"
    "    untrusted foreign process); we pass an allow-listed subset instead.\n"
    '    """\n'
    "    if explicit_env is not None:\n"
    "        return explicit_env\n"
    "    safe: dict = {}\n"
    "    for key in _SAFE_ENV_ALLOW:\n"
    "        val = os.environ.get(key)\n"
    "        if val is not None:\n"
    "            safe[key] = val\n"
    "    return safe\n\n"
    "\n"
    "def _sandbox_preexec(drop_uid: Optional[int] = None,\n"
    "                     drop_gid: Optional[int] = None,\n"
    "                     mem_mb: int = 512,\n"
    "                     cpu_seconds: int = 300) -> None:\n"
    '    """Best-effort privilege drop + resource quotas (POSIX; runs in the child).\n\n'
    "    Intended as ``preexec_fn`` for subprocess.Popen. Raises on any step so a\n"
    "    launch that *asked* to be sandboxed never silently runs unsandboxed.\n"
    "    Namespace isolation (unshare) is applied when available; the module's FUTURE\n"
    "    note is full chroot/OCI/seccomp-bpf.\n\n"
    "    Raises:\n"
    "        RuntimeError: If a requested isolation primitive is unavailable.\n"
    '    """\n'
    "    if resource is not None:\n"
    "        try:\n"
    "            resource.setrlimit(resource.RLIMIT_AS,\n"
    "                               (mem_mb * 1024 * 1024, mem_mb * 1024 * 1024))\n"
    "            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))\n"
    "            resource.setrlimit(resource.RLIMIT_NPROC, (256, 256))\n"
    "            resource.setrlimit(resource.RLIMIT_FSIZE,\n"
    "                               (1024 * 1024 * 1024, 1024 * 1024 * 1024))\n"
    "        except (ValueError, OSError) as exc:\n"
    '            raise RuntimeError(f"sandbox: rlimit apply failed: {exc}") from exc\n'
    "    if hasattr(os, \"unshare\"):\n"
    "        try:\n"
    "            # New mount + PID + network namespace (Linux). Best-effort isolation.\n"
    "            os.unshare(0x00020000 | 0x01000000 | 0x02000000)\n"
    "        except OSError as exc:\n"
    '            raise RuntimeError(f"sandbox: unshare failed: {exc}") from exc\n'
    "    if drop_gid is not None and hasattr(os, \"setgid\"):\n"
    "        try:\n"
    "            os.setgid(drop_gid)\n"
    "        except OSError as exc:\n"
    '            raise RuntimeError(f"sandbox: setgid failed: {exc}") from exc\n'
    "    if drop_uid is not None and hasattr(os, \"setuid\"):\n"
    "        try:\n"
    "            os.setuid(drop_uid)\n"
    "        except OSError as exc:\n"
    '            raise RuntimeError(f"sandbox: setuid failed: {exc}") from exc\n'
    "\n"
    "\n"
    "def _require_launch_capability(sandbox: bool) -> None:\n"
    '    """Zero-trust gate for foreign-binary launches (H52).\n\n'
    "    Fail-closed when a trust source is active (CapabilityManager wired or strict\n"
    "    mode): the launch capability must be granted. In a hard zero-trust posture\n"
    "    (gate.enforcing) an *unsandboxed* launch is refused outright - running\n"
    "    untrusted foreign code with the launcher's privileges is not permitted.\n"
    '    """\n'
    "    gate.require(CAP_FOREIGN_EXEC)\n"
    "    if gate.enforcing and not sandbox:\n"
    "        raise RuntimeError(\n"
    "            \"Refusing to launch foreign binary UNSANDBOXED while the zero-trust \"\n"
    "            \"posture is active (gate.enforcing). Enable sandbox=True or relax \"\n"
    "            \"strict mode.\"\n"
    "        )\n",
)

# 3) LinuxCompat.launch - add sandbox param
rep(
    "        env: Optional[dict] = None,\n    ) -> ContainerInstance:",
    "        env: Optional[dict] = None,\n        sandbox: bool = _SANDBOX_DEFAULT,\n    ) -> ContainerInstance:",
)
# 4) LinuxCompat.launch - body
rep(
    "        if not os.path.isfile(exe_path):\n"
    "            raise FileNotFoundError(f\"ELF binary not found: '{exe_path}'.\")\n"
    "        cmd  = [exe_path] + (args or [])\n"
    "        proc = subprocess.Popen(\n"
    "            cmd,\n"
    "            env=env,\n"
    "            stdout=subprocess.PIPE,\n"
    "            stderr=subprocess.PIPE,\n"
    "        )\n"
    "        return ContainerInstance(app_path=exe_path, app_type=APP_TYPE_LINUX, process=proc)",
    "        _require_launch_capability(sandbox)\n"
    "        if not os.path.isfile(exe_path):\n"
    "            raise FileNotFoundError(f\"ELF binary not found: '{exe_path}'.\")\n"
    "        cmd = [exe_path] + (args or [])\n"
    "        safe_env = _sanitize_env(env)\n"
    "        preexec = _sandbox_preexec() if (sandbox and os.name == \"posix\") else None\n"
    "        if sandbox and os.name != \"posix\":\n"
    "            raise RuntimeError(\n"
    "                \"sandbox=True requested but POSIX namespace/quota isolation is \"\n"
    "                \"unavailable on this platform; refusing unsandboxed launch.\"\n"
    "            )\n"
    "        proc = subprocess.Popen(\n"
    "            cmd,\n"
    "            env=safe_env,\n"
    "            stdout=subprocess.PIPE,\n"
    "            stderr=subprocess.PIPE,\n"
    "            preexec_fn=preexec,\n"
    "        )\n"
    "        return ContainerInstance(app_path=exe_path, app_type=APP_TYPE_LINUX, process=proc)",
)

# 5) WineShim.run - add sandbox param
rep(
    "        args:      Optional[List[str]] = None,\n    ) -> ContainerInstance:",
    "        args:      Optional[List[str]] = None,\n        sandbox:   bool = _SANDBOX_DEFAULT,\n    ) -> ContainerInstance:",
)
# 6) WineShim.run - body
rep(
    "        prefix = self.setup_prefix(app_id)\n"
    "        env    = {**os.environ, \"WINEPREFIX\": prefix}\n"
    "        cmd    = [self._wine, exe_path] + (args or [])\n\n"
    "        proc = subprocess.Popen(\n"
    "            cmd,\n"
    "            env=env,\n"
    "            stdout=subprocess.PIPE,\n"
    "            stderr=subprocess.PIPE,\n"
    "        )",
    "        _require_launch_capability(sandbox)\n"
    "        prefix = self.setup_prefix(app_id)\n"
    "        env    = {**_sanitize_env(None), \"WINEPREFIX\": prefix}\n"
    "        cmd    = [self._wine, exe_path] + (args or [])\n"
    "        preexec = _sandbox_preexec() if (sandbox and os.name == \"posix\") else None\n"
    "        if sandbox and os.name != \"posix\":\n"
    "            raise RuntimeError(\n"
    "                \"sandbox=True requested but POSIX namespace/quota isolation is \"\n"
    "                \"unavailable on this platform; refusing unsandboxed Wine launch.\"\n"
    "            )\n\n"
    "        proc = subprocess.Popen(\n"
    "            cmd,\n"
    "            env=env,\n"
    "            stdout=subprocess.PIPE,\n"
    "            stderr=subprocess.PIPE,\n"
    "            preexec_fn=preexec,\n"
    "        )",
)

# 7) AndroidContainer.launch_app - add sandbox param
rep(
    "    def launch_app(self, package_name: str) -> ContainerInstance:",
    "    def launch_app(self, package_name: str, sandbox: bool = _SANDBOX_DEFAULT) -> ContainerInstance:",
)
# 8) AndroidContainer.launch_app - adb block
rep(
    "            # EXPERIMENTAL: real ADB launch\n"
    "            try:\n"
    "                proc = subprocess.Popen(\n"
    "                    [self._adb, \"shell\", \"am\", \"start\", \"-n\",\n"
    "                     f\"{package_name}/.MainActivity\"],\n"
    "                    stdout=subprocess.PIPE,\n"
    "                    stderr=subprocess.PIPE,\n"
    "                )",
    "            # real ADB launch\n"
    "            _require_launch_capability(sandbox)\n"
    "            safe_env = _sanitize_env(None)\n"
    "            preexec = _sandbox_preexec() if (sandbox and os.name == \"posix\") else None\n"
    "            if sandbox and os.name != \"posix\":\n"
    "                raise RuntimeError(\n"
    "                    \"sandbox=True requested but POSIX namespace/quota isolation \"\n"
    "                    \"is unavailable; refusing unsandboxed ADB launch.\"\n"
    "                )\n"
    "            try:\n"
    "                proc = subprocess.Popen(\n"
    "                    [self._adb, \"shell\", \"am\", \"start\", \"-n\",\n"
    "                     f\"{package_name}/.MainActivity\"],\n"
    "                    stdout=subprocess.PIPE,\n"
    "                    stderr=subprocess.PIPE,\n"
    "                    env=safe_env,\n"
    "                    preexec_fn=preexec,\n"
    "                )",
)

F.write_text(text, encoding="utf-8")
print("H52_APPLY_OK")
