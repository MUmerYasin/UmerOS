"""
H193 - ``OptServiceManager.start_service`` (and ``stop_service`` /
``get_service_status``, which the row does not name) executed *any* script
that discovery happened to find: ``discover_services`` picks every
``.sh``/extensionless file under ``bin``/``sbin``/``scripts``/``services``
whose first 1 KB mentions start/stop/restart/status/daemon, and the control
methods then ``chmod(0o755)`` + ``subprocess.run`` it with no validation, no
capability gate and no confinement - a file dropped into a package bin dir
becomes code execution as the service manager.  The row's cited line had
drifted (:391 -> :497) but the defect was live, and it understated by one
method (``get_service_status`` executes too).

The fix makes registration the authority: a service must be recorded in a
registry (``/etc/opt/services.json`` by default - *outside* the /opt tree it
protects, mirroring the H190 package manifest) together with its streamed
SHA3-512 digest, and every execution path re-verifies the live digest,
containment (a symlink resolving outside /opt is refused), the regular-file
check, a shell-hostile-name check and - on POSIX - the world-writable check,
behind ``CAP_FS_ADMIN``.  The unconditional ``chmod(0o755)`` is gone: the
manager no longer makes dropped-in content executable.

These tests pin each of those dimensions plus the registry lifecycle.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from opt.integration import (  # noqa: E402
    HASH_ALGORITHM,
    SERVICE_REGISTRY_NAME,
    SERVICE_REGISTRY_VERSION,
    OptServiceManager,
)

#: A script discovery recognises (keyword in the first 1 KB) but that must
#: never run without registration.
SCRIPT_BODY = "#!/bin/sh\n# start stop restart status daemon\n"


def _opt_root(tmp_path: Path) -> Path:
    root = tmp_path / "opt"
    (root / "svc" / "bin").mkdir(parents=True)
    (root / "svc" / "bin" / "worker").write_text(SCRIPT_BODY, encoding="utf-8")
    return root


@pytest.fixture()
def manager(tmp_path: Path):
    return OptServiceManager(str(_opt_root(tmp_path)))


# ── discovery never executes ────────────────────────────────────────────────

def test_discovery_is_read_only(tmp_path: Path, manager: OptServiceManager):
    marker = tmp_path / "marker"
    script = tmp_path / "opt" / "svc" / "bin" / "worker"
    script.write_text(
        f"#!/bin/sh\n# start stop\necho ran > {marker}\n", encoding="utf-8"
    )
    services = manager.discover_services()
    assert "worker" in services
    assert not marker.exists(), "discovery executed the script"


def test_unknown_service_reporting(tmp_path: Path, manager: OptServiceManager):
    assert manager.start_service("nope") is False
    assert manager.stop_service("nope") is False
    assert manager.get_service_status("nope").startswith("Service not found")


# ── registration is the authority ───────────────────────────────────────────

def test_unregistered_service_is_refused(manager: OptServiceManager):
    assert manager.start_service("worker") is False
    assert manager.stop_service("worker") is False
    assert manager.get_service_status("worker").startswith("Service not available")
    assert manager.list_registered_services() == []


def test_register_then_authorize_round_trip(manager: OptServiceManager):
    assert manager.register_service("worker") is True
    authorized = manager._authorized_service("worker")
    assert authorized is not None
    assert authorized.name == "worker"
    assert manager.list_registered_services() == ["worker"]
    assert manager.unregister_service("worker") is True
    assert manager.unregister_service("worker") is False
    assert manager.list_registered_services() == []
    assert manager._authorized_service("worker") is None
    assert manager.start_service("worker") is False


def test_registry_lives_outside_the_protected_tree(tmp_path: Path):
    root = _opt_root(tmp_path)
    manager = OptServiceManager(str(root))
    expected = (tmp_path / "etc" / "opt" / SERVICE_REGISTRY_NAME).resolve()
    assert manager.registry_path.resolve() == expected
    assert manager.register_service("worker") is True
    assert expected.is_file()
    # an explicit override is honoured
    custom = tmp_path / "custom-registry.json"
    other = OptServiceManager(str(root), registry_path=str(custom))
    assert other.registry_path == custom
    assert other.register_service("worker") is True
    assert custom.is_file()


def test_registry_payload_shape(tmp_path: Path, manager: OptServiceManager):
    assert manager.register_service("worker") is True
    data = json.loads(manager.registry_path.read_text(encoding="utf-8"))
    assert data["version"] == SERVICE_REGISTRY_VERSION
    entry = data["services"]["worker"]
    assert entry[HASH_ALGORITHM]
    assert len(entry[HASH_ALGORITHM]) == 128  # SHA3-512 hex digest
    assert entry["path"] == "svc/bin/worker"


def test_malformed_registry_authorises_nothing(tmp_path: Path,
                                               manager: OptServiceManager):
    manager.registry_path.parent.mkdir(parents=True, exist_ok=True)
    manager.registry_path.write_text("{ not json", encoding="utf-8")
    assert manager._load_registry() == {}
    assert manager.list_registered_services() == []
    assert manager.start_service("worker") is False


# ── tamper detection ────────────────────────────────────────────────────────

def test_tampered_service_is_refused(tmp_path: Path, manager: OptServiceManager):
    assert manager.register_service("worker") is True
    script = tmp_path / "opt" / "svc" / "bin" / "worker"
    original = script.read_bytes()
    script.write_text(SCRIPT_BODY + "echo pwned\n", encoding="utf-8")
    assert manager._authorized_service("worker") is None
    assert manager.start_service("worker") is False
    assert manager.stop_service("worker") is False
    assert manager.get_service_status("worker").startswith("Service not available")
    script.write_bytes(original)
    assert manager._authorized_service("worker") is not None


# ── containment and hygiene ─────────────────────────────────────────────────

def test_escaping_symlink_is_refused(tmp_path: Path, manager: OptServiceManager):
    outside = tmp_path / "outside.sh"
    outside.write_text(SCRIPT_BODY, encoding="utf-8")
    link = tmp_path / "opt" / "svc" / "bin" / "escape"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("platform without symlink support")
    assert "escape" in manager.discover_services()
    assert manager._authorized_service("escape") is None
    assert manager.register_service("escape") is False
    assert manager.start_service("escape") is False


def test_shell_hostile_name_is_refused(tmp_path: Path):
    root = tmp_path / "opt"
    hostile = root / "ev$(id)`touch pwned`" / "bin"
    hostile.mkdir(parents=True)
    (hostile / "worker").write_text(SCRIPT_BODY, encoding="utf-8")
    manager = OptServiceManager(str(root))
    assert "worker" in manager.discover_services()
    reason = manager._validate_service_script(hostile / "worker")
    assert reason is not None and "shell-hostile" in reason
    assert manager.register_service("worker") is False


@pytest.mark.skipif(os.name != "posix", reason="POSIX mode bits required")
def test_world_writable_script_is_refused(tmp_path: Path,
                                          manager: OptServiceManager):
    script = tmp_path / "opt" / "svc" / "bin" / "worker"
    script.chmod(0o777)
    reason = manager._validate_service_script(script)
    assert reason is not None and "world-writable" in reason
    assert manager.register_service("worker") is False
    script.chmod(0o644)
    assert manager.register_service("worker") is True


# ── capability gate ─────────────────────────────────────────────────────────

def test_execution_requires_capability(tmp_path: Path, manager: OptServiceManager):
    import opt.integration as mod

    previous = mod.gate.strict
    try:
        mod.gate.set_strict(True)
        with pytest.raises(PermissionError):
            manager.register_service("worker")
        with pytest.raises(PermissionError):
            manager.start_service("worker")
        with pytest.raises(PermissionError):
            manager.stop_service("worker")
        with pytest.raises(PermissionError):
            manager.get_service_status("worker")
        with pytest.raises(PermissionError):
            manager.unregister_service("worker")
    finally:
        mod.gate.set_strict(previous)
    assert manager.list_registered_services() == []


# ── real execution round-trip (POSIX) ───────────────────────────────────────

@pytest.mark.skipif(os.name != "posix", reason="script execution needs a shell")
def test_registered_service_actually_executes(tmp_path: Path,
                                              manager: OptServiceManager):
    marker = tmp_path / "started.marker"
    script = tmp_path / "opt" / "svc" / "bin" / "worker"
    script.write_text(
        f"#!/bin/sh\n# start stop\necho started > {marker}\n", encoding="utf-8"
    )
    script.chmod(0o755)
    assert manager.register_service("worker") is True
    assert manager.start_service("worker") is True
    assert marker.exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX mode bits required")
def test_manager_no_longer_chmods_scripts(tmp_path: Path,
                                          manager: OptServiceManager):
    # the old implementation made any discovered script executable
    script = tmp_path / "opt" / "svc" / "bin" / "worker"
    script.chmod(0o644)
    assert manager.register_service("worker") is True
    assert manager.start_service("worker") is False  # not executable
    assert not os.access(script, os.X_OK), "manager chmod-ed the script"
