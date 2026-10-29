"""Sample Kernel Extension: Virtual Sensor Driver.

Demonstrates the type-safe Kernel Extension DSL.
"""
from __future__ import annotations

from sdk.kernel_dsl.extension_base import KernelExtension, system_capability
from sdk.kernel_dsl.types import Result, Success, Failure, Option, Some, None_


class VirtualSensorExtension(KernelExtension):
    def __init__(self) -> None:
        super().__init__("virtual_sensor", capabilities={"sensor.read", "sensor.write"})

    @system_capability("sensor.read")
    def read_temperature(self) -> Result[float, str]:
        """Read temperature from virtual sensor."""
        return Success(23.5)

    @system_capability("sensor.read")
    def read_humidity(self) -> Result[float, str]:
        """Read humidity from virtual sensor."""
        return Success(45.2)

    @system_capability("sensor.write")
    def calibrate(self, offset: float) -> Result[bool, str]:
        """Calibrate sensor with offset."""
        if offset < -10 or offset > 10:
            return Failure("Offset out of range [-10, 10]")
        return Success(True)

    def get_status(self) -> Option[str]:
        """Get sensor status."""
        return Some("operational")