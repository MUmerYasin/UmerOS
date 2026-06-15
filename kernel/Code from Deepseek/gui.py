"""
Umer OS Fluidic GUI (tkinter)
Modern, adaptive interface with system monitor, AI chat, app launcher.
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
import time
import random
from umer_ai import AIAssistant

class FluidicDesktop(tk.Tk):
    def __init__(self, kernel, kernel_thread):
        super().__init__()
        self.title("Umer OS - Fluidic Desktop")
        self.geometry("1024x768")
        self.configure(bg="#1e1e2e")
        self.kernel = kernel
        self.kernel_thread = kernel_thread
        self.ai = AIAssistant()

        self.create_widgets()
        # Start system monitor update
        self.update_monitor()

    def create_widgets(self):
        # Title
        title = tk.Label(self, text="Umer OS", font=("Helvetica", 24, "bold"),
                         fg="#cdd6f4", bg="#1e1e2e")
        title.pack(pady=10)

        # System Monitor Frame
        monitor_frame = tk.LabelFrame(self, text="System Monitor", fg="#cdd6f4",
                                      bg="#313244", font=("Helvetica", 12))
        monitor_frame.pack(pady=10, padx=20, fill="x")
        self.cpu_label = tk.Label(monitor_frame, text="CPU: --", fg="#a6e3a1",
                                  bg="#313244")
        self.cpu_label.pack(side="left", padx=20)
        self.mem_label = tk.Label(monitor_frame, text="Memory: --", fg="#89b4fa",
                                  bg="#313244")
        self.mem_label.pack(side="left", padx=20)
        self.disk_label = tk.Label(monitor_frame, text="Disk: --", fg="#f9e2af",
                                   bg="#313244")
        self.disk_label.pack(side="left", padx=20)

        # AI Chat Frame
        chat_frame = tk.LabelFrame(self, text="AI Assistant", fg="#cdd6f4",
                                   bg="#313244")
        chat_frame.pack(pady=10, padx=20, fill="both", expand=True)
        self.chat_area = scrolledtext.ScrolledText(chat_frame, height=10,
                                                   bg="#45475a", fg="#cdd6f4",
                                                   insertbackground="white")
        self.chat_area.pack(fill="both", expand=True, padx=5, pady=5)

        input_frame = tk.Frame(chat_frame, bg="#313244")
        input_frame.pack(fill="x", padx=5, pady=5)
        self.entry = tk.Entry(input_frame, bg="#45475a", fg="#cdd6f4",
                              insertbackground="white")
        self.entry.pack(side="left", fill="x", expand=True)
        send_btn = tk.Button(input_frame, text="Send", command=self.send_message,
                             bg="#89b4fa", fg="#1e1e2e")
        send_btn.pack(side="right", padx=5)

        # App Launcher Frame
        launcher_frame = tk.Frame(self, bg="#1e1e2e")
        launcher_frame.pack(pady=20)
        apps = [
            ("Quantum Sim", self.run_quantum_sim),
            ("File Manager", self.run_file_manager),
            ("Security", self.run_security),
            ("Settings", self.run_settings)
        ]
        for name, cmd in apps:
            btn = tk.Button(launcher_frame, text=name, command=cmd,
                            bg="#cba6f7", fg="#1e1e2e", width=15)
            btn.pack(side="left", padx=10)

        # Shutdown button
        shutdown_btn = tk.Button(self, text="Shutdown Umer OS", command=self.shutdown,
                                 bg="#f38ba8", fg="#1e1e2e")
        shutdown_btn.pack(pady=10)

    def update_monitor(self):
        # Simulate live metrics
        cpu = random.randint(5, 80)
        mem = random.randint(20, 70)
        disk = random.randint(10, 60)
        self.cpu_label.config(text=f"CPU: {cpu}%")
        self.mem_label.config(text=f"Memory: {mem}%")
        self.disk_label.config(text=f"Disk: {disk}%")
        self.after(2000, self.update_monitor)

    def send_message(self):
        msg = self.entry.get()
        if msg:
            self.chat_area.insert(tk.END, f"User: {msg}\n")
            reply = self.ai.process_command(msg)
            self.chat_area.insert(tk.END, f"Umer AI: {reply}\n\n")
            self.chat_area.see(tk.END)
            self.entry.delete(0, tk.END)

    def run_quantum_sim(self):
        self.chat_area.insert(tk.END, "[Launcher] Opening Quantum Simulator...\n")
        # Could launch a separate window; here just message
        messagebox.showinfo("Quantum Sim", "Quantum simulation window would open here.")

    def run_file_manager(self):
        self.chat_area.insert(tk.END, "[Launcher] Opening File Manager...\n")

    def run_security(self):
        self.chat_area.insert(tk.END, "[Launcher] Opening Security Dashboard...\n")

    def run_settings(self):
        self.chat_area.insert(tk.END, "[Launcher] Opening Settings...\n")

    def shutdown(self):
        if messagebox.askokcancel("Shutdown", "Shut down Umer OS?"):
            self.kernel.running = False
            self.destroy()

def start_gui(kernel, kernel_thread):
    desktop = FluidicDesktop(kernel, kernel_thread)
    desktop.mainloop()
    # After GUI closes, ensure kernel stops
    kernel.running = False

if __name__ == "__main__":
    print("This module is meant to be imported. Run main.py instead.")