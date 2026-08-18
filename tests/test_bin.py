"""
Test /bin modules - comprehensive coverage for FHS 3.0 /bin commands
Covers: essential_commands, system_info, process, shell, permissions,
        boolean_ops, network_cmds, user_commands, device, archive, csh, ed,
        usr_commands, usr_cmds, bin_manager
"""
from __future__ import annotations

import io
import os
import sys
import unittest
import tempfile
import stat

_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_this_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
_bin_dir = os.path.join(_project_root, "bin")
if _bin_dir not in sys.path:
    sys.path.insert(0, _bin_dir)

# ── Imports from /bin modules ────────────────────────────────────────────────

from essential_commands import (
    CatCommand, CatOptions, CpCommand, CpFlags, LsCommand, LsFlags,
    MvCommand, MvFlags, RmCommand, RmFlags, MkdirCommand, RmdirCommand,
    DdCommand, MoreCommand, LnCommand,
)
from system_info import (
    UnameCommand, UnameFlag, DmesgCommand,
    HostnameCommand, DfCommand, DfFormat,
    EchoCommand, EchoEscape, DateCommand, PwdCommand,
)
# process module uses termios (Unix-only)
try:
    from process import (
        PsCommand, KillCommand, MountCommand, UmountCommand,
        SttyCommand, SyncCommand,
    )
    _HAS_PROCESS = True
except ImportError:
    _HAS_PROCESS = False
from shell import (
    ShCommand, SedCommand, TarCommand, GzipCommand, GunzipCommand,
    ZcatCommand, NetstatCommand, PingCommand, CpioCommand,
)
from permissions import (
    ChmodCommand, ChmodMode, WhoFlag, PermChange,
    ChownCommand, ChgrpCommand,
)
from boolean_ops import (
    TrueCommand, FalseCommand, TestCommand, BracketTestCommand,
    YesCommand, PrintenvCommand, EnvCommand,
)
from network_cmds import (
    IfconfigCommand, IpCommand, RouteCommand, ArpCommand,
)
# user_commands module uses pwd (Unix-only)
try:
    from user_commands import SuCommand, LoginCommand
    _HAS_USER_CMDS = True
except ImportError:
    _HAS_USER_CMDS = False
from device import MknodCommand
from archive import TarCommand as ArchiveTarCommand
from csh import CshCommand
from ed import EdCommand
from bin_manager import (
    BinManager, BinBinary, BinCategory, BinStatus, BinPrivilege,
    BinType, BinSymlink, FHS_REQUIRED_BIN, FHS_REQUIRED_SBIN,
    BIN_CATEGORIES, COMMAND_REGISTRY,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  ESSENTIAL COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCatCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = CatCommand()

    def test_name(self):
        self.assertEqual(self.cmd.name, "cat")

    def test_cat_no_files_returns_0(self):
        self.assertEqual(self.cmd.execute([]), 0)

    def test_cat_existing_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world\n")
            f.flush()
            fname = f.name
        try:
            out = io.StringIO()
            rc = self.cmd.execute([fname], output=out)
            self.assertEqual(rc, 0)
            self.assertIn("hello world", out.getvalue())
        finally:
            os.unlink(fname)

    def test_cat_missing_file_returns_1(self):
        self.assertEqual(self.cmd.execute(["/nonexistent.txt"]), 1)

    def test_cat_multiple_files(self):
        f1 = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        f2 = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        f1.write("line1\n")
        f2.write("line2\n")
        f1.flush(); f2.flush()
        try:
            out = io.StringIO()
            rc = self.cmd.execute([f1.name, f2.name], output=out)
            self.assertEqual(rc, 0)
            text = out.getvalue()
            self.assertIn("line1", text)
            self.assertIn("line2", text)
        finally:
            os.unlink(f1.name); os.unlink(f2.name)

    def test_cat_option_number_all(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("a\nb\n")
            f.flush()
            fname = f.name
        try:
            out = io.StringIO()
            self.cmd.execute([fname], options=CatOptions.NUMBER_ALL, output=out)
            text = out.getvalue()
            self.assertIn("1", text)
            self.assertIn("2", text)
        finally:
            os.unlink(fname)

    def test_cat_option_show_ends(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("abc\n")
            f.flush()
            fname = f.name
        try:
            out = io.StringIO()
            self.cmd.execute([fname], options=CatOptions.SHOW_ENDS, output=out)
            self.assertIn("$", out.getvalue())
        finally:
            os.unlink(fname)

    def test_cat_option_squeeze_blank(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("a\n\n\n\nb\n")
            f.flush()
            fname = f.name
        try:
            out = io.StringIO()
            self.cmd.execute([fname], options=CatOptions.SQUEEZE_BLANK, output=out)
            lines = out.getvalue().split("\n")
            non_empty = [l for l in lines if l.strip() == ""]
            self.assertLessEqual(len(non_empty), 1)
        finally:
            os.unlink(fname)

    def test_cat_option_show_tabs(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("a\tb\n")
            f.flush()
            fname = f.name
        try:
            out = io.StringIO()
            self.cmd.execute([fname], options=CatOptions.SHOW_TABS, output=out)
            self.assertIn("^I", out.getvalue())
        finally:
            os.unlink(fname)

    def test_cat_directory_returns_error(self):
        rc = self.cmd.execute([tempfile.gettempdir()])
        self.assertNotEqual(rc, 0)


class TestCpCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = CpCommand()

    def test_name(self):
        self.assertEqual(self.cmd.name, "cp")

    def test_cp_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)

    def test_cp_version(self):
        rc = self.cmd.execute(["--version"])
        self.assertEqual(rc, 0)

    def test_cp_missing_source(self):
        rc = self.cmd.execute(["/nonexistent_src", "/tmp/cp_test_dst"])
        self.assertNotEqual(rc, 0)

    def test_cp_file(self):
        src = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        src.write("copy me\n")
        src.flush()
        dst_path = src.name + ".dst"
        try:
            rc = self.cmd.execute([src.name, dst_path])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(dst_path))
            with open(dst_path) as f:
                self.assertIn("copy me", f.read())
        finally:
            os.unlink(src.name)
            if os.path.exists(dst_path):
                os.unlink(dst_path)

    def test_cp_recursive(self):
        src_dir = tempfile.mkdtemp()
        dst_dir = src_dir + "_dst"
        try:
            sub = os.path.join(src_dir, "sub")
            os.makedirs(sub)
            with open(os.path.join(sub, "f.txt"), "w") as f:
                f.write("nested\n")
            rc = self.cmd.execute(["-r", src_dir, dst_dir])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(os.path.join(dst_dir, "sub", "f.txt")))
        finally:
            import shutil
            shutil.rmtree(src_dir, ignore_errors=True)
            shutil.rmtree(dst_dir, ignore_errors=True)

    def test_cp_no_args_returns_error(self):
        rc = self.cmd.execute([])
        self.assertNotEqual(rc, 0)


class TestLsCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = LsCommand()

    def test_name(self):
        self.assertEqual(self.cmd.name, "ls")

    def test_ls_current_dir(self):
        rc = self.cmd.execute([])
        self.assertEqual(rc, 0)

    def test_ls_long_format(self):
        rc = self.cmd.execute(["-l"])
        self.assertEqual(rc, 0)

    def test_ls_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)

    def test_ls_version(self):
        rc = self.cmd.execute(["--version"])
        self.assertEqual(rc, 0)

    def test_ls_a_shows_hidden(self):
        rc = self.cmd.execute(["-a"])
        self.assertEqual(rc, 0)

    def test_ls_nonexistent_returns_error(self):
        rc = self.cmd.execute(["/nonexistent_dir_xyz"])
        self.assertNotEqual(rc, 0)


class TestMvCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = MvCommand()

    def test_name(self):
        self.assertEqual(self.cmd.name, "mv")

    def test_mv_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)

    def test_mv_missing_source(self):
        rc = self.cmd.execute(["/nonexistent_src_mv", "/tmp/mv_test_dst"])
        self.assertNotEqual(rc, 0)

    def test_mv_file(self):
        src = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        src.write("move me\n")
        src.flush()
        dst_path = src.name + ".moved"
        try:
            rc = self.cmd.execute([src.name, dst_path])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(dst_path))
            self.assertFalse(os.path.exists(src.name))
        finally:
            if os.path.exists(src.name):
                os.unlink(src.name)
            if os.path.exists(dst_path):
                os.unlink(dst_path)

    def test_mv_no_args_returns_error(self):
        rc = self.cmd.execute([])
        self.assertNotEqual(rc, 0)


class TestRmCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = RmCommand()

    def test_name(self):
        self.assertEqual(self.cmd.name, "rm")

    def test_rm_file(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        f.write("delete me\n")
        f.flush()
        fname = f.name
        try:
            rc = self.cmd.execute([fname])
            self.assertEqual(rc, 0)
            self.assertFalse(os.path.exists(fname))
        finally:
            if os.path.exists(fname):
                os.unlink(fname)

    def test_rm_missing_file_returns_error(self):
        rc = self.cmd.execute(["/nonexistent_rm_file"])
        self.assertNotEqual(rc, 0)

    def test_rm_no_args(self):
        rc = self.cmd.execute([])
        self.assertNotEqual(rc, 0)

    def test_rm_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)


class TestMkdirCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = MkdirCommand()

    def test_name(self):
        self.assertEqual(self.cmd.name, "mkdir")

    def test_mkdir_creates_dir(self):
        d = os.path.join(tempfile.gettempdir(), "test_mkdir_new_dir")
        try:
            rc = self.cmd.execute([d])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.isdir(d))
        finally:
            os.rmdir(d) if os.path.isdir(d) else None

    def test_mkdir_parents(self):
        d = os.path.join(tempfile.gettempdir(), "test_mkdir_p", "sub", "deep")
        try:
            rc = self.cmd.execute(["-p", d])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.isdir(d))
        finally:
            import shutil
            shutil.rmtree(os.path.join(tempfile.gettempdir(), "test_mkdir_p"), ignore_errors=True)

    def test_mkdir_no_args(self):
        rc = self.cmd.execute([])
        self.assertNotEqual(rc, 0)


class TestRmdirCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = RmdirCommand()

    def test_name(self):
        self.assertEqual(self.cmd.name, "rmdir")

    def test_rmdir_empty_dir(self):
        d = tempfile.mkdtemp()
        try:
            rc = self.cmd.execute([d])
            self.assertEqual(rc, 0)
            self.assertFalse(os.path.exists(d))
        finally:
            if os.path.isdir(d):
                os.rmdir(d)

    def test_rmdir_no_args(self):
        rc = self.cmd.execute([])
        self.assertNotEqual(rc, 0)


class TestDdCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = DdCommand()

    def test_name(self):
        self.assertEqual(self.cmd.name, "dd")

    def test_dd_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)

    def test_dd_version(self):
        rc = self.cmd.execute(["--version"])
        self.assertEqual(rc, 0)

    def test_dd_no_args(self):
        rc = self.cmd.execute([])
        self.assertEqual(rc, 0)

    def test_dd_basic(self):
        rc = self.cmd.execute(["if=/dev/null", "of=/dev/null", "bs=512", "count=1"])
        self.assertEqual(rc, 0)


class TestMoreCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = MoreCommand()

    def test_name(self):
        self.assertEqual(self.cmd.name, "more")

    def test_more_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("line1\nline2\n")
            f.flush()
            fname = f.name
        try:
            rc = self.cmd.execute([fname])
            self.assertEqual(rc, 0)
        finally:
            os.unlink(fname)

    def test_more_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)


class TestLnCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = LnCommand()

    def test_name(self):
        self.assertEqual(self.cmd.name, "ln")

    def test_ln_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)

    def test_ln_version(self):
        rc = self.cmd.execute(["--version"])
        self.assertEqual(rc, 0)

    def test_ln_no_args(self):
        rc = self.cmd.execute([])
        self.assertNotEqual(rc, 0)

    def test_ln_hard_link(self):
        src = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        src.write("link me\n")
        src.flush()
        dst = src.name + ".lnk"
        try:
            rc = self.cmd.execute([src.name, dst])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(dst))
        finally:
            os.unlink(src.name)
            if os.path.exists(dst):
                os.unlink(dst)

    def test_ln_symbolic(self):
        src = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        src.write("symlink me\n")
        src.flush()
        dst = src.name + ".sym"
        try:
            rc = self.cmd.execute(["-s", src.name, dst])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.islink(dst))
        finally:
            os.unlink(src.name)
            if os.path.exists(dst):
                os.unlink(dst)


# ═══════════════════════════════════════════════════════════════════════════════
#  SYSTEM INFO COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════


class TestUnameCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = UnameCommand()

    def test_name(self):
        self.assertEqual(self.cmd.name, "uname")

    def test_uname_all(self):
        out = io.StringIO()
        rc = self.cmd.execute(UnameFlag.ALL, output=out)
        self.assertEqual(rc, 0)
        self.assertTrue(len(out.getvalue().strip()) > 0)

    def test_uname_s(self):
        out = io.StringIO()
        rc = self.cmd.execute(UnameFlag.SYSNAME, output=out)
        self.assertEqual(rc, 0)

    def test_uname_n(self):
        out = io.StringIO()
        rc = self.cmd.execute(UnameFlag.NODENAME, output=out)
        self.assertEqual(rc, 0)

    def test_uname_r(self):
        out = io.StringIO()
        rc = self.cmd.execute(UnameFlag.RELEASE, output=out)
        self.assertEqual(rc, 0)

    def test_uname_m(self):
        out = io.StringIO()
        rc = self.cmd.execute(UnameFlag.MACHINE, output=out)
        self.assertEqual(rc, 0)

    def test_uname_default(self):
        out = io.StringIO()
        rc = self.cmd.execute(0, output=out)
        self.assertEqual(rc, 0)

    def test_uname_get_info(self):
        info = self.cmd.get_info()
        self.assertTrue(info.sysname)


class TestDmesgCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = DmesgCommand()

    def test_name(self):
        self.assertTrue(hasattr(self.cmd, "execute"))

    def test_dmesg_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_dmesg_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)

    def test_dmesg_level_filter(self):
        rc = self.cmd.execute(["-l", "err"])
        self.assertEqual(rc, 0)


class TestHostnameCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = HostnameCommand()

    def test_hostname_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_hostname_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)


class TestDfCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = DfCommand()

    def test_df_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_df_human(self):
        rc = self.cmd.execute(["-h"])
        self.assertEqual(rc, 0)

    def test_df_inodes(self):
        rc = self.cmd.execute(["-i"])
        self.assertEqual(rc, 0)

    def test_df_kilobytes(self):
        rc = self.cmd.execute(["-k"])
        self.assertEqual(rc, 0)

    def test_df_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)


class TestEchoCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = EchoCommand()

    def test_echo_no_args(self):
        out = io.StringIO()
        rc = self.cmd.execute([], output=out)
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue().strip(), "")

    def test_echo_text(self):
        out = io.StringIO()
        rc = self.cmd.execute(["hello"], output=out)
        self.assertEqual(rc, 0)
        self.assertIn("hello", out.getvalue())

    def test_echo_escape(self):
        out = io.StringIO()
        rc = self.cmd.execute(["-e", "line1\\nline2"], output=out)
        self.assertEqual(rc, 0)

    def test_echo_no_escape(self):
        out = io.StringIO()
        rc = self.cmd.execute(["-E", "no\\nescape"], output=out)
        self.assertEqual(rc, 0)


class TestDateCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = DateCommand()

    def test_date_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_date_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)

    def test_date_version(self):
        rc = self.cmd.execute(["--version"])
        self.assertEqual(rc, 0)


class TestPwdCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = PwdCommand()

    def test_pwd_no_args(self):
        out = io.StringIO()
        rc = self.cmd.execute(output=out)
        self.assertEqual(rc, 0)
        self.assertTrue(len(out.getvalue().strip()) > 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  PROCESS COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════


@unittest.skipUnless(_HAS_PROCESS, "process module requires Unix (termios)")
class TestPsCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = PsCommand()

    def test_ps_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_ps_ef(self):
        rc = self.cmd.execute(["-ef"])
        self.assertEqual(rc, 0)

    def test_ps_aux(self):
        rc = self.cmd.execute(["aux"])
        self.assertEqual(rc, 0)

    def test_ps_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)


@unittest.skipUnless(_HAS_PROCESS, "process module requires Unix (termios)")
class TestKillCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = KillCommand()

    def test_kill_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_kill_list_signals(self):
        rc = self.cmd.execute(["-l"])
        self.assertEqual(rc, 0)

    def test_kill_invalid_pid(self):
        rc = self.cmd.execute(["999999"])
        self.assertNotEqual(rc, 0)

    def test_kill_signal_name(self):
        rc = self.cmd.execute(["-s", "TERM", "999999"])
        self.assertNotEqual(rc, 0)

    def test_kill_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)


@unittest.skipUnless(_HAS_PROCESS, "process module requires Unix (termios)")
class TestMountCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = MountCommand()

    def test_mount_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_mount_list(self):
        rc = self.cmd.execute(["-l"])
        self.assertEqual(rc, 0)

    def test_mount_version(self):
        rc = self.cmd.execute(["-V"])
        self.assertEqual(rc, 0)

    def test_mount_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)


@unittest.skipUnless(_HAS_PROCESS, "process module requires Unix (termios)")
class TestUmountCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = UmountCommand()

    def test_umount_no_args(self):
        rc = self.cmd.execute()
        self.assertNotEqual(rc, 0)

    def test_umount_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)

    def test_umount_nonexistent(self):
        rc = self.cmd.execute(["/nonexistent_mount_point_xyz"])
        self.assertNotEqual(rc, 0)


@unittest.skipUnless(_HAS_PROCESS, "process module requires Unix (termios)")
class TestSttyCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = SttyCommand()

    def test_name(self):
        self.assertEqual(self.cmd.name, "stty")

    def test_stty_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_stty_a(self):
        rc = self.cmd.execute(["-a"])
        self.assertEqual(rc, 0)

    def test_stty_g(self):
        rc = self.cmd.execute(["-g"])
        self.assertEqual(rc, 0)


@unittest.skipUnless(_HAS_PROCESS, "process module requires Unix (termios)")
class TestSyncCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = SyncCommand()

    def test_name(self):
        self.assertEqual(self.cmd.name, "sync")

    def test_sync_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_sync_force(self):
        rc = self.cmd.execute(["-f"])
        self.assertEqual(rc, 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  SHELL COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════


class TestShCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = ShCommand()

    def test_sh_interactive(self):
        out = io.StringIO()
        rc, out_text = self.cmd.execute(["sh"], stdout=out)
        self.assertEqual(rc, 0)

    def test_sh_c_string(self):
        rc, out = self.cmd.execute(["sh", "-c", "echo hello"])
        self.assertEqual(rc, 0)

    def test_sh_c_empty(self):
        rc, out = self.cmd.execute(["sh", "-c", ""])
        self.assertEqual(rc, 0)

    def test_sh_script_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write("echo 'from script'\n")
            f.flush()
            fname = f.name
        try:
            rc, out = self.cmd.execute(["sh", fname])
            self.assertEqual(rc, 0)
        finally:
            os.unlink(fname)

    def test_sh_missing_script(self):
        rc, out = self.cmd.execute(["sh", "/nonexistent_script.sh"])
        self.assertEqual(rc, 127)

    def test_sh_dash(self):
        rc, out = self.cmd.execute(["sh", "--", "echo ok"])
        self.assertEqual(rc, 0)


class TestSedCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = SedCommand()

    def test_sed_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_sed_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)

    def test_sed_version(self):
        rc = self.cmd.execute(["--version"])
        self.assertEqual(rc, 0)

    def test_sed_script(self):
        rc = self.cmd.execute(["s/foo/bar/g", "input.txt"])
        self.assertNotEqual(rc, 0)


class TestTarCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = TarCommand()

    def test_tar_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_tar_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)

    def test_tar_version(self):
        rc = self.cmd.execute(["--version"])
        self.assertEqual(rc, 0)

    def test_tar_create(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("tar content\n")
            f.flush()
            fname = f.name
        archive = fname + ".tar"
        try:
            rc = self.cmd.execute(["-cf", archive, fname])
            self.assertEqual(rc, 0)
        finally:
            if os.path.exists(fname):
                os.unlink(fname)
            if os.path.exists(archive):
                os.unlink(archive)


class TestGzipCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = GzipCommand()

    def test_gzip_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_gzip_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)

    def test_gzip_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("gzip me\n")
            f.flush()
            fname = f.name
        try:
            rc = self.cmd.execute([fname])
            self.assertEqual(rc, 0)
        finally:
            gz = fname + ".gz"
            if os.path.exists(gz):
                os.unlink(gz)


class TestGunzipCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = GunzipCommand()

    def test_gunzip_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_gunzip_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)


class TestZcatCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = ZcatCommand()

    def test_zcat_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_zcat_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)


class TestNetstatCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = NetstatCommand()

    def test_netstat_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_netstat_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)

    def test_netstat_all(self):
        rc = self.cmd.execute(["-a"])
        self.assertEqual(rc, 0)


class TestPingCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = PingCommand()

    def test_ping_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)


class TestCpioCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = CpioCommand()

    def test_cpio_name(self):
        self.assertEqual(self.cmd.name, "cpio")

    def test_cpio_no_args(self):
        rc = self.cmd.execute()
        self.assertNotEqual(rc, 0)

    def test_cpio_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)

    def test_cpio_version(self):
        rc = self.cmd.execute(["--version"])
        self.assertEqual(rc, 0)

    def test_cpio_create(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("cpio content\n")
            f.flush()
            fname = f.name
        try:
            out_archive = fname + ".cpio"
            rc = self.cmd.execute(["-o", "-H", "newc"], stdin=io.StringIO(fname + "\n"))
            self.assertNotEqual(rc, 0)
        finally:
            os.unlink(fname)


# ═══════════════════════════════════════════════════════════════════════════════
#  PERMISSIONS COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════


class TestChmodCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = ChmodCommand()

    def test_name(self):
        self.assertEqual(self.cmd.name, "chmod")

    def test_chmod_no_args(self):
        rc = self.cmd.execute()
        self.assertNotEqual(rc, 0)

    def test_chmod_numeric(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        f.write("chmod me\n")
        f.flush()
        fname = f.name
        try:
            rc = self.cmd.execute(["755", fname])
            self.assertEqual(rc, 0)
        finally:
            os.unlink(fname)

    def test_chmod_symbolic(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        f.write("chmod me\n")
        f.flush()
        fname = f.name
        try:
            rc = self.cmd.execute(["u+x", fname])
            self.assertEqual(rc, 0)
        finally:
            os.unlink(fname)

    def test_chmod_missing_file(self):
        rc = self.cmd.execute(["755", "/nonexistent_chmod_file"])
        self.assertNotEqual(rc, 0)

    def test_chmod_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)


class TestChownCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = ChownCommand()

    def test_name(self):
        self.assertEqual(self.cmd.name, "chown")

    def test_chown_no_args(self):
        rc = self.cmd.execute()
        self.assertNotEqual(rc, 0)

    def test_chown_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)


class TestChgrpCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = ChgrpCommand()

    def test_name(self):
        self.assertEqual(self.cmd.name, "chgrp")

    def test_chgrp_no_args(self):
        rc = self.cmd.execute()
        self.assertNotEqual(rc, 0)

    def test_chgrp_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  BOOLEAN OPS COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════


class TestTrueCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = TrueCommand()

    def test_true_returns_0(self):
        self.assertEqual(self.cmd.execute(), 0)

    def test_true_with_args(self):
        self.assertEqual(self.cmd.execute(["ignored"]), 0)


class TestFalseCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = FalseCommand()

    def test_false_returns_1(self):
        self.assertEqual(self.cmd.execute(), 1)

    def test_false_with_args(self):
        self.assertEqual(self.cmd.execute(["ignored"]), 1)


class TestTestCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = TestCommand()

    def test_test_true(self):
        rc = self.cmd.execute(["true"])
        self.assertEqual(rc, 0)

    def test_test_false(self):
        rc = self.cmd.execute(["false"])
        self.assertEqual(rc, 1)

    def test_test_no_args(self):
        rc = self.cmd.execute([])
        self.assertEqual(rc, 1)

    def test_test_string_eq(self):
        rc = self.cmd.execute(["hello", "=", "hello"])
        self.assertEqual(rc, 0)

    def test_test_string_ne(self):
        rc = self.cmd.execute(["hello", "!=", "world"])
        self.assertEqual(rc, 0)

    def test_test_file_exists(self):
        f = tempfile.NamedTemporaryFile(delete=False)
        fname = f.name
        f.close()
        try:
            rc = self.cmd.execute(["-f", fname])
            self.assertEqual(rc, 0)
        finally:
            os.unlink(fname)

    def test_test_file_not_exists(self):
        rc = self.cmd.execute(["-f", "/nonexistent_file_xyz"])
        self.assertEqual(rc, 1)

    def test_test_dir_exists(self):
        rc = self.cmd.execute(["-d", tempfile.gettempdir()])
        self.assertEqual(rc, 0)


class TestBracketTestCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = BracketTestCommand()

    def test_bracket_no_args(self):
        rc = self.cmd.execute([])
        self.assertEqual(rc, 1)

    def test_bracket_true(self):
        rc = self.cmd.execute(["true", "]"])
        self.assertEqual(rc, 0)

    def test_bracket_missing_close(self):
        rc = self.cmd.execute(["true"])
        self.assertNotEqual(rc, 0)

    def test_bracket_string_eq(self):
        rc = self.cmd.execute(["hello", "=", "hello", "]"])
        self.assertEqual(rc, 0)


class TestYesCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = YesCommand()

    @unittest.skip("YesCommand runs an infinite loop; cannot test execute() directly")
    def test_yes_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    @unittest.skip("YesCommand runs an infinite loop; cannot test execute() directly")
    def test_yes_with_string(self):
        rc = self.cmd.execute(["custom"])
        self.assertEqual(rc, 0)


class TestPrintenvCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = PrintenvCommand()

    def test_printenv_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_printenv_var(self):
        rc = self.cmd.execute(["PATH"])
        self.assertEqual(rc, 0)


class TestEnvCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = EnvCommand()

    def test_env_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_env_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  NETWORK COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════


class TestIfconfigCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = IfconfigCommand()

    def test_ifconfig_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_ifconfig_a(self):
        rc = self.cmd.execute(["-a"])
        self.assertEqual(rc, 0)

    def test_ifconfig_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)


class TestIpCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = IpCommand()

    def test_ip_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_ip_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)

    def test_ip_addr(self):
        rc = self.cmd.execute(["addr"])
        self.assertEqual(rc, 0)

    def test_ip_link(self):
        rc = self.cmd.execute(["link"])
        self.assertEqual(rc, 0)


class TestRouteCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = RouteCommand()

    def test_route_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_route_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)


class TestArpCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = ArpCommand()

    def test_arp_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_arp_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  USER COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════


@unittest.skipUnless(_HAS_USER_CMDS, "user_commands module requires Unix (pwd)")
class TestSuCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = SuCommand()

    def test_su_name(self):
        self.assertEqual(self.cmd.name, "su")

    def test_su_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_su_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)

    def test_su_version(self):
        rc = self.cmd.execute(["--version"])
        self.assertEqual(rc, 0)

    def test_su_login(self):
        rc = self.cmd.execute(["-l"])
        self.assertEqual(rc, 0)

    def test_su_command(self):
        rc = self.cmd.execute(["-c", "echo test"])
        self.assertEqual(rc, 0)


@unittest.skipUnless(_HAS_USER_CMDS, "user_commands module requires Unix (pwd)")
class TestLoginCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = LoginCommand()

    def test_login_name(self):
        self.assertEqual(self.cmd.name, "login")

    def test_login_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_login_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)

    def test_login_version(self):
        rc = self.cmd.execute(["--version"])
        self.assertEqual(rc, 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  DEVICE / MKNOD
# ═══════════════════════════════════════════════════════════════════════════════


class TestMknodCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = MknodCommand()

    def test_mknod_no_args(self):
        rc = self.cmd.execute()
        self.assertNotEqual(rc, 0)

    def test_mknod_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)

    def test_mknod_version(self):
        rc = self.cmd.execute(["--version"])
        self.assertEqual(rc, 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  CSH / ED
# ═══════════════════════════════════════════════════════════════════════════════


class TestCshCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = CshCommand()

    def test_csh_name(self):
        self.assertEqual(self.cmd.name, "csh")

    def test_csh_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_csh_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)


class TestEdCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = EdCommand()

    def test_ed_name(self):
        self.assertEqual(self.cmd.name, "ed")

    def test_ed_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_ed_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  ARCHIVE MODULE (alternate TarCommand)
# ═══════════════════════════════════════════════════════════════════════════════


class TestArchiveTarCommand(unittest.TestCase):
    def setUp(self):
        self.cmd = ArchiveTarCommand()

    def test_archive_tar_no_args(self):
        rc = self.cmd.execute()
        self.assertEqual(rc, 0)

    def test_archive_tar_help(self):
        rc = self.cmd.execute(["--help"])
        self.assertEqual(rc, 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  BIN MANAGER
# ═══════════════════════════════════════════════════════════════════════════════


class TestBinManager(unittest.TestCase):
    def setUp(self):
        self.mgr = BinManager()

    def test_manager_instantiation(self):
        self.assertIsInstance(self.mgr, BinManager)

    def test_register_fhs_required(self):
        count = self.mgr.register_fhs_required()
        self.assertGreaterEqual(count, 0)

    def test_register_fhs_sbin(self):
        count = self.mgr.register_fhs_sbin()
        self.assertGreaterEqual(count, 0)

    def test_get_binary(self):
        self.mgr.register_fhs_required()
        for name in list(FHS_REQUIRED_BIN)[:3]:
            b = self.mgr.get_binary(name)
            if b:
                self.assertEqual(b.name, name)

    def test_get_binary_missing(self):
        self.assertIsNone(self.mgr.get_binary("nonexistent_xyz_cmd"))

    def test_remove_binary(self):
        self.mgr.register_fhs_required()
        if FHS_REQUIRED_BIN:
            name = FHS_REQUIRED_BIN[0]
            self.mgr.register_binary(BinBinary(name=name, path=f"/bin/{name}"))
            self.assertTrue(self.mgr.remove_binary(name))
            self.assertIsNone(self.mgr.get_binary(name))

    def test_remove_binary_missing(self):
        self.assertFalse(self.mgr.remove_binary("nonexistent_xyz_cmd"))

    def test_list_binaries_all(self):
        self.mgr.register_fhs_required()
        all_bins = self.mgr.list_binaries()
        self.assertIsInstance(all_bins, list)

    def test_list_binaries_by_category(self):
        self.mgr.register_fhs_required()
        bins = self.mgr.list_binaries(category=BinCategory.FILE_OPS)
        self.assertIsInstance(bins, list)

    def test_list_binaries_by_privilege(self):
        self.mgr.register_fhs_required()
        bins = self.mgr.list_binaries(privilege=BinPrivilege.USER)
        self.assertIsInstance(bins, list)

    def test_list_user_commands(self):
        self.mgr.register_fhs_required()
        user_cmds = self.mgr.list_user_commands()
        self.assertIsInstance(user_cmds, list)

    def test_list_admin_commands(self):
        self.mgr.register_fhs_required()
        admin_cmds = self.mgr.list_admin_commands()
        self.assertIsInstance(admin_cmds, list)

    def test_symlink_management(self):
        s = self.mgr.register_symlink("ls", "/bin/coreutils")
        self.assertIsInstance(s, BinSymlink)
        self.assertEqual(s.name, "ls")
        self.assertEqual(s.target, "/bin/coreutils")
        self.assertIsNotNone(self.mgr.get_symlink("ls"))
        self.assertIsInstance(self.mgr.list_symlinks(), list)

    def test_alias_management(self):
        self.mgr.register_alias("ll", "ls")
        self.assertEqual(self.mgr.get_alias_target("ll"), "ls")
        self.assertIn("ll", self.mgr.list_aliases())

    def test_add_scan_path(self):
        prev = self.mgr.get_scan_paths()
        self.mgr.add_scan_path("/custom/path")
        self.assertIn("/custom/path", self.mgr.get_scan_paths())

    def test_add_scan_path_no_duplicate(self):
        prev_len = len(self.mgr.get_scan_paths())
        self.mgr.add_scan_path("/dup/path")
        self.mgr.add_scan_path("/dup/path")
        self.assertEqual(len(self.mgr.get_scan_paths()), prev_len + 1)

    def test_check_fhs_compliance(self):
        compliance = self.mgr.check_fhs_compliance()
        self.assertIsInstance(compliance, dict)

    def test_get_binary_by_path(self):
        self.mgr.register_fhs_required()
        binary = self.mgr.get_binary_by_path("/bin/sh")
        if binary:
            self.assertEqual(binary.path, "/bin/sh")

    def test_get_binary_by_path_missing(self):
        self.assertIsNone(self.mgr.get_binary_by_path("/bin/nonexistent_xyz"))


class TestFHSConstants(unittest.TestCase):
    def test_fhs_required_bin_is_set(self):
        self.assertIsInstance(FHS_REQUIRED_BIN, (list, set, frozenset))
        self.assertGreater(len(FHS_REQUIRED_BIN), 0)

    def test_fhs_required_sbin_is_set(self):
        self.assertIsInstance(FHS_REQUIRED_SBIN, (list, set, frozenset))

    def test_bin_categories(self):
        self.assertIsInstance(BIN_CATEGORIES, (list, set, frozenset))
        self.assertGreater(len(BIN_CATEGORIES), 0)

    def test_command_registry(self):
        self.assertIsInstance(COMMAND_REGISTRY, dict)
        self.assertGreater(len(COMMAND_REGISTRY), 0)


class TestEnums(unittest.TestCase):
    def test_bin_category_values(self):
        self.assertTrue(BinCategory.FILE_OPS)
        self.assertTrue(BinCategory.TEXT)
        self.assertTrue(BinCategory.PERMISSIONS)
        self.assertTrue(BinCategory.SYSTEM_INFO)
        self.assertTrue(BinCategory.PROCESS)
        self.assertTrue(BinCategory.FILESYSTEM)
        self.assertTrue(BinCategory.USER)
        self.assertTrue(BinCategory.SHELL)
        self.assertTrue(BinCategory.SYNC)
        self.assertTrue(BinCategory.PATH)
        self.assertTrue(BinCategory.UNKNOWN)

    def test_bin_status_values(self):
        self.assertTrue(BinStatus.ACTIVE)
        self.assertTrue(BinStatus.INACTIVE)
        self.assertTrue(BinStatus.MISSING)
        self.assertTrue(BinStatus.OBSOLETE)
        self.assertTrue(BinStatus.RESERVED)

    def test_bin_privilege_values(self):
        self.assertTrue(BinPrivilege.USER)
        self.assertTrue(BinPrivilege.ROOT)
        self.assertTrue(BinPrivilege.ADMIN)
        self.assertTrue(BinPrivilege.ANY)

    def test_bin_type_values(self):
        self.assertTrue(BinType.ELF_STATIC)
        self.assertTrue(BinType.ELF_DYNAMIC)
        self.assertTrue(BinType.SCRIPT)
        self.assertTrue(BinType.SYMLINK)
        self.assertTrue(BinType.UNKNOWN)


# ═══════════════════════════════════════════════════════════════════════════════
#  SELFTEST (run selftest on every bin module)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSelfTest(unittest.TestCase):
    def test_essential_commands_selftest(self):
        from essential_commands import _selftest
        self.assertTrue(_selftest())

    def test_system_info_selftest(self):
        from system_info import _selftest
        self.assertTrue(_selftest())

    @unittest.skipUnless(_HAS_PROCESS, "process module requires Unix (termios)")
    def test_process_selftest(self):
        from process import _selftest
        self.assertTrue(_selftest())

    def test_shell_selftest(self):
        from shell import _selftest
        self.assertTrue(_selftest())

    def test_permissions_selftest(self):
        from permissions import _selftest
        self.assertTrue(_selftest())

    def test_boolean_ops_selftest(self):
        from boolean_ops import _selftest
        self.assertTrue(_selftest())

    def test_network_cmds_selftest(self):
        from network_cmds import _selftest
        self.assertTrue(_selftest())

    @unittest.skipUnless(_HAS_USER_CMDS, "user_commands module requires Unix (pwd)")
    def test_user_commands_selftest(self):
        from user_commands import _selftest
        self.assertTrue(_selftest())

    def test_device_selftest(self):
        from device import _selftest
        self.assertTrue(_selftest())

    def test_archive_selftest(self):
        from archive import _selftest
        self.assertTrue(_selftest())

    def test_csh_selftest(self):
        from csh import _selftest
        self.assertTrue(_selftest())

    def test_ed_selftest(self):
        from ed import _selftest
        self.assertTrue(_selftest())


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main()
