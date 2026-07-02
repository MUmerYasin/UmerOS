#!/usr/bin/env python3
"""
Security Sandbox with Filesystem Isolation

Provides process-level isolation by restricting each sandboxed process
to a virtual chroot within the VFS. Integrates with the CapabilityManager
from Stage 2 and the CryptoEngine from Stage 4.

Equivalent to Linux's security/ + namespaces (security/apparmor, security/selinux).
"""

import hashlib
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
    
    Each process is registered with:
        - A permission set (read, write, exec, net, hardware)
        - A filesystem root (chroot jail path within the VFS)
    """

    def __init__(self):
        self.processes: Dict[int, ProcessRecord] = {}
        print("[SECURITY] Sandbox initialized.")

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
            print(f"[SECURITY] DENIED: PID {pid} is not registered.")
            return False
        allowed = permission in self.processes[pid].permissions
        if not allowed:
            print(f"[SECURITY] DENIED: PID {pid} lacks '{permission}' permission.")
        return allowed

    def resolve_path(self, pid: int, path: str) -> str:
        """Translate a process-relative path into its jailed absolute path.
        
        Prevents directory traversal attacks by normalizing and validating paths.
        """
        import os
        
        if pid not in self.processes:
            raise PermissionError(f"PID {pid} is not sandboxed.")
        
        jail = self.processes[pid].fs_root.rstrip("/")
        
        # Normalize the path to resolve . and .. components
        normalized = os.path.normpath(path)
        
        # Reject paths that try to escape with ..
        if normalized.startswith("..") or "/../" in normalized or "\\..\\" in normalized:
            raise PermissionError(f"Path traversal detected: {path}")
        
        # Remove leading slashes and normalize
        clean = normalized.lstrip("/").lstrip(".")
        
        # Construct final path
        if jail == "/":
            resolved = f"/{clean}"
        else:
            resolved = f"{jail}/{clean}"
        
        # Final validation: resolved path must start with jail
        real_jail = os.path.abspath(jail)
        real_resolved = os.path.abspath(resolved)
        if not real_resolved.startswith(real_jail):
            raise PermissionError(f"Path escapes jail: {path} -> {resolved}")
        
        return resolved

    def verify_signature(self, pid: int, signature: str) -> bool:
        expected = hashlib.sha3_512(f"{pid}".encode()).hexdigest()
        return signature == expected