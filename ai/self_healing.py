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
