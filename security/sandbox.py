#!/usr/bin/env python3
"""
Security Sandbox with Filesystem Isolation

Provides process-level isolation by restricting each sandboxed process
to a virtual chroot within the VFS. Integrates with the CapabilityManager
from Stage 2 and the CryptoEngine from Stage 4.

Equivalent to Linux's security/ + namespaces (security/apparmor, security/selinux).
"""

"""
UMER OS - Security Sandbox Module
Provides Zero-Trust process isolation, capability management, and jailbreak prevention.
"""

#!/usr/bin/env python3
"""
Security Sandbox with Filesystem Isolation
Provides process-level isolation by restricting each sandboxed process
to a virtual chroot within the VFS. 
"""
import hashlib
import os
from dataclasses import dataclass, field
from typing import Dict, Set

@dataclass
class ProcessRecord:
    pid: int
    name: str
    permissions: Set[str] = field(default_factory=lambda: {"read"})
    fs_root: str = "/"  # chroot-style filesystem jail

class SecuritySandbox:
    """
    Zero-trust process isolation manager.
    Compatible with UmerKernel's initialization sequence.
    """
    def __init__(self):
        self.processes: Dict[int, ProcessRecord] = {}
        print("[SECURITY] Sandbox initialized with Zero-Trust defaults.")

    def register_process(self, pid: int, name: str, fs_root: str = "/"):
        self.processes[pid] = ProcessRecord(pid=pid, name=name, fs_root=fs_root)
        print(f"[SECURITY] Registered PID {pid} ('{name}') with fs_root='{fs_root}'")

    def grant_permission(self, pid: int, permission: str):
        if pid in self.processes:
            self.processes[pid].permissions.add(permission)

    def revoke_permission(self, pid: int, permission: str):
        if pid in self.processes:
            self.processes[pid].permissions.discard(permission)

    def check_permission(self, pid: int, permission: str) -> bool:
        if pid not in self.processes:
            print(f"[SECURITY] 🚫 DENIED: PID {pid} is not registered.")
            return False
        allowed = permission in self.processes[pid].permissions
        if not allowed:
            print(f"[SECURITY] 🚫 DENIED: PID {pid} lacks '{permission}' permission.")
        return allowed

    def resolve_path(self, pid: int, path: str) -> str:
        """
        IMPROVED: Translates a process-relative path into its jailed absolute path.
        Uses os.path.realpath and os.path.commonpath to prevent ALL directory 
        traversal attacks (e.g., symlink escapes, complex '..' bypasses).
        """
        if pid not in self.processes:
            raise PermissionError(f"PID {pid} is not sandboxed.")
        
        jail = os.path.realpath(self.processes[pid].fs_root)
        # Join jail and requested path, then resolve all symlinks and '..' components
        target = os.path.realpath(os.path.join(jail, path.lstrip('/')))
        
        # Secure check: target MUST be strictly inside the jail
        try:
            common = os.path.commonpath([jail, target])
            if common != jail:
                raise PermissionError(f"🚫 Path traversal/jailbreak blocked: {path} resolved to {target}")
        except ValueError:
            # Occurs on Windows if paths resolve to different drives
            raise PermissionError(f"🚫 Invalid path resolution across drives: {path}")
        
        return target

    def verify_signature(self, pid: int, executable_payload: bytes, expected_hash: str) -> bool:
        """
        IMPROVED: Verifies the cryptographic signature of a process executable.
        Replaces the flawed PID-hashing with actual payload hashing (SHA3-512).
        """
        computed_hash = hashlib.sha3_512(executable_payload).hexdigest()
        # Constant-time comparison to prevent timing attacks
        is_valid = hashlib.compare_digest(computed_hash, expected_hash)
        
        if not is_valid:
            print(f"[SECURITY] 🚨 CODE SIGNING FAILED: PID {pid} hash mismatch!")
        else:
            print(f"[SECURITY] ✅ Code signature verified for PID {pid}.")
            
        return is_valid

# -------------------------------------------------------------------


# import os
# import hashlib
# import asyncio
# from dataclasses import dataclass, field
# from typing import Dict, Set, Optional

# @dataclass
# class ProcessRecord:
#     pid: int
#     name: str
#     permissions: Set[str] = field(default_factory=lambda: {"read"})
#     fs_root: str = "/"  # chroot-style filesystem jail
#     signature_verified: bool = False

# class SecuritySandbox:
#     """
#     Zero-trust process isolation manager.
#     Ensures no process is trusted by default. Every operation requires explicit capability grants.
#     """

#     def __init__(self):
#         self.processes: Dict[int, ProcessRecord] = {}
#         self.lock = asyncio.Lock()
#         print("[SECURITY] Sandbox initialized with Zero-Trust defaults.")

#     async def register_process(self, pid: int, name: str, fs_root: str = "/") -> None:
#         """Registers a new process in the sandbox with minimal default permissions."""
#         async with self.lock:
#             self.processes[pid] = ProcessRecord(pid=pid, name=name, fs_root=fs_root)
#         print(f"[SECURITY] Registered PID {pid} ('{name}') in sandbox.")

#     async def grant_permission(self, pid: int, permission: str) -> None:
#         async with self.lock:
#             if pid in self.processes:
#                 self.processes[pid].permissions.add(permission)

#     async def revoke_permission(self, pid: int, permission: str) -> None:
#         async with self.lock:
#             if pid in self.processes:
#                 self.processes[pid].permissions.discard(permission)

#     async def check_permission(self, pid: int, permission: str) -> bool:
#         async with self.lock:
#             if pid not in self.processes:
#                 print(f"[SECURITY] 🚫 DENIED: PID {pid} is not registered.")
#                 return False
            
#             if permission not in self.processes[pid].permissions:
#                 print(f"[SECURITY] 🚫 DENIED: PID {pid} lacks '{permission}' permission.")
#                 return False
#             return True

#     def resolve_path(self, pid: int, requested_path: str) -> str:
#         """
#         Translates a process-relative path into its jailed absolute path.
#         Uses os.path.realpath to resolve symlinks and prevent directory traversal attacks.
#         """
#         with self.lock:  # Note: asyncio lock not needed here if called from async context, but kept for thread-safety
#             if pid not in self.processes:
#                 raise PermissionError(f"PID {pid} is not sandboxed.")
            
#             jail = os.path.realpath(self.processes[pid].fs_root)
            
#             # Join jail and requested path, then resolve all symlinks and '..' components
#             target = os.path.realpath(os.path.join(jail, requested_path.lstrip('/')))
            
#             # Secure check: target MUST be strictly inside the jail
#             try:
#                 common = os.path.commonpath([jail, target])
#                 if common != jail:
#                     raise PermissionError(f"🚫 Path traversal/jailbreak blocked: {requested_path} resolved to {target}")
#             except ValueError:
#                 # Occurs on Windows if paths resolve to different drives
#                 raise PermissionError(f"🚫 Invalid path resolution across drives: {requested_path}")
            
#             return target

#     async def verify_signature(self, pid: int, executable_payload: bytes, expected_hash: str) -> bool:
#         """
#         Verifies the cryptographic signature of a process executable.
#         Replaces the flawed PID-hashing with actual payload hashing (Simulated SHA3-512 Code Signing).
#         """
#         computed_hash = hashlib.sha3_512(executable_payload).hexdigest()
        
#         # Constant-time comparison to prevent timing attacks
#         is_valid = hashlib.compare_digest(computed_hash, expected_hash)
        
#         async with self.lock:
#             if pid in self.processes:
#                 self.processes[pid].signature_verified = is_valid
                
#         if not is_valid:
#             print(f"[SECURITY] 🚨 CODE SIGNING FAILED: PID {pid} hash mismatch!")
#         else:
#             print(f"[SECURITY] ✅ Code signature verified for PID {pid}.")
            
#         return is_valid


        # -------------------------------------------------------------------

# import hashlib
# from dataclasses import dataclass, field
# from typing import Dict, Set


# @dataclass
# class ProcessRecord:
#     pid: int
#     name: str
#     permissions: Set[str] = field(default_factory=lambda: {"read"})
#     fs_root: str = "/"  # chroot-style filesystem jail


# class SecuritySandbox:
#     """
#     Zero-trust process isolation manager.
    
#     Each process is registered with:
#         - A permission set (read, write, exec, net, hardware)
#         - A filesystem root (chroot jail path within the VFS)
#     """

#     def __init__(self):
#         self.processes: Dict[int, ProcessRecord] = {}
#         print("[SECURITY] Sandbox initialized.")

#     def register_process(self, pid: int, name: str, fs_root: str = "/"):
#         self.processes[pid] = ProcessRecord(pid=pid, name=name, fs_root=fs_root)
#         print(f"[SECURITY] Registered PID {pid} ('{name}') with fs_root='{fs_root}'")

#     def grant_permission(self, pid: int, permission: str):
#         if pid in self.processes:
#             self.processes[pid].permissions.add(permission)

#     def revoke_permission(self, pid: int, permission: str):
#         if pid in self.processes:
#             self.processes[pid].permissions.discard(permission)

#     def check_permission(self, pid: int, permission: str) -> bool:
#         if pid not in self.processes:
#             print(f"[SECURITY] DENIED: PID {pid} is not registered.")
#             return False
#         allowed = permission in self.processes[pid].permissions
#         if not allowed:
#             print(f"[SECURITY] DENIED: PID {pid} lacks '{permission}' permission.")
#         return allowed

#     def resolve_path(self, pid: int, path: str) -> str:
#         """Translate a process-relative path into its jailed absolute path.
        
#         Prevents directory traversal attacks by normalizing and validating paths.
#         """
#         import os
        
#         if pid not in self.processes:
#             raise PermissionError(f"PID {pid} is not sandboxed.")
        
#         jail = self.processes[pid].fs_root.rstrip("/")
        
#         # Normalize the path to resolve . and .. components
#         normalized = os.path.normpath(path)
        
#         # Reject paths that try to escape with ..
#         if normalized.startswith("..") or "/../" in normalized or "\\..\\" in normalized:
#             raise PermissionError(f"Path traversal detected: {path}")
        
#         # Remove leading slashes and normalize
#         clean = normalized.lstrip("/").lstrip(".")
        
#         # Construct final path
#         if jail == "/":
#             resolved = f"/{clean}"
#         else:
#             resolved = f"{jail}/{clean}"
        
#         # Final validation: resolved path must start with jail
#         real_jail = os.path.abspath(jail)
#         real_resolved = os.path.abspath(resolved)
#         if not real_resolved.startswith(real_jail):
#             raise PermissionError(f"Path escapes jail: {path} -> {resolved}")
        
#         return resolved

#     def verify_signature(self, pid: int, signature: str) -> bool:
#         expected = hashlib.sha3_512(f"{pid}".encode()).hexdigest()
#         return signature == expected