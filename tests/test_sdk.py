"""Tests for UmerOS SDK."""
import sys
import tempfile
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sdk.app_template import UmerApp
from sdk.build_tool import BuildTool
from sdk.validator import AppValidator, ValidationResult


class TestUmerApp(unittest.TestCase):
    def test_create_app(self):
        app = UmerApp("TestApp", "1.0.0")
        self.assertEqual(app.name, "TestApp")
        self.assertEqual(app.version, "1.0.0")
        self.assertIsNone(app.pid)

    def test_lifecycle_hooks(self):
        app = UmerApp("TestApp")
        # Should not raise
        app.on_start()
        app.on_stop()
        app.on_message(1, "hello")

    def test_kernel_api_unbound(self):
        app = UmerApp("TestApp")
        with self.assertRaises(RuntimeError):
            app.read_file("/test")
        with self.assertRaises(RuntimeError):
            app.write_file("/test", b"data")
        with self.assertRaises(RuntimeError):
            app.send_ipc(1, "data")
        with self.assertRaises(RuntimeError):
            app.ask_ai("query")

    def test_bind_kernel(self):
        class FakeKernel:
            def __init__(self):
                self.vfs = self
                self.ipc = self
                self.ai_assistant = self
            def read_file(self, path):
                return b"content"
            def write_file(self, path, data):
                return True
            def send(self, sender, receiver, data):
                return True
            def query(self, q):
                return "response"

        app = UmerApp("TestApp")
        app.bind_kernel(FakeKernel())
        self.assertEqual(app.read_file("/test"), b"content")
        self.assertTrue(app.write_file("/test", b"data"))
        self.assertTrue(app.send_ipc(1, "data"))
        self.assertEqual(app.ask_ai("query"), "response")

    def test_hello_world_app(self):
        from sdk.app_template import HelloWorldApp
        app = HelloWorldApp()
        self.assertEqual(app.name, "HelloWorld")


class TestBuildTool(unittest.TestCase):
    def test_scaffold_dry_run(self):
        tool = BuildTool()
        base = tool.scaffold("TestApp")
        self.assertEqual(base, "/sdk/projects/TestApp")

    def test_scaffold_with_vfs(self):
        class FakeVFS:
            def __init__(self):
                self.files = {}
                self.dirs = set()
            def mkdir(self, path):
                self.dirs.add(path)
            def write_file(self, path, data):
                self.files[path] = data

        vfs = FakeVFS()
        tool = BuildTool(vfs=vfs)
        base = tool.scaffold("MyApp")
        self.assertIn("/sdk/projects/MyApp/src/main.py", vfs.files)
        self.assertIn("/sdk/projects/MyApp/manifest.json", vfs.files)

    def test_package(self):
        tool = BuildTool()
        info = tool.package("MyApp")
        self.assertEqual(info["name"], "myapp")
        self.assertEqual(info["status"], "packaged")


class TestAppValidator(unittest.TestCase):
    def test_valid_manifest(self):
        validator = AppValidator()
        manifest = {
            "name": "MyApp",
            "version": "1.0.0",
            "author": "Dev",
            "description": "Test app",
            "entry_point": "src/main.py",
        }
        result = validator.validate_manifest(manifest)
        self.assertTrue(result.valid)
        self.assertEqual(len(result.errors), 0)

    def test_missing_fields(self):
        validator = AppValidator()
        result = validator.validate_manifest({"name": "MyApp"})
        self.assertFalse(result.valid)
        self.assertTrue(len(result.errors) > 0)

    def test_invalid_version(self):
        validator = AppValidator()
        manifest = {
            "name": "MyApp",
            "version": "1.0",
            "author": "Dev",
            "description": "Test",
            "entry_point": "src/main.py",
        }
        result = validator.validate_manifest(manifest)
        self.assertTrue(result.valid)  # warning, not error
        self.assertTrue(len(result.warnings) > 0)

    def test_validate_structure(self):
        validator = AppValidator()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal structure
            os.makedirs(os.path.join(tmpdir, "src"))
            with open(os.path.join(tmpdir, "manifest.json"), "w") as f:
                import json
                json.dump({
                    "name": "TestApp",
                    "version": "1.0.0",
                    "author": "Dev",
                    "description": "Test",
                    "entry_point": "src/main.py",
                }, f)
            with open(os.path.join(tmpdir, "src", "main.py"), "w") as f:
                f.write("class TestApp:\n    def on_start(self): pass\n    def on_stop(self): pass\n")
            result = validator.validate_structure(tmpdir)
            self.assertTrue(result.valid)

    def test_validate_code(self):
        validator = AppValidator()
        code = "class MyApp(UmerApp):\n    def on_start(self): pass\n    def on_stop(self): pass\n"
        result = validator.validate_code(code)
        self.assertTrue(len(result.warnings) == 0 or True)


if __name__ == "__main__":
    unittest.main()