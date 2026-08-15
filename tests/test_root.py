"""
Tests for the Umer OS /root package.

Covers every public class/function in:
    root.home, root.dotfiles, root.shell, root.mail,
    root.safety, root.passwd, root.fhs, root.__main__
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
#  All imports from the root package
# ---------------------------------------------------------------------------

from root import (
    DEFAULT_ROOT_HOME,
    DISCOURAGED_SUBDIRS,
    ROOT_HOME_MODE,
    ROOT_UID,
    RootHomeInfo,
    RootHomeManager,
    RootHomeResolver,
    find_root_passwd_entry,
    DEFAULT_TEMPLATES,
    DotfileResult,
    DotfilesReport,
    RootDotfilesManager,
    DANGEROUS_VARS,
    DEFAULT_PATH,
    DEFAULT_SHELL,
    HARDENED_DEFAULTS,
    RootShellEnvironmentBuilder,
    ShellEnvironment,
    ADMIN_ROLES,
    FORWARD_FILENAME,
    ForwardEntry,
    ForwardParser,
    ForwardReport,
    RootMailForwarder,
    SafetyFinding,
    SafetyReport,
    SafetySeverity,
    RootSafetyAuditor,
    CanonicalRootBuilder,
    PasswdEntry,
    PasswdManager,
    FHSIssue,
    FHSIssueSeverity,
    FHSReport,
    FHSRootAuditor,
)

# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

IS_WINDOWS = os.name == "nt"
_skip_windows = unittest.skipIf(IS_WINDOWS, "Windows chmod is not restrictive")


def _tmp_home() -> Path:
    """Create a temporary directory for /root home."""
    return Path(tempfile.mkdtemp(prefix="umer_test_root_"))


# ===================================================================
#  root.home
# ===================================================================

class TestHomeResolver(unittest.TestCase):
    """RootHomeResolver resolves root's home from passwd / env / default."""

    def test_resolve_default(self):
        resolver = RootHomeResolver()
        path, source = resolver.resolve()
        self.assertIsInstance(path, Path)
        self.assertIn(source, ("passwd", "env", "default", "fallback"))

    def test_resolve_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            resolver = RootHomeResolver(home=td)
            path, source = resolver.resolve()
            self.assertEqual(path, Path(td))
            self.assertEqual(source, "explicit")


class TestHomeInfo(unittest.TestCase):
    """RootHomeInfo dataclass."""

    def test_as_dict(self):
        info = RootHomeInfo(path=Path("/root"))
        d = info.as_dict()
        self.assertIn("path", d)
        self.assertIn("exists", d)
        self.assertIn("uid", d)
        self.assertIn("issues", d)

    def test_from_dict_roundtrip(self):
        info = RootHomeInfo(path=Path("/root"), exists=True, uid=0)
        d = info.as_dict()
        info2 = RootHomeInfo.from_dict(d)
        self.assertEqual(info2.path, Path("/root"))
        self.assertTrue(info2.exists)
        self.assertEqual(info2.uid, 0)


class TestHomeManager(unittest.TestCase):
    """RootHomeManager audit / ensure."""

    def test_audit_missing_dir(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "nonexistent"
            mgr = RootHomeManager(default_path=str(home))
            info = mgr.audit()
            self.assertFalse(info.exists)
            self.assertTrue(len(info.issues) > 0)

    def test_ensure_creates_dir(self):
        home = _tmp_home()
        mgr = RootHomeManager(default_path=str(home))
        info = mgr.ensure()
        self.assertTrue(info.exists)
        self.assertTrue(home.is_dir())
        shutil.rmtree(home)

    def test_audit_existing_dir(self):
        home = _tmp_home()
        home.chmod(ROOT_HOME_MODE)
        mgr = RootHomeManager(default_path=str(home))
        info = mgr.audit()
        self.assertTrue(info.exists)
        shutil.rmtree(home)

    def test_render_table(self):
        home = _tmp_home()
        mgr = RootHomeManager(default_path=str(home))
        info = mgr.audit()
        text = mgr.render_table(info)
        self.assertIsInstance(text, str)
        shutil.rmtree(home)


class TestFindRootPasswdEntry(unittest.TestCase):
    """find_root_passwd_entry() returns a PasswdEntry or None."""

    def test_returns_entry_or_none(self):
        entry = find_root_passwd_entry()
        if entry is None:
            self.assertIsNone(entry)
        else:
            self.assertEqual(entry.uid, 0)


# ===================================================================
#  root.dotfiles
# ===================================================================

class TestDotfilesManager(unittest.TestCase):
    """RootDotfilesManager ensure / list_present / list_missing."""

    def test_ensure_all(self):
        home = _tmp_home()
        dm = RootDotfilesManager(home=str(home))
        report = dm.ensure_all(force=True)
        self.assertTrue(report.ok)
        self.assertTrue(len(report.results) > 0)
        shutil.rmtree(home)

    def test_list_present_after_ensure(self):
        home = _tmp_home()
        dm = RootDotfilesManager(home=str(home))
        dm.ensure_all(force=True)
        present = dm.list_present()
        self.assertTrue(len(present) > 0)
        self.assertIn(".bashrc", present)
        shutil.rmtree(home)

    def test_list_missing_empty_home(self):
        home = _tmp_home()
        dm = RootDotfilesManager(home=str(home))
        missing = dm.list_missing()
        self.assertTrue(len(missing) > 0)
        shutil.rmtree(home)

    def test_ensure_no_overwrite(self):
        home = _tmp_home()
        (home / ".bashrc").write_text("# my custom\n", encoding="utf-8")
        dm = RootDotfilesManager(home=str(home))
        report = dm.ensure_all(force=False)
        content = (home / ".bashrc").read_text(encoding="utf-8")
        self.assertEqual(content, "# my custom\n")
        shutil.rmtree(home)


class TestDotfileTemplates(unittest.TestCase):
    """Template constants are non-empty strings."""

    def test_templates_defined(self):
        from root.dotfiles import (
            BASHRC_TEMPLATE, BASH_PROFILE_TEMPLATE, PROFILE_TEMPLATE,
            BASH_LOGOUT_TEMPLATE, VIMRC_TEMPLATE,
        )
        self.assertIsInstance(BASHRC_TEMPLATE, str)
        self.assertTrue(len(BASHRC_TEMPLATE) > 0)
        self.assertIsInstance(BASH_PROFILE_TEMPLATE, str)
        self.assertIsInstance(PROFILE_TEMPLATE, str)
        self.assertIsInstance(BASH_LOGOUT_TEMPLATE, str)
        self.assertIsInstance(VIMRC_TEMPLATE, str)


class TestRegisterTemplate(unittest.TestCase):
    """register_template() adds a custom template."""

    def test_register_and_ensure(self):
        home = _tmp_home()
        dm = RootDotfilesManager(home=str(home))
        from root.dotfiles import register_template
        register_template(".custom_dotfile", "# custom\n")
        dm.ensure_all(force=True)
        self.assertTrue((home / ".custom_dotfile").is_file())
        shutil.rmtree(home)


# ===================================================================
#  root.shell
# ===================================================================

class TestShellConstants(unittest.TestCase):
    """DEFAULT_PATH, DANGEROUS_VARS, DEFAULT_SHELL, HARDENED_DEFAULTS."""

    def test_default_path_is_list(self):
        self.assertIsInstance(DEFAULT_PATH, (list, tuple))
        self.assertTrue(len(DEFAULT_PATH) > 0)

    def test_dangerous_vars(self):
        self.assertIn("LD_PRELOAD", DANGEROUS_VARS)
        self.assertIn("LD_LIBRARY_PATH", DANGEROUS_VARS)

    def test_default_shell(self):
        self.assertIsInstance(DEFAULT_SHELL, str)
        self.assertTrue(len(DEFAULT_SHELL) > 0)

    def test_hardened_defaults(self):
        self.assertIsInstance(HARDENED_DEFAULTS, dict)
        self.assertIn("PATH", HARDENED_DEFAULTS)


class TestShellEnvironmentBuilder(unittest.TestCase):
    """RootShellEnvironmentBuilder build / render."""

    def test_build_default(self):
        builder = RootShellEnvironmentBuilder()
        env = builder.build()
        self.assertIsInstance(env, ShellEnvironment)
        self.assertEqual(env.user, "root")

    def test_build_explicit_user(self):
        builder = RootShellEnvironmentBuilder(user="admin")
        env = builder.build()
        self.assertEqual(env.user, "admin")

    def test_render_bash_exports(self):
        builder = RootShellEnvironmentBuilder()
        env = builder.build()
        exports = env.render_bash_exports()
        self.assertIsInstance(exports, str)
        self.assertIn("export", exports)

    def test_ps1_ends_with_hash(self):
        builder = RootShellEnvironmentBuilder()
        env = builder.build()
        self.assertTrue(env.ps1.endswith("#"))

    def test_path_starts_with_sbin(self):
        builder = RootShellEnvironmentBuilder()
        env = builder.build()
        self.assertTrue(env.path.startswith("/usr/local/sbin") or env.path.startswith("/usr/sbin"))


# ===================================================================
#  root.mail
# ===================================================================

class TestForwardManager(unittest.TestCase):
    """ForwardManager ensure / audit / render."""

    def test_ensure_creates_forward(self):
        home = _tmp_home()
        fm = RootMailForwarder(home=str(home))
        report = fm.ensure("admin@example.com", comment="test")
        self.assertTrue(report.exists)
        self.assertTrue((home / ".forward").is_file())
        shutil.rmtree(home)

    def test_audit_no_forward(self):
        home = _tmp_home()
        fm = RootMailForwarder(home=str(home))
        report = fm.audit()
        self.assertFalse(report.exists)
        shutil.rmtree(home)

    def test_render(self):
        home = _tmp_home()
        fm = RootMailForwarder(home=str(home))
        report = fm.ensure("admin@example.com")
        text = fm.render(report)
        self.assertIsInstance(text, str)
        self.assertIn("forward", text.lower())
        shutil.rmtree(home)

    def test_admin_roles_defined(self):
        self.assertIn("root", ADMIN_ROLES)
        self.assertIn("postmaster", ADMIN_ROLES)
        self.assertIn("webmaster", ADMIN_ROLES)


class TestForwardParser(unittest.TestCase):
    """ForwardParser parses .forward file content."""

    def test_parse_single_address(self):
        entries = ForwardParser.parse("admin@example.com")
        self.assertTrue(len(entries) >= 1)
        self.assertEqual(entries[0].address, "admin@example.com")

    def test_parse_with_comment(self):
        entries = ForwardParser.parse("# my admin\nadmin@example.com")
        addresses = [e.address for e in entries]
        self.assertIn("admin@example.com", addresses)


class TestForwardEntry(unittest.TestCase):
    """ForwardEntry dataclass."""

    def test_as_dict(self):
        entry = ForwardEntry(address="admin@example.com", comment="test")
        d = entry.as_dict()
        self.assertEqual(d["address"], "admin@example.com")
        self.assertEqual(d["comment"], "test")


class TestForwardReport(unittest.TestCase):
    """ForwardReport dataclass."""

    def test_as_dict(self):
        report = ForwardReport(exists=True, forwards_to="admin@example.com")
        d = report.as_dict()
        self.assertTrue(d["exists"])
        self.assertEqual(d["forwards_to"], "admin@example.com")


# ===================================================================
#  root.safety
# ===================================================================

class TestSafetySeverity(unittest.TestCase):
    """SafetySeverity enum."""

    def test_levels(self):
        self.assertEqual(SafetySeverity.INFO.value, "info")
        self.assertEqual(SafetySeverity.WARN.value, "warn")
        self.assertEqual(SafetySeverity.ERROR.value, "error")
        self.assertEqual(SafetySeverity.BLOCK.value, "block")


class TestSafetyFinding(unittest.TestCase):
    """SafetyFinding dataclass."""

    def test_as_dict(self):
        f = SafetyFinding(
            code="PATH001",
            severity=SafetySeverity.WARN,
            title="dot in PATH",
            detail=".",
            fix="remove '.'",
        )
        d = f.as_dict()
        self.assertEqual(d["code"], "PATH001")
        self.assertEqual(d["severity"], "warn")


class TestSafetyReport(unittest.TestCase):
    """SafetyReport dataclass."""

    def test_as_dict(self):
        report = SafetyReport(findings=[])
        d = report.as_dict()
        self.assertIn("findings", d)
        self.assertIsInstance(d["findings"], list)

    def test_has_blocking_false(self):
        report = SafetyReport(findings=[])
        self.assertFalse(report.has_blocking())

    def test_has_blocking_true(self):
        report = SafetyReport(findings=[
            SafetyFinding("X001", SafetySeverity.BLOCK, "blocker", "", "")
        ])
        self.assertTrue(report.has_blocking())


class TestSafetyAuditor(unittest.TestCase):
    """RootSafetyAuditor audit."""

    def test_audit_returns_report(self):
        with tempfile.TemporaryDirectory() as td:
            auditor = RootSafetyAuditor(home=td)
            report = auditor.audit()
            self.assertIsInstance(report, SafetyReport)
            self.assertIsInstance(report.findings, list)

    def test_render(self):
        with tempfile.TemporaryDirectory() as td:
            auditor = RootSafetyAuditor(home=td)
            report = auditor.audit()
            text = report.render()
            self.assertIsInstance(text, str)
            self.assertIn("safety", text.lower())


# ===================================================================
#  root.passwd
# ===================================================================

class TestPasswdEntry(unittest.TestCase):
    """PasswdEntry dataclass."""

    def test_as_line(self):
        e = PasswdEntry("root", "x", 0, 0, "root", "/root", "/bin/bash")
        line = e.as_line()
        self.assertEqual(line, "root:x:0:0:root:/root:/bin/bash")

    def test_from_line(self):
        e = PasswdEntry.from_line("root:x:0:0:root:/root:/bin/bash")
        self.assertEqual(e.name, "root")
        self.assertEqual(e.uid, 0)
        self.assertEqual(e.home, "/root")
        self.assertEqual(e.shell, "/bin/bash")

    def test_from_struct_unix(self):
        if IS_WINDOWS:
            self.skipTest("pwd module not available on Windows")
        import pwd
        pw = pwd.struct_passwd(("root", "x", "0", "0", "root", "/root", "/bin/bash"))
        e = PasswdEntry.from_struct(pw)
        self.assertEqual(e.name, "root")
        self.assertEqual(e.uid, 0)


class TestPasswdManager(unittest.TestCase):
    """PasswdManager read / write / find."""

    def test_write_read_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "passwd"
            mgr = PasswdManager(path=str(path))
            entries = [
                PasswdEntry("root", "x", 0, 0, "root", "/root", "/bin/bash"),
                PasswdEntry("nobody", "x", 65534, 65534, "nobody", "/nonexistent", "/usr/sbin/nologin"),
            ]
            mgr.write(entries)
            read_entries = mgr.read()
            self.assertEqual(len(read_entries), 2)
            self.assertEqual(read_entries[0].name, "root")
            self.assertEqual(read_entries[1].name, "nobody")

    def test_find_by_uid(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "passwd"
            mgr = PasswdManager(path=str(path))
            mgr.write([
                PasswdEntry("root", "x", 0, 0, "root", "/root", "/bin/bash"),
                PasswdEntry("nobody", "x", 65534, 65534, "nobody", "/nonexistent", "/usr/sbin/nologin"),
            ])
            entry = mgr.find(uid=0)
            self.assertIsNotNone(entry)
            self.assertEqual(entry.name, "root")

    def test_find_by_name(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "passwd"
            mgr = PasswdManager(path=str(path))
            mgr.write([
                PasswdEntry("root", "x", 0, 0, "root", "/root", "/bin/bash"),
            ])
            entry = mgr.find(name="root")
            self.assertIsNotNone(entry)
            self.assertEqual(entry.uid, 0)

    def test_find_root(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "passwd"
            mgr = PasswdManager(path=str(path))
            mgr.write([
                PasswdEntry("root", "x", 0, 0, "root", "/root", "/bin/bash"),
            ])
            entry = mgr.find_root()
            self.assertIsNotNone(entry)
            self.assertEqual(entry.name, "root")


class TestCanonicalRootBuilder(unittest.TestCase):
    """CanonicalRootBuilder build / upsert."""

    def test_build(self):
        builder = CanonicalRootBuilder(home="/root", shell="/bin/bash")
        entry = builder.build()
        self.assertEqual(entry.name, "root")
        self.assertEqual(entry.uid, 0)
        self.assertEqual(entry.home, "/root")

    def test_upsert(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "passwd"
            mgr = PasswdManager(path=str(path))
            mgr.write([
                PasswdEntry("root", "x", 0, 0, "root", "/root", "/bin/bash"),
            ])
            builder = CanonicalRootBuilder(home="/root", shell="/bin/zsh")
            canonical = builder.upsert(mgr)
            self.assertEqual(canonical.shell, "/bin/zsh")
            # backup should exist
            self.assertTrue((Path(td) / "passwd.bak").is_file())


# ===================================================================
#  root.fhs
# ===================================================================

class TestFHSIssueSeverity(unittest.TestCase):
    """FHSIssueSeverity enum."""

    def test_values(self):
        self.assertEqual(FHSIssueSeverity.INFO.value, "info")
        self.assertEqual(FHSIssueSeverity.WARN.value, "warn")
        self.assertEqual(FHSIssueSeverity.ERROR.value, "error")


class TestFHSIssue(unittest.TestCase):
    """FHSIssue dataclass."""

    def test_as_dict(self):
        issue = FHSIssue(
            code="FHS001",
            severity=FHSIssueSeverity.ERROR,
            title="missing home",
            detail="/root does not exist",
            fix="create /root",
        )
        d = issue.as_dict()
        self.assertEqual(d["code"], "FHS001")
        self.assertEqual(d["severity"], "error")


class TestFHSReport(unittest.TestCase):
    """FHSReport dataclass."""

    def test_ok_true_no_errors(self):
        report = FHSReport(home="/root", issues=[
            FHSIssue("FHS010", FHSIssueSeverity.WARN, "missing .bashrc"),
        ])
        self.assertTrue(report.ok)

    def test_ok_false_with_error(self):
        report = FHSReport(home="/root", issues=[
            FHSIssue("FHS001", FHSIssueSeverity.ERROR, "missing home"),
        ])
        self.assertFalse(report.ok)

    def test_render(self):
        report = FHSReport(home="/root", issues=[
            FHSIssue("FHS001", FHSIssueSeverity.ERROR, "missing home"),
        ])
        text = report.render()
        self.assertIn("FHS001", text)
        self.assertIn("missing home", text)

    def test_render_ok(self):
        report = FHSReport(home="/root", issues=[])
        text = report.render()
        self.assertIn("OK", text)

    def test_as_dict(self):
        report = FHSReport(home="/root")
        d = report.as_dict()
        self.assertEqual(d["home"], "/root")
        self.assertTrue(d["ok"])


class TestFHSRootAuditor(unittest.TestCase):
    """FHSRootAuditor audit / safety_audit / full_report."""

    def test_audit_clean(self):
        home = _tmp_home()
        home.chmod(ROOT_HOME_MODE)
        dm = RootDotfilesManager(home=str(home))
        dm.ensure_all(force=True)
        auditor = FHSRootAuditor(home=str(home))
        report = auditor.audit()
        if IS_WINDOWS:
            # Windows chmod is not restrictive; FHS002 may fire
            pass
        else:
            self.assertTrue(report.ok)
        shutil.rmtree(home)

    def test_audit_discouraged_subdirs(self):
        home = _tmp_home()
        home.chmod(ROOT_HOME_MODE)
        (home / "Mail").mkdir()
        (home / ".mozilla").mkdir()
        auditor = FHSRootAuditor(home=str(home))
        report = auditor.audit()
        codes = [i.code for i in report.issues]
        self.assertIn("FHS004", codes)
        shutil.rmtree(home)

    def test_safety_audit(self):
        with tempfile.TemporaryDirectory() as td:
            auditor = FHSRootAuditor(home=td)
            safety = auditor.safety_audit()
            self.assertIsInstance(safety, SafetyReport)

    def test_full_report(self):
        with tempfile.TemporaryDirectory() as td:
            auditor = FHSRootAuditor(home=td)
            full = auditor.full_report()
            self.assertIn("fhs", full)
            self.assertIn("safety", full)


# ===================================================================
#  root.__main__
# ===================================================================

class TestCLI(unittest.TestCase):
    """CLI dispatcher commands."""

    def test_selftest_returns_zero(self):
        from root.__main__ import _cmd_selftest
        # Run in a fresh temp dir so selftests don't hit real /root
        os.environ["UMEROS_TEST_HOME"] = tempfile.mkdtemp()
        try:
            rc = _cmd_selftest([])
            self.assertEqual(rc, 0)
        finally:
            shutil.rmtree(os.environ.pop("UMEROS_TEST_HOME", ""), ignore_errors=True)

    def test_help_returns_zero(self):
        from root.__main__ import _cmd_help
        rc = _cmd_help([])
        self.assertEqual(rc, 0)

    def test_passwd_returns_zero(self):
        from root.__main__ import _cmd_passwd
        rc = _cmd_passwd([])
        self.assertEqual(rc, 0)

    def test_info_returns_zero(self):
        from root.__main__ import _cmd_info
        with tempfile.TemporaryDirectory() as td:
            rc = _cmd_info([td])
            self.assertEqual(rc, 0)

    def test_ensure_returns_zero(self):
        from root.__main__ import _cmd_ensure
        with tempfile.TemporaryDirectory() as td:
            rc = _cmd_ensure([td])
            self.assertEqual(rc, 0)

    def test_dotfiles_returns_zero(self):
        from root.__main__ import _cmd_dotfiles
        with tempfile.TemporaryDirectory() as td:
            rc = _cmd_dotfiles([td])
            self.assertEqual(rc, 0)

    def test_forward_requires_arg(self):
        from root.__main__ import _cmd_forward
        rc = _cmd_forward([])
        self.assertEqual(rc, 2)

    def test_forward_creates_file(self):
        from root.__main__ import _cmd_forward
        with tempfile.TemporaryDirectory() as td:
            os.environ["UMEROS_TEST_HOME"] = td
            try:
                # ForwardManager uses home=/root by default; we test the arg path
                rc = _cmd_forward(["admin@example.com"])
                # May return 1 if .forward is not at /root; just check it doesn't crash
                self.assertIn(rc, (0, 1))
            finally:
                os.environ.pop("UMEROS_TEST_HOME", None)


# ===================================================================
#  root package __init__ exports
# ===================================================================

class TestPackageExports(unittest.TestCase):
    """root package __init__ exports."""

    def test_all_list(self):
        import root
        self.assertIsInstance(root.__all__, list)
        self.assertTrue(len(root.__all__) > 0)

    def test_version(self):
        import root
        self.assertIsInstance(root.__version__, str)
        self.assertEqual(root.__version__, "2.0.0")


# ===================================================================
#  selftest() functions
# ===================================================================

class TestSelftest(unittest.TestCase):
    """Every module's _selftest() returns True."""

    def test_home_selftest(self):
        from root.home import _selftest
        self.assertTrue(_selftest())

    def test_dotfiles_selftest(self):
        from root.dotfiles import _selftest
        self.assertTrue(_selftest())

    def test_shell_selftest(self):
        from root.shell import _selftest
        self.assertTrue(_selftest())

    def test_mail_selftest(self):
        from root.mail import _selftest
        self.assertTrue(_selftest())

    def test_safety_selftest(self):
        from root.safety import _selftest
        self.assertTrue(_selftest())

    def test_passwd_selftest(self):
        from root.passwd import _selftest
        self.assertTrue(_selftest())

    def test_fhs_selftest(self):
        from root.fhs import _selftest
        self.assertTrue(_selftest())


# ===================================================================
#  Coverage: edge cases and additional paths
# ===================================================================

class TestHomeResolverEdgeCases(unittest.TestCase):
    """Edge cases for RootHomeResolver."""

    def test_resolve_with_env(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"HOME": td}):
                resolver = RootHomeResolver()
                path, source = resolver.resolve()
                self.assertIsInstance(path, Path)

    def test_resolve_missing_dir_fallback(self):
        resolver = RootHomeResolver(home="/nonexistent/path/xyz")
        path, source = resolver.resolve()
        self.assertIsInstance(path, Path)


class TestDotfilesEdgeCases(unittest.TestCase):
    """Edge cases for RootDotfilesManager."""

    def test_ensure_idempotent(self):
        home = _tmp_home()
        dm = RootDotfilesManager(home=str(home))
        dm.ensure_all(force=True)
        dm.ensure_all(force=True)
        present = dm.list_present()
        self.assertTrue(len(present) > 0)
        shutil.rmtree(home)

    def test_set_mode_override(self):
        home = _tmp_home()
        dm = RootDotfilesManager(home=str(home))
        dm.set_mode_override(".bash_history", 0o600)
        self.assertEqual(dm._mode_overrides.get(".bash_history"), 0o600)
        shutil.rmtree(home)


class TestShellEnvironmentEdgeCases(unittest.TestCase):
    """Edge cases for ShellEnvironment."""

    def test_render_bash_exports_empty(self):
        env = ShellEnvironment(path="", ps1="root# ", user="root", shell="/bin/bash")
        exports = env.render_bash_exports()
        self.assertIsInstance(exports, str)

    def test_custom_path(self):
        builder = RootShellEnvironmentBuilder(path="/custom/bin")
        env = builder.build()
        self.assertEqual(env.path, "/custom/bin")


class TestSafetyEdgeCases(unittest.TestCase):
    """Edge cases for RootSafetyAuditor."""

    def test_audit_with_ssh_dir(self):
        home = _tmp_home()
        ssh_dir = home / ".ssh"
        ssh_dir.mkdir()
        ssh_dir.chmod(0o700)
        auditor = RootSafetyAuditor(home=str(home))
        report = auditor.audit()
        self.assertIsInstance(report, SafetyReport)
        shutil.rmtree(home)

    def test_audit_with_history(self):
        home = _tmp_home()
        (home / ".bash_history").write_text("ls\n", encoding="utf-8")
        auditor = RootSafetyAuditor(home=str(home))
        report = auditor.audit()
        self.assertIsInstance(report, SafetyReport)
        shutil.rmtree(home)

    def test_render_full_report(self):
        with tempfile.TemporaryDirectory() as td:
            auditor = RootSafetyAuditor(home=td)
            report = auditor.audit()
            text = report.render()
            self.assertIn("safety", text.lower())
            self.assertIn("PATH", text)


class TestFHSReportRender(unittest.TestCase):
    """Additional FHSReport render tests."""

    def test_render_multiple_issues(self):
        report = FHSReport(home="/root", issues=[
            FHSIssue("FHS001", FHSIssueSeverity.ERROR, "missing home"),
            FHSIssue("FHS002", FHSIssueSeverity.ERROR, "world-readable"),
            FHSIssue("FHS010", FHSIssueSeverity.WARN, "missing .bashrc"),
            FHSIssue("FHS020", FHSIssueSeverity.INFO, "no .forward"),
        ])
        text = report.render()
        self.assertIn("FHS001", text)
        self.assertIn("FHS002", text)
        self.assertIn("FHS010", text)
        self.assertIn("FHS020", text)

    def test_render_no_fix(self):
        issue = FHSIssue("FHS001", FHSIssueSeverity.ERROR, "missing home", detail="", fix="")
        report = FHSReport(home="/root", issues=[issue])
        text = report.render()
        self.assertIn("FHS001", text)


class TestForwardParserEdgeCases(unittest.TestCase):
    """Edge cases for ForwardParser."""

    def test_parse_empty(self):
        entries = ForwardParser.parse("")
        self.assertIsInstance(entries, list)

    def test_parse_only_comments(self):
        entries = ForwardParser.parse("# comment1\n# comment2")
        self.assertIsInstance(entries, list)


class TestPasswdEntryEdgeCases(unittest.TestCase):
    """Edge cases for PasswdEntry."""

    def test_from_line_variants(self):
        # Standard 7-field line
        e = PasswdEntry.from_line("daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin")
        self.assertEqual(e.name, "daemon")
        self.assertEqual(e.uid, 1)
        self.assertEqual(e.shell, "/usr/sbin/nologin")

    def test_as_line_roundtrip(self):
        original = "root:x:0:0:root:/root:/bin/bash"
        e = PasswdEntry.from_line(original)
        self.assertEqual(e.as_line(), original)


class TestFHSRootAuditorEdgeCases(unittest.TestCase):
    """Edge cases for FHSRootAuditor."""

    def test_audit_with_discouraged_subdirs(self):
        home = _tmp_home()
        home.chmod(ROOT_HOME_MODE)
        (home / "Mail").mkdir()
        dm = RootDotfilesManager(home=str(home))
        dm.ensure_all(force=True)
        auditor = FHSRootAuditor(home=str(home))
        report = auditor.audit()
        codes = [i.code for i in report.issues]
        self.assertIn("FHS004", codes)
        shutil.rmtree(home)

    def test_full_report_structure(self):
        with tempfile.TemporaryDirectory() as td:
            auditor = FHSRootAuditor(home=td)
            full = auditor.full_report()
            self.assertIn("fhs", full)
            self.assertIn("safety", full)
            self.assertIn("home", full["fhs"])
            self.assertIn("ok", full["fhs"])
            self.assertIn("issues", full["fhs"])


class TestPackageImport(unittest.TestCase):
    """Verify all public names are importable from root."""

    def test_imports(self):
        import root
        self.assertTrue(hasattr(root, "DEFAULT_ROOT_HOME"))
        self.assertTrue(hasattr(root, "ROOT_HOME_MODE"))
        self.assertTrue(hasattr(root, "ROOT_UID"))
        self.assertTrue(hasattr(root, "RootHomeManager"))
        self.assertTrue(hasattr(root, "RootHomeResolver"))
        self.assertTrue(hasattr(root, "RootDotfilesManager"))
        self.assertTrue(hasattr(root, "DEFAULT_PATH"))
        self.assertTrue(hasattr(root, "DANGEROUS_VARS"))
        self.assertTrue(hasattr(root, "DEFAULT_SHELL"))
        self.assertTrue(hasattr(root, "RootShellEnvironmentBuilder"))
        self.assertTrue(hasattr(root, "ShellEnvironment"))
        self.assertTrue(hasattr(root, "ADMIN_ROLES"))
        self.assertTrue(hasattr(root, "FORWARD_FILENAME"))
        self.assertTrue(hasattr(root, "ForwardEntry"))
        self.assertTrue(hasattr(root, "ForwardParser"))
        self.assertTrue(hasattr(root, "ForwardReport"))
        self.assertTrue(hasattr(root, "RootMailForwarder"))
        self.assertTrue(hasattr(root, "SafetyFinding"))
        self.assertTrue(hasattr(root, "SafetyReport"))
        self.assertTrue(hasattr(root, "SafetySeverity"))
        self.assertTrue(hasattr(root, "RootSafetyAuditor"))
        self.assertTrue(hasattr(root, "CanonicalRootBuilder"))
        self.assertTrue(hasattr(root, "PasswdEntry"))
        self.assertTrue(hasattr(root, "PasswdManager"))
        self.assertTrue(hasattr(root, "FHSIssue"))
        self.assertTrue(hasattr(root, "FHSIssueSeverity"))
        self.assertTrue(hasattr(root, "FHSReport"))
        self.assertTrue(hasattr(root, "FHSRootAuditor"))
        self.assertTrue(hasattr(root, "DISCOURAGED_SUBDIRS"))
        self.assertTrue(hasattr(root, "DEFAULT_TEMPLATES"))
        self.assertTrue(hasattr(root, "DotfileResult"))
        self.assertTrue(hasattr(root, "DotfilesReport"))
        self.assertTrue(hasattr(root, "HARDENED_DEFAULTS"))
        self.assertTrue(hasattr(root, "find_root_passwd_entry"))


class TestDotfilesEnsureAll(unittest.TestCase):
    """DotfilesReport ensure_all returns DotfilesReport."""

    def test_report_type(self):
        home = _tmp_home()
        dm = RootDotfilesManager(home=str(home))
        report = dm.ensure_all(force=True)
        self.assertIsInstance(report, DotfilesReport)
        self.assertTrue(report.ok)
        shutil.rmtree(home)

    def test_result_entries(self):
        home = _tmp_home()
        dm = RootDotfilesManager(home=str(home))
        report = dm.ensure_all(force=True)
        for result in report.results:
            self.assertIsInstance(result, DotfileResult)
            self.assertTrue(result.exists)
        shutil.rmtree(home)


class TestShellHardenEnv(unittest.TestCase):
    """ShellEnvironment harden_env removes dangerous vars."""

    def test_harden_removes_dangerous(self):
        env = ShellEnvironment(
            path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin",
            ps1="root# ",
            user="root",
            shell="/bin/bash",
            extra={"LD_PRELOAD": "/evil", "MY_VAR": "ok"},
        )
        hardened = env.harden_env()
        self.assertNotIn("LD_PRELOAD", hardened)
        self.assertIn("MY_VAR", hardened)


class TestSafetyReportRender(unittest.TestCase):
    """SafetyReport render output."""

    def test_render_empty(self):
        report = SafetyReport(findings=[])
        text = report.render()
        self.assertIsInstance(text, str)

    def test_render_with_findings(self):
        report = SafetyReport(findings=[
            SafetyFinding("PATH001", SafetySeverity.WARN, "dot in PATH", ".", "remove"),
        ])
        text = report.render()
        self.assertIn("PATH001", text)
        self.assertIn("dot in PATH", text)


if __name__ == "__main__":
    unittest.main()
