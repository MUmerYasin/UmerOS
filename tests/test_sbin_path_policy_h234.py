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

"""H234 -- validate paths and harden mount options in the simulated ``/sbin``.

The row says ``sbin/mount.py`` and ``sbin/filesystem.py`` run privileged ops
"simulated against in-memory tables (``_MOUNT_TABLE``/``_DEVICE_NODES``/
``_LOOP_DEVICES``/``_SUPERBLOCKS``) -- when wired to real ``mount``/
``os.mknod``/``chroot`` they MUST enforce cap-gating + ``nosuid,nodev,noexec``
(per mnt/media H156-H168) + path validation".

Drift-recon (session 220): premise **true, with two corrections** --

* ``_SUPERBLOCKS`` is **not** in this pair: it lives in
  ``sbin/maintenance.py`` (``tune2fs``/``e2fsck``/``mke2fs``).  And
  ``filesystem.py`` has **no in-memory state at all** -- it is pure print
  simulation.  Three of the four named tables (``_MOUNT_TABLE``,
  ``_DEVICE_NODES``, ``_LOOP_DEVICES``) are in ``mount.py``.
* The ``nosuid,nodev,noexec`` strings in ``mount.py`` were only *literal seed
  data* on the pre-populated rows.  ``MountCommand`` stored whatever ``-o``
  said, verbatim, so a caller could mount with ``suid,dev,exec`` and nothing
  objected.

Cap-gating is now covered by H233's guard (every command's ``execute()`` is
wrapped), so this file pins the other two halves: **path validation** and
**option hardening**.

Also fixed here, found while adding the checks: ``losetup -o <non-numeric>``
raised an uncaught ``ValueError`` out of ``execute()``; ``mknod -m`` parsed a
mode and threw it away; and ``chroot -h`` returned 0 only because ``-h`` was
accepted as a directory name.
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
if str(PROJ) not in sys.path:
    sys.path.insert(0, str(PROJ))

import sbin.mount as mount_mod  # noqa: E402
import sbin.path_policy as policy  # noqa: E402
from sbin.filesystem import ChrootCommand  # noqa: E402
from sbin.mount import (  # noqa: E402
    LosetupCommand,
    MknodCommand,
    MountCommand,
    PivotRootCommand,
    UmountCommand,
)
from sbin.path_policy import UnsafePathError  # noqa: E402

SBIN = PROJ / "sbin"

HARDEN_FLAGS = ("noexec", "nosuid", "nodev")


@pytest.fixture(autouse=True)
def _clean_tables():
    """Snapshot and restore every module-level table these commands mutate."""
    saved = {
        "table": list(mount_mod._MOUNT_TABLE),
        "nodes": dict(mount_mod._DEVICE_NODES),
        "modes": dict(mount_mod._DEVICE_MODES),
        "loops": dict(mount_mod._LOOP_DEVICES),
    }
    yield
    mount_mod._MOUNT_TABLE[:] = saved["table"]
    mount_mod._DEVICE_NODES.clear()
    mount_mod._DEVICE_NODES.update(saved["nodes"])
    mount_mod._DEVICE_MODES.clear()
    mount_mod._DEVICE_MODES.update(saved["modes"])
    mount_mod._LOOP_DEVICES.clear()
    mount_mod._LOOP_DEVICES.update(saved["loops"])


def _src(name: str) -> str:
    return (SBIN / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# path_policy.normalise
# ---------------------------------------------------------------------------

class TestNormalise:
    @pytest.mark.parametrize("good", ["/", "/mnt", "/mnt/usb", "/dev/sda1", "/a/b/c"])
    def test_accepts_absolute(self, good):
        assert policy.normalise(good) == good

    def test_normalises_duplicate_and_trailing_separators(self):
        assert policy.normalise("/mnt//usb/") == "/mnt/usb"

    @pytest.mark.parametrize(
        "bad",
        [None, "", "   ", 123, "relative/path", "mnt/usb", "./x", "../etc",
         "/mnt/../etc", "/a/../../b", "C:\\Windows", "/mnt\\usb", "/mnt/\x00x",
         "/mnt/x\nrm -rf /"],
    )
    def test_rejects_unsafe(self, bad):
        with pytest.raises(UnsafePathError):
            policy.normalise(bad)

    def test_dot_dot_is_rejected_before_normalisation(self):
        """/mnt/../etc normalises to /etc -- it must be refused, not cleaned."""
        with pytest.raises(UnsafePathError):
            policy.normalise("/mnt/../etc")

    def test_what_appears_in_the_message(self):
        with pytest.raises(UnsafePathError, match="mount point"):
            policy.normalise("relative", "mount point")


# ---------------------------------------------------------------------------
# path_policy.require_under / validate_source / require_loop_device
# ---------------------------------------------------------------------------

class TestRequireUnder:
    def test_direct_child_and_nested(self):
        assert policy.require_under("/dev/sda1", "/dev") == "/dev/sda1"
        assert policy.require_under("/dev/disk/by-id/x", "/dev") == "/dev/disk/by-id/x"

    def test_prefix_boundary_is_not_a_substring_match(self):
        """/devx must not count as being under /dev."""
        with pytest.raises(UnsafePathError):
            policy.require_under("/devx/a", "/dev")

    def test_outside_prefix_rejected(self):
        with pytest.raises(UnsafePathError):
            policy.require_under("/etc/cron.d/root", "/dev")

    def test_traversal_rejected(self):
        with pytest.raises(UnsafePathError):
            policy.require_under("/dev/../../etc/passwd", "/dev")


class TestValidateSource:
    @pytest.mark.parametrize("good", ["/dev/sdb1", "proc", "tmpfs", "sysfs", "nfs:/export"])
    def test_accepts_devices_and_pseudo_fs(self, good):
        assert policy.validate_source(good) == good

    @pytest.mark.parametrize("bad", [None, "", "  ", "../etc", "/dev/../etc"])
    def test_rejects_empty_and_traversing(self, bad):
        with pytest.raises(UnsafePathError):
            policy.validate_source(bad)


class TestRequireLoopDevice:
    @pytest.mark.parametrize("good", ["/dev/loop0", "/dev/loop7", "/dev/loop128"])
    def test_accepts_loop_names(self, good):
        assert policy.require_loop_device(good) == good

    @pytest.mark.parametrize("bad", ["/dev/sda", "/dev/loop", "/dev/loopX", "/tmp/loop0", "loop0"])
    def test_rejects_other_devices(self, bad):
        with pytest.raises(UnsafePathError):
            policy.require_loop_device(bad)


# ---------------------------------------------------------------------------
# path_policy.harden_mount_options
# ---------------------------------------------------------------------------

class TestHardenMountOptions:
    def test_adds_all_three_to_a_bare_option_string(self):
        opts, added = policy.harden_mount_options("rw,relatime")
        assert opts == "rw,relatime,noexec,nosuid,nodev"
        assert added == ["noexec", "nosuid", "nodev"]

    def test_empty_options_still_harden(self):
        opts, added = policy.harden_mount_options("")
        assert opts == "noexec,nosuid,nodev"
        assert added == ["noexec", "nosuid", "nodev"]

    def test_none_is_treated_as_empty(self):
        opts, _ = policy.harden_mount_options(None)
        assert opts == "noexec,nosuid,nodev"

    def test_existing_flags_are_not_duplicated(self):
        opts, added = policy.harden_mount_options("rw,nosuid,nodev,noexec")
        assert opts == "rw,nosuid,nodev,noexec"
        assert added == []

    def test_explicit_opt_out_is_preserved(self):
        """`exec` is a deliberate privileged decision -- do not override it."""
        opts, added = policy.harden_mount_options("rw,exec")
        assert "exec" in opts.split(",")
        assert "noexec" not in opts.split(",")
        assert added == ["nosuid", "nodev"]

    def test_mixed_opt_out_and_auto_harden(self):
        opts, added = policy.harden_mount_options("suid,dev")
        names = opts.split(",")
        assert "suid" in names and "dev" in names
        assert "nosuid" not in names and "nodev" not in names
        assert added == ["noexec"]

    def test_pairs_match_the_mnt_engine(self):
        """`sbin/` must not drift from mnt/mount_ops -- the same three flags."""
        from mnt import mount_ops

        assert policy.HARDEN_PAIRS == mount_ops._HARDEN_PAIRS


# ---------------------------------------------------------------------------
# Commands refuse unsafe paths (the decisive behaviour)
# ---------------------------------------------------------------------------

class TestCommandsRefuseUnsafePaths:
    def test_mount_rejects_traversing_mount_point(self):
        before = len(mount_mod._MOUNT_TABLE)
        assert MountCommand().execute(["/dev/sdb1", "../../etc"]) == 1
        assert len(mount_mod._MOUNT_TABLE) == before, "table was mutated"

    def test_mount_rejects_relative_mount_point(self):
        assert MountCommand().execute(["/dev/sdb1", "mnt/usb"]) == 1

    def test_mount_rejects_traversing_device(self):
        assert MountCommand().execute(["../../etc", "/mnt/h234"]) == 1

    def test_umount_rejects_traversing_target(self):
        assert UmountCommand().execute(["../etc"]) == 1

    def test_mknod_refuses_a_node_outside_dev(self):
        """The classic privesc: plant a device node in a world-writable dir."""
        assert MknodCommand().execute(["/etc/cron.d/root", "c", "1", "1"]) == 1
        assert "/etc/cron.d/root" not in mount_mod._DEVICE_NODES

    def test_mknod_refuses_traversal_out_of_dev(self):
        assert MknodCommand().execute(["/dev/../../etc/passwd", "c", "1", "1"]) == 1
        assert "/etc/passwd" not in mount_mod._DEVICE_NODES

    def test_losetup_refuses_a_traversing_backing_file(self):
        assert LosetupCommand().execute(["/dev/loop0", "../../etc/passwd"]) == 1
        assert "/dev/loop0" not in mount_mod._LOOP_DEVICES

    def test_losetup_refuses_a_non_loop_device(self):
        assert LosetupCommand().execute(["/dev/sda", "/tmp/x.img"]) == 1

    def test_chroot_refuses_a_traversing_root(self):
        assert ChrootCommand().execute(["../../etc"]) == 1

    def test_pivot_root_refuses_a_traversing_put_old(self):
        assert PivotRootCommand().execute(["/new", "../../etc"]) == 1


# ---------------------------------------------------------------------------
# Hardening is actually applied to new mounts
# ---------------------------------------------------------------------------

class TestMountHardening:
    def test_new_mount_gets_hardened(self):
        assert MountCommand().execute(["-o", "rw", "/dev/sdb9", "/mnt/h234"]) == 0
        entry = next(m for m in mount_mod._MOUNT_TABLE if m["mount_point"] == "/mnt/h234")
        names = entry["options"].split(",")
        for flag in HARDEN_FLAGS:
            assert flag in names, f"{flag} missing from {entry['options']!r}"

    def test_explicit_exec_is_kept(self):
        assert MountCommand().execute(
            ["-o", "rw,exec", "/dev/sdb8", "/mnt/h234x"]
        ) == 0
        entry = next(m for m in mount_mod._MOUNT_TABLE if m["mount_point"] == "/mnt/h234x")
        names = entry["options"].split(",")
        assert "exec" in names and "noexec" not in names
        assert "nosuid" in names and "nodev" in names

    def test_happy_path_still_works(self):
        assert MountCommand().execute(["/dev/sdb1", "/mnt/usb"]) == 0
        assert MountCommand().execute(["/dev/sdb2", "/mnt/usb"]) == 1  # duplicate


# ---------------------------------------------------------------------------
# Bugs found while adding the checks
# ---------------------------------------------------------------------------

class TestBugsFixedAlongTheWay:
    def test_losetup_bad_offset_does_not_raise(self):
        """Used to be an uncaught ValueError straight out of execute()."""
        assert LosetupCommand().execute(["-o", "abc", "/dev/loop0", "/tmp/x.img"]) == 1

    def test_losetup_good_offset_still_attaches(self):
        assert LosetupCommand().execute(["-o", "512", "/dev/loop0", "/tmp/x.img"]) == 0
        assert mount_mod._LOOP_DEVICES["/dev/loop0"] == "/tmp/x.img"

    def test_mknod_records_the_requested_mode(self):
        """`-m` was parsed and discarded, so it silently did nothing."""
        assert MknodCommand().execute(
            ["-m", "0600", "/dev/h234probe", "c", "1", "1"]
        ) == 0
        assert mount_mod._DEVICE_MODES["/dev/h234probe"] == 0o600

    def test_mknod_default_mode_is_recorded(self):
        assert MknodCommand().execute(["/dev/h234def", "p"]) == 0
        assert mount_mod._DEVICE_MODES["/dev/h234def"] == 0o660

    def test_chroot_help_and_version(self):
        assert ChrootCommand().execute(["-h"]) == 0
        assert ChrootCommand().execute(["-V"]) == 0


# ---------------------------------------------------------------------------
# Source invariants: the policy is wired, not merely available
# ---------------------------------------------------------------------------

class TestSourceInvariants:
    @pytest.mark.parametrize(
        "module,callee",
        [
            ("mount.py", "normalise"),
            ("mount.py", "validate_source"),
            ("mount.py", "require_under"),
            ("mount.py", "require_loop_device"),
            ("mount.py", "harden_mount_options"),
            ("filesystem.py", "normalise"),
        ],
    )
    def test_module_calls_the_policy(self, module, callee):
        tree = ast.parse(_src(module))
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert callee in calls, f"{module} never calls path_policy.{callee}()"

    def test_policy_is_imported_with_a_standalone_fallback(self):
        for module in ("mount.py", "filesystem.py"):
            src = _src(module)
            assert "from . import path_policy" in src
            assert "import path_policy  # type: ignore[no-redef]" in src

    def test_no_bare_int_parse_survives_in_losetup(self):
        """`int(args[i + 1])` must sit inside a try/except."""
        tree = ast.parse(_src("mount.py"))
        losetup = next(
            n for n in tree.body
            if isinstance(n, ast.ClassDef) and n.name == "LosetupCommand"
        )
        guarded = False
        for node in ast.walk(losetup):
            if not isinstance(node, ast.Try):
                continue
            for inner in ast.walk(node):
                if (
                    isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Name)
                    and inner.func.id == "int"
                ):
                    guarded = True
        assert guarded, "losetup's offset parse is not inside a try block"
