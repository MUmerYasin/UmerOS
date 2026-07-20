# #!/usr/bin/env python3
# """
# Umer OS Bootloader Simulation
# Displays legal waiver, gets user consent, then launches the kernel.
# """

#!/usr/bin/env python3
"""
Umer OS Bootloader
Displays legal waiver, performs system checks, and launches the Umer Hybrid Quantum Kernel.
"""
import sys
import time
import asyncio
import platform

def show_legal_warning():
    print("=" * 70)
    print(" 🚀 Umer OS - Hybrid Quantum / AI Operating System")
    print("=" * 70)
    print()
    print("⚠️  WARNING: This is a prototype simulation running on your current OS.")
    print("By proceeding, you acknowledge that:")
    print("  1. This software is experimental and may void hardware warranties.")
    print("  2. Your existing OS and data are not affected; Umer OS runs as a simulation.")
    print("  3. The developers assume no liability for any consequences or data loss.")
    print()
    response = input("Do you agree and wish to continue? (yes/no): ").strip().lower()
    if response != "yes":
        print("\n[BOOT] Boot aborted by user.")
        sys.exit(0)
    print("\n✅ Consent recorded. Starting Umer OS...\n")
    time.sleep(1)

def system_check():
    print("[BOOT] Running hardware and environment checks...")
    print(f"[BOOT] Platform: {platform.system()} {platform.release()}")
    print(f"[BOOT] Python version: {sys.version.split()[0]}")
    print("[BOOT] Memory: OK (Simulated 4GB+ available for kernel)")
    print("[BOOT] Storage: OK (Quantum File System ready to mount)")
    print("[BOOT] Quantum Co-processor: Simulated (Qiskit/Cirq backend initialized)")
    time.sleep(1)

async def main():
    show_legal_warning()
    system_check()
    
    print("\n[BOOT] Loading Umer Hybrid Quantum Kernel...")
    try:
        # FIXED: Correctly import the UmerKernel class and run its async boot method
        from umer_kernel import UmerKernel
        
        kernel = UmerKernel()
        await kernel.boot()
        
    except ImportError as e:
        print(f"\n❌ ERROR: Failed to import UmerKernel.")
        print(f"Details: {e}")
        print("Ensure all OS modules are in the correct directory structure.")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 FATAL: Kernel panic during boot sequence!")
        import traceback
        traceback.print_exc3()
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[BOOT] Boot sequence interrupted by user (Ctrl+C).")
        sys.exit(0)

# import sys
# import time
# import subprocess



# def show_legal_warning():
#     print("=" * 60)
#     print("  Umer OS - Hybrid Quantum / AI Operating System")
#     print("=" * 60)
#     print()
#     print("WARNING: This is a prototype simulation running on your current OS.")
#     print("By proceeding, you acknowledge that:")
#     print("- This software is experimental and may void warranties.")
#     print("- Your existing OS and data are not affected; Umer OS runs as a simulation.")
#     print("- The developers assume no liability for any consequences.")
#     print()
#     response = input("Do you agree and wish to continue? (yes/no): ")
#     if response.lower() != "yes":
#         print("Boot aborted.")
#         sys.exit(0)
#     print("Consent recorded. Starting Umer OS...\n")
#     time.sleep(1)


# def system_check():
#     print("[BOOT] Running system checks...")
#     import platform
#     print(f"[BOOT] Platform: {platform.system()} {platform.release()}")
#     print(f"[BOOT] Python version: {sys.version}")
#     # Simulate hardware checks
#     print("[BOOT] Memory: OK (simulated)")
#     print("[BOOT] Storage: OK (simulated)")
#     time.sleep(1)


# if __name__ == "__main__":
#     show_legal_warning()
#     system_check()
#     print("[BOOT] Loading Umer Hybrid Quantum Kernel...")
#     try:
#         from umer_kernel import main as kernel_main
#         kernel_main()
#     except ImportError:
#         print("ERROR: umer_kernel.py not found. Ensure all OS modules are in the same directory.")
#         sys.exit(1)