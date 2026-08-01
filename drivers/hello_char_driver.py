from .char_device_base import CharDeviceDriver, CHAR_DEVICES

class HelloCharDriver(CharDeviceDriver):
    """Simple character device driver returning static hello message and logging writes."""

    def __init__(self):
        super().__init__(name="umer-hello")
        self._buffer = ""

    def load(self) -> bool:
        super().load()
        # Initialize buffer with greeting
        self._buffer = "Hello from UmerOS character device!\n"
        return True

    def read(self, size: int = -1) -> str:
        data = self._buffer if size == -1 else self._buffer[:size]
        print(f"[CHARDEV:{self.name}] read {len(data)} bytes")
        return data

    def write(self, data: str) -> int:
        self._buffer += data
        print(f"[CHARDEV:{self.name}] wrote {len(data)} bytes: {data!r}")
        return len(data)
