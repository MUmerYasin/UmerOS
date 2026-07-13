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
