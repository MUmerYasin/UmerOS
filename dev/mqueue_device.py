"""
UmerOS /dev/mqueue — POSIX message queue filesystem.

 /dev/mqueue:
  /dev/mqueue/ — Mount point for mqueuefs, a pseudo-filesystem
  that exposes POSIX message queues as files. Each queue
  appears as a file readable with mq_getattr() and friends.

  Mount: mount -t mqueue nodev /dev/mqueue

  File per queue shows attributes:
    QSIZE=N          — Current queue size in bytes
    FLAGS=N          — Queue flags
    MQ_MAXMSG=N      — Maximum messages
    MSGSIZE=N        — Maximum message size
    CURMSGS=N        — Current messages in queue

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.MQueueDevice")


class MQueueMessage:
    def __init__(self, priority: int, data: bytes):
        self.priority = priority
        self.data = data
        self.timestamp = time.time()


class MQueue:
    def __init__(self, name: str, max_msgs: int = 10, msg_size: int = 8192):
        self.name = name
        self.max_msgs = max_msgs
        self.msg_size = msg_size
        self._queue: List[MQueueMessage] = []
        self._flags = 0

    @property
    def cur_msgs(self) -> int:
        return len(self._queue)

    @property
    def qsize(self) -> int:
        return sum(len(m.data) for m in self._queue)

    def enqueue(self, data: bytes, priority: int = 0) -> bool:
        if len(self._queue) >= self.max_msgs:
            return False
        if len(data) > self.msg_size:
            return False
        self._queue.append(MQueueMessage(priority, data))
        self._queue.sort(key=lambda m: m.priority, reverse=True)
        return True

    def dequeue(self) -> Optional[bytes]:
        if not self._queue:
            return None
        msg = self._queue.pop(0)
        return msg.data

    def peek(self) -> Optional[bytes]:
        if not self._queue:
            return None
        return self._queue[0].data

    def attributes(self) -> Dict[str, int]:
        return {
            "QSIZE": self.qsize,
            "FLAGS": self._flags,
            "MQ_MAXMSG": self.max_msgs,
            "MSGSIZE": self.msg_size,
            "CURMSGS": self.cur_msgs,
        }


class MQueueDevice:
    """/dev/mqueue — POSIX message queue filesystem mount point.

    Provides the directory structure and management for POSIX
    named message queues (mq_open, mq_send, mq_receive).
    """

    def __init__(self):
        self._queues: Dict[str, MQueue] = {}
        self._mounted = False
        self._register_directory()
        log.info("MQueueDevice /dev/mqueue created")

    def _register_directory(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="mqueue", path="/dev/mqueue",
            dev_type=DeviceType.DIRECTORY,
            description="POSIX message queue filesystem",
        ))

    def mount(self) -> bool:
        self._mounted = True
        log.info("mqueue: mounted /dev/mqueue")
        return True

    def unmount(self) -> bool:
        self._mounted = False
        self._queues.clear()
        log.info("mqueue: unmounted /dev/mqueue")
        return True

    def create_queue(self, name: str, max_msgs: int = 10,
                     msg_size: int = 8192) -> bool:
        if not self._mounted:
            return False
        if name in self._queues:
            return False
        self._queues[name] = MQueue(name, max_msgs, msg_size)
        log.info("mqueue: created queue %s (max=%d, size=%d)",
                 name, max_msgs, msg_size)
        return True

    def remove_queue(self, name: str) -> bool:
        if name not in self._queues:
            return False
        del self._queues[name]
        log.info("mqueue: removed queue %s", name)
        return True

    def send(self, name: str, data: bytes, priority: int = 0) -> bool:
        q = self._queues.get(name)
        if not q:
            return False
        return q.enqueue(data, priority)

    def receive(self, name: str) -> Optional[bytes]:
        q = self._queues.get(name)
        if not q:
            return None
        return q.dequeue()

    def peek(self, name: str) -> Optional[bytes]:
        q = self._queues.get(name)
        if not q:
            return None
        return q.peek()

    def get_attributes(self, name: str) -> Optional[Dict[str, int]]:
        q = self._queues.get(name)
        if not q:
            return None
        return q.attributes()

    def list_queues(self) -> List[str]:
        return list(self._queues.keys())

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/mqueue",
            "mounted": self._mounted,
            "queue_count": len(self._queues),
            "queues": self.list_queues(),
        }
