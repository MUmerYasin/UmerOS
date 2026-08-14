"""
UmerOS NFC Framework
=====================
Kernel Near Field Communication subsystem.
Implements NFC controllers, secure elements, LLCP,
and simulated NFC devices.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NFC Constants
# ---------------------------------------------------------------------------
NFC_RF_INITIATOR: int = 0x01
NFC_RF_TARGET: int = 0x02
NFC_RF_PASSIVE: int = 0x04
NFC_RF_ACTIVE: int = 0x08

NFC_STATUS_OK: int = 0x00
NFC_STATUS_EIO: int = 0x01
NFC_STATUS_EINVAL: int = 0x02
NFC_STATUS_ENOTIMPL: int = 0x03
NFC_STATUS_ENOTSUPP: int = 0x04

NFC_SECURE_ELEMENT_OFF: int = 0
NFC_SECURE_ELEMENT_ON: int = 1

# NFC modulation types
NFC_MODULATION_TYPE_A: str = "iso14443a"
NFC_MODULATION_TYPE_B: str = "iso14443b"
NFC_MODULATION_TYPE_F: str = "iso15693"
NFC_MODULATION_TYPE_V: str = "iso18092"

# NFC target types
NFC_TARGET_TYPE_ISO14443A: str = "nfc_dep_a"
NFC_TARGET_TYPE_ISO14443B: str = "nfc_dep_b"
NFC_TARGET_TYPE_ISO15693: str = "iso15693"
NFC_TARGET_TYPE_ISO18092: str = "nfc_dep"

# ---------------------------------------------------------------------------
# Global Registries
# ---------------------------------------------------------------------------
_controllers: Dict[str, NfcController] = {}
_devices: Dict[str, NfcDevice] = {}
_llcp_saps: Dict[int, NfcLlcpSap] = {}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class NfcTarget:
    """NFC target (card/device) information"""
    target_type: str = ""
    modulation_type: str = ""
    uid: bytes = b""
    atqa: bytes = b""
    sak: int = 0
    ats: bytes = b""
    is_present: bool = False


@dataclass
class NfcSecureElement:
    """NFC secure element"""
    name: str
    is_enabled: bool = False
    aid_list: List[bytes] = field(default_factory=list)


@dataclass
class NfcController:
    """NFC controller device"""
    name: str
    supported_protocols: int = NFC_RF_INITIATOR | NFC_RF_TARGET
    max_targets: int = 16
    is_registered: bool = False
    is_powered: bool = False
    rf_mode: int = 0
    _targets: List[NfcTarget] = field(default_factory=list)
    _secure_elements: Dict[str, NfcSecureElement] = field(default_factory=dict)
    _ops: Dict[str, Callable] = field(default_factory=dict)


@dataclass
class NfcDevice:
    """Consumer NFC device"""
    name: str
    controller_name: str
    is_open: bool = False
    mode: int = NFC_RF_INITIATOR
    _callbacks: Dict[str, Callable] = field(default_factory=dict)


@dataclass
class NfcLlcpSap:
    """LLCP Service Access Point"""
    sap_id: int
    name: str
    service_name: str = ""
    is_connected: bool = False
    _recv_buf: List[bytes] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Registration Functions
# ---------------------------------------------------------------------------
def register_controller(name: str, supported_protocols: int = 0) -> NfcController:
    """Register an NFC controller"""
    if name in _controllers:
        log.warning("NFC controller %s already registered", name)
        return _controllers[name]

    ctrl = NfcController(
        name=name,
        supported_protocols=supported_protocols or (NFC_RF_INITIATOR | NFC_RF_TARGET),
        is_registered=True,
    )
    _controllers[name] = ctrl
    log.info("Registered NFC controller: %s", name)
    return ctrl


def register_device(name: str, controller_name: str) -> NfcDevice:
    """Register an NFC device"""
    if name in _devices:
        log.warning("NFC device %s already registered", name)
        return _devices[name]

    device = NfcDevice(
        name=name,
        controller_name=controller_name,
        is_open=True,
    )
    _devices[name] = device
    log.info("Registered NFC device: %s (controller=%s)", name, controller_name)
    return device


def unregister_controller(name: str) -> bool:
    """Unregister an NFC controller"""
    if name not in _controllers:
        log.warning("NFC controller %s not found", name)
        return False
    del _controllers[name]
    log.info("Unregistered NFC controller: %s", name)
    return True


def unregister_device(name: str) -> bool:
    """Unregister an NFC device"""
    if name not in _devices:
        log.warning("NFC device %s not found", name)
        return False
    del _devices[name]
    log.info("Unregistered NFC device: %s", name)
    return True


def get_controller(name: str) -> Optional[NfcController]:
    """Get a registered NFC controller"""
    return _controllers.get(name)


def get_device(name: str) -> Optional[NfcDevice]:
    """Get a registered NFC device"""
    return _devices.get(name)


def list_controllers() -> List[str]:
    """List all registered NFC controllers"""
    return list(_controllers.keys())


def list_devices() -> List[str]:
    """List all registered NFC devices"""
    return list(_devices.keys())


# ---------------------------------------------------------------------------
# Controller Operations
# ---------------------------------------------------------------------------
def enable_controller(name: str) -> bool:
    """Enable NFC controller"""
    ctrl = get_controller(name)
    if ctrl is None:
        log.error("NFC controller %s not found", name)
        return False

    ctrl.is_powered = True
    log.info("Enabled NFC controller: %s", name)
    return True


def disable_controller(name: str) -> bool:
    """Disable NFC controller"""
    ctrl = get_controller(name)
    if ctrl is None:
        return False

    ctrl.is_powered = False
    ctrl.rf_mode = 0
    ctrl._targets.clear()
    log.info("Disabled NFC controller: %s", name)
    return True


def set_rf_mode(name: str, mode: int) -> bool:
    """Set RF operating mode"""
    ctrl = get_controller(name)
    if ctrl is None:
        return False

    ctrl.rf_mode = mode
    log.debug("Set RF mode on %s: 0x%02X", name, mode)
    return True


def poll_targets(name: str, timeout_ms: int = 1000) -> List[NfcTarget]:
    """Poll for NFC targets"""
    ctrl = get_controller(name)
    if ctrl is None:
        return []

    # Simulated target detection
    targets = []
    if ctrl.is_powered and ctrl.rf_mode & NFC_RF_INITIATOR:
        target = NfcTarget(
            target_type=NFC_TARGET_TYPE_ISO14443A,
            modulation_type=NFC_MODULATION_TYPE_A,
            uid=b"\x04\x12\x34\x56\x78\x9A\xBC",
            sak=0x08,
            is_present=True,
        )
        targets.append(target)
        ctrl._targets.append(target)

    log.debug("Polled %d targets on %s", len(targets), name)
    return targets


def select_target(name: str, target: NfcTarget) -> bool:
    """Select an NFC target"""
    ctrl = get_controller(name)
    if ctrl is None:
        return False

    if target not in ctrl._targets:
        log.error("Target not found")
        return False

    log.info("Selected target on %s: %s", name, target.uid.hex())
    return True


def send_data(name: str, data: bytes) -> Optional[bytes]:
    """Send data to selected target"""
    ctrl = get_controller(name)
    if ctrl is None:
        return None

    # Simulated response
    response = b"\x90\x00"  # SW_OK
    log.debug("Sent %d bytes, received %d bytes", len(data), len(response))
    return response


def get_targets(name: str) -> List[NfcTarget]:
    """Get detected targets"""
    ctrl = get_controller(name)
    if ctrl is None:
        return []
    return ctrl._targets.copy()


# ---------------------------------------------------------------------------
# Secure Element Operations
# ---------------------------------------------------------------------------
def register_secure_element(controller_name: str, se_name: str) -> bool:
    """Register a secure element"""
    ctrl = get_controller(controller_name)
    if ctrl is None:
        return False

    se = NfcSecureElement(name=se_name)
    ctrl._secure_elements[se_name] = se
    log.info("Registered secure element: %s on %s", se_name, controller_name)
    return True


def enable_secure_element(controller_name: str, se_name: str) -> bool:
    """Enable a secure element"""
    ctrl = get_controller(controller_name)
    if ctrl is None:
        return False

    se = ctrl._secure_elements.get(se_name)
    if se is None:
        return False

    se.is_enabled = True
    log.info("Enabled secure element: %s", se_name)
    return True


def disable_secure_element(controller_name: str, se_name: str) -> bool:
    """Disable a secure element"""
    ctrl = get_controller(controller_name)
    if ctrl is None:
        return False

    se = ctrl._secure_elements.get(se_name)
    if se is None:
        return False

    se.is_enabled = False
    log.info("Disabled secure element: %s", se_name)
    return True


# ---------------------------------------------------------------------------
# LLCP Operations
# ---------------------------------------------------------------------------
def create_llcp_sap(name: str, service_name: str = "") -> NfcLlcpSap:
    """Create an LLCP Service Access Point"""
    sap_id = len(_llcp_saps) + 1

    if sap_id in _llcp_saps:
        log.warning("LLCP SAP ID %d already exists", sap_id)
        return _llcp_saps[sap_id]

    sap = NfcLlcpSap(
        sap_id=sap_id,
        name=name,
        service_name=service_name or name,
    )
    _llcp_saps[sap_id] = sap
    log.info("Created LLCP SAP: %s (id=%d)", name, sap_id)
    return sap


def connect_llcp_sap(sap_id: int) -> bool:
    """Connect an LLCP SAP"""
    sap = _llcp_saps.get(sap_id)
    if sap is None:
        return False

    sap.is_connected = True
    log.info("Connected LLCP SAP: %s", sap.name)
    return True


def disconnect_llcp_sap(sap_id: int) -> bool:
    """Disconnect an LLCP SAP"""
    sap = _llcp_saps.get(sap_id)
    if sap is None:
        return False

    sap.is_connected = False
    log.info("Disconnected LLCP SAP: %s", sap.name)
    return True


def send_llcp_data(sap_id: int, data: bytes) -> bool:
    """Send data via LLCP"""
    sap = _llcp_saps.get(sap_id)
    if sap is None or not sap.is_connected:
        return False

    log.debug("Sent %d bytes via LLCP SAP %s", len(data), sap.name)
    return True


def receive_llcp_data(sap_id: int) -> Optional[bytes]:
    """Receive data from LLCP"""
    sap = _llcp_saps.get(sap_id)
    if sap is None or not sap._recv_buf:
        return None

    return sap._recv_buf.pop(0)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=== UmerOS NFC Framework Demo ===\n")

    # Register controller
    ctrl = register_controller("nfc0", NFC_RF_INITIATOR | NFC_RF_TARGET)
    enable_controller("nfc0")

    # Register device
    register_device("nfc-dev0", "nfc0")

    print(f"Controllers: {list_controllers()}")
    print(f"Devices: {list_devices()}")

    # Poll for targets
    set_rf_mode("nfc0", NFC_RF_INITIATOR)
    targets = poll_targets("nfc0")
    print(f"\nDetected {len(targets)} target(s)")
    for t in targets:
        print(f"  Type: {t.target_type}, UID: {t.uid.hex()}")

    # Send data
    if targets:
        select_target("nfc0", targets[0])
        response = send_data("nfc0", b"\x00\xA4\x04\x00")
        print(f"  Response: {response.hex() if response else 'None'}")

    # Secure element
    register_secure_element("nfc0", "eSE")
    enable_secure_element("nfc0", "eSE")

    # LLCP
    sap = create_llcp_sap("nfc-app", service_name="urn:nfc:sn:test")
    connect_llcp_sap(sap.sap_id)
    send_llcp_data(sap.sap_id, b"Hello NFC!")
    print(f"\nLLCP SAP {sap.name}: connected={sap.is_connected}")

    # Cleanup
    disable_controller("nfc0")
