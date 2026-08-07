# Umer OS — Driver Writing Guide

## Quick Start

All drivers inherit from `DeviceDriver` (kernel/drivers/base_driver.py):

```python
from kernel.drivers.base_driver import DeviceDriver

class MyDriver(DeviceDriver):
    driver_name = "my_device"
    driver_version = "0.1.0"

    def probe(self) -> bool:
        # Detect hardware presence
        return True

    def init(self) -> bool:
        # Open device, allocate resources
        self._active = True
        return True

    def read(self, size: int = 64) -> bytes:
        return b"data"

    def write(self, data: bytes) -> int:
        return len(data)

    def shutdown(self) -> None:
        self._active = False
```

## Built-in Drivers

| Driver | File | Status |
|---|---|---|
| KeyboardDriver | keyboard_driver.py | ✅ TODAY (evdev stub) |
| NetworkDriver | network_driver.py | ✅ TODAY (socket-based) |
| GPUDriver | gpu_driver.py | ✅ TODAY (stub) / 🔮 FUTURE (Vulkan) |
| StorageDriver | storage_driver.py | ✅ TODAY (file-backed) |

## Required Methods

- `probe()` — return True if hardware found
- `init()` — return True on successful initialisation
- `read()` / `write()` — data transfer
- `shutdown()` — clean teardown

## Testing Your Driver

```python
import unittest
from kernel.drivers.my_driver import MyDriver

class TestMyDriver(unittest.TestCase):
    def test_probe_returns_bool(self):
        self.assertIsInstance(MyDriver().probe(), bool)
    def test_status_has_keys(self):
        s = MyDriver().status()
        for k in ("driver","version","active"):
            self.assertIn(k, s)
```
