import asyncio
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class Message:
    sender: str
    target: str
    payload: Any
    signature: bytes = b''  # placeholder; security sandbox will verify

class IPCBroker:
    """
    Simple broker: service_id -> asyncio.Queue
    Signature verification and policy enforcement belong to Security Sandbox.
    """
    def __init__(self):
        self.queues: Dict[str, asyncio.Queue] = {}

    def register(self, service_id: str, maxsize: int = 1024):
        if service_id in self.queues:
            return
        self.queues[service_id] = asyncio.Queue(maxsize=maxsize)

    async def send(self, msg: Message):
        q = self.queues.get(msg.target)
        if q is None:
            raise RuntimeError(f"target {msg.target} unknown")
        await q.put(msg)

    async def recv(self, service_id: str) -> Message:
        q = self.queues.get(service_id)
        if q is None:
            raise RuntimeError(f"service {service_id} not registered")
        msg = await q.get()
        q.task_done()
        return msg