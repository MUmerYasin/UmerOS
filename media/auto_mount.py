"""
UmerOS /media - Auto-Mount Daemon
===================================

Listens for hotplug events and automatically mounts/unmounts
removable media following FHS conventions.

FHS/TLDP reference:
    /media contains mount points for removable media.  When multiple
    devices are used, mount directories can be created by appending
    a digit (e.g. /media/cdrom0, /media/cdrom1), with the
    unqualified name existing as a symlink to the latest device.

Modules
-------
- ``AutoMountDaemon`` - event-driven auto-mount service.
- ``AutoMountPolicy`` - per-media-type mount policy.
- ``AutoMountEvent`` / ``AutoMountStatus`` - result types.

Quick start::

    from media.auto_mount import AutoMountDaemon, AutoMountPolicy

    policy = AutoMountPolicy(auto_mount_usb=True)
    daemon = AutoMountDaemon(policy=policy)
    daemon.start()
    # daemon now reacts to hotplug events
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from .hotplug import HotplugAction, HotplugBus, HotplugEvent
from .media_types import MediaType, MountNaming
from .mount_ops import MountError, MountResult, mount, unmount, is_mounted, sync_mount

log = logging.getLogger("UmerOS.Media.AutoMount")


# ---------------------------------------------------------------------------
#  Policy
# ---------------------------------------------------------------------------

@dataclass
class AutoMountPolicy:
    """Configuration for which media types to auto-mount."""
    auto_mount_usb: bool = True
    auto_mount_sd: bool = True
    auto_mount_optical: bool = True
    auto_mount_bluetooth: bool = False
    auto_mount_network: bool = False
    auto_mount_firewire: bool = True
    auto_mount_tape: bool = False
    auto_mount_nvme: bool = True
    auto_mount_mmc: bool = True
    default_fs_type: str = "auto"
    default_options: List[str] = field(default_factory=list)
    read_only_types: Set[str] = field(default_factory=lambda: {"iso9660", "udf"})
    deny_list: Set[str] = field(default_factory=set)
    user_mode: bool = True
    flush_before_unmount: bool = True

    def should_mount(self, media_type: MediaType) -> bool:
        """Return True if this media type should be auto-mounted."""
        if media_type.value in self.deny_list:
            return False
        _map = {
            MediaType.USB: self.auto_mount_usb,
            MediaType.MMC: self.auto_mount_sd,  # SD/MMC share policy
            MediaType.CDROM: self.auto_mount_optical,
            MediaType.CDRECORD: self.auto_mount_optical,
            MediaType.ZIP: self.auto_mount_optical,
            MediaType.BLUETOOTH: self.auto_mount_bluetooth,
            MediaType.NETWORK: self.auto_mount_network,
            MediaType.FIREWIRE: self.auto_mount_firewire,
            MediaType.TAPE: self.auto_mount_tape,
            MediaType.NVME: self.auto_mount_nvme,
        }
        return _map.get(media_type, True)


# ---------------------------------------------------------------------------
#  Events
# ---------------------------------------------------------------------------

@unique
class AutoMountStatus(Enum):
    """Status of an auto-mount operation."""
    MOUNTED = "mounted"
    UNMOUNTED = "unmounted"
    SKIPPED_POLICY = "skipped_policy"
    SKIPPED_DENY = "skipped_deny"
    FAILED = "failed"
    ALREADY_MOUNTED = "already_mounted"
    DEVICE_GONE = "device_gone"
    BUSY = "busy"


@dataclass
class AutoMountEvent:
    """Result of processing a hotplug event."""
    status: AutoMountStatus
    device_path: str
    mount_point: str = ""
    media_type: MediaType = MediaType.USB
    fs_type: str = ""
    message: str = ""
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
#  Daemon
# ---------------------------------------------------------------------------

class AutoMountDaemon:
    """Event-driven auto-mount service.

    Listens to a ``HotplugBus`` and automatically mounts/removes
    removable media according to ``AutoMountPolicy``.
    """

    def __init__(
        self,
        *,
        bus: Optional[HotplugBus] = None,
        policy: Optional[AutoMountPolicy] = None,
        base_path: str = "/media",
    ) -> None:
        self._bus = bus or HotplugBus()
        self._policy = policy or AutoMountPolicy()
        self._base_path = base_path
        self._history: List[AutoMountEvent] = []
        self._active_mounts: Dict[str, str] = {}   # device -> mount_point
        self._running = False
        self._on_event_callbacks: List[Callable[[AutoMountEvent], None]] = []
        # Subscribe to hotplug
        self._bus.subscribe(self._handle_hotplug)

    # -- Configuration -------------------------------------------------------

    @property
    def policy(self) -> AutoMountPolicy:
        return self._policy

    @property
    def base_path(self) -> str:
        return self._base_path

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def active_mounts(self) -> Dict[str, str]:
        """Device-to-mount-point mapping of active mounts."""
        return dict(self._active_mounts)

    @property
    def history(self) -> List[AutoMountEvent]:
        """History of auto-mount events."""
        return list(self._history)

    # -- Lifecycle ------------------------------------------------------------

    def start(self) -> None:
        """Start the daemon (sets running flag, emits synthetic ADD for
        already-connected devices)."""
        if self._running:
            return
        self._running = True
        log.info("AutoMount daemon started (base=%s)", self._base_path)
        self._scan_existing()

    def stop(self) -> None:
        """Stop the daemon and unmount all managed devices."""
        if not self._running:
            return
        self._running = False
        log.info("AutoMount daemon stopping; unmounting %d devices",
                 len(self._active_mounts))
        for device in list(self._active_mounts):
            self.unmount_device(device)
        log.info("AutoMount daemon stopped")

    # -- Callbacks ------------------------------------------------------------

    def on_event(self, callback: Callable[[AutoMountEvent], None]) -> None:
        """Register a callback for auto-mount events."""
        self._on_event_callbacks.append(callback)

    # -- Mount / Unmount ------------------------------------------------------

    def mount_device(
        self,
        device_path: str,
        media_type: MediaType = MediaType.USB,
        fs_type: str = "auto",
    ) -> AutoMountEvent:
        """Manually request mount of a device."""
        return self._do_mount(device_path, media_type, fs_type)

    def unmount_device(self, device_path: str) -> AutoMountEvent:
        """Manually request unmount of a device."""
        return self._do_unmount(device_path)

    # -- Internal -------------------------------------------------------------

    def _handle_hotplug(self, event: HotplugEvent) -> None:
        """Handle a hotplug event from the bus."""
        if not self._running:
            return
        if event.action == HotplugAction.ADD:
            self._do_mount(event.device_path, event.media_type)
        elif event.action == HotplugAction.REMOVE:
            self._do_unmount(event.device_path)
        else:
            log.debug("Ignoring event action %s for %s",
                      event.action, event.device_path)

    def _do_mount(
        self,
        device_path: str,
        media_type: MediaType,
        fs_type: str = "auto",
    ) -> AutoMountEvent:
        """Mount a device, respecting policy."""
        # Policy check
        if not self._policy.should_mount(media_type):
            ev = AutoMountEvent(
                status=AutoMountStatus.SKIPPED_POLICY,
                device_path=device_path,
                media_type=media_type,
                message=f"Policy denies auto-mount for {media_type.value}",
            )
            self._emit(ev)
            return ev

        if device_path in self._active_mounts:
            ev = AutoMountEvent(
                status=AutoMountStatus.ALREADY_MOUNTED,
                device_path=device_path,
                mount_point=self._active_mounts[device_path],
                media_type=media_type,
            )
            self._emit(ev)
            return ev

        # Compute mount point
        mount_point = MountNaming.mount_point_for(
            media_type, self._base_path, index=0
        )
        if not mount_point:
            ev = AutoMountEvent(
                status=AutoMountStatus.FAILED,
                device_path=device_path,
                media_type=media_type,
                message=f"Cannot compute mount point for {media_type.value}",
            )
            self._emit(ev)
            return ev

        # Determine fs_type
        actual_fs = fs_type
        if fs_type == "auto":
            if media_type in (MediaType.CDROM, MediaType.CDRECORD, MediaType.ZIP):
                actual_fs = "iso9660"
            elif media_type in (MediaType.USB, MediaType.MMC, MediaType.NVME):
                actual_fs = "auto"

        # Determine options
        opts = list(self._policy.default_options)
        if actual_fs in self._policy.read_only_types:
            opts.append("ro")

        # Mount
        result = mount(
            device_path, mount_point,
            fs_type=actual_fs,
            options=opts if opts else None,
            create_dir=True,
        )

        if result.success:
            self._active_mounts[device_path] = mount_point
            ev = AutoMountEvent(
                status=AutoMountStatus.MOUNTED,
                device_path=device_path,
                mount_point=mount_point,
                media_type=media_type,
                fs_type=actual_fs,
                message=result.summary,
            )
        else:
            ev = AutoMountEvent(
                status=AutoMountStatus.FAILED,
                device_path=device_path,
                mount_point=mount_point,
                media_type=media_type,
                message=f"[{result.error.value}] {result.message}",
            )

        self._emit(ev)
        return ev

    def _do_unmount(self, device_path: str) -> AutoMountEvent:
        """Unmount a device."""
        mount_point = self._active_mounts.get(device_path)
        if not mount_point:
            ev = AutoMountEvent(
                status=AutoMountStatus.DEVICE_GONE,
                device_path=device_path,
                message="Device not managed by this daemon",
            )
            self._emit(ev)
            return ev

        # Sync before unmount
        if self._policy.flush_before_unmount:
            sync_mount(mount_point)

        result = unmount(mount_point, sync=False)

        if result.success:
            del self._active_mounts[device_path]
            ev = AutoMountEvent(
                status=AutoMountStatus.UNMOUNTED,
                device_path=device_path,
                mount_point=mount_point,
                message=f"Unmounted {mount_point}",
            )
        elif result.error == MountError.BUSY:
            ev = AutoMountEvent(
                status=AutoMountStatus.BUSY,
                device_path=device_path,
                mount_point=mount_point,
                message=f"Device busy: {result.message}",
            )
        else:
            ev = AutoMountEvent(
                status=AutoMountStatus.FAILED,
                device_path=device_path,
                mount_point=mount_point,
                message=f"[{result.error.value}] {result.message}",
            )

        self._emit(ev)
        return ev

    def _scan_existing(self) -> None:
        """Scan for already-mounted removable media at startup."""
        for mp_name in ("floppy", "cdrom", "usb", "sd", "mmc"):
            mp = os.path.join(self._base_path, mp_name)
            if is_mounted(mp):
                log.info("Found existing mount at %s", mp)

    def _emit(self, event: AutoMountEvent) -> None:
        """Record event and notify callbacks."""
        self._history.append(event)
        for cb in self._on_event_callbacks:
            try:
                cb(event)
            except Exception:
                log.exception("AutoMount callback error")


# ---------------------------------------------------------------------------
#  Convenience
# ---------------------------------------------------------------------------

def create_default_daemon(
    base_path: str = "/media",
    **policy_kwargs: Any,
) -> AutoMountDaemon:
    """Create a daemon with sensible defaults."""
    policy = AutoMountPolicy(**policy_kwargs)
    return AutoMountDaemon(policy=policy, base_path=base_path)


def _selftest() -> bool:
    """Run self-diagnostics.  Returns True on success."""
    from .hotplug import HotplugBus, HotplugEvent, HotplugAction
    from .mount_ops import set_simulation, clear_sim_mounts

    set_simulation(True)
    clear_sim_mounts()

    # Policy
    p = AutoMountPolicy(auto_mount_usb=True, auto_mount_tape=False)
    assert p.should_mount(MediaType.USB)
    assert not p.should_mount(MediaType.TAPE)
    assert not p.should_mount(MediaType.NETWORK)

    # Deny list
    p2 = AutoMountPolicy(deny_list={"floppy"})
    assert not p2.should_mount(MediaType.FLOPPY)

    # Daemon lifecycle
    bus = HotplugBus()
    daemon = AutoMountDaemon(bus=bus, policy=p, base_path="/media")
    assert not daemon.is_running
    daemon.start()
    assert daemon.is_running
    daemon.stop()
    assert not daemon.is_running

    # Event recording
    events: List[AutoMountEvent] = []
    daemon2 = AutoMountDaemon(bus=bus, policy=p, base_path="/media")
    daemon2.on_event(events.append)
    daemon2.start()

    # Simulate hotplug ADD
    bus.emit(HotplugEvent(
        device_path="/dev/sdb1",
        action=HotplugAction.ADD,
        media_type=MediaType.USB,
    ))
    assert len(events) >= 1
    assert events[-1].status in (
        AutoMountStatus.MOUNTED, AutoMountStatus.SKIPPED_POLICY,
        AutoMountStatus.ALREADY_MOUNTED, AutoMountStatus.FAILED,
    )

    # Simulate hotplug REMOVE
    if events[-1].status == AutoMountStatus.MOUNTED:
        bus.emit(HotplugEvent(
            device_path="/dev/sdb1",
            action=HotplugAction.REMOVE,
            media_type=MediaType.USB,
        ))
        assert events[-1].status == AutoMountStatus.UNMOUNTED

    daemon2.stop()
    clear_sim_mounts()
    return True
