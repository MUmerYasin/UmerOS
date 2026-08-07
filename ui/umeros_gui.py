#!/usr/bin/env python3
"""UmerOS GUI — full desktop shell with 12 app windows.

Run standalone::

    python umeros_gui.py

Integrates with the UmerOS kernel, scheduler, memory manager, QFS,
network stack, and security subsystems — degrading gracefully when
any module is unavailable.
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ── PyQt6 imports ──────────────────────────────────────────────────
try:
    from PyQt6.QtCore import (
        QEasingCurve,
        QPropertyAnimation,
        QSettings,
        QSize,
        Qt,
        QTimer,
        pyqtSignal,
    )
    from PyQt6.QtGui import (
        QBrush,
        QColor,
        QFont,
        QFontMetrics,
        QIcon,
        QKeySequence,
        QPainter,
        QPainterPath,
        QPalette,
        QScreen,
        QPixmap,
        QShortcut,
    )
    from PyQt6.QtWidgets import (
        QApplication,
        QButtonGroup,
        QComboBox,

        QDialog,
        QFileDialog,
        QFrame,
        QGraphicsOpacityEffect,
        QGridLayout,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QLineEdit,
        QListWidget,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSlider,
        QSpinBox,
        QSplitter,
        QStatusBar,
        QTabWidget,
        QTextEdit,
        QToolButton,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    HAS_PYQT6 = True
except ImportError:
    HAS_PYQT6 = False
    print("[UmerOS] PyQt6 not installed — GUI unavailable.", file=sys.stderr)
    sys.exit(1)

# ── Backend imports (graceful degradation) ─────────────────────────
_BASE = Path(__file__).resolve().parent.parent
if str(_BASE) not in sys.path:
    sys.path.insert(0, str(_BASE))


def _try_import(module_path: str, attr: str):
    """Import *attr* from *module_path*, returning None on failure."""
    try:
        mod = importlib.import_module(module_path)
        return getattr(mod, attr, None)
    except Exception:
        return None


UmerKernel = _try_import("kernel.umer_kernel", "UmerKernel")
HybridScheduler = _try_import("kernel.scheduler", "HybridScheduler")
VirtualMemoryManager = _try_import("kernel.memory_manager", "VirtualMemoryManager")
QFS = _try_import("kernel.qfs", "QFS")
SecureBoot = _try_import("security.security", "SecureBoot")
IPCAuthenticator = _try_import("security.security", "IPCAuthenticator")
NetworkStack = _try_import("network.network_stack", "NetworkStack")
show_legal_warning = _try_import("kernel.bootloader", "show_legal_warning")
boot_kernel = _try_import("kernel.bootloader", "boot_kernel")


# ╔══════════════════════════════════════════════════════════════════╗
# ║                         CONSTANTS                               ║
# ╚══════════════════════════════════════════════════════════════════╝
APP_NAME = "UmerOS"
APP_VERSION = "1.0.0"
ORG_NAME = "UmerOS"

# Color palette
COLORS = {
    "primary": "#6C3483",       # deep purple
    "primary_dark": "#4A235A",
    "primary_light": "#8E44AD",
    "accent": "#1ABC9C",        # teal
    "accent_dark": "#16A085",
    "bg_dark": "#1a1a2e",
    "bg_mid": "#16213e",
    "bg_light": "#0f3460",
    "surface": "#1e2746",
    "surface_light": "#283856",
    "text": "#ecf0f1",
    "text_dim": "#95a5a6",
    "text_bright": "#ffffff",
    "success": "#2ecc71",
    "warning": "#f39c12",
    "danger": "#e74c3c",
    "border": "#34495e",
}

DOCK_SHORTCUTS = [
    ("Terminal", "terminal"),
    ("Files", "files"),
    ("Monitor", "monitor"),
    ("Settings", "settings"),
    ("Editor", "editor"),
    ("Packages", "packages"),
    ("Network", "network"),
    ("Quantum", "quantum"),
    ("Security", "security"),
    ("Boot", "boot"),
    ("Games", "games"),
    ("Docs", "docs"),
]

DESKTOP_APPS = [
    ("Terminal", "terminal", "🖥"),
    ("Files", "files", "📁"),
    ("System Monitor", "monitor", "📊"),
    ("Settings", "settings", "⚙"),
    ("Text Editor", "editor", "📝"),
    ("Package Manager", "packages", "📦"),
    ("Network", "network", "🌐"),
    ("Quantum Lab", "quantum", "⚛"),
    ("Security Center", "security", "🛡"),
    ("Boot Manager", "boot", "🔋"),
    ("Games", "games", "🎮"),
    ("Documentation", "docs", "📚"),
]


# ╔══════════════════════════════════════════════════════════════════╗
# ║                     STYLE / THEMING                             ║
# ╚══════════════════════════════════════════════════════════════════╝
class ThemeMode(Enum):
    DARK = auto()
    LIGHT = auto()


def _build_palette(mode: ThemeMode) -> QPalette:
    pal = QPalette()
    if mode is ThemeMode.DARK:
        pal.setColor(QPalette.ColorRole.Window, QColor(COLORS["bg_dark"]))
        pal.setColor(QPalette.ColorRole.WindowText, QColor(COLORS["text"]))
        pal.setColor(QPalette.ColorRole.Base, QColor(COLORS["surface"]))
        pal.setColor(QPalette.ColorRole.AlternateBase, QColor(COLORS["surface_light"]))
        pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(COLORS["bg_mid"]))
        pal.setColor(QPalette.ColorRole.ToolTipText, QColor(COLORS["text"]))
        pal.setColor(QPalette.ColorRole.Text, QColor(COLORS["text"]))
        pal.setColor(QPalette.ColorRole.Button, QColor(COLORS["primary"]))
        pal.setColor(QPalette.ColorRole.ButtonText, QColor(COLORS["text_bright"]))
        pal.setColor(QPalette.ColorRole.BrightText, QColor(COLORS["accent"]))
        pal.setColor(QPalette.ColorRole.Link, QColor(COLORS["accent"]))
        pal.setColor(QPalette.ColorRole.Highlight, QColor(COLORS["primary_light"]))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(COLORS["text_bright"]))
    else:
        pal.setColor(QPalette.ColorRole.Window, QColor("#f5f6fa"))
        pal.setColor(QPalette.ColorRole.WindowText, QColor("#2c3e50"))
        pal.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
        pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#ecf0f1"))
        pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
        pal.setColor(QPalette.ColorRole.ToolTipText, QColor("#2c3e50"))
        pal.setColor(QPalette.ColorRole.Text, QColor("#2c3e50"))
        pal.setColor(QPalette.ColorRole.Button, QColor(COLORS["primary"]))
        pal.setColor(QPalette.ColorRole.ButtonText, QColor("#ffffff"))
        pal.setColor(QPalette.ColorRole.BrightText, QColor(COLORS["danger"]))
        pal.setColor(QPalette.ColorRole.Link, QColor(COLORS["primary_dark"]))
        pal.setColor(QPalette.ColorRole.Highlight, QColor(COLORS["accent"]))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    return pal


_DARK_QSS = """
QMainWindow, QDialog { background: %(bg_dark)s; }
QWidget { color: %(text)s; font-family: 'Segoe UI', 'Consolas', sans-serif; }
QMenuBar { background: %(primary_dark)s; color: %(text)s; border-bottom: 1px solid %(border)s; }
QMenuBar::item:selected { background: %(primary)s; }
QMenu { background: %(surface)s; color: %(text)s; border: 1px solid %(border)s; }
QMenu::item:selected { background: %(primary_light)s; }
QToolBar { background: %(primary_dark)s; border: none; spacing: 4px; }
QStatusBar { background: %(bg_mid)s; color: %(text_dim)s; border-top: 1px solid %(border)s; }
QPushButton {
    background: %(primary)s; color: %(text_bright)s; border: none;
    border-radius: 6px; padding: 6px 14px; font-weight: bold;
}
QPushButton:hover { background: %(primary_light)s; }
QPushButton:pressed { background: %(primary_dark)s; }
QPushButton:disabled { background: %(surface)s; color: %(text_dim)s; }
QLineEdit, QTextEdit, QPlainTextEdit {
    background: %(surface)s; color: %(text)s; border: 1px solid %(border)s;
    border-radius: 4px; padding: 4px; selection-background-color: %(primary_light)s;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus { border: 1px solid %(accent)s; }
QComboBox {
    background: %(surface)s; color: %(text)s; border: 1px solid %(border)s;
    border-radius: 4px; padding: 4px 8px;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView { background: %(surface)s; color: %(text)s; selection-background-color: %(primary_light)s; }
QListWidget, QTreeWidget {
    background: %(surface)s; color: %(text)s; border: 1px solid %(border)s;
    border-radius: 4px; outline: none;
}
QListWidget::item:selected, QTreeWidget::item:selected { background: %(primary)s; }
QListWidget::item:hover, QTreeWidget::item:hover { background: %(surface_light)s; }
QTabWidget::pane { border: 1px solid %(border)s; background: %(surface)s; }
QTabBar::tab { background: %(bg_mid)s; color: %(text_dim)s; padding: 6px 16px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
QTabBar::tab:selected { background: %(primary)s; color: %(text_bright)s; }
QTabBar::tab:hover { background: %(primary_light)s; }
QProgressBar { border: 1px solid %(border)s; border-radius: 4px; text-align: center; background: %(surface)s; }
QProgressBar::chunk { background: %(accent)s; border-radius: 3px; }
QScrollBar:vertical { background: %(bg_mid)s; width: 10px; border-radius: 5px; }
QScrollBar::handle:vertical { background: %(border)s; border-radius: 5px; min-height: 20px; }
QScrollBar::handle:vertical:hover { background: %(text_dim)s; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QSlider::groove:horizontal { background: %(border)s; height: 6px; border-radius: 3px; }
QSlider::handle:horizontal { background: %(accent)s; width: 14px; margin: -4px 0; border-radius: 7px; }
QSpinBox { background: %(surface)s; color: %(text)s; border: 1px solid %(border)s; border-radius: 4px; padding: 2px; }
QSplitter::handle { background: %(border)s; }
QLabel#dockLabel { font-size: 10px; color: %(text_dim)s; }
QFrame#dockItem {
    background: %(surface)s; border-radius: 8px; padding: 4px;
}
QFrame#dockItem:hover { background: %(surface_light)s; }
QLabel#desktopIcon { font-size: 32px; }
QLabel#desktopLabel { font-size: 11px; color: %(text_dim)s; }
""" % COLORS

_LIGHT_QSS = """
QMainWindow, QDialog { background: #f5f6fa; }
QWidget { color: #2c3e50; font-family: 'Segoe UI', 'Consolas', sans-serif; }
QMenuBar { background: #ecf0f1; color: #2c3e50; border-bottom: 1px solid #bdc3c7; }
QMenuBar::item:selected { background: %(primary)s; color: #fff; }
QMenu { background: #ffffff; color: #2c3e50; border: 1px solid #bdc3c7; }
QMenu::item:selected { background: %(accent)s; color: #fff; }
QStatusBar { background: #ecf0f1; color: #7f8c8d; border-top: 1px solid #bdc3c7; }
QPushButton {
    background: %(primary)s; color: #fff; border: none;
    border-radius: 6px; padding: 6px 14px; font-weight: bold;
}
QPushButton:hover { background: %(primary_light)s; }
QPushButton:pressed { background: %(primary_dark)s; }
QLineEdit, QTextEdit, QPlainTextEdit {
    background: #ffffff; color: #2c3e50; border: 1px solid #bdc3c7;
    border-radius: 4px; padding: 4px; selection-background-color: %(accent)s;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus { border: 1px solid %(primary)s; }
QComboBox {
    background: #ffffff; color: #2c3e50; border: 1px solid #bdc3c7;
    border-radius: 4px; padding: 4px 8px;
}
QListWidget, QTreeWidget {
    background: #ffffff; color: #2c3e50; border: 1px solid #bdc3c7;
    border-radius: 4px; outline: none;
}
QListWidget::item:selected, QTreeWidget::item:selected { background: %(primary)s; color: #fff; }
QTabWidget::pane { border: 1px solid #bdc3c7; background: #ffffff; }
QTabBar::tab { background: #ecf0f1; color: #7f8c8d; padding: 6px 16px; }
QTabBar::tab:selected { background: %(primary)s; color: #fff; }
QProgressBar { border: 1px solid #bdc3c7; border-radius: 4px; text-align: center; background: #ecf0f1; }
QProgressBar::chunk { background: %(accent)s; border-radius: 3px; }
""" % COLORS


# ╔══════════════════════════════════════════════════════════════════╗
# ║                      BACKEND BRIDGE                              ║
# ╚══════════════════════════════════════════════════════════════════╝
class BackendBridge:
    """Thin wrapper around UmerOS kernel objects.

    Every method catches exceptions so the GUI never crashes even when
    backends are missing or misbehaving.
    """

    def __init__(self) -> None:
        self.kernel: Optional[Any] = None
        self.scheduler: Optional[Any] = None
        self.memory: Optional[Any] = None
        self.qfs: Optional[Any] = None
        self.network: Optional[Any] = None
        self.secure_boot: Optional[Any] = None
        self.auth: Optional[Any] = None
        self._init_backends()

    # ── init ──────────────────────────────────────────────────────
    def _init_backends(self) -> None:
        try:
            if UmerKernel:
                self.kernel = UmerKernel()
        except Exception:
            self.kernel = None
        try:
            if VirtualMemoryManager:
                self.memory = VirtualMemoryManager()
        except Exception:
            self.memory = None
        try:
            if QFS:
                self.qfs = QFS()
        except Exception:
            self.qfs = None
        try:
            if HybridScheduler:
                self.scheduler = HybridScheduler()
        except Exception:
            self.scheduler = None
        try:
            if NetworkStack:
                self.network = NetworkStack()
        except Exception:
            self.network = None
        try:
            if SecureBoot:
                self.secure_boot = SecureBoot()
        except Exception:
            self.secure_boot = None
        try:
            if IPCAuthenticator:
                self.auth = IPCAuthenticator()
        except Exception:
            self.auth = None

    # ── kernel ────────────────────────────────────────────────────
    def kernel_state(self) -> Dict[str, Any]:
        if self.kernel:
            try:
                return self.kernel.get_system_state()  # type: ignore[union-attr]
            except Exception:
                pass
        return {"status": "unavailable", "uptime": 0}

    def process_list(self) -> List[Dict[str, Any]]:
        if self.kernel:
            try:
                return self.kernel.get_process_list()  # type: ignore[union-attr]
            except Exception:
                pass
        return []

    # ── memory ────────────────────────────────────────────────────
    def memory_stats(self) -> Dict[str, Any]:
        if self.memory:
            try:
                return self.memory.stats()  # type: ignore[union-attr]
            except Exception:
                pass
        return {"total_pages": 0, "used_pages": 0, "free_pages": 0, "page_faults": 0}

    # ── filesystem ────────────────────────────────────────────────
    def fs_list(self, path: str = "/") -> List[str]:
        if self.qfs:
            try:
                return self.qfs.list_dir(path)  # type: ignore[union-attr]
            except Exception:
                pass
        return []

    def fs_read(self, path: str) -> str:
        if self.qfs:
            try:
                return self.qfs.read_file(path)  # type: ignore[union-attr]
            except Exception:
                pass
        return ""

    def fs_write(self, path: str, data: str) -> bool:
        if self.qfs:
            try:
                self.qfs.write_file(path, data)  # type: ignore[union-attr]
                return True
            except Exception:
                pass
        return False

    def fs_mkdir(self, path: str) -> bool:
        if self.qfs:
            try:
                self.qfs.create_dir(path)  # type: ignore[union-attr]
                return True
            except Exception:
                pass
        return False

    def fs_delete(self, path: str) -> bool:
        if self.qfs:
            try:
                self.qfs.delete_file(path)  # type: ignore[union-attr]
                return True
            except Exception:
                pass
        return False

    def fs_stats(self) -> Dict[str, Any]:
        if self.qfs:
            try:
                return self.qfs.get_stats()  # type: ignore[union-attr]
            except Exception:
                pass
        return {}

    # ── network ───────────────────────────────────────────────────
    def network_status(self) -> Dict[str, Any]:
        if self.network:
            try:
                return self.network.status()  # type: ignore[union-attr]
            except Exception:
                pass
        return {"running": False, "connections": 0}

    def network_connections(self) -> List[Dict[str, Any]]:
        if self.network:
            try:
                return list(self.network.connection_table())  # type: ignore[union-attr]
            except Exception:
                pass
        return []

    # ── security ──────────────────────────────────────────────────
    def security_audit(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"modules": {}}
        if self.secure_boot:
            try:
                result["modules"]["secure_boot"] = self.secure_boot.status()  # type: ignore[union-attr]
            except Exception:
                result["modules"]["secure_boot"] = {"error": "unavailable"}
        if self.auth:
            try:
                result["modules"]["ipc_auth"] = {"active_sessions": 0}
            except Exception:
                result["modules"]["ipc_auth"] = {"error": "unavailable"}
        return result

    # ── scheduler ─────────────────────────────────────────────────
    def scheduler_stats(self) -> Dict[str, Any]:
        if self.scheduler:
            try:
                return self.scheduler.get_stats()  # type: ignore[union-attr]
            except Exception:
                pass
        return {}

    def scheduler_tasks(self) -> List[Dict[str, Any]]:
        if self.scheduler:
            try:
                tasks = self.scheduler.get_running_tasks()  # type: ignore[union-attr]
                return [t.__dict__ if hasattr(t, "__dict__") else {"name": str(t)} for t in tasks]
            except Exception:
                pass
        return []


# Global bridge instance
bridge = BackendBridge()


# ╔══════════════════════════════════════════════════════════════════╗
# ║                     HELPER WIDGETS                              ║
# ╚══════════════════════════════════════════════════════════════════╝
def _icon_pixmap(text: str, size: int = 48) -> QPixmap:
    """Render an emoji / text into a square QPixmap."""
    pix = QPixmap(size, size)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = QFont("Segoe UI Emoji", size // 3)
    painter.setFont(font)
    painter.setPen(QColor(COLORS["text"]))
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, text)
    painter.end()
    return pix


class _ClickableFrame(QFrame):
    """A QFrame that emits clicked()."""
    clicked = pyqtSignal()

    def mousePressEvent(self, event):  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ╔══════════════════════════════════════════════════════════════════╗
# ║                       APP WINDOWS                               ║
# ╚══════════════════════════════════════════════════════════════════╝

class _AppWindow(QMainWindow):
    """Base class for all UmerOS app windows."""

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(700, 480)
        self.resize(820, 560)

    def _make_center(self, widget: QWidget) -> None:
        wrapper = QWidget()
        lay = QVBoxLayout(wrapper)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(widget)
        self.setCentralWidget(wrapper)


# ── Terminal ───────────────────────────────────────────────────────
class TerminalWindow(_AppWindow):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("UmerOS Terminal", parent)
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 8)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Cascadia Mono, Consolas, monospace", 11))
        self.output.setStyleSheet(
            "background:#0d1117; color:#c9d1d9; border:none; padding:8px;"
        )
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a command…")
        self.input.setFont(QFont("Cascadia Mono, Consolas, monospace", 11))
        self.input.returnPressed.connect(self._execute)
        lay.addWidget(self.output, 1)
        lay.addWidget(self.input)
        self._history: List[str] = []
        self._history_idx = -1
        self._print("Welcome to UmerOS Terminal v1.0")
        self._print("Type 'help' for available commands.\n")

    def _print(self, text: str) -> None:
        self.output.appendPlainText(text)

    def _execute(self) -> None:
        cmd = self.input.text().strip()
        self.input.clear()
        if not cmd:
            return
        self._history.append(cmd)
        self._history_idx = len(self._history)
        self._print(f"$ {cmd}")
        parts = cmd.split()
        handler = parts[0].lower()
        args = parts[1:]
        commands = {
            "help": self._cmd_help,
            "clear": self._cmd_clear,
            "uptime": self._cmd_uptime,
            "ps": self._cmd_ps,
            "mem": self._cmd_mem,
            "ls": self._cmd_ls,
            "cat": self._cmd_cat,
            "mkdir": self._cmd_mkdir,
            "rm": self._cmd_rm,
            "touch": self._cmd_touch,
            "df": self._cmd_df,
            "net": self._cmd_net,
            "sched": self._cmd_sched,
            "whoami": lambda: self._print("root@umeros"),
            "hostname": lambda: self._print("umeros"),
            "date": lambda: self._print(time.strftime("%Y-%m-%d %H:%M:%S")),
            "uname": lambda: self._print(f"UmerOS {APP_VERSION} (Quantum-inspired)"),
        }
        fn = commands.get(handler)
        if fn:
            try:
                fn() if not args else fn(args)  # type: ignore[misc]
            except TypeError:
                fn()
            except Exception as exc:
                self._print(f"Error: {exc}")
        else:
            self._print(f"Unknown command: {handler}. Type 'help' for list.")

    def _cmd_help(self) -> None:
        self._print(
            "Commands: help, clear, uptime, ps, mem, ls, cat, mkdir, rm,\n"
            "          touch, df, net, sched, whoami, hostname, date, uname"
        )

    def _cmd_clear(self) -> None:
        self.output.clear()

    def _cmd_uptime(self) -> None:
        state = bridge.kernel_state()
        self._print(f"System status: {state.get('status', 'unknown')}")
        self._print(f"Uptime ticks: {state.get('uptime', 0)}")

    def _cmd_ps(self) -> None:
        procs = bridge.process_list()
        if not procs:
            self._print("No processes running (kernel unavailable).")
            return
        self._print(f"{'PID':<6}{'Name':<20}{'State':<12}{'CPU%':<8}")
        self._print("-" * 46)
        for p in procs:
            self._print(
                f"{p.get('pid', '?'):<6}{p.get('name', '?'):<20}"
                f"{p.get('state', '?'):<12}{p.get('cpu', 0):<8.1f}"
            )

    def _cmd_mem(self) -> None:
        stats = bridge.memory_stats()
        total = stats.get("total_pages", 0)
        used = stats.get("used_pages", 0)
        free = stats.get("free_pages", 0)
        faults = stats.get("page_faults", 0)
        self._print(f"Total pages: {total}  Used: {used}  Free: {free}  Faults: {faults}")

    def _cmd_ls(self, args: Optional[List[str]] = None) -> None:
        path = args[0] if args else "/"
        entries = bridge.fs_list(path)
        if entries:
            self._print("  ".join(entries))
        else:
            self._print(f"(empty or unavailable: {path})")

    def _cmd_cat(self, args: Optional[List[str]] = None) -> None:
        if not args:
            self._print("Usage: cat <path>")
            return
        content = bridge.fs_read(args[0])
        self._print(content if content else "(file not found or empty)")

    def _cmd_mkdir(self, args: Optional[List[str]] = None) -> None:
        if not args:
            self._print("Usage: mkdir <path>")
            return
        ok = bridge.fs_mkdir(args[0])
        self._print(f"Created: {args[0]}" if ok else f"Failed to create: {args[0]}")

    def _cmd_rm(self, args: Optional[List[str]] = None) -> None:
        if not args:
            self._print("Usage: rm <path>")
            return
        ok = bridge.fs_delete(args[0])
        self._print(f"Deleted: {args[0]}" if ok else f"Failed to delete: {args[0]}")

    def _cmd_touch(self, args: Optional[List[str]] = None) -> None:
        if not args:
            self._print("Usage: touch <path>")
            return
        ok = bridge.fs_write(args[0], "")
        self._print(f"Touched: {args[0]}" if ok else f"Failed: {args[0]}")

    def _cmd_df(self) -> None:
        stats = bridge.fs_stats()
        if stats:
            for k, v in stats.items():
                self._print(f"  {k}: {v}")
        else:
            self._print("QFS stats unavailable.")

    def _cmd_net(self) -> None:
        status = bridge.network_status()
        for k, v in status.items():
            self._print(f"  {k}: {v}")

    def _cmd_sched(self) -> None:
        stats = bridge.scheduler_stats()
        if stats:
            for k, v in stats.items():
                self._print(f"  {k}: {v}")
        else:
            self._print("Scheduler stats unavailable.")

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down) and self._history:
            if event.key() == Qt.Key.Key_Up:
                self._history_idx = max(0, self._history_idx - 1)
            else:
                self._history_idx = min(len(self._history) - 1, self._history_idx + 1)
            if 0 <= self._history_idx < len(self._history):
                self.input.setText(self._history[self._history_idx])
        else:
            super().keyPressEvent(event)


# ── Files ──────────────────────────────────────────────────────────
class FilesWindow(_AppWindow):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("UmerOS Files", parent)
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 8)
        toolbar = QHBoxLayout()
        self.path_edit = QLineEdit("/")
        self.path_edit.returnPressed.connect(self._navigate)
        toolbar.addWidget(QLabel("Path:"))
        toolbar.addWidget(self.path_edit, 1)
        btn_open = QPushButton("Open")
        btn_open.clicked.connect(self._navigate)
        toolbar.addWidget(btn_open)
        btn_back = QPushButton("← Back")
        btn_back.clicked.connect(self._go_back)
        toolbar.addWidget(btn_back)
        lay.addLayout(toolbar)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Type", "Size"])
        self.tree.setColumnWidth(0, 300)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        lay.addWidget(self.tree, 1)
        status_bar = QHBoxLayout()
        self.status_label = QLabel("")
        status_bar.addWidget(self.status_label)
        lay.addLayout(status_bar)
        self._history_stack: List[str] = ["/"]
        self._skip_history_push = False
        self._navigate()

    def _navigate(self) -> None:
        path = self.path_edit.text().strip() or "/"
        self.tree.clear()
        entries = bridge.fs_list(path)
        for name in entries:
            item = QTreeWidgetItem([name, "dir" if "." not in name else "file", "—"])
            self.tree.addTopLevelItem(item)
        self.status_label.setText(f"{len(entries)} items — Path: {path}")
        if not self._skip_history_push:
            if not self._history_stack or self._history_stack[-1] != path:
                self._history_stack.append(path)
        self._skip_history_push = False

    def _go_back(self) -> None:
        if len(self._history_stack) > 1:
            self._history_stack.pop()
            prev = self._history_stack[-1]
            self.path_edit.setText(prev)
            self._skip_history_push = True
            self._navigate()

    def _on_double_click(self, item: QTreeWidgetItem, _col: int) -> None:
        name = item.text(0)
        current = self.path_edit.text().strip()
        new_path = f"{current.rstrip('/')}/{name}"
        self.path_edit.setText(new_path)
        self._navigate()


# ── System Monitor ─────────────────────────────────────────────────
class MonitorWindow(_AppWindow):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("UmerOS System Monitor", parent)
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 8)
        tabs = QTabWidget()
        tabs.addTab(self._make_cpu_tab(), "CPU / Scheduler")
        tabs.addTab(self._make_mem_tab(), "Memory")
        tabs.addTab(self._make_proc_tab(), "Processes")
        tabs.addTab(self._make_net_tab(), "Network")
        lay.addWidget(tabs, 1)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(2000)
        self._refresh()

    def _make_cpu_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.cpu_label = QLabel("Scheduler: —")
        self.cpu_label.setFont(QFont("Consolas", 11))
        lay.addWidget(self.cpu_label)
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        lay.addWidget(self.cpu_bar)
        self.sched_tree = QTreeWidget()
        self.sched_tree.setHeaderLabels(["Task", "State", "Quantum Score"])
        lay.addWidget(self.sched_tree, 1)
        return w

    def _make_mem_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.mem_label = QLabel("Memory: —")
        self.mem_label.setFont(QFont("Consolas", 11))
        lay.addWidget(self.mem_label)
        self.mem_bar = QProgressBar()
        self.mem_bar.setRange(0, 100)
        lay.addWidget(self.mem_bar)
        self.mem_detail = QLabel("")
        self.mem_detail.setFont(QFont("Consolas", 10))
        lay.addWidget(self.mem_detail)
        lay.addStretch()
        return w

    def _make_proc_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.proc_tree = QTreeWidget()
        self.proc_tree.setHeaderLabels(["PID", "Name", "State", "CPU%", "Memory"])
        self.proc_tree.setColumnWidth(1, 160)
        lay.addWidget(self.proc_tree, 1)
        return w

    def _make_net_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.net_label = QLabel("Network: —")
        self.net_label.setFont(QFont("Consolas", 11))
        lay.addWidget(self.net_label)
        self.net_tree = QTreeWidget()
        self.net_tree.setHeaderLabels(["Host", "Port", "Type", "Priority"])
        lay.addWidget(self.net_tree, 1)
        return w

    def _refresh(self) -> None:
        # CPU / scheduler
        sched = bridge.scheduler_stats()
        self.cpu_label.setText(f"Scheduler: {sched}")
        self.cpu_bar.setValue(min(100, int(sched.get("cpu_usage", 0) * 100)) if sched else 0)
        self.sched_tree.clear()
        for t in bridge.scheduler_tasks():
            item = QTreeWidgetItem([
                str(t.get("name", t.get("id", "?"))),
                str(t.get("state", "?")),
                str(t.get("quantum_score", t.get("score", "—"))),
            ])
            self.sched_tree.addTopLevelItem(item)

        # Memory
        mem = bridge.memory_stats()
        total = mem.get("total_pages", 1) or 1
        used = mem.get("used_pages", 0)
        pct = int(used / total * 100)
        self.mem_label.setText(f"Pages: {used}/{total} — Faults: {mem.get('page_faults', 0)}")
        self.mem_bar.setValue(pct)
        self.mem_detail.setText(
            f"Total: {total}  Used: {used}  Free: {mem.get('free_pages', 0)}"
        )

        # Processes
        self.proc_tree.clear()
        for p in bridge.process_list():
            item = QTreeWidgetItem([
                str(p.get("pid", "?")),
                str(p.get("name", "?")),
                str(p.get("state", "?")),
                str(p.get("cpu", "—")),
                str(p.get("memory", "—")),
            ])
            self.proc_tree.addTopLevelItem(item)

        # Network
        status = bridge.network_status()
        self.net_label.setText(f"Connections: {status.get('connections', 0)}  Running: {status.get('running', False)}")
        self.net_tree.clear()
        for c in bridge.network_connections():
            item = QTreeWidgetItem([
                str(c.get("host", "?")),
                str(c.get("port", "?")),
                str(c.get("traffic_type", "?")),
                str(c.get("priority", "?")),
            ])
            self.net_tree.addTopLevelItem(item)


# ── Settings ───────────────────────────────────────────────────────
class SettingsWindow(_AppWindow):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("UmerOS Settings", parent)
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.addWidget(QLabel("Appearance"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme:"))
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch()
        lay.addLayout(theme_row)
        lay.addWidget(QLabel("Display"))
        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Font size:"))
        self.font_spin = QSpinBox()
        self.font_spin.setRange(8, 24)
        self.font_spin.setValue(11)
        font_row.addWidget(self.font_spin)
        font_row.addStretch()
        lay.addLayout(font_row)
        lay.addWidget(QLabel("Behavior"))
        self.startup_check = QPushButton("Run Boot Sequence")
        self.startup_check.clicked.connect(self._run_boot)
        lay.addWidget(self.startup_check)
        btn_row = QHBoxLayout()
        btn_apply = QPushButton("Apply")
        btn_apply.clicked.connect(self._apply)
        btn_row.addWidget(btn_apply)
        btn_row.addStretch()
        lay.addLayout(btn_row)
        lay.addStretch()
        self._settings = QSettings(ORG_NAME, APP_NAME)
        self._load_settings()

    def _load_settings(self) -> None:
        theme = self._settings.value("theme", "dark")
        self.theme_combo.setCurrentIndex(0 if theme == "dark" else 1)
        font_size = self._settings.value("font_size", 11, type=int)
        self.font_spin.setValue(font_size)

    def _apply(self) -> None:
        mode = ThemeMode.DARK if self.theme_combo.currentIndex() == 0 else ThemeMode.LIGHT
        app = QApplication.instance()
        if app:
            app.setPalette(_build_palette(mode))
            app.setStyleSheet(_DARK_QSS if mode is ThemeMode.DARK else _LIGHT_QSS)
        self._settings.setValue("theme", "dark" if mode is ThemeMode.DARK else "light")
        self._settings.setValue("font_size", self.font_spin.value())

    def _run_boot(self) -> None:
        if show_legal_warning:
            try:
                show_legal_warning()
            except Exception:
                pass
        QMessageBox.information(self, "Boot", "Boot sequence check complete.")


# ── Text Editor ────────────────────────────────────────────────────
class EditorWindow(_AppWindow):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("UmerOS Editor", parent)
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 8)
        toolbar = QHBoxLayout()
        self.file_label = QLabel("Untitled")
        self.file_label.setStyleSheet("font-weight:bold; color:%s;" % COLORS["accent"])
        toolbar.addWidget(self.file_label, 1)
        for text, fn in [("New", self._new), ("Open", self._open), ("Save", self._save),
                         ("Save As", self._save_as), ("QFS Save", self._qfs_save)]:
            btn = QPushButton(text)
            btn.clicked.connect(fn)
            toolbar.addWidget(btn)
        lay.addLayout(toolbar)
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Cascadia Mono, Consolas", 11))
        lay.addWidget(self.editor, 1)
        self._current_path: Optional[str] = None
        self._modified = False
        self.editor.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self) -> None:
        self._modified = True

    def _mark_saved(self) -> None:
        self._modified = False

    def _confirm_discard(self) -> bool:
        if not self._modified:
            return True
        ret = QMessageBox.question(
            self, "Unsaved Changes",
            "You have unsaved changes. Discard?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return ret == QMessageBox.StandardButton.Discard

    def _new(self) -> None:
        if not self._confirm_discard():
            return
        self.editor.clear()
        self.file_label.setText("Untitled")
        self._current_path = None
        self._modified = False

    def _open(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "All Files (*)")
        if path:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    self.editor.setPlainText(f.read())
                self.file_label.setText(path)
                self._current_path = path
                self._modified = False
            except Exception as exc:
                QMessageBox.warning(self, "Error", str(exc))

    def _save(self) -> None:
        if self._current_path:
            try:
                with open(self._current_path, "w", encoding="utf-8") as f:
                    f.write(self.editor.toPlainText())
                self._mark_saved()
            except Exception as exc:
                QMessageBox.warning(self, "Error", str(exc))
        else:
            self._save_as()

    def _save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save File", "", "All Files (*)")
        if path:
            self._current_path = path
            self.file_label.setText(path)
            self._save()

    def _qfs_save(self) -> None:
        path, ok = QInputDialog.getText(self, "QFS Path", "Save to QFS path:", text="/")
        if ok and path:
            data = self.editor.toPlainText()
            if bridge.fs_write(path, data):
                self._mark_saved()
                QMessageBox.information(self, "QFS", f"Saved to {path}")
            else:
                QMessageBox.warning(self, "QFS", f"Failed to save to {path}")

    def closeEvent(self, event) -> None:
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()


# ── Package Manager ────────────────────────────────────────────────
class PackagesWindow(_AppWindow):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("UmerOS Package Manager", parent)
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(QLabel("Installed Packages (placeholder)"))
        self.pkg_list = QListWidget()
        pkgs = ["umer-kernel", "umer-scheduler", "umer-qfs", "umer-network",
                "umer-security", "umer-gui"]
        for p in pkgs:
            self.pkg_list.addItem(p)
        lay.addWidget(self.pkg_list, 1)
        btn_row = QHBoxLayout()
        for text in ["Install", "Update", "Remove", "Refresh"]:
            btn = QPushButton(text)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search packages…")
        lay.addWidget(self.search)


# ── Network ────────────────────────────────────────────────────────
class NetworkWindow(_AppWindow):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("UmerOS Network", parent)
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 8)
        tabs = QTabWidget()
        # Overview tab
        overview = QWidget()
        o_lay = QVBoxLayout(overview)
        self.status_label = QLabel("Status: —")
        self.status_label.setFont(QFont("Consolas", 11))
        o_lay.addWidget(self.status_label)
        self.qos_label = QLabel("QoS: —")
        self.qos_label.setFont(QFont("Consolas", 10))
        o_lay.addWidget(self.qos_label)
        o_lay.addStretch()
        tabs.addTab(overview, "Overview")
        # Connections tab
        conn_tab = QWidget()
        c_lay = QVBoxLayout(conn_tab)
        self.conn_tree = QTreeWidget()
        self.conn_tree.setHeaderLabels(["Host", "Port", "Type", "Priority", "Opened"])
        c_lay.addWidget(self.conn_tree, 1)
        tabs.addTab(conn_tab, "Connections")
        # VPN tab
        vpn_tab = QWidget()
        v_lay = QVBoxLayout(vpn_tab)
        self.vpn_label = QLabel("VPN: —")
        v_lay.addWidget(self.vpn_label)
        btn_vpn = QPushButton("Toggle VPN")
        btn_vpn.clicked.connect(self._toggle_vpn)
        v_lay.addWidget(btn_vpn)
        v_lay.addStretch()
        tabs.addTab(vpn_tab, "VPN")
        # DNS tab
        dns_tab = QWidget()
        d_lay = QVBoxLayout(dns_tab)
        self.dns_input = QLineEdit()
        self.dns_input.setPlaceholderText("Hostname to resolve…")
        d_lay.addWidget(self.dns_input)
        btn_resolve = QPushButton("Resolve")
        btn_resolve.clicked.connect(self._resolve_dns)
        d_lay.addWidget(btn_resolve)
        self.dns_result = QPlainTextEdit()
        self.dns_result.setReadOnly(True)
        d_lay.addWidget(self.dns_result, 1)
        tabs.addTab(dns_tab, "DNS")
        lay.addWidget(tabs, 1)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(3000)
        self._refresh()

    def _refresh(self) -> None:
        status = bridge.network_status()
        self.status_label.setText(f"Running: {status.get('running', False)}  |  "
                                  f"Connections: {status.get('connections', 0)}")
        qos = status.get("qos", {})
        self.qos_label.setText(f"Bandwidth: {qos.get('bandwidth_kbps', '?')} kbps  |  "
                               f"Low BW: {qos.get('low_bandwidth', '?')}")
        vpn = status.get("vpn", {})
        self.vpn_label.setText(f"VPN available: {vpn.get('available', False)}  |  "
                               f"Connected: {vpn.get('connected', False)}")
        self.conn_tree.clear()
        for c in bridge.network_connections():
            item = QTreeWidgetItem([
                str(c.get("host", "?")),
                str(c.get("port", "?")),
                str(c.get("traffic_type", "?")),
                str(c.get("priority", "?")),
                str(round(c.get("opened_at", 0), 1)),
            ])
            self.conn_tree.addTopLevelItem(item)

    def _toggle_vpn(self) -> None:
        if bridge.network:
            try:
                vpn = bridge.network.vpn  # type: ignore[union-attr]
                if vpn.is_connected:
                    vpn.disconnect()
                else:
                    vpn.connect()
                self._refresh()
            except Exception as exc:
                QMessageBox.warning(self, "VPN", str(exc))

    def _resolve_dns(self) -> None:
        hostname = self.dns_input.text().strip()
        if not hostname:
            return
        if bridge.network:
            try:
                results = bridge.network.resolve(hostname)  # type: ignore[union-attr]
                self.dns_result.setPlainText("\n".join(results) if results else "No results.")
            except Exception as exc:
                self.dns_result.setPlainText(f"Error: {exc}")
        else:
            self.dns_result.setPlainText("Network stack unavailable.")


# ── Quantum Lab ────────────────────────────────────────────────────
class QuantumWindow(_AppWindow):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("UmerOS Quantum Lab", parent)
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(QLabel("Quantum Computing Lab (Simulation)"))
        tabs = QTabWidget()
        # Circuit tab
        circuit_tab = QWidget()
        c_lay = QVBoxLayout(circuit_tab)
        self.circuit_display = QPlainTextEdit()
        self.circuit_display.setReadOnly(True)
        self.circuit_display.setFont(QFont("Cascadia Mono", 11))
        self.circuit_display.setPlainText(
            "┌───┐ ┌───┐ ┌───┐\n"
            "│ H ├──┤ X ├──┤ M │\n"
            "└───┘ └───┘ └───┘\n"
            "┌───┐         ┌───┐\n"
            "│ H ├─────────┤ M │\n"
            "└───┘         └───┘"
        )
        c_lay.addWidget(self.circuit_display)
        btn_row = QHBoxLayout()
        for name in ["Simulate", "Reset", "Export"]:
            btn = QPushButton(name)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        c_lay.addLayout(btn_row)
        tabs.addTab(circuit_tab, "Circuit")
        # Qubits tab
        qubit_tab = QWidget()
        q_lay = QVBoxLayout(qubit_tab)
        self.qubit_display = QPlainTextEdit()
        self.qubit_display.setReadOnly(True)
        self.qubit_display.setPlainText(
            "Qubit 0: |0⟩ (α=1.000, β=0.000)\n"
            "Qubit 1: |0⟩ (α=1.000, β=0.000)\n"
            "Qubit 2: |0⟩ (α=1.000, β=0.000)"
        )
        q_lay.addWidget(self.qubit_display)
        tabs.addTab(qubit_tab, "Qubits")
        # Stats tab
        stats_tab = QWidget()
        s_lay = QVBoxLayout(stats_tab)
        self.quantum_stats = QLabel("Quantum kernel stats: —")
        s_lay.addWidget(self.quantum_stats)
        s_lay.addStretch()
        tabs.addTab(stats_tab, "Stats")
        lay.addWidget(tabs, 1)


# ── Security Center ────────────────────────────────────────────────
class SecurityWindow(_AppWindow):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("UmerOS Security Center", parent)
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 8)
        tabs = QTabWidget()
        # Overview
        overview = QWidget()
        o_lay = QVBoxLayout(overview)
        self.audit_label = QLabel("Security audit: —")
        self.audit_label.setFont(QFont("Consolas", 11))
        o_lay.addWidget(self.audit_label)
        self.audit_tree = QTreeWidget()
        self.audit_tree.setHeaderLabels(["Module", "Status"])
        o_lay.addWidget(self.audit_tree, 1)
        btn_refresh = QPushButton("Refresh Audit")
        btn_refresh.clicked.connect(self._refresh_audit)
        o_lay.addWidget(btn_refresh)
        tabs.addTab(overview, "Audit")
        # Secure Boot
        boot_tab = QWidget()
        b_lay = QVBoxLayout(boot_tab)
        self.boot_label = QLabel("Secure Boot: —")
        b_lay.addWidget(self.boot_label)
        btn_verify = QPushButton("Verify Boot Chain")
        btn_verify.clicked.connect(self._verify_boot)
        b_lay.addWidget(btn_verify)
        b_lay.addStretch()
        tabs.addTab(boot_tab, "Secure Boot")
        # IPC Auth
        ipc_tab = QWidget()
        i_lay = QVBoxLayout(ipc_tab)
        self.ipc_label = QLabel("IPC Authentication: —")
        i_lay.addWidget(self.ipc_label)
        btn_auth = QPushButton("Create Test Session")
        btn_auth.clicked.connect(self._test_auth)
        i_lay.addWidget(btn_auth)
        i_lay.addStretch()
        tabs.addTab(ipc_tab, "IPC Auth")
        # AI Monitor
        ai_tab = QWidget()
        a_lay = QVBoxLayout(ai_tab)
        self.ai_label = QLabel("AI Behavioral Monitor: —")
        a_lay.addWidget(self.ai_label)
        a_lay.addStretch()
        tabs.addTab(ai_tab, "AI Monitor")
        lay.addWidget(tabs, 1)
        self._refresh_audit()

    def _refresh_audit(self) -> None:
        audit = bridge.security_audit()
        modules = audit.get("modules", {})
        self.audit_label.setText(f"Modules scanned: {len(modules)}")
        self.audit_tree.clear()
        for name, info in modules.items():
            status = "OK" if "error" not in info else f"Error: {info['error']}"
            item = QTreeWidgetItem([name, status])
            self.audit_tree.addTopLevelItem(item)

    def _verify_boot(self) -> None:
        if bridge.secure_boot:
            try:
                result = bridge.secure_boot.verify()  # type: ignore[union-attr]
                self.boot_label.setText(f"Boot verified: {result}")
            except Exception as exc:
                self.boot_label.setText(f"Boot verification failed: {exc}")
        else:
            self.boot_label.setText("SecureBoot module unavailable.")

    def _test_auth(self) -> None:
        if bridge.auth:
            try:
                session = bridge.auth.create_session("test_process")  # type: ignore[union-attr]
                self.ipc_label.setText(f"Session created: {session}")
            except Exception as exc:
                self.ipc_label.setText(f"Auth failed: {exc}")
        else:
            self.ipc_label.setText("IPCAuthenticator unavailable.")


# ── Boot Manager ───────────────────────────────────────────────────
class BootWindow(_AppWindow):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("UmerOS Boot Manager", parent)
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.addWidget(QLabel("Boot Sequence"))
        self.boot_log = QPlainTextEdit()
        self.boot_log.setReadOnly(True)
        self.boot_log.setFont(QFont("Cascadia Mono, Consolas", 10))
        lay.addWidget(self.boot_log, 1)
        btn_row = QHBoxLayout()
        btn_start = QPushButton("Start Boot")
        btn_start.clicked.connect(self._start_boot)
        btn_row.addWidget(btn_start)
        btn_legal = QPushButton("Legal Warning")
        btn_legal.clicked.connect(self._show_legal)
        btn_row.addWidget(btn_legal)
        btn_row.addStretch()
        lay.addLayout(btn_row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        lay.addWidget(self.progress)
        self._boot_steps = []
        self._boot_idx = 0
        self._boot_timer = QTimer(self)
        self._boot_timer.timeout.connect(self._boot_tick)

    def _log(self, msg: str) -> None:
        self.boot_log.appendPlainText(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def _start_boot(self) -> None:
        self.boot_log.clear()
        self.progress.setValue(0)
        self._boot_steps = [
            (10, "Initializing hardware abstraction layer…"),
            (20, "Loading kernel modules…"),
            (35, "Starting scheduler…"),
            (45, "Mounting QFS filesystem…"),
            (55, "Initializing memory manager…"),
            (65, "Starting network stack…"),
            (75, "Loading security modules…"),
            (85, "Running integrity checks…"),
            (95, "Starting GUI shell…"),
            (100, "Boot complete."),
        ]
        self._boot_idx = 0
        self._boot_timer.start(300)

    def _boot_tick(self) -> None:
        if self._boot_idx >= len(self._boot_steps):
            self._boot_timer.stop()
            if boot_kernel:
                try:
                    boot_kernel()  # type: ignore[misc]
                except Exception as exc:
                    self._log(f"Kernel boot error: {exc}")
            self._log("System ready.")
            return
        pct, msg = self._boot_steps[self._boot_idx]
        self.progress.setValue(pct)
        self._log(msg)
        self._boot_idx += 1

    def _show_legal(self) -> None:
        if show_legal_warning:
            try:
                show_legal_warning()
            except Exception:
                pass
        QMessageBox.information(self, "Legal", "UmerOS — For educational purposes only.\nNo warranty provided.")


# ── Games ──────────────────────────────────────────────────────────
class GamesWindow(_AppWindow):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("UmerOS Games", parent)
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.addWidget(QLabel("Mini Games"))
        # Tic-Tac-Toe
        ttt_group = QFrame()
        ttt_group.setStyleSheet("QFrame{border:1px solid %s; border-radius:8px; padding:8px;}" % COLORS["border"])
        ttt_lay = QVBoxLayout(ttt_group)
        ttt_lay.addWidget(QLabel("Tic-Tac-Toe"))
        self.ttt_board: List[QPushButton] = []
        grid = QGridLayout()
        for i in range(9):
            btn = QPushButton("")
            btn.setFixedSize(60, 60)
            btn.setFont(QFont("Consolas", 18, QFont.Weight.Bold))
            btn.clicked.connect(lambda _, idx=i: self._ttt_click(idx))
            grid.addWidget(btn, i // 3, i % 3)
            self.ttt_board.append(btn)
        ttt_lay.addLayout(grid)
        self.ttt_status = QLabel("X's turn")
        ttt_lay.addWidget(self.ttt_status)
        btn_reset = QPushButton("New Game")
        btn_reset.clicked.connect(self._ttt_reset)
        ttt_lay.addWidget(btn_reset)
        lay.addWidget(ttt_group)
        lay.addStretch()
        self._ttt_state = [""] * 9
        self._ttt_turn = "X"

    def _ttt_click(self, idx: int) -> None:
        if self._ttt_state[idx]:
            return
        self._ttt_state[idx] = self._ttt_turn
        self.ttt_board[idx].setText(self._ttt_turn)
        if self._check_ttt_win(self._ttt_turn):
            self.ttt_status.setText(f"{self._ttt_turn} wins!")
            return
        if all(self._ttt_state):
            self.ttt_status.setText("Draw!")
            return
        self._ttt_turn = "O" if self._ttt_turn == "X" else "X"
        self.ttt_status.setText(f"{self._ttt_turn}'s turn")

    def _ttt_reset(self) -> None:
        self._ttt_state = [""] * 9
        self._ttt_turn = "X"
        for btn in self.ttt_board:
            btn.setText("")
        self.ttt_status.setText("X's turn")

    def _check_ttt_win(self, player: str) -> bool:
        b = self._ttt_state
        wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
        return any(b[i] == b[j] == b[k] == player for i,j,k in wins)


# ── Documentation ──────────────────────────────────────────────────
class DocsWindow(_AppWindow):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("UmerOS Documentation", parent)
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 8)
        search = QLineEdit()
        search.setPlaceholderText("Search documentation…")
        lay.addWidget(search)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.doc_list = QListWidget()
        self.doc_list.setMaximumWidth(200)
        docs = [
            "Getting Started", "Kernel Architecture", "Scheduler",
            "Memory Manager", "QFS File System", "Network Stack",
            "Security", "Boot Process", "GUI Guide", "API Reference",
        ]
        for d in docs:
            self.doc_list.addItem(d)
        self.doc_list.currentTextChanged.connect(self._load_doc)
        splitter.addWidget(self.doc_list)
        self.doc_view = QPlainTextEdit()
        self.doc_view.setReadOnly(True)
        self.doc_view.setFont(QFont("Segoe UI", 11))
        splitter.addWidget(self.doc_view)
        splitter.setSizes([200, 600])
        lay.addWidget(splitter, 1)

    def _load_doc(self, title: str) -> None:
        content = {
            "Getting Started": (
                "UmerOS Documentation\n"
                "====================\n\n"
                "Welcome to UmerOS — a quantum-inspired operating system.\n\n"
                "This GUI provides access to all system components:\n"
                "• Terminal — command-line interface\n"
                "• Files — QFS file browser\n"
                "• Monitor — system resource monitor\n"
                "• Settings — theme and display options\n"
                "• Editor — text editor with QFS integration\n"
                "• Packages — package manager\n"
                "• Network — network stack, VPN, DNS\n"
                "• Quantum — quantum computing lab\n"
                "• Security — security audit tools\n"
                "• Boot — boot manager\n"
                "• Games — mini games\n"
                "• Docs — this documentation"
            ),
            "Kernel Architecture": (
                "The UmerKernel provides:\n"
                "• Process management with PID allocation\n"
                "• Sysctl registry for runtime configuration\n"
                "• Kernel taint tracking\n"
                "• AI-powered subsystem integration\n"
                "• Security subsystem hooks"
            ),
            "Scheduler": (
                "HybridScheduler uses quantum-inspired scoring:\n"
                "• Tasks have quantum_score for priority\n"
                "• Supports task states: READY, RUNNING, BLOCKED, DONE\n"
                "• Adaptive scheduling based on system load"
            ),
            "Memory Manager": (
                "VirtualMemoryManager simulates 4KiB pages:\n"
                "• Page table simulation\n"
                "• Page fault tracking\n"
                "• Stats: total_pages, used_pages, free_pages, page_faults"
            ),
            "QFS File System": (
                "QFS provides compressed file storage:\n"
                "• write_file(path, data) / read_file(path)\n"
                "• list_dir(path) / create_dir(path) / delete_file(path)\n"
                "• Uses zlib compression via QuantumCompressor"
            ),
            "Network Stack": (
                "NetworkStack includes:\n"
                "• DNSOverHTTPS — DNS resolution with fallback\n"
                "• VPNClient — WireGuard wrapper\n"
                "• MDNSDiscovery — local peer discovery\n"
                "• AINetworkQoS — traffic classification\n"
                "• TCP connection management"
            ),
            "Security": (
                "Security modules:\n"
                "• SecureBoot — boot chain verification\n"
                "• IPCAuthenticator — HMAC-SHA3-512 sessions\n"
                "• AIBehavioralMonitor — anomaly detection"
            ),
            "Boot Process": (
                "Boot sequence:\n"
                "1. show_legal_warning() — display terms\n"
                "2. Hardware checks\n"
                "3. Kernel module loading\n"
                "4. Scheduler initialization\n"
                "5. QFS mount\n"
                "6. Network stack start\n"
                "7. Security module activation\n"
                "8. GUI shell launch"
            ),
            "GUI Guide": (
                "The GUI provides:\n"
                "• Menu bar with File, View, Help menus\n"
                "• Desktop with app icons (double-click to open)\n"
                "• Dock bar at bottom for quick access\n"
                "• LaunchPad overlay (Ctrl+L)\n"
                "• Window management with animations\n"
                "• System tray integration\n"
                "• Dark/Light theme toggle"
            ),
            "API Reference": (
                "Backend Bridge API:\n"
                "• bridge.kernel_state() → dict\n"
                "• bridge.process_list() → list\n"
                "• bridge.memory_stats() → dict\n"
                "• bridge.fs_list(path) → list\n"
                "• bridge.fs_read(path) → str\n"
                "• bridge.fs_write(path, data) → bool\n"
                "• bridge.network_status() → dict\n"
                "• bridge.security_audit() → dict\n"
                "• bridge.scheduler_stats() → dict"
            ),
        }
        self.doc_view.setPlainText(content.get(title, f"Documentation for '{title}' not found."))


# ╔══════════════════════════════════════════════════════════════════╗
# ║                    LAUNCHPAD OVERLAY                             ║
# ╚══════════════════════════════════════════════════════════════════╝
class LaunchPadOverlay(QWidget):
    """Full-screen app launcher overlay."""

    app_selected = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(900, 600)
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)
        self._anim: Optional[QPropertyAnimation] = None
        self._build_ui()
        self.hide()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        bg = QFrame()
        bg.setStyleSheet(
            "QFrame{background:rgba(26,26,46,0.95); border-radius:16px;}"
        )
        bg_lay = QVBoxLayout(bg)
        title = QLabel("LaunchPad")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setStyleSheet("color:white; background:transparent;")
        bg_lay.addWidget(title)
        grid = QGridLayout()
        grid.setSpacing(20)
        for i, (name, key, emoji) in enumerate(DESKTOP_APPS):
            frame = _ClickableFrame()
            frame.setObjectName("dockItem")
            frame.setFixedSize(140, 120)
            frame.setCursor(Qt.CursorShape.PointingHandCursor)
            frame_lay = QVBoxLayout(frame)
            frame_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lbl = QLabel(emoji)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lbl.setFont(QFont("Segoe UI Emoji", 28))
            icon_lbl.setStyleSheet("background:transparent;")
            name_lbl = QLabel(name)
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_lbl.setObjectName("dockLabel")
            name_lbl.setStyleSheet("background:transparent; font-size:11px;")
            frame_lay.addWidget(icon_lbl)
            frame_lay.addWidget(name_lbl)
            frame.clicked.connect(lambda _, k=key: self._on_click(k))
            grid.addWidget(frame, i // 4, i % 4)
        bg_lay.addLayout(grid)
        layout.addWidget(bg)

    def _on_click(self, key: str) -> None:
        self.hide()
        self.app_selected.emit(key)

    def toggle(self) -> None:
        if self.isVisible():
            self._fade_out()
        else:
            self._fade_in()

    def _fade_in(self) -> None:
        self.show()
        self.raise_()
        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim.setDuration(200)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    def _fade_out(self) -> None:
        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim.setDuration(150)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim.finished.connect(self.hide)
        self._anim.start()


# ╔══════════════════════════════════════════════════════════════════╗
# ║                      MAIN WINDOW                                ║
# ╚══════════════════════════════════════════════════════════════════╝
class UmerOSMainWindow(QMainWindow):
    """Desktop shell: menu bar, desktop grid, dock, and window manager."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — Quantum-Inspired OS")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        # Window registry
        self._windows: Dict[str, _AppWindow] = {}
        self._window_classes: Dict[str, type] = {
            "terminal": TerminalWindow,
            "files": FilesWindow,
            "monitor": MonitorWindow,
            "settings": SettingsWindow,
            "editor": EditorWindow,
            "packages": PackagesWindow,
            "network": NetworkWindow,
            "quantum": QuantumWindow,
            "security": SecurityWindow,
            "boot": BootWindow,
            "games": GamesWindow,
            "docs": DocsWindow,
        }

        self._build_menu_bar()

        # Central layout: dock on top, desktop below
        central = QWidget()
        central_lay = QVBoxLayout(central)
        central_lay.setContentsMargins(0, 0, 0, 0)
        central_lay.setSpacing(0)
        self._build_dock(central_lay)
        self._build_desktop(central_lay)
        self.setCentralWidget(central)

        self._build_status_bar()

        # LaunchPad
        self._launchpad = LaunchPadOverlay(self)
        self._launchpad.app_selected.connect(self._open_app)

        # Global shortcuts
        QShortcut(QKeySequence("Ctrl+L"), self, self._launchpad.toggle)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.close)
        QShortcut(QKeySequence("F1"), self, self._show_about)

        self._apply_theme(ThemeMode.DARK)

    # ── Theme ─────────────────────────────────────────────────────
    def _apply_theme(self, mode: ThemeMode) -> None:
        app = QApplication.instance()
        if app:
            app.setPalette(_build_palette(mode))
            app.setStyleSheet(_DARK_QSS if mode is ThemeMode.DARK else _LIGHT_QSS)

    # ── Menu Bar ──────────────────────────────────────────────────
    def _build_menu_bar(self) -> None:
        mb = self.menuBar()

        def _make_action(text: str, slot=None, shortcut: str | None = None) -> QAction:
            a = QAction(text, self)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            if slot:
                a.triggered.connect(slot)
            return a

        # File
        file_menu = mb.addMenu("&File")
        file_menu.addAction(_make_action("New Terminal", lambda: self._open_app("terminal")))
        file_menu.addAction(_make_action("New Editor", lambda: self._open_app("editor")))
        file_menu.addAction(_make_action("Open Files", lambda: self._open_app("files")))
        file_menu.addSeparator()
        file_menu.addAction(_make_action("Exit", self.close, "Ctrl+Q"))
        # View
        view_menu = mb.addMenu("&View")
        view_menu.addAction(_make_action("LaunchPad", self._launchpad.toggle, "Ctrl+L"))
        view_menu.addAction(_make_action("System Monitor", lambda: self._open_app("monitor")))
        view_menu.addAction(_make_action("Settings", lambda: self._open_app("settings")))
        view_menu.addSeparator()
        view_menu.addAction(_make_action("Toggle Dark/Light", self._toggle_theme))
        # Apps
        apps_menu = mb.addMenu("&Apps")
        for name, key in [(n, k) for n, k, _ in DESKTOP_APPS]:
            apps_menu.addAction(_make_action(name, lambda k=key: self._open_app(k)))
        # Help
        help_menu = mb.addMenu("&Help")
        help_menu.addAction(_make_action("Documentation", lambda: self._open_app("docs")))
        help_menu.addAction(_make_action("About UmerOS", self._show_about))

    def _toggle_theme(self) -> None:
        app = QApplication.instance()
        if not app:
            return
        current = app.palette()
        bg = current.color(QPalette.ColorRole.Window)
        mode = ThemeMode.LIGHT if bg.lightness() < 128 else ThemeMode.DARK
        self._apply_theme(mode)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<h2>{APP_NAME} v{APP_VERSION}</h2>"
            "<p>A quantum-inspired operating system with PyQt6 GUI.</p>"
            "<p>Features: kernel management, QFS filesystem, network stack, "
            "security center, quantum lab, and 12 integrated applications.</p>"
            "<p><b>Keyboard Shortcuts:</b></p>"
            "<ul>"
            "<li>Ctrl+L — LaunchPad</li>"
            "<li>Ctrl+Q — Quit</li>"
            "<li>F1 — About</li>"
            "</ul>",
        )

    # ── Desktop ───────────────────────────────────────────────────
    def _build_desktop(self, parent_layout: QVBoxLayout) -> None:
        desktop = QWidget()
        grid = QGridLayout(desktop)
        grid.setSpacing(16)
        grid.setContentsMargins(40, 30, 40, 80)
        for i, (name, key, emoji) in enumerate(DESKTOP_APPS):
            frame = _ClickableFrame()
            frame.setObjectName("dockItem")
            frame.setFixedSize(130, 110)
            frame.setCursor(Qt.CursorShape.PointingHandCursor)
            frame_lay = QVBoxLayout(frame)
            frame_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lbl = QLabel(emoji)
            icon_lbl.setObjectName("desktopIcon")
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lbl.setFont(QFont("Segoe UI Emoji", 30))
            icon_lbl.setStyleSheet("background:transparent;")
            name_lbl = QLabel(name)
            name_lbl.setObjectName("desktopLabel")
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_lbl.setStyleSheet("background:transparent; font-size:11px;")
            frame_lay.addWidget(icon_lbl)
            frame_lay.addWidget(name_lbl)
            frame.clicked.connect(lambda _, k=key: self._open_app(k))
            grid.addWidget(frame, i // 4, i % 4)
        # Fill remaining grid cells with spacers
        for idx in range(len(DESKTOP_APPS), 16):
            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            grid.addWidget(spacer, idx // 4, idx % 4)
        parent_layout.addWidget(desktop, 1)

    # ── Dock ──────────────────────────────────────────────────────
    def _build_dock(self, parent_layout: QVBoxLayout) -> None:
        dock = QFrame()
        dock.setFixedHeight(64)
        dock.setStyleSheet(
            "QFrame{background:rgba(74,35,90,0.9); border-top:1px solid %s;}"
            "QPushButton{background:transparent; color:%s; border:none; "
            "border-radius:8px; padding:6px 10px; font-size:10px;}"
            "QPushButton:hover{background:rgba(108,52,131,0.6);}"
            "QLabel{background:transparent; color:%s; font-size:9px;}"
            % (COLORS["border"], COLORS["text"], COLORS["text_dim"])
        )
        dock_layout = QHBoxLayout(dock)
        dock_layout.setContentsMargins(8, 4, 8, 4)
        dock_layout.setSpacing(2)
        for name, key in DOCK_SHORTCUTS:
            btn_frame = QWidget()
            btn_lay = QVBoxLayout(btn_frame)
            btn_lay.setContentsMargins(0, 0, 0, 0)
            btn_lay.setSpacing(1)
            btn = QPushButton(f" {name[:4]} ")
            btn.setFixedSize(48, 36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._open_app(k))
            lbl = QLabel(name[:6])
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            btn_lay.addWidget(btn)
            btn_lay.addWidget(lbl)
            dock_layout.addWidget(btn_frame)
        dock_layout.addStretch()
        self.statusBar().setVisible(False)
        parent_layout.addWidget(dock)

    # ── Status Bar ────────────────────────────────────────────────
    def _build_status_bar(self) -> None:
        sb = QStatusBar()
        sb.setFixedHeight(28)
        self._status_label = QLabel("Ready")
        sb.addWidget(self._status_label, 1)
        self.setStatusBar(sb)
        # Timer for status updates
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_status)
        self._status_timer.start(5000)
        self._update_status()

    def _update_status(self) -> None:
        ks = bridge.kernel_state()
        ms = bridge.memory_stats()
        ns = bridge.network_status()
        parts = [
            f"Kernel: {ks.get('status', '?')}",
            f"Mem: {ms.get('used_pages', 0)}/{ms.get('total_pages', 0)}",
            f"Net: {'ON' if ns.get('running') else 'OFF'}",
            f"Conn: {ns.get('connections', 0)}",
        ]
        self._status_label.setText("  |  ".join(parts))

    # ── Window Management ─────────────────────────────────────────
    def _open_app(self, key: str) -> None:
        if key in self._windows:
            w = self._windows[key]
            if w.isMinimized():
                w.showNormal()
            w.raise_()
            w.activateWindow()
            return
        cls = self._window_classes.get(key)
        if not cls:
            return
        win = cls(parent=None)
        win.setWindowTitle(f"{APP_NAME} — {win.windowTitle()}")
        win.destroyed.connect(lambda _, k=key: self._windows.pop(k, None))
        self._windows[key] = win
        win.show()
        win.raise_()
        win.activateWindow()


# ╔══════════════════════════════════════════════════════════════════╗
# ║                        ENTRY POINT                              ║
# ╚══════════════════════════════════════════════════════════════════╝
def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORG_NAME)
    app.setPalette(_build_palette(ThemeMode.DARK))
    app.setStyleSheet(_DARK_QSS)
    font = QFont("Segoe UI", 11)
    app.setFont(font)

    window = UmerOSMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
