#!/usr/bin/env python3
"""
Example GPU Platform Driver
"""

from .platform_driver import PlatformDriver

class GpuPlatformDriver(PlatformDriver):
    def __init__(self):
        super().__init__("gpu-platform-driver", "1.0.0", "GPU/Display")

    # Inherits can_bind from PlatformDriver (matches hardware_type)
    # Additional driver‑specific initialization can be added here.
