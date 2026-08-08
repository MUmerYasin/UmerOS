"""
UmerOS /dev — Virtualization and networking character devices.

Linux /dev structure:
  /dev/kvm            — KVM virtualization (major 10:232)
  /dev/vhost-net      — vhost network backend (major 10:238)
  /dev/vhost-vsock    — vhost vsock (major 10:241)
  /dev/vhost-user-*   — vhost-user socket devices (char 10:242+)
  /dev/vhci           — Virtual Host Controller Interface (10:137)
  /dev/tun            — Network tunnel device (major 10:200)
  /dev/cuse           — Character device in Userspace (major 10:203)
  /dev/vsock          — Virtual socket (major 10:240)
  /dev/net/tun        — Network TUN/TAP (in /dev/net/ subdirectory)

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.VirtualDevices")


class KVMDevice:
    """/dev/kvm — Kernel-based Virtual Machine.

    Provides ioctl interface to KVM for hardware-assisted
    virtualization. Used by QEMU, Firecracker, Cloud-Hypervisor.
    """

    MAJOR = 10
    MINOR = 232

    def __init__(self):
        self._vms: Dict[int, Dict[str, Any]] = {}
        self._register()
        log.info("KVMDevice /dev/kvm created")

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="kvm", path="/dev/kvm", dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR, mode=0o660,
            description="KVM virtualization",
            ioctl_callback=self._ioctl,
        ))

    def _ioctl(self, request: int, arg: Any) -> int:
        # KVM_GET_API_VERSION = 0xAE00
        if request == 0xAE00:
            return 12  # KVM API version 12
        # KVM_CREATE_VM = 0xAE01
        if request == 0xAE01:
            vm_id = len(self._vms)
            self._vms[vm_id] = {"vcpus": 0, "memory": 0}
            return vm_id
        # KVM_GET_VCPU_MMAP_SIZE = 0xAE04
        if request == 0xAE04:
            return 0x1000  # 4KB
        # KVM_CHECK_EXTENSION = 0xAE03
        if request == 0xAE03:
            return 1  # Supported
        return -1

    def create_vm(self) -> int:
        vm_id = len(self._vms)
        self._vms[vm_id] = {"vcpus": 0, "memory": 0}
        log.info("KVM: created VM %d", vm_id)
        return vm_id

    def destroy_vm(self, vm_id: int) -> bool:
        if vm_id not in self._vms:
            return False
        del self._vms[vm_id]
        log.info("KVM: destroyed VM %d", vm_id)
        return True

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/kvm",
            "api_version": 12,
            "active_vms": len(self._vms),
            "vm_ids": list(self._vms.keys()),
        }


class TUNDevice:
    """/dev/net/tun and /dev/tun — Network TUN/TAP device.

    TUN (Layer 3) and TAP (Layer 2) virtual network devices.
    Used by VPNs (WireGuard, OpenVPN), containers, and VM networking.

    major 10, minor 200
    """

    MAJOR = 10
    MINOR = 200

    def __init__(self):
        self._interfaces: Dict[str, Dict[str, Any]] = {}
        self._register()
        log.info("TUNDevice /dev/net/tun created")

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="tun", path="/dev/net/tun", dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR, mode=0o660,
            description="TUN/TAP network device",
            ioctl_callback=self._ioctl,
            read_callback=self._read,
            write_callback=self._write,
        ))

    def _ioctl(self, request: int, arg: Any) -> int:
        # TUNSETIFF = 0x400454CA
        if request == 0x400454CA:
            return 0
        # TUNSETPERSIST = 0x400454CB
        if request == 0x400454CB:
            return 0
        # TUNSETOWNER = 0x400454CC
        if request == 0x400454CC:
            return 0
        # TUNSETGROUP = 0x400454CE
        if request == 0x400454CE:
            return 0
        return -1

    def _read(self, size: int, offset: int = 0) -> bytes:
        return b"\x00" * size

    def _write(self, data: bytes, offset: int = 0) -> int:
        return len(data)

    def create_interface(self, name: str, mode: str = "tap") -> bool:
        if name in self._interfaces:
            return False
        self._interfaces[name] = {"mode": mode, "up": False}
        log.info("TUN: created interface %s (mode=%s)", name, mode)
        return True

    def delete_interface(self, name: str) -> bool:
        if name not in self._interfaces:
            return False
        del self._interfaces[name]
        log.info("TUN: deleted interface %s", name)
        return True

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/net/tun",
            "interfaces": list(self._interfaces.keys()),
            "count": len(self._interfaces),
        }


class VhostNetDevice:
    """/dev/vhost-net — vhost network backend.

    Kernel-based virtio network backend for faster VM networking
    than QEMU userspace vhost-net. Bypasses QEMU for data path.

    major 10, minor 238
    """

    MAJOR = 10
    MINOR = 238

    def __init__(self):
        self._register()
        log.info("VhostNetDevice /dev/vhost-net created")

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="vhost-net", path="/dev/vhost-net",
            dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR, mode=0o660,
            description="vhost network backend",
            ioctl_callback=self._ioctl,
        ))

    def _ioctl(self, request: int, arg: Any) -> int:
        return 0

    def get_info(self) -> Dict[str, Any]:
        return {"path": "/dev/vhost-net", "major": self.MAJOR, "minor": self.MINOR}


class VhostVSockDevice:
    """/dev/vhost-vsock — vhost vsock device.

    Host-side vsock backend for VM <-> host communication
    using virtio-vsock. Used by Firecracker, QEMU, Cloud-Hypervisor.

    major 10, minor 241
    """

    MAJOR = 10
    MINOR = 241

    def __init__(self):
        self._register()
        log.info("VhostVSockDevice /dev/vhost-vsock created")

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="vhost-vsock", path="/dev/vhost-vsock",
            dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR, mode=0o660,
            description="vhost vsock device",
            ioctl_callback=self._ioctl,
        ))

    def _ioctl(self, request: int, arg: Any) -> int:
        return 0

    def get_info(self) -> Dict[str, Any]:
        return {"path": "/dev/vhost-vsock", "major": self.MAJOR, "minor": self.MINOR}


class VhostUserDevice:
    """/dev/vhost-user-* — vhost-user socket devices.

    Userspace vhost backends communicating over Unix sockets.
    Used with OVS-DPDK, SPDK, and other userspace data planes.

    major 10, minor 242+
    """

    MAJOR = 10
    MINOR_START = 242
    MAX_DEVICES = 8

    def __init__(self):
        self._devices: Dict[int, Dict[str, Any]] = {}
        self._register_devices()
        log.info("VhostUserDevice: registered %d vhost-user devices", self.MAX_DEVICES)

    def _register_devices(self) -> None:
        mgr = DeviceManager.get_instance()
        for i in range(self.MAX_DEVICES):
            minor = self.MINOR_START + i
            mgr.create_node(DeviceNode(
                name=f"vhost-user-{i}",
                path=f"/dev/vhost-user-{i}",
                dev_type=DeviceType.CHAR,
                major=self.MAJOR, minor=minor, mode=0o660,
                description=f"vhost-user socket device {i}",
                ioctl_callback=lambda r, a, n=i: self._ioctl(r, a, n),
            ))
            self._devices[i] = {"connected": False, "socket_path": ""}

    def _ioctl(self, request: int, arg: Any, dev_id: int) -> int:
        return 0

    def connect(self, dev_id: int, socket_path: str) -> bool:
        if dev_id not in self._devices:
            return False
        self._devices[dev_id]["connected"] = True
        self._devices[dev_id]["socket_path"] = socket_path
        log.info("vhost-user-%d: connected to %s", dev_id, socket_path)
        return True

    def disconnect(self, dev_id: int) -> bool:
        if dev_id not in self._devices:
            return False
        self._devices[dev_id]["connected"] = False
        self._devices[dev_id]["socket_path"] = ""
        return True

    def get_info(self) -> Dict[str, Any]:
        return {
            "max_devices": self.MAX_DEVICES,
            "connected": [d for d, v in self._devices.items() if v["connected"]],
        }


class VHCIDevice:
    """/dev/vhci — Virtual Host Controller Interface.

    USB virtual host controller for USB/IP. Allows sharing USB
    devices over the network by emulating USB host controllers.

    major 10, minor 137
    """

    MAJOR = 10
    MINOR = 137
    MAX_PORTS = 8

    def __init__(self):
        self._ports: Dict[int, Dict[str, Any]] = {}
        self._register()
        log.info("VHCIDevice /dev/vhci created")

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="vhci", path="/dev/vhci",
            dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR, mode=0o660,
            description="Virtual Host Controller Interface (USB/IP)",
            ioctl_callback=self._ioctl,
        ))

    def _ioctl(self, request: int, arg: Any) -> int:
        return 0

    def attach_device(self, port: int, speed: str = "high") -> bool:
        if port < 0 or port >= self.MAX_PORTS:
            return False
        self._ports[port] = {"speed": speed, "attached": True}
        log.info("VHCI: attached device on port %d (speed=%s)", port, speed)
        return True

    def detach_device(self, port: int) -> bool:
        if port not in self._ports:
            return False
        del self._ports[port]
        log.info("VHCI: detached device from port %d", port)
        return True

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/vhci",
            "max_ports": self.MAX_PORTS,
            "attached_ports": list(self._ports.keys()),
        }


class CUSEDevice:
    """/dev/cuse — Character device in Userspace.

    CUSE is the character device counterpart of FUSE. It allows
    creating custom character devices where the device logic runs
    in userspace. Used for custom hardware emulation.

    major 10, minor 203
    """

    MAJOR = 10
    MINOR = 203

    def __init__(self):
        self._devices: Dict[str, Dict[str, Any]] = {}
        self._register()
        log.info("CUSEDevice /dev/cuse created")

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="cuse", path="/dev/cuse",
            dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR, mode=0o660,
            description="Character device in Userspace",
            ioctl_callback=self._ioctl,
        ))

    def _ioctl(self, request: int, arg: Any) -> int:
        # CUSE_INIT = 0xAE00
        if request == 0xAE00:
            return 0
        return -1

    def get_info(self) -> Dict[str, Any]:
        return {"path": "/dev/cuse", "major": self.MAJOR, "minor": self.MINOR}


class VSockDevice:
    """/dev/vsock — Virtual socket device.

    Linux VM sockets for host <-> guest communication.
    Uses CID (Context ID) and port numbers similar to TCP/IP.
    AF_VSOCK socket family.

    major 10, minor 240
    """

    MAJOR = 10
    MINOR = 240

    VMADDR_CID_ANY = 0xFFFFFFFF
    VMADDR_CID_HOST = 2

    def __init__(self):
        self._connections: Dict[int, Dict[str, Any]] = {}
        self._register()
        log.info("VSockDevice /dev/vsock created")

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="vsock", path="/dev/vsock",
            dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR, mode=0o666,
            description="Virtual socket (AF_VSOCK)",
            ioctl_callback=self._ioctl,
        ))

    def _ioctl(self, request: int, arg: Any) -> int:
        return 0

    def connect(self, cid: int, port: int) -> int:
        conn_id = len(self._connections)
        self._connections[conn_id] = {"cid": cid, "port": port, "state": "connected"}
        log.info("vsock: connected to cid=%d port=%d (conn=%d)", cid, port, conn_id)
        return conn_id

    def disconnect(self, conn_id: int) -> bool:
        if conn_id not in self._connections:
            return False
        del self._connections[conn_id]
        return True

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/vsock",
            "active_connections": len(self._connections),
            "host_cid": self.VMADDR_CID_HOST,
        }
