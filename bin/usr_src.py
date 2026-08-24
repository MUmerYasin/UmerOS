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
UmerOS /usr/src - Source Code Hierarchy
========================================
/usr: Contains kernel sources, header files, and documentation.
"""

from __future__ import annotations

from core.command import Command


class SrcDirCommand(Command):
    """Source code directory listing."""

    name = "src-dir"
    description = "List /usr/src source code directories"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/        - Source code\n"
            "  /              -  kernel source\n"
            "  headers/       - headers for compilation\n"
            "  packages/      - Source packages\n"
        )


class SrcLinuxCommand(Command):
    """ kernel source directory."""

    name = "src"
    description = "/usr/src/ - kernel source tree"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/         - kernel source\n"
            "  .config         - Kernel configuration\n"
            "  Makefile        - Build system\n"
            "  README          - Kernel release notes\n"
            "  CREDITS         - Contributors\n"
            "  MAINTAINERS     - Subsystem maintainers\n"
            "  COPYING         - GNU GPL license\n"
            "  arch/           - Architecture-specific code\n"
            "  drivers/        - Device drivers\n"
            "  fs/             - Filesystems\n"
            "  net/            - Networking\n"
            "  mm/             - Memory management\n"
            "  kernel/         - Core kernel\n"
            "  Documentation/  - Kernel docs\n"
        )


class SrcKernelHeadersCommand(Command):
    """Kernel headers directory."""

    name = "src-kernel-headers"
    description = "/usr/src/headers - kernel headers for building modules"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/headers-$(uname -r)/\n"
            "  Kconfig, Makefile, Module.symvers\n"
            "  include/  - Kernel headers\n"
            "  scripts/  - Build scripts\n"
            "  arch/     - Architecture headers\n"
        )


class SrcRPMBuildCommand(Command):
    """RPM build directory."""

    name = "src-rpm-build"
    description = "/usr/src/RPM/BUILD - RPM build area"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/RPM/\n"
            "  BUILD/      - Temporary build files\n"
            "  RPMS/       - Built RPM packages\n"
            "  SOURCES/    - Source tarballs, patches\n"
            "  SPECS/      - RPM spec files\n"
            "  SRPMS/      - Source RPMs\n"
        )


# ─── Kernel Subsystem Headers ───────────────────────────────────────────────


class SrcNetCommand(Command):
    """kernel networking subsystem."""

    name = "src-net"
    description = "/usr/src/net - Kernel networking stack"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/net/ - Networking subsystem\n"
            "  ipv4/        - IPv4 stack (TCP, UDP, ICMP, IP)\n"
            "  ipv6/        - IPv6 stack\n"
            "  netfilter/   - Packet filtering (iptables, nftables)\n"
            "  unix/        - Unix domain sockets\n"
            "  bluetooth/   - Bluetooth protocol stack\n"
            "  bridge/      - Ethernet bridging\n"
            "  mac80211/    - Wireless MAC layer\n"
            "  qrtr/        - QRTR IPC (Qualcomm)\n"
            "  tipc/        - Transparent Inter-Process Communication\n"
            "  xfrm/        - IPsec framework\n"
            "  af_packet.c  - Raw packet socket implementation\n"
        )


class SrcDriversCommand(Command):
    """kernel device drivers."""

    name = "src-drivers"
    description = "/usr/src/drivers - Kernel device drivers"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/drivers/ - Device drivers\n"
            "  net/         - Network interface drivers\n"
            "  block/       - Block device drivers (SCSI, IDE, NVMe)\n"
            "  char/        - Character device drivers\n"
            "  usb/         - USB host and gadget drivers\n"
            "  pci/         - PCI bus drivers\n"
            "  gpu/         - GPU/display drivers (DRM/KMS)\n"
            "  input/       - Input subsystem (keyboard, mouse, touch)\n"
            "  scsi/        - SCSI subsystem drivers\n"
            "  nvme/        - NVMe SSD drivers\n"
            "  sound/       - ALSA sound drivers\n"
            "  media/       - Video capture and DVB drivers\n"
            "  hid/         - Human Interface Device drivers\n"
            "  acpi/        - ACPI platform drivers\n"
            "  firmware/    - Firmware loading helpers\n"
        )


class SrcFsCommand(Command):
    """kernel filesystem implementations."""

    name = "src-fs"
    description = "/usr/src/fs - Kernel filesystem implementations"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/fs/ - Filesystem implementations\n"
            "  ext4/        - ext4 filesystem\n"
            "  xfs/         - XFS filesystem\n"
            "  btrfs/       - Btrfs copy-on-write filesystem\n"
            "  f2fs/        - Flash-Friendly File System\n"
            "  ntfs3/       - NTFS read/write driver\n"
            "  vfat/        - VFAT (FAT32) filesystem\n"
            "  nfs/         - Network File System client\n"
            "  cifs/        - CIFS/SMB network filesystem\n"
            "  proc/        - /proc virtual filesystem\n"
            "  sysfs/       - /sys virtual filesystem\n"
            "  devtmpfs/    - /dev temporary filesystem\n"
            "  overlay/     - OverlayFS (containers)\n"
            "  fuse/        - Filesystem in Userspace\n"
        )


class SrcMmCommand(Command):
    """Kernel memory management."""

    name = "src-mm"
    description = "/usr/src/mm - Kernel memory management"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/mm/ - Memory management\n"
            "  page_alloc.c - Page frame allocator\n"
            "  slub.c       - SLUB slab allocator\n"
            "  vmalloc.c    - Virtual memory allocator\n"
            "  mmap.c       - Memory-mapped file support\n"
            "  swap.c       - Swap space management\n"
            "  oom_kill.c   - Out-of-memory killer\n"
            "  compaction.c - Memory compaction\n"
            "  hugepage.c   - Huge page support\n"
            "  ksm.c        - Kernel Same-page Merging\n"
            "  zswap.c      - Compressed swap cache\n"
        )


class SrcIpcCommand(Command):
    """Kernel IPC mechanisms."""

    name = "src-ipc"
    description = "/usr/src/ipc - Inter-Process Communication"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/ipc/ - IPC subsystem\n"
            "  msg.c        - System V message queues\n"
            "  sem.c        - System V semaphores\n"
            "  shm.c        - System V shared memory\n"
            "  util.c       - IPC utility functions\n"
            "  compat.c     - 32-bit compat layer on 64-bit\n"
        )


class SrcSecurityCommand(Command):
    """Kernel security subsystem."""

    name = "src-security"
    description = "/usr/src/security - Kernel security framework"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/security/ - Security module framework\n"
            "  commoncap.c  - Common capabilities logic\n"
            "  apparmor/    - AppArmor LSM\n"
            "  selinux/     - SELinux LSM\n"
            "  smack/       - Simplified Mandatory Access Control\n"
            "  tomoyo/      - TOMOYO LSM\n"
            "  yama/        - Yama ptrace restrictions\n"
            "  integrity/   - Kernel integrity measurement\n"
            "  keys/        - Kernel key management\n"
        )


class SrcCryptoCommand(Command):
    """Kernel crypto subsystem."""

    name = "src-crypto"
    description = "/usr/src/crypto - Kernel crypto API"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/crypto/ - Cryptographic API\n"
            "  aes.c        - AES symmetric cipher\n"
            "  sha256.c     - SHA-256 hash\n"
            "  rsa.c        - RSA public key cipher\n"
            "  ecdh.c       - Elliptic Curve Diffie-Hellman\n"
            "  hmac.c       - Hash-based Message Authentication\n"
            "  aead.c       - Authenticated Encryption with Associated Data\n"
            "  algif_hash.c - AF_ALG hash interface\n"
            "  testmgr.c    - Crypto algorithm self-tests\n"
        )


class SrcBlockCommand(Command):
    """Kernel block layer."""

    name = "src-block"
    description = "/usr/src/block - Kernel block I/O layer"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/block/ - Block I/O layer\n"
            "  blk-core.c   - Block layer core (I/O submission)\n"
            "  blk-mq.c     - Multi-queue block layer\n"
            "  blk-sched.c  - I/O schedulers (mq-deadline, BFQ, kyber)\n"
            "  blk-cgroup.c - Block I/O cgroup controller\n"
            "  iosched/     - I/O scheduler implementations\n"
        )


class SrcInitCommand(Command):
    """Kernel initialization."""

    name = "src-init"
    description = "/usr/src/init - Kernel initialization code"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/init/ - Kernel boot and initialization\n"
            "  main.c       - start_kernel() - primary init entry\n"
            "  do_mounts.c  - Root filesystem mounting\n"
            "  calibrate.c  - CPU clock calibration\n"
            "  cmdline.c    - Kernel command line parsing\n"
        )


class SrcSoundCommand(Command):
    """Kernel sound subsystem (ALSA)."""

    name = "src-sound"
    description = "/usr/src/sound - ALSA sound subsystem"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/sound/ - ALSA sound subsystem\n"
            "  core/        - ALSA core (PCM, control, timer)\n"
            "  drivers/     - Sound card drivers (HDA, USB audio)\n"
            "  usb/         - USB audio class drivers\n"
            "  pci/         - PCI sound drivers (HDA Intel)\n"
            "  soc/         - ASoC (SoC audio framework)\n"
            "  firewire/    - FireWire audio drivers\n"
            "  sequencer/   - ALSA sequencer (MIDI routing)\n"
        )


class SrcLibCommand(Command):
    """Kernel library routines."""

    name = "src-lib"
    description = "/usr/src/lib - Kernel library functions"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/lib/ - Kernel-space library routines\n"
            "  string.c     - String manipulation functions\n"
            "  vsprintf.c   - printf-family implementation\n"
            "  rbtree.c     - Red-black tree\n"
            "  list_sort.c  - Merge sort on linked lists\n"
            "  sort.c       - Heapsort implementation\n"
            "  bsearch.c    - Binary search\n"
            "  zlib/        - Compressed filesystem support\n"
            "  lz4/         - LZ4 compression\n"
            "  zstd/        - Zstandard compression\n"
            "  sha256.c     - SHA-256 for dm-verity\n"
        )


class SrcScriptsCommand(Command):
    """Kernel build scripts."""

    name = "src-scripts"
    description = "/usr/src/scripts - Kernel build system scripts"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/scripts/ - Build system scripts\n"
            "  Makefile.build  - Recursive make infrastructure\n"
            "  Kconfig         - Configuration menu system\n"
            "  modpost         - Module symbol post-processing\n"
            "  checkstack.pl   - Stack size checker\n"
            "  get_maintainer.pl - MAINTAINERS file parser\n"
            "  sparse          - Static analysis integration\n"
            "  clang-tools/    - Clang static analyzer configs\n"
        )


class SrcArchCommand(Command):
    """Kernel architecture-specific code."""

    name = "src-arch"
    description = "/usr/src/arch - Architecture-specific kernel code"
    category = "usr"
    privileges = ["user"]

    def execute(self, *args):
        return (
            "/usr/src/arch/ - Architecture-specific code\n"
            "  x86/         - x86/x86_64 (most common)\n"
            "  arm64/       - AArch64 (ARM 64-bit)\n"
            "  arm/         - ARM 32-bit\n"
            "  riscv/       - RISC-V\n"
            "  s390/        - IBM System/390\n"
            "  ppc/         - PowerPC\n"
            "  mips/        - MIPS\n"
            "  Each arch/ contains: entry, mm, kernel, include, boot\n"
        )
