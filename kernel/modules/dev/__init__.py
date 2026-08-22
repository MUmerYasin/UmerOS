# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
UmerOS Device Subsystem

Based on Greg Kroah-Hartman's udev paper (OLS 2003):
"Creating a Dynamic /dev Directory with udev"

This module implements:
- Device node management (device_manager.py)
- udev rules engine (udev_rules.py)
- Hotplug event handling (hotplug.py)

Architecture (from the paper):
    Kernel → Netlink → udevd → Rules Engine → /dev node creation

The device manager handles the /dev filesystem, the rules engine
matches device events against rules to determine node properties,
and the hotplug system simulates kernel device events.
"""

from .device_manager import DeviceManager, DeviceNode, DeviceType
from .hotplug import HotplugBus, HotplugEvent, HotplugEventType, HotplugSimulator
from .udev_rules import UdevAction, UdevEvent, UdevRule, UdevRulesEngine

__all__ = [
    # Device Manager
    "DeviceManager",
    "DeviceNode",
    "DeviceType",
    # Hotplug
    "HotplugBus",
    "HotplugEvent",
    "HotplugEventType",
    "HotplugSimulator",
    # udev Rules
    "UdevAction",
    "UdevEvent",
    "UdevRule",
    "UdevRulesEngine",
]


def create_dev_subsystem(dev_path=None):
    """
    Create a complete device subsystem with all components wired together.

    This is the main entry point for setting up /dev management.

    Args:
        dev_path: Path to /dev directory (default: /dev)

    Returns:
        Tuple of (device_manager, rules_engine, hotplug_bus, simulator)
    """
    device_manager = DeviceManager(dev_path)
    hotplug_bus = HotplugBus(device_manager)
    rules_engine = hotplug_bus.rules_engine
    simulator = HotplugSimulator(hotplug_bus)

    return device_manager, rules_engine, hotplug_bus, simulator
