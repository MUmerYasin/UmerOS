"""
Umer OS Bootloader  [TODAY - Python simulation]
================================================
Simulates the Umer OS boot sequence on classical hardware.

TODAY (this file):
  - System compatibility check (Python version, platform, RAM).
  - Condensed legal warning display.
  - Kernel image integrity verification via SHA3-256.
  - Loads and initialises UmerKernel.

FUTURE (bare-metal, see boot/uefi_stub.c pseudocode):
  - UEFI entry point in C sets up paging + interrupts.
  - Jumps to Python interpreter entry point.
  - Verified Boot chain-of-trust enforced by SecureBoot module.

Run directly to test the boot sequence::

    python -m boot.bootloader

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import sys
import time
from typing import Optional

# Configure logging before any other imports
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("UmerOS.Boot")

# ── Banner ─────────────────────────────────────────────────────────────────

BANNER = r"""
  _   _                    ___  ____
 | | | |_ __ ___   ___ _ |   \/ ___|
 | | | | '_ ` _ \ / _ \ '__| |\___ \
 | |_| | | | | | |  __/ |  | | ___) |
  \___/|_| |_| |_|\___|_|  |_||____/

  Umer OS  v0.1.0-alpha  |  Hybrid Quantum AI Operating System
  Python-First • Zero-Trust • Quantum-Inspired
  ──────────────────────────────────────────────
"""

LEGAL_WARNING = """
  ┌──────────────────────────────────────────────────────┐
  │  NOTICE: Umer OS is experimental software.           │
  │  Use at your own risk. No warranty provided.         │
  │  Full EULA: run installer.py for complete terms.     │
  └──────────────────────────────────────────────────────┘
"""

# Minimum requirements
MIN_PYTHON = (3, 10)
MIN_RAM_MB = 512


# ---------------------------------------------------------------------------
# System check
# ---------------------------------------------------------------------------

def system_check() -> bool:
    """Verify the host system meets minimum Umer OS requirements.

    Checks Python version, platform compatibility, and available RAM.

    Returns:
        True if all checks pass, False if any critical check fails.
    """
    all_ok = True

    # Python version
    py = sys.version_info
    if py >= MIN_PYTHON:
        log.info("✓ Python %d.%d.%d", py.major, py.minor, py.micro)
    else:
        log.error(
            "✗ Python %d.%d found — Umer OS requires Python %d.%d+",
            py.major, py.minor, MIN_PYTHON[0], MIN_PYTHON[1],
        )
        all_ok = False

    # Platform
    arch = platform.machine()
    osys = platform.system()
    log.info("✓ Platform: %s / %s", osys, arch)
    if arch not in ("x86_64", "AMD64", "aarch64", "arm64", "armv7l"):
        log.warning("⚠ Architecture '%s' is not officially supported yet.", arch)

    # RAM (optional — psutil not guaranteed)
    try:
        import psutil  # type: ignore
        ram_mb = psutil.virtual_memory().total // (1024 * 1024)
        if ram_mb >= MIN_RAM_MB:
            log.info("✓ RAM: %d MiB available.", ram_mb)
        else:
            log.warning("⚠ RAM: %d MiB found — %d MiB recommended.", ram_mb, MIN_RAM_MB)
    except ImportError:
        log.info("  RAM check skipped (psutil not installed).")

    # GPU (informational)
    try:
        import subprocess  # noqa: PLC0415
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            log.info("✓ GPU: %s (NVIDIA)", result.stdout.strip().splitlines()[0])
    except Exception:  # noqa: BLE001
        log.info("  GPU: detection skipped (nvidia-smi not found).")

    return all_ok


# ---------------------------------------------------------------------------
# Kernel image verification
# ---------------------------------------------------------------------------

def verify_kernel(path: str, expected_hash: Optional[str] = None) -> bool:
    """Verify the kernel image SHA3-256 hash.

    When ``expected_hash`` is None, the check is skipped (development mode).
    In production, ``expected_hash`` is embedded in the signed boot manifest.

    Args:
        path:          Filesystem path to the kernel module/image.
        expected_hash: Expected 64-char hex SHA3-256 digest, or None to skip.

    Returns:
        True if verification passes (or is skipped), False on mismatch.
    """
    if not os.path.isfile(path):
        log.warning("Kernel path '%s' not found — skipping hash verification.", path)
        return True  # Permissive during prototype phase

    if expected_hash is None:
        log.info("Kernel hash verification: SKIPPED (development mode).")
        return True

    h = hashlib.sha3_256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
    except OSError as exc:
        log.error("Cannot read kernel image '%s': %s", path, exc)
        return False

    computed = h.hexdigest()
    ok = computed == expected_hash.lower()
    if ok:
        log.info("✓ Kernel image verified: %s…", computed[:16])
    else:
        log.error("✗ Kernel hash MISMATCH for '%s'!", path)
        log.error("  Expected: %s", expected_hash[:16])
        log.error("  Computed: %s", computed[:16])
    return ok


# ---------------------------------------------------------------------------
# Banner + legal notice
# ---------------------------------------------------------------------------

def show_banner() -> None:
    """Print the Umer OS startup banner."""
    print(BANNER)


def show_legal_warning() -> None:
    """Print the condensed legal/warranty notice."""
    print(LEGAL_WARNING)


# ---------------------------------------------------------------------------
# Kernel loader
# ---------------------------------------------------------------------------

def load_kernel(
    total_memory_bytes: int = 512 * 1024 * 1024,
    quantum_simulator=None,
):
    """Import and instantiate the Umer OS hybrid kernel.

    Args:
        total_memory_bytes: Simulated RAM to allocate (default 512 MiB).
            NOTE: The main UmerKernel hardcodes 4 GiB; this parameter is
            accepted for signature compatibility but not forwarded.
        quantum_simulator:  Optional QuantumCircuitSimulator for enhanced
                            scheduling (pass None for pure heuristic mode).
            NOTE: Not forwarded; the main UmerKernel creates its own simulator.

    Returns:
        Initialised UmerKernel instance (not yet running — call boot() to start).
    """
    # Ensure the repo root is on sys.path so kernel package is importable
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    try:
        from kernel.umer_kernel import UmerKernel  # noqa: PLC0415
    except ImportError as exc:
        log.error("Failed to import UmerKernel: %s", exc)
        raise

    log.info("Loading Umer Hybrid Quantum Kernel …")
    kernel = UmerKernel()
    log.info("✓ Kernel object created.")
    return kernel


# ---------------------------------------------------------------------------
# Main boot sequence
# ---------------------------------------------------------------------------

def main(
    kernel_path: Optional[str] = None,
    expected_hash: Optional[str] = None,
    ram_mb: int = 512,
) -> int:
    """Execute the Umer OS boot sequence.

    Steps:
      1. Show banner.
      2. Show legal warning.
      3. System compatibility check.
      4. Verify kernel image (if path provided).
      5. Load kernel.
      6. Print success message.

    Args:
        kernel_path:   Path to kernel module for hash check (None = skip).
        expected_hash: Expected kernel SHA3-256 hash (None = skip).
        ram_mb:        Simulated RAM in MiB to give the kernel.

    Returns:
        0 on success, 1 on failure.
    """
    t_start = time.monotonic()

    show_banner()
    show_legal_warning()

    log.info("=" * 60)
    log.info("Umer OS Boot Sequence Starting …")
    log.info("=" * 60)

    # Step 1: System check
    log.info("--- Phase 1: System Check ---")
    if not system_check():
        log.error("System check FAILED. Boot aborted.")
        return 1

    # Step 2: Kernel verification
    log.info("--- Phase 2: Kernel Integrity ---")
    kpath = kernel_path or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "kernel", "umer_kernel.py",
    )
    if not verify_kernel(kpath, expected_hash):
        log.error("Kernel verification FAILED. Boot aborted.")
        return 1

    # Step 3: Load kernel
    log.info("--- Phase 3: Kernel Load ---")
    try:
        kernel = load_kernel(total_memory_bytes=ram_mb * 1024 * 1024)
    except Exception as exc:
        log.error("Kernel load FAILED: %s", exc)
        return 1

    elapsed = round(time.monotonic() - t_start, 3)
    log.info("=" * 60)
    log.info("✓ Umer OS boot complete in %.3f s", elapsed)
    log.info("  Kernel uptime: %.3f s", kernel.uptime())
    log.info("  Status: %s", kernel.status())
    log.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
