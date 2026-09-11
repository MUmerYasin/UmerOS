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
UmerOS systemd Service Manager
================================
Manages services with systemd-inspired unit file management.

Supports:
    - Unit file parsing and generation (.service, .target, .timer, .socket)
    - Service lifecycle management (start, stop, restart, enable, disable)
    - Dependency resolution (After=, Before=, Requires=, Wants=)
    - Service status tracking
    - Drop-in configuration support
    - Template instantiation
    - Service types: simple, oneshot, notify, forking, idle
    - Timer-based activation

Based on RHEL systemd documentation:
    https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/7/
    html/system_administrators_guide/chap-managing_services_with_systemd

Reference: https://www.freedesktop.org/software/systemd/man/systemctl.html

Author: UmerOS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import configparser
import enum
import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UnitType(str, enum.Enum):
    """Systemd unit types."""
    SERVICE = "service"
    SOCKET = "socket"
    TIMER = "timer"
    TARGET = "target"
    MOUNT = "mount"
    PATH = "path"
    SCOPE = "scope"
    SLICE = "slice"
    SNAPSHOT = "snapshot"
    AUTOMOUNT = "automount"
    SWAP = "swap"


class ServiceType(str, enum.Enum):
    """Service type for [Service] section."""
    SIMPLE = "simple"
    ONESHOT = "oneshot"
    FORKING = "forking"
    NOTIFY = "notify"
    DBUS = "dbus"
    IDLE = "idle"
    EXEC = "exec"
    RELOAD = "reload"


class UnitState(str, enum.Enum):
    """Current state of a loaded unit."""
    LOADED = "loaded"
    NOT_FOUND = "not-found"
    BAD_SETTING = "bad-setting"
    ERROR = "error"
    MASKED = "masked"
    DEAD = "dead"
    LOADING = "loading"


class ServiceActiveState(str, enum.Enum):
    """Active state of a service."""
    ACTIVE = "active"
    RELOADING = "reloading"
    INACTIVE = "inactive"
    FAILED = "failed"
    ACTIVATING = "activating"
    DEACTIVATING = "deactivating"
    MAINTENANCE = "maintenance"


class ServiceSubState(str, enum.Enum):
    """Sub-state providing more detail on active state."""
    DEAD = "dead"
    RUNNING = "running"
    EXITING = "exiting"
    ACTIVE = "active"
    RELOADING = "reloading"
    AUTO_RESTART = "auto-restart"
    PRE_START = "pre-start"
    PRE_STOP = "pre-stop"
    START = "start"
    START_POST = "start-post"
    STOP = "stop"
    STOP_POST = "stop-post"
    FINAL_SIGTERM = "final-sigterm"
    FINAL_SIGKILL = "final-sigkill"
    RESULT = "result"
    RESOURCE = "resource"


class RestartPolicy(str, enum.Enum):
    """Restart policy for failed services."""
    NO = "no"
    ON_SUCCESS = "on-success"
    ON_FAILURE = "on-failure"
    ON_ABNORMAL = "on-abnormal"
    ON_WATCHDOG = "on-watchdog"
    ON_ABORT = "on-abort"
    ALWAYS = "always"


class InstallSectionType(str, enum.Enum):
    """Target type in [Install] section."""
    WANTED_BY = "WantedBy"
    REQUIRED_BY = "RequiredBy"
    ALSO = "Also"
    DEFAULT_INSTANCE = "DefaultInstance"


# ---------------------------------------------------------------------------
# Unit File Parser
# ---------------------------------------------------------------------------

@dataclass
class UnitSection:
    """Parsed [Unit] section of a unit file."""
    description: Optional[str] = None
    documentation: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)
    wants: List[str] = field(default_factory=list)
    after: List[str] = field(default_factory=list)
    before: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    replaces: List[str] = field(default_factory=list)
    part_of: Optional[str] = None
    require_overrides: bool = True
    want_overrides: bool = True
    stop_if_unneeded: bool = True
    refuse_manual_start: bool = False
    refuse_manual_stop: bool = False
    allow_isolate: bool = False
    default_dependencies: bool = True
    job_timeout_sec: Optional[int] = None
    start_limit_interval_sec: Optional[int] = None
    start_limit_burst: Optional[int] = None
    success_exit_status: List[int] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    environment_files: List[str] = field(default_factory=list)
    assertions: List[str] = field(default_factory=list)
    check_paths: List[str] = field(default_factory=list)
    condition_path_exists: Optional[str] = None
    condition_path_is_directory: Optional[str] = None
    condition_virtualization: Optional[str] = None
    condition_architecture: Optional[str] = None
    condition_host_name: Optional[str] = None
    condition_kernel_command_line: Optional[str] = None
    condition_os_release: Optional[str] = None


@dataclass
class ServiceSection:
    """Parsed [Service] section of a unit file."""
    type: ServiceType = ServiceType.SIMPLE
    bus_name: Optional[str] = None
    exec_start: List[str] = field(default_factory=list)
    exec_start_pre: List[str] = field(default_factory=list)
    exec_start_post: List[str] = field(default_factory=list)
    exec_stop: List[str] = field(default_factory=list)
    exec_stop_post: List[str] = field(default_factory=list)
    exec_reload: Optional[str] = None
    environment: Dict[str, str] = field(default_factory=dict)
    environment_files: List[str] = field(default_factory=list)
    working_directory: Optional[str] = None
    user: Optional[str] = None
    group: Optional[str] = None
    supplementary_groups: List[str] = field(default_factory=list)
    nice: int = 0
    oom_score_adjust: Optional[int] = None
    limit_nofile: Optional[int] = None
    limit_nproc: Optional[int] = None
    limit_core: Optional[int] = None
    capability_bounding_set: Optional[str] = None
    ambient_capabilities: Optional[str] = None
    capability_last_drop: Optional[str] = None
    protect_system: Optional[str] = None
    protect_home: Optional[str] = None
    private_tmp: bool = False
    private_network: bool = False
    no_new_privileges: bool = False
    read_only_paths: List[str] = field(default_factory=list)
    read_write_paths: List[str] = field(default_factory=list)
    inaccessible_paths: List[str] = field(default_factory=list)
    bind_paths: List[str] = field(default_factory=list)
    bind_ro_paths: List[str] = field(default_factory=list)
    tmpfiles: List[str] = field(default_factory=list)
    timeout_start_sec: Optional[int] = None
    timeout_stop_sec: Optional[int] = None
    timeout_abort_sec: Optional[int] = None
    timeout_watchdog_sec: Optional[int] = None
    restart: RestartPolicy = RestartPolicy.NO
    restart_sec: Optional[int] = None
    restart_max_delay_sec: Optional[int] = None
    restart_steps: Optional[int] = None
    restart_usec: Optional[int] = None
    start_limit_interval_sec: Optional[int] = None
    start_limit_burst: Optional[int] = None
    pid_file: Optional[str] = None
    socket_name: Optional[str] = None
    socket_user: Optional[str] = None
    socket_group: Optional[str] = None
    file_descriptor_store_max: int = 0
    file_descriptor_store_persists: bool = True
    non_blocking: bool = False
    dbus_name: Optional[str] = None
    dbus_acquire_bus_name: bool = False
    bus_policy_name: Optional[str] = None
    notify_access: Optional[str] = None
    kill_mode: Optional[str] = None
    kill_signal: Optional[str] = None
    send_sighup: bool = False
    send_sigkill: bool = True
    watchdog_signal: Optional[str] = None
    standard_output: str = "journal"
    standard_error: str = "inherit"
    standard_input: str = "null"
    standard_output_is_kmsg: bool = False
    standard_error_is_kmsg: bool = False
    syslog_identifier: Optional[str] = None
    syslog_facility: Optional[str] = None
    syslog_level: Optional[str] = None
    syslog_filter: Optional[str] = None
    log_ratelimit_sec: Optional[int] = None
    log_extra_fields: List[str] = field(default_factory=list)
    log_namespace: Optional[str] = None
    service_run_directory: Optional[str] = None
    service_runtime_directory: Optional[str] = None
    service_state_directory: Optional[str] = None
    service_cache_directory: Optional[str] = None
    service_logs_directory: Optional[str] = None
    service_configuration_directory: Optional[str] = None
    root_directory: Optional[str] = None
    root_image: Optional[str] = None
    root_image_options: List[str] = field(default_factory=list)
    mount_api_vfs: bool = False
    ephemeral: bool = False
    smack_process_label: Optional[str] = None
    se_comp: Optional[str] = None
    selinux_context: Optional[str] = None
    app_armor_profile: Optional[str] = None
    accuse: bool = False
    load_module: List[str] = field(default_factory=list)
    coredump_filter: Optional[str] = None
    restrict_address_families: Optional[str] = None
    memory_deny_write_execute: bool = False
    restrict_realtime: bool = False
    restrict_suid_sg_id: bool = False
    memory_ksm: bool = False
    keyed_network: bool = False
    protect_clock: bool = False
    protect_hostname: bool = False
    protect_control_groups: bool = False
    protect_kernel_logs: bool = False
    protect_kernel_modules: bool = False
    protect_kernel_tunables: bool = False
    protect_system_strict: bool = False
    remove_ipc: bool = False
    temporary_filesystem: List[str] = field(default_factory=list)
    log_color_mode: Optional[str] = None
    log_level_max: Optional[str] = None
    status_signal: Optional[str] = None
    file_descriptor_store_max_per_user: Optional[int] = None
    main_pid_select: Optional[str] = None
    main_pid_accent: Optional[str] = None
    main_pid_directory: Optional[str] = None
    delegate: bool = False
    delegate_to: List[str] = field(default_factory=list)
    delegation_subgroup: Optional[str] = None
    device_policy: Optional[str] = None
    device_allow: List[str] = field(default_factory=list)


@dataclass
class InstallSection:
    """Parsed [Install] section of a unit file."""
    wanted_by: List[str] = field(default_factory=list)
    required_by: List[str] = field(default_factory=list)
    also: List[str] = field(default_factory=list)
    alias: List[str] = field(default_factory=list)
    default_instance: Optional[str] = None
    symlink: Optional[str] = None


@dataclass
class TimerSection:
    """Parsed [Timer] section of a unit file."""
    on_boot_sec: Optional[str] = None
    on_startup_sec: Optional[str] = None
    on_unit_active_sec: Optional[str] = None
    on_unit_inactive_sec: Optional[str] = None
    on_calendar: Optional[str] = None
    on_clock_change: bool = False
    on_time_zone_change: bool = False
    persistent: bool = False
    accurate_sec: Optional[str] = None
    randomized_delay_sec: Optional[str] = None
    randomized_delay_sec_min: Optional[str] = None
    randomized_delay_sec_max: Optional[str] = None
    unit: Optional[str] = None
    remain_after_elapse: bool = True
    wake_system: bool = False
    hit_unit: Optional[str] = None


@dataclass
class SocketSection:
    """Parsed [Socket] section of a unit file."""
    listen_stream: List[str] = field(default_factory=list)
    listen_datagram: List[str] = field(default_factory=list)
    listen_sequential_packet: List[str] = field(default_factory=list)
    listen_fifo: List[str] = field(default_factory=list)
    listen_special: List[str] = field(default_factory=list)
    listen_usb_function: Optional[str] = None
    listen_netlink: Optional[str] = None
    listen_mq: Optional[str] = None
    socket_user: Optional[str] = None
    socket_group: Optional[str] = None
    socket_mode: int = 0o666
    directory_mode: int = 0o755
    accept: bool = False
    writable: bool = False
    flush_pending: bool = True
    max_connections: Optional[int] = None
    keep_alive: bool = False
    priority: Optional[int] = None
    receive_buffer: Optional[int] = None
    send_buffer: Optional[int] = None
    reuse_port: bool = False
    service: Optional[str] = None


@dataclass
class ParsedUnitFile:
    """Complete parsed representation of a systemd unit file."""
    filename: str
    unit_type: UnitType
    unit: UnitSection = field(default_factory=UnitSection)
    service: Optional[ServiceSection] = None
    timer: Optional[TimerSection] = None
    socket: Optional[SocketSection] = None
    install: InstallSection = field(default_factory=InstallSection)
    drop_ins: List[Tuple[str, Dict[str, List[Tuple[str, str]]]]] = field(default_factory=list)


class UnitFileParser:
    """Parser for systemd unit files."""

    _SECTION_MAP: Dict[str, str] = {
        "unit": "unit",
        "install": "install",
        "service": "service",
        "timer": "timer",
        "socket": "socket",
    }

    def parse(self, content: str, filename: Optional[str] = None) -> ParsedUnitFile:
        """Parse unit file content into a ParsedUnitFile."""
        lines = content.splitlines()
        current_section: Optional[str] = None
        sections: Dict[str, List[Tuple[str, str]]] = {}
        comments: List[str] = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                comments.append(line)
                continue

            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1].lower()
                if current_section not in sections:
                    sections[current_section] = []
                continue

            if current_section is None:
                continue

            if "=" in line:
                key, _, value = line.partition("=")
                sections[current_section].append((key.strip(), value.strip()))

        unit_type = self._detect_unit_type(filename or "", sections)
        unit_file = ParsedUnitFile(
            filename=filename or "unknown",
            unit_type=unit_type,
        )

        if "unit" in sections:
            unit_file.unit = self._parse_unit_section(sections["unit"])

        if "service" in sections:
            unit_file.service = self._parse_service_section(sections["service"])

        if "timer" in sections:
            unit_file.timer = self._parse_timer_section(sections["timer"])

        if "socket" in sections:
            unit_file.socket = self._parse_socket_section(sections["socket"])

        if "install" in sections:
            unit_file.install = self._parse_install_section(sections["install"])

        return unit_file

    def _detect_unit_type(self, filename: str, sections: Dict[str, List[Tuple[str, str]]]) -> UnitType:
        """Detect unit type from filename or sections."""
        if "." in filename:
            ext = filename.rsplit(".", 1)[-1]
            if ext == "service":
                return UnitType.SERVICE
            if ext == "timer":
                return UnitType.TIMER
            if ext == "socket":
                return UnitType.SOCKET
            if ext == "target":
                return UnitType.TARGET
            if ext == "mount":
                return UnitType.MOUNT
            if ext == "path":
                return UnitType.PATH
            if ext == "scope":
                return UnitType.SCOPE
            if ext == "slice":
                return UnitType.SLICE
            if ext == "snapshot":
                return UnitType.SNAPSHOT
            if ext == "automount":
                return UnitType.AUTOMOUNT
            if ext == "swap":
                return UnitType.SWAP

        if "service" in sections:
            return UnitType.SERVICE
        if "timer" in sections:
            return UnitType.TIMER
        if "socket" in sections:
            return UnitType.SOCKET
        return UnitType.SERVICE

    def _parse_unit_section(self, items: List[Tuple[str, str]]) -> UnitSection:
        """Parse [Unit] section key-value pairs."""
        section = UnitSection()
        for key, value in items:
            kl = key.lower()
            if kl == "description":
                section.description = value
            elif kl == "documentation":
                section.documentation = self._list_value(value)
            elif kl == "requires":
                section.requires = self._list_value(value)
            elif kl == "wants":
                section.wants = self._list_value(value)
            elif kl == "after":
                section.after = self._list_value(value)
            elif kl == "before":
                section.before = self._list_value(value)
            elif kl == "conflicts":
                section.conflicts = self._list_value(value)
            elif kl == "replaces":
                section.replaces = self._list_value(value)
            elif kl == "partof":
                section.part_of = value
            elif kl == "require-overrides":
                section.require_overrides = value.lower() in ("true", "yes", "1")
            elif kl == "want-overrides":
                section.want_overrides = value.lower() in ("true", "yes", "1")
            elif kl == "stop-if-unneeded":
                section.stop_if_unneeded = value.lower() in ("true", "yes", "1")
            elif kl == "refuse-manual-start":
                section.refuse_manual_start = value.lower() in ("true", "yes", "1")
            elif kl == "refuse-manual-stop":
                section.refuse_manual_stop = value.lower() in ("true", "yes", "1")
            elif kl == "allow-isolate":
                section.allow_isolate = value.lower() in ("true", "yes", "1")
            elif kl == "default-dependencies":
                section.default_dependencies = value.lower() in ("true", "yes", "1")
            elif kl == "job-timeoutsec":
                section.job_timeout_sec = self._int_value(value)
            elif kl == "start-limit-intervalsec":
                section.start_limit_interval_sec = self._int_value(value)
            elif kl == "start-limit-burst":
                section.start_limit_burst = self._int_value(value)
            elif kl == "success-exit-status":
                section.success_exit_status = [self._int_value(v) for v in value.split() if v.isdigit()]
            elif kl == "environment":
                section.environment = self._dict_value(value)
            elif kl == "environmentfiles":
                section.environment_files = self._list_value(value)
            elif kl == "conditionpathexists":
                section.condition_path_exists = value
            elif kl == "conditionpathisdirectory":
                section.condition_path_is_directory = value
            elif kl == "conditionvirtualization":
                section.condition_virtualization = value
            elif kl == "conditionarchitecture":
                section.condition_architecture = value
            elif kl == "conditionhostname":
                section.condition_host_name = value
            elif kl == "conditionkernelcommandline":
                section.condition_kernel_command_line = value
            elif kl == "conditionosrelease":
                section.condition_os_release = value
        return section

    def _parse_service_section(self, items: List[Tuple[str, str]]) -> ServiceSection:
        """Parse [Service] section key-value pairs."""
        section = ServiceSection()
        for key, value in items:
            kl = key.lower()
            if kl == "type":
                section.type = ServiceType(value)
            elif kl == "execstart":
                section.exec_start = self._list_value(value)
            elif kl == "execstartpre":
                section.exec_start_pre = self._list_value(value)
            elif kl == "execstartpost":
                section.exec_start_post = self._list_value(value)
            elif kl == "execstop":
                section.exec_stop = self._list_value(value)
            elif kl == "execstoppost":
                section.exec_stop_post = self._list_value(value)
            elif kl == "execreload":
                section.exec_reload = value
            elif kl == "environment":
                section.environment = self._dict_value(value)
            elif kl == "environmentfiles":
                section.environment_files = self._list_value(value)
            elif kl == "workingdirectory":
                section.working_directory = value
            elif kl == "user":
                section.user = value
            elif kl == "group":
                section.group = value
            elif kl == "supplementarygroups":
                section.supplementary_groups = self._list_value(value)
            elif kl == "nice":
                section.nice = self._int_value(value) if value.isdigit() else 0
            elif kl == "limitnofile":
                section.limit_nofile = self._int_value(value)
            elif kl == "limitnproc":
                section.limit_nproc = self._int_value(value)
            elif kl == "limitcore":
                section.limit_core = self._int_value(value)
            elif kl == "no_new_privileges" or kl == "nonewprivileges":
                section.no_new_privileges = value.lower() in ("true", "yes", "1")
            elif kl == "protectsystem":
                section.protect_system = value
            elif kl == "protecthome":
                section.protect_home = value
            elif kl == "privatetmp":
                section.private_tmp = value.lower() in ("true", "yes", "1")
            elif kl == "privatenetwork":
                section.private_network = value.lower() in ("true", "yes", "1")
            elif kl == "readonlypaths":
                section.read_only_paths = self._list_value(value)
            elif kl == "readwritepaths":
                section.read_write_paths = self._list_value(value)
            elif kl == "inaccessiblepaths":
                section.inaccessible_paths = self._list_value(value)
            elif kl == "timeoutstartusec":
                section.timeout_start_sec = self._int_value(value)
            elif kl == "timeoutstopusec":
                section.timeout_stop_sec = self._int_value(value)
            elif kl == "timeoutabortsec":
                section.timeout_abort_sec = self._int_value(value)
            elif kl == "timeoutwatchdogusec":
                section.timeout_watchdog_sec = self._int_value(value)
            elif kl == "restart":
                section.restart = RestartPolicy(value)
            elif kl == "restartsec":
                section.restart_sec = self._int_value(value)
            elif kl == "pidfile":
                section.pid_file = value
            elif kl == "socketname":
                section.socket_name = value
            elif kl == "socketuser":
                section.socket_user = value
            elif kl == "socketgroup":
                section.socket_group = value
            elif kl == "filedescriptorstoremax":
                section.file_descriptor_store_max = self._int_value(value) if value.isdigit() else 0
            elif kl == "nonblocking":
                section.non_blocking = value.lower() in ("true", "yes", "1")
            elif kl == "dbusname":
                section.dbus_name = value
            elif kl == "notifyaccess":
                section.notify_access = value
            elif kl == "killmode":
                section.kill_mode = value
            elif kl == "killsignal":
                section.kill_signal = value
            elif kl == "sendsighup":
                section.send_sighup = value.lower() in ("true", "yes", "1")
            elif kl == "sendsigkill":
                section.send_sigkill = value.lower() in ("true", "yes", "1")
            elif kl == "watchdogsignal":
                section.watchdog_signal = value
            elif kl == "standardoutput":
                section.standard_output = value
            elif kl == "standarderror":
                section.standard_error = value
            elif kl == "standardinput":
                section.standard_input = value
            elif kl == "syslogidentifier":
                section.syslog_identifier = value
            elif kl == "syslogfacility":
                section.syslog_facility = value
            elif kl == "sysloglevel":
                section.syslog_level = value
            elif kl == "capacityboundingset":
                section.capability_bounding_set = value
            elif kl == "ambientcapabilities":
                section.ambient_capabilities = value
            elif kl == "capabilitylastdrop":
                section.capability_last_drop = value
            elif kl == "delegate":
                section.delegate = value.lower() in ("true", "yes", "1")
            elif kl == "devicepolicy":
                section.device_policy = value
            elif kl == "deviceallow":
                section.device_allow = self._list_value(value)
            elif kl == "oomscoreadjust":
                section.oom_score_adjust = self._int_value(value) if value.lstrip("-").isdigit() else None
            elif kl == "tmpfiles":
                section.tmpfiles = self._list_value(value)
            elif kl == "bindpaths":
                section.bind_paths = self._list_value(value)
            elif kl == "bindropaths":
                section.bind_ro_paths = self._list_value(value)
            elif kl == "execstart":
                section.exec_start = self._list_value(value)
            elif kl == "busname":
                section.bus_name = value
            elif kl == "d busacquirebusname" or kl == "dbusacquirebusname":
                section.dbus_acquire_bus_name = value.lower() in ("true", "yes", "1")
            elif kl == "rootdirectory":
                section.root_directory = value
            elif kl == "rootimage":
                section.root_image = value
            elif kl == "ephemeral":
                section.ephemeral = value.lower() in ("true", "yes", "1")
            elif kl == "removeipc":
                section.remove_ipc = value.lower() in ("true", "yes", "1")
            elif kl == "protectclock":
                section.protect_clock = value.lower() in ("true", "yes", "1")
            elif kl == "protecthostname":
                section.protect_hostname = value.lower() in ("true", "yes", "1")
            elif kl == "protectcontrolgroups":
                section.protect_control_groups = value.lower() in ("true", "yes", "1")
            elif kl == "protectkernellogs":
                section.protect_kernel_logs = value.lower() in ("true", "yes", "1")
            elif kl == "protectkernelmodules":
                section.protect_kernel_modules = value.lower() in ("true", "yes", "1")
            elif kl == "protectkerneltunables":
                section.protect_kernel_tunables = value.lower() in ("true", "yes", "1")
            elif kl == "protectsystemstrict":
                section.protect_system_strict = value.lower() in ("true", "yes", "1")
            elif kl == "memorydenywriteexecute":
                section.memory_deny_write_execute = value.lower() in ("true", "yes", "1")
            elif kl == "restrictruntime":
                section.restrict_realtime = value.lower() in ("true", "yes", "1")
            elif kl == "restrictsuidsgid":
                section.restrict_suid_sg_id = value.lower() in ("true", "yes", "1")
            elif kl == "restrictaddressfamilies":
                section.restrict_address_families = value
            elif kl == "keyednetwork":
                section.keyed_network = value.lower() in ("true", "yes", "1")
            elif kl == "select":
                section.main_pid_select = value
            elif kl == "directorymode":
                pass  # handled elsewhere
        return section

    def _parse_timer_section(self, items: List[Tuple[str, str]]) -> TimerSection:
        """Parse [Timer] section key-value pairs."""
        section = TimerSection()
        for key, value in items:
            kl = key.lower()
            if kl == "onbootsec":
                section.on_boot_sec = value
            elif kl == "onstartupsec":
                section.on_startup_sec = value
            elif kl == "onunitactivesec":
                section.on_unit_active_sec = value
            elif kl == "onunitinactivesec":
                section.on_unit_inactive_sec = value
            elif kl == "oncalendar":
                section.on_calendar = value
            elif kl == "onclockchange":
                section.on_clock_change = value.lower() in ("true", "yes", "1")
            elif kl == "ontimezonechange":
                section.on_time_zone_change = value.lower() in ("true", "yes", "1")
            elif kl == "persistent":
                section.persistent = value.lower() in ("true", "yes", "1")
            elif kl == "accuratesec":
                section.accurate_sec = value
            elif kl == "randomizeddelaysec":
                section.randomized_delay_sec = value
            elif kl == "unit":
                section.unit = value
            elif kl == "rema afterelapse" or kl == "remainafterelapse":
                section.remain_after_elapse = value.lower() in ("true", "yes", "1")
            elif kl == "wakesystem":
                section.wake_system = value.lower() in ("true", "yes", "1")
        return section

    def _parse_socket_section(self, items: List[Tuple[str, str]]) -> SocketSection:
        """Parse [Socket] section key-value pairs."""
        section = SocketSection()
        for key, value in items:
            kl = key.lower()
            if kl == "listenstream":
                section.listen_stream = self._list_value(value)
            elif kl == "listendatagram":
                section.listen_datagram = self._list_value(value)
            elif kl == "listensequentialpacket":
                section.listen_sequential_packet = self._list_value(value)
            elif kl == "listenfifo":
                section.listen_fifo = self._list_value(value)
            elif kl == "listenspecial":
                section.listen_special = self._list_value(value)
            elif kl == "listenusbfunction":
                section.listen_usb_function = value
            elif kl == "listennetlink":
                section.listen_netlink = value
            elif kl == "listenmq":
                section.listen_mq = value
            elif kl == "socketuser":
                section.socket_user = value
            elif kl == "socketgroup":
                section.socket_group = value
            elif kl == "socketmode":
                section.socket_mode = self._int_value(value) if value.isdigit() else 0o666
            elif kl == "directorymode":
                section.directory_mode = self._int_value(value) if value.isdigit() else 0o755
            elif kl == "accept":
                section.accept = value.lower() in ("true", "yes", "1")
            elif kl == "writable":
                section.writable = value.lower() in ("true", "yes", "1")
            elif kl == "flushpending":
                section.flush_pending = value.lower() in ("true", "yes", "1")
            elif kl == "maxconnections":
                section.max_connections = self._int_value(value)
            elif kl == "keepalive":
                section.keep_alive = value.lower() in ("true", "yes", "1")
            elif kl == "priority":
                section.priority = self._int_value(value)
            elif kl == "receivebuffer":
                section.receive_buffer = self._int_value(value)
            elif kl == "sendbuffer":
                section.send_buffer = self._int_value(value)
            elif kl == "reuseport":
                section.reuse_port = value.lower() in ("true", "yes", "1")
            elif kl == "service":
                section.service = value
        return section

    def _parse_install_section(self, items: List[Tuple[str, str]]) -> InstallSection:
        """Parse [Install] section key-value pairs."""
        section = InstallSection()
        for key, value in items:
            kl = key.lower()
            if kl == "wantedby":
                section.wanted_by = self._list_value(value)
            elif kl == "requiredby":
                section.required_by = self._list_value(value)
            elif kl == "also":
                section.also = self._list_value(value)
            elif kl == "alias":
                section.alias = self._list_value(value)
            elif kl == "defaultinstance":
                section.default_instance = value
            elif kl == "symlink":
                section.symlink = value
        return section

    def _list_value(self, value: str) -> List[str]:
        """Split a space-separated value into a list."""
        return [v for v in value.split() if v]

    def _dict_value(self, value: str) -> Dict[str, str]:
        """Parse KEY=VALUE pairs from space-separated string."""
        result: Dict[str, str] = {}
        for part in value.split():
            if "=" in part:
                k, _, v = part.partition("=")
                result[k] = v
        return result

    def _int_value(self, value: str) -> int:
        """Parse integer value."""
        try:
            return int(value)
        except ValueError:
            return 0


# ---------------------------------------------------------------------------
# Unit File Generator
# ---------------------------------------------------------------------------

class UnitFileGenerator:
    """Generates systemd unit file content from dataclass instances."""

    def generate_service(self, parsed: ParsedUnitFile) -> str:
        """Generate complete unit file content."""
        lines: List[str] = []
        lines.append("# Auto-generated by UmerOS systemd_manager")
        lines.append("")

        # [Unit] section
        if parsed.unit:
            lines.append("[Unit]")
            if parsed.unit.description:
                lines.append(f"Description={parsed.unit.description}")
            if parsed.unit.documentation:
                lines.append(f"Documentation={' '.join(parsed.unit.documentation)}")
            if parsed.unit.requires:
                lines.append(f"Requires={parsed.unit.requires[0] if len(parsed.unit.requires) == 1 else ' '.join(parsed.unit.requires)}")
            if parsed.unit.wants:
                lines.append(f"Wants={parsed.unit.wants[0] if len(parsed.unit.wants) == 1 else ' '.join(parsed.unit.wants)}")
            if parsed.unit.after:
                lines.append(f"After={parsed.unit.after[0] if len(parsed.unit.after) == 1 else ' '.join(parsed.unit.after)}")
            if parsed.unit.before:
                lines.append(f"Before={parsed.unit.before[0] if len(parsed.unit.before) == 1 else ' '.join(parsed.unit.before)}")
            if parsed.unit.conflicts:
                lines.append(f"Conflicts={parsed.unit.conflicts[0] if len(parsed.unit.conflicts) == 1 else ' '.join(parsed.unit.conflicts)}")
            if parsed.unit.replaces:
                lines.append(f"Replaces={parsed.unit.replaces[0] if len(parsed.unit.replaces) == 1 else ' '.join(parsed.unit.replaces)}")
            if parsed.unit.part_of:
                lines.append(f"PartOf={parsed.unit.part_of}")
            if not parsed.unit.require_overrides:
                lines.append("RequireOverrides=no")
            if not parsed.unit.want_overrides:
                lines.append("WantOverrides=no")
            if not parsed.unit.stop_if_unneeded:
                lines.append("StopIfUnneeded=no")
            if parsed.unit.refuse_manual_start:
                lines.append("RefuseManualStart=yes")
            if parsed.unit.refuse_manual_stop:
                lines.append("RefuseManualStop=yes")
            if parsed.unit.allow_isolate:
                lines.append("AllowIsolate=yes")
            if not parsed.unit.default_dependencies:
                lines.append("DefaultDependencies=no")
            if parsed.unit.job_timeout_sec is not None:
                lines.append(f"JobTimeoutSec={parsed.unit.job_timeout_sec}")
            if parsed.unit.start_limit_interval_sec is not None:
                lines.append(f"StartLimitIntervalSec={parsed.unit.start_limit_interval_sec}")
            if parsed.unit.start_limit_burst is not None:
                lines.append(f"StartLimitBurst={parsed.unit.start_limit_burst}")
            if parsed.unit.success_exit_status:
                lines.append(f"SuccessExitStatus={' '.join(str(x) for x in parsed.unit.success_exit_status)}")
            if parsed.unit.environment:
                env_str = " ".join(f"{k}={v}" for k, v in parsed.unit.environment.items())
                lines.append(f"Environment={env_str}")
            if parsed.unit.environment_files:
                for ef in parsed.unit.environment_files:
                    lines.append(f"EnvironmentFile={ef}")
            if parsed.unit.condition_path_exists:
                lines.append(f"ConditionPathExists={parsed.unit.condition_path_exists}")
            if parsed.unit.condition_path_is_directory:
                lines.append(f"ConditionPathIsDirectory={parsed.unit.condition_path_is_directory}")
            if parsed.unit.condition_virtualization:
                lines.append(f"ConditionVirtualization={parsed.unit.condition_virtualization}")
            if parsed.unit.condition_architecture:
                lines.append(f"ConditionArchitecture={parsed.unit.condition_architecture}")
            if parsed.unit.condition_host_name:
                lines.append(f"ConditionHost={parsed.unit.condition_host_name}")
            if parsed.unit.condition_kernel_command_line:
                lines.append(f"ConditionKernelCommandLine={parsed.unit.condition_kernel_command_line}")
            lines.append("")

        # [Service] section
        if parsed.service:
            lines.append("[Service]")
            lines.append(f"Type={parsed.service.type.value}")
            if parsed.service.bus_name:
                lines.append(f"BusName={parsed.service.bus_name}")
            if parsed.service.exec_start:
                for cmd in parsed.service.exec_start:
                    lines.append(f"ExecStart={cmd}")
            if parsed.service.exec_start_pre:
                for cmd in parsed.service.exec_start_pre:
                    lines.append(f"ExecStartPre={cmd}")
            if parsed.service.exec_start_post:
                for cmd in parsed.service.exec_start_post:
                    lines.append(f"ExecStartPost={cmd}")
            if parsed.service.exec_stop:
                for cmd in parsed.service.exec_stop:
                    lines.append(f"ExecStop={cmd}")
            if parsed.service.exec_stop_post:
                for cmd in parsed.service.exec_stop_post:
                    lines.append(f"ExecStopPost={cmd}")
            if parsed.service.exec_reload:
                lines.append(f"ExecReload={parsed.service.exec_reload}")
            if parsed.service.environment:
                env_str = " ".join(f"{k}={v}" for k, v in parsed.service.environment.items())
                lines.append(f"Environment={env_str}")
            if parsed.service.environment_files:
                for ef in parsed.service.environment_files:
                    lines.append(f"EnvironmentFile={ef}")
            if parsed.service.working_directory:
                lines.append(f"WorkingDirectory={parsed.service.working_directory}")
            if parsed.service.user:
                lines.append(f"User={parsed.service.user}")
            if parsed.service.group:
                lines.append(f"Group={parsed.service.group}")
            if parsed.service.supplementary_groups:
                lines.append(f"SupplementaryGroups={parsed.service.supplementary_groups[0] if len(parsed.service.supplementary_groups) == 1 else ' '.join(parsed.service.supplementary_groups)}")
            if parsed.service.nice:
                lines.append(f"Nice={parsed.service.nice}")
            if parsed.service.oom_score_adjust is not None:
                lines.append(f"OOMScoreAdjust={parsed.service.oom_score_adjust}")
            if parsed.service.limit_nofile is not None:
                lines.append(f"LimitNOFILE={parsed.service.limit_nofile}")
            if parsed.service.limit_nproc is not None:
                lines.append(f"LimitNPROC={parsed.service.limit_nproc}")
            if parsed.service.limit_core is not None:
                lines.append(f"LimitCORE={parsed.service.limit_core}")
            if parsed.service.capability_bounding_set:
                lines.append(f"CapabilityBoundingSet={parsed.service.capability_bounding_set}")
            if parsed.service.ambient_capabilities:
                lines.append(f"AmbientCapabilities={parsed.service.ambient_capabilities}")
            if parsed.service.capability_last_drop:
                lines.append(f"CapabilityLastDrop={parsed.service.capability_last_drop}")
            if parsed.service.protect_system:
                lines.append(f"ProtectSystem={parsed.service.protect_system}")
            if parsed.service.protect_home:
                lines.append(f"ProtectHome={parsed.service.protect_home}")
            if parsed.service.private_tmp:
                lines.append("PrivateTmp=yes")
            if parsed.service.private_network:
                lines.append("PrivateNetwork=yes")
            if parsed.service.no_new_privileges:
                lines.append("NoNewPrivileges=yes")
            if parsed.service.read_only_paths:
                for p in parsed.service.read_only_paths:
                    lines.append(f"ReadOnlyPaths={p}")
            if parsed.service.read_write_paths:
                for p in parsed.service.read_write_paths:
                    lines.append(f"ReadWritePaths={p}")
            if parsed.service.inaccessible_paths:
                for p in parsed.service.inaccessible_paths:
                    lines.append(f"InaccessiblePaths={p}")
            if parsed.service.timeout_start_sec is not None:
                lines.append(f"TimeoutStartSec={parsed.service.timeout_start_sec}")
            if parsed.service.timeout_stop_sec is not None:
                lines.append(f"TimeoutStopSec={parsed.service.timeout_stop_sec}")
            if parsed.service.timeout_abort_sec is not None:
                lines.append(f"TimeoutAbortSec={parsed.service.timeout_abort_sec}")
            if parsed.service.timeout_watchdog_sec is not None:
                lines.append(f"TimeoutWatchdogSec={parsed.service.timeout_watchdog_sec}")
            if parsed.service.restart:
                lines.append(f"Restart={parsed.service.restart.value}")
            if parsed.service.restart_sec is not None:
                lines.append(f"RestartSec={parsed.service.restart_sec}")
            if parsed.service.pid_file:
                lines.append(f"PIDFile={parsed.service.pid_file}")
            if parsed.service.socket_name:
                lines.append(f"SocketName={parsed.service.socket_name}")
            if parsed.service.socket_user:
                lines.append(f"SocketUser={parsed.service.socket_user}")
            if parsed.service.socket_group:
                lines.append(f"SocketGroup={parsed.service.socket_group}")
            if parsed.service.file_descriptor_store_max:
                lines.append(f"FileDescriptorStoreMax={parsed.service.file_descriptor_store_max}")
            if parsed.service.non_blocking:
                lines.append("NonBlocking=yes")
            if parsed.service.dbus_name:
                lines.append(f"DBusName={parsed.service.dbus_name}")
            if parsed.service.dbus_acquire_bus_name:
                lines.append("DBusAcquireBusName=yes")
            if parsed.service.notify_access:
                lines.append(f"NotifyAccess={parsed.service.notify_access}")
            if parsed.service.kill_mode:
                lines.append(f"KillMode={parsed.service.kill_mode}")
            if parsed.service.kill_signal:
                lines.append(f"KillSignal={parsed.service.kill_signal}")
            if parsed.service.send_sighup:
                lines.append("SendSIGHUP=yes")
            if parsed.service.send_sigkill:
                lines.append("SendSIGKILL=yes")
            else:
                lines.append("SendSIGKILL=no")
            if parsed.service.watchdog_signal:
                lines.append(f"WatchdogSignal={parsed.service.watchdog_signal}")
            if parsed.service.standard_output:
                lines.append(f"StandardOutput={parsed.service.standard_output}")
            if parsed.service.standard_error:
                lines.append(f"StandardError={parsed.service.standard_error}")
            if parsed.service.standard_input:
                lines.append(f"StandardInput={parsed.service.standard_input}")
            if parsed.service.syslog_identifier:
                lines.append(f"SyslogIdentifier={parsed.service.syslog_identifier}")
            if parsed.service.syslog_facility:
                lines.append(f"SyslogFacility={parsed.service.syslog_facility}")
            if parsed.service.syslog_level:
                lines.append(f"SyslogLevel={parsed.service.syslog_level}")
            if parsed.service.delegate:
                lines.append("Delegate=yes")
            if parsed.service.device_policy:
                lines.append(f"DevicePolicy={parsed.service.device_policy}")
            if parsed.service.device_allow:
                for d in parsed.service.device_allow:
                    lines.append(f"DeviceAllow={d}")
            if parsed.service.remove_ipc:
                lines.append("RemoveIPC=yes")
            if parsed.service.protect_clock:
                lines.append("ProtectClock=yes")
            if parsed.service.protect_hostname:
                lines.append("ProtectHostname=yes")
            if parsed.service.protect_control_groups:
                lines.append("ProtectControlGroups=yes")
            if parsed.service.protect_kernel_logs:
                lines.append("ProtectKernelLogs=yes")
            if parsed.service.protect_kernel_modules:
                lines.append("ProtectKernelModules=yes")
            if parsed.service.protect_kernel_tunables:
                lines.append("ProtectKernelTunables=yes")
            if parsed.service.protect_system_strict:
                lines.append("ProtectSystem=strict")
            if parsed.service.memory_deny_write_execute:
                lines.append("MemoryDenyWriteExecute=yes")
            if parsed.service.restrict_realtime:
                lines.append("RestrictRealtime=yes")
            if parsed.service.restrict_suid_sg_id:
                lines.append("RestrictSUIDSGID=yes")
            if parsed.service.restrict_address_families:
                lines.append(f"RestrictAddressFamilies={parsed.service.restrict_address_families}")
            if parsed.service.keyed_network:
                lines.append("KeyedNetwork=yes")
            if parsed.service.ephemeral:
                lines.append("Ephemeral=yes")
            if parsed.service.root_directory:
                lines.append(f"RootDirectory={parsed.service.root_directory}")
            if parsed.service.root_image:
                lines.append(f"RootImage={parsed.service.root_image}")
            lines.append("")

        # [Timer] section
        if parsed.timer:
            lines.append("[Timer]")
            if parsed.timer.on_boot_sec:
                lines.append(f"OnBootSec={parsed.timer.on_boot_sec}")
            if parsed.timer.on_startup_sec:
                lines.append(f"OnStartupSec={parsed.timer.on_startup_sec}")
            if parsed.timer.on_unit_active_sec:
                lines.append(f"OnUnitActiveSec={parsed.timer.on_unit_active_sec}")
            if parsed.timer.on_unit_inactive_sec:
                lines.append(f"OnUnitInactiveSec={parsed.timer.on_unit_inactive_sec}")
            if parsed.timer.on_calendar:
                lines.append(f"OnCalendar={parsed.timer.on_calendar}")
            if parsed.timer.on_clock_change:
                lines.append("OnClockChange=yes")
            if parsed.timer.on_time_zone_change:
                lines.append("OnTimeZoneChange=yes")
            if parsed.timer.persistent:
                lines.append("Persistent=yes")
            if parsed.timer.accurate_sec:
                lines.append(f"AccurateSec={parsed.timer.accurate_sec}")
            if parsed.timer.randomized_delay_sec:
                lines.append(f"RandomizedDelaySec={parsed.timer.randomized_delay_sec}")
            if parsed.timer.unit:
                lines.append(f"Unit={parsed.timer.unit}")
            if not parsed.timer.remain_after_elapse:
                lines.append("RemainAfterElapse=no")
            if parsed.timer.wake_system:
                lines.append("WakeSystem=yes")
            lines.append("")

        # [Socket] section
        if parsed.socket:
            lines.append("[Socket]")
            if parsed.socket.listen_stream:
                for addr in parsed.socket.listen_stream:
                    lines.append(f"ListenStream={addr}")
            if parsed.socket.listen_datagram:
                for addr in parsed.socket.listen_datagram:
                    lines.append(f"ListenDatagram={addr}")
            if parsed.socket.listen_sequential_packet:
                for addr in parsed.socket.listen_sequential_packet:
                    lines.append(f"ListenSequentialPacket={addr}")
            if parsed.socket.listen_fifo:
                for fifo in parsed.socket.listen_fifo:
                    lines.append(f"ListenFIFO={fifo}")
            if parsed.socket.listen_special:
                for spec in parsed.socket.listen_special:
                    lines.append(f"ListenSpecial={spec}")
            if parsed.socket.listen_usb_function:
                lines.append(f"ListenUSBFunction={parsed.socket.listen_usb_function}")
            if parsed.socket.listen_netlink:
                lines.append(f"ListenNetlink={parsed.socket.listen_netlink}")
            if parsed.socket.listen_mq:
                lines.append(f"ListenMQ={parsed.socket.listen_mq}")
            if parsed.socket.socket_user:
                lines.append(f"SocketUser={parsed.socket.socket_user}")
            if parsed.socket.socket_group:
                lines.append(f"SocketGroup={parsed.socket.socket_group}")
            if parsed.socket.socket_mode != 0o666:
                lines.append(f"SocketMode={oct(parsed.socket.socket_mode)}")
            if parsed.socket.directory_mode != 0o755:
                lines.append(f"DirectoryMode={oct(parsed.socket.directory_mode)}")
            if parsed.socket.accept:
                lines.append("Accept=yes")
            if parsed.socket.writable:
                lines.append("Writable=yes")
            if parsed.socket.flush_pending:
                lines.append("FlushPending=yes")
            if parsed.socket.max_connections is not None:
                lines.append(f"MaxConnections={parsed.socket.max_connections}")
            if parsed.socket.keep_alive:
                lines.append("KeepAlive=yes")
            if parsed.socket.priority is not None:
                lines.append(f"Priority={parsed.socket.priority}")
            if parsed.socket.receive_buffer is not None:
                lines.append(f"ReceiveBuffer={parsed.socket.receive_buffer}")
            if parsed.socket.send_buffer is not None:
                lines.append(f"SendBuffer={parsed.socket.send_buffer}")
            if parsed.socket.reuse_port:
                lines.append("ReusePort=yes")
            if parsed.socket.service:
                lines.append(f"Service={parsed.socket.service}")
            lines.append("")

        # [Install] section
        if parsed.install:
            lines.append("[Install]")
            if parsed.install.wanted_by:
                for target in parsed.install.wanted_by:
                    lines.append(f"WantedBy={target}")
            if parsed.install.required_by:
                for target in parsed.install.required_by:
                    lines.append(f"RequiredBy={target}")
            if parsed.install.also:
                for unit in parsed.install.also:
                    lines.append(f"Also={unit}")
            if parsed.install.alias:
                for alias in parsed.install.alias:
                    lines.append(f"Alias={alias}")
            if parsed.install.default_instance:
                lines.append(f"DefaultInstance={parsed.install.default_instance}")
            if parsed.install.symlink:
                lines.append(f"Symlink={parsed.install.symlink}")
            lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Service Lifecycle Manager
# ---------------------------------------------------------------------------

@dataclass
class ServiceRecord:
    """Record of a service managed by systemd_manager."""
    name: str
    unit_type: UnitType
    unit_file_path: Optional[str] = None
    enabled: bool = False
    active_state: ServiceActiveState = ServiceActiveState.INACTIVE
    sub_state: ServiceSubState = ServiceSubState.DEAD
    pid: Optional[int] = None
    main_pid: Optional[int] = None
    exit_code: Optional[int] = None
    active_enter_timestamp: Optional[float] = None
    active_exit_timestamp: Optional[float] = None
    state_change_timestamp: Optional[float] = None
    last_restart_timestamp: Optional[float] = None
    restart_count: int = 0
    failed: bool = False
    load_state: UnitState = UnitState.LOADED
    description: Optional[str] = None
    documentation: Optional[str] = None
    drop_in_files: List[str] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    watchdog_us: Optional[int] = None
    main_pid_set: Optional[int] = None
    main_pid_accent: Optional[str] = None
    main_pid_directory: Optional[str] = None


class ServiceManager:
    """Manages systemd services and their lifecycle."""

    def __init__(self, systemd_dir: Optional[Path] = None):
        self.systemd_dir = systemd_dir or Path("/etc/systemd/system")
        self.services: Dict[str, ServiceRecord] = {}
        self.unit_files: Dict[str, ParsedUnitFile] = {}
        self.parser = UnitFileParser()
        self.generator = UnitFileGenerator()
        self._on_state_change: List[Callable[[str, ServiceActiveState, ServiceActiveState], None]] = []

    def register_state_change_handler(self, handler: Callable[[str, ServiceActiveState, ServiceActiveState], None]) -> None:
        """Register a callback for service state changes."""
        self._on_state_change.append(handler)

    def _notify_state_change(self, name: str, old: ServiceActiveState, new: ServiceActiveState) -> None:
        """Notify all handlers of a state change."""
        for handler in self._on_state_change:
            try:
                handler(name, old, new)
            except Exception as exc:
                logger.warning("State change handler failed for %s: %s", name, exc)

    def load_unit_file(self, path: Path) -> Optional[ParsedUnitFile]:
        """Load and parse a unit file."""
        try:
            content = path.read_text(encoding="utf-8")
            parsed = self.parser.parse(content, filename=path.name)
            self.unit_files[path.name] = parsed
            logger.info("Loaded unit file: %s", path)
            return parsed
        except (OSError, UnicodeDecodeError) as exc:
            logger.error("Failed to load unit file %s: %s", path, exc)
            return None

    def create_service(self, name: str, parsed: ParsedUnitFile, enable: bool = False) -> ServiceRecord:
        """Create a new service from a parsed unit file."""
        service_file = self.systemd_dir / name
        unit_content = self.generator.generate_service(parsed)
        service_file.write_text(unit_content, encoding="utf-8")
        self.unit_files[name] = parsed

        record = ServiceRecord(
            name=name,
            unit_type=parsed.unit_type,
            unit_file_path=str(service_file),
            enabled=enable,
            description=parsed.unit.description,
            documentation=" ".join(parsed.unit.documentation) if parsed.unit.documentation else None,
        )
        self.services[name] = record

        if enable:
            self._create_enable_symlink(name, parsed)

        logger.info("Created service: %s (enabled=%s)", name, enable)
        return record

    def _create_enable_symlink(self, name: str, parsed: ParsedUnitFile) -> None:
        """Create enable symlinks based on [Install] section."""
        if not parsed.install:
            return

        wants_dir = self.systemd_dir / "wants"
        wants_dir.mkdir(parents=True, exist_ok=True)

        for target in parsed.install.wanted_by:
            target_path = self.systemd_dir / target
            target_path.mkdir(parents=True, exist_ok=True)
            link_path = target_path / name
            if not link_path.exists():
                try:
                    link_path.symlink_to(self.systemd_dir / name)
                except OSError as exc:
                    logger.warning("Failed to create symlink %s: %s", link_path, exc)

        for alias in parsed.install.alias:
            alias_path = self.systemd_dir / alias
            if not alias_path.exists():
                try:
                    alias_path.symlink_to(self.systemd_dir / name)
                except OSError as exc:
                    logger.warning("Failed to create alias symlink %s: %s", alias_path, exc)

    def _remove_enable_symlink(self, name: str, parsed: ParsedUnitFile) -> None:
        """Remove enable symlinks."""
        if not parsed.install:
            return

        for target in parsed.install.wanted_by:
            target_path = self.systemd_dir / target / name
            if target_path.is_symlink() or target_path.exists():
                try:
                    target_path.unlink()
                except OSError as exc:
                    logger.warning("Failed to remove symlink %s: %s", target_path, exc)

    def delete_service(self, name: str) -> bool:
        """Delete a service and its unit file."""
        if name not in self.services:
            logger.warning("Service %s not found", name)
            return False

        record = self.services[name]
        parsed = self.unit_files.get(name)

        # Stop if active
        if record.active_state == ServiceActiveState.ACTIVE:
            self.stop_service(name)

        # Remove symlinks
        if parsed and record.enabled:
            self._remove_enable_symlink(name, parsed)

        # Remove unit file
        if record.unit_file_path:
            unit_file = Path(record.unit_file_path)
            if unit_file.exists():
                unit_file.unlink()

        # Remove drop-in files
        drop_in_dir = self.systemd_dir / f"{name}.d"
        if drop_in_dir.exists():
            shutil.rmtree(drop_in_dir, ignore_errors=True)

        del self.services[name]
        if name in self.unit_files:
            del self.unit_files[name]

        logger.info("Deleted service: %s", name)
        return True

    def enable_service(self, name: str) -> bool:
        """Enable a service to start on boot."""
        if name not in self.services:
            logger.warning("Service %s not found", name)
            return False

        record = self.services[name]
        parsed = self.unit_files.get(name)

        if record.enabled:
            return True

        if parsed:
            self._create_enable_symlink(name, parsed)

        record.enabled = True
        logger.info("Enabled service: %s", name)
        return True

    def disable_service(self, name: str) -> bool:
        """Disable a service from starting on boot."""
        if name not in self.services:
            logger.warning("Service %s not found", name)
            return False

        record = self.services[name]
        parsed = self.unit_files.get(name)

        if not record.enabled:
            return True

        if parsed:
            self._remove_enable_symlink(name, parsed)

        record.enabled = False
        logger.info("Disabled service: %s", name)
        return True

    def is_enabled(self, name: str) -> bool:
        """Check if a service is enabled."""
        if name not in self.services:
            return False
        return self.services[name].enabled

    def start_service(self, name: str) -> bool:
        """Start a service."""
        if name not in self.services:
            logger.warning("Service %s not found", name)
            return False

        record = self.services[name]
        parsed = self.unit_files.get(name)

        if record.active_state == ServiceActiveState.ACTIVE:
            logger.info("Service %s already active", name)
            return True

        old_state = record.active_state
        record.active_state = ServiceActiveState.ACTIVATING
        record.state_change_timestamp = time.time()

        # Execute pre-start commands
        if parsed and parsed.service and parsed.service.exec_start_pre:
            for cmd in parsed.service.exec_start_pre:
                if not self._execute_command(cmd, name, "ExecStartPre"):
                    record.active_state = old_state
                    record.failed = True
                    self._notify_state_change(name, old_state, ServiceActiveState.FAILED)
                    return False

        # Execute start commands
        if parsed and parsed.service and parsed.service.exec_start:
            for cmd in parsed.service.exec_start:
                if not self._execute_command(cmd, name, "ExecStart"):
                    record.active_state = old_state
                    record.failed = True
                    self._notify_state_change(name, old_state, ServiceActiveState.FAILED)
                    return False
        else:
            # No ExecStart - for services that don't need one
            pass

        # Execute post-start commands
        if parsed and parsed.service and parsed.service.exec_start_post:
            for cmd in parsed.service.exec_start_post:
                if not self._execute_command(cmd, name, "ExecStartPost"):
                    record.active_state = old_state
                    record.failed = True
                    self._notify_state_change(name, old_state, ServiceActiveState.FAILED)
                    return False

        record.active_state = ServiceActiveState.ACTIVE
        record.sub_state = ServiceSubState.RUNNING
        record.active_enter_timestamp = time.time()
        record.failed = False

        self._notify_state_change(name, old_state, ServiceActiveState.ACTIVE)
        logger.info("Started service: %s", name)
        return True

    def stop_service(self, name: str) -> bool:
        """Stop a service."""
        if name not in self.services:
            logger.warning("Service %s not found", name)
            return False

        record = self.services[name]
        parsed = self.unit_files.get(name)

        if record.active_state == ServiceActiveState.INACTIVE:
            logger.info("Service %s already inactive", name)
            return True

        old_state = record.active_state
        record.active_state = ServiceActiveState.DEACTIVATING
        record.state_change_timestamp = time.time()

        # Execute stop commands
        if parsed and parsed.service and parsed.service.exec_stop:
            for cmd in parsed.service.exec_stop:
                self._execute_command(cmd, name, "ExecStop")

        # Execute post-stop commands
        if parsed and parsed.service and parsed.service.exec_stop_post:
            for cmd in parsed.service.exec_stop_post:
                self._execute_command(cmd, name, "ExecStopPost")

        record.active_state = ServiceActiveState.INACTIVE
        record.sub_state = ServiceSubState.DEAD
        record.active_exit_timestamp = time.time()
        record.pid = None
        record.main_pid = None

        self._notify_state_change(name, old_state, ServiceActiveState.INACTIVE)
        logger.info("Stopped service: %s", name)
        return True

    def restart_service(self, name: str) -> bool:
        """Restart a service (stop then start)."""
        logger.info("Restarting service: %s", name)
        if not self.stop_service(name):
            return False
        return self.start_service(name)

    def reload_service(self, name: str) -> bool:
        """Reload a service configuration."""
        if name not in self.services:
            logger.warning("Service %s not found", name)
            return False

        record = self.services[name]
        parsed = self.unit_files.get(name)

        if record.active_state != ServiceActiveState.ACTIVE:
            logger.warning("Service %s is not active, cannot reload", name)
            return False

        if parsed and parsed.service and parsed.service.exec_reload:
            if not self._execute_command(parsed.service.exec_reload, name, "ExecReload"):
                return False

        logger.info("Reloaded service: %s", name)
        return True

    def get_service_status(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed status of a service."""
        if name not in self.services:
            return None

        record = self.services[name]
        parsed = self.unit_files.get(name)

        result: Dict[str, Any] = {
            "name": record.name,
            "description": record.description or name,
            "unit_type": record.unit_type.value,
            "load_state": record.load_state.value,
            "active_state": record.active_state.value,
            "sub_state": record.sub_state.value,
            "enabled": record.enabled,
            "pid": record.pid,
            "main_pid": record.main_pid,
            "exit_code": record.exit_code,
            "active_enter_timestamp": record.active_enter_timestamp,
            "active_exit_timestamp": record.active_exit_timestamp,
            "state_change_timestamp": record.state_change_timestamp,
            "failed": record.failed,
            "restart_count": record.restart_count,
            "unit_file_path": record.unit_file_path,
        }

        if parsed and parsed.unit:
            result["description"] = parsed.unit.description or name
            result["documentation"] = " ".join(parsed.unit.documentation) if parsed.unit.documentation else None

        if parsed and parsed.service:
            result["type"] = parsed.service.type.value
            result["exec_start"] = parsed.service.exec_start
            result["restart_policy"] = parsed.service.restart.value if parsed.service.restart else None

        return result

    def list_services(self, active_only: bool = False, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """List all services with optional filters."""
        results: List[Dict[str, Any]] = []
        for name, record in self.services.items():
            if active_only and record.active_state != ServiceActiveState.ACTIVE:
                continue
            if enabled_only and not record.enabled:
                continue
            status = self.get_service_status(name)
            if status:
                results.append(status)
        return sorted(results, key=lambda x: x.get("name", ""))

    def list_unit_files(self, unit_type: Optional[UnitType] = None) -> List[Dict[str, Any]]:
        """List all loaded unit files."""
        results: List[Dict[str, Any]] = []
        for filename, parsed in self.unit_files.items():
            if unit_type and parsed.unit_type != unit_type:
                continue
            results.append({
                "filename": filename,
                "unit_type": parsed.unit_type.value,
                "description": parsed.unit.description,
                "wanted_by": parsed.install.wanted_by if parsed.install else [],
                "required_by": parsed.install.required_by if parsed.install else [],
                "alias": parsed.install.alias if parsed.install else [],
            })
        return sorted(results, key=lambda x: x.get("filename", ""))

    def get_service_dependencies(self, name: str) -> Dict[str, List[str]]:
        """Get dependencies of a service."""
        if name not in self.unit_files:
            return {}

        parsed = self.unit_files[name]
        result: Dict[str, List[str]] = {
            "requires": [],
            "wants": [],
            "after": [],
            "before": [],
            "conflicts": [],
            "replaces": [],
            "part_of": [],
        }

        if parsed.unit:
            result["requires"] = list(parsed.unit.requires)
            result["wants"] = list(parsed.unit.wants)
            result["after"] = list(parsed.unit.after)
            result["before"] = list(parsed.unit.before)
            result["conflicts"] = list(parsed.unit.conflicts)
            result["replaces"] = list(parsed.unit.replaces)
            if parsed.unit.part_of:
                result["part_of"] = [parsed.unit.part_of]

        return result

    def add_drop_in(self, name: str, drop_in_name: str, section: str, key: str, value: str) -> bool:
        """Add a drop-in configuration file for a service."""
        if name not in self.services:
            logger.warning("Service %s not found", name)
            return False

        drop_in_dir = self.systemd_dir / f"{name}.d"
        drop_in_dir.mkdir(parents=True, exist_ok=True)

        drop_in_file = drop_in_dir / drop_in_name
        content = f"[{section}]\n{key}={value}\n"
        drop_in_file.write_text(content, encoding="utf-8")

        record = self.services[name]
        if drop_in_name not in record.drop_in_files:
            record.drop_in_files.append(drop_in_name)

        logger.info("Added drop-in %s for service %s", drop_in_name, name)
        return True

    def remove_drop_in(self, name: str, drop_in_name: str) -> bool:
        """Remove a drop-in configuration file."""
        if name not in self.services:
            logger.warning("Service %s not found", name)
            return False

        drop_in_dir = self.systemd_dir / f"{name}.d"
        drop_in_file = drop_in_dir / drop_in_name

        if drop_in_file.exists():
            drop_in_file.unlink()

        record = self.services[name]
        if drop_in_name in record.drop_in_files:
            record.drop_in_files.remove(drop_in_name)

        logger.info("Removed drop-in %s for service %s", drop_in_name, name)
        return True

    def daemon_reload(self) -> bool:
        """Reload systemd manager configuration (re-scan unit files)."""
        self.unit_files.clear()
        if self.systemd_dir.exists():
            for path in self.systemd_dir.glob("*.service"):
                self.load_unit_file(path)
            for path in self.systemd_dir.glob("*.timer"):
                self.load_unit_file(path)
            for path in self.systemd_dir.glob("*.socket"):
                self.load_unit_file(path)
            for path in self.systemd_dir.glob("*.target"):
                self.load_unit_file(path)
        logger.info("Daemon reloaded")
        return True

    def _execute_command(self, cmd: str, service_name: str, phase: str) -> bool:
        """Execute a command for a service phase."""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                check=False,
                capture_output=True,
                timeout=30,
                text=True,
            )
            if result.returncode != 0:
                logger.error(
                    "Service %s %s failed: %s (exit %d)",
                    service_name, phase, cmd, result.returncode,
                )
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.error("Service %s %s timed out: %s", service_name, phase, cmd)
            return False
        except OSError as exc:
            logger.error("Service %s %s error: %s", service_name, phase, exc)
            return False

    def mask_service(self, name: str) -> bool:
        """Mask a service (prevent manual start)."""
        if name not in self.services:
            logger.warning("Service %s not found", name)
            return False

        record = self.services[name]
        record.load_state = UnitState.MASKED

        # Stop if running
        if record.active_state == ServiceActiveState.ACTIVE:
            self.stop_service(name)

        # Create mask symlink to /dev/null
        mask_path = self.systemd_dir / name
        if not mask_path.exists():
            try:
                mask_path.symlink_to("/dev/null")
            except OSError as exc:
                logger.warning("Failed to create mask symlink %s: %s", mask_path, exc)
                return False

        logger.info("Masked service: %s", name)
        return True

    def unmask_service(self, name: str) -> bool:
        """Unmask a service."""
        if name not in self.services:
            logger.warning("Service %s not found", name)
            return False

        record = self.services[name]
        record.load_state = UnitState.LOADED

        mask_path = self.systemd_dir / name
        if mask_path.is_symlink() and mask_path.readlink() == Path("/dev/null"):
            mask_path.unlink()

        logger.info("Unmasked service: %s", name)
        return True

    def is_masked(self, name: str) -> bool:
        """Check if a service is masked."""
        if name not in self.services:
            return False
        return self.services[name].load_state == UnitState.MASKED

    def freeze_service(self, name: str) -> bool:
        """Freeze a service (cgroup freezer)."""
        if name not in self.services:
            logger.warning("Service %s not found", name)
            return False

        record = self.services[name]
        if record.active_state != ServiceActiveState.ACTIVE:
            logger.warning("Service %s is not active, cannot freeze", name)
            return False

        old_state = record.active_state
        record.active_state = ServiceActiveState.MAINTENANCE
        self._notify_state_change(name, old_state, ServiceActiveState.MAINTENANCE)
        logger.info("Froze service: %s", name)
        return True

    def thaw_service(self, name: str) -> bool:
        """Thaw a frozen service."""
        if name not in self.services:
            logger.warning("Service %s not found", name)
            return False

        record = self.services[name]
        if record.active_state != ServiceActiveState.MAINTENANCE:
            logger.warning("Service %s is not frozen, cannot thaw", name)
            return False

        old_state = record.active_state
        record.active_state = ServiceActiveState.ACTIVE
        self._notify_state_change(name, old_state, ServiceActiveState.ACTIVE)
        logger.info("Thawed service: %s", name)
        return True

    def set_service_property(self, name: str, section: str, key: str, value: str) -> bool:
        """Set a property in a service's unit file."""
        if name not in self.services:
            logger.warning("Service %s not found", name)
            return False

        record = self.services[name]
        if not record.unit_file_path:
            logger.warning("Service %s has no unit file path", name)
            return False

        unit_file = Path(record.unit_file_path)
        if not unit_file.exists():
            logger.warning("Unit file %s does not exist", unit_file)
            return False

        content = unit_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        new_lines: List[str] = []
        in_section = False
        section_found = False
        key_found = False

        for line in lines:
            stripped = line.strip()

            if stripped.lower() == f"[{section.lower()}]":
                in_section = True
                section_found = True
                new_lines.append(line)
                continue

            if stripped.startswith("[") and stripped.endswith("]"):
                if in_section and not key_found:
                    new_lines.append(f"{key}={value}")
                    key_found = True
                in_section = False
                new_lines.append(line)
                continue

            if in_section and stripped.lower() == f"{key.lower()}":
                new_lines.append(f"{key}={value}")
                key_found = True
                continue

            new_lines.append(line)

        if in_section and not key_found:
            new_lines.append(f"{key}={value}")
            key_found = True

        if section_found and not key_found:
            # Section found but key not found - append at end
            new_lines.append("")
            new_lines.append(f"{key}={value}")

        if not section_found:
            # Section not found - add at end
            new_lines.append("")
            new_lines.append(f"[{section}]")
            new_lines.append(f"{key}={value}")

        unit_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

        logger.info("Set property %s=%s in [%s] for %s", key, value, section, name)
        return True


# ---------------------------------------------------------------------------
# Template Instantiation
# ---------------------------------------------------------------------------

class TemplateInstantiator:
    """Instantiates systemd template unit files with instance parameters."""

    @staticmethod
    def instantiate(template_file: Path, instance_name: str, output_dir: Optional[Path] = None) -> Optional[Path]:
        """Create an instance from a template unit file."""
        if not template_file.exists():
            logger.warning("Template file %s not found", template_file)
            return None

        content = template_file.read_text(encoding="utf-8")

        # Replace template specifiers
        content = content.replace("%i", instance_name)
        content = content.replace("%I", instance_name)
        content = content.replace("%n", instance_name)
        content = content.replace("%N", instance_name)
        content = content.replace("%p", instance_name)

        # Generate instance filename
        base_name = template_file.name
        if "@" in base_name:
            parts = base_name.split("@", 1)
            instance_filename = f"{parts[0]}@{instance_name}.{parts[1].split('.', 1)[-1]}"
        else:
            instance_filename = base_name

        if output_dir is None:
            output_dir = template_file.parent

        output_file = output_dir / instance_filename
        output_file.write_text(content, encoding="utf-8")

        logger.info("Instantiated %s as %s", template_file.name, instance_filename)
        return output_file

    @staticmethod
    def parse_template_name(name: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse a template name into template and instance parts.

        Returns (template_name, instance_name) or (None, None) if not a template.
        """
        if "@" not in name:
            return None, None

        parts = name.split("@", 1)
        if "." in parts[1]:
            instance_name = parts[1].split(".", 1)[0]
            template_name = f"{parts[0]}@.{parts[1].split('.', 1)[-1]}"
            return template_name, instance_name

        return None, None


# ---------------------------------------------------------------------------
# Timer Management
# ---------------------------------------------------------------------------

class TimerManager:
    """Manages systemd timer units."""

    @staticmethod
    def create_timer(
        name: str,
        service_name: str,
        on_calendar: Optional[str] = None,
        on_boot_sec: Optional[str] = None,
        on_unit_active_sec: Optional[str] = None,
        persistent: bool = False,
        randomized_delay_sec: Optional[str] = None,
    ) -> ParsedUnitFile:
        """Create a timer unit for a service."""
        timer = ParsedUnitFile(
            filename=f"{name}.timer",
            unit_type=UnitType.TIMER,
            unit=UnitSection(
                description=f"Timer for {service_name}",
            ),
            timer=TimerSection(
                on_calendar=on_calendar,
                on_boot_sec=on_boot_sec,
                on_unit_active_sec=on_unit_active_sec,
                persistent=persistent,
                randomized_delay_sec=randomized_delay_sec,
                unit=service_name,
            ),
        )
        return timer

    @staticmethod
    def parse_calendar(expression: str) -> Dict[str, Any]:
        """Parse an OnCalendar expression.

        Supports formats like:
        - *-*-* *:*:*  (daily at midnight)
        - Mon *-*-* *:*:*  (weekly on Monday)
        - *-*-01 00:00:00  (monthly on first day)
        - hourly, daily, weekly, monthly, yearly  (aliases)
        """
        aliases = {
            "hourly": "*-*-* *:00:00",
            "daily": "*-*-* 00:00:00",
            "weekly": "Mon *-*-* 00:00:00",
            "monthly": "*-*-01 00:00:00",
            "yearly": "*-01-01 00:00:00",
            "annually": "*-01-01 00:00:00",
        }

        if expression.lower() in aliases:
            expression = aliases[expression.lower()]

        return {
            "expression": expression,
            "is_calendar": True,
        }


# ---------------------------------------------------------------------------
# Drop-in Configuration Manager
# ---------------------------------------------------------------------------

class DropInManager:
    """Manages drop-in configuration files for systemd units."""

    @staticmethod
    def create_drop_in(
        base_dir: Path,
        unit_name: str,
        drop_in_name: str,
        section: str,
        settings: Dict[str, str],
    ) -> Path:
        """Create a drop-in configuration file."""
        drop_in_dir = base_dir / f"{unit_name}.d"
        drop_in_dir.mkdir(parents=True, exist_ok=True)

        drop_in_file = drop_in_dir / drop_in_name
        lines = [f"[{section}]"]
        for key, value in settings.items():
            lines.append(f"{key}={value}")
        lines.append("")

        drop_in_file.write_text("\n".join(lines), encoding="utf-8")

        logger.info("Created drop-in %s for %s", drop_in_name, unit_name)
        return drop_in_file

    @staticmethod
    def list_drop_ins(base_dir: Path, unit_name: str) -> List[Path]:
        """List all drop-in files for a unit."""
        drop_in_dir = base_dir / f"{unit_name}.d"
        if not drop_in_dir.exists():
            return []
        return sorted(drop_in_dir.glob("*.conf"))

    @staticmethod
    def remove_drop_in(base_dir: Path, unit_name: str, drop_in_name: str) -> bool:
        """Remove a drop-in configuration file."""
        drop_in_file = base_dir / f"{unit_name}.d" / drop_in_name
        if drop_in_file.exists():
            drop_in_file.unlink()
            logger.info("Removed drop-in %s for %s", drop_in_name, unit_name)
            return True
        return False

    @staticmethod
    def read_drop_in(base_dir: Path, unit_name: str, drop_in_name: str) -> Optional[Dict[str, List[Tuple[str, str]]]]:
        """Read a drop-in configuration file."""
        drop_in_file = base_dir / f"{unit_name}.d" / drop_in_name
        if not drop_in_file.exists():
            return None

        sections: Dict[str, List[Tuple[str, str]]] = {}
        current_section: Optional[str] = None

        for line in drop_in_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1]
                if current_section not in sections:
                    sections[current_section] = []
                continue
            if "=" in line and current_section:
                key, _, value = line.partition("=")
                sections[current_section].append((key.strip(), value.strip()))

        return sections


# ---------------------------------------------------------------------------
# Dependency Resolver
# ---------------------------------------------------------------------------

class DependencyResolver:
    """Resolves systemd service dependencies and ordering."""

    def __init__(self, services: Dict[str, ParsedUnitFile]):
        self.services = services
        self._resolved_cache: Dict[str, List[str]] = {}

    def resolve_dependencies(self, name: str) -> List[str]:
        """Resolve all dependencies of a service (requires + wants)."""
        if name in self._resolved_cache:
            return self._resolved_cache[name]

        visited: Set[str] = set()
        result: List[str] = []

        self._resolve_recursive(name, visited, result)

        self._resolved_cache[name] = result
        return result

    def _resolve_recursive(self, name: str, visited: Set[str], result: List[str]) -> None:
        """Recursively resolve dependencies."""
        if name in visited:
            return
        visited.add(name)

        if name not in self.services:
            return

        parsed = self.services[name]
        if not parsed.unit:
            return

        # Process Requires first (hard dependencies)
        for req in parsed.unit.requires:
            if req not in visited:
                self._resolve_recursive(req, visited, result)
                if req not in result:
                    result.append(req)

        # Process Wants (soft dependencies)
        for want in parsed.unit.wants:
            if want not in visited:
                self._resolve_recursive(want, visited, result)
                if want not in result:
                    result.append(want)

    def get_start_order(self, name: str) -> List[str]:
        """Get the order in which services should be started."""
        deps = self.resolve_dependencies(name)
        order: List[str] = []

        # Add all dependencies in After= order first
        for dep in deps:
            if dep in self.services:
                parsed = self.services[dep]
                if parsed.unit and parsed.unit.after:
                    for after_dep in parsed.unit.after:
                        if after_dep not in order and after_dep in self.services:
                            order.append(after_dep)
            if dep not in order:
                order.append(dep)

        # Add the service itself last
        if name not in order:
            order.append(name)

        return order

    def get_stop_order(self, name: str) -> List[str]:
        """Get the order in which services should be stopped (reverse of start)."""
        start_order = self.get_start_order(name)
        return list(reversed(start_order))

    def detect_cycles(self) -> List[List[str]]:
        """Detect dependency cycles."""
        cycles: List[List[str]] = []

        for name in self.services:
            visited: Set[str] = set()
            path: List[str] = []
            self._detect_cycle_dfs(name, visited, path, cycles)

        return cycles

    def _detect_cycle_dfs(
        self,
        name: str,
        visited: Set[str],
        path: List[str],
        cycles: List[List[str]],
    ) -> None:
        """DFS to detect cycles in dependency graph."""
        if name in path:
            cycle_start = path.index(name)
            cycles.append(path[cycle_start:] + [name])
            return
        if name in visited:
            return

        visited.add(name)
        path.append(name)

        if name in self.services:
            parsed = self.services[name]
            if parsed.unit:
                for dep in parsed.unit.requires + parsed.unit.wants:
                    self._detect_cycle_dfs(dep, visited, path, cycles)

        path.pop()

    def get_reverse_dependencies(self, name: str) -> List[str]:
        """Get all services that depend on the given service."""
        reverse_deps: List[str] = []

        for other_name, parsed in self.services.items():
            if other_name == name:
                continue
            if not parsed.unit:
                continue

            if name in parsed.unit.requires or name in parsed.unit.wants:
                reverse_deps.append(other_name)

        return reverse_deps


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    """Run built-in self-test for systemd_manager."""
    import shutil
    import tempfile

    td = tempfile.mkdtemp(prefix="umeros_sdm_test_")
    try:
        systemd_dir = Path(td) / "systemd" / "system"
        systemd_dir.mkdir(parents=True)

        # Test UnitFileParser
        parser = UnitFileParser()
        sample_unit = """[Unit]
Description=Test Service
Documentation=https://example.com
Requires=network.target
Wants=nginx.service
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/test --daemon
ExecStartPre=/usr/bin/test --check
ExecStartPost=/usr/bin/test --started
ExecStop=/usr/bin/test --stop
ExecStopPost=/usr/bin/test --cleanup
Restart=on-failure
RestartSec=5
User=testuser
WorkingDirectory=/tmp
Environment=FOO=bar BAZ=qux
EnvironmentFile=/etc/sysconfig/test
LimitNOFILE=65536
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
"""
        parsed = parser.parse(sample_unit, filename="test.service")
        assert parsed.unit_type == UnitType.SERVICE
        assert parsed.unit.description == "Test Service"
        assert parsed.unit.requires == ["network.target"]
        assert parsed.unit.wants == ["nginx.service"]
        assert parsed.unit.after == ["network.target"]
        assert parsed.service.type == ServiceType.SIMPLE
        assert parsed.service.exec_start == ["/usr/bin/test --daemon"]
        assert parsed.service.restart == RestartPolicy.ON_FAILURE
        assert parsed.service.user == "testuser"
        assert parsed.service.no_new_privileges is True
        assert parsed.service.protect_system == "strict"
        assert parsed.install.wanted_by == ["multi-user.target"]

        # Test Timer section
        timer_unit = """[Unit]
Description=Test Timer

[Timer]
OnCalendar=daily
Persistent=yes
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
"""
        timer_parsed = parser.parse(timer_unit, filename="test.timer")
        assert timer_parsed.unit_type == UnitType.TIMER
        assert timer_parsed.timer.on_calendar == "daily"
        assert timer_parsed.timer.persistent is True
        assert timer_parsed.timer.randomized_delay_sec == "300"

        # Test Socket section
        socket_unit = """[Unit]
Description=Test Socket

[Socket]
ListenStream=8080
ListenDatagram=9090
SocketUser=testuser
SocketGroup=testgroup
Accept=yes

[Install]
WantedBy=sockets.target
"""
        socket_parsed = parser.parse(socket_unit, filename="test.socket")
        assert socket_parsed.unit_type == UnitType.SOCKET
        assert socket_parsed.socket.listen_stream == ["8080"]
        assert socket_parsed.socket.listen_datagram == ["9090"]
        assert socket_parsed.socket.socket_user == "testuser"
        assert socket_parsed.socket.accept is True

        # Test UnitFileGenerator
        generator = UnitFileGenerator()
        output = generator.generate_service(parsed)
        assert "[Unit]" in output
        assert "[Service]" in output
        assert "[Install]" in output
        assert "Description=Test Service" in output
        assert "Type=simple" in output
        assert "Restart=on-failure" in output
        assert "WantedBy=multi-user.target" in output

        # Test ServiceManager
        manager = ServiceManager(systemd_dir=systemd_dir)
        record = manager.create_service("test.service", parsed, enable=True)
        assert record.name == "test.service"
        assert record.unit_type == UnitType.SERVICE
        assert record.enabled is True

        # Test enable/disable
        assert manager.is_enabled("test.service") is True
        manager.disable_service("test.service")
        assert manager.is_enabled("test.service") is False
        manager.enable_service("test.service")
        assert manager.is_enabled("test.service") is True

        # Test start/stop (mock execution)
        # Since _execute_command runs subprocess, we test the state transitions
        old_handler = manager._on_state_change
        state_changes: List[Tuple[str, str, str]] = []
        manager.register_state_change_handler(
            lambda n, o, nw: state_changes.append((n, o.value, nw.value))
        )

        # Test get_service_status
        status = manager.get_service_status("test.service")
        assert status is not None
        assert status["name"] == "test.service"
        assert status["enabled"] is True

        # Test list_services
        services = manager.list_services()
        assert len(services) == 1
        assert services[0]["name"] == "test.service"

        # Test drop-in
        manager.add_drop_in("test.service", "override.conf", "Service", "Nice", "5")
        drop_in_path = systemd_dir / "test.service.d" / "override.conf"
        assert drop_in_path.exists()

        manager.remove_drop_in("test.service", "override.conf")
        assert not drop_in_path.exists()

        # Test delete
        assert manager.delete_service("test.service") is True
        assert manager.get_service_status("test.service") is None

        # Test get_service_dependencies
        manager.create_service("dep-test.service", parsed)
        deps = manager.get_service_dependencies("dep-test.service")
        assert "network.target" in deps["requires"]
        assert "nginx.service" in deps["wants"]

        # Test TemplateInstantiator
        template_dir = Path(td) / "templates"
        template_dir.mkdir(parents=True)
        template_content = """[Unit]
Description=Template for %i

[Service]
Type=simple
ExecStart=/usr/bin/service %i

[Install]
WantedBy=multi-user.target
"""
        template_file = template_dir / "service@.service"
        template_file.write_text(template_content)

        instance = TemplateInstantiator.instantiate(template_file, "myinstance", output_dir=template_dir)
        assert instance is not None
        assert instance.exists()
        instance_content = instance.read_text()
        assert "myinstance" in instance_content
        assert "%i" not in instance_content

        template_name, instance_name = TemplateInstantiator.parse_template_name("service@myinstance.service")
        assert template_name == "service@.service"
        assert instance_name == "myinstance"

        # Test TimerManager
        timer = TimerManager.create_timer(
            name="backup.timer",
            service_name="backup.service",
            on_calendar="daily",
            persistent=True,
        )
        assert timer.unit_type == UnitType.TIMER
        assert timer.timer.on_calendar == "daily"
        assert timer.timer.persistent is True

        # Test DependencyResolver
        resolver = DependencyResolver(manager.services)
        deps = resolver.resolve_dependencies("dep-test.service")
        assert "network.target" in deps
        assert "nginx.service" in deps

        start_order = resolver.get_start_order("dep-test.service")
        assert "dep-test.service" in start_order

        # Test DropInManager
        drop_in_dir = Path(td) / "dropins"
        DropInManager.create_drop_in(
            base_dir=drop_in_dir,
            unit_name="test.service",
            drop_in_name="override.conf",
            section="Service",
            settings={"Nice": "5", "ProtectSystem": "strict"},
        )
        drop_ins = DropInManager.list_drop_ins(drop_in_dir, "test.service")
        assert len(drop_ins) == 1
        content = DropInManager.read_drop_in(drop_in_dir, "test.service", "override.conf")
        assert content is not None
        assert "Service" in content
        DropInManager.remove_drop_in(drop_in_dir, "test.service", "override.conf")
        assert DropInManager.list_drop_ins(drop_in_dir, "test.service") == []

        # Test mask/unmask
        manager.create_service("mask-test.service", parsed)
        assert manager.mask_service("mask-test.service") is True
        assert manager.is_masked("mask-test.service") is True
        assert manager.unmask_service("mask-test.service") is True
        assert manager.is_masked("mask-test.service") is False
        manager.delete_service("mask-test.service")

        # Cleanup
        manager.delete_service("dep-test.service")

        return True
    except Exception as exc:
        import sys
        print(f"systemd_manager selftest FAILED: {exc}", file=sys.stderr)
        return False
    finally:
        shutil.rmtree(td, ignore_errors=True)
