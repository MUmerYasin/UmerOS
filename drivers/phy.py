"""
UmerOS PHY Subsystem
====================
Linux kernel-like Physical Layer Transceiver framework.
Manages USB, PCIe, HDMI, Ethernet, and SATA PHYs.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# PHY Type Constants
# ---------------------------------------------------------------------------
PHY_TYPE_USB: str = "usb"
PHY_TYPE_PCIE: str = "pcie"
PHY_TYPE_HDMI: str = "hdmi"
PHY_TYPE_ETHERNET: str = "ethernet"
PHY_TYPE_SATA: str = "sata"
PHY_TYPE_DP: str = "dp"
PHY_TYPE_MIPI_DPHY: str = "mipi_dphy"
PHY_TYPE_UFS: str = "ufs"
PHY_TYPE_EDP: str = "edp"

# ---------------------------------------------------------------------------
# PHY Mode Constants
# ---------------------------------------------------------------------------
PHY_MODE_HOST: str = "host"
PHY_MODE_DEVICE: str = "device"
PHY_MODE_OTG: str = "otg"
PHY_MODE_SUSPEND: str = "suspend"
PHY_MODE_RESUME: str = "resume"

# ---------------------------------------------------------------------------
# Speed Constants (Mbps)
# ---------------------------------------------------------------------------
SPEED_USB_LS: int = 1       # USB Low-Speed 1.5 Mbps
SPEED_USB_FS: int = 12      # USB Full-Speed 12 Mbps
SPEED_USB_HS: int = 480     # USB High-Speed 480 Mbps
SPEED_USB_SS: int = 5000    # USB SuperSpeed 5 Gbps
SPEED_USB_SS_PLUS: int = 10000  # USB SuperSpeed+ 10 Gbps

SPEED_PCIE_GEN1: int = 2500  # PCIe Gen1 2.5 GT/s per lane
SPEED_PCIE_GEN2: int = 5000  # PCIe Gen2 5 GT/s per lane
SPEED_PCIE_GEN3: int = 8000  # PCIe Gen3 8 GT/s per lane

SPEED_HDMI_14: int = 10200   # HDMI 1.4 ~10.2 Gbps
SPEED_HDMI_20: int = 18000   # HDMI 2.0 ~18 Gbps
SPEED_HDMI_21: int = 48000   # HDMI 2.1 ~48 Gbps

SPEED_ETH_100: int = 100
SPEED_ETH_1000: int = 1000
SPEED_ETH_2500: int = 2500
SPEED_ETH_10G: int = 10000

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PhyConfig:
    """PHY configuration parameters."""
    speed: int = 0
    lanes: int = 1
    mode: str = PHY_MODE_HOST
    polarity: str = "normal"       # "normal", "inverted"
    sscaled: bool = False          # superspeed plus
    amp_enable: bool = True
    vbus_supply: str = "5V"


@dataclass
class Phy:
    """Physical layer transceiver."""
    id: int
    name: str
    phy_type: str                  # "usb", "pcie", "hdmi", "ethernet", "sata", "dp"
    label: str
    speed: int = 0                 # current speed (Mbps)
    max_speed: int = 0
    lanes: int = 1                 # number of lanes
    mode: str = PHY_MODE_HOST      # "host", "device", "otg"
    _power_state: bool = field(default=False, repr=False)
    enabled: bool = True
    _init_done: bool = field(default=False, repr=False)
    _provider: Optional[PhyProvider] = field(default=None, repr=False)
    _ops: dict = field(default_factory=dict, repr=False)
    _config: PhyConfig = field(default_factory=PhyConfig, repr=False)
    _consumers: list = field(default_factory=list, repr=False)

    # -- properties ---------------------------------------------------------

    @property
    def power_on(self) -> bool:
        return self._power_state

    @property
    def init_done(self) -> bool:
        return self._init_done

    # -- lifecycle ----------------------------------------------------------

    def init(self) -> None:
        if self._init_done:
            return
        if not self.enabled:
            raise RuntimeError(f"PHY {self.name} is disabled")
        if self._ops.get("init"):
            self._ops["init"](self)
        self._init_done = True
        print(f"  [phy] {self.name}: initialized")

    def exit(self) -> None:
        if not self._init_done:
            return
        if self._power_state:
            self.power_off()
        if self._ops.get("exit"):
            self._ops["exit"](self)
        self._init_done = False
        print(f"  [phy] {self.name}: shutdown")

    def do_power_on(self) -> None:
        if not self._init_done:
            raise RuntimeError(f"PHY {self.name} not initialized")
        if self._power_state:
            return
        if self._ops.get("power_on"):
            self._ops["power_on"](self)
        self._power_state = True
        print(f"  [phy] {self.name}: power on")

    def do_power_off(self) -> None:
        if not self._power_state:
            return
        if self._ops.get("power_off"):
            self._ops["power_off"](self)
        self._power_state = False
        print(f"  [phy] {self.name}: power off")

    def set_mode(self, mode: str) -> None:
        if mode not in (PHY_MODE_HOST, PHY_MODE_DEVICE,
                        PHY_MODE_OTG, PHY_MODE_SUSPEND, PHY_MODE_RESUME):
            raise ValueError(f"Invalid PHY mode: {mode!r}")
        old = self.mode
        self.mode = mode
        if self._ops.get("set_mode"):
            self._ops["set_mode"](self, mode)
        print(f"  [phy] {self.name}: mode {old!r} -> {mode!r}")

    def set_speed(self, speed: int) -> None:
        if speed < 0:
            raise ValueError(f"Invalid PHY speed: {speed}")
        self.speed = speed
        if self._ops.get("set_speed"):
            self._ops["set_speed"](self, speed)
        print(f"  [phy] {self.name}: speed -> {speed} Mbps")

    def set_lanes(self, lanes: int) -> None:
        if lanes < 1:
            raise ValueError(f"Invalid lane count: {lanes}")
        self.lanes = lanes
        if self._ops.get("set_lanes"):
            self._ops["set_lanes"](self, lanes)
        print(f"  [phy] {self.name}: lanes -> {lanes}")

    def configure(self, config: PhyConfig) -> None:
        self._config = config
        if config.speed:
            self.set_speed(config.speed)
        if config.lanes != 1:
            self.set_lanes(config.lanes)
        if config.mode != self.mode:
            self.set_mode(config.mode)
        if self._ops.get("configure"):
            self._ops["configure"](self, config)
        print(f"  [phy] {self.name}: configured {config}")

    def status_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.phy_type,
            "label": self.label,
            "speed_mbps": self.speed,
            "max_speed_mbps": self.max_speed,
            "lanes": self.lanes,
            "mode": self.mode,
            "powered": self._power_state,
            "enabled": self.enabled,
            "initialized": self._init_done,
            "consumers": list(self._consumers),
        }


@dataclass
class PhyProvider:
    """PHY provider (chip/IP block) that owns one or more PHY instances."""
    name: str
    phys: list = field(default_factory=list)
    _is_registered: bool = field(default=False, repr=False)

    def add_phy(self, phy: Phy) -> Phy:
        phy._provider = self
        self.phys.append(phy)
        return phy

    def find_phy(self, phy_type: str) -> Optional[Phy]:
        for p in self.phys:
            if p.phy_type == phy_type:
                return p
        return None

    def find_phy_by_id(self, phy_id: int) -> Optional[Phy]:
        for p in self.phys:
            if p.id == phy_id:
                return p
        return None

    def all_phys(self) -> list:
        return list(self.phys)


# ---------------------------------------------------------------------------
# Global Registry
# ---------------------------------------------------------------------------
_next_phy_id: int = 0
_providers: dict[str, PhyProvider] = {}
_phy_registry: dict[int, Phy] = {}
_consumer_refs: dict[str, list[int]] = {}   # consumer_name -> [phy_id, ...]


def _alloc_phy_id() -> int:
    global _next_phy_id
    phy_id = _next_phy_id
    _next_phy_id += 1
    return phy_id


# ---------------------------------------------------------------------------
# Kernel-like API Functions
# ---------------------------------------------------------------------------

def phy_register(provider: PhyProvider) -> None:
    """Register PHY provider -- like of_phy_provider_register()."""
    if provider.name in _providers:
        raise ValueError(f"PHY provider {provider.name!r} already registered")
    _providers[provider.name] = provider
    provider._is_registered = True
    for phy in provider.phys:
        _phy_registry[phy.id] = phy
    print(f"  [phy] provider {provider.name!r} registered "
          f"({len(provider.phys)} PHYs)")


def phy_unregister(provider_name: str) -> None:
    """Unregister PHY provider."""
    provider = _providers.pop(provider_name, None)
    if provider is None:
        raise KeyError(f"PHY provider {provider_name!r} not found")
    provider._is_registered = False
    for phy in provider.phys:
        _phy_registry.pop(phy.id, None)
    print(f"  [phy] provider {provider_name!r} unregistered")


def phy_get(consumer_name: str, index: int = 0) -> Phy:
    """Get PHY -- like phy_get()."""
    phys = list(_phy_registry.values())
    if index >= len(phys):
        raise IndexError(f"No PHY at index {index} (total: {len(phys)})")
    phy = phys[index]
    _consumer_refs.setdefault(consumer_name, [])
    if phy.id not in _consumer_refs[consumer_name]:
        _consumer_refs[consumer_name].append(phy.id)
    phy._consumers.append(consumer_name)
    print(f"  [phy] consumer {consumer_name!r} -> PHY {phy.name} (id={phy.id})")
    return phy


def phy_put(consumer_name: str) -> None:
    """Release PHY reference."""
    refs = _consumer_refs.pop(consumer_name, [])
    for pid in refs:
        phy = _phy_registry.get(pid)
        if phy and consumer_name in phy._consumers:
            phy._consumers.remove(consumer_name)
    if refs:
        print(f"  [phy] consumer {consumer_name!r} released {len(refs)} PHY ref(s)")
    else:
        print(f"  [phy] consumer {consumer_name!r} had no active PHY refs")


def phy_init(phy_id: int) -> None:
    """Initialize PHY -- like phy_init()."""
    phy = _phy_registry.get(phy_id)
    if phy is None:
        raise KeyError(f"PHY id {phy_id} not found")
    phy.init()


def phy_exit(phy_id: int) -> None:
    """Shutdown PHY -- like phy_exit()."""
    phy = _phy_registry.get(phy_id)
    if phy is None:
        raise KeyError(f"PHY id {phy_id} not found")
    phy.exit()


def phy_power_on(phy_id: int) -> None:
    """Power on PHY -- like phy_power_on()."""
    phy = _phy_registry.get(phy_id)
    if phy is None:
        raise KeyError(f"PHY id {phy_id} not found")
    phy.do_power_on()


def phy_power_off(phy_id: int) -> None:
    """Power off PHY."""
    phy = _phy_registry.get(phy_id)
    if phy is None:
        raise KeyError(f"PHY id {phy_id} not found")
    phy.do_power_off()


def phy_set_mode(phy_id: int, mode: str) -> None:
    """Set PHY mode."""
    phy = _phy_registry.get(phy_id)
    if phy is None:
        raise KeyError(f"PHY id {phy_id} not found")
    phy.set_mode(mode)


def phy_set_speed(phy_id: int, speed: int) -> None:
    """Set PHY speed."""
    phy = _phy_registry.get(phy_id)
    if phy is None:
        raise KeyError(f"PHY id {phy_id} not found")
    phy.set_speed(speed)


def phy_set_lanes(phy_id: int, lanes: int) -> None:
    """Set number of lanes."""
    phy = _phy_registry.get(phy_id)
    if phy is None:
        raise KeyError(f"PHY id {phy_id} not found")
    phy.set_lanes(lanes)


def phy_configure(phy_id: int, config: PhyConfig) -> None:
    """Configure PHY with PhyConfig."""
    phy = _phy_registry.get(phy_id)
    if phy is None:
        raise KeyError(f"PHY id {phy_id} not found")
    phy.configure(config)


def phy_get_speed(phy_id: int) -> int:
    """Get current PHY speed."""
    phy = _phy_registry.get(phy_id)
    if phy is None:
        raise KeyError(f"PHY id {phy_id} not found")
    return phy.speed


def phy_get_mode(phy_id: int) -> str:
    """Get current PHY mode."""
    phy = _phy_registry.get(phy_id)
    if phy is None:
        raise KeyError(f"PHY id {phy_id} not found")
    return phy.mode


def phy_is_powered(phy_id: int) -> bool:
    """Check if PHY is powered on."""
    phy = _phy_registry.get(phy_id)
    if phy is None:
        raise KeyError(f"PHY id {phy_id} not found")
    return phy.power_on


def phy_create(consumer_name: str, phy_type: str, name: str,
               label: str = "") -> Phy:
    """Create a PHY."""
    global _next_phy_id
    phy_id = _alloc_phy_id()
    phy = Phy(id=phy_id, name=name, phy_type=phy_type,
              label=label or name)
    _phy_registry[phy_id] = phy
    _consumer_refs.setdefault(consumer_name, [])
    _consumer_refs[consumer_name].append(phy_id)
    phy._consumers.append(consumer_name)
    print(f"  [phy] created {phy_type!r} PHY {name!r} (id={phy_id})")
    return phy


def phy_get_all() -> list:
    """Return list of all registered PHYs."""
    return list(_phy_registry.values())


def phy_get_by_type(phy_type: str) -> list:
    """Return all PHYs of a given type."""
    return [p for p in _phy_registry.values() if p.phy_type == phy_type]


# ---------------------------------------------------------------------------
# Built-in PHY Drivers
# ---------------------------------------------------------------------------

class UsbPhyProvider(PhyProvider):
    """USB PHY provider (USB 2.0/3.0/3.1)."""

    def __init__(self, name: str = "usb-phy",
                 ports: int = 2,
                 max_speed: int = SPEED_USB_SS) -> None:
        super().__init__(name=name)
        for i in range(ports):
            phy_id = _alloc_phy_id()
            speed = SPEED_USB_SS if max_speed >= SPEED_USB_SS else SPEED_USB_HS
            phy = Phy(
                id=phy_id,
                name=f"{name}-port{i}",
                phy_type=PHY_TYPE_USB,
                label=f"USB Port {i}",
                max_speed=max_speed,
                speed=speed if max_speed <= SPEED_USB_SS else SPEED_USB_SS,
                _ops={
                    "init": self._usb_init,
                    "exit": self._usb_exit,
                    "power_on": self._usb_power_on,
                    "power_off": self._usb_power_off,
                    "set_mode": self._usb_set_mode,
                    "set_speed": self._usb_set_speed,
                },
            )
            self.add_phy(phy)

    @staticmethod
    def _usb_init(phy: Phy) -> None:
        print(f"    [usb] {phy.name}: USB PHY reset, clock enable, UTMI+ link up")

    @staticmethod
    def _usb_exit(phy: Phy) -> None:
        print(f"    [usb] {phy.name}: UTMI+ link down, clock disable")

    @staticmethod
    def _usb_power_on(phy: Phy) -> None:
        print(f"    [usb] {phy.name}: VBUS supply {phy._config.vbus_supply}, "
              f"USB PHY power sequence start")

    @staticmethod
    def _usb_power_off(phy: Phy) -> None:
        print(f"    [usb] {phy.name}: VBUS off, USB PHY power down")

    @staticmethod
    def _usb_set_mode(phy: Phy, mode: str) -> None:
        if mode == PHY_MODE_OTG:
            print(f"    [usb] {phy.name}: OTG SRP/HNP enabled")
        elif mode == PHY_MODE_HOST:
            print(f"    [usb] {phy.name}: host mode, VBUS driving")
        elif mode == PHY_MODE_DEVICE:
            print(f"    [usb] {phy.name}: device mode, VBUS sensing")
        elif mode == PHY_MODE_SUSPEND:
            print(f"    [usb] {phy.name}: suspend, remote wakeup armed")
        elif mode == PHY_MODE_RESUME:
            print(f"    [usb] {phy.name}: resume, signaling K")

    @staticmethod
    def _usb_set_speed(phy: Phy, speed: int) -> None:
        speed_map = {
            SPEED_USB_LS: "Low-Speed (1.5 Mbps)",
            SPEED_USB_FS: "Full-Speed (12 Mbps)",
            SPEED_USB_HS: "High-Speed (480 Mbps)",
            SPEED_USB_SS: "SuperSpeed (5 Gbps)",
            SPEED_USB_SS_PLUS: "SuperSpeed+ (10 Gbps)",
        }
        label = speed_map.get(speed, f"{speed} Mbps")
        print(f"    [usb] {phy.name}: speed -> {label}")


class PciePhyProvider(PhyProvider):
    """PCIe PHY provider (Gen 1/2/3)."""

    def __init__(self, name: str = "pcie-phy",
                 lanes: int = 4,
                 gen: int = 3) -> None:
        super().__init__(name=name)
        gen_speed = {
            1: SPEED_PCIE_GEN1,
            2: SPEED_PCIE_GEN2,
            3: SPEED_PCIE_GEN3,
        }
        speed = gen_speed.get(gen, SPEED_PCIE_GEN3)
        phy_id = _alloc_phy_id()
        phy = Phy(
            id=phy_id,
            name=f"{name}-x{lanes}",
            phy_type=PHY_TYPE_PCIE,
            label=f"PCIe x{lanes} Gen{gen}",
            speed=speed,
            max_speed=speed,
            lanes=lanes,
            _ops={
                "init": self._pcie_init,
                "exit": self._pcie_exit,
                "power_on": self._pcie_power_on,
                "power_off": self._pcie_power_off,
                "set_lanes": self._pcie_set_lanes,
                "set_speed": self._pcie_set_speed,
                "configure": self._pcie_configure,
            },
        )
        self.add_phy(phy)

    @staticmethod
    def _pcie_init(phy: Phy) -> None:
        print(f"    [pcie] {phy.name}: LTSSM training, "
              f"lane polarity {phy._config.polarity}")
        print(f"    [pcie] {phy.name}: DLL link up, "
              f"L{phy.lanes} x{phy.speed // 1000} GT/s")

    @staticmethod
    def _pcie_exit(phy: Phy) -> None:
        print(f"    [pcie] {phy.name}: DLL link down, LTSSM reset")

    @staticmethod
    def _pcie_power_on(phy: Phy) -> None:
        print(f"    [pcie] {phy.name}: AUX power on, impedance calibration")

    @staticmethod
    def _pcie_power_off(phy: Phy) -> None:
        print(f"    [pcie] {phy.name}: power down sequence")

    @staticmethod
    def _pcie_set_lanes(phy: Phy, lanes: int) -> None:
        print(f"    [pcie] {phy.name}: retrain LTSSM for L{lanes}")

    @staticmethod
    def _pcie_set_speed(phy: Phy, speed: int) -> None:
        gen = 3 if speed >= SPEED_PCIE_GEN3 else (2 if speed >= SPEED_PCIE_GEN2 else 1)
        print(f"    [pcie] {phy.name}: speed change -> Gen{gen}")

    @staticmethod
    def _pcie_configure(phy: Phy, config: PhyConfig) -> None:
        print(f"    [pcie] {phy.name}: applying polarity={config.polarity}, "
              f"amp_enable={config.amp_enable}")


class HdmiPhyProvider(PhyProvider):
    """HDMI PHY provider (1.4/2.0/2.1)."""

    def __init__(self, name: str = "hdmi-phy",
                 version: float = 2.0) -> None:
        super().__init__(name=name)
        version_speed = {
            1.4: SPEED_HDMI_14,
            2.0: SPEED_HDMI_20,
            2.1: SPEED_HDMI_21,
        }
        speed = version_speed.get(version, SPEED_HDMI_20)
        phy_id = _alloc_phy_id()
        phy = Phy(
            id=phy_id,
            name=f"{name}-v{version}",
            phy_type=PHY_TYPE_HDMI,
            label=f"HDMI {version}",
            speed=speed,
            max_speed=speed,
            lanes=4,
            _ops={
                "init": self._hdmi_init,
                "exit": self._hdmi_exit,
                "power_on": self._hdmi_power_on,
                "power_off": self._hdmi_power_off,
                "set_speed": self._hdmi_set_speed,
            },
        )
        self.add_phy(phy)

    @staticmethod
    def _hdmi_init(phy: Phy) -> None:
        print(f"    [hdmi] {phy.name}: DDC init, EDID read, "
              f"TMDS/FRL clock enable")

    @staticmethod
    def _hdmi_exit(phy: Phy) -> None:
        print(f"    [hdmi] {phy.name}: TMDS/FRL clock disable")

    @staticmethod
    def _hdmi_power_on(phy: Phy) -> None:
        print(f"    [hdmi] {phy.name}: HDMI PHY PLL lock, "
              f"TMDS enable, 5V rail up")

    @staticmethod
    def _hdmi_power_off(phy: Phy) -> None:
        print(f"    [hdmi] {phy.name}: 5V rail off, PLL power down")

    @staticmethod
    def _hdmi_set_speed(phy: Phy, speed: int) -> None:
        if speed >= SPEED_HDMI_21:
            print(f"    [hdmi] {phy.name}: FRL mode, {speed // 1000} Gbps")
        else:
            print(f"    [hdmi] {phy.name}: TMDS mode, {speed // 1000} Gbps")


class EthernetPhyProvider(PhyProvider):
    """Ethernet PHY (10/100/1000/2500)."""

    def __init__(self, name: str = "eth-phy",
                 ports: int = 1,
                 max_speed: int = SPEED_ETH_1000) -> None:
        super().__init__(name=name)
        for i in range(ports):
            phy_id = _alloc_phy_id()
            phy = Phy(
                id=phy_id,
                name=f"{name}-port{i}",
                phy_type=PHY_TYPE_ETHERNET,
                label=f"Ethernet Port {i}",
                speed=SPEED_ETH_1000,
                max_speed=max_speed,
                _ops={
                    "init": self._eth_init,
                    "exit": self._eth_exit,
                    "power_on": self._eth_power_on,
                    "power_off": self._eth_power_off,
                    "set_speed": self._eth_set_speed,
                },
            )
            self.add_phy(phy)

    @staticmethod
    def _eth_init(phy: Phy) -> None:
        print(f"    [eth] {phy.name}: MII/RGMII init, MDIO bus scan")

    @staticmethod
    def _eth_exit(phy: Phy) -> None:
        print(f"    [eth] {phy.name}: MAC disconnect")

    @staticmethod
    def _eth_power_on(phy: Phy) -> None:
        print(f"    [eth] {phy.name}: PHY reset, auto-neg start")

    @staticmethod
    def _eth_power_off(phy: Phy) -> None:
        print(f"    [eth] {phy.name}: link down, power off")

    @staticmethod
    def _eth_set_speed(phy: Phy, speed: int) -> None:
        duplex = "Full" if speed >= SPEED_ETH_1000 else "Half/Full"
        print(f"    [eth] {phy.name}: {speed} Mbps {duplex}, "
              f"auto-neg{'off' if speed >= SPEED_ETH_2500 else 'on'}")


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def demo() -> None:
    print("=" * 64)
    print("  UmerOS PHY Subsystem Demo")
    print("=" * 64)

    # -- 1. Create providers ------------------------------------------------
    print("\n--- 1. Create PHY providers ---")
    usb_provider = UsbPhyProvider("usb-phy", ports=2,
                                  max_speed=SPEED_USB_SS_PLUS)
    pcie_provider = PciePhyProvider("pcie-phy", lanes=4, gen=3)
    hdmi_provider = HdmiPhyProvider("hdmi-phy", version=2.1)
    eth_provider = EthernetPhyProvider("eth-phy", ports=2,
                                       max_speed=SPEED_ETH_2500)

    # -- 2. Register providers ----------------------------------------------
    print("\n--- 2. Register providers ---")
    phy_register(usb_provider)
    phy_register(pcie_provider)
    phy_register(hdmi_provider)
    phy_register(eth_provider)

    # -- 3. List all PHYs ---------------------------------------------------
    print("\n--- 3. All registered PHYs ---")
    for p in phy_get_all():
        print(f"  [{p.id:2d}] {p.name:20s}  type={p.phy_type:10s}  "
              f"label={p.label}")

    # -- 4. Consumer requests USB PHY ---------------------------------------
    print("\n--- 4. Consumer requests USB PHY ---")
    usb_phy = phy_get("gadget-zero", index=0)
    print(f"  Got: PHY {usb_phy.name} (id={usb_phy.id})")

    # -- 5. Init -> configure -> power on -> use -----------------------------
    print("\n--- 5. Init -> Configure -> Power On -> Use ---")
    phy_init(usb_phy.id)

    cfg = PhyConfig(
        speed=SPEED_USB_SS,
        lanes=1,
        mode=PHY_MODE_DEVICE,
        polarity="normal",
        vbus_supply="5V",
    )
    phy_configure(usb_phy.id, cfg)

    phy_power_on(usb_phy.id)
    phy_set_speed(usb_phy.id, SPEED_USB_HS)
    phy_set_mode(usb_phy.id, PHY_MODE_HOST)

    print(f"\n  Status: speed={phy_get_speed(usb_phy.id)} Mbps, "
          f"mode={phy_get_mode(usb_phy.id)}, "
          f"powered={phy_is_powered(usb_phy.id)}")

    # -- 6. PCIe lane configuration -----------------------------------------
    print("\n--- 6. PCIe lane configuration ---")
    pcie_phy = phy_get_by_type(PHY_TYPE_PCIE)[0]
    phy_get("nvme-ctrl", index=pcie_phy.id)
    phy_init(pcie_phy.id)
    phy_power_on(pcie_phy.id)
    phy_set_speed(pcie_phy.id, SPEED_PCIE_GEN3)
    print(f"  PCIe: {pcie_phy.lanes} lanes @ {pcie_phy.speed // 1000} GT/s")

    # -- 7. HDMI setup ------------------------------------------------------
    print("\n--- 7. HDMI PHY setup ---")
    hdmi_phy = phy_get_by_type(PHY_TYPE_HDMI)[0]
    phy_get("display-0", index=hdmi_phy.id)
    phy_init(hdmi_phy.id)
    phy_power_on(hdmi_phy.id)
    phy_set_speed(hdmi_phy.id, SPEED_HDMI_21)
    print(f"  HDMI: {hdmi_phy.label}, {hdmi_phy.speed // 1000} Gbps")

    # -- 8. Ethernet setup --------------------------------------------------
    print("\n--- 8. Ethernet PHY setup ---")
    eth_phy = phy_get_by_type(PHY_TYPE_ETHERNET)[0]
    phy_get("net-eth0", index=eth_phy.id)
    phy_init(eth_phy.id)
    phy_power_on(eth_phy.id)
    phy_set_speed(eth_phy.id, SPEED_ETH_2500)
    print(f"  Ethernet: {eth_phy.label}, {eth_phy.speed} Mbps")

    # -- 9. Mode switching demo (host -> OTG -> device) ---------------------
    print("\n--- 9. Mode switching: host -> OTG -> device ---")
    phy_set_mode(usb_phy.id, PHY_MODE_OTG)
    phy_set_mode(usb_phy.id, PHY_MODE_DEVICE)

    # -- 10. Power off & exit -----------------------------------------------
    print("\n--- 10. Power off & shutdown ---")
    phy_power_off(usb_phy.id)
    phy_exit(usb_phy.id)
    phy_power_off(pcie_phy.id)
    phy_exit(pcie_phy.id)
    phy_power_off(hdmi_phy.id)
    phy_exit(hdmi_phy.id)
    phy_power_off(eth_phy.id)
    phy_exit(eth_phy.id)

    # -- 11. Release references ---------------------------------------------
    print("\n--- 11. Release consumer references ---")
    phy_put("gadget-zero")
    phy_put("nvme-ctrl")
    phy_put("display-0")
    phy_put("net-eth0")

    # -- 12. Final status ---------------------------------------------------
    print("\n--- 12. Final PHY status ---")
    print(f"  {'ID':>3s}  {'Name':20s}  {'Type':10s}  "
          f"{'Powered':>7s}  {'Init':>4s}  {'Speed':>8s}")
    print(f"  {'---':>3s}  {'----':20s}  {'----':10s}  "
          f"{'-------':>7s}  {'----':>4s}  {'-----':>8s}")
    for p in phy_get_all():
        st = "ON" if p.power_on else "OFF"
        ini = "YES" if p.init_done else "NO"
        print(f"  {p.id:3d}  {p.name:20s}  {p.phy_type:10s}  "
              f"{st:>7s}  {ini:>4s}  {p.speed:>6d} Mb")

    # -- 13. Unregister all -------------------------------------------------
    print("\n--- 13. Unregister providers ---")
    phy_unregister("usb-phy")
    phy_unregister("pcie-phy")
    phy_unregister("hdmi-phy")
    phy_unregister("eth-phy")

    print("\n" + "=" * 64)
    print("  PHY subsystem demo complete.")
    print("=" * 64)


if __name__ == "__main__":
    demo()
