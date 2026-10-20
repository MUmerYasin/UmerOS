"""Regression tests for H172 - the ``enforce_user`` flag was dead.

``MountManager.__init__`` accepted ``enforce_user`` and stored it in
``self._enforce_user``, but nothing in the module ever read the attribute:
``mount()`` consulted ``enforce_noauto`` and ignored its sibling entirely.  A
caller who passed ``enforce_user=True`` got exactly the permissive behaviour
they were trying to opt out of.

H172 wires it into ``mount()``: when the flag is set, a request that does not
carry the fstab ``user``/``users`` option is refused with :class:`MountError`
and audited as a permission denial.  The default stays ``False`` so existing
callers are unaffected.

Note: ``tempfile.TemporaryDirectory`` is used rather than pytest's ``tmp_path``
because the Windows profile directory contains a space and ``mnt/fstab.py``
splits fstab lines on whitespace (see ``tests/test_mnt.py``).
"""

from __future__ import annotations

import os
import tempfile

import pytest

from mnt.audit import AuditEvent, AuditLog
from mnt.mount_ops import MountError, MountManager


@pytest.fixture()
def tree():
    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(tmp, "mnt")
        os.makedirs(os.path.join(root, "usb"))
        os.makedirs(os.path.join(root, "other"))
        yield {
            "tmp": tmp,
            "root": root,
            "usb": os.path.join(root, "usb"),
            "other": os.path.join(root, "other"),
            "absent": os.path.join(tmp, "no-proc-mounts"),
        }


def _strict(tree, **kwargs):
    return MountManager(
        proc_mounts=tree["absent"],
        enforce_noauto=False,
        enforce_user=True,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# The flag is stored and defaulted as documented
# ---------------------------------------------------------------------------

class TestFlagWiring:
    def test_default_is_permissive(self, tree):
        mgr = MountManager(proc_mounts=tree["absent"])
        assert mgr._enforce_user is False

    def test_flag_is_stored(self, tree):
        assert _strict(tree)._enforce_user is True

    def test_flag_is_actually_read(self, tree):
        """The regression: the attribute used to be written and never read."""
        mgr = _strict(tree)
        with pytest.raises(MountError):
            mgr.mount("/dev/sdb1", tree["usb"], "vfat", "rw")


# ---------------------------------------------------------------------------
# Enforcement
# ---------------------------------------------------------------------------

class TestEnforcement:
    @pytest.mark.parametrize("opts", ["defaults", "rw", "rw,relatime", "noauto"])
    def test_non_user_requests_are_refused(self, tree, opts):
        mgr = _strict(tree)
        with pytest.raises(MountError):
            mgr.mount("/dev/sdb1", tree["usb"], "vfat", opts)
        assert not mgr.is_mounted(tree["usb"])

    @pytest.mark.parametrize("opts", ["user", "users", "user,noexec,nosuid,nodev"])
    def test_user_requests_are_allowed(self, tree, opts):
        mgr = _strict(tree)
        mgr.mount("/dev/sdb1", tree["usb"], "vfat", opts)
        assert mgr.is_mounted(tree["usb"])

    def test_users_option_is_accepted(self, tree):
        """``users`` is the shared variant of ``user`` -- both qualify."""
        mgr = _strict(tree)
        mgr.mount("/dev/sdb1", tree["usb"], "vfat", "users,noexec")
        assert mgr.is_mounted(tree["usb"])

    def test_error_message_names_the_option(self, tree):
        mgr = _strict(tree)
        with pytest.raises(MountError) as excinfo:
            mgr.mount("/dev/sdb1", tree["usb"], "vfat", "rw")
        message = str(excinfo.value)
        assert "user" in message
        assert "enforce_user" in message

    def test_refused_mount_is_not_recorded(self, tree):
        mgr = _strict(tree)
        with pytest.raises(MountError):
            mgr.mount("/dev/sdb1", tree["usb"], "vfat", "rw")
        assert mgr.mounts == []
        assert mgr.find_mount(tree["usb"]) is None

    def test_permissive_manager_still_mounts_non_user(self, tree):
        """Default ``enforce_user=False`` must be behaviour-neutral."""
        mgr = MountManager(proc_mounts=tree["absent"], enforce_noauto=False)
        mgr.mount("/dev/sdb1", tree["usb"], "vfat", "rw")
        assert mgr.is_mounted(tree["usb"])

    def test_bind_mount_is_subject_to_the_policy(self, tree):
        """``bind_mount`` delegates to ``mount``, so it inherits the gate."""
        mgr = _strict(tree)
        with pytest.raises(MountError):
            mgr.bind_mount(tree["usb"], tree["other"])


# ---------------------------------------------------------------------------
# Interaction with the neighbouring checks
# ---------------------------------------------------------------------------

class TestInteraction:
    def test_noauto_still_skips_rather_than_failing(self, tree):
        """``noauto`` is an expected condition, not a policy denial."""
        mgr = MountManager(
            proc_mounts=tree["absent"],
            enforce_noauto=True,
            enforce_user=True,
        )
        rec = mgr.mount("/dev/sdb1", tree["usb"], "vfat", "noauto")
        assert rec.mount_point == tree["usb"]
        assert not mgr.is_mounted(tree["usb"])

    def test_h169_hardening_still_applies_to_allowed_mounts(self, tree):
        mgr = _strict(tree)
        rec = mgr.mount("/dev/sdb1", tree["usb"], "vfat", "user")
        assert {"noexec", "nosuid", "nodev"} <= set(rec.options_set)

    def test_h170_validator_still_runs_after_the_policy_check(self, tree):
        """A user mount to a symlinked target is still refused (MNT004)."""
        link = os.path.join(tree["root"], "link")
        try:
            os.symlink(tree["other"], link, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:  # pragma: no cover
            pytest.skip(f"symlinks unavailable: {exc}")

        # mnt_root must point at the temp tree for /mnt policy to apply.
        mgr = _strict(tree, mnt_root=tree["root"])
        with pytest.raises(MountError) as excinfo:
            mgr.mount("/dev/sdb1", link, "vfat", "user")
        assert "MNT004" in str(excinfo.value)

    def test_capability_gate_still_runs_first(self, tree, monkeypatch):
        """The fs.admin gate precedes the policy check."""
        import mnt.mount_ops as mod

        class DenyingGate:
            def require(self, *args, **kwargs):
                raise PermissionError("denied by test gate")

        monkeypatch.setattr(mod, "gate", DenyingGate())
        mgr = _strict(tree)
        with pytest.raises(PermissionError):
            mgr.mount("/dev/sdb1", tree["usb"], "vfat", "rw")


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

class TestAudit:
    def test_denial_is_audited_as_permission_deny(self, tree):
        audit = AuditLog(log_path=os.path.join(tree["tmp"], "audit.jsonl"))
        mgr = _strict(tree, audit=audit)

        with pytest.raises(MountError):
            mgr.mount("/dev/sdb1", tree["usb"], "vfat", "rw")

        records = audit.for_mount_point(tree["usb"])
        assert records, "denial was not audited"
        record = records[-1]
        assert record.event == AuditEvent.PERMISSION_DENY.value
        assert record.success is False
        assert "enforce_user" in record.message

    def test_allowed_mount_is_audited_as_success(self, tree):
        audit = AuditLog(log_path=os.path.join(tree["tmp"], "audit.jsonl"))
        mgr = _strict(tree, audit=audit)

        mgr.mount("/dev/sdb1", tree["usb"], "vfat", "user")

        record = audit.for_mount_point(tree["usb"])[-1]
        assert record.event == AuditEvent.MOUNT.value
        assert record.success is True
