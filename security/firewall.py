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

class AIFirewall:
    """AI-driven firewall (simple packet filter) merged from Deepseek code."""
    def __init__(self):
        self.rules = []  # List of (ip, port, action)
        self.blocked_ips = set()

    def analyze_packet(self, src_ip: str, dst_port: int) -> str:
        """AI-based heuristic: if port 22 and not in rules, block."""
        if dst_port == 22 and src_ip not in self.blocked_ips:
            print(f"[Firewall] Blocking suspicious SSH from {src_ip}")
            self.blocked_ips.add(src_ip)
            return "DROP"
        return "ALLOW"

    def add_rule(self, rule: tuple):
        self.rules.append(rule)
