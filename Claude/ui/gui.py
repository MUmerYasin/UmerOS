"""
Umer OS Fluidic UI Shell  [TODAY - Kivy / fallback headless]
=============================================================
Provides the Umer OS desktop environment.

TODAY:
  - Kivy-based adaptive GUI (falls back to headless mode if Kivy is absent).
  - TaskBar with notification support.
  - AppLauncher grid with keyword search.
  - VoiceController stub (Vosk / Whisper-tiny when available).
  - AIUIAdapter — keyword-based layout suggestions.

EXPERIMENTAL:
  - GPU-accelerated window compositing via Kivy OpenGL backend.
  - Gesture recognition via camera input.

FUTURE:
  - Full voice + gesture control with on-device speech models.
  - AR/VR integration hooks.
  - TODO: QPU integration — quantum-inspired personalisation.

Run::

    python -m ui.gui          # launch desktop (requires Kivy)
    python -m ui.gui --headless  # headless/test mode

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from typing import Callable, Dict, List, Optional

log = logging.getLogger("UmerOS.GUI")

# Attempt Kivy import; fall back to headless mode gracefully
_KIVY_AVAILABLE = False
try:
    # Suppress Kivy's verbose startup logging
    os.environ.setdefault("KIVY_LOG_LEVEL", "warning")
    from kivy.app import App                          # type: ignore
    from kivy.core.window import Window               # type: ignore
    from kivy.uix.boxlayout import BoxLayout          # type: ignore
    from kivy.uix.button import Button                # type: ignore
    from kivy.uix.gridlayout import GridLayout        # type: ignore
    from kivy.uix.label import Label                  # type: ignore
    from kivy.uix.popup import Popup                  # type: ignore
    from kivy.uix.scrollview import ScrollView        # type: ignore
    from kivy.uix.textinput import TextInput          # type: ignore
    from kivy.clock import Clock                      # type: ignore
    _KIVY_AVAILABLE = True
    log.info("Kivy available — full GUI mode enabled.")
except ImportError:
    log.warning("Kivy not installed — running in headless mode. "
                "Install with: pip install kivy")


# ---------------------------------------------------------------------------
# VoiceController
# ---------------------------------------------------------------------------

class VoiceController:
    """Local speech-to-text command processor.

    TODAY:   Stub that returns a fixed "voice not available" string.
    EXPERIMENTAL: Vosk offline STT (install: pip install vosk).
    FUTURE:  Whisper-tiny on-device model for high-accuracy recognition.

    Privacy: All voice processing runs locally. No audio leaves the device.
    """

    def __init__(self) -> None:
        self._vosk_available = False
        try:
            import vosk  # type: ignore  # noqa: F401
            self._vosk_available = True
            log.info("VoiceController: Vosk available.")
        except ImportError:
            log.info("VoiceController: Vosk not installed (stub mode).")

    def listen(self, timeout: float = 3.0) -> str:
        """Listen for a voice command and return the transcribed text.

        Args:
            timeout: Maximum seconds to listen.

        Returns:
            Transcribed command string, or empty string if nothing heard.
        """
        if not self._vosk_available:
            log.debug("VoiceController.listen(): Vosk not available — returning stub.")
            return ""
        # EXPERIMENTAL: Real Vosk integration would go here.
        return ""

    def execute_command(self, cmd: str) -> str:
        """Map a voice command string to an OS action.

        Args:
            cmd: Transcribed command text.

        Returns:
            Human-readable result string.
        """
        cmd_lower = cmd.lower().strip()
        if "open" in cmd_lower:
            return f"Opening application: {cmd_lower.replace('open', '').strip()}"
        if "search" in cmd_lower:
            query = cmd_lower.replace("search", "").strip()
            return f"Searching for: {query}"
        if "shutdown" in cmd_lower or "power off" in cmd_lower:
            return "Shutdown requested."
        if "help" in cmd_lower:
            return "Available voice commands: open <app>, search <query>, shutdown, help."
        return f"Command not recognised: '{cmd}'"


# ---------------------------------------------------------------------------
# AIUIAdapter
# ---------------------------------------------------------------------------

class AIUIAdapter:
    """AI-driven layout and personalisation engine.

    TODAY:   Keyword-based heuristic suggestions.
    FUTURE:  LSTM-based usage-pattern predictor for adaptive layouts.
             TODO: QPU integration — quantum-inspired personalisation.

    Args:
        history_size: How many recent app-open events to track.
    """

    def __init__(self, history_size: int = 100) -> None:
        self._open_counts: Dict[str, int] = {}
        self._pinned:      List[str]      = []
        self._workspaces:  Dict[str, List[str]] = {}
        self._history_size = history_size

    def record_open(self, app_id: str) -> None:
        """Record an app-open event.

        Args:
            app_id: Application identifier.
        """
        self._open_counts[app_id] = self._open_counts.get(app_id, 0) + 1
        # Auto-pin apps opened 5+ times
        if self._open_counts[app_id] >= 5 and app_id not in self._pinned:
            self.pin_app(app_id)

    def pin_app(self, app_id: str) -> None:
        """Pin an app to the taskbar.

        Args:
            app_id: Application identifier.
        """
        if app_id not in self._pinned:
            self._pinned.append(app_id)
            log.info("AIUIAdapter: pinned '%s' to taskbar.", app_id)

    def unpin_app(self, app_id: str) -> None:
        """Unpin an app from the taskbar."""
        try:
            self._pinned.remove(app_id)
        except ValueError:
            pass

    def create_workspace(self, name: str, apps: List[str]) -> None:
        """Create a named workspace grouping a set of apps.

        Args:
            name: Workspace name (e.g. "Photo Editing").
            apps: List of app IDs in this workspace.
        """
        self._workspaces[name] = list(apps)
        log.info("AIUIAdapter: workspace '%s' created (%d apps).", name, len(apps))

    def suggest_layout(self, usage_stats: Optional[dict] = None) -> dict:
        """Return layout suggestions based on usage patterns.

        Args:
            usage_stats: Optional external stats dict to override internal counts.

        Returns:
            Dict with pinned, top_apps, and suggested_workspace keys.
        """
        counts = usage_stats or self._open_counts
        top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:6]
        suggestion = {
            "pinned":              list(self._pinned),
            "top_apps":            [a for a, _ in top],
            "suggested_workspace": None,
        }
        # Suggest a workspace if ≥3 apps are frequently used together
        if len(top) >= 3:
            suggestion["suggested_workspace"] = {
                "name": "Frequent Apps",
                "apps": [a for a, _ in top[:3]],
            }
        return suggestion

    def get_pinned(self) -> List[str]:
        """Return list of pinned app IDs."""
        return list(self._pinned)


# ---------------------------------------------------------------------------
# TaskBar (headless / Kivy)
# ---------------------------------------------------------------------------

class TaskBar:
    """Dynamic taskbar with notification support.

    Works in both headless mode (dict-based) and as a Kivy BoxLayout
    when Kivy is available.

    Args:
        ai_adapter: AIUIAdapter for pin-aware updates.
    """

    def __init__(self, ai_adapter: Optional[AIUIAdapter] = None) -> None:
        self._adapter      = ai_adapter or AIUIAdapter()
        self._apps:        Dict[str, str] = {}   # app_id → icon_path
        self._notifications: List[dict]   = []
        self._lock         = threading.Lock()

    def add_app_icon(self, name: str, icon_path: str = "") -> None:
        """Add an application icon to the taskbar.

        Args:
            name:      Application ID / label.
            icon_path: Path to icon image file.
        """
        with self._lock:
            self._apps[name] = icon_path
        log.debug("TaskBar: added icon '%s'.", name)

    def remove_app_icon(self, name: str) -> bool:
        """Remove an application icon.

        Args:
            name: Application ID.

        Returns:
            True if removed, False if not found.
        """
        with self._lock:
            removed = self._apps.pop(name, None)
        return removed is not None

    def show_notification(self, title: str, message: str) -> None:
        """Display a system notification.

        TODAY: Appends to notification list and logs.
        FUTURE: Native desktop notification via Kivy popup / D-Bus.

        Args:
            title:   Notification title.
            message: Notification body text.
        """
        entry = {"title": title, "message": message, "ts": time.time()}
        with self._lock:
            self._notifications.append(entry)
        log.info("NOTIFICATION [%s]: %s", title, message)

    def get_notifications(self, clear: bool = False) -> List[dict]:
        """Return pending notifications.

        Args:
            clear: If True, clear the list after returning.

        Returns:
            List of notification dicts.
        """
        with self._lock:
            result = list(self._notifications)
            if clear:
                self._notifications.clear()
        return result

    def get_apps(self) -> Dict[str, str]:
        """Return current taskbar apps as {name: icon_path}."""
        with self._lock:
            return dict(self._apps)


# ---------------------------------------------------------------------------
# AppLauncher
# ---------------------------------------------------------------------------

class AppLauncher:
    """Application grid with search and launch support.

    TODAY:  Dict-based launcher with keyword search.
    FUTURE: GPU-accelerated icon grid via Kivy GridLayout.

    Args:
        ai_adapter: AIUIAdapter to record app-open events.
    """

    # Built-in system app stubs
    DEFAULT_APPS: Dict[str, dict] = {
        "terminal":       {"label": "Terminal",        "icon": "🖥"},
        "file_manager":   {"label": "File Manager",    "icon": "📁"},
        "settings":       {"label": "Settings",        "icon": "⚙"},
        "browser":        {"label": "Web Browser",     "icon": "🌐"},
        "text_editor":    {"label": "Text Editor",     "icon": "📝"},
        "ai_assistant":   {"label": "AI Assistant",    "icon": "🤖"},
        "quantum_demo":   {"label": "Quantum Demo",    "icon": "⚛"},
        "security_centre":{"label": "Security Centre", "icon": "🔒"},
    }

    def __init__(
        self,
        ai_adapter:      Optional[AIUIAdapter] = None,
        launch_callback: Optional[Callable]   = None,
    ) -> None:
        self._apps:     Dict[str, dict] = dict(self.DEFAULT_APPS)
        self._adapter   = ai_adapter or AIUIAdapter()
        self._on_launch = launch_callback or (lambda app_id: None)

    def register_app(self, app_id: str, label: str, icon: str = "📦") -> None:
        """Register a new application with the launcher.

        Args:
            app_id: Unique application identifier.
            label:  Human-readable name.
            icon:   Emoji or icon path.
        """
        self._apps[app_id] = {"label": label, "icon": icon}

    def load_apps(self) -> List[dict]:
        """Return all registered applications.

        Returns:
            List of app dicts with id, label, and icon keys.
        """
        return [
            {"id": k, "label": v["label"], "icon": v["icon"]}
            for k, v in self._apps.items()
        ]

    def search_apps(self, query: str) -> List[dict]:
        """Search applications by name keyword.

        Args:
            query: Search string (case-insensitive).

        Returns:
            List of matching app dicts.
        """
        q = query.lower()
        return [
            {"id": k, "label": v["label"], "icon": v["icon"]}
            for k, v in self._apps.items()
            if q in k.lower() or q in v["label"].lower()
        ]

    def launch_app(self, app_id: str) -> bool:
        """Trigger launch of an application.

        Records the event in the AI adapter and calls the launch callback.

        Args:
            app_id: Application identifier.

        Returns:
            True if the app exists and was launched, False otherwise.
        """
        if app_id not in self._apps:
            log.warning("AppLauncher: unknown app '%s'.", app_id)
            return False
        self._adapter.record_open(app_id)
        self._on_launch(app_id)
        log.info("AppLauncher: launched '%s'.", app_id)
        return True


# ---------------------------------------------------------------------------
# UmerDesktop (Kivy App)
# ---------------------------------------------------------------------------

if _KIVY_AVAILABLE:

    class UmerDesktop(App):
        """Main Kivy desktop application for Umer OS.

        Builds a minimal desktop with a taskbar, app grid, search bar,
        and notification area.
        """

        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            self._ai         = AIUIAdapter()
            self._taskbar    = TaskBar(ai_adapter=self._ai)
            self._launcher   = AppLauncher(ai_adapter=self._ai)
            self._voice      = VoiceController()
            self._search_input: Optional[TextInput] = None
            self._app_grid:    Optional[GridLayout] = None
            self.title        = "Umer OS"

        def build(self):
            """Construct the UI widget tree."""
            Window.clearcolor = (0.08, 0.08, 0.12, 1)  # dark background

            root = BoxLayout(orientation="vertical")

            # ── Top bar ────────────────────────────────────────────────────
            topbar = BoxLayout(
                size_hint=(1, 0.06),
                padding=4,
                spacing=4,
            )
            lbl = Label(
                text="[b]Umer OS[/b]",
                markup=True,
                size_hint=(0.3, 1),
                color=(0.6, 0.8, 1, 1),
            )
            self._search_input = TextInput(
                hint_text="Search apps…",
                multiline=False,
                size_hint=(0.5, 0.9),
            )
            self._search_input.bind(text=self._on_search)

            time_lbl = Label(
                text=self._current_time(),
                size_hint=(0.2, 1),
                color=(0.8, 0.8, 0.8, 1),
            )
            Clock.schedule_interval(
                lambda dt: setattr(time_lbl, "text", self._current_time()), 1
            )
            topbar.add_widget(lbl)
            topbar.add_widget(self._search_input)
            topbar.add_widget(time_lbl)
            root.add_widget(topbar)

            # ── App grid ───────────────────────────────────────────────────
            scroll = ScrollView(size_hint=(1, 0.86))
            self._app_grid = GridLayout(
                cols=4,
                spacing=8,
                padding=8,
                size_hint_y=None,
            )
            self._app_grid.bind(
                minimum_height=self._app_grid.setter("height")
            )
            self._populate_grid(self._launcher.load_apps())
            scroll.add_widget(self._app_grid)
            root.add_widget(scroll)

            # ── Bottom taskbar ─────────────────────────────────────────────
            bottom = BoxLayout(size_hint=(1, 0.08), spacing=4, padding=4)
            for app in self._launcher.load_apps()[:4]:
                btn = Button(
                    text=f"{app['icon']}\n{app['label']}",
                    size_hint=(0.25, 1),
                    background_color=(0.15, 0.15, 0.25, 1),
                )
                btn.bind(
                    on_press=lambda b, aid=app["id"]: self._launcher.launch_app(aid)
                )
                bottom.add_widget(btn)
            root.add_widget(bottom)

            return root

        def _populate_grid(self, apps: List[dict]) -> None:
            """Fill the app grid with icon buttons."""
            if self._app_grid is None:
                return
            self._app_grid.clear_widgets()
            for app in apps:
                btn = Button(
                    text=f"{app['icon']}\n{app['label']}",
                    size_hint=(None, None),
                    size=(100, 100),
                    background_color=(0.12, 0.12, 0.2, 1),
                )
                btn.bind(
                    on_press=lambda b, aid=app["id"]: self._launcher.launch_app(aid)
                )
                self._app_grid.add_widget(btn)

        def _on_search(self, instance, value: str) -> None:
            """Update the app grid to show search results."""
            if value.strip():
                results = self._launcher.search_apps(value)
            else:
                results = self._launcher.load_apps()
            self._populate_grid(results)

        @staticmethod
        def _current_time() -> str:
            import datetime
            return datetime.datetime.now().strftime("%H:%M:%S")

        def on_start(self) -> None:
            log.info("UmerDesktop started.")

        def on_stop(self) -> None:
            log.info("UmerDesktop shutting down.")

else:
    # Headless stub when Kivy is not available
    class UmerDesktop:  # type: ignore[no-redef]
        """Headless Umer OS desktop (Kivy not installed)."""

        def __init__(self) -> None:
            self._ai       = AIUIAdapter()
            self._taskbar  = TaskBar(ai_adapter=self._ai)
            self._launcher = AppLauncher(ai_adapter=self._ai)
            self._voice    = VoiceController()
            log.info("UmerDesktop running in headless mode.")

        def run(self) -> None:
            """Start headless event loop (prints status, then exits)."""
            log.info("Headless desktop active. Apps: %d",
                     len(self._launcher.load_apps()))
            print("Umer OS Desktop — headless mode (Kivy not installed).")
            print("Install Kivy for full GUI: pip install kivy")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(headless: bool = False) -> None:
    """Launch the Umer OS desktop.

    Args:
        headless: Force headless mode even if Kivy is available.
    """
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s: %(message)s")

    if "--headless" in sys.argv:
        headless = True

    desktop = UmerDesktop()
    if _KIVY_AVAILABLE and not headless:
        desktop.run()
    else:
        if hasattr(desktop, "run"):
            desktop.run()
        else:
            log.info("Headless desktop ready.")


if __name__ == "__main__":
    main()
