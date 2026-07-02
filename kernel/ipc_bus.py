import hmac
import hashlib
import os
import secrets

class IPCMessage:
    def __init__(self, sender_pid, receiver_pid, data, signature):
        self.sender_pid = sender_pid
        self.receiver_pid = receiver_pid
        self.data = data
        self.signature = signature

class IPCBus:
    """Secure IPC bus with HMAC message authentication.
    
    Uses environment variable UMEROS_IPC_SECRET or generates a secure random key.
    """
    
    def __init__(self, secret_key=None):
        """Initialize IPC bus with secure secret key.
        
        Args:
            secret_key: Optional bytes key. If None, loads from environment
                       or generates a new secure key.
        """
        if secret_key is not None:
            self.secret_key = secret_key if isinstance(secret_key, bytes) else secret_key.encode()
        else:
            # Try to load from environment
            env_key = os.environ.get('UMEROS_IPC_SECRET')
            if env_key:
                self.secret_key = env_key.encode()
                print("[IPC] Loaded secret key from environment")
            else:
                # Generate secure random key
                self.secret_key = secrets.token_bytes(32)
                print("[IPC] WARNING: Generated new random key. Set UMEROS_IPC_SECRET for persistence.")
        
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
