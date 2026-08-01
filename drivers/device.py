from typing import Dict, Any, Optional

class Device:
    """Represents a hardware device instance.
    It can be attached to a Bus, bound to a Driver, and hold generic resources.
    """

    def __init__(self, name: str, bus: Optional["Bus"] = None):
        self.name = name
        self.bus = bus
        self.driver: Optional[object] = None  # Assigned when bound
        self.resources: Dict[str, Any] = {}

    def bind_driver(self, driver: object) -> None:
        """Associate a driver with this device.
        If the driver defines a ``probe`` method, it will be called for initialization.
        """
        self.driver = driver
        if hasattr(driver, "probe"):
            driver.probe(self)

    def unbind_driver(self) -> None:
        """Detach the driver and invoke ``remove`` if present for cleanup."""
        if self.driver and hasattr(self.driver, "remove"):
            self.driver.remove(self)
        self.driver = None

    def add_resource(self, key: str, resource: Any) -> None:
        """Attach a generic resource (e.g., memory, IRQ) to the device."""
        self.resources[key] = resource

    def release_resources(self) -> None:
        """Release all stored resources."""
        self.resources.clear()
