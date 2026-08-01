from .example_driver import DriverBase, CHAR_DEVICES, FileOperations

class HelloCharDriver(DriverBase, FileOperations):
    """Simple character device driver returning static hello message and logging writes."""

    def __init__(self):
        super().__init__("umer-hello", "1.0.0", "CharDevice")
        self._buffer = ""

    def load(self) -> bool:
        super().load()
        # Register in global char device registry
        CHAR_DEVICES[self.name] = self
        # Initialize buffer with greeting
        self._buffer = "Hello from UmerOS character device!\n"
        return True

    def open(self, mode: str = "r") -> None:
        pass

    def read(self, size: int = -1) -> str:
        data = self._buffer if size == -1 else self._buffer[:size]
        print(f"[CHARDEV:{self.name}] read {len(data)} bytes")
        return data

    def write(self, data: str) -> int:
        self._buffer += data
        print(f"[CHARDEV:{self.name}] wrote {len(data)} bytes: {data!r}")
        return len(data)

    def release(self) -> None:
        # Cleanup if needed
        CHAR_DEVICES.pop(self.name, None)
        pass
