#!/usr/bin/env python3
"""
Umer OS – Fluidic GUI (Kivy prototype)
Demonstrates an adaptive cross-platform window with AI assistant integration.
Requires: pip install kivy
"""

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
import random

# Try to import the AI assistant, fallback to a simple internal version
try:
    from umer_ai import AIAssistant
    ai_available = True
except ImportError:
    ai_available = False
    # Simple fallback AI
    class AIAssistant:
        def process(self, cmd):
            return f"[AI] Received: {cmd} (offline)"

class UmerDesktop(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        # Top status bar
        self.status = Label(text="Umer OS v1.0 | CPU: 12% | MEM: 34%", size_hint=(1, 0.1))
        self.add_widget(self.status)
        # Main area split
        main_area = BoxLayout(orientation='horizontal')
        # Left panel: apps
        left_panel = BoxLayout(orientation='vertical', size_hint=(0.3, 1))
        left_panel.add_widget(Label(text="Apps", bold=True))
        apps_list = ScrollView()
        apps_label = Label(text=" - AI Assistant\n - Quantum Explorer\n - File Manager\n - Settings")
        apps_list.add_widget(apps_label)
        left_panel.add_widget(apps_list)
        main_area.add_widget(left_panel)
        # Right panel: AI console
        right_panel = BoxLayout(orientation='vertical', size_hint=(0.7, 1))
        right_panel.add_widget(Label(text="AI Assistant Terminal", bold=True, size_hint=(1, 0.1)))
        self.history = ScrollView()
        self.history_label = Label(text="[System] Welcome to Umer OS GUI.\n")
        self.history.add_widget(self.history_label)
        right_panel.add_widget(self.history)
        # Input row
        input_row = BoxLayout(size_hint=(1, 0.1))
        self.cmd_input = TextInput(hint_text="Type command...", multiline=False)
        input_row.add_widget(self.cmd_input)
        send_btn = Button(text="Send", size_hint=(0.2, 1))
        send_btn.bind(on_press=self.send_command)
        input_row.add_widget(send_btn)
        right_panel.add_widget(input_row)
        main_area.add_widget(right_panel)
        self.add_widget(main_area)
        # AI instance
        self.ai = AIAssistant()
        # Periodic status update
        Clock.schedule_interval(self.update_status, 2)

    def send_command(self, instance):
        cmd = self.cmd_input.text.strip()
        if cmd:
            response = self.ai.process(cmd)
            self.history_label.text += f">>> {cmd}\n{response}\n"
            self.cmd_input.text = ""
            self.history.scroll_y = 0

    def update_status(self, dt):
        cpu = random.randint(5, 60)
        mem = random.randint(10, 70)
        self.status.text = f"Umer OS v1.0 | CPU: {cpu}% | MEM: {mem}%"

class UmerOSApp(App):
    def build(self):
        return UmerDesktop()

if __name__ == "__main__":
    if not ai_available:
        print("Note: umer_ai module not found, using offline AI stub.")
    UmerOSApp().run()