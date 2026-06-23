class AIAssistant:
    def __init__(self):
        self.name = "Umer OS Assistant"
        self.model_loaded = True

    def query(self, text):
        print(f"[{self.name}] Processing query: '{text}'")
        if "status" in text.lower():
            return "System is running optimally. Kernel initialized."
        elif "crash" in text.lower():
            return "I can analyze crash dumps using the Self-Healing service."
        return "I am monitoring the system environment."