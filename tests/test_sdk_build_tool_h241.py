"""H241: ``BuildTool.scaffold``/``package`` must not trust ``app_name``.

The row flagged the VFS path build.  Drift-recon found that half true and
half understated: ``app_name`` is interpolated into a *logical* path (no real
filesystem escape, since QFS keys are opaque strings), but it is ALSO
interpolated unquoted into the generated ``src/main.py`` -- so ordinary names
like ``my-app`` produced modules that could not even be imported.
"""
import ast
import io
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.path_guard import PathTraversalError  # noqa: E402
from sdk.build_tool import (  # noqa: E402
    PROJECTS_ROOT,
    BuildTool,
    class_identifier,
    project_path,
    validate_app_name,
)

SRC = ROOT / "sdk" / "build_tool.py"
TEXT = io.open(SRC, encoding="utf-8").read()
TREE = ast.parse(TEXT)


class RecordingVFS:
    """Records every mutation so 'nothing happened' is provable."""

    def __init__(self):
        self.files = {}
        self.dirs = []
        self.calls = []

    def mkdir(self, path):
        self.calls.append(("mkdir", path))
        self.dirs.append(path)

    def write_file(self, path, data):
        self.calls.append(("write_file", path))
        self.files[path] = data


TRAVERSALS = [
    "../../evil",
    "../evil",
    "a/b",
    "a\\b",
    "/etc/passwd",
    "..",
    ".",
    "",
    "a.b",
    "a b",
    "x" * 65,
    "-lead",
    "a\nb",
    "a\x00b",
]


class TestTraversalIsRefused:
    @pytest.mark.parametrize("name", TRAVERSALS)
    def test_scaffold_refuses(self, name):
        vfs = RecordingVFS()
        with pytest.raises(PathTraversalError):
            BuildTool(vfs=vfs).scaffold(name)

    @pytest.mark.parametrize("name", TRAVERSALS)
    def test_package_refuses(self, name):
        vfs = RecordingVFS()
        with pytest.raises(PathTraversalError):
            BuildTool(vfs=vfs).package(name)

    @pytest.mark.parametrize("name", ["../../evil", "a/b", ".."])
    def test_nothing_is_written_on_refusal(self, name):
        """The decisive test: refusal must happen *before* any VFS call."""
        vfs = RecordingVFS()
        with pytest.raises(PathTraversalError):
            BuildTool(vfs=vfs).scaffold(name)
        assert vfs.calls == [], f"VFS was touched before validation: {vfs.calls}"
        assert vfs.files == {}
        assert vfs.dirs == []

    def test_package_writes_nothing_on_refusal(self):
        vfs = RecordingVFS()
        with pytest.raises(PathTraversalError):
            BuildTool(vfs=vfs).package("../../evil")
        assert vfs.calls == []

    def test_non_string_names_are_refused(self):
        for bad in (None, 42, ["a"], b"bytes"):
            with pytest.raises(PathTraversalError):
                project_path(bad)


class TestTheGuardIsTheRepoContract:
    def test_raises_the_shared_exception_type(self):
        """A new bespoke exception would fragment the security contract."""
        with pytest.raises(PathTraversalError):
            project_path("../../evil")
        assert issubclass(PathTraversalError, ValueError)

    def test_imports_path_guard_rather_than_reinventing_it(self):
        imported = {
            alias.name
            for node in ast.walk(TREE)
            if isinstance(node, ast.ImportFrom) and node.module == "core.path_guard"
            for alias in node.names
        }
        assert "PathTraversalError" in imported


class TestAcceptedNamesStillWork:
    ACCEPTED = ["MyApp", "my-app", "1Bad", "a_b", "A" * 64, "app2"]

    @pytest.mark.parametrize("name", ACCEPTED)
    def test_path_is_a_direct_child_of_the_root(self, name):
        path = project_path(name)
        assert path == f"{PROJECTS_ROOT}/{name}"
        assert path.count("/") == PROJECTS_ROOT.count("/") + 1

    @pytest.mark.parametrize("name", ACCEPTED)
    def test_generated_source_compiles(self, name):
        """The half the row missed: a bad name produced unimportable code."""
        vfs = RecordingVFS()
        base = BuildTool(vfs=vfs).scaffold(name)
        src = vfs.files[f"{base}/src/main.py"].decode()
        compile(src, "<generated>", "exec")

    @pytest.mark.parametrize("name", ACCEPTED)
    def test_class_identifier_is_a_valid_identifier(self, name):
        ident = class_identifier(name)
        assert ident.isidentifier(), f"{name!r} -> {ident!r} is not an identifier"
        assert not __import__("keyword").iskeyword(ident)
        compile(f"class {ident}: pass", "<id>", "exec")

    def test_hyphenated_name_maps_to_underscore(self):
        assert class_identifier("my-app") == "my_app"

    def test_leading_digit_gets_an_underscore(self):
        assert class_identifier("1Bad") == "_1Bad"

    def test_keyword_name_is_repaired(self):
        assert class_identifier("class") == "class_app"
        compile(f"class {class_identifier('class')}: pass", "<id>", "exec")

    def test_name_is_embedded_as_a_quoted_literal(self):
        vfs = RecordingVFS()
        base = BuildTool(vfs=vfs).scaffold("my-app")
        src = vfs.files[f"{base}/src/main.py"].decode()
        assert 'super().__init__("my-app", "1.0.0")' in src
        assert "class my_app(UmerApp):" in src


class TestNoRawInterpolationRemains:
    def test_source_does_not_build_the_path_inline(self):
        """The regression: ``f"/sdk/projects/{app_name}"`` inside the methods."""
        assert 'f"/sdk/projects/{' not in TEXT

    @pytest.mark.parametrize("method", ["scaffold", "package"])
    def test_method_delegates_to_project_path(self, method):
        func = next(
            n for n in ast.walk(TREE)
            if isinstance(n, ast.FunctionDef) and n.name == method
        )
        called = {
            node.func.id
            for node in ast.walk(func)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "project_path" in called, f"{method}() does not call project_path()"

    @pytest.mark.parametrize("method", ["scaffold", "package"])
    def test_validation_happens_before_the_vfs_branch(self, method):
        """``project_path`` must be assigned before ``if self.vfs``."""
        func = next(
            n for n in ast.walk(TREE)
            if isinstance(n, ast.FunctionDef) and n.name == method
        )
        lines = [
            n.lineno for n in ast.walk(func)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "project_path"
        ]
        vfs_test = [
            n.lineno for n in ast.walk(func)
            if isinstance(n, ast.If) and "vfs" in ast.unparse(n.test)
        ]
        assert lines and vfs_test, (lines, vfs_test)
        assert min(lines) < min(vfs_test)


class TestQuotingIsDefenceInDepth:
    """``_py_literal`` guards the code sink even though the regex already
    excludes quotes.  Tested directly so a future widening of the alphabet
    cannot quietly re-open the injection."""

    HOSTILE = ['a"b', "a'b", "a\nb", 'a"b"; import os; os.system("id"); #']

    @pytest.mark.parametrize("value", HOSTILE)
    def test_literal_round_trips(self, value):
        from sdk.build_tool import _py_literal

        literal = _py_literal(value)
        assert eval(literal) == value  # noqa: S307 - asserting a literal, not running input

    @pytest.mark.parametrize("value", HOSTILE)
    def test_embedding_a_hostile_name_still_compiles(self, value):
        from sdk.build_tool import _py_literal

        compile(f'x = {_py_literal(value)}', "<q>", "exec")


class TestManifestAndArchive:
    def test_manifest_carries_the_validated_name(self):
        vfs = RecordingVFS()
        base = BuildTool(vfs=vfs).scaffold("MyApp")
        manifest = __import__("json").loads(
            vfs.files[f"{base}/manifest.json"].decode()
        )
        assert manifest["name"] == "myapp"
        assert "MyApp" in manifest["description"]

    def test_archive_name_is_derived_from_the_validated_name(self):
        vfs = RecordingVFS()
        base = BuildTool(vfs=vfs).scaffold("MyApp")
        info = BuildTool(vfs=vfs).package("MyApp")
        assert info["archive"] == "myapp-1.0.0.umer.pkg"
        written = [p for p in vfs.files if p.endswith(".umer.pkg")]
        assert written == [f"{base}/myapp-1.0.0.umer.pkg"]

    def test_custom_app_code_is_still_written_verbatim(self):
        """Explicit developer-supplied code is not name-validated."""
        vfs = RecordingVFS()
        base = BuildTool(vfs=vfs).scaffold("MyApp", custom_app_code="# mine\n")
        assert vfs.files[f"{base}/src/main.py"] == b"# mine\n"


class TestDryRunUnchanged:
    def test_dry_run_returns_the_path_and_writes_nothing(self):
        base = BuildTool().scaffold("MyApp")
        assert base == f"{PROJECTS_ROOT}/MyApp"

    def test_dry_run_still_validates(self):
        with pytest.raises(PathTraversalError):
            BuildTool().scaffold("../../evil")


class TestHeaderSurvived:
    def test_canonical_block_and_trailer_still_present(self):
        head = TEXT[:2000]
        assert "# This program is free software" in head
        assert "License: GPL-3.0 (GNU General Public License v3)" in head
        first = next(
            n for n in TREE.body
            if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))
        )
        assert "from __future__ import annotations" in ast.unparse(first)
