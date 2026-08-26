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
UmerOS /dev hierarchy — Device file management.

FHS 3.0 /dev specification:
  /dev       Device files (char/block/FIFO/symlink)
  /dev/input Input devices (event, js, mouse)
  /dev/pts   Pseudo-terminal devices
  /dev/shm   POSIX shared memory
  /dev/block Block device symlinks (by major:minor)
  /dev/char  Character device symlinks (by major:minor)
  /dev/disk  Disk symlinks (by-id, by-label, by-uuid, by-path)
  /dev/net   Network device nodes (tun, tap)
  /dev/usb   USB device nodes
  /dev/dri   Direct Rendering Interface (GPU)
  /dev/snd   ALSA sound devices
  /dev/mapper Device-mapper (LVM, dm-crypt)
  /dev/log   Syslog socket

Managers:
  DeviceType         — Enum of device types (char, block, fifo, socket, symlink)
  DeviceNode         — Dataclass for a single device node
  DeviceManager      — Central registry, create/remove/query device nodes
  NullDevice         — /dev/null  (discard)
  ZeroDevice         — /dev/zero  (zero-fill)
  RandomDevice       — /dev/random, /dev/urandom  (entropy)
  FullDevice         — /dev/full  (write-full)
  TTYDevice          — /dev/tty, /dev/console, /dev/ttyN
  PtmxDevice         — /dev/ptmx  (PTY master)
  FdDevice           — /dev/stdin, /dev/stdout, /dev/stderr, /dev/fd
  DevTmpFS           — devtmpfs population engine
  MAKEDEVCommand     — MAKEDEV script
  MknodCommand       — mknod (virtual)
  UdevadmCommand     — udevadm command
  LosetupCommand     — losetup command
  InputDevice        — /dev/input/ subsystem
  PtsDevice          — /dev/pts/ subsystem
  ShmDevice          — /dev/shm/ subsystem
  BlockDeviceLinks   — /dev/block/ symlinks
  CharDeviceLinks    — /dev/char/ symlinks
  DiskDeviceLinks    — /dev/disk/ symlinks (by-id, by-label, by-uuid, by-path, by-name, by-partlabel)
  NetDevice          — /dev/net/ subsystem
  UsbDevice          — /dev/bus/usb/
  DriDevice          — /dev/dri/ GPU
  SndDevice          — /dev/snd/ ALSA
  LogDevice          — /dev/log  (syslog)
  MapperDevice       — /dev/mapper/
  MemoryDevice       — /dev/mem, /dev/kmem, /dev/port (memory access)
  SCSIBlockDevice    — /dev/sd* (SCSI/SATA disks)
  SCSIGenericDevice  — /dev/sg* (SCSI generic)
  SCSITapeDevice     — /dev/st*, /dev/nst* (SCSI tapes)
  SCSIBSGDevice      — /dev/bsg/ (block SCSI generic)
  NVMeController     — /dev/nvme* (NVMe controllers)
  NVMeNamespace      — /dev/nvme*n* (NVMe namespaces)
  KVMDevice          — /dev/kvm (KVM virtualization)
  TUNDevice          — /dev/net/tun (TUN/TAP networking)
  VhostNetDevice     — /dev/vhost-net (vhost networking)
  FuseDevice         — /dev/fuse (FUSE filesystem)
  UHIDDevice         — /dev/uhid (user-space HID)
  HPETDevice         — /dev/hpet (High Precision Event Timer)
  WatchdogDevice     — /dev/watchdog (hardware watchdog)
  I2CDevice          — /dev/i2c-* (I2C bus)
  HugePagesDevice    — /dev/hugepages/ (huge pages)
  MQueueDevice       — /dev/mqueue/ (POSIX message queues)
  LoopControlDevice  — /dev/loop-control (loop device control)
  USBSerialDevice    — /dev/ttyUSB*, /dev/ttyACM* (USB serial)
  HidrawDevice       — /dev/hidraw* (HID raw access)
  UinputDevice       — /dev/uinput (virtual input injection)
  FramebufferDevice  — /dev/fb* (framebuffer display)
  MediaDevice        — /dev/media*, /dev/dvb*, /dev/video* (media framework)
  ParallelDevice     — /dev/lp*, /dev/parport* (parallel port)
  BtrfsControlDevice — /dev/btrfs-control (Btrfs control)
  DAXDevice          — /dev/dax* (DAX/persistent memory)
  VGAArbiterDevice   — /dev/vga_arbiter (VGA arbitration)

Integration:
  drivers/device_registry.py — DEVICE_REGISTRY (kernel-level)
  bin/device.py             — mknod host command
  kernel/umer_kernel.py     — mkdir /dev at boot
"""

from dev.core import DeviceType, DeviceNode, DeviceManager, get_device_manager
from dev.null_device import NullDevice
from dev.zero_device import ZeroDevice
from dev.random_device import RandomDevice
from dev.full_device import FullDevice
from dev.tty_device import TTYDevice
from dev.ptmx_device import PtmxDevice
from dev.fd_device import FdDevice
from dev.devtmpfs import DevTmpFS
from dev.makedev import MAKEDEVCommand
from dev.mknod_virtual import MknodVirtualCommand
from dev.udevadm import UdevadmCommand
from dev.losetup import LosetupCommand
from dev.input_device import InputDevice
from dev.pts_device import PtsDevice
from dev.shm_device import ShmDevice
from dev.block_devices import BlockDeviceLinks
from dev.char_devices import CharDeviceLinks
from dev.disk_device import DiskDeviceLinks
from dev.net_device import NetDevice
from dev.usb_device import UsbDevice
from dev.dri_device import DriDevice
from dev.snd_device import SndDevice
from dev.log_device import LogDevice
from dev.mapper_device import MapperDevice
# New subsystems
from dev.memory_devices import MemoryDevice, KernelMemoryDevice, PortDevice
from dev.scsi_devices import SCSIBlockDevice, SCSIGenericDevice, SCSITapeDevice, SCSIBSGDevice
from dev.nvme_devices import NVMeController, NVMeNamespace
from dev.virtual_devices import (
    KVMDevice, TUNDevice, VhostNetDevice, VhostVSockDevice,
    VhostUserDevice, VHCIDevice, CUSEDevice, VSockDevice,
)
from dev.fuse_device import FuseDevice
from dev.misc_char_devices import (
    UHIDDevice, UserfaultfdDevice, HPETDevice, PPPDevice, WatchdogDevice,
    IntelEtherDevice, PSAUXDevice, AGPGARTDevice, TPMDevice,
    SnapshotDevice, McelogDevice,
)
from dev.i2c_devices import I2CDevice
from dev.hugepages_device import HugePagesDevice
from dev.mqueue_device import MQueueDevice
from dev.loop_control import LoopControlDevice
# Second-phase subsystems
from dev.usb_serial_device import USBSerialDevice
from dev.hidraw_device import HidrawDevice
from dev.uinput_device import UinputDevice
from dev.framebuffer_device import FramebufferDevice
from dev.media_device import MediaDevice
from dev.parallel_device import ParallelDevice
from dev.misc_system_devices import BtrfsControlDevice, DAXDevice, VGAArbiterDevice

# Modern next-generation subsystems (2025+ techniques)
from dev.virtualization_devices import VFIODevice, DmaBufHeap, MdevDevice
from dev.modern_devices import (
    GpioCharDevice, ZramDevice, UserfaultfdNode,
    UsbGadgetDevice, NvmeGenericDevice, PtpClockDevice, RfKillDevice,
)
from dev.udev_modern import (
    UeventNetlinkMonitor, DeviceTagRegistry, PredictableNamingPolicy,
    SystemdDeviceUnits, MknodPolicy,
)

# Device-I/O internals (round two): ioctl codec, kmsg, rtc, usbmon, iio,
# modern loop/TUN management.
from dev.ioctl_codec import IoctlCodec
from dev.kmsg_rtc import KmsgRing, RtcWakeDevice
from dev.io_subsystems import (
    UsbmonTracer, IioBufferDevice, LoopModernOps, TunModernOps,
)

__all__ = [
    # Core
    "DeviceType", "DeviceNode", "DeviceManager", "get_device_manager",
    # Pseudo-devices
    "NullDevice", "ZeroDevice", "RandomDevice", "FullDevice",
    # Terminal
    "TTYDevice", "PtmxDevice", "FdDevice",
    # Filesystems
    "DevTmpFS", "PtsDevice", "ShmDevice",
    # Commands
    "MAKEDEVCommand", "MknodVirtualCommand", "UdevadmCommand", "LosetupCommand",
    # Device links
    "BlockDeviceLinks", "CharDeviceLinks", "DiskDeviceLinks",
    # Subsystems
    "InputDevice", "NetDevice", "UsbDevice", "DriDevice", "SndDevice",
    # Misc
    "LogDevice", "MapperDevice",
    # Memory devices
    "MemoryDevice", "KernelMemoryDevice", "PortDevice",
    # SCSI devices
    "SCSIBlockDevice", "SCSIGenericDevice", "SCSITapeDevice", "SCSIBSGDevice",
    # NVMe devices
    "NVMeController", "NVMeNamespace",
    # Virtual devices
    "KVMDevice", "TUNDevice", "VhostNetDevice", "VhostVSockDevice",
    "VhostUserDevice", "VHCIDevice", "CUSEDevice", "VSockDevice",
    # FUSE
    "FuseDevice",
    # Misc char devices
    "UHIDDevice", "UserfaultfdDevice", "HPETDevice", "PPPDevice",
    "WatchdogDevice", "IntelEtherDevice", "PSAUXDevice", "AGPGARTDevice",
    "TPMDevice", "SnapshotDevice", "McelogDevice",
    # I2C devices
    "I2CDevice",
    # Hugepages
    "HugePagesDevice",
    # POSIX mqueue
    "MQueueDevice",
    # Loop control
    "LoopControlDevice",
    # Second-phase subsystems
    "USBSerialDevice",
    "HidrawDevice",
    "UinputDevice",
    "FramebufferDevice",
    "MediaDevice",
    "ParallelDevice",
    "BtrfsControlDevice", "DAXDevice", "VGAArbiterDevice",
    # Modern next-generation devices
    "VFIODevice", "DmaBufHeap", "MdevDevice",
    "GpioCharDevice", "ZramDevice", "UserfaultfdNode",
    "UsbGadgetDevice", "NvmeGenericDevice", "PtpClockDevice", "RfKillDevice",
    "UeventNetlinkMonitor", "DeviceTagRegistry", "PredictableNamingPolicy",
    "SystemdDeviceUnits", "MknodPolicy",
    "IoctlCodec", "KmsgRing", "RtcWakeDevice",
    "UsbmonTracer", "IioBufferDevice", "LoopModernOps", "TunModernOps",
]
