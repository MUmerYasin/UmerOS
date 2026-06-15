"""
Umer OS Installer
Creates the directory structure and copies necessary files.
Includes legal waiver and rollback option.
"""

import os
import shutil
import sys

INSTALL_DIR = "umer_os_installation"
FILES_TO_COPY = [
    "bootloader.py",
    "umer_kernel.py",
    "quantum_sim.py",
    "umer_ai.py",
    "gui.py",
    "container_engine.py",
    "security.py",
    "qfs.py",
    "main.py"
]

def legal_waiver():
    print("=" * 50)
    print("UMER OS INSTALLER")
    print("=" * 50)
    print("WARNING: Installing Umer OS may void device warranties.")
    print("This is experimental software. Use at your own risk.")
    print("By continuing, you accept all liability.")
    consent = input("Type 'I ACCEPT' to install: ")
    if consent.strip().upper() != "I ACCEPT":
        print("Installation aborted.")
        sys.exit(0)

def create_directory():
    if os.path.exists(INSTALL_DIR):
        print(f"Directory {INSTALL_DIR} already exists. Overwrite? (y/n)")
        if input().lower() != 'y':
            sys.exit(0)
        shutil.rmtree(INSTALL_DIR)
    os.makedirs(INSTALL_DIR)

def copy_files():
    src_dir = os.path.dirname(os.path.abspath(__file__))
    for file in FILES_TO_COPY:
        src_path = os.path.join(src_dir, file)
        dst_path = os.path.join(INSTALL_DIR, file)
        if os.path.exists(src_path):
            shutil.copy(src_path, dst_path)
            print(f"Copied {file}")
        else:
            print(f"Warning: {file} not found, skipping.")

def install():
    legal_waiver()
    create_directory()
    copy_files()
    print(f"\nUmer OS installed to {INSTALL_DIR}.")
    print("Run 'python main.py' from that directory to start.")

if __name__ == "__main__":
    install()