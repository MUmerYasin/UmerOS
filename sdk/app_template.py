# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

#!/usr/bin/env python3
"""
Umer OS SDK - Application Template

Base class for building apps that run on Umer OS. Provides lifecycle
hooks and safe access to kernel services (VFS, IPC, AI).

Developers subclass UmerApp and implement on_start/on_stop/on_message.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations


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


def _selftest() -> bool:
    """Run self-tests for the ``UmerApp`` lifecycle and kernel binding."""
    print("[sdk/app_template] selftest …")
    ok = True

    def check(condition: bool, label: str) -> None:
        nonlocal ok
        if condition:
            print(f"  [PASS] {label}")
        else:
            ok = False
            print(f"  [FAIL] {label}")

    app = UmerApp("Selftest", "2.3.4")
    check(app.name == "Selftest", "name recorded")
    check(app.version == "2.3.4", "version recorded")
    check(app.pid is None, "pid starts unbound")

    app.on_start()
    app.on_stop()
    app.on_message(7, "hello")
    check(True, "lifecycle hooks run without a kernel")

    for method, args in (
        (app.read_file, ("/x",)),
        (app.write_file, ("/x", b"d")),
        (app.send_ipc, (1, "d")),
        (app.ask_ai, ("q",)),
    ):
        try:
            method(*args)
        except RuntimeError:
            check(True, f"{method.__name__} refuses an unbound kernel")
        else:
            check(False, f"{method.__name__} should have raised RuntimeError")

    class _Kernel:
        def __init__(self) -> None:
            self.vfs = self
            self.ipc = self
            self.ai_assistant = self

        def read_file(self, path: str) -> bytes:
            return b"content"

        def write_file(self, path: str, data: bytes) -> bool:
            return True

        def send(self, sender: int, receiver: int, data: object) -> bool:
            return True

        def query(self, q: str) -> str:
            return "response"

    app.bind_kernel(_Kernel())
    check(app.read_file("/x") == b"content", "read_file delegates to the bound kernel")
    check(app.write_file("/x", b"d") is True, "write_file delegates to the bound kernel")
    check(app.send_ipc(1, "d") is True, "send_ipc delegates to the bound kernel")
    check(app.ask_ai("q") == "response", "ask_ai delegates to the bound kernel")

    check(HelloWorldApp().name == "HelloWorld", "HelloWorldApp example constructs")

    print("[sdk/app_template] selftest " + ("PASSED" if ok else "FAILED"))
    return ok


if __name__ == "__main__":
    _selftest()
