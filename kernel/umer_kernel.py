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

# ── kernel modules (NEW) ──────────────────────────────────────
from kernel.pid_allocator import PidAllocator, PID_SYSTEM, PID_INIT
from kernel.taint import KernelTaint, TAINT_OOM_KILL, TAINT_CRYPTO_FAIL, TAINT_SANDBOX_VIOLATION
from kernel.sysctl import SysctlRegistry, TYPE_INT, TYPE_BOOL
from kernel.panic import PanicNotifier, WarnCounter, OopsContext
from kernel.signals import SIGKILL, SIGTERM, SIGCHLD
from kernel.cgroup import CGroupManager
from kernel.audit import AuditLogger
from kernel.workqueue import WorkQueue
from kernel.cred import CredentialStore, Credentials, ROOT_UID
from kernel.reboot import RebootManager, SystemState
from kernel.resource import ResourceManager, IORESOURCE_MEM, IORESOURCE_IO
from kernel.softirq import SoftIRQManager, TaskletManager

# -- lost+found / fsck subsystem (lib/lostfound) --
try:
    from lib.lostfound import (
        FilesystemChecker as _LostFoundFsck,
        FilesystemPartition as _LostFoundPartition,
    )
    _LOSTFOUND_AVAILABLE = True
except ImportError:  # pragma: no cover - graceful degradation
    _LostFoundFsck = None
    _LostFoundPartition = None
    _LOSTFOUND_AVAILABLE = False

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

class VFSNode:
    def __init__(self, name, is_dir=False, owner="umer", group="umer", mode=None, is_symlink=False, symlink_target=None):
        self.name = name
        self.is_dir = is_dir
        self.content = ""
        self.children = {} if is_dir else None
        self.owner = owner
        self.group = group
        self.mode = mode if mode else ("rwxr-xr-x" if is_dir else "rw-r--r--")
        self.mtime = time.time()
        self.atime = time.time()
        self.is_symlink = is_symlink
        self.symlink_target = symlink_target

    @property
    def size(self):
        if self.is_dir:
            return 4096
        return len(self.content.encode('utf-8'))

class VirtualFileSystem:
    def __init__(self, underlying_fs):
        self.fs = underlying_fs
        self.root = VFSNode("/", is_dir=True)
        self.cwd = "/"
        # Pre-populate system files
        self.mkdir("/home", parents=True)
        self.mkdir("/home/umer", parents=True)
        self.mkdir("/etc", parents=True)
        self.mkdir("/bin", parents=True)
        self.mkdir("/usr/bin", parents=True)
        self.mkdir("/var/log", parents=True)
        self.mkdir("/tmp", parents=True)
        self.mkdir("/proc", parents=True)
        self.mkdir("/dev", parents=True)
        self.mkdir("/sys", parents=True)
        
        self.write_file("/etc/passwd", "root:x:0:0:root:/root:/bin/bash\numer:x:1000:1000:umer:/home/umer:/bin/bash\n")
        self.write_file("/etc/group", "root:x:0:\numer:x:1000:umer,sudo\nsudo:x:27:umer\n")
        self.write_file("/etc/hostname", "UmerOS-Node1\n")
        self.write_file("/etc/issue", "UmerOS v2.1.0 Quantum Kernel \\n \\l\n")
        self.touch("/var/log/dmesg.log")
        self.write_file("/var/log/dmesg.log", "[ 0.000000] UmerOS (root@buildhost) (gcc version 9.3.0)\n[ 0.000005] Command line: BOOT_IMAGE=/vmlinuz-umer root=QFS quiet\n")

        # Proc virtual files
        self.write_file("/proc/cpuinfo", "processor\t: 0\nvendor_id\t: QuantumGenuineIntel\ncpu family\t: 6\nmodel name\t: UmerOS Quantum AI Accelerator CPU @ 3.40GHz\nstepping\t: 3\ncpu MHz\t\t: 3400.000\ncache size\t: 16384 KB\nflags\t\t: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush dts acpi mmx fxsr sse sse2 ss ht tm pbe syscall nx pdpe1gb rdtscp lm constant_tsc art arch_perfmon pebs bts rep_good nopl xtopology nonstop_tsc cpuid tsc_known_freq pni pclmulqdq dtes64 monitor ds_cpl vmx smx est tm2 ssse3 sdbg fma cx16 xtpr pdcm pcid sse4_1 sse4_2 x2apic movbe popcnt tsc_deadline_timer aes xsave avx f16c rdrand lahf_lm abm 3dnowprefetch cpuid_fault epb cat_l3 cdp_l3 invpcid_single intel_pt ssbd mba ibrs ibpb stibp ibrs_enhanced tpr_shadow vnmi flexpriority ept vpid ept_ad fsgsbase tsc_adjust bmi1 avx2 smep bmi2 erms invpcid rtm mpx rdt_a avx512f avx512dq rdseed adx smap avx512ifma clflushopt clwb avx512cd sha_ni avx512bw avx512vl xsaveopt xsavec xgetbv1 xsaves split_lock_detect wbnoinvd dtherm ida arat pln pts hwp hwp_notify hwp_act_window hwp_epp hwp_pkg_req avx512_vbmi umip pku ospke avx512_vbmi2 gfni vaes vpclmulqdq avx512_vnni avx512_bitalg avx512_vpopcntdq rdpid fsrm md_clear flush_l1d arch_capabilities\n\n")
        self.write_file("/proc/meminfo", "MemTotal:        4194304 kB\nMemFree:         2097152 kB\nMemAvailable:    2883584 kB\nBuffers:          112230 kB\nCached:          1011846 kB\nSwapTotal:       2097152 kB\nSwapFree:        2097152 kB\nDirty:                 0 kB\nWriteback:             0 kB\nAnonPages:       1048576 kB\nMapped:           262144 kB\nShmem:             16384 kB\nSlab:             131072 kB\nSReclaimable:      98304 kB\nSUnreclaim:        32768 kB\nKernelStack:       16384 kB\nPageTables:        32768 kB\n")
        self.write_file("/proc/mounts", "qfs_root / qfs rw,relatime 0 0\nproc /proc proc rw,nosuid,nodev,noexec,relatime 0 0\nsysfs /sys sysfs rw,nosuid,nodev,noexec,relatime 0 0\ndevtmpfs /dev devtmpfs rw,nosuid,size=2000000k,nr_inodes=500000,mode=755 0 0\ntmpfs /run tmpfs rw,nosuid,nodev,mode=755 0 0\n")
        self.write_file("/proc/uptime", "3600.00 7100.00\n")
        self.write_file("/proc/version", "UmerOS (root@buildhost) (gcc version 9.3.0) #1 SMP PREEMPT 2026\n")

        self.cwd = "/home/umer"

    def _resolve(self, path):
        if not path: return self._resolve(self.cwd)
        if not path.startswith("/"):
            path = self.cwd.rstrip("/") + "/" + path
        
        parts = [p for p in path.split("/") if p and p != "."]
        
        # Resolve ..
        resolved_parts = []
        for p in parts:
            if p == "..":
                if resolved_parts: resolved_parts.pop()
            else:
                resolved_parts.append(p)
                
        curr = self.root
        for p in resolved_parts:
            if not curr.is_dir or p not in curr.children:
                return None, None # Node not found
            curr = curr.children[p]
        return curr, "/" + "/".join(resolved_parts)

    def cd(self, path):
        node, abs_path = self._resolve(path)
        if not node:
            raise FileNotFoundError("No such file or directory")
        if not node.is_dir:
            raise NotADirectoryError("Not a directory")
        self.cwd = abs_path if abs_path else "/"

    def ls(self, path=None):
        if path is None: path = self.cwd
        node, _ = self._resolve(path)
        if not node:
            raise FileNotFoundError("No such file or directory")
        if not node.is_dir:
            return [node.name]
        return list(node.children.keys())

    def mkdir(self, path, parents=False):
        if not path.startswith("/"):
            path = self.cwd.rstrip("/") + "/" + path
            
        parts = [p for p in path.split("/") if p]
        if not parts: return
        
        curr = self.root
        for i, part in enumerate(parts):
            if part not in curr.children:
                if i < len(parts) - 1 and not parents:
                    raise FileNotFoundError("Parent directory does not exist")
                new_node = VFSNode(part, is_dir=True)
                curr.children[part] = new_node
                curr = new_node
            else:
                curr = curr.children[part]
                if i == len(parts) - 1 and not parents:
                    raise FileExistsError("File exists")

    def touch(self, path):
        if not path.startswith("/"):
            path = self.cwd.rstrip("/") + "/" + path
            
        parts = [p for p in path.split("/") if p]
        if not parts: return
        
        parent_path = "/" + "/".join(parts[:-1])
        name = parts[-1]
        
        parent, _ = self._resolve(parent_path)
        if not parent or not parent.is_dir:
            raise FileNotFoundError("Parent directory does not exist")
            
        if name not in parent.children:
            parent.children[name] = VFSNode(name, is_dir=False)
        else:
            parent.children[name].mtime = time.time()

    def write_file(self, path, data):
        node, _ = self._resolve(path)
        if not node:
            self.touch(path)
            node, _ = self._resolve(path)
        if node.is_dir:
            raise IsADirectoryError("Is a directory")
        node.content = data
        node.mtime = time.time()

    def read_file(self, path):
        node, _ = self._resolve(path)
        if not node:
            raise FileNotFoundError("No such file or directory")
        if node.is_dir:
            raise IsADirectoryError("Is a directory")
        node.atime = time.time()
        return node.content

    def rmdir(self, path):
        self.rm(path, rmdir_only=True)
        
    def rm(self, path, recursive=False, rmdir_only=False):
        if not path.startswith("/"):
            path = self.cwd.rstrip("/") + "/" + path
            
        parts = [p for p in path.split("/") if p]
        if not parts:
            raise PermissionError("Cannot remove root")
            
        parent_path = "/" + "/".join(parts[:-1])
        name = parts[-1]
        
        parent, _ = self._resolve(parent_path)
        if not parent or name not in parent.children:
            raise FileNotFoundError("No such file or directory")
            
        target = parent.children[name]
        if rmdir_only and not target.is_dir:
            raise NotADirectoryError("Not a directory")
        if rmdir_only and target.is_dir and target.children:
            raise OSError("Directory not empty")
        if target.is_dir and not recursive and not rmdir_only:
            raise IsADirectoryError("Is a directory")
            
        del parent.children[name]

    def stat(self, path):
        node, abs_path = self._resolve(path)
        if not node:
            raise FileNotFoundError("No such file or directory")
        return {
            "name": node.name,
            "path": abs_path,
            "is_dir": node.is_dir,
            "size": node.size,
            "owner": node.owner,
            "group": node.group,
            "mode": node.mode,
            "mtime": node.mtime,
            "atime": node.atime,
        }

    def chmod(self, path, mode_str):
        node, _ = self._resolve(path)
        if not node:
            raise FileNotFoundError("No such file or directory")
        node.mode = mode_str

    def chown(self, path, owner, group=None):
        node, _ = self._resolve(path)
        if not node:
            raise FileNotFoundError("No such file or directory")
        node.owner = owner
        if group:
            node.group = group

    def cp(self, src_path, dest_path, recursive=False):
        src_node, _ = self._resolve(src_path)
        if not src_node:
            raise FileNotFoundError(f"cannot stat '{src_path}': No such file or directory")
        if src_node.is_dir and not recursive:
            raise IsADirectoryError(f"-r not specified; omitting directory '{src_path}'")

        dest_node, _ = self._resolve(dest_path)
        if dest_node and dest_node.is_dir:
            target_path = dest_path.rstrip("/") + "/" + src_node.name
        else:
            target_path = dest_path

        def _copy_recursive(node, target):
            if not node.is_dir:
                self.write_file(target, node.content)
                self.chmod(target, node.mode)
                self.chown(target, node.owner, node.group)
            else:
                self.mkdir(target, parents=True)
                for child_name, child_node in node.children.items():
                    _copy_recursive(child_node, target.rstrip("/") + "/" + child_name)

        _copy_recursive(src_node, target_path)

    def mv(self, src_path, dest_path):
        src_node, _ = self._resolve(src_path)
        if not src_node:
            raise FileNotFoundError(f"cannot stat '{src_path}': No such file or directory")
        
        self.cp(src_path, dest_path, recursive=True)
        self.rm(src_path, recursive=True)

    def find(self, path=".", name_pattern=None):
        start_node, base_abs_path = self._resolve(path)
        if not start_node:
            raise FileNotFoundError(f"'{path}': No such file or directory")
        
        results = []
        def _walk(node, current_path):
            if name_pattern is None or name_pattern in node.name or name_pattern == "*":
                results.append(current_path)
            if node.is_dir:
                for child_name, child_node in node.children.items():
                    sub = (current_path.rstrip("/") + "/" + child_name) if current_path != "/" else "/" + child_name
                    _walk(child_node, sub)

        _walk(start_node, base_abs_path if base_abs_path else "/")
        return results

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
    def __init__(self, kernel):
        self.kernel = kernel
        self.current_user = "umer"  # Default simulated user
        self.history = []
        
        # Load Command Registry
        try:
            from kernel.shell_commands import get_registry, CommandContext
            self.registry = get_registry()
            self.CommandContext = CommandContext
        except ImportError as e:
            print(f"[SHELL] Failed to load command registry: {e}")
            self.registry = {}
            self.CommandContext = None

    def start(self, interactive=True):
        if interactive:
            print("\n[KERNEL] System Idle. Waiting for user input. Type 'help' or 'exit'.")
            asyncio.create_task(self._listen_for_input_async())

    async def _listen_for_input_async(self):
        """Asynchronous version of the input listener."""
        while self.kernel.running:
            try:
                prompt_str = f"{self.current_user}@UmerOS:{self.kernel.vfs.cwd}# "
                print(prompt_str, end='', flush=True)
                
                try:
                    raw_input = input("").strip()
                    if not raw_input: continue
                    
                    self.history.append(raw_input)
                    parts = raw_input.split()
                    cmd = parts[0].lower()
                    args = parts[1:]

                    # Built-in kernel-level commands
                    if cmd == 'exit':
                        print("[KERNEL] Shutting down safely...")
                        self.kernel.request_shutdown()
                        return
                    elif cmd == 'status':
                        stats = self.kernel.status()
                        print(f"[KERNEL STATUS] Uptime: {stats['uptime_seconds']}s, Tasks: {stats['scheduler_tasks']}, Running: {stats['running']}")



                    # elif cmd == 'gui_start' or cmd == 'startx':
                    #     print("[KERNEL] Switching to GUI mode...")
                    #     await self.kernel.start_gui_shell()
                    #     print("[KERNEL] Returned from GUI.")

                    # # --- GUI COMMANDS ADDED HERE ---
                    # elif cmd == 'gui_start' or cmd == 'startx':
                    #     print("[KERNEL] Switching to GUI mode (Desktop default)...")
                    #     await self.kernel.start_gui_shell(mode='desktop')
                    #     print("[KERNEL] Returned from GUI launch attempt. Kernel still running.")
                    # elif cmd == 'gui_android':
                    #     print("[KERNEL] Attempting to launch GUI on Android device/emulator...")
                    #     await self.kernel.start_gui_shell(mode='android')
                    #     print("[KERNEL] Returned from Android GUI launch attempt.")
                    # elif cmd == 'gui_ios':
                    #     print("[KERNEL] Attempting to launch GUI on iOS simulator/device...")
                    #     await self.kernel.start_gui_shell(mode='ios') # Only works if kernel runs on macOS
                    #     print("[KERNEL] Returned from iOS GUI launch attempt.")
                    # elif cmd == 'gui_web':
                    #     print("[KERNEL] Attempting to launch GUI in Web Browser (Chrome)...")
                    #     await self.kernel.start_gui_shell(mode='web')
                    #     print("[KERNEL] Returned from Web GUI launch attempt.")
                    # # --- END GUI COMMANDS ---

                    # Dynamic Command Registry
                                        # --- GUI COMMANDS ADDED HERE ---
                    elif cmd == 'gui_start' or cmd == 'startx':
                        print("[KERNEL] Switching to GUI mode (Desktop default)...")
                        await self.kernel.start_gui_shell(mode='desktop')
                        print("[KERNEL] Returned from GUI launch attempt. Kernel still running.")
                    elif cmd == 'gui_android':
                        print("[KERNEL] Attempting to launch GUI on Android device/emulator...")
                        await self.kernel.start_gui_shell(mode='android')
                        print("[KERNEL] Returned from Android GUI launch attempt.")
                    elif cmd == 'gui_ios':
                        print("[KERNEL] Attempting to launch GUI on iOS simulator/device...")
                        await self.kernel.start_gui_shell(mode='ios') # Only works if kernel runs on macOS
                        print("[KERNEL] Returned from iOS GUI launch attempt.")
                    elif cmd == 'gui_web':
                        print("[KERNEL] Attempting to launch GUI in Web Browser (Chrome)...")
                        await self.kernel.start_gui_shell(mode='web')
                        print("[KERNEL] Returned from Web GUI launch attempt.")
                    # --- END GUI COMMANDS ---
                    elif cmd in self.registry:
                        ctx = self.CommandContext(self.kernel, self)
                        output = self.registry[cmd].execute(ctx, args)
                        if output:
                            print(output)
                    else:
                        print(f"{cmd}: command not found")
                        
                except EOFError:
                    print("\n[KERNEL] Received EOF. Shutting down...")
                    self.kernel.request_shutdown()
                    return
            except Exception as e:
                print(f"[SHELL] Error in input loop: {e}")
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

        # Root partition with its own isolated lost+found.
        if _LOSTFOUND_AVAILABLE:
            self.root_partition = _LostFoundPartition(
                name="qfs_root", mount_point="/",
            )
            self.lost_found = self.root_partition.lost_found
        else:
            self.root_partition = None
            self.lost_found = None

        # --- STAGE 5: Networking & Cloud ---
        self.dns = DNSResolver()
        self.http = HTTPClient()
        self.vpn = VPNTunnel(self.crypto)
        self.ota = UpdateManager(self.crypto)

        # --- STAGE 6: Packages, Drivers, SDK ---
        self.pkg = MockPackageManager()
        self.drivers = DriverManager()
        self.sdk = BuildTool(vfs=self.vfs)
        self.shell = FluidicShell(self)

        self.running = False
        self._shutdown_requested = False # Flag to signal shutdown

        # ── kernel subsystems (NEW) ──────────────────────────────
        # PID allocator: replaces hardcoded PIDs with cyclic allocation
        # kernel/pid.c — alloc_pid() with idr_alloc_cyclic.
        self.pid_allocator = PidAllocator()

        # Kernel taint: monotonic bitmask tracking integrity events.
        # kernel/panic.c — taint_flags[].
        self.taint = KernelTaint()

        # Sysctl: runtime-tunable parameters.
        # kernel/sysctl.c — /proc/sys/.
        self.sysctl = SysctlRegistry()
        self._register_default_sysctls()

        # Panic notifier chain: subsystems react to fatal events.
        # kernel/panic.c — panic_notifier_list.
        self.panic_notifier = PanicNotifier()

        # Warn counter: rate-limited warning with optional panic on overflow.
        # kernel/panic.c — check_panic_on_warn().
        self.warn_counter = WarnCounter(limit=0)  # 0 = unlimited by default

        # ── NEW: More subsystems ─────────────────────────────
        # Credential store: per-task uid/gid/caps with copy-on-write + override.
        # kernel/cred.c (David Howells).
        self.cred_store = CredentialStore()

        # Reboot manager: ordered reboot/halt/poweroff notifier chains.
        #  kernel/reboot.c.
        self.reboot = RebootManager()

        # Resource manager: I/O port / MMIO / IRQ / DMA region tracking.
        # kernel/resource.c (<linux/ioport.h>).
        self.resources = ResourceManager()

        # SoftIRQ manager + tasklets: deferred interrupt bottom-halves.
        # kernel/softirq.c.
        self.softirq = SoftIRQManager()
        self.tasklets = TaskletManager(self.softirq)

        log.info("kernel subsystems initialised "
                 "(PID allocator, taint, sysctl, panic notifier, "
                 "credentials, reboot, resources, softirq).")

    def request_shutdown(self):
        """Public method for components (like the shell) to request a shutdown."""
        self._shutdown_requested = True

    def _register_default_sysctls(self) -> None:
        """Register default runtime-tunable kernel parameters.

        ``kernel/sysctl.c`` — exposes knobs for
        panic timeout, hung-task threshold, and warn limit.
        """
        self.sysctl.register(
            "kernel.panic_timeout", 0,
            ptype=TYPE_INT, min_val=-1, max_val=600,
            desc="Seconds before auto-reboot after panic (0=hang, -1=skip)",
        )
        self.sysctl.register(
            "kernel.hung_task_timeout", 120,
            ptype=TYPE_INT, min_val=10, max_val=3600,
            desc="Seconds before declaring a task hung",
        )
        self.sysctl.register(
            "kernel.warn_limit", 0,
            ptype=TYPE_INT, min_val=0, max_val=100000,
            desc="Max warnings before kernel panic (0=unlimited)",
        )
        self.sysctl.register(
            "kernel.panic_on_taint", False,
            ptype=TYPE_BOOL,
            desc="Panic immediately if the kernel becomes tainted",
        )

    async def panic(self, message: str) -> None:
        """Handle a fatal kernel error.

        ``panic()``: logs the message, fires the panic
        notifier chain (so subsystems can dump state / zero keys), taints
        the kernel, then either hangs or reboots based on
        ``kernel.panic_timeout``.

        Args:
            message: Human-readable panic reason.
        """
        async with OopsContext():
            log.critical("KERNEL PANIC: %s", message)
            log.critical("Taint state: %s", self.taint.summary() or "(clean)")
            log.critical("Uptime: %.3fs", self.uptime())

        # Fire the notifier chain — subsystems dump state, zero keys, etc.
        await self.panic_notifier.fire(message)

        # Taint the kernel
        self.taint.add("TAINT_KERNEL_PANIC")

        # Decide recovery action based on panic_timeout
        timeout = self.sysctl.get("kernel.panic_timeout", 0)
        if timeout > 0:
            log.warning("Auto-rebooting in %d seconds...", timeout)
            await asyncio.sleep(timeout)
            # Attempt re-initialisation (in a real OS this would be a reboot)
            self.running = False
            self._shutdown_requested = True
        else:
            # Hang forever — set running False so the main loop exits
            log.error("Kernel halted. Manual restart required.")
            self.running = False
            self._shutdown_requested = True

    async def boot(self):
        print("[KERNEL] Boot sequence initiated.")
        self.running = True

        # ── transition system_state BOOTING → RUNNING,
        # start softirq daemon (ksoftirqd) and register root credentials.
        self.reboot.mark_running()
        await self.softirq.start()
        self.cred_store.register(PID_SYSTEM)  # kernel root cred

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
        # Register init process — use the PID allocator ( pid.c style)
        # instead of a hardcoded PID. Reserve PID_INIT (1000) for init.
        init_pid = PID_INIT
        self.pid_allocator._in_use.add(init_pid)  # mark as allocated
        self.capabilities.register(init_pid)
        self.ipc.register(init_pid) # Register kernel (PID 0)
        self.cred_store.register(init_pid)  # init gets root credentials
        init_task = Task(pid=init_pid, name="init", priority=1.0)
        await self.scheduler.add_task(init_task)
        self.sandbox.register_process(init_pid, "init", fs_root="/")
        log.info("Init process registered as PID %d (via PID allocator, root cred).", init_pid)

        # Mount filesystem
        print("[KERNEL] Mounting Quantum File System via VFS...")
        self.qfs.mount("/")

        # Root-partition fsck + lost+found setup ( FHS /lost+found).
        # mkfs.ext4 creates /lost+found with preallocated blocks; fsck then
        # recovers any orphaned inodes into it before the FS goes live.
        if self.root_partition is not None:
            mkfs_info = self.root_partition.mkfs()
            print(f"[KERNEL] qfs_root: lost+found ready "
                  f"(slots={mkfs_info['lost_found'].get('slots_reserved', 0)})")
            sb = self.root_partition.superblock
            sb.on_mount()  # marks FS dirty, increments mount count
            if sb.needs_check():
                print("[KERNEL] Filesystem check required (fsck)...")
                checker = _LostFoundFsck(self.root_partition, auto_repair=True)
                fsck_report = checker.check(force=True)
                print(f"[KERNEL] fsck: {fsck_report.summary()}")
                for _entry in fsck_report.recovered_names:
                    print(f"[KERNEL]   recovered -> /lost+found/{_entry}")
            # Expose lost+found in the VFS tree as well.
            self.vfs.mkdir("/lost+found")

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
        """Gracefully shut down the kernel in ordered phases.

        ``kernel/reboot.c`` — ``kernel_restart_prepare()``
        → ``device_shutdown()`` → ``syscore_shutdown()`` → halt.
        Each phase is logged so the operator can see where shutdown stalls.
        """
        log.info("=== Graceful shutdown initiated ===")

        # Phase 0: Trigger the reboot notifier chain ( reboot.c style).
        log.info("[shutdown] Phase 0/5: Firing reboot notifiers...")
        try:
            from kernel.reboot import RebootAction
            await self.reboot.reboot_notifiers.call(RebootAction.HALT, "shutdown")
        except Exception as exc:  # noqa: BLE001
            log.warning("[shutdown] Reboot notifier error: %s", exc)

        # Phase 1: Stop scheduler (no new tasks dispatched)
        log.info("[shutdown] Phase 1/5: Stopping scheduler...")
        self.running = False
        await self.scheduler.stop()

        # Phase 2: Stop softirq daemon (ksoftirqd) and flush pending work.
        log.info("[shutdown] Phase 2/5: Stopping softirq daemon...")
        try:
            await self.softirq.stop()
        except Exception as exc:  # noqa: BLE001
            log.warning("[shutdown] SoftIRQ stop error: %s", exc)

        # Phase 3: Release credentials for all known tasks.
        log.info("[shutdown] Phase 3/5: Releasing credentials & IPC...")
        try:
            # Best-effort: release root + init creds.
            self.cred_store.unregister(PID_SYSTEM)
            self.cred_store.unregister(PID_INIT)
            if hasattr(self.ipc, 'unregister'):
                log.debug("IPC queues left for garbage collection.")
        except Exception as exc:  # noqa: BLE001
            log.warning("[shutdown] Cred/IPC cleanup error: %s", exc)

        # Phase 4: Free memory allocations
        log.info("[shutdown] Phase 4/5: Freeing memory allocations...")
        try:
            for pid, allocs in list(self._mem_allocs.items()) if hasattr(self, '_mem_allocs') else []:
                for ptr, _ in allocs:
                    try:
                        self.memory.free(ptr, pid)
                    except (ValueError, Exception):  # noqa: BLE001
                        pass
        except Exception as exc:  # noqa: BLE001
            log.warning("[shutdown] Memory cleanup error: %s", exc)

        # Phase 5: Final status dump + system_state transition
        log.info("[shutdown] Phase 5/5: Final status dump...")
        from kernel.reboot import SystemState as _SS
        self.reboot.system_state = _SS.HALT
        log.info("  Taint: %s", self.taint.summary() or "(clean)")
        log.info("  Uptime: %.3fs", self.uptime())
        log.info("  PID allocator: %s", self.pid_allocator.stats())
        log.info("  Resource tree: %s", self.resources.status())

        log.info("=== UmerKernel shut down cleanly ===")
    
    async def start_gui_shell(self, mode='desktop'): # Default to desktop
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
            print(f"[KERNEL] Launching GUI ({mode}) in a separate process...")
            # Pass the desired mode as a command-line argument to the launcher script
            
            process = subprocess.Popen([sys.executable, launcher_script_path], stdin=subprocess.PIPE, text=True)
            # Send the mode choice via stdin to the launcher script
            # The launcher script reads this input to decide the platform
            process.stdin.write(f"{ {'desktop': '1', 'android': '2', 'ios': '3', 'web': '4'}.get(mode, '1') }\n")
            process.stdin.flush() # Ensure the input is sent
            process.stdin.close() # Close stdin after sending
            print(f"[KERNEL] GUI ({mode}) process started with PID {process.pid}. Return to kernel shell to manage it.")

           
            # Option 1: Run as a subprocess (Recommended for isolation)
            # print("[KERNEL] Launching GUI in a separate process...")
            # process = subprocess.Popen([sys.executable, launcher_script_path])
            # print(f"[KERNEL] GUI process started with PID {process.pid}. Return to kernel shell to manage it.")
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