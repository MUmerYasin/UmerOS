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
UmerOS udev System Demo
Based on Greg Kroah-Hartman's udev paper (OLS 2003)

This demo shows how the device subsystem works:
1. Device manager creates/removes nodes in /dev
2. Rules engine matches events and applies naming rules
3. Hotplug bus handles device add/remove events
4. Simulator demonstrates USB drive and TTY hotplug
"""

import asyncio
import logging
from pathlib import Path

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from dev import (
    DeviceManager,
    DeviceNode,
    DeviceType,
    HotplugBus,
    HotplugEvent,
    HotplugEventType,
    HotplugSimulator,
    UdevAction,
    UdevEvent,
    UdevRule,
    UdevRulesEngine,
    create_dev_subsystem,
)
from dev.udev_rules import UdevRuleMatch, UdevRuleAction

logging.basicConfig(level=logging.DEBUG, format='%(name)s: %(message)s')
logger = logging.getLogger(__name__)


async def demo_device_manager():
    """Demo basic device manager operations."""
    print("\n=== Device Manager Demo ===")

    dm = DeviceManager(Path("/dev"))

    # Create some devices
    sda = DeviceNode(
        name="sda",
        dev_type=DeviceType.BLOCK,
        major=8,
        minor=0,
        mode=0o660,
    )
    sda.symlink_to(Path("disk/by-id/usb-SanDisk_SDCZ48-016G"))
    dm.create(sda)

    sdb = DeviceNode(
        name="sdb",
        dev_type=DeviceType.BLOCK,
        major=8,
        minor=16,
    )
    dm.create(sdb)

    ttyUSB0 = DeviceNode(
        name="ttyUSB0",
        dev_type=DeviceType.CHAR,
        major=188,
        minor=0,
        mode=0o620,
    )
    dm.create(ttyUSB0)

    print(f"Created {len(dm.list_devices())} devices")
    print(f"Block devices: {len(dm.list_block_devices())}")
    print(f"Char devices: {len(dm.list_char_devices())}")

    # Query by device number
    found = dm.get_by_devnum(8, 0)
    print(f"Device at 8:0 = {found.name if found else 'not found'}")

    # Query by symlink
    found = dm.get_by_symlink(Path("disk/by-id/usb-SanDisk_SDCZ48-016G"))
    print(f"Symlink points to: {found.name if found else 'not found'}")

    print(f"Stats: {dm.get_stats()}")
    return dm


async def demo_hotplug():
    """Demo hotplug event system."""
    print("\n=== Hotplug Demo ===")

    dm, rules, bus, simulator = create_dev_subsystem()

    # Event counter
    event_count = {"add": 0, "remove": 0}

    async def on_device_add(event: HotplugEvent):
        event_count["add"] += 1
        print(f"  [ADD] {event.subsystem}/{event.kernel}")

    async def on_device_remove(event: HotplugEvent):
        event_count["remove"] += 1
        print(f"  [REMOVE] {event.subsystem}/{event.kernel}")

    bus.subscribe(HotplugEventType.DEVICE_ADD, on_device_add)
    bus.subscribe(HotplugEventType.DEVICE_REMOVE, on_device_remove)

    # Simulate USB drive plug
    print("\n1. Plugging USB drive...")
    await simulator.plug_usb_drive(
        kernel="sdb",
        vendor="SanDisk",
        product="Cruzer Blade",
        serial="0000000000001234",
    )
    await asyncio.sleep(0.1)  # Let async handlers run

    # Simulate TTY adapter plug
    print("\n2. Plugging USB-serial adapter...")
    await simulator.plug_tty(
        kernel="ttyUSB0",
        baud=9600,
    )
    await asyncio.sleep(0.1)

    # Simulate keyboard plug
    print("\n3. Plugging USB keyboard...")
    await simulator.plug_input_device(
        kernel="event0",
        name="USB Keyboard",
    )
    await asyncio.sleep(0.1)

    print(f"\nEvent summary: {event_count}")
    print(f"Devices currently plugged: {simulator.get_plugged_devices()}")

    # Unplug devices
    print("\n4. Unplugging USB drive...")
    await simulator.unplug_usb_drive("sdb")
    await asyncio.sleep(0.1)

    print(f"After unplugging: {simulator.get_plugged_devices()}")
    print(f"Stats: {bus.get_stats()}")


async def demo_rules_engine():
    """Demo udev rules engine."""
    print("\n=== Rules Engine Demo ===")

    dm, rules, bus, simulator = create_dev_subsystem()

    # Add a custom rule
    custom_rule = UdevRule(
        matches=[
            UdevRuleMatch("SUBSYSTEM", "block"),
            UdevRuleMatch("KERNEL", "sd*"),
        ],
        actions=[
            UdevRuleAction("SYMLINK", "disk/by-partlabel/%k"),
            UdevRuleAction("MODE", "0660"),
            UdevRuleAction("GROUP", "disk"),
        ],
        priority=50,  # Higher priority (lower number)
    )
    rules.add_rule(custom_rule)

    print(f"Loaded {len(rules.rules)} rules")

    # Process an event
    event = UdevEvent(
        subsystem="block",
        kernel="sda",
        action=UdevAction.ADD,
        major=8,
        minor=0,
        env={
            "ID_SERIAL": "SanDisk_Cruzer_0000000000001234",
            "ID_VENDOR": "SanDisk",
            "ID_MODEL": "Cruzer Blade",
        },
    )

    print("\nProcessing event: block/sda add")
    results = rules.process_event(event)
    print(f"Created {len(results)} device nodes")
    for dev in results:
        print(f"  - {dev.name}: {dev.dev_type.value} {dev.major}:{dev.minor}")
        if dev.symlinks:
            print(f"    Symlinks: {[str(s) for s in dev.symlinks]}")

    print(f"\nRules summary: {rules.get_rules_summary()}")


async def main():
    """Run all demos."""
    print("UmerOS udev System Demo")
    print("=" * 50)
    print("Based on Greg Kroah-Hartman's udev paper (OLS 2003)")
    print("'Creating a Dynamic /dev Directory with udev'")
    print("=" * 50)

    await demo_device_manager()
    await demo_hotplug()
    await demo_rules_engine()

    print("\n" + "=" * 50)
    print("Demo complete!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
