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
Tests for the ``initrd`` package.

Written with the stdlib :mod:`unittest` framework so the tests work
on every Python version without needing pytest (the installed pytest
on this machine still imports the removed ``imp`` module).

Run with::

    python -m unittest tests.test_initrd -v
    python tests/run_initrd_tests.py
    python tests/run_initrd_tests.py TestArchivers
"""

from __future__ import annotations

import asyncio
import gzip
import json
import os
import struct
import sys
import unittest
from pathlib import Path

# Make sure the package under test is on the path regardless of cwd.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from initrd.ai_helper import AIHelper
from initrd.archivers import (
    GzipArchiver,
    Lz4Archiver,
    RawArchiver,
    XzArchiver,
    ZstdArchiver,
    detect_archiver,
    get_archiver,
    list_archivers,
)
from initrd.builder import BuildRequest, InitrdBuilder, OutputFormat
from initrd.cpio import (
    newc_dir,
    newc_file,
    newc_symlink,
    pack_archive,
    unpack_archive,
)
from initrd.hooks import HookAbort, HookManager, HookPoint
from initrd.linuxrc import BootContext, run as linuxrc_run, _drop_to_root
from initrd.module_resolver import ModuleResolver, detect_rootfstype
from initrd.mounts import (
    FilesystemType, MountFlag, MountTable, chroot_into, chroot_undo,
    dev_read, mount, mount_dev, mount_proc, mount_sys, populate_dev,
    resolve_in_chroot, unmount,
)
from initrd.phase_machine import BootPhase, PhaseMachine, PhaseOutcome
from initrd.pivot_root import PivotRootError, pivot_root
from initrd.ramdisk import RamDisk, RamDiskState
from initrd.scenarios import (
    SCENARIO_CATALOGUE,
    ScenarioId,
    ScenarioRunner,
    get_scenario,
    list_scenarios,
)
from initrd.signals import InitSignal, PID1SignalHandler
from initrd.vfs_ops import VfsRoot

# Zero-trust capability gate (used by the H92 privileged-boot-op test).  Guarded
# so this test module still imports if core is not on the path.
try:
    from core.capability_gate import gate as _cap_gate
except Exception:  # pragma: no cover
    class _NoGate:
        def require(self, *args, **kwargs):  # always allow
            return None
        def unwire(self):
            return None
        def set_strict(self, value):
            return None
    _cap_gate = _NoGate()


# ---------------------------------------------------------------------------
# archivers
# ---------------------------------------------------------------------------

class TestArchivers(unittest.TestCase):
    def test_roundtrip_gzip(self):
        data = b"umeros archivers test " * 100
        out = GzipArchiver.compress(data)
        self.assertEqual(GzipArchiver.decompress(out), data)
        self.assertTrue(out.startswith(GzipArchiver.magic))

    def test_roundtrip_xz(self):
        data = b"umeros xz test " * 100
        out = XzArchiver.compress(data)
        self.assertEqual(XzArchiver.decompress(out), data)
        self.assertTrue(out.startswith(XzArchiver.magic))

    def test_raw_passthrough(self):
        self.assertEqual(RawArchiver.compress(b"x"), b"x")
        self.assertEqual(RawArchiver.decompress(b"y"), b"y")

    def test_get_and_detect(self):
        self.assertIs(get_archiver("gzip"), GzipArchiver)
        sample = GzipArchiver.compress(b"hello")
        self.assertIs(detect_archiver(sample), GzipArchiver)

    def test_list_includes_known(self):
        names = list_archivers()
        for k in ("gzip", "xz", "raw"):
            self.assertIn(k, names)

    def test_unknown_archiver_raises(self):
        with self.assertRaises(KeyError):
            get_archiver("definitely-not-a-real-archiver")


# ---------------------------------------------------------------------------
# cpio
# ---------------------------------------------------------------------------

class TestCpio(unittest.TestCase):
    def test_header_size(self):
        # cpio newc: 6 + 13*8 = 110 bytes per header
        self.assertEqual(
            struct.calcsize("6s8s8s8s8s8s8s8s8s8s8s8s8s8s"),
            110,
        )

    def test_pack_and_unpack(self):
        entries = [
            newc_dir("."),
            newc_dir("etc"),
            newc_file("etc/hostname", b"umer-os\n"),
            newc_symlink("bin/sh", "bin/busybox"),
        ]
        blob = pack_archive(entries)
        rt = unpack_archive(blob)
        by_name = {e.name: e for e in rt}
        # cpio uses relative paths without a leading slash.
        self.assertIn("etc", by_name)
        self.assertIn("etc/hostname", by_name)
        self.assertEqual(by_name["etc/hostname"].data, b"umer-os\n")
        self.assertEqual(by_name["bin/sh"].target, "bin/busybox")

    def test_alignment_padding(self):
        entries = [newc_file("a", b"x")]
        blob = pack_archive(entries)
        rt = unpack_archive(blob)
        self.assertEqual(len(rt), 1)
        self.assertEqual(rt[0].name, "a")

    def test_directory_mode_preserved(self):
        entries = [newc_dir("run", mode=0o775)]
        rt = unpack_archive(pack_archive(entries))
        self.assertEqual(rt[0].mode & 0o777, 0o775)

    def test_trailer_record_present(self):
        blob = pack_archive([])
        self.assertIn(b"TRAILER!!!", blob)


# ---------------------------------------------------------------------------
# vfs_ops
# ---------------------------------------------------------------------------

class TestVfsOps(unittest.TestCase):
    def test_mkdir_and_touch(self):
        r = VfsRoot()
        r.mkdir("/etc")
        r.touch("/etc/hostname", data=b"umer-os\n")
        self.assertEqual(r.read_file("/etc/hostname"), b"umer-os\n")
        self.assertEqual(r.listdir("/"), ["etc"])

    def test_symlink(self):
        r = VfsRoot()
        r.symlink("/bin/sh", "/bin/busybox")
        node = r.find("/bin/sh")
        self.assertIsNotNone(node)
        self.assertEqual(node.symlink_target, "/bin/busybox")

    def test_unlink(self):
        r = VfsRoot()
        r.touch("/tmp/a", data=b"x")
        self.assertTrue(r.unlink("/tmp/a"))
        self.assertIsNone(r.find("/tmp/a"))

    def test_walk_lists_everything(self):
        r = VfsRoot()
        r.mkdir("/etc")
        r.mkdir("/var/log")
        r.touch("/etc/hostname", data=b"x")
        r.touch("/var/log/dmesg.log", data=b"")
        seen = [(path, dirs, files) for path, dirs, files in r.walk("/")]
        self.assertTrue(
            any(dirs == [] and files == ["hostname"] for _, dirs, files in seen)
        )


# ---------------------------------------------------------------------------
# ramdisk
# ---------------------------------------------------------------------------

class TestRamDisk(unittest.TestCase):
    def _make_disk(self) -> RamDisk:
        return RamDisk(name="test", max_bytes=8 * 1024 * 1024)

    def test_load_and_extract(self):
        disk = self._make_disk()
        entries = [newc_dir("etc"), newc_file("/etc/hostname", b"umer-os\n")]
        disk.load(pack_archive(entries))
        disk.extract()
        self.assertEqual(disk.state, RamDiskState.EXTRACTED)
        self.assertIsNotNone(disk.find("/etc/hostname"))

    def test_full_lifecycle(self):
        disk = self._make_disk()
        disk.load(pack_archive([newc_file("/init", b"#!x\n")]))
        disk.extract()
        disk.mount("/")
        disk.pivot()
        disk.release()
        self.assertEqual(disk.state, RamDiskState.RELEASED)

    def test_extract_requires_loaded(self):
        disk = self._make_disk()
        with self.assertRaises(RuntimeError):
            disk.extract()

    def test_add_file_updates_stats(self):
        disk = self._make_disk()
        disk.populate([])
        disk.add_file("/etc/hostname", b"hello world\n")
        self.assertEqual(disk.stats.file_count, 1)
        self.assertEqual(disk.stats.extracted_bytes, len(b"hello world\n"))

    def test_too_big_raises(self):
        disk = self._make_disk()
        with self.assertRaises(MemoryError):
            disk.load(b"x" * (disk.max_bytes + 1))

    def test_read_only_flag(self):
        disk = self._make_disk()
        disk.load(pack_archive([newc_file("/init", b"#!/bin/sh\n")]))
        disk.extract()
        disk.mount("/", read_only=True)
        self.assertTrue(disk.read_only)
        disk.mount("/", read_only=False)
        self.assertFalse(disk.read_only)

    def test_has_mount_table(self):
        disk = self._make_disk()
        self.assertIsNotNone(disk.mount_table)
        self.assertEqual(disk.mount_table.list(), [])

    def test_snapshot_round_trip(self):
        with tempfile_TmpDir() as tmp:
            disk = self._make_disk()
            disk.load(pack_archive([
                newc_dir("etc"),
                newc_file("etc/hostname", b"umer-os\n"),
            ]))
            disk.extract()
            # Mutate the VFS - add a marker file the original cpio
            # did not have.
            disk.add_file("/etc/extra", b"added at boot\n", mode=0o644)
            raw = disk.snapshot_to_image()
            self.assertIn(b"umer-os\n", raw)
            self.assertIn(b"added at boot", raw)
            # Snapshot must be a valid cpio archive.
            entries = {e.name for e in unpack_archive(raw)}
            self.assertIn("etc/hostname", entries)
            self.assertIn("etc/extra", entries)
            # write_snapshot should produce a gzipped file on disk.
            out = tmp / "initramfs-snapshot.img.gz"
            disk.write_snapshot(str(out), archiver="gzip")
            self.assertTrue(out.is_file())
            self.assertGreater(out.stat().st_size, 0)
            self.assertTrue(detect_archiver(out.read_bytes()) is GzipArchiver)


# ---------------------------------------------------------------------------
# hooks
# ---------------------------------------------------------------------------

class TestHooks(unittest.TestCase):
    def test_run_in_order(self):
        mgr = HookManager()
        events = []
        mgr.add(HookPoint.PRE_LOAD, lambda c: events.append("a"))
        mgr.add(HookPoint.PRE_LOAD, lambda c: events.append("b"))
        mgr.add(HookPoint.POST_LOAD, lambda c: events.append("c"))
        mgr.run(HookPoint.PRE_LOAD)
        mgr.run(HookPoint.POST_LOAD)
        self.assertEqual(events, ["a", "b", "c"])

    def test_async_hook(self):
        mgr = HookManager()
        events = []

        async def h(ctx):
            events.append("async")
            await asyncio.sleep(0)

        async def runner():
            await mgr.run_async(HookPoint.PRE_LOAD)

        mgr.add(HookPoint.PRE_LOAD, h)
        asyncio.run(runner())
        self.assertEqual(events, ["async"])

    def test_abort_stops_run(self):
        mgr = HookManager()
        mgr.add(HookPoint.PRE_LOAD, lambda c: mgr.abort("nope"))
        mgr.add(HookPoint.PRE_LOAD, lambda c: self.fail("should not run"))
        with self.assertRaises(HookAbort):
            mgr.run(HookPoint.PRE_LOAD)

    def test_custom_point(self):
        mgr = HookManager()
        mgr.define("after_kernel")
        mgr.add("after_kernel", lambda c: None, name="myhook")
        hooks = mgr.list("after_kernel")
        self.assertEqual(len(hooks), 1)
        self.assertEqual(hooks[0], "myhook")


# ---------------------------------------------------------------------------
# phase_machine
# ---------------------------------------------------------------------------

class TestPhaseMachine(unittest.TestCase):
    def test_start_to_first_phase(self):
        pm = PhaseMachine()
        rec = pm.begin_phase()
        self.assertEqual(rec.phase, BootPhase.PHASE_1_LOAD)
        pm.finish_phase(rec)
        self.assertEqual(pm.phase, BootPhase.PHASE_2_CONVERT)

    def test_invalid_transition_raises(self):
        pm = PhaseMachine()
        with self.assertRaises(RuntimeError):
            pm.transition(BootPhase.PHASE_5_MOUNT_REAL)

    def test_full_walk_to_completed(self):
        pm = PhaseMachine()
        for _ in range(9):
            rec = pm.begin_phase()
            pm.finish_phase(rec)
        self.assertEqual(pm.phase, BootPhase.COMPLETED)

    def test_failure_records(self):
        pm = PhaseMachine()
        rec = pm.begin_phase()
        pm.finish_phase(rec, outcome=PhaseOutcome.FAILED, error="boom")
        self.assertEqual(pm.phase, BootPhase.FAILED)
        self.assertTrue(any(r.error == "boom" for r in pm.history))

    def test_skip_phase(self):
        pm = PhaseMachine()
        rec1 = pm.begin_phase()
        pm.finish_phase(rec1)
        skip = pm.skip_phase("not needed")
        self.assertEqual(skip.outcome, PhaseOutcome.SKIPPED)
        # The skipped phase should still have been entered
        self.assertNotEqual(pm.phase, BootPhase.FAILED)


# ---------------------------------------------------------------------------
# pivot_root
# ---------------------------------------------------------------------------

class TestPivotRoot(unittest.TestCase):
    def test_swap_promotes_new(self):
        old = VfsRoot(); old.touch("/bin/old", data=b"OLD")
        new = VfsRoot(); new.touch("/bin/new", data=b"NEW")
        result = pivot_root(old, new, new_root_path="/newroot",
                            put_old_path="/newroot/initrd")
        self.assertTrue(result.swapped)
        self.assertIsNotNone(old.find("/bin/new"))

    def test_same_tree_raises(self):
        tree = VfsRoot()
        with self.assertRaises(PivotRootError):
            pivot_root(tree, tree)

    def test_same_path_raises(self):
        old = VfsRoot(); new = VfsRoot()
        with self.assertRaises(PivotRootError):
            pivot_root(old, new, new_root_path="/x", put_old_path="/x")


# ---------------------------------------------------------------------------
# module_resolver
# ---------------------------------------------------------------------------

class TestModuleResolver(unittest.TestCase):
    def test_user_explicit(self):
        r = ModuleResolver()
        specs = r.from_user_config(["ext4", "ahci", "missing"])
        names = {s.name for s in specs}
        self.assertTrue({"ext4", "ahci"}.issubset(names))
        self.assertNotIn("missing", names)

    def test_autoprobe_empty_when_no_sys(self):
        with tempfile_TmpDir() as tmp:
            r = ModuleResolver()
            self.assertEqual(r.autoprobe(host_root=str(tmp)), [])

    def test_hybrid_combines(self):
        r = ModuleResolver()
        r.from_user_config(["ext4"])
        r.hybrid(extras=["ahci"])
        names = {s.name for s in r.list_selected()}
        self.assertTrue({"ext4", "ahci"}.issubset(names))

    def test_export_is_jsonable(self):
        r = ModuleResolver()
        r.from_user_config(["ext4"])
        text = r.to_json()
        loaded = json.loads(text)
        self.assertIsInstance(loaded, list)
        self.assertEqual(loaded[0]["name"], "ext4")

    def test_detect_rootfstype(self):
        self.assertEqual(detect_rootfstype("TYPE=\"ext4\""), "ext4")
        self.assertIsNone(detect_rootfstype(""))


# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------

class TestScenarios(unittest.TestCase):
    def test_catalogue_has_all(self):
        s = {s.value for s in list_scenarios()}
        for k in ("normal", "install", "recovery", "live", "rescue", "per_machine"):
            self.assertIn(k, s)

    def test_get_scenario_unknown(self):
        with self.assertRaises(KeyError):
            get_scenario("not-a-real-id")

    def test_normal_has_ext4(self):
        s = get_scenario(ScenarioId.NORMAL)
        self.assertIn("ext4", s.extra_modules)

    def test_live_keeps_root(self):
        s = get_scenario(ScenarioId.LIVE)
        self.assertTrue(s.keep_as_root)
        runner = ScenarioRunner(s)
        self.assertTrue(runner.should_keep_as_root())

    def test_build_entries_includes_extras(self):
        s = get_scenario(ScenarioId.NORMAL)
        out = s.build_entries([])
        self.assertTrue(any(e.name == "/etc/hostname" for e in out))


# ---------------------------------------------------------------------------
# ai_helper
# ---------------------------------------------------------------------------

class TestAIHelper(unittest.TestCase):
    def test_suggest_modules_returns_known(self):
        h = AIHelper()
        out = h.suggest_modules(["ext4"], top_k=3)
        # Whatever it returns must come from the resolver's DB or
        # from the rule-based "paired with" suggestions.
        from initrd.module_resolver import DEFAULT_MODULE_DB
        paired = {"mbcache", "jbd2", "crc32c", "dm_mod", "nvme_core",
                  "libahci", "virtio", "zstd", "xor"}
        for s in out:
            self.assertTrue(s.name in DEFAULT_MODULE_DB or s.name in paired)

    def test_score_scenario_empty(self):
        h = AIHelper()
        self.assertEqual(h.score_scenario({}), 0.5)

    def test_score_scenario_installer(self):
        h = AIHelper()
        s = h.score_scenario({"installer_signature_found": 1.0})
        self.assertGreater(s, 0.5)

    def test_entropy_bytes(self):
        h = AIHelper()
        b = h.entropy_bytes(32)
        self.assertIsInstance(b, bytes)
        self.assertEqual(len(b), 32)


# ---------------------------------------------------------------------------
# builder
# ---------------------------------------------------------------------------

class TestBuilder(unittest.TestCase):
    def test_build_gz(self):
        with tempfile_TmpDir() as tmp:
            out = tmp / "initramfs.img.gz"
            req = BuildRequest(
                kernel_version="6.6.0-umeros",
                scenario=ScenarioId.NORMAL,
                output_format=OutputFormat.CPIO_GZ,
                output_path=str(out),
            )
            result = InitrdBuilder().build(req)
            self.assertTrue(out.is_file())
            self.assertGreater(result.entry_count, 0)
            self.assertTrue(out.with_suffix(out.suffix + ".json").is_file())

    def test_build_xz(self):
        with tempfile_TmpDir() as tmp:
            out = tmp / "initramfs.img.xz"
            req = BuildRequest(
                kernel_version="6.6.0-umeros",
                output_format=OutputFormat.CPIO_XZ,
                output_path=str(out),
            )
            result = InitrdBuilder().build(req)
            with out.open("rb") as f:
                head = f.read(6)
            self.assertTrue(head.startswith(XzArchiver.magic))
            self.assertEqual(result.archiver, "xz")

    def test_build_directory(self):
        with tempfile_TmpDir() as tmp:
            out = tmp / "initrd-tree"
            req = BuildRequest(
                kernel_version="6.6.0-umeros",
                output_format=OutputFormat.DIRECTORY,
                output_path=str(out),
            )
            InitrdBuilder().build(req)
            self.assertTrue(out.is_dir())
            self.assertTrue((out / "init").is_file())

    def test_roundtrip_request_json(self):
        req = BuildRequest(
            kernel_version="6.6.0-umeros",
            scenario=ScenarioId.LIVE,
            extra_files={"/etc/issue": b"umer-os\n"},
        )
        text = req.to_json()
        rt = BuildRequest.from_json(text)
        self.assertEqual(rt.kernel_version, req.kernel_version)
        self.assertEqual(rt.scenario, req.scenario)
        self.assertEqual(rt.extra_files, req.extra_files)


# ---------------------------------------------------------------------------
# linuxrc (end-to-end)
# ---------------------------------------------------------------------------

class TestLinuxrc(unittest.TestCase):
    def test_default_boot_runs(self):
        with tempfile_TmpDir() as tmp:
            entries = [newc_dir("bin"), newc_file("/init", b"#!/bin/sh\n")]
            ctx = BootContext.from_request(
                BuildRequest(kernel_version="test", scenario=ScenarioId.NORMAL),
                blob=pack_archive(entries),
                host_root=str(tmp),
            )
            code = linuxrc_run(ctx)
            self.assertEqual(code, 0)
            self.assertEqual(ctx.ramdisk.state, RamDiskState.RELEASED)

    def test_hooks_fire(self):
        events: list = []
        ctx = BootContext.default_demo()
        ctx.hooks.add(HookPoint.POST_EXTRACT, lambda c: events.append("post_extract"))
        ctx.hooks.add(HookPoint.PRE_PIVOT_ROOT, lambda c: events.append("pre_pivot"))
        linuxrc_run(ctx)
        self.assertIn("post_extract", events)
        # The pivot step is only relevant when the scenario does not
        # keep the initrd as root.
        self.assertIn("pre_pivot", events)

    def test_ai_suggester_called(self):
        ctx = BootContext.default_demo()
        called = []
        original = ctx.ai.suggest_modules
        def spy(base, host_root="/", top_k=5):
            called.append(base)
            return original(base, host_root, top_k)
        ctx.ai.suggest_modules = spy  # type: ignore[method-assign]
        linuxrc_run(ctx)
        self.assertTrue(called, "AI helper should have been consulted at least once")

    def test_context_has_pid1_handler(self):
        ctx = BootContext.default_demo()
        self.assertIsInstance(ctx.signal_handler, PID1SignalHandler)
        self.assertEqual(ctx.effective_uid, 0)  # recorded contract value
        # BootContext comes with a default reap handler so zombies
        # produced during the boot are reaped.
        self.assertTrue(ctx.signal_handler.reap(123))
        self.assertIn(123, ctx.signal_handler.reaped())

    def test_context_has_mount_table(self):
        ctx = BootContext.default_demo()
        self.assertIsInstance(ctx.mount_table, MountTable)

    def test_install_scenario_chroots(self):
        from initrd.builder import BuildRequest
        from initrd.cpio import pack_archive, newc_dir, newc_file
        from initrd.scenarios import ScenarioId
        with tempfile_TmpDir() as tmp:
            entries = [newc_dir("bin"), newc_file("/init", b"#!/bin/sh\n")]
            ctx = BootContext.from_request(
                BuildRequest(kernel_version="install-test",
                             scenario=ScenarioId.INSTALL),
                blob=pack_archive(entries),
                host_root=str(tmp),
            )
            linuxrc_run(ctx)
            # The install scenario chroots into /newroot during
            # phase 5b; it is undone before phase 6 (which is
            # skipped because install keeps the initrd as root).
            self.assertIsNone(ctx.chroot_ctx,
                              "install chroot must be undone before pivot")
            # The mount table records the real-root mount.
            newroot = ctx.mount_table.find("/newroot")
            self.assertIsNotNone(newroot)
            self.assertEqual(newroot.fstype, FilesystemType.EXT4)
            # The /dev, /proc, /sys pseudo filesystems were mounted.
            mp = {m.mount_point: m for m in ctx.mount_table.list()}
            self.assertIn("/dev", mp)
            self.assertIn("/proc", mp)
            self.assertIn("/sys", mp)


# ---------------------------------------------------------------------------
# ai_helper history log (H2 / H91 - code injection via eval)
# ---------------------------------------------------------------------------

class TestAIHelperHistorySafety(unittest.TestCase):
    """The boot history log must be parsed safely, never with eval()."""

    def _history_path(self, root: Path) -> Path:
        p = root / "var" / "log" / "umeros_initrd_history.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def test_load_history_parses_dict_literals(self):
        with tempfile_TmpDir() as tmp:
            hist = self._history_path(tmp)
            hist.write_text(
                '{"modules": ["ext4", "nvme"]}\n'
                '{"modules": ["btrfs"]}\n',
                encoding="utf-8",
            )
            loaded = AIHelper()._load_history(str(tmp))
            self.assertEqual(
                loaded,
                [{"modules": ["ext4", "nvme"]}, {"modules": ["btrfs"]}],
            )

    def test_load_history_rejects_code_injection(self):
        with tempfile_TmpDir() as tmp:
            sentinel = tmp / "PWNED_BY_EVAL.txt"
            hist = self._history_path(tmp)
            # A malicious history line that eval() WOULD execute (creating the
            # sentinel file).  literal_eval refuses it, so it must be skipped.
            payload = (
                '__import__("pathlib").Path(r"%s").write_text("pwned")'
                % str(sentinel)
            )
            hist.write_text(
                '{"modules": ["ext4"]}\n' + payload + "\n",
                encoding="utf-8",
            )
            loaded = AIHelper()._load_history(str(tmp))
            # The legitimate dict is kept; the injection line never ran.
            self.assertEqual(loaded, [{"modules": ["ext4"]}])
            self.assertFalse(
                sentinel.exists(),
                "malicious history line executed code (eval injection not fixed)",
            )


# ---------------------------------------------------------------------------
# builder cpio unpack (H93 - directory traversal on unpack)
# ---------------------------------------------------------------------------

class TestBuilderCpioTraversal(unittest.TestCase):
    """_unpack_to_dir must reject cpio entries that escape the target."""

    @staticmethod
    def _raw_with(*entries):
        return pack_archive(list(entries))

    def test_unpack_rejects_parent_traversal(self):
        with tempfile_TmpDir() as tmp:
            target = tmp / "tree"
            raw = self._raw_with(
                newc_dir("."),
                newc_file("etc/hostname", b"ok"),
                newc_file("../evil.txt", b"PWNED"),
            )
            InitrdBuilder()._unpack_to_dir(raw, target)
            # Benign entry written...
            self.assertTrue((target / "etc" / "hostname").is_file())
            self.assertEqual((target / "etc" / "hostname").read_bytes(), b"ok")
            # ...but the traversal entry must NOT appear outside the target.
            self.assertFalse((target.parent / "evil.txt").exists())

    def test_unpack_rejects_nested_traversal(self):
        with tempfile_TmpDir() as tmp:
            target = tmp / "tree"
            raw = self._raw_with(newc_file("etc/../../pwned", b"x"))
            InitrdBuilder()._unpack_to_dir(raw, target)
            self.assertFalse((target.parent / "pwned").exists())

    def test_unpack_normal_tree_written(self):
        with tempfile_TmpDir() as tmp:
            target = tmp / "tree"
            raw = self._raw_with(
                newc_dir("bin"),
                newc_file("bin/sh", b"#!/bin/sh\n", mode=0o755),
                newc_symlink("bin/ash", "bin/sh"),
            )
            InitrdBuilder()._unpack_to_dir(raw, target)
            self.assertTrue((target / "bin" / "sh").is_file())
            self.assertTrue((target / "bin" / "ash").is_symlink())


# ---------------------------------------------------------------------------
# linuxrc privileged boot op (H92 - seteuid(0) capability gate)
# ---------------------------------------------------------------------------

class TestDropToRootCapGate(unittest.TestCase):
    """Acquiring uid 0 is gated behind CAP_SYS_ADMIN (fail-closed)."""

    def setUp(self):
        # Start from the historical default: no trust source wired, non-strict.
        _cap_gate.unwire()
        _cap_gate.set_strict(False)

    def tearDown(self):
        _cap_gate.unwire()
        _cap_gate.set_strict(False)

    def test_default_permissive_returns_uid(self):
        # With no manager wired the gate is permissive -> no exception.
        self.assertIsInstance(_drop_to_root(), int)

    def test_strict_mode_denies_seteuid(self):
        _cap_gate.set_strict(True)
        with self.assertRaises(PermissionError):
            _drop_to_root()

    def test_boot_aborts_without_capability(self):
        # Integration: a boot with strict mode must fail closed (the privileged
        # drop-to-root is refused) instead of proceeding as a non-privileged
        # PID 1.
        with tempfile_TmpDir() as tmp:
            _cap_gate.set_strict(True)
            try:
                ctx = BootContext.default_demo()
                ctx.host_root = str(tmp)
                code = linuxrc_run(ctx)
                self.assertNotEqual(code, 0)
            finally:
                _cap_gate.set_strict(False)


# ---------------------------------------------------------------------------
# mounts
# ---------------------------------------------------------------------------

class TestMounts(unittest.TestCase):
    def test_basic_mount(self):
        table = MountTable()
        mount(table, device="/dev/sda1", fstype=FilesystemType.EXT4,
              mount_point="/newroot", flags=[MountFlag.RDONLY])
        rec = table.find("/newroot")
        self.assertIsNotNone(rec)
        self.assertTrue(rec.is_read_only)

    def test_replace_existing(self):
        table = MountTable()
        mount(table, device="/dev/sda1", fstype=FilesystemType.EXT4,
              mount_point="/newroot")
        mount(table, device="/dev/sda2", fstype=FilesystemType.EXT4,
              mount_point="/newroot")
        rec = table.find("/newroot")
        self.assertEqual(rec.device, "/dev/sda2")
        self.assertEqual(len(table.list()), 1)

    def test_unmount(self):
        table = MountTable()
        mount(table, device="/dev/sda1", fstype=FilesystemType.EXT4,
              mount_point="/newroot")
        self.assertTrue(unmount(table, "/newroot"))
        self.assertIsNone(table.find("/newroot"))

    def test_as_lines_matches_proc_mounts_shape(self):
        table = MountTable()
        mount(table, device="proc", fstype=FilesystemType.PROC,
              mount_point="/proc")
        line = table.as_lines()[0]
        # device mount-point fstype options dump pass fsckpass
        parts = line.split()
        self.assertEqual(parts[0], "proc")
        self.assertEqual(parts[1], "/proc")
        self.assertEqual(parts[2], "proc")

    def test_chroot_round_trip(self):
        root = VfsRoot()
        root.mkdir("/proc")
        root.touch("/proc/version", data=b"umer-os\n")
        ctx = chroot_into(root, "/proc")
        try:
            # Inside the chroot, /proc/version is what /version resolves to.
            # resolve_in_chroot translates back to the outside view.
            self.assertEqual(resolve_in_chroot(ctx, "/version"), "/proc/version")
        finally:
            chroot_undo(ctx)

    def test_chroot_rejects_non_dir(self):
        root = VfsRoot()
        root.touch("/file", data=b"x")
        with self.assertRaises(NotADirectoryError):
            chroot_into(root, "/file")

    def test_populate_dev_creates_nodes(self):
        with tempfile_TmpDir() as tmp:
            root = VfsRoot()
            n = populate_dev(root)
            self.assertGreaterEqual(n, 5)  # null, zero, random, urandom, tty, ...
            self.assertTrue(root.exists("/dev/null"))
            self.assertTrue(root.exists("/dev/zero"))
            self.assertTrue(root.exists("/dev/urandom"))

    def test_dev_read_semantics(self):
        root = VfsRoot()
        populate_dev(root)
        self.assertEqual(dev_read(root, "/dev/null", 16), b"")
        self.assertEqual(dev_read(root, "/dev/zero", 8), b"\x00" * 8)
        self.assertEqual(len(dev_read(root, "/dev/urandom", 12)), 12)
        with self.assertRaises(IOError):
            dev_read(root, "/dev/full", 1)

    def test_mount_proc_creates_well_known_files(self):
        table = MountTable()
        root = VfsRoot()
        mount_proc(table, root, mount_point="/proc")
        self.assertTrue(root.exists("/proc/version"))
        self.assertTrue(root.exists("/proc/uptime"))
        self.assertTrue(root.exists("/proc/loadavg"))
        self.assertTrue(root.exists("/proc/meminfo"))
        self.assertTrue(root.exists("/proc/mounts"))

    def test_mount_sys_creates_block_and_firmware(self):
        table = MountTable()
        root = VfsRoot()
        mount_sys(table, root, mount_point="/sys")
        self.assertTrue(root.exists("/sys/block"))
        self.assertTrue(root.exists("/sys/firmware/efi"))

    def test_mount_dev_populates(self):
        table = MountTable()
        root = VfsRoot()
        mount_dev(table, root, mount_point="/dev")
        self.assertTrue(root.exists("/dev/null"))


# ---------------------------------------------------------------------------
# signals (PID 1 layer)
# ---------------------------------------------------------------------------

class TestPID1SignalHandler(unittest.TestCase):
    def test_direct_registration(self):
        h = PID1SignalHandler()
        events = []
        h.on(InitSignal.SIGUSR1, lambda pid: events.append(pid))
        h.dispatch(InitSignal.SIGUSR1, pid=42)
        self.assertEqual(events, [42])

    def test_decorator_registration(self):
        h = PID1SignalHandler()
        events = []

        @h.on(InitSignal.SIGUSR1)
        def _reload(pid: int) -> None:
            events.append(pid)

        h.dispatch(InitSignal.SIGUSR1, pid=99)
        self.assertEqual(events, [99])

    def test_reap_default(self):
        h = PID1SignalHandler()
        self.assertTrue(h.reap(7))
        self.assertIn(7, h.reaped())

    def test_reap_with_handler(self):
        h = PID1SignalHandler()
        h.on_reap(lambda pid: pid != 5)
        self.assertTrue(h.reap(7))
        self.assertFalse(h.reap(5))
        self.assertIn(7, h.reaped())
        self.assertNotIn(5, h.reaped())

    def test_exit_signal_marks_should_exit(self):
        h = PID1SignalHandler()
        h.dispatch(InitSignal.SIGTERM, pid=99)
        self.assertTrue(h.should_exit)
        self.assertIsNotNone(h.exit_code)
        self.assertNotEqual(h.exit_code, 0)

    def test_ignore_signal_does_not_exit(self):
        h = PID1SignalHandler()
        h.dispatch(InitSignal.SIGUSR1, pid=99)
        self.assertFalse(h.should_exit)

    def test_install_without_env_noop(self):
        h = PID1SignalHandler()
        # Default env var unset -> install() should refuse.
        self.assertFalse(h.install())

    def test_history_serialisable(self):
        h = PID1SignalHandler()
        h.dispatch(InitSignal.SIGUSR1, pid=1)
        h.dispatch(InitSignal.SIGTERM, pid=1)
        hist = h.history()
        self.assertEqual(len(hist), 2)
        import json
        # All entries must round-trip through json.
        json.dumps(hist)


# ---------------------------------------------------------------------------
# Stdlib helper - lightweight per-test temp dir
# ---------------------------------------------------------------------------

import contextlib
import tempfile as _tempfile

@contextlib.contextmanager
def tempfile_TmpDir():
    d = Path(_tempfile.mkdtemp(prefix="initrd-test-"))
    try:
        yield d
    finally:
        # Best-effort cleanup; the OS will sweep the temp dir eventually.
        try:
            for child in d.glob("*"):
                try:
                    if child.is_file() or child.is_symlink():
                        child.unlink()
                    else:
                        for sub in child.glob("**/*"):
                            if sub.is_file() or sub.is_symlink():
                                sub.unlink()
                except OSError:
                    pass
            try:
                d.rmdir()
            except OSError:
                pass
        except OSError:
            pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
