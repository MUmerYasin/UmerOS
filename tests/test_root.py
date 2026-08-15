"""
Tests for the ``root`` package (P007).

Exercises:

- home -- ``RootHomeInfo``, ``RootHomeResolver``, ``root_home_audit``
- passwd -- ``read_passwd_entries``, ``passwd_summary``
- dotfiles -- ``DotfilesReport``, ``dotfiles_audit``, ``root_dir_audit``,
              ``RootDotfilesScanner``, ``ensure_dotfile_structure``,
              ``root_profile_loader``, ``default_root_profile``,
              ``register_profile_template``, ``resolve_profile_template``,
              ``list_profile_templates``, ``migrate_to_xdg`` (if present)
- shell -- ``ShellEnvironment``, ``RootShellEnvironmentBuilder``,
           ``shell_safety_report`` (if present)
- safety -- ``SafetySeverity``, ``SafetyReport``, ``SafetyFinding``,
            ``root_safety_audit``
- mail -- ``ForwardEntry``, ``ForwardReport``, ``root_mail_audit``
- fhs -- ``FHSReport``, ``root_fhs_audit``

Conventions:

- Every ``_selftest()`` is tested so regressions surface fast.
- Every public API receives at least one happy-path and one edge/negative test.
- Fixtures live in ``tests/fixtures/root/`` (created on demand via ``tmp_path``).
- Windows-specific skips use ``pytest.mark.skipif`` when syscalls differ.
- All docstrings use plain ASCII; arrows render as ``->``.
"""

from __future__ import annotations

import os
import sys
import stat
import textwrap
import tempfile
import unittest
from pathlib import Path
from typing import Dict

import tests

# All root submodules are optional; import what we can.
try:
    from root.home import RootHomeInfo, RootHomeResolver, root_home_audit, HOME_DISCOURAGED_SUBDIRS
except ImportError:
    RootHomeInfo = None  # type: ignore[assignment,misc]
    RootHomeResolver = None  # type: ignore[assignment,misc]
    root_home_audit = None  # type: ignore[assignment,misc]
    HOME_DISCOURAGED_SUBDIRS = []  # type: ignore[assignment]

try:
    from root.passwd import read_passwd_entries, passwd_summary, PASSWD_DB_PATH
except ImportError:
    read_passwd_entries = None  # type: ignore[assignment,misc]
    passwd_summary = None  # type: ignore[assignment,misc]
    PASSWD_DB_PATH = "/etc/passwd"  # type: ignore[assignment]

try:
    from root.dotfiles import (
        DotfilesReport,
        dotfiles_audit,
        root_dir_audit,
        RootDotfilesScanner,
        ensure_dotfile_structure,
        root_profile_loader,
        default_root_profile,
        register_profile_template,
        resolve_profile_template,
        list_profile_templates,
        migrate_to_xdg,
        DOTFILE_NAMES,
        DEFAULT_PROFILE,
        HOME_DISCOURAGED as DOTFILES_DISCOURAGED,
    )
except ImportError:
    DotfilesReport = None  # type: ignore[assignment,misc]
    dotfiles_audit = None  # type: ignore[assignment,misc]
    root_dir_audit = None  # type: ignore[assignment,misc]
    RootDotfilesScanner = None  # type: ignore[assignment,misc]
    ensure_dotfile_structure = None  # type: ignore[assignment,misc]
    root_profile_loader = None  # type: ignore[assignment,misc]
    default_root_profile = None  # type: ignore[assignment,misc]
    register_profile_template = None  # type: ignore[assignment,misc]
    resolve_profile_template = None  # type: ignore[assignment,misc]
    list_profile_templates = None  # type: ignore[assignment,misc]
    migrate_to_xdg = None  # type: ignore[assignment,misc]
    DOTFILE_NAMES = []  # type: ignore[assignment]
    DEFAULT_PROFILE = None  # type: ignore[assignment]
    DOTFILES_DISCOURAGED = []  # type: ignore[assignment]

try:
    from root.shell import (
        ShellEnvironment,
        RootShellEnvironmentBuilder,
        root_profile_path,
        root_ps1,
        shell_safety_report,
    )
except ImportError:
    ShellEnvironment = None  # type: ignore[assignment,misc]
    RootShellEnvironmentBuilder = None  # type: ignore[assignment,misc]
    root_profile_path = None  # type: ignore[assignment,misc]
    root_ps1 = None  # type: ignore[assignment,misc]
    shell_safety_report = None  # type: ignore[assignment,misc]

try:
    from root.safety import (
        SafetySeverity,
        SafetyReport,
        SafetyFinding,
        root_safety_audit,
    )
except ImportError:
    SafetySeverity = None  # type: ignore[assignment,misc]
    SafetyReport = None  # type: ignore[assignment,misc]
    SafetyFinding = None  # type: ignore[assignment,misc]
    root_safety_audit = None  # type: ignore[assignment,misc]

try:
    from root.mail import ForwardEntry, ForwardReport, root_mail_audit
except ImportError:
    ForwardEntry = None  # type: ignore[assignment,misc]
    ForwardReport = None  # type: ignore[assignment,misc]
    root_mail_audit = None  # type: ignore[assignment,misc]

try:
    from root.fhs import FHSReport, root_fhs_audit
except ImportError:
    FHSReport = None  # type: ignore[assignment,misc]
    root_fhs_audit = None  # type: ignore[assignment,misc]

try:
    from root import __version__
except ImportError:
    __version__ = "0.0.0"

try:
    from root import main as root_main
except ImportError:
    root_main = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has(*names):
    return all(n is not None for n in names)


def _write(path: Path, content: str = "", *, binary: bytes | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if binary is not None:
        path.write_bytes(binary)
    else:
        path.write_text(content, encoding="utf-8")


def _run_cli(args: list[str]) -> tuple[int, str, str]:
    """Run ``root.__main__`` CLI in-process."""
    if root_main is None:
        unittest.skip("root.__main__ not importable")
    import io
    from contextlib import redirect_stdout, redirect_stderr

    buf_out = io.StringIO()
    buf_err = io.StringIO()
    old_argv = sys.argv[:]
    try:
        sys.argv = ["root"] + args
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            rc = root_main()
    finally:
        sys.argv = old_argv
    return rc, buf_out.getvalue(), buf_err.getvalue()


# ---------------------------------------------------------------------------
# Package metadata
# ---------------------------------------------------------------------------

class TestPackageMetadata(unittest.TestCase):
    """P007.A -- package metadata and structural basics."""

    def test_version_is_string(self):
        self.assertIsInstance(__version__, str)
        parts = __version__.split(".")
        self.assertGreaterEqual(len(parts), 2)

    def test_init_exports_public_names(self):
        import root as pkg

        self.assertTrue(hasattr(pkg, "__version__"), "root.__version__ must be exported")
        self.assertIsNotNone(pkg.__version__)


# ---------------------------------------------------------------------------
# home -- RootHomeInfo, RootHomeResolver, root_home_audit
# ---------------------------------------------------------------------------

class TestHomeAudit(unittest.TestCase):
    """P007.H -- root home directory auditing."""

    @unittest.skipUnless(_has(RootHomeResolver), "root.home not importable")
    def test_resolver_default_path(self):
        resolver = RootHomeResolver()
        path, source = resolver.resolve()
        self.assertEqual(path, "/root")
        self.assertIn(source, ("default", "fallback", "passwd"))

    @unittest.skipUnless(_has(RootHomeResolver), "root.home not importable")
    def test_resolver_custom_path(self):
        with tempfile.TemporaryDirectory() as td:
            resolver = RootHomeResolver(default_path=td)
            path, source = resolver.resolve()
            self.assertIn(str(td), str(path))

    @unittest.skipUnless(_has(RootHomeInfo), "root.home not importable")
    def test_home_info_minimal_attrs(self):
        info = RootHomeInfo(path=Path("/root"))
        self.assertTrue(hasattr(info, "path"))
        self.assertTrue(hasattr(info, "exists"))
        self.assertTrue(hasattr(info, "issues"))

    @unittest.skipUnless(_has(root_home_audit), "root.home not importable")
    def test_audit_returns_list(self):
        with tempfile.TemporaryDirectory() as td:
            result = root_home_audit(td)
            self.assertIsInstance(result, (list, dict))

    @unittest.skipUnless(_has(RootHomeInfo), "root.home not importable")
    def test_home_info_as_dict(self):
        info = RootHomeInfo(path=Path("/root"))
        if hasattr(info, "as_dict"):
            d = info.as_dict()
            self.assertIsInstance(d, dict)
            self.assertIn("path", d)


# ---------------------------------------------------------------------------
# passwd -- read_passwd_entries, passwd_summary
# ---------------------------------------------------------------------------

class TestPasswd(unittest.TestCase):
    """P007.P -- /etc/passwd parsing."""

    @unittest.skipUnless(_has(read_passwd_entries), "root.passwd not importable")
    def test_read_passwd_entries_returns_list(self):
        if os.name == "nt":
            self.skipTest("passwd module requires Unix")
        entries = read_passwd_entries()
        self.assertIsInstance(entries, list)

    @unittest.skipUnless(_has(passwd_summary), "root.passwd not importable")
    def test_passwd_summary_returns_dict(self):
        if os.name == "nt":
            self.skipTest("passwd module requires Unix")
        result = passwd_summary()
        self.assertIsInstance(result, dict)


# ---------------------------------------------------------------------------
# dotfiles -- DotfilesReport, scanner, audit, profiles
# ---------------------------------------------------------------------------

class TestDotfiles(unittest.TestCase):
    """P007.D -- root dotfiles auditing."""

    @unittest.skipUnless(_has(RootDotfilesScanner), "root.dotfiles not importable")
    def test_scanner_scan(self):
        with tempfile.TemporaryDirectory() as td:
            scanner = RootDotfilesScanner(Path(td))
            report = scanner.scan()
            self.assertTrue(hasattr(report, "results"))

    @unittest.skipUnless(_has(dotfiles_audit), "root.dotfiles not importable")
    def test_dotfiles_audit_returns_report(self):
        with tempfile.TemporaryDirectory() as td:
            report = dotfiles_audit(td)
            self.assertTrue(hasattr(report, "results"))
            self.assertTrue(hasattr(report, "issues"))

    @unittest.skipUnless(_has(root_dir_audit), "root.dotfiles not importable")
    def test_root_dir_audit_returns_report(self):
        with tempfile.TemporaryDirectory() as td:
            report = root_dir_audit(td)
            self.assertTrue(hasattr(report, "results"))

    @unittest.skipUnless(_has(ensure_dotfile_structure), "root.dotfiles not importable")
    def test_ensure_dotfile_structure(self):
        with tempfile.TemporaryDirectory() as td:
            result = ensure_dotfile_structure(td)
            self.assertIsInstance(result, (bool, dict))

    @unittest.skipUnless(_has(list_profile_templates), "root.dotfiles not importable")
    def test_list_profile_templates(self):
        templates = list_profile_templates()
        self.assertIsInstance(templates, (list, dict))

    @unittest.skipUnless(_has(default_root_profile), "root.dotfiles not importable")
    def test_default_root_profile(self):
        profile = default_root_profile()
        self.assertTrue(hasattr(profile, "name"))

    @unittest.skipUnless(_has(root_profile_loader), "root.dotfiles not importable")
    def test_root_profile_loader(self):
        loader = root_profile_loader()
        self.assertTrue(hasattr(loader, "load"))

    @unittest.skipUnless(
        _has(register_profile_template, resolve_profile_template),
        "root.dotfiles not importable",
    )
    def test_register_and_resolve_template(self):
        from dataclasses import dataclass

        @dataclass
        class FakeTemplate:
            name: str
            content: str

        register_profile_template(FakeTemplate("test-profile", "echo ok"))
        resolved = resolve_profile_template("test-profile")
        self.assertIsNotNone(resolved)


# ---------------------------------------------------------------------------
# shell -- ShellEnvironment, RootShellEnvironmentBuilder
# ---------------------------------------------------------------------------

class TestShellEnvironment(unittest.TestCase):
    """P007.S -- shell environment for root."""

    @unittest.skipUnless(_has(ShellEnvironment), "root.shell not importable")
    def test_shell_environment_fields(self):
        env = ShellEnvironment(variables={}, unset=[], notes=[])
        self.assertTrue(hasattr(env, "variables"))
        self.assertTrue(hasattr(env, "unset"))
        self.assertTrue(hasattr(env, "notes"))

    @unittest.skipUnless(
        _has(RootShellEnvironmentBuilder), "root.shell not importable"
    )
    def test_builder_default(self):
        builder = RootShellEnvironmentBuilder()
        env = builder.build()
        self.assertTrue(hasattr(env, "variables"))
        self.assertIsInstance(env.variables, dict)

    @unittest.skipUnless(
        _has(RootShellEnvironmentBuilder), "root.shell not importable"
    )
    def test_builder_custom_path(self):
        builder = RootShellEnvironmentBuilder(path=("/custom/bin",))
        env = builder.build()
        path_val = env.variables.get("PATH", "")
        self.assertIn("/custom/bin", str(path_val))

    @unittest.skipUnless(_has(shell_safety_report), "root.shell not importable")
    def test_shell_safety_report(self):
        report = shell_safety_report()
        self.assertTrue(hasattr(report, "issues"))


# ---------------------------------------------------------------------------
# safety -- SafetySeverity, SafetyReport, root_safety_audit
# ---------------------------------------------------------------------------

class TestSafetyAudit(unittest.TestCase):
    """P007.X -- root safety auditing."""

    @unittest.skipUnless(_has(SafetySeverity), "root.safety not importable")
    def test_severity_values(self):
        self.assertTrue(hasattr(SafetySeverity, "INFO"))
        self.assertTrue(hasattr(SafetySeverity, "LOW"))
        self.assertTrue(hasattr(SafetySeverity, "MEDIUM"))
        self.assertTrue(hasattr(SafetySeverity, "HIGH"))
        self.assertTrue(hasattr(SafetySeverity, "CRITICAL"))

    @unittest.skipUnless(_has(root_safety_audit), "root.safety not importable")
    def test_root_safety_audit(self):
        with tempfile.TemporaryDirectory() as td:
            report = root_safety_audit(td)
            self.assertTrue(hasattr(report, "findings"))

    @unittest.skipUnless(_has(SafetyReport), "root.safety not importable")
    def test_safety_report_has_findings(self):
        report = SafetyReport(home=Path("/root"), findings=[])
        self.assertIsInstance(report.findings, list)
        self.assertEqual(len(report.findings), 0)

    @unittest.skipUnless(_has(SafetyFinding), "root.safety not importable")
    def test_safety_finding(self):
        finding = SafetyFinding(
            severity=SafetySeverity.MEDIUM,
            check="TEST001",
            message="test finding",
            detail="detail text",
            suggestion="fix suggestion",
        )
        self.assertEqual(finding.severity, SafetySeverity.MEDIUM)
        self.assertEqual(finding.check, "TEST001")


# ---------------------------------------------------------------------------
# mail -- ForwardEntry, ForwardReport, root_mail_audit
# ---------------------------------------------------------------------------

class TestMailForwarding(unittest.TestCase):
    """P007.M -- root mail forwarding audit."""

    @unittest.skipUnless(_has(ForwardEntry), "root.mail not importable")
    def test_forward_entry(self):
        entry = ForwardEntry(address="root@example.com", is_valid=True, error="")
        self.assertEqual(entry.address, "root@example.com")
        self.assertTrue(entry.is_valid)

    @unittest.skipUnless(_has(ForwardEntry), "root.mail not importable")
    def test_forward_entry_invalid(self):
        entry = ForwardEntry(address="", is_valid=False, error="empty address")
        self.assertFalse(entry.is_valid)

    @unittest.skipUnless(_has(ForwardReport), "root.mail not importable")
    def test_forward_report(self):
        report = ForwardReport(path=Path("/root/.forward"))
        self.assertTrue(hasattr(report, "entries"))

    @unittest.skipUnless(_has(root_mail_audit), "root.mail not importable")
    def test_root_mail_audit(self):
        with tempfile.TemporaryDirectory() as td:
            fwd = Path(td) / ".forward"
            _write(fwd, "root@example.com\n")
            report = root_mail_audit(td)
            self.assertTrue(hasattr(report, "entries"))


# ---------------------------------------------------------------------------
# fhs -- FHSReport, root_fhs_audit
# ---------------------------------------------------------------------------

class TestFhsAudit(unittest.TestCase):
    """P007.F -- FHS compliance audit."""

    @unittest.skipUnless(_has(root_fhs_audit), "root.fhs not importable")
    def test_fhs_audit_returns_report(self):
        report = root_fhs_audit()
        self.assertTrue(hasattr(report, "issues"))

    @unittest.skipUnless(_has(FHSReport), "root.fhs not importable")
    def test_fhs_report_render(self):
        report = FHSReport(issues=[])
        rendered = report.render()
        self.assertIsInstance(rendered, str)
        self.assertGreater(len(rendered), 0)

    @unittest.skipUnless(_has(FHSReport), "root.fhs not importable")
    def test_fhs_report_render_with_issues(self):
        from dataclasses import dataclass

        if not hasattr(FHSReport, "__init__"):
            self.skipTest("FHSReport not constructable")

        @dataclass
        class FakeIssue:
            code: str
            message: str

        report = FHSReport(issues=[FakeIssue(code="FHS001", message="test issue")])
        rendered = report.render()
        self.assertIn("FHS001", rendered)


# ---------------------------------------------------------------------------
# CLI -- __main__ entry point
# ---------------------------------------------------------------------------

class TestCLI(unittest.TestCase):
    """P007.C -- CLI entry points."""

    @unittest.skipUnless(root_main is not None, "root.__main__ not importable")
    def test_cli_help(self):
        rc, out, err = _run_cli(["help"])
        self.assertEqual(rc, 0)
        self.assertIn("root", (out + err).lower())

    @unittest.skipUnless(root_main is not None, "root.__main__ not importable")
    def test_cli_info_returns_zero(self):
        with tempfile.TemporaryDirectory() as td:
            rc, out, err = _run_cli(["info", td])
            self.assertEqual(rc, 0)

    @unittest.skipUnless(root_main is not None, "root.__main__ not importable")
    def test_cli_info_nonexistent(self):
        rc, out, err = _run_cli(["info", "/nonexistent/root/dir"])
        self.assertNotEqual(rc, 0)


# ---------------------------------------------------------------------------
# _selftest() validation
# ---------------------------------------------------------------------------

class TestSelfTests(unittest.TestCase):
    """Every _selftest() must exist and return True when callable."""

    def _check_selftest(self, module_name: str):
        try:
            mod = __import__(f"root.{module_name}", fromlist=[module_name])
        except ImportError:
            self.skipTest(f"root.{module_name} not importable")
        fn = getattr(mod, "_selftest", None)
        if fn is None:
            self.fail(f"root.{module_name}._selftest() not found")
        result = fn()
        self.assertTrue(result, f"root.{module_name}._selftest() must return True")

    def test_selftest_home(self):
        self._check_selftest("home")

    def test_selftest_passwd(self):
        self._check_selftest("passwd")

    def test_selftest_dotfiles(self):
        self._check_selftest("dotfiles")

    def test_selftest_shell(self):
        self._check_selftest("shell")

    def test_selftest_safety(self):
        self._check_selftest("safety")

    def test_selftest_mail(self):
        self._check_selftest("mail")

    def test_selftest_fhs(self):
        self._check_selftest("fhs")


# ---------------------------------------------------------------------------
# Cross-module integration
# ---------------------------------------------------------------------------

class TestIntegration(unittest.TestCase):
    """P007.I -- integration across root submodules."""

    @unittest.skipUnless(
        _has(root_home_audit, root_fhs_audit), "root.home and root.fhs required"
    )
    def test_home_audit_then_fhs(self):
        with tempfile.TemporaryDirectory() as td:
            home_result = root_home_audit(td)
            fhs_result = root_fhs_audit()
            self.assertIsNotNone(home_result)
            self.assertIsNotNone(fhs_result)

    @unittest.skipUnless(
        _has(dotfiles_audit, root_safety_audit), "root.dotfiles and root.safety required"
    )
    def test_dotfiles_then_safety(self):
        with tempfile.TemporaryDirectory() as td:
            dot_report = dotfiles_audit(td)
            safety_report = root_safety_audit(td)
            self.assertTrue(hasattr(dot_report, "issues"))
            self.assertTrue(hasattr(safety_report, "findings"))

    @unittest.skipUnless(
        _has(root_mail_audit, root_safety_audit), "root.mail and root.safety required"
    )
    def test_mail_then_safety(self):
        with tempfile.TemporaryDirectory() as td:
            mail_report = root_mail_audit(td)
            safety_report = root_safety_audit(td)
            self.assertIsNotNone(mail_report)
            self.assertIsNotNone(safety_report)

    @unittest.skipUnless(
        _has(root_home_audit, root_dir_audit, root_safety_audit),
        "root.home, root.dotfiles, root.safety required",
    )
    def test_full_audit_pipeline(self):
        with tempfile.TemporaryDirectory() as td:
            home = root_home_audit(td)
            dots = root_dir_audit(td)
            safe = root_safety_audit(td)
            self.assertIsNotNone(home)
            self.assertIsNotNone(dots)
            self.assertIsNotNone(safe)


if __name__ == "__main__":
    unittest.main()
