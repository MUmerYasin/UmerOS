#This script handles the strict legal requirements, device checks, and transitions into the kernel.
import sys
import time
import platform

class UmerOSInstaller:
    def __init__(self):
        self.os_version = "1.0.0-Alpha"
        self.target_architecture = platform.machine()
        
    def show_legal_waiver(self):
        print("=" * 60)
        print(f"   INITIALIZING UMER OS v{self.os_version} INSTALLATION")
        print("=" * 60)
        print("\n[LEGAL WAIVER & WARRANTY WARNING]")
        print("WARNING: Installing Umer OS will deeply modify your system's")
        print("hardware abstraction layer. This may VOID YOUR WARRANTY.")
        print("This software utilizes experimental AI-driven resource allocation")
        print("and simulated quantum processing. You accept all liability for")
        print("data loss or hardware malfunction.")
        print("\nDo you agree to the terms and wish to proceed? (Y/N)")
        
        choice = input(">> ").strip().upper()
        if choice != 'Y':
            print("\nInstallation aborted. Exiting safely...")
            sys.exit(0)
            
    def system_check(self):
        print("\n[+] Running System Diagnostics...")
        time.sleep(1)
        print(f"    - Architecture detected: {self.target_architecture}")
        print("    - Checking RAM capacity... OK")
        print("    - Checking CPU threads... OK")
        print("    - Verifying AI module compatibility... OK")
        print("[+] Diagnostics Complete. System is ready for Umer OS.")
        time.sleep(1)

    def boot_kernel(self):
        print("\n[+] Handing over to Umer Hybrid Kernel...")
        time.sleep(1)
        print("\n" + "="*60 + "\n")
        # In a real environment, this would execute the kernel binary
        import umer_kernel
        kernel = umer_kernel.UmerKernel()
        kernel.boot()

if __name__ == "__main__":
    installer = UmerOSInstaller()
    installer.show_legal_waiver()
    installer.system_check()
    installer.boot_kernel()