# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
UmerOS /media/network - Network Mount Operations
================================================

Mount and unmount network shares (SMB/CIFS, NFS, SSHFS, etc.)
under /media/network with proper option handling and error reporting.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .network_share import NetworkShare, ShareProtocol, ShareStatus, ShareCredentials

log = logging.getLogger("UmerOS.Media.Network.Mount")

# Simulation mode for testing without real network
_SIM_MODE = True
_SIM_MOUNTS: Dict[str, dict] = {}


def set_simulation(enabled: bool) -> None:
    global _SIM_MODE
    _SIM_MODE = enabled


def get_sim_mounts() -> Dict[str, dict]:
    return dict(_SIM_MOUNTS)


def clear_sim_mounts() -> None:
    _SIM_MOUNTS.clear()


@dataclass
class NetworkMountResult:
    """Result of a network mount/unmount operation."""
    success: bool
    mount_point: Optional[str] = None
    error: Optional[str] = None
    protocol: Optional[str] = None
    duration_ms: float = 0.0


def _sanitize_name(name: str) -> str:
    """Sanitize share name for use as directory name."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def mount_share(
    share: NetworkShare,
    media_root: str = "/media/network",
    simulation: bool = True,
) -> NetworkMountResult:
    """Mount a network share.

    In simulation mode, creates the mount point directory and tracks
    the mount in memory. In real mode, executes the appropriate
    mount command.
    """
    start = time.monotonic()
    try:
        mount_point = os.path.join(media_root, _sanitize_name(share.name))
        os.makedirs(mount_point, exist_ok=True)

        if simulation or _SIM_MODE:
            # Simulation: track mount in memory
            _SIM_MOUNTS[mount_point] = {
                "share": share.name,
                "protocol": share.protocol.value,
                "host": share.host,
                "path": share.path,
                "mounted_at": time.time(),
            }
            share.mount_point = mount_point
            share.status = ShareStatus.MOUNTED
            share.last_connected = time.time()
            duration = (time.monotonic() - start) * 1000
            log.info("Simulated mount: %s -> %s", share.uri, mount_point)
            return NetworkMountResult(
                success=True,
                mount_point=mount_point,
                protocol=share.protocol.value,
                duration_ms=duration,
            )

        # Real mount
        opts = share.credentials.to_mount_options(share.protocol) if share.credentials else []
        if share.read_only:
            opts.append("ro")

        cmd = ["mount", "-t", share.mount_type, share.uri, mount_point]
        if opts:
            cmd.extend(["-o", ",".join(opts)])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            share.mount_point = mount_point
            share.status = ShareStatus.MOUNTED
            share.last_connected = time.time()
            duration = (time.monotonic() - start) * 1000
            return NetworkMountResult(
                success=True,
                mount_point=mount_point,
                protocol=share.protocol.value,
                duration_ms=duration,
            )
        else:
            share.status = ShareStatus.ERROR
            share.error_message = result.stderr.strip()
            return NetworkMountResult(
                success=False,
                error=result.stderr.strip(),
                protocol=share.protocol.value,
            )

    except Exception as e:
        share.status = ShareStatus.ERROR
        share.error_message = str(e)
        return NetworkMountResult(
            success=False,
            error=str(e),
            protocol=share.protocol.value,
        )


def unmount_share(
    share: NetworkShare,
    force: bool = False,
    simulation: bool = True,
) -> NetworkMountResult:
    """Unmount a network share."""
    start = time.monotonic()
    mount_point = share.mount_point
    if not mount_point:
        return NetworkMountResult(success=False, error="Share not mounted")

    try:
        share.status = ShareStatus.UNMOUNTING

        if simulation or _SIM_MODE:
            _SIM_MOUNTS.pop(mount_point, None)
            share.mount_point = None
            share.status = ShareStatus.DISCONNECTED
            duration = (time.monotonic() - start) * 1000
            log.info("Simulated unmount: %s", mount_point)
            return NetworkMountResult(
                success=True,
                mount_point=mount_point,
                duration_ms=duration,
            )

        cmd = ["umount", mount_point]
        if force:
            cmd.insert(1, "-f")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            share.mount_point = None
            share.status = ShareStatus.DISCONNECTED
            duration = (time.monotonic() - start) * 1000
            return NetworkMountResult(
                success=True,
                mount_point=mount_point,
                duration_ms=duration,
            )
        else:
            share.status = ShareStatus.MOUNTED  # Revert status
            return NetworkMountResult(
                success=False,
                error=result.stderr.strip(),
            )

    except Exception as e:
        share.status = ShareStatus.MOUNTED  # Revert status
        return NetworkMountResult(success=False, error=str(e))


def is_share_mounted(mount_point: str, simulation: bool = True) -> bool:
    """Check if a mount point is currently mounted."""
    if simulation or _SIM_MODE:
        return mount_point in _SIM_MOUNTS
    try:
        with open("/proc/mounts", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == mount_point:
                    return True
        return False
    except Exception:
        return False


def list_mounted_shares(simulation: bool = True) -> List[dict]:
    """List all currently mounted network shares."""
    if simulation or _SIM_MODE:
        return [
            {"mount_point": mp, **info}
            for mp, info in _SIM_MOUNTS.items()
        ]
    # Real: parse /proc/mounts for network filesystems
    result = []
    try:
        with open("/proc/mounts", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3 and parts[2] in ("cifs", "nfs", "fuse.sshfs", "davfs2"):
                    result.append({
                        "device": parts[0],
                        "mount_point": parts[1],
                        "fs_type": parts[2],
                        "options": parts[3] if len(parts) > 3 else "",
                    })
    except Exception:
        pass
    return result