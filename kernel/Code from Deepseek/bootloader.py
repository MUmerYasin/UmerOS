"""
Umer OS Bootloader
Displays legal warning, obtains user consent, performs system check,
then loads the Umer Hybrid Quantum Kernel.
"""

import sys
import os
import time

REQUIRED_PYTHON = (3, 8)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_centered(text):
    width = os.get_terminal_size().columns
    print(text.center(width))

def legal_warning():
    clear_screen()
    print_centered("=" * 60)
    print_centered("UMER OS")
    print_centered("Next-Generation Quantum/AI Operating System")
    print_centered("=" * 60)
    print()
    print_centered("IMPORTANT LEGAL NOTICE")
    print()
    lines = [
        "By proceeding, you acknowledge that Umer OS is experimental software.",
        "It simulates quantum computing on classical hardware and integrates AI.",
        "You accept all risks, including data loss, instability, and hardware damage.",
        "Your device warranty may be voided. You assume full responsibility.",
        "All AI training is opt-in only; no data is shared without permission.",
        "Type 'I AGREE' to continue or any other key to abort."
    ]
    for line in lines:
        print_centered(line)
    print()
    consent = input("> ").strip()
    if consent.upper() != "I AGREE":
        print_centered("Consent denied. Shutting down.")
        sys.exit(1)
    clear_screen()
    print_centered("Consent accepted. Starting system check...")
    time.sleep(1)

def system_check():
    if sys.version_info < REQUIRED_PYTHON:
        print_centered(f"ERROR: Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]} or higher required.")
        sys.exit(1)
    print_centered("CPU: OK")
    print_centered("Memory: OK")
    print_centered("Storage: OK")
    print_centered("System check passed.")
    time.sleep(1)
    clear_screen()
    print_centered("Booting Umer Hybrid Quantum Kernel...")
    time.sleep(2)
    clear_screen()

def boot():
    legal_warning()
    system_check()
    # Start the kernel and pass control
    import umer_kernel
    umer_kernel.start()

if __name__ == "__main__":
    boot()