"""H242: ``custom_app_code`` is trusted input — screened, not sandboxed.

The row offers "document it as trusted developer input, **or** restrict it".
Both were done, in the right proportion: the contract is documented, and the
screening only catches accidents (control characters, unparseable source) --
it never blocks a legitimate fragment, because a fragment is a valid thing to
scaffold.
"""
import ast
import io
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import sdk.build_tool as build_tool  # noqa: E402
from sdk.build_tool import BuildTool, validate_custom_code  # noqa: E402
from sdk.validator import AppValidator  # noqa: E402

SRC = ROOT / "sdk" / "build_tool.py"
TEXT = io.open(SRC, encoding="utf-8").read()
TREE = ast.parse(TEXT)

GOOD_CODE = '''from sdk.app_template import UmerApp

class MyApp(UmerApp):
    def on_start(self): pass
    def on_stop(self): pass
'''


class RecordingVFS:
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


CONTROL_CHARS = [
    ("nul", "x = 1\x00\n"),
    ("esc", "x = 1\x1b\n"),
    ("del", "x = 1\x7f\n"),
    ("bell", "x = 1\x07\n"),
    ("c1-nel", "x = 1\x85\n"),
]


class TestControlCharactersAreRefused:
    @pytest.mark.parametrize("label,code", CONTROL_CHARS)
    def test_validate_rejects(self, label, code):
        with pytest.raises(ValueError, match="control character"):
            validate_custom_code(code)

    @pytest.mark.parametrize("label,code", CONTROL_CHARS)
    def test_scaffold_rejects_and_writes_nothing(self, label, code):
        vfs = RecordingVFS()
        with pytest.raises(ValueError):
            BuildTool(vfs=vfs).scaffold("MyApp", custom_app_code=code)
        assert vfs.calls == [], f"{label}: VFS touched before validation"

    def test_ordinary_whitespace_is_not_a_control_character(self):
        """Tab / newline / CR must stay legal -- they are normal source text."""
        code = (
            "class A(UmerApp):\r\n"
            "\tdef on_start(self):\r\n"
            "\t\tpass\r\n"
            "\tdef on_stop(self):\r\n"
            "\t\tpass\r\n"
        )
        assert validate_custom_code(code) == []


class TestUnparseableCodeIsRefused:
    def test_syntax_error_refused(self):
        with pytest.raises(ValueError, match="does not parse"):
            validate_custom_code("def broken(:\n")

    def test_syntax_error_writes_nothing(self):
        vfs = RecordingVFS()
        with pytest.raises(ValueError):
            BuildTool(vfs=vfs).scaffold("MyApp", custom_app_code="def broken(:\n")
        assert vfs.calls == []

    def test_non_string_refused(self):
        for bad in (42, None, b"bytes", ["x"]):
            with pytest.raises(ValueError):
                validate_custom_code(bad)


class TestItScreensButDoesNotSandbox:
    def test_a_fragment_is_still_scaffolded(self):
        """The decisive test that this did not become a restriction."""
        fragment = "# a fragment, not a full app\n"
        vfs = RecordingVFS()
        base = BuildTool(vfs=vfs).scaffold("MyApp", custom_app_code=fragment)
        assert vfs.files[f"{base}/src/main.py"] == fragment.encode()

    def test_warnings_do_not_block_the_write(self):
        warnings = validate_custom_code("# only a comment\n")
        assert warnings, "a comment-only fragment should warn"
        vfs = RecordingVFS()
        BuildTool(vfs=vfs).scaffold("MyApp", custom_app_code="# only a comment\n")
        assert vfs.files, "warnings must not prevent the write"

    def test_warnings_are_reported_to_the_caller(self, capsys):
        BuildTool(vfs=RecordingVFS()).scaffold(
            "MyApp", custom_app_code="# only a comment\n"
        )
        out = capsys.readouterr().out
        assert "[SDK] Warning:" in out

    def test_complete_code_produces_no_warnings(self):
        assert validate_custom_code(GOOD_CODE) == []


class TestItReusesTheExistingValidator:
    def test_same_class_not_a_second_definition(self):
        """Two definitions of 'valid app code' would drift apart."""
        assert build_tool.AppValidator is AppValidator

    def test_warnings_match_the_validator_exactly(self):
        for code in ("# c\n", GOOD_CODE, "class X: pass\n"):
            assert validate_custom_code(code) == list(
                AppValidator().validate_code(code).warnings
            )


class TestWrittenVerbatim:
    def test_valid_code_is_byte_for_byte(self):
        vfs = RecordingVFS()
        base = BuildTool(vfs=vfs).scaffold("MyApp", custom_app_code=GOOD_CODE)
        assert vfs.files[f"{base}/src/main.py"] == GOOD_CODE.encode()

    def test_trailing_newline_is_preserved(self):
        vfs = RecordingVFS()
        base = BuildTool(vfs=vfs).scaffold("MyApp", custom_app_code="x = 1")
        assert vfs.files[f"{base}/src/main.py"] == b"x = 1"

    def test_no_custom_code_still_generates_the_template(self):
        vfs = RecordingVFS()
        base = BuildTool(vfs=vfs).scaffold("MyApp")
        src = vfs.files[f"{base}/src/main.py"].decode()
        assert "class MyApp(UmerApp):" in src


class TestValidationOrder:
    def test_validated_before_the_vfs_branch(self):
        """Same discipline as H241: refuse before touching the VFS."""
        func = next(
            n for n in ast.walk(TREE)
            if isinstance(n, ast.FunctionDef) and n.name == "scaffold"
        )
        calls = [
            n.lineno for n in ast.walk(func)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "validate_custom_code"
        ]
        branches = [
            n.lineno for n in ast.walk(func)
            if isinstance(n, ast.If) and "vfs" in ast.unparse(n.test)
        ]
        assert calls and branches, (calls, branches)
        assert min(calls) < min(branches)


class TestTheContractIsDocumented:
    def test_docstring_states_trusted_developer_input(self):
        doc = ast.get_docstring(
            next(
                n for n in ast.walk(TREE)
                if isinstance(n, ast.FunctionDef) and n.name == "scaffold"
            ),
            clean=False,
        )
        assert "trusted" in doc.lower()
        assert "untrusted" in doc.lower(), (
            "the docstring must say what NOT to do with this parameter"
        )
        assert "sandbox" in doc.lower()

    def test_helper_docstring_says_it_does_not_sandbox(self):
        doc = ast.get_docstring(
            next(
                n for n in ast.walk(TREE)
                if isinstance(n, ast.FunctionDef) and n.name == "validate_custom_code"
            ),
            clean=False,
        )
        assert "sandbox" in doc.lower()
        assert "untrusted" in doc.lower()
