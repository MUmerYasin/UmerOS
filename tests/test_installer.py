"""Tests for Umer OS Installer."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

from installer.installer import (
    UmerInstaller,
    InstallLogger,
    EULA_TEXT,
)


class TestInstallLogger(unittest.TestCase):

    def test_record_adds_entry(self):
        logger = InstallLogger(log_path="/tmp/umer_test_install.log")
        logger.record("Test action")
        entries = logger.get_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("Test action", entries[0])

    def test_record_includes_timestamp(self):
        logger = InstallLogger(log_path="/tmp/umer_test_install.log")
        logger.record("timestamped")
        entry = logger.get_entries()[0]
        # Entry must start with [ and contain a timestamp
        self.assertTrue(entry.startswith("["), f"Entry does not start with '[': {entry!r}")
        # Must contain UTC offset indicator: either 'Z' or '+00:00'
        self.assertTrue(
            "Z" in entry or "+00:00" in entry or "UTC" in entry,
            f"No UTC indicator found in: {entry!r}",
        )

    def test_flush_writes_to_disk(self):
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            path = f.name
        try:
            logger = InstallLogger(log_path=path)
            logger.record("written to disk")
            result = logger.flush()
            self.assertTrue(result)
            with open(path) as fh:
                content = fh.read()
            self.assertIn("written to disk", content)
        finally:
            os.unlink(path)

    def test_flush_clears_entries(self):
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            path = f.name
        try:
            logger = InstallLogger(log_path=path)
            logger.record("entry")
            logger.flush()
            self.assertEqual(logger.get_entries(), [])
        finally:
            os.unlink(path)

    def test_get_entries_returns_list(self):
        logger = InstallLogger(log_path="/tmp/test.log")
        self.assertIsInstance(logger.get_entries(), list)

    def test_multiple_records(self):
        logger = InstallLogger(log_path="/tmp/test.log")
        for i in range(5):
            logger.record(f"action {i}")
        self.assertEqual(len(logger.get_entries()), 5)


class TestUmerInstallerEULA(unittest.TestCase):

    def test_eula_text_is_defined(self):
        self.assertIsInstance(EULA_TEXT, str)
        self.assertGreater(len(EULA_TEXT), 100)

    def test_eula_contains_liability_waiver(self):
        self.assertIn("liability", EULA_TEXT.lower())

    def test_eula_contains_warranty_notice(self):
        self.assertIn("warranty", EULA_TEXT.lower())

    def test_eula_contains_data_loss_warning(self):
        self.assertIn("data loss", EULA_TEXT.lower())

    def test_show_eula_non_interactive_returns_false(self):
        """Non-interactive mode: show_eula() must return False (consent denied)."""
        inst = UmerInstaller(interactive=False)
        result = inst.show_eula()
        self.assertFalse(result)


class TestUmerInstallerPlatform(unittest.TestCase):

    def setUp(self):
        self.tmp   = tempfile.mkdtemp()
        self.inst  = UmerInstaller(
            source_dir=self.tmp,
            install_root=os.path.join(self.tmp, "installed"),
            backup_dir=os.path.join(self.tmp, "backup"),
            interactive=False,
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_detect_platform_returns_dict(self):
        info = self.inst.detect_platform()
        self.assertIsInstance(info, dict)

    def test_detect_platform_has_arch(self):
        info = self.inst.detect_platform()
        self.assertIn("arch", info)
        self.assertIsInstance(info["arch"], str)

    def test_detect_platform_has_python_version(self):
        info = self.inst.detect_platform()
        self.assertIn("python_version", info)

    def test_detect_platform_has_os(self):
        info = self.inst.detect_platform()
        self.assertIn("os", info)

    def test_check_prerequisites_passes(self):
        result = self.inst.check_prerequisites()
        self.assertTrue(result)


class TestUmerInstallerBackup(unittest.TestCase):

    def setUp(self):
        self.tmp  = tempfile.mkdtemp()
        self.inst = UmerInstaller(
            source_dir=self.tmp,
            install_root=os.path.join(self.tmp, "installed"),
            backup_dir=os.path.join(self.tmp, "backup"),
            interactive=False,
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_backup_creates_file(self):
        path = self.inst.backup_bootloader()
        self.assertTrue(os.path.isfile(path))

    def test_backup_is_valid_json(self):
        path = self.inst.backup_bootloader()
        with open(path) as fh:
            data = json.load(fh)
        self.assertIn("timestamp", data)
        self.assertIn("platform", data)

    def test_backup_marks_state(self):
        self.inst.backup_bootloader()
        self.assertTrue(self.inst.get_state()["backup_taken"])

    def test_backup_custom_dest(self):
        custom = os.path.join(self.tmp, "custom_backup")
        os.makedirs(custom, exist_ok=True)
        path = self.inst.backup_bootloader(dest=custom)
        self.assertTrue(path.startswith(custom))


class TestUmerInstallerFileCopy(unittest.TestCase):

    def setUp(self):
        self.src  = tempfile.mkdtemp()
        self.dst  = tempfile.mkdtemp()
        self.inst = UmerInstaller(
            source_dir=self.src,
            install_root=self.dst,
            interactive=False,
        )
        # Create some source files
        for name in ("kernel.py", "ai.py", "README.md"):
            with open(os.path.join(self.src, name), "w") as f:
                f.write(f"# {name}")

    def tearDown(self):
        shutil.rmtree(self.src, ignore_errors=True)
        shutil.rmtree(self.dst, ignore_errors=True)

    def test_copy_os_files_copies_all(self):
        n = self.inst.copy_os_files(source=self.src, dest=self.dst)
        self.assertEqual(n, 3)

    def test_copied_files_exist_at_dest(self):
        self.inst.copy_os_files(source=self.src, dest=self.dst)
        self.assertTrue(os.path.isfile(os.path.join(self.dst, "kernel.py")))

    def test_marks_files_copied_state(self):
        self.inst.copy_os_files()
        self.assertTrue(self.inst.get_state()["files_copied"])


class TestUmerInstallerBootloader(unittest.TestCase):

    def setUp(self):
        self.tmp  = tempfile.mkdtemp()
        self.inst = UmerInstaller(
            source_dir=self.tmp,
            install_root=self.tmp,
            interactive=False,
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_install_bootloader_creates_file(self):
        result = self.inst.install_bootloader()
        self.assertTrue(result)
        boot_dir = os.path.join(self.tmp, "boot")
        entry    = os.path.join(boot_dir, "umer_boot_entry.json")
        self.assertTrue(os.path.isfile(entry))

    def test_boot_entry_is_valid_json(self):
        self.inst.install_bootloader()
        entry = os.path.join(self.tmp, "boot", "umer_boot_entry.json")
        with open(entry) as fh:
            data = json.load(fh)
        self.assertIn("label", data)
        self.assertEqual(data["label"], "Umer OS")

    def test_marks_bootloader_state(self):
        self.inst.install_bootloader()
        self.assertTrue(self.inst.get_state()["bootloader_installed"])


class TestUmerInstallerRollback(unittest.TestCase):

    def setUp(self):
        self.src  = tempfile.mkdtemp()
        self.dst  = tempfile.mkdtemp()
        self.inst = UmerInstaller(
            source_dir=self.src,
            install_root=self.dst,
            interactive=False,
        )

    def tearDown(self):
        shutil.rmtree(self.src, ignore_errors=True)
        shutil.rmtree(self.dst, ignore_errors=True)

    def test_rollback_nothing_installed_returns_false(self):
        result = self.inst.rollback()
        self.assertFalse(result)

    def test_rollback_after_copy_removes_install_root(self):
        with open(os.path.join(self.src, "f.py"), "w") as f:
            f.write("pass")
        self.inst.copy_os_files()
        result = self.inst.rollback()
        self.assertTrue(result)
        self.assertFalse(os.path.isdir(self.dst))

    def test_rollback_resets_state(self):
        with open(os.path.join(self.src, "g.py"), "w") as f:
            f.write("pass")
        self.inst.copy_os_files()
        self.inst.rollback()
        state = self.inst.get_state()
        self.assertFalse(state["files_copied"])


class TestUmerInstallerRun(unittest.TestCase):

    def setUp(self):
        self.src  = tempfile.mkdtemp()
        self.dst  = os.path.join(tempfile.gettempdir(), "umer_run_test")
        self.bkp  = os.path.join(tempfile.gettempdir(), "umer_run_bkp")
        # Create a minimal source tree
        with open(os.path.join(self.src, "main.py"), "w") as f:
            f.write("# Umer OS main")

    def tearDown(self):
        shutil.rmtree(self.src, ignore_errors=True)
        shutil.rmtree(self.dst, ignore_errors=True)
        shutil.rmtree(self.bkp, ignore_errors=True)

    def test_run_without_consent_returns_false(self):
        inst = UmerInstaller(
            source_dir=self.src,
            install_root=self.dst,
            backup_dir=self.bkp,
            interactive=False,
        )
        result = inst.run(consent_override=False)
        self.assertFalse(result)

    def test_run_with_consent_override_succeeds(self):
        inst = UmerInstaller(
            source_dir=self.src,
            install_root=self.dst,
            backup_dir=self.bkp,
            interactive=False,
        )
        result = inst.run(consent_override=True)
        self.assertTrue(result)
        self.assertEqual(inst.get_state()["phase"], "complete")

    def test_run_creates_first_boot_config(self):
        inst = UmerInstaller(
            source_dir=self.src,
            install_root=self.dst,
            backup_dir=self.bkp,
            interactive=False,
        )
        inst.run(consent_override=True)
        cfg = os.path.join(self.dst, "config", "first_boot.json")
        self.assertTrue(os.path.isfile(cfg))

    def test_first_boot_config_defaults(self):
        inst = UmerInstaller(
            source_dir=self.src,
            install_root=self.dst,
            backup_dir=self.bkp,
            interactive=False,
        )
        inst.run(consent_override=True)
        cfg = os.path.join(self.dst, "config", "first_boot.json")
        with open(cfg) as fh:
            data = json.load(fh)
        self.assertFalse(data["ai_consent"])
        self.assertFalse(data["telemetry"])
        self.assertTrue(data["first_run"])


if __name__ == "__main__":
    unittest.main()
