"""Tests for Umer OS Compatibility Layer."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

from compatibility.container_engine import (
    ContainerEngine,
    ContainerInstance,
    WineShim,
    AndroidContainer,
    LinuxCompat,
    SyscallTranslator,
    APP_TYPE_LINUX,
    APP_TYPE_WINDOWS,
    APP_TYPE_ANDROID,
)


class TestSyscallTranslator(unittest.TestCase):

    def setUp(self):
        self.trans = SyscallTranslator()

    def test_translate_win32_known_call(self):
        posix, args = self.trans.translate_win32("CreateFile")
        self.assertEqual(posix, "open")
        self.assertIsInstance(args, dict)

    def test_translate_win32_unknown_call(self):
        posix, _ = self.trans.translate_win32("SomeFakeCall")
        self.assertEqual(posix, "UNKNOWN")

    def test_translate_android_known_call(self):
        posix, args = self.trans.translate_android("openFile")
        self.assertEqual(posix, "open")

    def test_translate_android_unknown_call(self):
        posix, _ = self.trans.translate_android("FakeAndroidBinder")
        self.assertEqual(posix, "UNKNOWN")

    def test_translate_with_args(self):
        posix, args = self.trans.translate_win32("ReadFile", {"handle": 3})
        self.assertEqual(args["handle"], 3)

    def test_list_win32_mappings_non_empty(self):
        mappings = self.trans.list_win32_mappings()
        self.assertGreater(len(mappings), 5)
        self.assertIn("CreateFile", mappings)

    def test_list_android_mappings_non_empty(self):
        mappings = self.trans.list_android_mappings()
        self.assertGreater(len(mappings), 3)
        self.assertIn("openFile", mappings)

    def test_all_win32_values_are_strings(self):
        for k, v in self.trans.list_win32_mappings().items():
            self.assertIsInstance(v, str)

    def test_translate_returns_tuple(self):
        result = self.trans.translate_win32("Sleep")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)


class TestContainerInstance(unittest.TestCase):

    def test_container_id_is_hex_string(self):
        inst = ContainerInstance(app_path="/bin/true", app_type=APP_TYPE_LINUX)
        self.assertIsInstance(inst.container_id, str)
        self.assertEqual(len(inst.container_id), 32)  # UUID4 hex

    def test_pid_is_none_without_process(self):
        inst = ContainerInstance(app_path="/app", app_type=APP_TYPE_LINUX)
        self.assertIsNone(inst.pid)

    def test_status_is_stopped_without_process(self):
        inst = ContainerInstance(app_path="/app", app_type=APP_TYPE_LINUX)
        self.assertEqual(inst.status, "stopped")

    def test_is_alive_without_process(self):
        inst = ContainerInstance(app_path="/app")
        self.assertFalse(inst.is_alive())

    def test_resource_usage_returns_dict(self):
        inst = ContainerInstance(app_path="/app")
        usage = inst.resource_usage()
        self.assertIn("container_id", usage)
        self.assertIn("status", usage)
        self.assertIn("uptime_seconds", usage)

    def test_repr_contains_type(self):
        inst = ContainerInstance(app_path="/app", app_type=APP_TYPE_LINUX)
        self.assertIn(APP_TYPE_LINUX, repr(inst))

    def test_terminate_safe_without_process(self):
        inst = ContainerInstance(app_path="/app")
        inst.terminate()  # must not raise

    def test_kill_safe_without_process(self):
        inst = ContainerInstance(app_path="/app")
        inst.kill()  # must not raise


class TestLinuxCompat(unittest.TestCase):

    def test_launch_nonexistent_raises(self):
        lc = LinuxCompat()
        with self.assertRaises(FileNotFoundError):
            lc.launch("/nonexistent/binary")

    @unittest.skipUnless(sys.platform.startswith("linux") or
                         sys.platform == "darwin", "Requires POSIX shell")
    def test_launch_true_command(self):
        true_cmd = "/bin/true"
        if not os.path.isfile(true_cmd):
            self.skipTest("/bin/true not found")
        lc = LinuxCompat()
        inst = lc.launch(true_cmd)
        self.assertIsNotNone(inst)
        exit_code = inst.wait(timeout=3.0)
        self.assertEqual(exit_code, 0)


class TestWineShim(unittest.TestCase):

    def test_wine_available_property_is_bool(self):
        wine = WineShim()
        self.assertIsInstance(wine.wine_available, bool)

    def test_run_nonexistent_exe_raises(self):
        wine = WineShim()
        # When Wine is not installed EnvironmentError is raised first;
        # when Wine IS installed but the file is missing, FileNotFoundError.
        with self.assertRaises((FileNotFoundError, EnvironmentError)):
            wine.run("/nonexistent/app.exe")

    def test_run_without_wine_raises_environment_error(self):
        """When wine is explicitly set to None, run() must raise EnvironmentError."""
        wine = WineShim()
        wine._wine = None  # simulate Wine not installed
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            f.write(b"fake exe")
            name = f.name
        try:
            with self.assertRaises(EnvironmentError):
                wine.run(name)
        finally:
            os.unlink(name)

    def test_setup_prefix_creates_directory(self):
        wine = WineShim(wineprefix_base="/tmp/.umer_test_wine")
        prefix = wine.setup_prefix("test_app")
        self.assertTrue(os.path.isdir(prefix))
        # Cleanup
        import shutil
        shutil.rmtree("/tmp/.umer_test_wine", ignore_errors=True)

    def test_list_installed_apps_returns_list(self):
        wine = WineShim(wineprefix_base="/tmp/.umer_test_wine2")
        apps = wine.list_installed_apps()
        self.assertIsInstance(apps, list)
        import shutil
        shutil.rmtree("/tmp/.umer_test_wine2", ignore_errors=True)


class TestAndroidContainer(unittest.TestCase):

    def test_adb_available_property_is_bool(self):
        ac = AndroidContainer()
        self.assertIsInstance(ac.adb_available, bool)

    def test_install_nonexistent_apk_raises(self):
        ac = AndroidContainer()
        with self.assertRaises(FileNotFoundError):
            ac.install_apk("/nonexistent/app.apk")

    def test_install_valid_apk_returns_package_name(self):
        ac = AndroidContainer()
        with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as f:
            f.write(b"PK\x03\x04fake apk data")
            name = f.name
        try:
            pkg = ac.install_apk(name)
            self.assertIsInstance(pkg, str)
            self.assertGreater(len(pkg), 0)
        finally:
            os.unlink(name)

    def test_launch_uninstalled_raises(self):
        ac = AndroidContainer()
        with self.assertRaises(RuntimeError):
            ac.launch_app("com.notinstalled.app")

    def test_launch_installed_returns_instance(self):
        ac = AndroidContainer()
        with tempfile.NamedTemporaryFile(suffix=".apk", delete=False) as f:
            f.write(b"fake apk")
            name = f.name
        try:
            pkg = ac.install_apk(name)
            inst = ac.launch_app(pkg)
            self.assertIsInstance(inst, ContainerInstance)
            self.assertEqual(inst.app_type, APP_TYPE_ANDROID)
        finally:
            os.unlink(name)

    def test_list_installed_returns_list(self):
        ac = AndroidContainer()
        self.assertIsInstance(ac.list_installed(), list)

    def test_bridge_notification_does_not_raise(self):
        ac = AndroidContainer()
        ac.bridge_notification("com.example.app", "Test notification")


class TestContainerEngine(unittest.TestCase):

    def setUp(self):
        self.engine = ContainerEngine(wineprefix_base="/tmp/.umer_ce_test")

    def tearDown(self):
        import shutil
        shutil.rmtree("/tmp/.umer_ce_test", ignore_errors=True)

    def test_detect_type_exe(self):
        self.assertEqual(self.engine.detect_type("myapp.exe"), APP_TYPE_WINDOWS)

    def test_detect_type_apk(self):
        self.assertEqual(self.engine.detect_type("game.apk"), APP_TYPE_ANDROID)

    def test_detect_type_unknown_defaults_to_linux(self):
        self.assertEqual(self.engine.detect_type("program"), APP_TYPE_LINUX)

    def test_detect_type_msi(self):
        self.assertEqual(self.engine.detect_type("setup.msi"), APP_TYPE_WINDOWS)

    def test_launch_nonexistent_raises(self):
        with self.assertRaises((FileNotFoundError, EnvironmentError)):
            self.engine.launch("/nonexistent/app.exe")

    def test_list_containers_empty_initially(self):
        self.assertEqual(self.engine.list_containers(), [])

    def test_stop_unknown_container_returns_false(self):
        self.assertFalse(self.engine.stop("unknown_id"))

    def test_get_status_unknown_returns_none(self):
        self.assertIsNone(self.engine.get_status("unknown_id"))

    def test_wine_property_returns_shim(self):
        self.assertIsInstance(self.engine.wine, WineShim)

    def test_android_property_returns_container(self):
        self.assertIsInstance(self.engine.android, AndroidContainer)

    def test_translator_property_returns_translator(self):
        self.assertIsInstance(self.engine.translator, SyscallTranslator)


if __name__ == "__main__":
    unittest.main()
