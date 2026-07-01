#!/usr/bin/env python3
"""
Umer OS SDK - Application Template

Base class for building apps that run on Umer OS. Provides lifecycle
hooks and safe access to kernel services (VFS, IPC, AI).

Developers subclass UmerApp and implement on_start/on_stop/on_message.
"""


class UmerApp:
    """Base class for all Umer OS applications."""

    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.pid = None
        self._kernel_api = None

    def bind_kernel(self, kernel_api):
        """Called by the kernel to provide safe API access."""
        self._kernel_api = kernel_api

    # ── Lifecycle Hooks (override in subclass) ────────────────────────

    def on_start(self):
        """Called when the app is launched."""
        print(f"[APP:{self.name}] Started (v{self.version})")

    def on_stop(self):
        """Called when the app is terminated."""
        print(f"[APP:{self.name}] Stopped.")

    def on_message(self, sender_pid: int, data):
        """Called when the app receives an IPC message."""
        print(f"[APP:{self.name}] Message from PID {sender_pid}: {data}")

    # ── Safe Kernel API ───────────────────────────────────────────────

    def read_file(self, path: str) -> bytes:
        if self._kernel_api and hasattr(self._kernel_api, 'vfs'):
            return self._kernel_api.vfs.read_file(path)
        raise RuntimeError("Kernel API not bound.")

    def write_file(self, path: str, data: bytes):
        if self._kernel_api and hasattr(self._kernel_api, 'vfs'):
            return self._kernel_api.vfs.write_file(path, data)
        raise RuntimeError("Kernel API not bound.")

    def send_ipc(self, receiver_pid: int, data):
        if self._kernel_api and hasattr(self._kernel_api, 'ipc'):
            return self._kernel_api.ipc.send(self.pid, receiver_pid, data)
        raise RuntimeError("Kernel API not bound.")

    def ask_ai(self, query: str) -> str:
        if self._kernel_api and hasattr(self._kernel_api, 'ai_assistant'):
            return self._kernel_api.ai_assistant.query(query)
        raise RuntimeError("Kernel API not bound.")


# ── Example App ───────────────────────────────────────────────────────

class HelloWorldApp(UmerApp):
    """A minimal example Umer OS application."""

    def __init__(self):
        super().__init__("HelloWorld", "1.0.0")

    def on_start(self):
        super().on_start()
        print(f"[APP:{self.name}] Hello from Umer OS!")
        response = self.ask_ai("status")
        print(f"[APP:{self.name}] AI says: {response}")
