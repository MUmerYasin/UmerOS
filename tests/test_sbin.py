"""
Test /sbin modules - comprehensive coverage for boot, filesystem, modules, network, system, mount, maintenance
"""
from __future__ import annotations
import unittest
import os
import sys

_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_this_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
_sbin_dir = os.path.join(_project_root, "sbin")
if _sbin_dir not in sys.path:
    sys.path.insert(0, _sbin_dir)

from boot import (
    HaltCommand, InitCommand, PoweroffCommand, RebootCommand,
    ShutdownCommand, GettyCommand, FastbootCommand, FasthaltCommand,
    UpdateCommand,
)
from filesystem import (
    FdiskCommand, FsckCommand, MkfsCommand, SwaponCommand,
    SwapoffCommand, MkswapCommand, ChrootCommand,
)
from modules import (
    InsmodCommand, LsmodCommand, ModprobeCommand, RmmodCommand,
    DepmodCommand,
)
from network import IfconfigCommand, IpCommand, RouteCommand
from system import SysctlCommand, HwclockCommand, LdconfigCommand
from mount import (
    MountCommand, UmountCommand, MknodCommand, LosetupCommand,
    PivotRootCommand,
)
from maintenance import (
    Tune2fsCommand, E2fsckCommand, Mke2fsCommand, CtrlaltdelCommand,
    KbdrateCommand, LoadkeysCommand, DumpCommand, RestoreCommand,
    SlnCommand, MktempCommand, SetfdprmCommand, RdevCommand,
)
from sbin_manager import (
    SbinManager, FHS_REQUIRED_SBIN, FHS_OPTIONAL_SBIN,
    ALL_SBIN_ENTRIES, SBIN_COMMAND_REGISTRY,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  BOOT COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

class TestHalt(unittest.TestCase):
    def test_halt_no_args(self):
        cmd = HaltCommand()
        self.assertEqual(cmd.name, "halt")
        self.assertTrue(cmd.description)
        self.assertEqual(cmd.execute(), 0)

    def test_halt_help(self):
        self.assertEqual(HaltCommand().execute(["-h"]), 0)

    def test_halt_version(self):
        self.assertEqual(HaltCommand().execute(["-V"]), 0)

    def test_halt_w(self):
        self.assertEqual(HaltCommand().execute(["-w"]), 0)

    def test_halt_f(self):
        self.assertEqual(HaltCommand().execute(["-f"]), 0)

    def test_halt_p(self):
        self.assertEqual(HaltCommand().execute(["-p"]), 0)


class TestInit(unittest.TestCase):
    def test_init_no_args(self):
        cmd = InitCommand()
        self.assertEqual(cmd.name, "init")
        self.assertEqual(cmd.execute(), 0)

    def test_init_runlevel_3(self):
        self.assertEqual(InitCommand().execute(["3"]), 0)

    def test_init_runlevel_5(self):
        self.assertEqual(InitCommand().execute(["5"]), 0)

    def test_init_s(self):
        self.assertEqual(InitCommand().execute(["s"]), 0)

    def test_init_q(self):
        self.assertEqual(InitCommand().execute(["-q"]), 0)

    def test_init_bad_level(self):
        self.assertEqual(InitCommand().execute(["99"]), 1)

    def test_init_bad_target(self):
        self.assertEqual(InitCommand().execute(["unknown"]), 1)


class TestPoweroff(unittest.TestCase):
    def test_poweroff(self):
        self.assertEqual(PoweroffCommand().execute(), 0)

    def test_poweroff_w(self):
        self.assertEqual(PoweroffCommand().execute(["-w"]), 0)

    def test_poweroff_f(self):
        self.assertEqual(PoweroffCommand().execute(["-f"]), 0)

    def test_poweroff_h(self):
        self.assertEqual(PoweroffCommand().execute(["-h"]), 0)

    def test_poweroff_v(self):
        self.assertEqual(PoweroffCommand().execute(["-V"]), 0)


class TestReboot(unittest.TestCase):
    def test_reboot(self):
        self.assertEqual(RebootCommand().execute(), 0)

    def test_reboot_w(self):
        self.assertEqual(RebootCommand().execute(["-w"]), 0)

    def test_reboot_f(self):
        self.assertEqual(RebootCommand().execute(["-f"]), 0)

    def test_reboot_h(self):
        self.assertEqual(RebootCommand().execute(["-h"]), 0)

    def test_reboot_v(self):
        self.assertEqual(RebootCommand().execute(["-V"]), 0)


class TestShutdown(unittest.TestCase):
    def test_shutdown_no_args(self):
        self.assertEqual(ShutdownCommand().execute(), 1)

    def test_shutdown_now(self):
        self.assertEqual(ShutdownCommand().execute(["now"]), 0)

    def test_shutdown_plus(self):
        self.assertEqual(ShutdownCommand().execute(["+10"]), 0)

    def test_shutdown_time(self):
        self.assertEqual(ShutdownCommand().execute(["12:00"]), 0)

    def test_shutdown_cancel(self):
        self.assertEqual(ShutdownCommand().execute(["-c"]), 0)

    def test_shutdown_help(self):
        self.assertEqual(ShutdownCommand().execute(["-h"]), 0)


class TestGetty(unittest.TestCase):
    def test_getty_no_args(self):
        self.assertEqual(GettyCommand().execute(), 0)

    def test_getty_115200(self):
        self.assertEqual(GettyCommand().execute(["115200", "/dev/tty1"]), 0)

    def test_getty_h(self):
        self.assertEqual(GettyCommand().execute(["-h"]), 0)


class TestFastboot(unittest.TestCase):
    def test_fastboot(self):
        self.assertEqual(FastbootCommand().execute(), 0)

    def test_fastboot_h(self):
        self.assertEqual(FastbootCommand().execute(["-h"]), 0)


class TestFasthalt(unittest.TestCase):
    def test_fasthalt(self):
        self.assertEqual(FasthaltCommand().execute(), 0)

    def test_fasthalt_h(self):
        self.assertEqual(FasthaltCommand().execute(["-h"]), 0)


class TestUpdate(unittest.TestCase):
    def test_update(self):
        self.assertEqual(UpdateCommand().execute(), 0)

    def test_update_h(self):
        self.assertEqual(UpdateCommand().execute(["-h"]), 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  FILESYSTEM COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

class TestFdisk(unittest.TestCase):
    def test_fdisk_list(self):
        self.assertEqual(FdiskCommand().execute(["-l"]), 0)

    def test_fdisk_l_device(self):
        self.assertEqual(FdiskCommand().execute(["-l", "/dev/sda"]), 0)

    def test_fdisk_l_none(self):
        self.assertEqual(FdiskCommand().execute(["-l", "/dev/nonexistent"]), 1)

    def test_fdisk_p(self):
        self.assertEqual(FdiskCommand().execute(["-p", "/dev/sda"]), 0)

    def test_fdisk_h(self):
        self.assertEqual(FdiskCommand().execute(["-h"]), 0)


class TestFsck(unittest.TestCase):
    def test_fsck_a(self):
        self.assertEqual(FsckCommand().execute(["-a", "/dev/sda1"]), 0)

    def test_fsck_y(self):
        self.assertEqual(FsckCommand().execute(["-y", "/dev/sda1"]), 0)

    def test_fsck_n(self):
        self.assertEqual(FsckCommand().execute(["-n", "/dev/sda1"]), 0)

    def test_fsck_t(self):
        self.assertEqual(FsckCommand().execute(["-t", "ext4", "/dev/sda1"]), 0)

    def test_fsck_h(self):
        self.assertEqual(FsckCommand().execute(["-h"]), 0)

    def test_fsck_no_args(self):
        self.assertEqual(FsckCommand().execute(), 1)


class TestMkfs(unittest.TestCase):
    def test_mkfs_dev(self):
        self.assertEqual(MkfsCommand().execute(["/dev/sdb1"]), 0)

    def test_mkfs_t_ext4(self):
        self.assertEqual(MkfsCommand().execute(["-t", "ext4", "/dev/sdb1"]), 0)

    def test_mkfs_b(self):
        self.assertEqual(MkfsCommand().execute(["-b", "2048", "/dev/sdb1"]), 0)

    def test_mkfs_L(self):
        self.assertEqual(MkfsCommand().execute(["-L", "root", "/dev/sdb1"]), 0)

    def test_mkfs_h(self):
        self.assertEqual(MkfsCommand().execute(["-h"]), 0)

    def test_mkfs_no_args(self):
        self.assertEqual(MkfsCommand().execute(), 1)


class TestSwapon(unittest.TestCase):
    def test_swapon_dev(self):
        self.assertEqual(SwaponCommand().execute(["/dev/sdb2"]), 0)

    def test_swapon_a(self):
        self.assertEqual(SwaponCommand().execute(["-a"]), 0)

    def test_swapon_p(self):
        self.assertEqual(SwaponCommand().execute(["-p", "10", "/dev/sdb2"]), 0)

    def test_swapon_h(self):
        self.assertEqual(SwaponCommand().execute(["-h"]), 0)

    def test_swapon_no_args(self):
        self.assertEqual(SwaponCommand().execute(), 1)


class TestSwapoff(unittest.TestCase):
    def test_swapoff_dev(self):
        self.assertEqual(SwapoffCommand().execute(["/dev/sdb2"]), 0)

    def test_swapoff_a(self):
        self.assertEqual(SwapoffCommand().execute(["-a"]), 0)

    def test_swapoff_h(self):
        self.assertEqual(SwapoffCommand().execute(["-h"]), 0)

    def test_swapoff_no_args(self):
        self.assertEqual(SwapoffCommand().execute(), 1)


class TestMkswap(unittest.TestCase):
    def test_mkswap_dev(self):
        self.assertEqual(MkswapCommand().execute(["/dev/sdb2"]), 0)

    def test_mkswap_L(self):
        self.assertEqual(MkswapCommand().execute(["-L", "myswap", "/dev/sdb2"]), 0)

    def test_mkswap_h(self):
        self.assertEqual(MkswapCommand().execute(["-h"]), 0)

    def test_mkswap_no_args(self):
        self.assertEqual(MkswapCommand().execute(), 1)


class TestChroot(unittest.TestCase):
    def test_chroot_dir(self):
        self.assertEqual(ChrootCommand().execute(["/"]), 0)

    def test_chroot_cmd(self):
        self.assertEqual(ChrootCommand().execute(["/mnt", "ls"]), 0)

    def test_chroot_h(self):
        self.assertEqual(ChrootCommand().execute(["-h"]), 0)

    def test_chroot_no_args(self):
        self.assertEqual(ChrootCommand().execute(), 1)


# ═══════════════════════════════════════════════════════════════════════════════
#  KERNEL MODULE COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

class TestInsmod(unittest.TestCase):
    def test_insmod_file(self):
        self.assertEqual(InsmodCommand().execute(["/lib/modules/test.ko"]), 0)

    def test_insmod_h(self):
        self.assertEqual(InsmodCommand().execute(["-h"]), 0)

    def test_insmod_no_args(self):
        self.assertEqual(InsmodCommand().execute(), 1)


class TestLsmod(unittest.TestCase):
    def test_lsmod(self):
        self.assertEqual(LsmodCommand().execute(), 0)

    def test_lsmod_h(self):
        self.assertEqual(LsmodCommand().execute(["-h"]), 0)


class TestModprobe(unittest.TestCase):
    def test_modprobe_load(self):
        self.assertEqual(ModprobeCommand().execute(["test"]), 0)

    def test_modprobe_r(self):
        self.assertEqual(ModprobeCommand().execute(["-r", "test"]), 0)

    def test_modprobe_l(self):
        self.assertEqual(ModprobeCommand().execute(["-l"]), 0)

    def test_modprobe_h(self):
        self.assertEqual(ModprobeCommand().execute(["-h"]), 0)

    def test_modprobe_no_args(self):
        self.assertEqual(ModprobeCommand().execute(), 1)


class TestRmmod(unittest.TestCase):
    def test_rmmod_module(self):
        self.assertEqual(RmmodCommand().execute(["test"]), 0)

    def test_rmmod_f(self):
        self.assertEqual(RmmodCommand().execute(["-f", "test"]), 0)

    def test_rmmod_h(self):
        self.assertEqual(RmmodCommand().execute(["-h"]), 0)

    def test_rmmod_no_args(self):
        self.assertEqual(RmmodCommand().execute(), 1)


class TestDepmod(unittest.TestCase):
    def test_depmod(self):
        self.assertEqual(DepmodCommand().execute(), 0)

    def test_depmod_a(self):
        self.assertEqual(DepmodCommand().execute(["-a"]), 0)

    def test_depmod_h(self):
        self.assertEqual(DepmodCommand().execute(["-h"]), 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  NETWORK COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

class TestIfconfig(unittest.TestCase):
    def test_ifconfig_no_args(self):
        self.assertEqual(IfconfigCommand().execute(), 0)

    def test_ifconfig_a(self):
        self.assertEqual(IfconfigCommand().execute(["-a"]), 0)

    def test_ifconfig_up(self):
        self.assertEqual(IfconfigCommand().execute(["eth0", "up"]), 0)

    def test_ifconfig_down(self):
        self.assertEqual(IfconfigCommand().execute(["eth0", "down"]), 0)

    def test_ifconfig_ip(self):
        self.assertEqual(IfconfigCommand().execute(["eth0", "192.168.1.1"]), 0)

    def test_ifconfig_netmask(self):
        self.assertEqual(IfconfigCommand().execute(["eth0", "netmask", "255.255.255.0"]), 0)

    def test_ifconfig_h(self):
        self.assertEqual(IfconfigCommand().execute(["-h"]), 0)

    def test_ifconfig_v(self):
        self.assertEqual(IfconfigCommand().execute(["-V"]), 0)


class TestIp(unittest.TestCase):
    def test_ip_no_args(self):
        self.assertEqual(IpCommand().execute(), 1)

    def test_ip_addr(self):
        self.assertEqual(IpCommand().execute(["addr"]), 0)

    def test_ip_route(self):
        self.assertEqual(IpCommand().execute(["route"]), 0)

    def test_ip_link(self):
        self.assertEqual(IpCommand().execute(["link"]), 0)

    def test_ip_a(self):
        self.assertEqual(IpCommand().execute(["a"]), 0)

    def test_ip_r(self):
        self.assertEqual(IpCommand().execute(["r"]), 0)

    def test_ip_help(self):
        self.assertEqual(IpCommand().execute(["help"]), 0)

    def test_ip_bad(self):
        self.assertEqual(IpCommand().execute(["unknown"]), 1)


class TestRoute(unittest.TestCase):
    def test_route_no_args(self):
        self.assertEqual(RouteCommand().execute(), 0)

    def test_route_n(self):
        self.assertEqual(RouteCommand().execute(["-n"]), 0)

    def test_route_add(self):
        self.assertEqual(RouteCommand().execute(["add", "-net", "192.168.2.0/24", "gw", "192.168.1.1"]), 0)

    def test_route_del(self):
        self.assertEqual(RouteCommand().execute(["del", "-net", "192.168.2.0/24"]), 0)

    def test_route_help(self):
        self.assertEqual(RouteCommand().execute(["-h"]), 0)

    def test_route_bad(self):
        self.assertEqual(RouteCommand().execute(["unknown"]), 1)


# ═══════════════════════════════════════════════════════════════════════════════
#  SYSTEM COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSysctl(unittest.TestCase):
    def test_sysctl_a(self):
        self.assertEqual(SysctlCommand().execute(["-a"]), 0)

    def test_sysctl_w(self):
        self.assertEqual(SysctlCommand().execute(["-w", "net.ipv4.ip_forward=1"]), 0)

    def test_sysctl_p(self):
        self.assertEqual(SysctlCommand().execute(["-p", "/etc/sysctl.conf"]), 0)

    def test_sysctl_h(self):
        self.assertEqual(SysctlCommand().execute(["-h"]), 0)

    def test_sysctl_key(self):
        self.assertEqual(SysctlCommand().execute(["net.ipv4.ip_forward"]), 0)

    def test_sysctl_no_args(self):
        self.assertEqual(SysctlCommand().execute(), 1)


class TestHwclock(unittest.TestCase):
    def test_hwclock(self):
        self.assertEqual(HwclockCommand().execute(), 0)

    def test_hwclock_r(self):
        self.assertEqual(HwclockCommand().execute(["-r"]), 0)

    def test_hwclock_w(self):
        self.assertEqual(HwclockCommand().execute(["-w"]), 0)

    def test_hwclock_s(self):
        self.assertEqual(HwclockCommand().execute(["-s"]), 0)

    def test_hwclock_h(self):
        self.assertEqual(HwclockCommand().execute(["-h"]), 0)


class TestLdconfig(unittest.TestCase):
    def test_ldconfig(self):
        self.assertEqual(LdconfigCommand().execute(), 0)

    def test_ldconfig_v(self):
        self.assertEqual(LdconfigCommand().execute(["-v"]), 0)

    def test_ldconfig_p(self):
        self.assertEqual(LdconfigCommand().execute(["-p"]), 0)

    def test_ldconfig_dirs(self):
        self.assertEqual(LdconfigCommand().execute(["-N", "/usr/lib"]), 0)

    def test_ldconfig_h(self):
        self.assertEqual(LdconfigCommand().execute(["-h"]), 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  MOUNT COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

class TestMount(unittest.TestCase):
    def test_mount_list(self):
        self.assertEqual(MountCommand().execute(), 0)

    def test_mount_a(self):
        self.assertEqual(MountCommand().execute(["-a"]), 0)

    def test_mount_l(self):
        self.assertEqual(MountCommand().execute(["-l"]), 0)

    def test_mount_v(self):
        self.assertEqual(MountCommand().execute(["-V"]), 0)

    def test_mount_f(self):
        self.assertEqual(MountCommand().execute(["-f"]), 0)

    def test_mount_h(self):
        self.assertEqual(MountCommand().execute(["-h"]), 0)

    def test_mount_device_point(self):
        self.assertEqual(MountCommand().execute(["/dev/sdb1", "/mnt/usb"]), 0)

    def test_mount_t_o(self):
        self.assertEqual(MountCommand().execute(["-t", "vfat", "-o", "rw", "/dev/sdb2", "/mnt/usb2"]), 0)


class TestUmount(unittest.TestCase):
    def test_umount_help(self):
        self.assertEqual(UmountCommand().execute(["-h"]), 0)

    def test_umount_version(self):
        self.assertEqual(UmountCommand().execute(["-V"]), 0)

    def test_umount_target(self):
        self.assertEqual(UmountCommand().execute(["/tmp"]), 0)

    def test_umount_not_mounted(self):
        self.assertEqual(UmountCommand().execute(["/nonexistent"]), 1)

    def test_umount_no_args(self):
        self.assertEqual(UmountCommand().execute(), 1)

    def test_umount_a(self):
        self.assertEqual(UmountCommand().execute(["-a"]), 0)


class TestMknod(unittest.TestCase):
    def test_mknod_no_args(self):
        self.assertEqual(MknodCommand().execute(), 1)

    def test_mknod_block(self):
        self.assertEqual(MknodCommand().execute(["/dev/test", "b", "1", "0"]), 0)

    def test_mknod_char(self):
        self.assertEqual(MknodCommand().execute(["/dev/testchar", "c", "1", "1"]), 0)

    def test_mknod_pipe(self):
        self.assertEqual(MknodCommand().execute(["/dev/testpipe", "p"]), 0)

    def test_mknod_m(self):
        self.assertEqual(MknodCommand().execute(["-m", "0644", "/dev/testm", "b", "1", "2"]), 0)

    def test_mknod_invalid_type(self):
        self.assertEqual(MknodCommand().execute(["/dev/test", "x"]), 1)

    def test_mknod_missing_major(self):
        self.assertEqual(MknodCommand().execute(["/dev/test", "b"]), 1)


class TestLosetup(unittest.TestCase):
    def test_losetup_list(self):
        self.assertEqual(LosetupCommand().execute(), 0)

    def test_losetup_find(self):
        self.assertEqual(LosetupCommand().execute(["-f"]), 0)

    def test_losetup_attach(self):
        self.assertEqual(LosetupCommand().execute(["/dev/loop0", "/tmp/test.img"]), 0)

    def test_losetup_a(self):
        self.assertEqual(LosetupCommand().execute(["-a"]), 0)

    def test_losetup_detach(self):
        self.assertEqual(LosetupCommand().execute(["-d", "/dev/loop0"]), 0)

    def test_losetup_detach_nonexistent(self):
        self.assertEqual(LosetupCommand().execute(["-d", "/dev/nonexistent"]), 1)

    def test_losetup_v(self):
        self.assertEqual(LosetupCommand().execute(["-V"]), 0)

    def test_losetup_h(self):
        self.assertEqual(LosetupCommand().execute(["-h"]), 0)


class TestPivotRoot(unittest.TestCase):
    def test_pivot_root_no_args(self):
        self.assertEqual(PivotRootCommand().execute(), 1)

    def test_pivot_root_one_arg(self):
        self.assertEqual(PivotRootCommand().execute(["/new"]), 1)

    def test_pivot_root_two_args(self):
        self.assertEqual(PivotRootCommand().execute(["/new", "/old"]), 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAINTENANCE COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

class TestTune2fs(unittest.TestCase):
    def test_tune2fs_no_args(self):
        self.assertEqual(Tune2fsCommand().execute(), 1)

    def test_tune2fs_help(self):
        self.assertEqual(Tune2fsCommand().execute(["-h"]), 0)

    def test_tune2fs_list(self):
        self.assertEqual(Tune2fsCommand().execute(["-l", "/dev/sda1"]), 0)

    def test_tune2fs_c(self):
        self.assertEqual(Tune2fsCommand().execute(["-c", "5", "/dev/sda1"]), 0)

    def test_tune2fs_L(self):
        self.assertEqual(Tune2fsCommand().execute(["-L", "test", "/dev/sda1"]), 0)

    def test_tune2fs_U(self):
        self.assertEqual(Tune2fsCommand().execute(["-U", "1234-5678", "/dev/sda1"]), 0)

    def test_tune2fs_i(self):
        self.assertEqual(Tune2fsCommand().execute(["-i", "30", "/dev/sda1"]), 0)


class TestE2fsck(unittest.TestCase):
    def test_e2fsck_no_args(self):
        self.assertEqual(E2fsckCommand().execute(), 1)

    def test_e2fsck_help(self):
        self.assertEqual(E2fsckCommand().execute(["-h"]), 0)

    def test_e2fsck_dev(self):
        self.assertEqual(E2fsckCommand().execute(["/dev/sda1"]), 0)

    def test_e2fsck_f(self):
        self.assertEqual(E2fsckCommand().execute(["-f", "/dev/sda1"]), 0)

    def test_e2fsck_y(self):
        self.assertEqual(E2fsckCommand().execute(["-y", "/dev/sda1"]), 0)

    def test_e2fsck_n(self):
        self.assertEqual(E2fsckCommand().execute(["-n", "/dev/sda1"]), 0)

    def test_e2fsck_p(self):
        self.assertEqual(E2fsckCommand().execute(["-p", "/dev/sda1"]), 0)


class TestMke2fs(unittest.TestCase):
    def test_mke2fs_no_args(self):
        self.assertEqual(Mke2fsCommand().execute(), 1)

    def test_mke2fs_help(self):
        self.assertEqual(Mke2fsCommand().execute(["-h"]), 0)

    def test_mke2fs_dev(self):
        self.assertEqual(Mke2fsCommand().execute(["/dev/sdb1"]), 0)

    def test_mke2fs_t(self):
        self.assertEqual(Mke2fsCommand().execute(["-t", "ext3", "/dev/sdb1"]), 0)

    def test_mke2fs_b(self):
        self.assertEqual(Mke2fsCommand().execute(["-b", "2048", "/dev/sdb1"]), 0)

    def test_mke2fs_L(self):
        self.assertEqual(Mke2fsCommand().execute(["-L", "rootfs", "/dev/sdb1"]), 0)

    def test_mke2fs_n(self):
        self.assertEqual(Mke2fsCommand().execute(["-n", "/dev/sdb1"]), 0)


class TestCtrlaltdel(unittest.TestCase):
    def test_ctrlaltdel_no_args(self):
        self.assertEqual(CtrlaltdelCommand().execute(), 0)

    def test_ctrlaltdel_hard(self):
        self.assertEqual(CtrlaltdelCommand().execute(["hard"]), 0)

    def test_ctrlaltdel_soft(self):
        self.assertEqual(CtrlaltdelCommand().execute(["soft"]), 0)

    def test_ctrlaltdel_invalid(self):
        self.assertEqual(CtrlaltdelCommand().execute(["invalid"]), 1)


class TestKbdrate(unittest.TestCase):
    def test_kbdrate_no_args(self):
        self.assertEqual(KbdrateCommand().execute(), 0)

    def test_kbdrate_r(self):
        self.assertEqual(KbdrateCommand().execute(["-r", "50"]), 0)

    def test_kbdrate_d(self):
        self.assertEqual(KbdrateCommand().execute(["-d", "500"]), 0)

    def test_kbdrate_s(self):
        self.assertEqual(KbdrateCommand().execute(["-s"]), 0)

    def test_kbdrate_h(self):
        self.assertEqual(KbdrateCommand().execute(["-h"]), 0)

    def test_kbdrate_rd(self):
        self.assertEqual(KbdrateCommand().execute(["-r", "20", "-d", "500"]), 0)


class TestLoadkeys(unittest.TestCase):
    def test_loadkeys_no_args(self):
        self.assertEqual(LoadkeysCommand().execute(), 1)

    def test_loadkeys_us(self):
        self.assertEqual(LoadkeysCommand().execute(["us"]), 0)

    def test_loadkeys_d(self):
        self.assertEqual(LoadkeysCommand().execute(["-d", "defkeymap"]), 0)

    def test_loadkeys_q(self):
        self.assertEqual(LoadkeysCommand().execute(["-q", "us"]), 0)

    def test_loadkeys_h(self):
        self.assertEqual(LoadkeysCommand().execute(["-h"]), 0)

    def test_loadkeys_u(self):
        self.assertEqual(LoadkeysCommand().execute(["-u", "us"]), 0)


class TestDump(unittest.TestCase):
    def test_dump_no_args(self):
        self.assertEqual(DumpCommand().execute(), 1)

    def test_dump_help(self):
        self.assertEqual(DumpCommand().execute(["-h"]), 0)

    def test_dump_level_fs(self):
        self.assertEqual(DumpCommand().execute(["0", "/dev/sda1"]), 0)

    def test_dump_f(self):
        self.assertEqual(DumpCommand().execute(["-f", "/tmp/dump.img", "0", "/dev/sda1"]), 0)


class TestRestore(unittest.TestCase):
    def test_restore_no_args(self):
        self.assertEqual(RestoreCommand().execute(), 0)

    def test_restore_help(self):
        self.assertEqual(RestoreCommand().execute(["-h"]), 0)

    def test_restore_r(self):
        self.assertEqual(RestoreCommand().execute(["-r"]), 0)

    def test_restore_R(self):
        self.assertEqual(RestoreCommand().execute(["-R"]), 0)

    def test_restore_x(self):
        self.assertEqual(RestoreCommand().execute(["-x"]), 0)

    def test_restore_C(self):
        self.assertEqual(RestoreCommand().execute(["-C"]), 0)

    def test_restore_f(self):
        self.assertEqual(RestoreCommand().execute(["-f", "/tmp/dump.img"]), 0)

    def test_restore_T(self):
        self.assertEqual(RestoreCommand().execute(["-T", "/tmp"]), 0)


class TestSln(unittest.TestCase):
    def test_sln_no_args(self):
        self.assertEqual(SlnCommand().execute(), 1)

    def test_sln_one_arg(self):
        self.assertEqual(SlnCommand().execute(["/lib/libc.so"]), 1)

    def test_sln_two_args(self):
        self.assertEqual(SlnCommand().execute(["/lib/libc.so", "/lib/libc.so.6"]), 0)


class TestMktemp(unittest.TestCase):
    def test_mktemp_no_args(self):
        self.assertEqual(MktempCommand().execute(), 0)

    def test_mktemp_d(self):
        self.assertEqual(MktempCommand().execute(["-d"]), 0)

    def test_mktemp_t(self):
        self.assertEqual(MktempCommand().execute(["-t", "test.XXXXXX"]), 0)

    def test_mktemp_h(self):
        self.assertEqual(MktempCommand().execute(["-h"]), 0)

    def test_mktemp_template(self):
        self.assertEqual(MktempCommand().execute(["/tmp/tmp.XXXXXX"]), 0)


class TestSetfdprm(unittest.TestCase):
    def test_setfdprm_no_args(self):
        self.assertEqual(SetfdprmCommand().execute(), 1)

    def test_setfdprm_one_arg(self):
        self.assertEqual(SetfdprmCommand().execute(["/dev/fd0"]), 1)

    def test_setfdprm_two_args(self):
        self.assertEqual(SetfdprmCommand().execute(["/dev/fd0", "1440"]), 0)


class TestRdev(unittest.TestCase):
    def test_rdev_no_args(self):
        self.assertEqual(RdevCommand().execute(), 0)

    def test_rdev_one_arg(self):
        self.assertEqual(RdevCommand().execute(["/dev/sda1"]), 0)

    def test_rdev_two_args(self):
        self.assertEqual(RdevCommand().execute(["/dev/sda1", "/boot/vmlinuz"]), 0)


# ═══════════════════════════════════════════════════════════════════════════════
#  SBIN MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class TestSbinManager(unittest.TestCase):
    def test_has_required_commands(self):
        mgr = SbinManager()
        for cmd in FHS_REQUIRED_SBIN:
            self.assertTrue(mgr.has_command(cmd), f"Missing required: {cmd}")

    def test_has_optional_commands(self):
        mgr = SbinManager()
        for cmd in FHS_OPTIONAL_SBIN:
            self.assertTrue(mgr.has_command(cmd), f"Missing optional: {cmd}")

    def test_list_commands(self):
        mgr = SbinManager()
        cmds = mgr.list_commands()
        self.assertGreater(len(cmds), 30)

    def test_get_command(self):
        mgr = SbinManager()
        self.assertIsNotNone(mgr.get_command("halt"))
        self.assertIsNotNone(mgr.get_command("mount"))
        self.assertIsNotNone(mgr.get_command("mktemp"))
        self.assertIsNone(mgr.get_command("nonexistent"))

    def test_execute(self):
        mgr = SbinManager()
        self.assertEqual(mgr.execute("halt"), 0)
        self.assertEqual(mgr.execute("nonexistent"), 127)

    def test_check_compliance(self):
        mgr = SbinManager()
        c = mgr.check_compliance()
        self.assertTrue(c["compliant"])
        self.assertEqual(len(c["required_missing"]), 0)
        self.assertGreater(c["total_commands"], 30)


# ═══════════════════════════════════════════════════════════════════════════════
#  SELFTEST RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

class TestSelftest(unittest.TestCase):
    def test_boot_selftest(self):
        from boot import _selftest
        self.assertTrue(_selftest())

    def test_filesystem_selftest(self):
        from filesystem import _selftest
        self.assertTrue(_selftest())

    def test_modules_selftest(self):
        from modules import _selftest
        self.assertTrue(_selftest())

    def test_network_selftest(self):
        from network import _selftest
        self.assertTrue(_selftest())

    def test_system_selftest(self):
        from system import _selftest
        self.assertTrue(_selftest())

    def test_mount_selftest(self):
        from mount import _selftest
        self.assertTrue(_selftest())

    def test_maintenance_selftest(self):
        from maintenance import _selftest
        self.assertTrue(_selftest())


if __name__ == "__main__":
    unittest.main(verbosity=2)
