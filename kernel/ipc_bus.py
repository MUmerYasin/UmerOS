import hmac
import hashlib

class IPCMessage:
    def __init__(self, sender_pid, receiver_pid, data, signature):
        self.sender_pid = sender_pid
        self.receiver_pid = receiver_pid
        self.data = data
        self.signature = signature

class IPCBus:
    def __init__(self, secret_key=b'umer_os_zero_trust_key'):
        self.secret_key = secret_key
        self.mailboxes = {}

    def register_process(self, pid):
        if pid not in self.mailboxes:
            self.mailboxes[pid] = []

    def _sign(self, data):
        return hmac.new(self.secret_key, str(data).encode(), hashlib.sha256).hexdigest()

    def send(self, sender_pid, receiver_pid, data):
        if receiver_pid not in self.mailboxes:
            return False
        sig = self._sign(data)
        msg = IPCMessage(sender_pid, receiver_pid, data, sig)
        self.mailboxes[receiver_pid].append(msg)
        return True

    def receive(self, pid):
        if pid in self.mailboxes and self.mailboxes[pid]:
            msg = self.mailboxes[pid].pop(0)
            if msg.signature == self._sign(msg.data):
                return msg
            else:
                print(f"[SECURITY] IPC Signature mismatch for PID {pid}")
        return None
