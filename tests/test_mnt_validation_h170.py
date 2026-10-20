"""Regression tests for H170 - ``MntValidator`` findings were advisory-only.

Before H170 the validator exported by ``mnt/validation.py`` was consulted by
*nothing* on the mount path: ``MountManager.mount()`` recorded whatever it was
given, so a symlinked mount point, a non-directory target, or an unusual leaf
name all mounted happily.  This is the "detect-but-don't-fail-closed" family
already closed for ``media/`` (H159).

The fix adds :meth:`MntValidator.validate_mount_request` -- a request-scoped
subset of the whole-tree audit -- and wires it into ``MountManager.mount()``
(fail-closed on ``ERROR`` findings, logged on ``WARNING``), with a
``validate_mounts=False`` opt-out.

Note: ``tempfile.TemporaryDirectory`` is used rather than pytest's ``tmp_path``
because the Windows profile directory contains a space, and ``mnt/fstab.py``
splits fstab lines on whitespace (see ``tests/test_mnt.py``).
"""

from __future__ import annotations

import os
import tempfile

import pytest

from mnt.mount_ops import MountError, MountManager
from mnt.validation import Finding, MntValidator, Severity


def _symlink_or_skip(target: str, link: str) -> None:
    """Create a directory symlink, or skip when the OS refuses."""
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:  # pragma: no cover
        pytest.skip(f"symlinks unavailable: {exc}")


@pytest.fixture()
def tree():
    """A throw-away ``/mnt`` root with a sound point, a file and a dir."""
    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(tmp, "mnt")
        os.makedirs(os.path.join(root, "good"))
        os.makedirs(os.path.join(root, "target"))
        with open(os.path.join(root, "afile"), "w", encoding="utf-8") as fh:
            fh.write("not a mount point")
        yield root


@pytest.fixture()
def validator(tree):
    return MntValidator(mnt_root=tree, fstab_path=os.path.join(tree, "fstab"))


@pytest.fixture()
def manager(tree):
    return MountManager(proc_mounts=os.path.join(tree, "absent"), mnt_root=tree)


# ---------------------------------------------------------------------------
# validate_mount_request - scoping
# ---------------------------------------------------------------------------

class TestRequestScoping:
    def test_outside_mnt_root_is_ignored(self, validator):
        """``/mnt`` policy must not veto ``/media`` or arbitrary mounts."""
        assert validator.validate_mount_request(
            "/dev/sdb1", "/media/usb", "vfat", "user,exec"
        ) == []

    def test_root_itself_is_checked(self, validator, tree):
        """Mounting directly onto the mnt root is in scope."""
        findings = validator.validate_mount_request(
            "/dev/sdb1", tree, "vfat", "user,exec"
        )
        assert [f.code for f in findings] == ["MNT009"]

    def test_sibling_prefix_is_not_under_root(self, validator, tree):
        """``/mntfoo`` must not be treated as ``/mnt``."""
        sibling = tree + "foo"
        os.makedirs(sibling)
        assert validator.validate_mount_request(
            "/dev/sdb1", os.path.join(sibling, "x"), "vfat", "user,exec"
        ) == []

    def test_sound_request_has_no_findings(self, validator, tree):
        assert validator.validate_mount_request(
            "/dev/sdb1", os.path.join(tree, "good"), "vfat",
            "user,noexec,nosuid,nodev",
        ) == []


# ---------------------------------------------------------------------------
# validate_mount_request - individual checks
# ---------------------------------------------------------------------------

class TestRequestChecks:
    def test_mnt003_non_directory(self, validator, tree):
        findings = validator.validate_mount_request(
            "/dev/sdb1", os.path.join(tree, "afile"), "vfat"
        )
        assert [f.code for f in findings] == ["MNT003"]
        assert findings[0].severity == Severity.ERROR

    def test_mnt004_symlink(self, validator, tree):
        link = os.path.join(tree, "link")
        _symlink_or_skip(os.path.join(tree, "target"), link)
        findings = validator.validate_mount_request("/dev/sdb1", link, "vfat")
        assert [f.code for f in findings] == ["MNT004"]
        assert findings[0].severity == Severity.ERROR

    def test_mnt004_does_not_require_existence(self, validator, tree):
        """A dangling symlink is still a redirection risk."""
        link = os.path.join(tree, "dangling")
        _symlink_or_skip(os.path.join(tree, "gone"), link)
        codes = [f.code for f in
                 validator.validate_mount_request("/dev/sdb1", link, "vfat")]
        assert "MNT004" in codes

    @pytest.mark.parametrize("name", ["bad name", "we$ird", "tab\there", "semi;colon"])
    def test_mnt005_unusual_name(self, validator, tree, name):
        findings = validator.validate_mount_request(
            "/dev/sdb1", os.path.join(tree, name), "vfat"
        )
        assert [f.code for f in findings] == ["MNT005"]
        assert findings[0].severity == Severity.ERROR

    @pytest.mark.parametrize("name", ["usb", "usb0", "data-1", "a.b", "UPPER"])
    def test_mnt005_accepts_sane_names(self, validator, tree, name):
        assert validator.validate_mount_request(
            "/dev/sdb1", os.path.join(tree, name), "vfat"
        ) == []

    @pytest.mark.parametrize("opts", ["user", "users", "user,exec", "users,suid,dev"])
    def test_mnt009_weak_user_options_warn(self, validator, tree, opts):
        findings = validator.validate_mount_request(
            "/dev/sdb1", os.path.join(tree, "good"), "vfat", opts
        )
        assert [f.code for f in findings] == ["MNT009"]
        assert findings[0].severity == Severity.WARNING

    def test_mnt009_reports_the_missing_flags(self, validator, tree):
        finding = validator.validate_mount_request(
            "/dev/sdb1", os.path.join(tree, "good"), "vfat", "user"
        )[0]
        assert "noexec" in finding.message
        assert "nosuid" in finding.message
        assert "nodev" in finding.message

    def test_mnt009_not_raised_for_privileged_mounts(self, validator, tree):
        assert validator.validate_mount_request(
            "/dev/sdb1", os.path.join(tree, "good"), "ext4", "rw,relatime"
        ) == []

    def test_finding_carries_request_context(self, validator, tree):
        finding = validator.validate_mount_request(
            "/dev/sdz9", os.path.join(tree, "good"), "vfat", "user"
        )[0]
        assert finding.context["device"] == "/dev/sdz9"
        assert finding.context["fstype"] == "vfat"


# ---------------------------------------------------------------------------
# Severity contract: audit warns, request refuses
# ---------------------------------------------------------------------------

class TestSeverityPromotion:
    def test_symlink_is_warning_in_audit_but_error_in_request(self, tree):
        link = os.path.join(tree, "link")
        _symlink_or_skip(os.path.join(tree, "target"), link)
        validator = MntValidator(mnt_root=tree, fstab_path=os.path.join(tree, "f"))

        audit = {f.code: f.severity for f in validator.validate()}
        request = {f.code: f.severity for f in
                   validator.validate_mount_request("/dev/sdb1", link, "vfat")}

        assert audit["MNT004"] == Severity.WARNING
        assert request["MNT004"] == Severity.ERROR

    def test_name_check_is_warning_in_audit_but_error_in_request(self, tree):
        os.makedirs(os.path.join(tree, "odd name"))
        validator = MntValidator(mnt_root=tree, fstab_path=os.path.join(tree, "f"))

        audit = {f.code: f.severity for f in validator.validate()}
        request = {f.code: f.severity for f in validator.validate_mount_request(
            "/dev/sdb1", os.path.join(tree, "odd name"), "vfat")}

        assert audit["MNT005"] == Severity.WARNING
        assert request["MNT005"] == Severity.ERROR


# ---------------------------------------------------------------------------
# MountManager wiring
# ---------------------------------------------------------------------------

class TestMountManagerGate:
    def test_default_construction_is_gated(self):
        mgr = MountManager(proc_mounts="/nonexistent")
        assert mgr._validate_mounts is True
        assert mgr._validator is not None
        assert mgr._mnt_root == "/mnt"

    def test_symlinked_mount_point_is_refused(self, manager, tree):
        link = os.path.join(tree, "link")
        _symlink_or_skip(os.path.join(tree, "target"), link)
        with pytest.raises(MountError) as excinfo:
            manager.mount("/dev/sdb1", link, "vfat")
        assert "MNT004" in str(excinfo.value)
        assert not manager.is_mounted(link)

    def test_unusual_name_is_refused(self, manager, tree):
        """The point must exist, else ``_validate_mount_point`` fires first."""
        bad = os.path.join(tree, "bad name")
        os.makedirs(bad)
        with pytest.raises(MountError) as excinfo:
            manager.mount("/dev/sdb1", bad, "vfat")
        assert "MNT005" in str(excinfo.value)

    def test_sound_request_still_mounts(self, manager, tree):
        rec = manager.mount(
            "/dev/sdb1", os.path.join(tree, "good"), "vfat",
            "user,noexec,nosuid,nodev",
        )
        assert manager.is_mounted(os.path.join(tree, "good"))
        assert "noexec" in rec.options_set

    def test_h169_hardening_still_applied(self, manager, tree):
        rec = manager.mount("/dev/sdb1", os.path.join(tree, "good"), "vfat", "user")
        assert {"noexec", "nosuid", "nodev"} <= set(rec.options_set)

    def test_opt_out_restores_permissive_behaviour(self, tree):
        link = os.path.join(tree, "link")
        _symlink_or_skip(os.path.join(tree, "target"), link)
        lax = MountManager(
            proc_mounts=os.path.join(tree, "absent"),
            mnt_root=tree,
            validate_mounts=False,
        )
        lax.mount("/dev/sdb2", link, "vfat")
        assert lax.is_mounted(link)

    def test_mounts_outside_mnt_root_are_unaffected(self, tree):
        """A pre-H170 caller mounting outside ``/mnt`` must keep working."""
        outside = os.path.join(os.path.dirname(tree), "outside dir")
        os.makedirs(outside)
        mgr = MountManager(proc_mounts=os.path.join(tree, "absent"), mnt_root=tree)
        mgr.mount("/dev/sdb1", outside, "vfat")
        assert mgr.is_mounted(outside)

    def test_bind_mount_goes_through_the_gate(self, manager, tree):
        """``bind_mount`` delegates to ``mount``, so it is gated too."""
        bad = os.path.join(tree, "bad name")
        os.makedirs(bad)
        with pytest.raises(MountError) as excinfo:
            manager.bind_mount(os.path.join(tree, "good"), bad)
        assert "MNT005" in str(excinfo.value)

    def test_injected_validator_is_used(self, tree):
        calls = []

        class Recording(MntValidator):
            def validate_mount_request(self, device, mount_point,
                                       fstype="auto", options="defaults"):
                calls.append(mount_point)
                return [Finding(Severity.ERROR, "MNT999", "vetoed")]

        mgr = MountManager(
            proc_mounts=os.path.join(tree, "absent"),
            mnt_root=tree,
            validator=Recording(mnt_root=tree),
        )
        with pytest.raises(MountError) as excinfo:
            mgr.mount("/dev/sdb1", os.path.join(tree, "good"), "vfat")
        assert "MNT999" in str(excinfo.value)
        assert calls == [os.path.join(tree, "good")]

    def test_warning_findings_do_not_block(self, tree):
        """A deliberate ``exec`` override warns but still mounts."""
        mgr = MountManager(proc_mounts=os.path.join(tree, "absent"), mnt_root=tree)
        rec = mgr.mount("/dev/sdb1", os.path.join(tree, "good"), "vfat",
                        "user,exec,nosuid,nodev")
        assert "exec" in rec.options_set
        assert mgr.is_mounted(os.path.join(tree, "good"))

    def test_denial_is_audited_as_failure(self, tree):
        from mnt.audit import AuditLog

        audit_path = os.path.join(tree, "audit.jsonl")
        audit = AuditLog(log_path=audit_path)
        mgr = MountManager(
            proc_mounts=os.path.join(tree, "absent"),
            mnt_root=tree,
            audit=audit,
        )
        bad = os.path.join(tree, "bad name")
        os.makedirs(bad)
        with pytest.raises(MountError):
            mgr.mount("/dev/sdb1", bad, "vfat")

        records = audit.for_mount_point(bad)
        assert records, "denial was not audited"
        assert records[-1].success is False
        assert "MNT005" in records[-1].message

    def test_remount_is_not_revalidated(self, manager, tree):
        """``remount`` targets an existing mount, so it is out of scope."""
        point = os.path.join(tree, "good")
        manager.mount("/dev/sdb1", point, "ext4", "rw")
        manager.remount(point, "ro")
        assert manager.find_mount(point).is_readonly
