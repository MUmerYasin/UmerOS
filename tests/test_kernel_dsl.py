"""Tests for UmerOS Type-Safe Kernel Extension DSL."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sdk.kernel_dsl.types import Result, Success, Failure, Option, Some, None_
from sdk.kernel_dsl.extension_base import KernelExtension, system_capability


class TestResultType(unittest.TestCase):
    def test_success(self):
        r = Success(42)
        self.assertTrue(r.is_success())
        self.assertFalse(r.is_failure())
        self.assertEqual(r.unwrap(), 42)

    def test_failure(self):
        r = Failure("error")
        self.assertFalse(r.is_success())
        self.assertTrue(r.is_failure())
        with self.assertRaises(RuntimeError):
            r.unwrap()

    def test_unwrap_or(self):
        self.assertEqual(Success(42).unwrap_or(0), 42)
        self.assertEqual(Failure("err").unwrap_or(0), 0)

    def test_map(self):
        r = Success(5).map(lambda x: x * 2)
        self.assertEqual(r.unwrap(), 10)

    def test_map_on_failure(self):
        r = Failure("err").map(lambda x: x * 2)
        self.assertTrue(r.is_failure())


class TestOptionType(unittest.TestCase):
    def test_some(self):
        o = Some(42)
        self.assertTrue(o.is_some())
        self.assertFalse(o.is_none())
        self.assertEqual(o.unwrap(), 42)

    def test_none(self):
        o = None_()
        self.assertFalse(o.is_some())
        self.assertTrue(o.is_none())
        with self.assertRaises(RuntimeError):
            o.unwrap()

    def test_unwrap_or(self):
        self.assertEqual(Some(42).unwrap_or(0), 42)
        self.assertEqual(None_().unwrap_or(0), 0)


class TestKernelExtension(unittest.TestCase):
    def test_register_unregister(self):
        ext = KernelExtension("test_ext", capabilities={"test.read"})
        self.assertFalse(ext.is_registered)
        self.assertTrue(ext.register())
        self.assertTrue(ext.is_registered)
        self.assertFalse(ext.register())  # Already registered
        self.assertTrue(ext.unregister())
        self.assertFalse(ext.is_registered)

    def test_capability_check(self):
        ext = KernelExtension("test_ext", capabilities={"cap.read"})
        self.assertTrue(ext.has_capability("cap.read"))
        self.assertFalse(ext.has_capability("cap.write"))
        ext.grant_capability("cap.write")
        self.assertTrue(ext.has_capability("cap.write"))
        ext.revoke_capability("cap.write")
        self.assertFalse(ext.has_capability("cap.write"))

    def test_system_capability_decorator(self):
        class MyExt(KernelExtension):
            def __init__(self):
                super().__init__("my_ext", capabilities={"sys.read"})

            @system_capability("sys.read")
            def do_read(self) -> str:
                return "data"

            @system_capability("sys.write")
            def do_write(self) -> str:
                return "written"

        ext = MyExt()
        self.assertEqual(ext.do_read(), "data")
        with self.assertRaises(PermissionError):
            ext.do_write()

    def test_validate_types(self):
        class GoodExt(KernelExtension):
            def __init__(self):
                super().__init__("good_ext")

            def process(self, data: str) -> int:
                return 42

        ext = GoodExt()
        errors = ext.validate_types()
        self.assertEqual(errors, [])

    def test_repr(self):
        ext = KernelExtension("test", capabilities={"a"})
        r = repr(ext)
        self.assertIn("test", r)


class TestPluginRunner(unittest.TestCase):
    def test_run_extension(self):
        from kernel.plugin_runner import PluginRunner
        ext = KernelExtension("runner_test", capabilities={"test.read"})
        ext.register()

        @system_capability("test.read")
        def hello(self) -> str:
            return "world"

        # Monkey-patch method
        ext.hello = hello.__get__(ext, type(ext))
        runner = PluginRunner()
        result = runner.run_extension("runner_test", "hello")
        self.assertEqual(result, "world")

    def test_unregistered_extension(self):
        from kernel.plugin_runner import PluginRunner
        runner = PluginRunner()
        with self.assertRaises(RuntimeError):
            runner.run_extension("nonexistent", "method")

    def test_missing_method(self):
        from kernel.plugin_runner import PluginRunner
        ext = KernelExtension("missing_method_ext")
        ext.register()
        runner = PluginRunner()
        with self.assertRaises(AttributeError):
            runner.run_extension("missing_method_ext", "nonexistent_method")


if __name__ == "__main__":
    unittest.main()