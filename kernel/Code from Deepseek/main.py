"""
Umer OS Main Entry Point
Runs bootloader, then starts kernel and GUI.
"""

from bootloader import boot
import threading
from umer_kernel import start as kernel_start
from gui import start_gui

if __name__ == "__main__":
    # Boot process (legal, check)
    boot()  # This blocks until consent given and checks pass.

    # Start kernel (non-blocking)
    kernel, kernel_thread = kernel_start()

    # Start GUI (blocking main thread)
    start_gui(kernel, kernel_thread)

    # After GUI closes, kernel thread will stop because kernel.running set to False
    print("Umer OS terminated.")