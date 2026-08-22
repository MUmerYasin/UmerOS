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
Tests for the UmerOS ``root`` package.

Run with::

    python -m unittest tests.test_root -v
    python tests/run_root_tests.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# POSIX-only helpers (os.chmod, /etc/passwd, file mode bits) are honoured
# on Linux and macOS but not on Windows.  The ``root`` package is a
# Umer OS / Linux target, so on Windows we skip the parts that depend
# on POSIX semantics.  The package is still *importable* on Windows
# (the pwd import is conditional) - it just cannot enforce FHS modes.
IS_WINDOWS = sys.platform.startswith("win") or os.name == "nt"
skip_windows = unittest.skipIf(IS_WINDOWS, "POSIX-only test - skipped on Windows")

import root
from root.dotfiles import (
    DEFAULT_TEMPLATES,
    DotfileResult,
    RootDotfilesManager,
)
from root.fhs import FHSRootAuditor
from root.home import (
    DEFAULT_ROOT_HOME,
    DISCOURAGED_SUBDIRS,
    ROOT_HOME_MODE,
    ROOT_UID,
    RootHomeInfo,
    RootHomeManager,
    RootHomeResolver,
    find_root_passwd_entry,
)
from root.mail import (
    ADMIN_ROLES,
    FORWARD_FILENAME,
    ForwardEntry,
    ForwardParser,
    ForwardReport,
    RootMailForwarder,
)
from root.passwd import CanonicalRootBuilder, PasswdEntry, PasswdManager
from root.safety import (
    SafetyReport,
    SafetySeverity,
    RootSafetyAuditor,
)
from root.shell import (
    DANGEROUS_VARS,
    DEFAULT_PATH,
    DEFAULT_SHELL,
    HARDENED_DEFAULTS,
    RootShellEnvironmentBuilder,
    ShellEnvironment,
)


class TestRootHome(unittest.TestCase):
    def test_default_constants(self):
        self.assertEqual(DEFAULT_ROOT_HOME, "/root")
        self.assertEqual(ROOT_HOME_MODE, 0o700)
        self.assertEqual(ROOT_UID, 0)
        self.assertIn("Mail", DISCOURAGED_SUBDIRS)

    def test_resolver_returns_valid_source(self):
        r = RootHomeResolver(default_path="/nope")
        path, source = r.resolve(env={})
        self.assertTrue(path)
        self.assertIn(source, ("passwd", "env", "default", "fallback-/"))

    @skip_windows
    def test_resolver_fallback_to_root(self):
        # On POSIX, /root may exist. If so, resolver should pick it up.
        # If not, it falls back to /. Either is acceptable; we just
        # make sure the resolver returns a usable path.
        r = RootHomeResolver(default_path="/root")
        path, source = r.resolve(env={})
        self.assertTrue(path)
        self.assertIn(source, ("passwd", "env", "default", "fallback-/"))

    @skip_windows
    def test_audit_happy_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "root"
            home.mkdir()
            home.chmod(ROOT_HOME_MODE)
            mgr = RootHomeManager(default_path=str(home),
                                  passwd_path=str(Path(tmp) / "passwd"))
            info = mgr.audit(path=str(home))
            self.assertTrue(info.exists)
            self.assertEqual(info.mode, ROOT_HOME_MODE)
            self.assertEqual(info.uid, ROOT_UID)

    def test_audit_flags_discouraged_subdirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "root"
            home.mkdir()
            (home / "Mail").mkdir()
            mgr = RootHomeManager(default_path=str(home))
            info = mgr.audit(path=str(home))
            self.assertIn("Mail", info.discouraged_subdirs)
            self.assertTrue(any("discouraged" in i for i in info.issues))

    @skip_windows
    def test_ensure_creates_and_tightens(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "root"
            mgr = RootHomeManager(default_path=str(home),
                                  expected_mode=0o700)
            info = mgr.ensure(path=str(home))
            self.assertTrue(info.exists)
            self.assertTrue(home.is_dir())
            import stat
            self.assertEqual(stat.S_IMODE(home.stat().st_mode), 0o700)


class TestRootDotfiles(unittest.TestCase):
    def _home(self, tmp: str) -> Path:
        home = Path(tmp) / "root"
        home.mkdir()
        return home

    def test_default_templates_present(self):
        for required in (".bashrc", ".bash_profile", ".profile",
                         ".bash_logout", ".vimrc"):
            self.assertIn(required, DEFAULT_TEMPLATES)

    def test_ensure_all_creates_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp)
            mgr = RootDotfilesManager(home=str(home))
            report = mgr.ensure_all()
            self.assertEqual(len(report.results), len(DEFAULT_TEMPLATES))
            for r in report.results:
                self.assertTrue(r.created)
                self.assertTrue(Path(r.path).is_file())

    def test_ensure_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp)
            mgr = RootDotfilesManager(home=str(home))
            mgr.ensure_all()
            report2 = mgr.ensure_all()
            self.assertFalse(any(r.created for r in report2.results))
            self.assertFalse(any(r.updated for r in report2.results))

    @skip_windows
    def test_private_file_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp)
            mgr = RootDotfilesManager(home=str(home))
            res = mgr.ensure_private_file(".bash_history")
            self.assertTrue(res.created)
            import stat
            mode = stat.S_IMODE((home / ".bash_history").stat().st_mode)
            self.assertEqual(mode, 0o600)

    def test_existing_content_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = self._home(tmp)
            mgr = RootDotfilesManager(home=str(home))
            mgr.ensure(".bashrc")
            (home / ".bashrc").write_text("custom content\n")
            res = mgr.ensure(".bashrc")
            self.assertFalse(res.created)
            self.assertFalse(res.updated)
            res2 = mgr.ensure(".bashrc", force=True)
            self.assertTrue(res2.updated)


class TestRootShell(unittest.TestCase):
    def test_defaults(self):
        b = RootShellEnvironmentBuilder()
        env = b.build()
        self.assertEqual(env.variables["USER"], "root")
        self.assertEqual(env.variables["SHELL"], DEFAULT_SHELL)
        self.assertTrue(env.variables["PS1"].rstrip().endswith("#"))
        # First PATH entry on POSIX is /usr/local/sbin.
        # On Windows the builder still uses the POSIX default because
        # this is a UmerOS / Linux target.
        self.assertEqual(env.variables["PATH"].split(":")[0], "/usr/local/sbin")
        self.assertEqual(env.variables["LD_LIBRARY_PATH"], "")

    def test_dangerous_vars_stripped(self):
        b = RootShellEnvironmentBuilder()
        env = b.build(inherit_from={"LD_PRELOAD": "/tmp/evil", "LANG": "C"})
        self.assertNotIn("LD_PRELOAD", env.variables)
        self.assertIn("LD_PRELOAD", env.unset)
        self.assertEqual(env.variables["LANG"], "C")

    def test_overrides_win(self):
        b = RootShellEnvironmentBuilder()
        env = b.build(overrides={"PATH": "/custom/bin"})
        self.assertEqual(env.variables["PATH"], "/custom/bin")

    def test_bash_export_rendering(self):
        b = RootShellEnvironmentBuilder()
        text = b.as_bash_exports()
        self.assertIn("export USER=", text)
        self.assertIn("export SHELL=", text)


class TestRootMail(unittest.TestCase):
    def test_parser_classifies(self):
        entries = ForwardParser.parse(
            "admin@example.com\n"
            "| /usr/bin/procmail\n"
            "/var/spool/mail/root/\n"
        )
        kinds = [e.kind for e in entries]
        self.assertIn("remote", kinds)
        self.assertIn("pipe", kinds)
        self.assertIn("file", kinds)

    def test_parser_marks_malformed(self):
        # The parser tries to classify "not-a-valid-address" as a
        # local-part only (no @) and validates against _LOCAL_RE.
        # The default _LOCAL_RE is permissive enough that a single
        # token *without* '@' may still be accepted as "local".  So
        # we instead test the explicit "remote with bad shape" case
        # which is unambiguously invalid.
        bad = ForwardParser.parse("nope@bad\n")[0]
        self.assertFalse(bad.valid)
        self.assertEqual(bad.kind, "remote")

    def test_ensure_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            fm = RootMailForwarder(home=str(home))
            report = fm.ensure("admin@example.com", comment="test")
            self.assertTrue(report.exists)
            self.assertEqual(report.forwards_to, "admin@example.com")

    def test_loop_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            fm = RootMailForwarder(home=str(home))
            fm.ensure("root")
            report = fm.audit()
            self.assertTrue(any("loop" in i for i in report.issues))

    def test_admin_role_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            fm = RootMailForwarder(home=str(tmp))
            table = fm.admin_role_forwards()
            for role in ("root", "postmaster", "webmaster"):
                self.assertIn(role, table)


class TestRootSafety(unittest.TestCase):
    def test_path_with_dot_is_flagged(self):
        # Use the OS-native separator so this works on every platform.
        sep = ";" if IS_WINDOWS else ":"
        auditor = RootSafetyAuditor(home="/nonexistent")
        report = auditor.audit(env={"PATH": f"/bin{sep}."})
        self.assertTrue(any(f.code == "PATH001" for f in report.findings))

    def test_ld_preload_critical(self):
        with tempfile.TemporaryDirectory() as tmp:
            auditor = RootSafetyAuditor(home=tmp)
            report = auditor.audit(env={"LD_PRELOAD": "/evil.so"})
            self.assertTrue(any(
                f.code == "LD002" and f.severity == SafetySeverity.CRITICAL
                for f in report.findings))

    @skip_windows
    def test_world_writable_path_critical(self):
        with tempfile.TemporaryDirectory() as tmp:
            world = Path(tmp) / "world"
            world.mkdir()
            world.chmod(0o777)
            auditor = RootSafetyAuditor(home=tmp)
            report = auditor.audit(env={"PATH": str(world)})
            self.assertTrue(any(
                f.code == "PATH003" and f.severity == SafetySeverity.CRITICAL
                for f in report.findings))

    @skip_windows
    def test_history_mode_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".bash_history").write_text("echo hi\n")
            (home / ".bash_history").chmod(0o644)
            auditor = RootSafetyAuditor(home=str(home))
            report = auditor.audit()
            self.assertTrue(any(f.code == "HIST001" for f in report.findings))

    @skip_windows
    def test_ssh_key_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            ssh = home / ".ssh"
            ssh.mkdir()
            ssh.chmod(0o755)
            (ssh / "id_rsa").write_text("key\n")
            (ssh / "id_rsa").chmod(0o644)
            auditor = RootSafetyAuditor(home=str(home))
            report = auditor.audit()
            codes = {f.code for f in report.findings}
            self.assertIn("SSH001", codes)
            self.assertIn("SSH002", codes)

    def test_user_state_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "Mail").mkdir()
            auditor = RootSafetyAuditor(home=str(home))
            report = auditor.audit()
            self.assertTrue(any(f.code == "STATE001" for f in report.findings))

    def test_blocking_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            auditor = RootSafetyAuditor(home=tmp)
            report = auditor.audit(env={"LD_PRELOAD": "/e"})
            self.assertTrue(report.has_blocking())


class TestRootPasswd(unittest.TestCase):
    def test_round_trip(self):
        line = "root:x:0:0:root:/root:/bin/bash"
        e = PasswdEntry.from_line(line)
        self.assertEqual(e.as_line(), line)

    @skip_windows
    def test_from_struct(self):
        import pwd
        pw = pwd.struct_passwd(("root", "x", "0", "0", "root", "/root", "/bin/bash"))
        e = PasswdEntry.from_struct(pw)
        self.assertEqual(e.uid, 0)

    def test_canonical_builder(self):
        b = CanonicalRootBuilder(home="/root", shell="/bin/zsh")
        e = b.build()
        self.assertEqual(e.uid, 0)
        self.assertEqual(e.home, "/root")
        self.assertEqual(e.shell, "/bin/zsh")

    def test_passwd_manager_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "passwd"
            mgr = PasswdManager(path=str(path))
            mgr.write([
                PasswdEntry("root", "x", 0, 0, "root", "/root", "/bin/bash"),
                PasswdEntry("nobody", "x", 65534, 65534, "nobody", "/nonexistent", "/usr/sbin/nologin"),
            ])
            entries = mgr.read()
            self.assertEqual(len(entries), 2)
            self.assertIsNotNone(mgr.find(uid=0))
            self.assertIsNotNone(mgr.find(name="nobody"))


class TestRootFHS(unittest.TestCase):
    @skip_windows
    def test_fresh_home_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "root"
            home.mkdir()
            home.chmod(ROOT_HOME_MODE)
            # Materialise dotfiles so the audit does not flag FHS010.
            RootDotfilesManager(home=str(home)).ensure_all(force=True)
            # Create a .forward so FHS020 is not reported.
            RootMailForwarder(home=str(home)).ensure("admin@example.com")
            auditor = FHSRootAuditor(home=str(home))
            report = auditor.audit()
            self.assertTrue(report.ok, [i.as_dict() for i in report.issues])

    @skip_windows
    def test_world_accessible_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "root"
            home.mkdir()
            home.chmod(0o755)
            auditor = FHSRootAuditor(home=str(home))
            report = auditor.audit()
            self.assertFalse(report.ok)
            self.assertTrue(any(i.code == "FHS002" for i in report.issues))

    def test_missing_dotfiles_warn(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "root"
            home.mkdir()
            auditor = FHSRootAuditor(home=str(home))
            report = auditor.audit()
            # At least one FHS010 should fire for missing .bashrc etc.
            self.assertTrue(any(i.code == "FHS010" for i in report.issues))

    def test_full_report_combines_fhs_and_safety(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "root"
            home.mkdir()
            auditor = FHSRootAuditor(home=str(home))
            combined = auditor.full_report()
            self.assertIn("fhs", combined)
            self.assertIn("safety", combined)


class TestRootMain(unittest.TestCase):
    def test_help(self):
        from root.__main__ import main
        self.assertEqual(main(["help"]), 0)

    def test_unknown_command(self):
        from root.__main__ import main
        self.assertEqual(main(["nope"]), 2)

    def test_info_runs(self):
        from root.__main__ import main
        # Will report issues because /root doesn't exist on this host,
        # but the command should not crash.
        rc = main(["info"])
        self.assertIn(rc, (0, 1))


class TestRootSelftests(unittest.TestCase):
    def test_all_module_selftests(self):
        import importlib
        for mod_name in ("root.home", "root.dotfiles", "root.shell",
                          "root.mail", "root.safety", "root.passwd",
                          "root.fhs"):
            mod = importlib.import_module(mod_name)
            self.assertTrue(bool(mod._selftest()),
                            f"{mod_name}._selftest() failed")


class TestCLIInvocation(unittest.TestCase):
    def test_selftest_via_subprocess(self):
        proc = subprocess.run(
            [sys.executable, "-m", "root", "selftest"],
            cwd=str(_ROOT),
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0,
                         f"stderr:\n{proc.stderr}\nstdout:\n{proc.stdout}")
        self.assertIn("root.home", proc.stdout)

    def test_help_via_subprocess(self):
        proc = subprocess.run(
            [sys.executable, "-m", "root", "help"],
            cwd=str(_ROOT),
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Umer OS /root", proc.stdout)

    def test_passwd_via_subprocess(self):
        proc = subprocess.run(
            [sys.executable, "-m", "root", "passwd"],
            cwd=str(_ROOT),
            capture_output=True, text=True, timeout=60,
        )
        # exit code may be 0 (found) or 1 (not found) - just no crash.
        self.assertIn(proc.returncode, (0, 1))
        # Either "current: root:..." or "(no /etc/passwd entry for uid 0 found)"
        self.assertTrue(
            "root:" in proc.stdout or "no /etc/passwd" in proc.stdout
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
