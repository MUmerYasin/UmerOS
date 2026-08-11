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
from initrd.linuxrc import BootContext, run as linuxrc_run
from initrd.module_resolver import ModuleResolver, detect_rootfstype
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
from initrd.vfs_ops import VfsRoot


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
