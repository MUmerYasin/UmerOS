#!/usr/bin/env python3
"""
Umer OS Bootloader Simulation
Displays legal waiver, gets user consent, then launches the kernel.
"""

import sys
import time
import subprocess



def show_legal_warning():
    print("=" * 60)
    print("  Umer OS - Hybrid Quantum / AI Operating System")
    print("=" * 60)
    print()
    print("WARNING: This is a prototype simulation running on your current OS.")
    print("By proceeding, you acknowledge that:")
    print("- This software is experimental and may void warranties.")
    print("- Your existing OS and data are not affected; Umer OS runs as a simulation.")
    print("- The developers assume no liability for any consequences.")
    print()
    response = input("Do you agree and wish to continue? (yes/no): ")
    if response.lower() != "yes":
        print("Boot aborted.")
        sys.exit(0)
    print("Consent recorded. Starting Umer OS...\n")
    time.sleep(1)


def system_check():
    print("[BOOT] Running system checks...")
    import platform
    print(f"[BOOT] Platform: {platform.system()} {platform.release()}")
    print(f"[BOOT] Python version: {sys.version}")
    # Simulate hardware checks
    print("[BOOT] Memory: OK (simulated)")
    print("[BOOT] Storage: OK (simulated)")
    time.sleep(1)


if __name__ == "__main__":
    show_legal_warning()
    system_check()
    print("[BOOT] Loading Umer Hybrid Quantum Kernel...")
    try:
        from umer_kernel import main as kernel_main
        kernel_main()
    except ImportError:
        print("ERROR: umer_kernel.py not found. Ensure all OS modules are in the same directory.")
        sys.exit(1)