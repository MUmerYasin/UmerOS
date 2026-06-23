class SelfHealingService:
    def __init__(self):
        self.crashed_pids = set()

    def detect_anomaly(self, pid, status):
        if status == "CRASHED":
            print(f"[Self-Healing] Anomaly detected: PID {pid} has crashed.")
            self.crashed_pids.add(pid)
            return True
        return False

    def mitigate(self, pid):
        if pid in self.crashed_pids:
            print(f"[Self-Healing] Mitigating PID {pid}: Restarting process in isolated state...")
            self.crashed_pids.remove(pid)
            return True
        return False
