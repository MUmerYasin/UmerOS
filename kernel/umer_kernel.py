#!/usr/bin/env python3
"""
Umer Hybrid Quantum Kernel (Simulation)
Complete microkernel with all stages integrated using Claude-quality subsystems.
Stages:
Stage 2: Scheduler, Memory, IPC, Capabilities, Quantum
Stage 3: AI Orchestration, Compatibility Containers
Stage 4: QFS, VFS, Post-Quantum Crypto, Sandbox
Stage 5: Networking, Cloud/OTA, Fluidic Shell
Stage 6: Package Manager, Driver Framework, SDK

MERGE NOTE: Incorporates enhanced AI/Quantum logic from 'umer_kernel1.py'
- AIResourceManager now includes prediction logic.
- QuantumScheduler simulation is integrated into the main scheduler loop.
"""
import sys
import asyncio
import os
import logging
import time
import random # Needed for the enhanced AI logic
import secrets # Needed for crypto

# --- STAGE 2: Core Kernel Subsystems ---
# NOTE: Import paths assume the correct folder structure and __init__.py files.
# If modules like 'scheduler' don't exist yet, their logic might be simulated here.
# Placeholder for scheduler logic (could be defined within this file if needed)
class TaskState:
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"

class Task:
    def __init__(self, pid, name, priority=1.0):
        self.pid = pid
        self.name = name
        self.priority = priority
        self.state = TaskState.READY
        self.cpu_time = 0.0

class NullAIManager:
    async def predict_task_success(self, task): return 0.5

# Placeholder scheduler logic based on the original complex structure
class HybridScheduler:
    def __init__(self, quantum_simulator=None):
        self._tasks = {}
        self._lock = asyncio.Lock()
        self._ai_manager = NullAIManager()
        self._quantum_sim = quantum_simulator # Injected quantum adapter
        self._running = False

    def set_ai_manager(self, ai_manager):
        self._ai_manager = ai_manager

    async def add_task(self, task):
        async with self._lock:
            self._tasks[task.pid] = task

    async def stop(self):
        self._running = False

    def __len__(self):
        return len(self._tasks)

# --- MERGED COMPONENT: Enhanced AIResourceManager from umer_kernel1.py ---
class AIResourceManager:
    """Simulates the Deep Learning AI that predicts and allocates resources."""
    def __init__(self, window=20, alpha=0.3):
        self.system_memory = 100.0  # Percentage
        self.cpu_usage = 0.0
        self.historical_data = {} # Store historical resource usage per PID
        self.prediction_window = window
        self.learning_rate = alpha

    def predict_allocation(self, tasks: list) -> dict:
        print("[AI Subsystem] Analyzing historical data and predicting resource needs...")
        allocations = {}
        for task_name in tasks:
            # Simulate AI prediction based on history or default range
            base_pred = self.historical_data.get(task_name, {}).get('avg_memory', 0)
            variance = 5.0 # Simulate some variance
            predicted_mem = max(1.0, min(100.0, base_pred + random.uniform(-variance, variance)))
            allocations[task_name] = round(predicted_mem, 2)
        return allocations

    def record_cpu(self, pid, usage):
        if pid not in self.historical_data:
            self.historical_data[pid] = {'cpu': [], 'ram': []}
        self.historical_data[pid]['cpu'].append(usage)
        if len(self.historical_data[pid]['cpu']) > self.prediction_window:
            self.historical_data[pid]['cpu'].pop(0) # Keep window size

    def record_ram(self, pid, usage_bytes):
        if pid not in self.historical_data:
            self.historical_data[pid] = {'cpu': [], 'ram': []}
        # Convert bytes to MB for easier handling
        usage_mb = usage_bytes / (1024 * 1024)
        self.historical_data[pid]['ram'].append(usage_mb)
        if len(self.historical_data[pid]['ram']) > self.prediction_window:
            self.historical_data[pid]['ram'].pop(0)

    async def predict_task_success(self, task: Task) -> float:
        """Enhanced prediction based on historical performance."""
        hist = self.historical_data.get(task.name, {})
        avg_cpu = sum(hist.get('cpu', [0])) / len(hist.get('cpu', [0])) if hist.get('cpu') else 0
        avg_ram = sum(hist.get('ram', [0])) / len(hist.get('ram', [0])) if hist.get('ram') else 0
        
        # Simple heuristic: Higher resource usage historically might mean lower success chance if resources are tight
        # This is a placeholder for a real ML model prediction
        success_chance = 0.9 - (avg_cpu / 100.0) * 0.1 - (avg_ram / 100.0) * 0.1
        return max(0.1, min(1.0, success_chance)) # Clamp between 0.1 and 1.0

# --- MERGED COMPONENT: Enhanced QuantumScheduler from umer_kernel1.py ---
class QuantumScheduler:
    """Simulates Superposition to process multiple tasks 'simultaneously'."""
    def __init__(self):
        self.entanglement_sync_active = True
        # Simulate quantum state overlap for tasks
        self._task_superposition_states = {}

    def execute_superposition(self, tasks_with_resources: dict):
        print(f"[Quantum Scheduler] Placing {len(tasks_with_resources)} tasks into superposition state...")
        time.sleep(0.1) # Simulate quantum processing time
        for task_name, allocated_resource in tasks_with_resources.items():
            # Simulate quantum effect: tasks might finish slightly faster due to parallel exploration
            effective_runtime = max(0.05, 0.1 - (allocated_resource / 100.0) * 0.05)
            time.sleep(effective_runtime)
            print(f"    -> [Q-State Executing] {task_name} (Allocated {allocated_resource}% resource)")
            # Update superposition state to reflect execution outcome
            self._task_superposition_states[task_name] = "Collapsed_Success"
        print("[Quantum Scheduler] Wave function collapsed. Tasks completed with Zero Error.")

# --- STAGE 3: AI & Compatibility (Placeholder) ---
class AIFirewall:
    def __init__(self): pass
class LocalAIAssistant:
    def __init__(self): pass

# --- STAGE 4: Filesystem & Crypto & Security (Placeholders) ---
class QFS: # Quantum File System (Placeholder)
    def mount(self, path): print(f"[QFS] Mounted at {path}")
    def stats(self): return {"compression_ratio": "90%"}

class VirtualFileSystem: # VFS (Placeholder)
    def __init__(self, underlying_fs): self.fs = underlying_fs
    def mkdir(self, path): print(f"[VFS] Created directory: {path}")
    def write_file(self, path, data): print(f"[VFS] Wrote file: {path}")
    def ls(self, path): return ["welcome.txt", "kernel.sig"]

class CryptoEngine: # Crypto (Placeholder)
    def random_bytes(self, n): import secrets; return secrets.token_bytes(n)
    def encrypt(self, data): return (b"nonce", data+b"_encrypted") # Dummy
    def decrypt(self, nonce, data): return data.rstrip(b'_encrypted') # Dummy
    def sign(self, data): return b"dummy_signature" # Dummy
    def verify(self, data, sig): return True # Dummy

class SecuritySandbox: # Sandbox (Using the improved version from security/sandbox.py)
    def __init__(self):
        self.processes = {}
    def register_process(self, pid, name, fs_root): 
        self.processes[pid] = {"name": name, "fs_root": fs_root}
        print(f"[SECURITY] Registered PID {pid} ('{name}') with fs_root='{fs_root}'")

# --- STAGE 5: Networking & Cloud (Placeholders) ---
class DNSResolver: pass
class HTTPClient: pass
class VPNTunnel:
    def __init__(self, crypto): self.crypto = crypto
    def connect(self, addr, port): print(f"[VPN] Connected to {addr}:{port}")
    def send(self, data): print(f"[VPN] Sent: {data}")
    def disconnect(self): print("[VPN] Disconnected")
class UpdateManager:
    def __init__(self, crypto_engine): self.crypto = crypto_engine
    def run_update_pipeline(self): print("[OTA] Update check completed.")

# --- STAGE 6: Packages, Drivers, SDK (Placeholders) ---
class MockPackageManager:
    def install(self, pkg_name): print(f"[PKG] Installed '{pkg_name}'")
class DriverManager:
    def load_all_defaults(self): print("[DRIVER] Loaded default drivers")
class BuildTool:
    def __init__(self, vfs): self.vfs = vfs
    def scaffold(self, name, custom_app_code): print(f"[SDK] Scaffolded app: {name}")
    def package(self, name): print(f"[SDK] Packaged app: {name}"); return f"{name}_pkg_info"

# --- STAGE 7: UI Shell (FIXED) ---
class FluidicShell:
    def __init__(self, kernel): self.kernel = kernel
    def start(self, interactive=True):
        if interactive:
            print("\n[KERNEL] System Idle. Waiting for user input. Type 'exit' to shutdown, 'status' for kernel stats.")
            # Use asyncio.run_coroutine_threadsafe if input is blocking,
            # or run the listener in the existing event loop using a task.
            # For simplicity here, we'll run the listener loop directly.
            asyncio.create_task(self._listen_for_input_async()) # Create task in current loop

    async def _listen_for_input_async(self):
        """Asynchronous version of the input listener."""
        while self.kernel.running:
            try:
                print("UmerOS@root:~# ", end='', flush=True)
                import sys
                # Note: Using standard input in an async loop like this is blocking.
                # A true async solution requires aioconsole or similar.
                # For this integration, we proceed with the blocking input.
                try:
                    cmd = input("").strip().lower()
                    if cmd == 'exit':
                        print("[KERNEL] Shutting down safely...")
                        self.kernel.request_shutdown() # Signal shutdown
                        return # Exit the input loop
                    elif cmd == 'status':
                        stats = self.kernel.status()
                        print(f"[KERNEL STATUS] Uptime: {stats['uptime_seconds']}s, Tasks: {stats['scheduler_tasks']}, Running: {stats['running']}")
                    elif cmd == 'ai_predict':
                        incoming_tasks = ["UI_Render_Engine", "AI_Background_Trainer"]
                        resource_map = self.kernel.ai_manager.predict_allocation(incoming_tasks)
                        print(f"[AI] Predicted Allocations: {resource_map}")
                    elif cmd == 'quantum_run':
                        incoming_tasks = ["UI_Render_Engine", "AI_Background_Trainer"]
                        resource_map = self.kernel.ai_manager.predict_allocation(incoming_tasks)
                        self.kernel.q_scheduler.execute_superposition(resource_map)
                    # --- NEW COMMAND ADDED HERE ---
                    elif cmd == 'gui_start' or cmd == 'startx':
                        print("[KERNEL] Switching to GUI mode...")
                        # Call the new kernel method to launch the GUI
                        await self.kernel.start_gui_shell()
                        print("[KERNEL] Returned from GUI launch attempt. Kernel still running.")
                    # --- END NEW COMMAND ---
                    else:
                        print(f"[KERNEL] Unknown command: {cmd}")
                except EOFError: # Handle Ctrl+D (EOF)
                    print("\n[KERNEL] Received EOF. Shutting down...")
                    self.kernel.request_shutdown() # Signal shutdown
                    return # Exit the input loop
            except Exception as e:
                print(f"[SHELL] Error in input loop: {e}")
                break # Exit loop on error

# -------------------------------------------
    # async def _listen_for_input_async(self):
    #     """Asynchronous version of the input listener."""
    #     while self.kernel.running:
    #         try:
    #             # For async input, we might need a different approach or a helper library like aioconsole.
    #             # For now, we keep the blocking input but handle shutdown correctly within the loop.
    #             # A proper async input would require aioconsole: `pip install aioconsole`
    #             # from aioconsole import ainput
    #             # cmd = await ainput("UmerOS@root:~# ")
                
    #             # For this fix, we simulate non-blocking behavior poorly by polling.
    #             # The better fix is to handle shutdown differently in the synchronous input loop.
    #             # Let's revert to a synchronous loop but handle shutdown correctly.
    #             print("UmerOS@root:~# ", end='', flush=True)
    #             import select
    #             import sys
    #             # Note: select is Unix-specific. This won't work on Windows easily.
    #             # A robust solution requires a dedicated async input library.
    #             # For this fix, we will handle the exit command by setting a flag.
                
    #             # Simpler synchronous fix: Handle shutdown gracefully within the sync loop.
    #             while self.kernel.running:
    #                 try:
    #                     cmd = input("").strip().lower()
    #                     if cmd == 'exit':
    #                         print("[KERNEL] Shutting down safely...")
    #                         # DO NOT use asyncio.run here!
    #                         # Instead, just call the shutdown coroutine directly or set a flag.
    #                         # The boot sequence will handle shutdown when the loop exits naturally.
    #                         self.kernel.request_shutdown() # Signal shutdown
    #                         return # Exit the input loop
    #                     elif cmd == 'status':
    #                         stats = self.kernel.status()
    #                         print(f"[KERNEL STATUS] Uptime: {stats['uptime_seconds']}s, Tasks: {stats['scheduler_tasks']}, Running: {stats['running']}")
    #                     elif cmd == 'ai_predict':
    #                         # Example of triggering the enhanced AI prediction
    #                         incoming_tasks = ["UI_Render_Engine", "AI_Background_Trainer"]
    #                         resource_map = self.kernel.ai_manager.predict_allocation(incoming_tasks)
    #                         print(f"[AI] Predicted Allocations: {resource_map}")
    #                     elif cmd == 'quantum_run':
    #                         # Example of triggering the enhanced Quantum execution
    #                         incoming_tasks = ["UI_Render_Engine", "AI_Background_Trainer"]
    #                         resource_map = self.kernel.ai_manager.predict_allocation(incoming_tasks)
    #                         self.kernel.q_scheduler.execute_superposition(resource_map)
    #                     else:
    #                         print(f"[KERNEL] Unknown command: {cmd}")
    #                     print("UmerOS@root:~# ", end='', flush=True) # Print prompt again
    #                 except EOFError: # Handle Ctrl+D (EOF)
    #                     print("\n[KERNEL] Received EOF. Shutting down...")
    #                     self.kernel.request_shutdown() # Signal shutdown
    #                     return # Exit the input loop
    #         except Exception as e:
    #             print(f"[SHELL] Error in input loop: {e}")
    #             break # Exit loop on error



# ------------------------------------------
    # OLD SYNC METHOD (BROKEN)
    # def listen_for_input(self):
    #     while self.kernel.running:
    #         try:
    #             cmd = input("UmerOS@root:~# ").strip().lower()
    #             if cmd == 'exit':
    #                 print("[KERNEL] Shutting down safely...")
    #                 # THIS WAS THE PROBLEM: asyncio.run(self.kernel.shutdown())
    #                 # It should be: self.kernel.request_shutdown() and let the boot loop handle it.
    #                 self.kernel.request_shutdown()
    #                 break
    #             elif cmd == 'status':
    #                 stats = self.kernel.status()
    #                 print(f"[KERNEL STATUS] Uptime: {stats['uptime_seconds']}s, Tasks: {stats['scheduler_tasks']}, Running: {stats['running']}")
    #             elif cmd == 'ai_predict':
    #                 incoming_tasks = ["UI_Render_Engine", "AI_Background_Trainer"]
    #                 resource_map = self.kernel.ai_manager.predict_allocation(incoming_tasks)
    #                 print(f"[AI] Predicted Allocations: {resource_map}")
    #             elif cmd == 'quantum_run':
    #                 incoming_tasks = ["UI_Render_Engine", "AI_Background_Trainer"]
    #                 resource_map = self.kernel.ai_manager.predict_allocation(incoming_tasks)
    #                 self.kernel.q_scheduler.execute_superposition(resource_map)
    #             else:
    #                 print(f"[KERNEL] Unknown command: {cmd}")
    #         except EOFError: # Handle Ctrl+D (EOF)
    #             print("\n[KERNEL] Received EOF. Shutting down...")
    #             # asyncio.run(self.kernel.shutdown()) # BROKEN
    #             self.kernel.request_shutdown() # CORRECT
    #             break

# --- Main UmerKernel Class ---
log = logging.getLogger("UmerOS.Kernel")
PAGE_SIZE = 4096 # Standard 4 KiB page
_DEFAULT_RAM = (4 * 1024 * 1024 * 1024 // PAGE_SIZE) * PAGE_SIZE # 4 GiB simulated

class UmerKernel:
    def __init__(self):
        print("[KERNEL] Initializing Umer Hybrid Quantum Kernel...")
        self._boot_time = time.monotonic()
        
        # --- MERGED LOGIC: Use the enhanced classes ---
        self.ai_manager = AIResourceManager(window=20, alpha=0.3)
        self.q_scheduler = QuantumScheduler() # The enhanced one from umer_kernel1.py

        # --- STAGE 2: Core Kernel Subsystems ---
        # Using the simplified scheduler logic here, incorporating the enhanced AI
        self.scheduler = HybridScheduler(quantum_simulator=self.q_scheduler) # Pass quantum ref if needed by scheduler
        self.memory = type('MemoryManager', (), {'stats': lambda self: {"used": "1GB", "total": "4GB"}, 'allocate': lambda self, size, pid: 0x1000, 'free': lambda self, ptr, pid: None})() # Placeholder
        self.ipc = type('IPCBus', (), {'start': lambda self: print("[IPC] Bus started"), 'register': lambda self, pid: print(f"[IPC] Registered PID {pid}")})() # Placeholder
        self.capabilities = type('CapabilityManager', (), {'register': lambda self, pid: None, 'grant_many': lambda self, pid, caps: None})() # Placeholder

        # --- STAGE 3: AI & Compatibility ---
        self.ai_firewall = AIFirewall()
        self.ai_assistant = LocalAIAssistant()

        # --- STAGE 4: Filesystem & Crypto & Security ---
        self.qfs = QFS()
        self.vfs = VirtualFileSystem(self.qfs)
        self.crypto = CryptoEngine()
        self.sandbox = SecuritySandbox()

        # --- STAGE 5: Networking & Cloud ---
        self.dns = DNSResolver()
        self.http = HTTPClient()
        self.vpn = VPNTunnel(self.crypto)
        self.ota = UpdateManager(self.crypto)

        # --- STAGE 6: Packages, Drivers, SDK ---
        self.pkg = MockPackageManager()
        self.drivers = DriverManager()
        self.sdk = BuildTool(vfs=self.vfs)

        self.running = False
        self._shutdown_requested = False # Flag to signal shutdown

    def request_shutdown(self):
        """Public method for components (like the shell) to request a shutdown."""
        self._shutdown_requested = True

    async def boot(self):
        print("[KERNEL] Boot sequence initiated.")
        self.running = True

        # Inject the enhanced AI manager into the scheduler
        self.scheduler.set_ai_manager(self.ai_manager)

        # Start core services
        self.ipc.start()
        self.ipc.register(0) # Register kernel (PID 0)

        # --- DEMONSTRATE MERGED FUNCTIONALITY ---
        print("\n--- DEMONSTRATING MERGED AI/QUANTUM LOGIC ---")
        incoming_tasks = [
            "UI_Render_Engine",
            "Universal_Container_Android",
            "Universal_Container_Windows",
            "AI_Background_Trainer"
        ]
        print(f"[KERNEL] Simulating incoming process requests: {incoming_tasks}")

        # Step 1: AI Resource Prediction (Enhanced from umer_kernel1.py)
        resource_map = self.ai_manager.predict_allocation(incoming_tasks)

        # Step 2: Quantum-Inspired Execution (Enhanced from umer_kernel1.py)
        self.q_scheduler.execute_superposition(resource_map)
        print("--- END DEMONSTRATION ---\n")


        # --- Remainder of Boot Sequence (as per original complex kernel) ---
        # Register init process
        init_pid = 1000
        self.capabilities.register(init_pid)
        self.ipc.register(init_pid)
        init_task = Task(pid=init_pid, name="init", priority=1.0)
        await self.scheduler.add_task(init_task)
        self.sandbox.register_process(init_pid, "init", fs_root="/")

        # Mount filesystem
        print("[KERNEL] Mounting Quantum File System via VFS...")
        self.qfs.mount("/")
        self.vfs.mkdir("/system")
        self.vfs.mkdir("/user")
        self.vfs.mkdir("/tmp")
        self.vfs.mkdir("/packages")
        self.vfs.write_file("/system/welcome.txt", b"Welcome to Umer OS v2.0.0-Quantum")

        # Crypto verification (placeholder)
        secret = b"Top-secret quantum state data"
        nonce, ciphertext = self.crypto.encrypt(secret)
        self.vfs.write_file("/system/secrets.enc", ciphertext)
        decrypted = self.crypto.decrypt(nonce, ciphertext)
        assert decrypted == secret, "Crypto round-trip failed!"
        print("[KERNEL] Crypto round-trip verification: PASS")

        # Load drivers
        print("[KERNEL] Loading hardware drivers...")
        self.drivers.load_all_defaults()

        # VPN demo
        self.vpn.connect("10.0.0.1", port=51820)
        self.vpn.send(b"hello from kernel")
        self.vpn.disconnect()

        # OTA update check
        self.ota.run_update_pipeline()

        # --- Kernel loop (simplified for this merge) ---
        await self.run_loop()

        # --- Launch interactive shell ---
        interactive = sys.stdin.isatty()
        shell = FluidicShell(self)
        shell.start(interactive=interactive)

        # --- MAIN KERNEL LOOP (handles shutdown request) ---
        while self.running and not self._shutdown_requested:
            # Simulate some background kernel activity
            await asyncio.sleep(0.1)
        
        # Shutdown requested by shell or external signal
        print("\n[KERNEL] Shutdown signal received. Cleaning up...")
        await self.shutdown()


    async def run_loop(self):
        """Boot-time scheduler demonstration loop."""
        print("[KERNEL] Entering main execution loop...")
        ticks = 0
        max_ticks = 3
        async with self.scheduler._lock:
            ready_tasks = [t for t in self.scheduler._tasks.values() if t.state == TaskState.READY]
            for task in ready_tasks[:max_ticks]:
                print(f"[SCHEDULER] Executing Task: {task.name} (PID {task.pid}, Priority {task.priority})")
                # Simulate recording resource usage for AI
                self.ai_manager.record_cpu(task.pid, 0.15)
                self.ai_manager.record_ram(task.pid, 256 * 1024 * 1024)
                # Get AI prediction for this task
                predicted = await self.ai_manager.predict_task_success(task)
                print(f"[AI] Predicted success for {task.name} (PID {task.pid}): {predicted:.2f}")
                ticks += 1
        if ticks == 0:
            print("[SCHEDULER] No READY tasks at boot. Idle.")
        print("[KERNEL] Boot-time kernel loop complete.")

    def uptime(self) -> float:
        return time.monotonic() - self._boot_time

    def status(self) -> dict:
        return {
            "uptime_seconds": round(self.uptime(), 3),
            "scheduler_tasks": len(self.scheduler),
            "memory": self.memory.stats(),
            "running": self.running,
        }

    async def shutdown(self) -> None:
        self.running = False
        await self.scheduler.stop()
        print("[KERNEL] UmerKernel shut down cleanly.")
    
    async def start_gui_shell(self):
        """Attempts to launch the Flutter-based GUI shell."""
        print("[KERNEL] Attempting to launch UmerOS GUI Shell...")
        # Import the launcher script
        try:
            # Use importlib to run the script as a module
            import importlib.util
            import subprocess
            import os

            # Get the path to the launcher script
            launcher_script_path = os.path.join(os.path.dirname(__file__), "..", "ui", "launch_gui.py")
            launcher_script_path = os.path.abspath(launcher_script_path)

            print(f"[KERNEL] Using launcher script: {launcher_script_path}")

            # Option 1: Run as a subprocess (Recommended for isolation)
            print("[KERNEL] Launching GUI in a separate process...")
            process = subprocess.Popen([sys.executable, launcher_script_path])
            print(f"[KERNEL] GUI process started with PID {process.pid}. Return to kernel shell to manage it.")
            # Note: The kernel doesn't wait for the GUI process to finish.
            # The GUI runs independently. The user might need to close the GUI window
            # or use another mechanism (like a signal/file check) to know when it stops.
            # For now, we just start it and return control.

            # Option 2: Run inline (Less recommended, might block kernel)
            # spec = importlib.util.spec_from_file_location("launch_gui", launcher_script_path)
            # launcher_module = importlib.util.module_from_spec(spec)
            # spec.loader.exec_module(launcher_module)
            # launcher_module.main() # This would block the kernel until GUI closes

        except ImportError as e:
            print(f"[KERNEL] Failed to import GUI launcher: {e}")
        except FileNotFoundError:
            print(f"[KERNEL] GUI launcher script not found at expected location: {launcher_script_path}")
        except Exception as e:
            print(f"[KERNEL] An error occurred launching the GUI: {e}")

# Standalone execution check
if __name__ == "__main__":
    # Allows standalone testing of the kernel
    kernel = UmerKernel()
    try:
        asyncio.run(kernel.boot())
    except KeyboardInterrupt:
        print("\n[KERNEL] Interrupted. Shutting down...")
        # Need to get the running loop if one exists, or create one just for shutdown
        try:
            loop = asyncio.get_running_loop()
            # Schedule shutdown if inside a loop
            loop.create_task(kernel.shutdown())
        except RuntimeError: # No running loop
            # Run shutdown in a new loop
            asyncio.run(kernel.shutdown())

# -----------------------------------------------

# import sys
# import asyncio
# import os
# import logging
# import time
# import random # Needed for the enhanced AI logic

# # --- STAGE 2: Core Kernel Subsystems ---
# # NOTE: Import paths assume the correct folder structure and __init__.py files.
# # If modules like 'scheduler' don't exist yet, their logic might be simulated here.
# # Placeholder for scheduler logic (could be defined within this file if needed)
# class TaskState:
#     READY = "READY"
#     RUNNING = "RUNNING"
#     WAITING = "WAITING"

# class Task:
#     def __init__(self, pid, name, priority=1.0):
#         self.pid = pid
#         self.name = name
#         self.priority = priority
#         self.state = TaskState.READY
#         self.cpu_time = 0.0

# class NullAIManager:
#     async def predict_task_success(self, task): return 0.5

# # Placeholder scheduler logic based on the original complex structure
# class HybridScheduler:
#     def __init__(self, quantum_simulator=None):
#         self._tasks = {}
#         self._lock = asyncio.Lock()
#         self._ai_manager = NullAIManager()
#         self._quantum_sim = quantum_simulator # Injected quantum adapter
#         self._running = False

#     def set_ai_manager(self, ai_manager):
#         self._ai_manager = ai_manager

#     async def add_task(self, task):
#         async with self._lock:
#             self._tasks[task.pid] = task

#     async def stop(self):
#         self._running = False

#     def __len__(self):
#         return len(self._tasks)

# # --- MERGED COMPONENT: Enhanced AIResourceManager from umer_kernel1.py ---
# class AIResourceManager:
#     """Simulates the Deep Learning AI that predicts and allocates resources."""
#     def __init__(self, window=20, alpha=0.3):
#         self.system_memory = 100.0  # Percentage
#         self.cpu_usage = 0.0
#         self.historical_data = {} # Store historical resource usage per PID
#         self.prediction_window = window
#         self.learning_rate = alpha

#     def predict_allocation(self, tasks: list) -> dict:
#         print("[AI Subsystem] Analyzing historical data and predicting resource needs...")
#         allocations = {}
#         for task_name in tasks:
#             # Simulate AI prediction based on history or default range
#             base_pred = self.historical_data.get(task_name, {}).get('avg_memory', 0)
#             variance = 5.0 # Simulate some variance
#             predicted_mem = max(1.0, min(100.0, base_pred + random.uniform(-variance, variance)))
#             allocations[task_name] = round(predicted_mem, 2)
#         return allocations

#     def record_cpu(self, pid, usage):
#         if pid not in self.historical_data:
#             self.historical_data[pid] = {'cpu': [], 'ram': []}
#         self.historical_data[pid]['cpu'].append(usage)
#         if len(self.historical_data[pid]['cpu']) > self.prediction_window:
#             self.historical_data[pid]['cpu'].pop(0) # Keep window size

#     def record_ram(self, pid, usage_bytes):
#         if pid not in self.historical_data:
#             self.historical_data[pid] = {'cpu': [], 'ram': []}
#         # Convert bytes to MB for easier handling
#         usage_mb = usage_bytes / (1024 * 1024)
#         self.historical_data[pid]['ram'].append(usage_mb)
#         if len(self.historical_data[pid]['ram']) > self.prediction_window:
#             self.historical_data[pid]['ram'].pop(0)

#     async def predict_task_success(self, task: Task) -> float:
#         """Enhanced prediction based on historical performance."""
#         hist = self.historical_data.get(task.name, {})
#         avg_cpu = sum(hist.get('cpu', [0])) / len(hist.get('cpu', [0])) if hist.get('cpu') else 0
#         avg_ram = sum(hist.get('ram', [0])) / len(hist.get('ram', [0])) if hist.get('ram') else 0
        
#         # Simple heuristic: Higher resource usage historically might mean lower success chance if resources are tight
#         # This is a placeholder for a real ML model prediction
#         success_chance = 0.9 - (avg_cpu / 100.0) * 0.1 - (avg_ram / 100.0) * 0.1
#         return max(0.1, min(1.0, success_chance)) # Clamp between 0.1 and 1.0

# # --- MERGED COMPONENT: Enhanced QuantumScheduler from umer_kernel1.py ---
# class QuantumScheduler:
#     """Simulates Superposition to process multiple tasks 'simultaneously'."""
#     def __init__(self):
#         self.entanglement_sync_active = True
#         # Simulate quantum state overlap for tasks
#         self._task_superposition_states = {}

#     def execute_superposition(self, tasks_with_resources: dict):
#         print(f"[Quantum Scheduler] Placing {len(tasks_with_resources)} tasks into superposition state...")
#         time.sleep(0.1) # Simulate quantum processing time
#         for task_name, allocated_resource in tasks_with_resources.items():
#             # Simulate quantum effect: tasks might finish slightly faster due to parallel exploration
#             effective_runtime = max(0.05, 0.1 - (allocated_resource / 100.0) * 0.05)
#             time.sleep(effective_runtime)
#             print(f"    -> [Q-State Executing] {task_name} (Allocated {allocated_resource}% resource)")
#             # Update superposition state to reflect execution outcome
#             self._task_superposition_states[task_name] = "Collapsed_Success"
#         print("[Quantum Scheduler] Wave function collapsed. Tasks completed with Zero Error.")

# # --- STAGE 3: AI & Compatibility (Placeholder) ---
# class AIFirewall:
#     def __init__(self): pass
# class LocalAIAssistant:
#     def __init__(self): pass

# # --- STAGE 4: Filesystem & Crypto & Security (Placeholders) ---
# class QFS: # Quantum File System (Placeholder)
#     def mount(self, path): print(f"[QFS] Mounted at {path}")
#     def stats(self): return {"compression_ratio": "90%"}

# class VirtualFileSystem: # VFS (Placeholder)
#     def __init__(self, underlying_fs): self.fs = underlying_fs
#     def mkdir(self, path): print(f"[VFS] Created directory: {path}")
#     def write_file(self, path, data): print(f"[VFS] Wrote file: {path}")
#     def ls(self, path): return ["welcome.txt", "kernel.sig"]

# class CryptoEngine: # Crypto (Placeholder)
#     def random_bytes(self, n): import secrets; return secrets.token_bytes(n)
#     def encrypt(self, data): return (b"nonce", data+b"_encrypted") # Dummy
#     def decrypt(self, nonce, data): return data.rstrip(b'_encrypted') # Dummy
#     def sign(self, data): return b"dummy_signature" # Dummy
#     def verify(self, data, sig): return True # Dummy

# class SecuritySandbox: # Sandbox (Using the improved version from security/sandbox.py)
#     def __init__(self):
#         self.processes = {}
#     def register_process(self, pid, name, fs_root): 
#         self.processes[pid] = {"name": name, "fs_root": fs_root}
#         print(f"[SECURITY] Registered PID {pid} ('{name}') with fs_root='{fs_root}'")

# # --- STAGE 5: Networking & Cloud (Placeholders) ---
# class DNSResolver: pass
# class HTTPClient: pass
# class VPNTunnel:
#     def __init__(self, crypto): self.crypto = crypto
#     def connect(self, addr, port): print(f"[VPN] Connected to {addr}:{port}")
#     def send(self, data): print(f"[VPN] Sent: {data}")
#     def disconnect(self): print("[VPN] Disconnected")
# class UpdateManager:
#     def __init__(self, crypto_engine): self.crypto = crypto_engine
#     def run_update_pipeline(self): print("[OTA] Update check completed.")

# # --- STAGE 6: Packages, Drivers, SDK (Placeholders) ---
# class MockPackageManager:
#     def install(self, pkg_name): print(f"[PKG] Installed '{pkg_name}'")
# class DriverManager:
#     def load_all_defaults(self): print("[DRIVER] Loaded default drivers")
# class BuildTool:
#     def __init__(self, vfs): self.vfs = vfs
#     def scaffold(self, name, custom_app_code): print(f"[SDK] Scaffolded app: {name}")
#     def package(self, name): print(f"[SDK] Packaged app: {name}"); return f"{name}_pkg_info"

# # --- STAGE 7: UI Shell (Placeholder) ---
# class FluidicShell:
#     def __init__(self, kernel): self.kernel = kernel
#     def start(self, interactive=True):
#         if interactive:
#             print("\n[KERNEL] System Idle. Waiting for user input. Type 'exit' to shutdown, 'status' for kernel stats.")
#             self.listen_for_input()
#     def listen_for_input(self):
#         while self.kernel.running:
#             try:
#                 cmd = input("UmerOS@root:~# ").strip().lower()
#                 if cmd == 'exit':
#                     print("[KERNEL] Shutting down safely...")
#                     asyncio.run(self.kernel.shutdown())
#                     break
#                 elif cmd == 'status':
#                     stats = self.kernel.status()
#                     print(f"[KERNEL STATUS] Uptime: {stats['uptime_seconds']}s, Tasks: {stats['scheduler_tasks']}, Running: {stats['running']}")
#                 elif cmd == 'ai_predict':
#                     # Example of triggering the enhanced AI prediction
#                     incoming_tasks = ["UI_Render_Engine", "AI_Background_Trainer"]
#                     resource_map = self.kernel.ai_manager.predict_allocation(incoming_tasks)
#                     print(f"[AI] Predicted Allocations: {resource_map}")
#                 elif cmd == 'quantum_run':
#                     # Example of triggering the enhanced Quantum execution
#                     incoming_tasks = ["UI_Render_Engine", "AI_Background_Trainer"]
#                     resource_map = self.kernel.ai_manager.predict_allocation(incoming_tasks)
#                     self.kernel.q_scheduler.execute_superposition(resource_map)
#                 else:
#                     print(f"[KERNEL] Unknown command: {cmd}")
#             except EOFError: # Handle Ctrl+D (EOF)
#                 print("\n[KERNEL] Received EOF. Shutting down...")
#                 asyncio.run(self.kernel.shutdown())
#                 break


# # --- Main UmerKernel Class ---
# log = logging.getLogger("UmerOS.Kernel")
# PAGE_SIZE = 4096 # Standard 4 KiB page
# _DEFAULT_RAM = (4 * 1024 * 1024 * 1024 // PAGE_SIZE) * PAGE_SIZE # 4 GiB simulated

# class UmerKernel:
#     def __init__(self):
#         print("[KERNEL] Initializing Umer Hybrid Quantum Kernel...")
#         self._boot_time = time.monotonic()
        
#         # --- MERGED LOGIC: Use the enhanced classes ---
#         self.ai_manager = AIResourceManager(window=20, alpha=0.3)
#         self.q_scheduler = QuantumScheduler() # The enhanced one from umer_kernel1.py

#         # --- STAGE 2: Core Kernel Subsystems ---
#         # Using the simplified scheduler logic here, incorporating the enhanced AI
#         self.scheduler = HybridScheduler(quantum_simulator=self.q_scheduler) # Pass quantum ref if needed by scheduler
#         self.memory = type('MemoryManager', (), {'stats': lambda self: {"used": "1GB", "total": "4GB"}, 'allocate': lambda self, size, pid: 0x1000, 'free': lambda self, ptr, pid: None})() # Placeholder
#         self.ipc = type('IPCBus', (), {'start': lambda self: print("[IPC] Bus started"), 'register': lambda self, pid: print(f"[IPC] Registered PID {pid}")})() # Placeholder
#         self.capabilities = type('CapabilityManager', (), {'register': lambda self, pid: None, 'grant_many': lambda self, pid, caps: None})() # Placeholder

#         # --- STAGE 3: AI & Compatibility ---
#         self.ai_firewall = AIFirewall()
#         self.ai_assistant = LocalAIAssistant()

#         # --- STAGE 4: Filesystem & Crypto & Security ---
#         self.qfs = QFS()
#         self.vfs = VirtualFileSystem(self.qfs)
#         self.crypto = CryptoEngine()
#         self.sandbox = SecuritySandbox()

#         # --- STAGE 5: Networking & Cloud ---
#         self.dns = DNSResolver()
#         self.http = HTTPClient()
#         self.vpn = VPNTunnel(self.crypto)
#         self.ota = UpdateManager(self.crypto)

#         # --- STAGE 6: Packages, Drivers, SDK ---
#         self.pkg = MockPackageManager()
#         self.drivers = DriverManager()
#         self.sdk = BuildTool(vfs=self.vfs)

#         self.running = False

#     async def boot(self):
#         print("[KERNEL] Boot sequence initiated.")
#         self.running = True

#         # Inject the enhanced AI manager into the scheduler
#         self.scheduler.set_ai_manager(self.ai_manager)

#         # Start core services
#         self.ipc.start()
#         self.ipc.register(0) # Register kernel (PID 0)

#         # --- DEMONSTRATE MERGED FUNCTIONALITY ---
#         print("\n--- DEMONSTRATING MERGED AI/QUANTUM LOGIC ---")
#         incoming_tasks = [
#             "UI_Render_Engine",
#             "Universal_Container_Android",
#             "Universal_Container_Windows",
#             "AI_Background_Trainer"
#         ]
#         print(f"[KERNEL] Simulating incoming process requests: {incoming_tasks}")

#         # Step 1: AI Resource Prediction (Enhanced from umer_kernel1.py)
#         resource_map = self.ai_manager.predict_allocation(incoming_tasks)

#         # Step 2: Quantum-Inspired Execution (Enhanced from umer_kernel1.py)
#         self.q_scheduler.execute_superposition(resource_map)
#         print("--- END DEMONSTRATION ---\n")


#         # --- Remainder of Boot Sequence (as per original complex kernel) ---
#         # Register init process
#         init_pid = 1000
#         self.capabilities.register(init_pid)
#         self.ipc.register(init_pid)
#         init_task = Task(pid=init_pid, name="init", priority=1.0)
#         await self.scheduler.add_task(init_task)
#         self.sandbox.register_process(init_pid, "init", fs_root="/")

#         # Mount filesystem
#         print("[KERNEL] Mounting Quantum File System via VFS...")
#         self.qfs.mount("/")
#         self.vfs.mkdir("/system")
#         self.vfs.mkdir("/user")
#         self.vfs.mkdir("/tmp")
#         self.vfs.mkdir("/packages")
#         self.vfs.write_file("/system/welcome.txt", b"Welcome to Umer OS v2.0.0-Quantum")

#         # Crypto verification (placeholder)
#         secret = b"Top-secret quantum state data"
#         nonce, ciphertext = self.crypto.encrypt(secret)
#         self.vfs.write_file("/system/secrets.enc", ciphertext)
#         decrypted = self.crypto.decrypt(nonce, ciphertext)
#         assert decrypted == secret, "Crypto round-trip failed!"
#         print("[KERNEL] Crypto round-trip verification: PASS")

#         # Load drivers
#         print("[KERNEL] Loading hardware drivers...")
#         self.drivers.load_all_defaults()

#         # VPN demo
#         self.vpn.connect("10.0.0.1", port=51820)
#         self.vpn.send(b"hello from kernel")
#         self.vpn.disconnect()

#         # OTA update check
#         self.ota.run_update_pipeline()

#         # --- Kernel loop (simplified for this merge) ---
#         await self.run_loop()

#         # --- Launch interactive shell ---
#         interactive = sys.stdin.isatty()
#         shell = FluidicShell(self)
#         shell.start(interactive=interactive)


#     async def run_loop(self):
#         """Boot-time scheduler demonstration loop."""
#         print("[KERNEL] Entering main execution loop...")
#         ticks = 0
#         max_ticks = 3
#         async with self.scheduler._lock:
#             ready_tasks = [t for t in self.scheduler._tasks.values() if t.state == TaskState.READY]
#             for task in ready_tasks[:max_ticks]:
#                 print(f"[SCHEDULER] Executing Task: {task.name} (PID {task.pid}, Priority {task.priority})")
#                 # Simulate recording resource usage for AI
#                 self.ai_manager.record_cpu(task.pid, 0.15)
#                 self.ai_manager.record_ram(task.pid, 256 * 1024 * 1024)
#                 # Get AI prediction for this task
#                 predicted = await self.ai_manager.predict_task_success(task)
#                 print(f"[AI] Predicted success for {task.name} (PID {task.pid}): {predicted:.2f}")
#                 ticks += 1
#         if ticks == 0:
#             print("[SCHEDULER] No READY tasks at boot. Idle.")
#         print("[KERNEL] Boot-time kernel loop complete.")

#     def uptime(self) -> float:
#         return time.monotonic() - self._boot_time

#     def status(self) -> dict:
#         return {
#             "uptime_seconds": round(self.uptime(), 3),
#             "scheduler_tasks": len(self.scheduler),
#             "memory": self.memory.stats(),
#             "running": self.running,
#         }

#     async def shutdown(self) -> None:
#         self.running = False
#         await self.scheduler.stop()
#         print("[KERNEL] UmerKernel shut down cleanly.")

# # Standalone execution check
# if __name__ == "__main__":
#     # Allows standalone testing of the kernel
#     kernel = UmerKernel()
#     try:
#         asyncio.run(kernel.boot())
#     except KeyboardInterrupt:
#         print("\n[KERNEL] Interrupted. Shutting down...")
#         asyncio.run(kernel.shutdown())

# -------------------------------------------------------------
# import sys
# import asyncio
# import os
# import logging
# import time

# # ... other imports ...
# from kernel.scheduler import HybridScheduler, Task, TaskState, NullAIManager # <-- Make sure this line is correct
# from security.security import SecureBoot, IPCAuthenticator, AIBehavioralMonitor # <-- And this one
# # ... rest of the file ...


# # ── Claude-quality Kernel Subsystems ──────────────────────────────────────────
# from kernel.scheduler import HybridScheduler, Task, TaskState, NullAIManager
# from kernel.memory_manager import MemoryManager, PAGE_SIZE
# from kernel.ipc_bus import IPCBus, IPCMessage
# from kernel.capability_manager import (
#     CapabilityManager, SYSTEM_PID,
#     CAP_FS_READ, CAP_FS_WRITE, CAP_FS_ADMIN,
#     CAP_NET_SEND, CAP_NET_RECV,
#     CAP_AI_INFERENCE, CAP_PROC_SPAWN, CAP_PROC_KILL,
# )

# # ── Quantum Layer ─────────────────────────────────────────────────────────────
# from quantum.quantum_sim import QuantumCircuitSimulator, SuperpositionSchedulerAdapter

# # ── AI Layer ──────────────────────────────────────────────────────────────────
# from ai.umer_ai import AIResourceManager, NullAIResourceManager, AIFirewall, LocalAIAssistant

# # ── Filesystem ────────────────────────────────────────────────────────────────
# from fs.qfs import QFS, QuantumFileSystem
# from fs.vfs import VirtualFileSystem

# # ── Security ──────────────────────────────────────────────────────────────────
# from security.crypto_engine import CryptoEngine
# from security.sandbox import SecuritySandbox
# from security.security import SecureBoot, IPCAuthenticator, AIBehavioralMonitor

# # ── Networking ────────────────────────────────────────────────────────────────
# from network.dns_resolver import DNSResolver
# from network.http_client import HTTPClient
# from network.vpn_tunnel import VPNTunnel

# # ── Cloud / OTA ───────────────────────────────────────────────────────────────
# from cloud.ota_updater.update_system import UpdateManager

# # ── Packages / SDK / Drivers ──────────────────────────────────────────────────
# try:
#     from packages.umer_pkg import UmerPackageManager
# except ImportError:
#     UmerPackageManager = None

# from drivers.example_driver import DriverManager
# from sdk.build_tool import BuildTool

# # ── UI Shell ──────────────────────────────────────────────────────────────────
# from ui.fluidic_ui import FluidicShell

# # ── Compatibility ──────────────────────────────────────────────────────────────
# from compatibility.container import ZeroTrustContainer

# log = logging.getLogger("UmerOS.Kernel")

# # 4 GiB simulated RAM (page-aligned)
# _DEFAULT_RAM = (4 * 1024 * 1024 * 1024 // PAGE_SIZE) * PAGE_SIZE


# class MockPackageManager:
#     """Mock package manager for the ecosystem demonstration."""
#     def __init__(self, vfs, crypto):
#         self.vfs = vfs
#         self.crypto = crypto

#     def install(self, pkg_name):
#         print(f"[PKG] Verified package signature for '{pkg_name}'")
#         print(f"[PKG] Installed '{pkg_name}' into VFS /packages/{pkg_name}")
#         self.vfs.mkdir(f"/packages/{pkg_name}")


# class UmerKernel:
#     def __init__(self):
#         print("[KERNEL] Initializing Umer Microkernel...")
#         self._boot_time = time.monotonic()

#         # ── Quantum layer (attach to scheduler for quantum-inspired scoring) ──
#         self.quantum_sim = QuantumCircuitSimulator(n_qubits=4)
#         self.qsched_adapter = SuperpositionSchedulerAdapter(
#             QuantumCircuitSimulator(n_qubits=1)
#         )

#         # ── Stage 2: Core Kernel Subsystems (Claude-quality) ──────────────────
#         self.scheduler = HybridScheduler(quantum_simulator=self.qsched_adapter)
#         self.memory = MemoryManager(total_memory_bytes=_DEFAULT_RAM)
#         self.ipc = IPCBus()
#         self.capabilities = CapabilityManager()

#         # ── Stage 3: AI & Compatibility ───────────────────────────────────────
#         self.ai_manager = AIResourceManager(window=20, alpha=0.3)
#         self.ai_firewall = AIFirewall()
#         self.ai_assistant = LocalAIAssistant()

#         # ── Stage 4: Filesystem & Crypto ──────────────────────────────────────
#         self.qfs = QFS()
#         self.vfs = VirtualFileSystem(self.qfs)
#         self.crypto = CryptoEngine()
#         self.sandbox = SecuritySandbox()

#         # ── Stage 5: Networking & Cloud ───────────────────────────────────────
#         self.dns = DNSResolver()
#         self.http = HTTPClient()
#         self.vpn = VPNTunnel(self.crypto)
#         self.ota = UpdateManager(crypto_engine=self.crypto)

#         # ── Stage 6: Packages, Drivers, SDK ───────────────────────────────────
#         self.pkg = MockPackageManager(vfs=self.vfs, crypto=self.crypto)

#         self.drivers = DriverManager()
#         self.sdk = BuildTool(vfs=self.vfs)

#         # Track allocated memory pointers for proper freeing
#         self._mem_allocs: dict = {}  # pid -> list of (ptr, size)

#         self.running = False
#         print("[IPC] WARNING: Generated new random key. Set UMEROS_IPC_SECRET for persistence.")

#     def _allocate_for_pid(self, pid: int, size_mb: int):
#         """Helper: allocate MB of memory for a PID, tracking the pointer."""
#         size_bytes = size_mb * 1024 * 1024
#         try:
#             ptr = self.memory.allocate(size_bytes, pid)
#             if pid not in self._mem_allocs:
#                 self._mem_allocs[pid] = []
#             self._mem_allocs[pid].append((ptr, size_bytes))
#             return ptr
#         except MemoryError as e:
#             log.warning("Memory allocation for PID %d failed: %s", pid, e)
#             return None

#     def _free_for_pid(self, pid: int):
#         """Helper: free all memory allocations for a PID."""
#         for ptr, _ in self._mem_allocs.get(pid, []):
#             try:
#                 self.memory.free(ptr, pid)
#             except ValueError:
#                 pass
#         self._mem_allocs.pop(pid, None)

#     async def boot(self):
#         print("[KERNEL] Boot sequence initiated.")
#         self.running = True

#         # ── Inject AI manager into scheduler ──────────────────────────────────
#         self.scheduler.set_ai_manager(self.ai_manager)

#         # ── Start IPC bus ─────────────────────────────────────────────────────
#         self.ipc.start()
#         self.ipc.register(SYSTEM_PID)  # Register kernel (PID 0)

#         # ── Quantum entropy seed ───────────────────────────────────────────────
#         print("[KERNEL] Generating Quantum entropy seed...")
#         self.quantum_sim.apply_h(0)
#         seed_int = self.quantum_sim.measure()
#         seed = format(seed_int, "04b")
#         print(f"[KERNEL] Quantum Seed: {seed}")

#         # ── Register init process ──────────────────────────────────────────────
#         init_pid = 1000
#         self.capabilities.register(init_pid)
#         self.capabilities.grant_many(init_pid, [
#             CAP_FS_READ, CAP_FS_WRITE, CAP_FS_ADMIN,
#             CAP_NET_SEND, CAP_NET_RECV, CAP_AI_INFERENCE,
#             CAP_PROC_SPAWN, "HARDWARE"
#         ])
#         self.ipc.register(init_pid)
#         init_task = Task(pid=init_pid, name="init", priority=1.0)
#         await self.scheduler.add_task(init_task)
#         self._allocate_for_pid(init_pid, 128)
#         self.sandbox.register_process(init_pid, "init", fs_root="/")
#         print(f"[SECURITY] Registered PID {init_pid} ('init') with fs_root='/'")

#         # ── Mount filesystem ───────────────────────────────────────────────────
#         print("[KERNEL] Mounting Quantum File System via VFS...")
#         self.qfs.mount("/")
#         self.vfs.mkdir("/system")
#         self.vfs.mkdir("/user")
#         self.vfs.mkdir("/tmp")
#         self.vfs.mkdir("/packages")
#         self.vfs.write_file("/system/welcome.txt", b"Welcome to Umer OS v2.0.0-Quantum")
#         self.vfs.write_file("/system/kernel.sig", self.crypto.random_bytes(64))
#         self.vfs.write_file("/system/welcome_copy.txt", b"Welcome to Umer OS v2.0.0-Quantum")

#         # ── Crypto verification ────────────────────────────────────────────────
#         secret = b"Top-secret quantum state data"
#         nonce, ciphertext = self.crypto.encrypt(secret)
#         self.vfs.write_file("/system/secrets.enc", ciphertext)
#         decrypted = self.crypto.decrypt(nonce, ciphertext)
#         assert decrypted == secret, "Crypto round-trip failed!"
#         print("[KERNEL] Crypto round-trip verification: PASS")

#         sig = self.crypto.sign(b"kernel_boot_state_ok")
#         verified = self.crypto.verify(b"kernel_boot_state_ok", sig)
#         print(f"[KERNEL] Kernel state signature verified: {verified}")

#         # ── Load hardware drivers ──────────────────────────────────────────────
#         print("[KERNEL] Loading hardware drivers...")
#         self.drivers.load_all_defaults()

#         # ── VPN tunnel demo ────────────────────────────────────────────────────
#         self.vpn.connect("10.0.0.1", port=51820)
#         self.vpn.send(b"hello from kernel")
#         self.vpn.disconnect()

#         # ── OTA update check ───────────────────────────────────────────────────
#         self.ota.run_update_pipeline()

#         # ── Stage 7: Ecosystem Demonstration ──────────────────────────────────
#         print("[KERNEL] Demonstrating Umer OS Ecosystem (SDK & Package Manager)...")
#         chat_code = '''from sdk.app_template import UmerApp

# class UmerChat(UmerApp):
#     def __init__(self):
#         super().__init__("UmerChat", "1.0.0")

#     def on_start(self):
#         super().on_start()
#         print(f"[APP:{self.name}] Initiating secure AI channel...")
#         response = self.ask_ai("What is the core philosophy of Umer OS?")
#         print(f"[APP:{self.name}] AI: {response}")
#         self.write_file("/user/chat_log.txt", response.encode())
#         print(f"[APP:{self.name}] Chat logged to /user/chat_log.txt")
# '''
#         self.sdk.scaffold("UmerChat", custom_app_code=chat_code)
#         pkg_info = self.sdk.package("UmerChat")
#         self.pkg.install("umer-chat")

#         # Execute the app in the sandbox
#         print("[KERNEL] Executing installed app 'umer-chat'...")
#         try:
#             import types
#             mod = types.ModuleType("umer_chat_main")
#             exec(chat_code, mod.__dict__)
#             app_instance = mod.UmerChat()
#             app_instance.pid = 2000
#             app_instance.bind_kernel(self)
#             self.sandbox.register_process(2000, "umer-chat", fs_root="/user")
#             app_instance.on_start()
#         except Exception as e:
#             print(f"[KERNEL] App execution failed: {e}")

#         # ── Filesystem summary ─────────────────────────────────────────────────
#         print(f"[VFS] Root contents: {self.vfs.ls('/')}")
#         print(f"[QFS] Stats: {self.qfs.stats()}")

#         # ── Legacy container ───────────────────────────────────────────────────
#         legacy_pid = 1001
#         self.capabilities.register(legacy_pid)
#         # GRANT HARDWARE to avoid PermissionError
#         self.capabilities.grant_many(legacy_pid, ["HARDWARE"])
#         self.ipc.register(legacy_pid)
#         await self.scheduler.add_task(Task(pid=legacy_pid, name="legacy_app", priority=0.5))
#         self._allocate_for_pid(legacy_pid, 64)
#         self.sandbox.register_process(legacy_pid, "legacy_app", fs_root="/user")
#         container = ZeroTrustContainer(legacy_pid, self.capabilities)
#         # Catch permission error in case something else is checked
#         try:
#             container.execute_binary("/bin/bash", os_type="linux")
#         except PermissionError as e:
#             print(f"[Container] Access denied: {e}")

#         # ── Kernel loop ───────────────────────────────────────────────────────
#         await self.run_loop()

#         # ── Launch interactive shell ───────────────────────────────────────────
#         interactive = sys.stdin.isatty()
#         shell = FluidicShell(self)
#         shell.start(interactive=interactive)

#     async def run_loop(self):
#         """Boot-time scheduler demonstration loop.

#         Reads READY tasks directly from the scheduler to avoid the Python 3.14
#         asyncio._run_once empty-deque bug triggered by awaiting coroutines that
#         immediately yield with no pending callbacks.
#         """
#         print("[KERNEL] Entering main execution loop...")
#         ticks = 0
#         max_ticks = 3

#         # Snapshot READY tasks synchronously without awaiting internal asyncio sleep(0)
#         async with self.scheduler._lock:
#             ready_tasks = [
#                 t for t in self.scheduler._tasks.values()
#                 if t.state == TaskState.READY
#             ]

#         for task in ready_tasks[:max_ticks]:
#             print(f"[SCHEDULER] Executing Task: {task.name} (PID {task.pid}, Priority {task.priority})")
#             self.ai_manager.record_cpu(task.pid, 0.15)
#             self.ai_manager.record_ram(task.pid, 256 * 1024 * 1024)
#             predicted = self.ai_manager.predict_task_success(task)
#             if predicted < 0.3:
#                 print(f"[AI] Low success probability ({predicted:.2f}) for PID {task.pid}.")
#             ticks += 1

#         if ticks == 0:
#             print("[SCHEDULER] No READY tasks at boot. Idle.")

#         print("[KERNEL] Boot-time kernel loop complete.")

#     # ── Health / monitoring (cherry-picked from Claude kernel) ─────────────────

#     def uptime(self) -> float:
#         """Return seconds since the kernel was constructed.

#         Returns:
#             Float seconds since ``__init__``.
#         """
#         return time.monotonic() - self._boot_time

#     def status(self) -> dict:
#         """Return a health snapshot of the kernel.

#         Returns:
#             Dict with uptime_seconds, scheduler_tasks, memory stats, and
#             running flag.
#         """
#         mem = self.memory.stats()
#         return {
#             "uptime_seconds": round(self.uptime(), 3),
#             "scheduler_tasks": len(self.scheduler),
#             "memory": mem,
#             "running": self.running,
#         }

#     async def shutdown(self) -> None:
#         """Gracefully stop the scheduler and mark the kernel as halted.

#         Call after ``boot()`` completes (or from an external signal handler)
#         to release the background scheduling loop cleanly.
#         """
#         self.running = False
#         await self.scheduler.stop()
#         log.info("UmerKernel shut down cleanly.")