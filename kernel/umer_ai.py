#!/usr/bin/env python3
"""
Umer OS Local AI Assistant
Rule-based system with simulated self-healing and predictive resource hints.
"""

import random
import time

class AIAssistant:
    def __init__(self):
        self.commands = {
            "help": self.show_help,
            "status": self.system_status,
            "optimize": self.optimize_system,
            "heal": self.self_heal,
            "predict": self.predict_load,
            "exit": lambda: "Goodbye!",
        }
        self.resource_history = []
        self.bug_fixed = False

    def show_help(self):
        return ("Available commands:\n"
                "  help     - Show this help\n"
                "  status   - Show system status\n"
                "  optimize - Run AI memory/cpu optimizer\n"
                "  heal     - Trigger self-healing (detects and fixes a simulated bug)\n"
                "  predict  - Predict future resource usage\n"
                "  exit     - Exit assistant")

    def system_status(self):
        cpu = random.randint(20, 80)
        mem = random.randint(30, 70)
        return f"CPU: {cpu}% | Memory: {mem}% | AI status: Online"

    def optimize_system(self):
        print("[AI] Analyzing resource patterns...")
        time.sleep(1)
        # Simulate optimization
        return "Optimized cache, freed 150 MB. Predicted next app launch, preloaded libraries."

    def self_heal(self):
        if not self.bug_fixed:
            print("[AI] Scanning for code anomalies...")
            time.sleep(1.5)
            print("[AI] Critical bug detected in memory allocator (simulated).")
            print("[AI] Generating patch...")
            time.sleep(1)
            print("[AI] Patch applied. System stable.")
            self.bug_fixed = True
            return "Self-healing complete: memory allocator bug fixed."
        else:
            return "System is healthy. No bugs detected."

    def predict_load(self):
        last = random.randint(10, 90)
        predicted = last + random.randint(-10, 10)
        self.resource_history.append(predicted)
        return f"Predicted CPU usage in 5 seconds: {predicted}% (based on history)."

    def process(self, user_input: str):
        cmd = user_input.strip().lower()
        if cmd in self.commands:
            return self.commands[cmd]()
        else:
            return ("I'm a prototype AI assistant. "
                    "I can handle help, status, optimize, heal, predict, exit.")

def main():
    assistant = AIAssistant()
    print("Umer AI Assistant (type 'help' for commands, 'exit' to quit)")
    while True:
        try:
            user = input("AI> ")
        except (EOFError, KeyboardInterrupt):
            print("\nAI session ended.")
            break
        if user.lower() == "exit":
            print(assistant.process("exit"))
            break
        print(assistant.process(user))

if __name__ == "__main__":
    main()