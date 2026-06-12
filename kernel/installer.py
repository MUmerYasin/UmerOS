#!/usr/bin/env python3
"""
Umer OS Installer / Executive Script
Copies OS modules and creates a simulated installation.
"""

import os
import sys
import shutil
import textwrap

def legal_disclaimer():
    print("=" * 70)
    print(" Umer OS - Installation Wizard")
    print("=" * 70)
    print()
    print("WARNING: This prototype installs Umer OS as a simulation environment.")
    print("It will NOT replace your current operating system, but it will copy")
    print("the necessary Python files into a folder named 'umer_os'.")
    print()
    print("By continuing, you agree that:")
    print("- This software may void warranties of your device.")
    print("- The developers are not liable for any damages or data loss.")
    print("- You accept all risks associated with experimental software.")
    print()
    consent = input("Do you agree? (yes/no): ")
    if consent.lower() != "yes":
        print("Installation cancelled.")
        sys.exit(0)

def install_files(target_dir="umer_os"):
    print(f"\nInstalling Umer OS to '{target_dir}'...")
    os.makedirs(target_dir, exist_ok=True)
    modules = [
        "bootloader.py",
        "umer_kernel.py",
        "quantum_sim.py",
        "umer_ai.py",
        "gui.py",
        "container_engine.py",
        "security.py",
        "qfs.py",
        "installer.py",
    ]
    for mod in modules:
        if os.path.exists(mod):
            shutil.copy(mod, os.path.join(target_dir, mod))
            print(f"  Copied {mod}")
        else:
            print(f"  WARNING: {mod} not found, skipping.")
    # Create a config file
    with open(os.path.join(target_dir, "umer_os.conf"), "w") as f:
        f.write("version=1.0.0\n")
        f.write("quantum_simulation=True\n")
    print("\nInstallation complete. You can now run 'python bootloader.py' from the 'umer_os' folder.")

if __name__ == "__main__":
    legal_disclaimer()
    install_files()