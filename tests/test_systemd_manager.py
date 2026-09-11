"""Tests for srv/systemd_manager.py — unit file parsing, service lifecycle, dependency resolution, templates, timers, drop-ins, mask/unmask/freeze/thaw."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from srv.systemd_manager import (
    DependencyResolver,
    DropInManager,
    ParsedUnitFile,
    RestartPolicy,
    ServiceActiveState,
    ServiceManager,
    ServiceRecord,
    ServiceSubState,
    ServiceType,
    TemplateInstantiator,
    TimerManager,
    UnitFileGenerator,
    UnitFileParser,
    UnitState,
    UnitType,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SERVICE = """\
[Unit]
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

SAMPLE_TIMER = """\
[Unit]
Description=Test Timer

[Timer]
OnCalendar=daily
Persistent=yes
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
"""

SAMPLE_SOCKET = """\
[Unit]
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


@pytest.fixture
def tmp_systemd(tmp_path):
    """Create a temporary systemd directory and return (systemd_dir, parser, parsed)."""
    systemd_dir = tmp_path / "systemd" / "system"
    systemd_dir.mkdir(parents=True)
    parser = UnitFileParser()
    parsed = parser.parse(SAMPLE_SERVICE, filename="test.service")
    return systemd_dir, parser, parsed


@pytest.fixture
def manager(tmp_systemd):
    """Return a ServiceManager with a temp dir and one parsed service."""
    systemd_dir, _, parsed = tmp_systemd
    mgr = ServiceManager(systemd_dir=systemd_dir)
    return mgr, parsed


# ---------------------------------------------------------------------------
# UnitFileParser
# ---------------------------------------------------------------------------

class TestUnitFileParser:
    def test_parse_service(self):
        parser = UnitFileParser()
        parsed = parser.parse(SAMPLE_SERVICE, filename="test.service")
        assert parsed.unit_type == UnitType.SERVICE
        assert parsed.unit.description == "Test Service"
        assert parsed.unit.requires == ["network.target"]
        assert parsed.unit.wants == ["nginx.service"]
        assert parsed.unit.after == ["network.target"]
        assert parsed.service.type == ServiceType.SIMPLE
        assert parsed.service.exec_start == ["/usr/bin/test --daemon"]
        assert parsed.service.exec_start_pre == ["/usr/bin/test --check"]
        assert parsed.service.exec_start_post == ["/usr/bin/test --started"]
        assert parsed.service.exec_stop == ["/usr/bin/test --stop"]
        assert parsed.service.exec_stop_post == ["/usr/bin/test --cleanup"]
        assert parsed.service.restart == RestartPolicy.ON_FAILURE
        assert parsed.service.user == "testuser"
        assert parsed.service.working_directory == "/tmp"
        assert parsed.service.limit_nofile == 65536
        assert parsed.service.no_new_privileges is True
        assert parsed.service.protect_system == "strict"
        assert parsed.service.protect_home is True
        assert parsed.service.private_tmp is True
        assert parsed.install.wanted_by == ["multi-user.target"]

    def test_parse_timer(self):
        parser = UnitFileParser()
        parsed = parser.parse(SAMPLE_TIMER, filename="test.timer")
        assert parsed.unit_type == UnitType.TIMER
        assert parsed.timer.on_calendar == "daily"
        assert parsed.timer.persistent is True
        assert parsed.timer.randomized_delay_sec == "300"

    def test_parse_socket(self):
        parser = UnitFileParser()
        parsed = parser.parse(SAMPLE_SOCKET, filename="test.socket")
        assert parsed.unit_type == UnitType.SOCKET
        assert parsed.socket.listen_stream == ["8080"]
        assert parsed.socket.listen_datagram == ["9090"]
        assert parsed.socket.socket_user == "testuser"
        assert parsed.socket.socket_group == "testgroup"
        assert parsed.socket.accept is True

    def test_empty_input(self):
        parser = UnitFileParser()
        parsed = parser.parse("", filename="empty.service")
        assert parsed.unit_type == UnitType.SERVICE
        assert parsed.unit.description == ""

    def test_comments_ignored(self):
        parser = UnitFileParser()
        content = "# This is a comment\n[Unit]\nDescription=With Comment\n"
        parsed = parser.parse(content, filename="comment.service")
        assert parsed.unit.description == "With Comment"

    def test_unknown_directives_ignored(self):
        parser = UnitFileParser()
        content = "[Service]\nUnknownThing=yes\nExecStart=/bin/true\n"
        parsed = parser.parse(content, filename="unknown.service")
        assert parsed.service.exec_start == ["/bin/true"]


# ---------------------------------------------------------------------------
# UnitFileGenerator
# ---------------------------------------------------------------------------

class TestUnitFileGenerator:
    def test_generate_service(self):
        parser = UnitFileParser()
        parsed = parser.parse(SAMPLE_SERVICE, filename="test.service")
        generator = UnitFileGenerator()
        output = generator.generate_service(parsed)
        assert "[Unit]" in output
        assert "[Service]" in output
        assert "[Install]" in output
        assert "Description=Test Service" in output
        assert "Type=simple" in output
        assert "Restart=on-failure" in output
        assert "WantedBy=multi-user.target" in output
        assert "ExecStart=/usr/bin/test --daemon" in output

    def test_generate_preserves_all_sections(self):
        parser = UnitFileParser()
        parsed = parser.parse(SAMPLE_SERVICE, filename="test.service")
        generator = UnitFileGenerator()
        output = generator.generate_service(parsed)
        # Check install section is present
        assert "WantedBy=multi-user.target" in output
        # Check unit section
        assert "Requires=network.target" in output


# ---------------------------------------------------------------------------
# ServiceManager — lifecycle
# ---------------------------------------------------------------------------

class TestServiceManagerLifecycle:
    def test_create_service(self, manager):
        mgr, parsed = manager
        record = mgr.create_service("test.service", parsed, enable=False)
        assert record.name == "test.service"
        assert record.unit_type == UnitType.SERVICE
        assert record.enabled is False
        assert record.load_state == UnitState.LOADED

    def test_create_and_enable(self, manager):
        mgr, parsed = manager
        record = mgr.create_service("test.service", parsed, enable=True)
        assert record.enabled is True
        assert mgr.is_enabled("test.service") is True
        # Wants directory should have symlink
        wants_dir = mgr.systemd_dir / "wants" / "multi-user.target"
        assert wants_dir.exists()

    def test_enable_disable(self, manager):
        mgr, parsed = manager
        mgr.create_service("test.service", parsed)
        assert mgr.is_enabled("test.service") is False
        mgr.enable_service("test.service")
        assert mgr.is_enabled("test.service") is True
        mgr.disable_service("test.service")
        assert mgr.is_enabled("test.service") is False

    def test_delete_service(self, manager):
        mgr, parsed = manager
        mgr.create_service("test.service", parsed)
        assert mgr.delete_service("test.service") is True
        assert mgr.get_service_status("test.service") is None

    def test_delete_nonexistent(self, manager):
        mgr, _ = manager
        assert mgr.delete_service("nope.service") is False

    def test_get_service_status(self, manager):
        mgr, parsed = manager
        mgr.create_service("test.service", parsed)
        status = mgr.get_service_status("test.service")
        assert status is not None
        assert status["name"] == "test.service"
        assert status["enabled"] is False
        assert status["active_state"] == "inactive"

    def test_list_services(self, manager):
        mgr, parsed = manager
        mgr.create_service("a.service", parsed)
        mgr.create_service("b.service", parsed)
        services = mgr.list_services()
        assert len(services) == 2
        assert services[0]["name"] == "a.service"
        assert services[1]["name"] == "b.service"

    def test_list_services_active_only(self, manager):
        mgr, parsed = manager
        mgr.create_service("a.service", parsed)
        active = mgr.list_services(active_only=True)
        assert len(active) == 0

    def test_list_services_enabled_only(self, manager):
        mgr, parsed = manager
        mgr.create_service("a.service", parsed, enable=True)
        mgr.create_service("b.service", parsed, enable=False)
        enabled = mgr.list_services(enabled_only=True)
        assert len(enabled) == 1
        assert enabled[0]["name"] == "a.service"

    def test_list_unit_files(self, manager):
        mgr, parsed = manager
        mgr.create_service("test.service", parsed)
        files = mgr.list_unit_files()
        assert len(files) == 1
        assert files[0]["filename"] == "test.service"

    def test_list_unit_files_by_type(self, manager):
        mgr, parsed = manager
        mgr.create_service("test.service", parsed)
        timer = TimerManager.create_timer("backup.timer", "backup.service", on_calendar="daily")
        mgr.unit_files["backup.timer"] = timer
        services = mgr.list_unit_files(unit_type=UnitType.SERVICE)
        assert len(services) == 1
        timers = mgr.list_unit_files(unit_type=UnitType.TIMER)
        assert len(timers) == 1


# ---------------------------------------------------------------------------
# ServiceManager — state transitions
# ---------------------------------------------------------------------------

class TestServiceManagerStateTransitions:
    def test_state_change_handler(self, manager):
        mgr, parsed = manager
        mgr.create_service("test.service", parsed)
        changes = []
        mgr.register_state_change_handler(lambda n, o, nw: changes.append((n, o, nw)))
        # Mask triggers state change notification indirectly
        mgr.mask_service("test.service")
        # The mask doesn't trigger a state change if not active, but let's verify mask set
        assert mgr.is_masked("test.service")

    def test_start_service_no_exec(self, manager):
        """Service with no ExecStart should still transition to ACTIVE."""
        mgr, _ = manager
        # Create a minimal parsed unit without ExecStart
        parsed = ParsedUnitFile(
            filename="minimal.service",
            unit_type=UnitType.SERVICE,
        )
        mgr.create_service("minimal.service", parsed)
        result = mgr.start_service("minimal.service")
        assert result is True
        status = mgr.get_service_status("minimal.service")
        assert status["active_state"] == "active"

    def test_stop_service(self, manager):
        mgr, _ = manager
        parsed = ParsedUnitFile(filename="noop.service", unit_type=UnitType.SERVICE)
        mgr.create_service("noop.service", parsed)
        mgr.start_service("noop.service")
        assert mgr.stop_service("noop.service") is True
        status = mgr.get_service_status("noop.service")
        assert status["active_state"] == "inactive"

    def test_restart_service(self, manager):
        mgr, _ = manager
        parsed = ParsedUnitFile(filename="restart.service", unit_type=UnitType.SERVICE)
        mgr.create_service("restart.service", parsed)
        mgr.start_service("restart.service")
        assert mgr.restart_service("restart.service") is True
        status = mgr.get_service_status("restart.service")
        assert status["active_state"] == "active"

    def test_reload_service_not_active(self, manager):
        mgr, parsed = manager
        mgr.create_service("test.service", parsed)
        assert mgr.reload_service("test.service") is False

    def test_reload_service_active_no_exec(self, manager):
        mgr, _ = manager
        parsed = ParsedUnitFile(filename="reload.service", unit_type=UnitType.SERVICE)
        mgr.create_service("reload.service", parsed)
        mgr.start_service("reload.service")
        # No ExecReload defined → should still succeed
        assert mgr.reload_service("reload.service") is True


# ---------------------------------------------------------------------------
# ServiceManager — mask / unmask / freeze / thaw
# ---------------------------------------------------------------------------

class TestMaskUnmaskFreezeThaw:
    def test_mask_service(self, manager):
        mgr, parsed = manager
        mgr.create_service("m.service", parsed)
        assert mgr.mask_service("m.service") is True
        assert mgr.is_masked("m.service") is True
        assert mgr.services["m.service"].load_state == UnitState.MASKED

    def test_unmask_service(self, manager):
        mgr, parsed = manager
        mgr.create_service("m.service", parsed)
        mgr.mask_service("m.service")
        assert mgr.unmask_service("m.service") is True
        assert mgr.is_masked("m.service") is False

    def test_mask_nonexistent(self, manager):
        mgr, _ = manager
        assert mgr.mask_service("nope.service") is False

    def test_unmask_nonexistent(self, manager):
        mgr, _ = manager
        assert mgr.unmask_service("nope.service") is False

    def test_freeze_service(self, manager):
        mgr, _ = manager
        parsed = ParsedUnitFile(filename="f.service", unit_type=UnitType.SERVICE)
        mgr.create_service("f.service", parsed)
        mgr.start_service("f.service")
        assert mgr.freeze_service("f.service") is True
        status = mgr.get_service_status("f.service")
        assert status["active_state"] == "maintenance"

    def test_freeze_nonexistent(self, manager):
        mgr, _ = manager
        assert mgr.freeze_service("nope.service") is False

    def test_freeze_inactive(self, manager):
        mgr, parsed = manager
        mgr.create_service("f.service", parsed)
        assert mgr.freeze_service("f.service") is False

    def test_thaw_service(self, manager):
        mgr, _ = manager
        parsed = ParsedUnitFile(filename="f.service", unit_type=UnitType.SERVICE)
        mgr.create_service("f.service", parsed)
        mgr.start_service("f.service")
        mgr.freeze_service("f.service")
        assert mgr.thaw_service("f.service") is True
        status = mgr.get_service_status("f.service")
        assert status["active_state"] == "active"

    def test_thaw_nonexistent(self, manager):
        mgr, _ = manager
        assert mgr.thaw_service("nope.service") is False

    def test_thaw_not_frozen(self, manager):
        mgr, _ = manager
        parsed = ParsedUnitFile(filename="f.service", unit_type=UnitType.SERVICE)
        mgr.create_service("f.service", parsed)
        mgr.start_service("f.service")
        assert mgr.thaw_service("f.service") is False


# ---------------------------------------------------------------------------
# ServiceManager — drop-ins
# ---------------------------------------------------------------------------

class TestDropIns:
    def test_add_drop_in(self, manager):
        mgr, parsed = manager
        mgr.create_service("test.service", parsed)
        assert mgr.add_drop_in("test.service", "override.conf", "Service", "Nice", "5") is True
        drop_path = mgr.systemd_dir / "test.service.d" / "override.conf"
        assert drop_path.exists()
        assert "Nice=5" in drop_path.read_text()
        assert "override.conf" in mgr.services["test.service"].drop_in_files

    def test_remove_drop_in(self, manager):
        mgr, parsed = manager
        mgr.create_service("test.service", parsed)
        mgr.add_drop_in("test.service", "override.conf", "Service", "Nice", "5")
        assert mgr.remove_drop_in("test.service", "override.conf") is True
        drop_path = mgr.systemd_dir / "test.service.d" / "override.conf"
        assert not drop_path.exists()
        assert "override.conf" not in mgr.services["test.service"].drop_in_files

    def test_add_drop_in_nonexistent(self, manager):
        mgr, _ = manager
        assert mgr.add_drop_in("nope.service", "x.conf", "Service", "A", "B") is False

    def test_remove_drop_in_nonexistent(self, manager):
        mgr, _ = manager
        assert mgr.remove_drop_in("nope.service", "x.conf") is False


# ---------------------------------------------------------------------------
# ServiceManager — daemon-reload
# ---------------------------------------------------------------------------

class TestDaemonReload:
    def test_daemon_reload(self, manager):
        mgr, parsed = manager
        # Write a unit file directly
        unit_file = mgr.systemd_dir / "reloaded.service"
        unit_file.write_text("[Unit]\nDescription=Reloaded\n\n[Service]\nType=oneshot\nExecStart=/bin/true\n")
        assert mgr.daemon_reload() is True
        assert "reloaded.service" in mgr.unit_files


# ---------------------------------------------------------------------------
# ServiceManager — set_service_property
# ---------------------------------------------------------------------------

class TestSetServiceProperty:
    def test_set_existing_property(self, manager):
        mgr, parsed = manager
        mgr.create_service("test.service", parsed)
        assert mgr.set_service_property("test.service", "Service", "User", "newuser") is True
        content = (mgr.systemd_dir / "test.service").read_text()
        assert "User=newuser" in content

    def test_set_new_property_in_existing_section(self, manager):
        mgr, parsed = manager
        mgr.create_service("test.service", parsed)
        assert mgr.set_service_property("test.service", "Service", "Nice", "10") is True
        content = (mgr.systemd_dir / "test.service").read_text()
        assert "Nice=10" in content

    def test_set_nonexistent_service(self, manager):
        mgr, _ = manager
        assert mgr.set_service_property("nope.service", "Service", "A", "B") is False


# ---------------------------------------------------------------------------
# ServiceManager — get_service_dependencies
# ---------------------------------------------------------------------------

class TestServiceDependencies:
    def test_get_dependencies(self, manager):
        mgr, parsed = manager
        mgr.create_service("test.service", parsed)
        deps = mgr.get_service_dependencies("test.service")
        assert "network.target" in deps["requires"]
        assert "nginx.service" in deps["wants"]
        assert "network.target" in deps["after"]

    def test_get_dependencies_nonexistent(self, manager):
        mgr, _ = manager
        deps = mgr.get_service_dependencies("nope.service")
        assert deps == {}


# ---------------------------------------------------------------------------
# TemplateInstantiator
# ---------------------------------------------------------------------------

class TestTemplateInstantiator:
    def test_instantiate(self, tmp_path):
        tpl_dir = tmp_path / "templates"
        tpl_dir.mkdir()
        content = "[Unit]\nDescription=Template for %i\n\n[Service]\nType=simple\nExecStart=/usr/bin/service %i\n\n[Install]\nWantedBy=multi-user.target\n"
        tpl_file = tpl_dir / "service@.service"
        tpl_file.write_text(content)

        instance = TemplateInstantiator.instantiate(tpl_file, "myinstance", output_dir=tpl_dir)
        assert instance is not None
        assert instance.exists()
        assert "myinstance" in instance.read_text()
        assert "%i" not in instance.read_text()
        assert instance.name == "service@myinstance.service"

    def test_instantiate_missing_file(self, tmp_path):
        result = TemplateInstantiator.instantiate(tmp_path / "missing.service", "x")
        assert result is None

    def test_parse_template_name(self):
        name, inst = TemplateInstantiator.parse_template_name("service@myinstance.service")
        assert name == "service@.service"
        assert inst == "myinstance"

    def test_parse_template_name_no_at(self):
        name, inst = TemplateInstantiator.parse_template_name("plain.service")
        assert name is None
        assert inst is None

    def test_instantiate_specifier_percent_I(self, tmp_path):
        tpl_dir = tmp_path / "templates"
        tpl_dir.mkdir()
        content = "[Service]\nExecStart=/usr/bin/%I\n"
        tpl_file = tpl_dir / "svc@.service"
        tpl_file.write_text(content)
        instance = TemplateInstantiator.instantiate(tpl_file, "hello", output_dir=tpl_dir)
        assert "hello" in instance.read_text()


# ---------------------------------------------------------------------------
# TimerManager
# ---------------------------------------------------------------------------

class TestTimerManager:
    def test_create_timer(self):
        timer = TimerManager.create_timer(
            name="backup.timer",
            service_name="backup.service",
            on_calendar="daily",
            persistent=True,
        )
        assert timer.unit_type == UnitType.TIMER
        assert timer.timer.on_calendar == "daily"
        assert timer.timer.persistent is True
        assert timer.timer.unit == "backup.service"

    def test_create_timer_on_boot(self):
        timer = TimerManager.create_timer(
            name="boot.timer",
            service_name="boot.service",
            on_boot_sec="60",
        )
        assert timer.timer.on_boot_sec == "60"

    def test_parse_calendar_alias(self):
        result = TimerManager.parse_calendar("daily")
        assert result["expression"] == "*-*-* 00:00:00"
        assert result["is_calendar"] is True

    def test_parse_calendar_custom(self):
        result = TimerManager.parse_calendar("Mon *-*-* *:00:00")
        assert result["expression"] == "Mon *-*-* *:00:00"


# ---------------------------------------------------------------------------
# DropInManager
# ---------------------------------------------------------------------------

class TestDropInManager:
    def test_create_and_list(self, tmp_path):
        DropInManager.create_drop_in(
            base_dir=tmp_path,
            unit_name="svc.service",
            drop_in_name="override.conf",
            section="Service",
            settings={"Nice": "5", "ProtectSystem": "strict"},
        )
        drop_ins = DropInManager.list_drop_ins(tmp_path, "svc.service")
        assert len(drop_ins) == 1

    def test_read_drop_in(self, tmp_path):
        DropInManager.create_drop_in(
            base_dir=tmp_path,
            unit_name="svc.service",
            drop_in_name="override.conf",
            section="Service",
            settings={"Nice": "5"},
        )
        content = DropInManager.read_drop_in(tmp_path, "svc.service", "override.conf")
        assert content is not None
        assert "Service" in content
        assert any(k == "Nice" and v == "5" for k, v in content["Service"])

    def test_remove_drop_in(self, tmp_path):
        DropInManager.create_drop_in(
            base_dir=tmp_path,
            unit_name="svc.service",
            drop_in_name="override.conf",
            section="Service",
            settings={"Nice": "5"},
        )
        assert DropInManager.remove_drop_in(tmp_path, "svc.service", "override.conf") is True
        assert DropInManager.list_drop_ins(tmp_path, "svc.service") == []

    def test_remove_nonexistent_drop_in(self, tmp_path):
        assert DropInManager.remove_drop_in(tmp_path, "svc.service", "nope.conf") is False

    def test_read_nonexistent_drop_in(self, tmp_path):
        assert DropInManager.read_drop_in(tmp_path, "svc.service", "nope.conf") is None

    def test_list_empty(self, tmp_path):
        assert DropInManager.list_drop_ins(tmp_path, "svc.service") == []


# ---------------------------------------------------------------------------
# DependencyResolver
# ---------------------------------------------------------------------------

class TestDependencyResolver:
    def _make_services(self):
        """Build a small service graph for dependency testing."""
        services = {}
        # network.target — no deps
        services["network.target"] = ParsedUnitFile(
            filename="network.target",
            unit_type=UnitType.TARGET,
        )
        # nginx.service — wants network.target
        services["nginx.service"] = ParsedUnitFile(
            filename="nginx.service",
            unit_type=UnitType.SERVICE,
        )
        services["nginx.service"].unit.wants = ["network.target"]
        # app.service — requires nginx.service, wants network.target
        services["app.service"] = ParsedUnitFile(
            filename="app.service",
            unit_type=UnitType.SERVICE,
        )
        services["app.service"].unit.requires = ["nginx.service"]
        services["app.service"].unit.wants = ["network.target"]
        services["app.service"].unit.after = ["nginx.service"]
        return services

    def test_resolve_dependencies(self):
        services = self._make_services()
        resolver = DependencyResolver(services)
        deps = resolver.resolve_dependencies("app.service")
        assert "nginx.service" in deps
        assert "network.target" in deps

    def test_get_start_order(self):
        services = self._make_services()
        resolver = DependencyResolver(services)
        order = resolver.get_start_order("app.service")
        assert "app.service" in order
        assert "nginx.service" in order
        # network.target should come before nginx
        assert order.index("network.target") < order.index("nginx.service")

    def test_get_stop_order(self):
        services = self._make_services()
        resolver = DependencyResolver(services)
        stop = resolver.get_stop_order("app.service")
        start = resolver.get_start_order("app.service")
        assert stop == list(reversed(start))

    def test_detect_cycles_none(self):
        services = self._make_services()
        resolver = DependencyResolver(services)
        cycles = resolver.detect_cycles()
        assert len(cycles) == 0

    def test_detect_cycles_present(self):
        services = self._make_services()
        # Create a cycle: a -> b -> a
        services["a.service"] = ParsedUnitFile(
            filename="a.service", unit_type=UnitType.SERVICE
        )
        services["a.service"].unit.requires = ["b.service"]
        services["b.service"] = ParsedUnitFile(
            filename="b.service", unit_type=UnitType.SERVICE
        )
        services["b.service"].unit.requires = ["a.service"]
        resolver = DependencyResolver(services)
        cycles = resolver.detect_cycles()
        assert len(cycles) > 0

    def test_get_reverse_dependencies(self):
        services = self._make_services()
        resolver = DependencyResolver(services)
        reverse = resolver.get_reverse_dependencies("network.target")
        assert "nginx.service" in reverse
        assert "app.service" in reverse

    def test_resolve_nonexistent(self):
        resolver = DependencyResolver({})
        deps = resolver.resolve_dependencies("nope.service")
        assert deps == []


# ---------------------------------------------------------------------------
# Integration: full lifecycle
# ---------------------------------------------------------------------------

class TestIntegrationLifecycle:
    def test_full_lifecycle(self, tmp_systemd):
        """End-to-end: parse → create → enable → start → stop → disable → delete."""
        systemd_dir, _, parsed = tmp_systemd
        mgr = ServiceManager(systemd_dir=systemd_dir)

        # Create + enable
        record = mgr.create_service("web.service", parsed, enable=True)
        assert record.enabled is True

        # Start (no ExecStart in parsed, but ServiceManager handles it)
        assert mgr.start_service("web.service") is True
        assert mgr.get_service_status("web.service")["active_state"] == "active"

        # Stop
        assert mgr.stop_service("web.service") is True
        assert mgr.get_service_status("web.service")["active_state"] == "inactive"

        # Disable
        mgr.disable_service("web.service")
        assert mgr.is_enabled("web.service") is False

        # Delete
        assert mgr.delete_service("web.service") is True
        assert mgr.get_service_status("web.service") is None

    def test_template_to_service(self, tmp_systemd):
        """Parse a template, instantiate, and create service."""
        systemd_dir, _, _ = tmp_systemd
        mgr = ServiceManager(systemd_dir=systemd_dir)

        # Create template file
        tpl_content = "[Unit]\nDescription=Worker %i\n\n[Service]\nType=simple\nExecStart=/usr/bin/worker %i\n\n[Install]\nWantedBy=multi-user.target\n"
        tpl_file = systemd_dir / "worker@.service"
        tpl_file.write_text(tpl_content)

        # Instantiate
        instance = TemplateInstantiator.instantiate(tpl_file, "pool1")
        assert instance is not None

        # Parse and create service from instance
        parser = UnitFileParser()
        parsed = parser.parse(instance.read_text(), filename=instance.name)
        record = mgr.create_service(instance.name, parsed)
        assert record.name == "worker@pool1.service"
        assert "pool1" in record.description

    def test_drop_in_with_manager(self, tmp_systemd):
        """Full drop-in lifecycle through ServiceManager."""
        systemd_dir, _, parsed = tmp_systemd
        mgr = ServiceManager(systemd_dir=systemd_dir)
        mgr.create_service("svc.service", parsed)

        # Add
        mgr.add_drop_in("svc.service", "tuning.conf", "Service", "Nice", "-10")
        drop_path = systemd_dir / "svc.service.d" / "tuning.conf"
        assert drop_path.exists()
        assert "Nice=-10" in drop_path.read_text()

        # Remove
        mgr.remove_drop_in("svc.service", "tuning.conf")
        assert not drop_path.exists()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_freeze_thaw_cycle(self, manager):
        mgr, _ = manager
        parsed = ParsedUnitFile(filename="cycle.service", unit_type=UnitType.SERVICE)
        mgr.create_service("cycle.service", parsed)
        mgr.start_service("cycle.service")

        # Freeze → Thaw → Freeze
        assert mgr.freeze_service("cycle.service") is True
        assert mgr.thaw_service("cycle.service") is True
        assert mgr.freeze_service("cycle.service") is True

    def test_mask_stops_active(self, manager):
        mgr, _ = manager
        parsed = ParsedUnitFile(filename="mask.service", unit_type=UnitType.SERVICE)
        mgr.create_service("mask.service", parsed)
        mgr.start_service("mask.service")
        # Mask should stop the service
        mgr.mask_service("mask.service")
        assert mgr.services["mask.service"].active_state == ServiceActiveState.INACTIVE

    def test_state_change_handler_exception(self, manager):
        mgr, _ = manager
        parsed = ParsedUnitFile(filename="err.service", unit_type=UnitType.SERVICE)
        mgr.create_service("err.service", parsed)

        def bad_handler(name, old, new):
            raise RuntimeError("handler boom")

        mgr.register_state_change_handler(bad_handler)
        # Should not raise
        result = mgr.start_service("err.service")
        assert result is True
