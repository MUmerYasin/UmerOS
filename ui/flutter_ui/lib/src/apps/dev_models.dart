import 'package:flutter/material.dart';

enum DevType { char, block, fifo, socket, symlink, directory }

class DeviceNodeModel {
  final String name;
  final String path;
  final DevType devType;
  final int major;
  final int minor;
  final int mode;
  final String? symlinkTarget;
  final String description;

  const DeviceNodeModel({
    required this.name,
    required this.path,
    required this.devType,
    this.major = 0,
    this.minor = 0,
    this.mode = 438,
    this.symlinkTarget,
    required this.description,
  });

  bool get hasDevNums => devType == DevType.char || devType == DevType.block;

  String get modeStr => mode.toRadixString(8).padLeft(3, '0');

  String get permsStr {
    String triple(int d) {
      return '${d & 4 != 0 ? 'r' : '-'}${d & 2 != 0 ? 'w' : '-'}${d & 1 != 0 ? 'x' : '-'}';
    }

    if (devType == DevType.directory) return 'drwxr-xr-x';
    if (devType == DevType.symlink) return 'lrwxrwxrwx';
    final s = modeStr.padLeft(3, '0');
    final t = switch (devType) {
      DevType.char => 'c',
      DevType.block => 'b',
      DevType.fifo => 'p',
      _ => 's',
    };
    return '$t${triple(int.parse(s[0]))}${triple(int.parse(s[1]))}${triple(int.parse(s[2]))}';
  }
}

class UdevResult {
  final String command;
  final List<String> args;
  final int exitCode;
  final String stdout;
  final String stderr;

  const UdevResult({
    required this.command,
    required this.args,
    required this.exitCode,
    this.stdout = '',
    this.stderr = '',
  });

  bool get success => exitCode == 0;
}

class FhsDevDir {
  final String path;
  final String purpose;
  final bool present;

  const FhsDevDir({required this.path, required this.purpose, required this.present});
}

class ModernTech {
  final String name;
  final String nodePath;
  final String kernelSince;
  final String summary;
  final IconData icon;

  const ModernTech({
    required this.name,
    required this.nodePath,
    required this.kernelSince,
    required this.summary,
    required this.icon,
  });
}

class DevService {
  static const Map<DevType, Color> typeColors = {
    DevType.char: Colors.blue,
    DevType.block: Colors.deepOrange,
    DevType.fifo: Color(0xFFFFB300),
    DevType.socket: Colors.purple,
    DevType.symlink: Colors.cyan,
    DevType.directory: Colors.teal,
  };

  static const Map<DevType, IconData> typeIcons = {
    DevType.char: Icons.memory_outlined,
    DevType.block: Icons.storage_outlined,
    DevType.fifo: Icons.linear_scale,
    DevType.socket: Icons.hub_outlined,
    DevType.symlink: Icons.link,
    DevType.directory: Icons.folder_outlined,
  };

  static const Map<DevType, String> typeLabels = {
    DevType.char: 'char',
    DevType.block: 'block',
    DevType.fifo: 'fifo',
    DevType.socket: 'socket',
    DevType.symlink: 'symlink',
    DevType.directory: 'dir',
  };

  static List<DeviceNodeModel> get nodes {
    final list = <DeviceNodeModel>[
      const DeviceNodeModel(name: 'null', path: '/dev/null', devType: DevType.char, major: 1, minor: 3, description: 'Null device — discards all data'),
      const DeviceNodeModel(name: 'zero', path: '/dev/zero', devType: DevType.char, major: 1, minor: 5, description: 'Zero device — infinite zero reads'),
      const DeviceNodeModel(name: 'full', path: '/dev/full', devType: DevType.char, major: 1, minor: 7, description: 'Full device — writes fail ENOSPC'),
      const DeviceNodeModel(name: 'random', path: '/dev/random', devType: DevType.char, major: 1, minor: 8, mode: 420, description: 'Entropy pool (blocking)'),
      const DeviceNodeModel(name: 'urandom', path: '/dev/urandom', devType: DevType.char, major: 1, minor: 9, mode: 420, description: 'Pseudo-random (non-blocking)'),
      const DeviceNodeModel(name: 'tty', path: '/dev/tty', devType: DevType.char, major: 5, minor: 0, description: 'Controlling terminal'),
      const DeviceNodeModel(name: 'console', path: '/dev/console', devType: DevType.char, major: 5, minor: 1, mode: 400, description: 'System console'),
      const DeviceNodeModel(name: 'ptmx', path: '/dev/ptmx', devType: DevType.char, major: 5, minor: 2, description: 'PTY master clone device'),
      const DeviceNodeModel(name: 'log', path: '/dev/log', devType: DevType.socket, major: 10, minor: 229, description: 'Syslog unix socket'),
      const DeviceNodeModel(name: 'kvm', path: '/dev/kvm', devType: DevType.char, major: 10, minor: 232, mode: 432, description: 'Kernel virtual machine interface'),
      const DeviceNodeModel(name: 'fuse', path: '/dev/fuse', devType: DevType.char, major: 10, minor: 229, description: 'FUSE filesystem control'),
      const DeviceNodeModel(name: 'watchdog', path: '/dev/watchdog', devType: DevType.char, major: 10, minor: 130, mode: 384, description: 'Hardware watchdog timer'),
      const DeviceNodeModel(name: 'uinput', path: '/dev/uinput', devType: DevType.char, major: 10, minor: 223, mode: 384, description: 'Virtual input injection'),
      const DeviceNodeModel(name: 'btrfs-control', path: '/dev/btrfs-control', devType: DevType.char, major: 10, minor: 234, description: 'Btrfs control device'),
      const DeviceNodeModel(name: 'vga_arbiter', path: '/dev/vga_arbiter', devType: DevType.char, major: 10, minor: 63, description: 'VGA arbitration'),
      const DeviceNodeModel(name: 'loop-control', path: '/dev/loop-control', devType: DevType.char, major: 10, minor: 237, description: 'Loop device control'),
      const DeviceNodeModel(name: 'hpet', path: '/dev/hpet', devType: DevType.char, major: 10, minor: 228, description: 'High Precision Event Timer'),
      const DeviceNodeModel(name: 'tpm0', path: '/dev/tpm0', devType: DevType.char, major: 10, minor: 224, mode: 384, description: 'TPM 2.0 device'),
      for (var i = 0; i <= 7; i++)
        DeviceNodeModel(
          name: 'tty$i', path: '/dev/tty$i', devType: DevType.char,
          major: 4, minor: i, mode: 400, description: 'Virtual terminal $i',
        ),
      for (var i = 0; i <= 3; i++)
        DeviceNodeModel(
          name: 'ttyS$i', path: '/dev/ttyS$i', devType: DevType.char,
          major: 4, minor: 64 + i, mode: 400, description: 'Serial port $i',
        ),
      for (var i = 0; i <= 7; i++)
        DeviceNodeModel(
          name: 'loop$i', path: '/dev/loop$i', devType: DevType.block,
          major: 7, minor: i, mode: 432, description: 'Loop device $i',
        ),
      for (var i = 0; i < 4; i++)
        DeviceNodeModel(
          name: 'sd${String.fromCharCode(97 + i)}',
          path: '/dev/sd${String.fromCharCode(97 + i)}',
          devType: DevType.block, major: 8, minor: i * 16, mode: 432,
          description: 'SCSI/SATA disk ${String.fromCharCode(97 + i)}',
        ),
      const DeviceNodeModel(name: 'sr0', path: '/dev/sr0', devType: DevType.block, major: 11, minor: 0, mode: 432, description: 'CD-ROM drive'),
      const DeviceNodeModel(name: 'nvme0n1', path: '/dev/nvme0n1', devType: DevType.block, major: 259, minor: 0, mode: 432, description: 'NVMe namespace 1'),
      const DeviceNodeModel(name: 'tun', path: '/dev/net/tun', devType: DevType.char, major: 10, minor: 200, description: 'TUN/TAP network device'),
      for (var i = 0; i <= 3; i++) ...[
        DeviceNodeModel(
          name: 'card$i', path: '/dev/dri/card$i', devType: DevType.char,
          major: 226, minor: i, mode: 432, description: 'DRI card $i',
        ),
        DeviceNodeModel(
          name: 'renderD${128 + i}', path: '/dev/dri/renderD${128 + i}',
          devType: DevType.char, major: 226, minor: 128 + i, mode: 432,
          description: 'DRM render node ${128 + i}',
        ),
      ],
      for (var i = 0; i <= 3; i++)
        DeviceNodeModel(
          name: 'card$i', path: '/dev/snd/card$i', devType: DevType.char,
          major: 116, minor: i, mode: 432, description: 'ALSA card $i',
        ),
      const DeviceNodeModel(name: 'controlC0', path: '/dev/snd/controlC0', devType: DevType.char, major: 116, minor: 0, mode: 432, description: 'ALSA control device'),
      const DeviceNodeModel(name: 'pcmC0D0p', path: '/dev/snd/pcmC0D0p', devType: DevType.char, major: 116, minor: 4, mode: 432, description: 'ALSA playback PCM'),
      for (var i = 0; i <= 3; i++)
        DeviceNodeModel(
          name: 'event$i', path: '/dev/input/event$i', devType: DevType.char,
          major: 13, minor: 64 + i, mode: 432, description: 'Input event device $i',
        ),
      const DeviceNodeModel(name: 'js0', path: '/dev/input/js0', devType: DevType.char, major: 13, minor: 0, mode: 432, description: 'Joystick device 0'),
      const DeviceNodeModel(name: 'mice', path: '/dev/input/mice', devType: DevType.char, major: 13, minor: 200, mode: 432, description: 'Mouse multiplexer'),
      const DeviceNodeModel(name: 'mouse0', path: '/dev/input/mouse0', devType: DevType.char, major: 13, minor: 32, mode: 432, description: 'Mouse device 0'),
      const DeviceNodeModel(name: 'hidraw0', path: '/dev/hidraw0', devType: DevType.char, major: 246, minor: 0, mode: 384, description: 'HID raw access'),
      const DeviceNodeModel(name: 'fb0', path: '/dev/fb0', devType: DevType.char, major: 29, minor: 0, mode: 384, description: 'Framebuffer display'),
      const DeviceNodeModel(name: 'i2c-0', path: '/dev/i2c-0', devType: DevType.char, major: 89, minor: 0, description: 'I2C bus 0'),
      const DeviceNodeModel(name: 'mapper', path: '/dev/mapper/control', devType: DevType.char, major: 10, minor: 236, mode: 384, description: 'Device-mapper control'),
      const DeviceNodeModel(name: 'stdin', path: '/dev/stdin', devType: DevType.symlink, symlinkTarget: '/proc/self/fd/0', description: 'Standard input'),
      const DeviceNodeModel(name: 'stdout', path: '/dev/stdout', devType: DevType.symlink, symlinkTarget: '/proc/self/fd/1', description: 'Standard output'),
      const DeviceNodeModel(name: 'stderr', path: '/dev/stderr', devType: DevType.symlink, symlinkTarget: '/proc/self/fd/2', description: 'Standard error'),
      const DeviceNodeModel(name: 'core', path: '/dev/core', devType: DevType.symlink, symlinkTarget: '/proc/kcore', description: 'Kernel memory image'),
      const DeviceNodeModel(name: 'initctl', path: '/dev/initctl', devType: DevType.fifo, description: 'Init control FIFO'),
      const DeviceNodeModel(name: 'input', path: '/dev/input', devType: DevType.directory, description: 'Input devices'),
      const DeviceNodeModel(name: 'pts', path: '/dev/pts', devType: DevType.directory, description: 'Pseudo-terminal slaves'),
      const DeviceNodeModel(name: 'shm', path: '/dev/shm', devType: DevType.directory, description: 'POSIX shared memory'),
      const DeviceNodeModel(name: 'block', path: '/dev/block', devType: DevType.directory, description: 'Block symlinks by major:minor'),
      const DeviceNodeModel(name: 'char', path: '/dev/char', devType: DevType.directory, description: 'Character symlinks by major:minor'),
      const DeviceNodeModel(name: 'disk', path: '/dev/disk', devType: DevType.directory, description: 'Disk symlinks'),
      const DeviceNodeModel(name: 'by-id', path: '/dev/disk/by-id', devType: DevType.directory, description: 'Disk by ID'),
      const DeviceNodeModel(name: 'by-label', path: '/dev/disk/by-label', devType: DevType.directory, description: 'Disk by label'),
      const DeviceNodeModel(name: 'by-uuid', path: '/dev/disk/by-uuid', devType: DevType.directory, description: 'Disk by UUID'),
      const DeviceNodeModel(name: 'by-path', path: '/dev/disk/by-path', devType: DevType.directory, description: 'Disk by path'),
      const DeviceNodeModel(name: 'net', path: '/dev/net', devType: DevType.directory, description: 'Network devices'),
      const DeviceNodeModel(name: 'usb', path: '/dev/bus/usb', devType: DevType.directory, description: 'USB bus devices'),
      const DeviceNodeModel(name: 'dri', path: '/dev/dri', devType: DevType.directory, description: 'Direct Rendering Interface'),
      const DeviceNodeModel(name: 'snd', path: '/dev/snd', devType: DevType.directory, description: 'ALSA sound devices'),
      const DeviceNodeModel(name: 'mapper', path: '/dev/mapper', devType: DevType.directory, description: 'Device-mapper (LVM, dm-crypt)'),
      const DeviceNodeModel(name: 'hugepages', path: '/dev/hugepages', devType: DevType.directory, description: 'Huge pages mount'),
      const DeviceNodeModel(name: 'mqueue', path: '/dev/mqueue', devType: DevType.directory, description: 'POSIX message queues'),
      const DeviceNodeModel(name: 'vfio', path: '/dev/vfio', devType: DevType.directory, description: 'VFIO IOMMU groups'),
      const DeviceNodeModel(name: 'vfio', path: '/dev/vfio/vfio', devType: DevType.char, major: 10, minor: 196, mode: 432, description: 'IOMMU container for userspace passthrough'),
      const DeviceNodeModel(name: '42', path: '/dev/vfio/42', devType: DevType.char, major: 10, minor: 42, mode: 432, description: 'IOMMU group 42 (vfio-pci bound)'),
      const DeviceNodeModel(name: 'dma_heap', path: '/dev/dma_heap', devType: DevType.directory, description: 'DMA-BUF allocation heaps'),
      const DeviceNodeModel(name: 'system', path: '/dev/dma_heap/system', devType: DevType.char, major: 254, minor: 511, mode: 384, description: 'DMA-BUF system RAM heap'),
      const DeviceNodeModel(name: 'cma', path: '/dev/dma_heap/cma', devType: DevType.char, major: 254, minor: 512, mode: 384, description: 'DMA-BUF contiguous heap'),
      const DeviceNodeModel(name: 'secure', path: '/dev/dma_heap/secure', devType: DevType.char, major: 254, minor: 513, mode: 384, description: 'Protected content heap'),
      const DeviceNodeModel(name: 'gpiochip0', path: '/dev/gpiochip0', devType: DevType.char, major: 254, minor: 0, mode: 432, description: 'GPIO controller chip 0 (32 lines)'),
      const DeviceNodeModel(name: 'gpiochip1', path: '/dev/gpiochip1', devType: DevType.char, major: 254, minor: 1, mode: 432, description: 'GPIO controller chip 1 (32 lines)'),
      const DeviceNodeModel(name: 'zram-control', path: '/dev/zram-control', devType: DevType.char, major: 230, minor: 254, mode: 384, description: 'zram hot-add/remove control'),
      const DeviceNodeModel(name: 'zram0', path: '/dev/zram0', devType: DevType.block, major: 230, minor: 0, mode: 432, description: 'Compressed RAM disk (lz4 swap)'),
      const DeviceNodeModel(name: 'zram1', path: '/dev/zram1', devType: DevType.block, major: 230, minor: 1, mode: 432, description: 'Compressed RAM disk 1'),
      const DeviceNodeModel(name: 'userfaultfd', path: '/dev/userfaultfd', devType: DevType.char, major: 10, minor: 126, mode: 384, description: 'userfaultfd entry point (k6.1+)'),
      const DeviceNodeModel(name: 'hidg0', path: '/dev/hidg0', devType: DevType.char, major: 248, minor: 0, mode: 432, description: 'HID gadget endpoint (device-side USB)'),
      const DeviceNodeModel(name: 'functionfs', path: '/dev/functionfs', devType: DevType.char, major: 10, minor: 239, mode: 384, description: 'Userspace USB function transport'),
      const DeviceNodeModel(name: 'nvme0c', path: '/dev/nvme0c', devType: DevType.char, major: 245, minor: 0, mode: 384, description: 'NVMe controller char node'),
      const DeviceNodeModel(name: 'ng0n1', path: '/dev/ng0n1', devType: DevType.char, major: 245, minor: 1, mode: 384, description: 'NVMe generic namespace node'),
      const DeviceNodeModel(name: 'ng0n2', path: '/dev/ng0n2', devType: DevType.char, major: 245, minor: 2, mode: 384, description: 'NVMe generic namespace node'),
      const DeviceNodeModel(name: 'ptp0', path: '/dev/ptp0', devType: DevType.char, major: 247, minor: 0, mode: 384, description: 'PTP hardware clock'),
      const DeviceNodeModel(name: 'rfkill', path: '/dev/rfkill', devType: DevType.char, major: 10, minor: 59, mode: 432, description: 'Radio kill switch multiplexer'),
      const DeviceNodeModel(name: 'mctl', path: '/dev/mctl', devType: DevType.char, major: 10, minor: 240, mode: 384, description: 'Mediated device control (vGPU style)'),
      const DeviceNodeModel(name: 'kmsg', path: '/dev/kmsg', devType: DevType.char, major: 1, minor: 11, mode: 416, description: 'printk structured ring buffer'),
      const DeviceNodeModel(name: 'rtc0', path: '/dev/rtc0', devType: DevType.char, major: 254, minor: 0, mode: 384, description: 'Real-time clock with wakealarm'),
      const DeviceNodeModel(name: 'usbmon0', path: '/dev/usbmon0', devType: DevType.char, major: 10, minor: 54, mode: 384, description: 'USB monitor - all buses'),
      const DeviceNodeModel(name: 'iio:device0', path: '/dev/iio:device0', devType: DevType.char, major: 242, minor: 0, mode: 432, description: 'Industrial I/O sensor buffer'),
    ];
    return list..sort((a, b) => a.path.compareTo(b.path));
  }

  static Map<String, List<DeviceNodeModel>> groupedNodes() {
    final map = <String, List<DeviceNodeModel>>{};
    for (final n in nodes) {
      var group = '/dev';
      if (n.path.startsWith('/dev/') && n.path.split('/').length > 3) {
        group = n.path.split('/').take(3).join('/');
      }
      map.putIfAbsent(group, () => []).add(n);
    }
    final keys = map.keys.toList()..sort();
    return {for (final k in keys) k: map[k]!};
  }

  static Map<String, int> statistics() {
    final byType = <String, int>{};
    for (final t in DevType.values) {
      byType[t.name] = nodes.where((n) => n.devType == t).length;
    }
    return {'total': nodes.length, 'groups': groupedNodes().length, ...byType};
  }

  static List<FhsDevDir> fhsMap() {
    return const [
      FhsDevDir(path: '/dev', purpose: 'Device files (char/block/FIFO/socket/symlink)', present: true),
      FhsDevDir(path: '/dev/input', purpose: 'Input devices (event, js, mouse)', present: true),
      FhsDevDir(path: '/dev/pts', purpose: 'Pseudo-terminal devices', present: true),
      FhsDevDir(path: '/dev/shm', purpose: 'POSIX shared memory', present: true),
      FhsDevDir(path: '/dev/block', purpose: 'Block device symlinks (major:minor)', present: true),
      FhsDevDir(path: '/dev/char', purpose: 'Character device symlinks (major:minor)', present: true),
      FhsDevDir(path: '/dev/disk', purpose: 'Disk links (by-id, by-label, by-uuid, by-path)', present: true),
      FhsDevDir(path: '/dev/net', purpose: 'Network device nodes (tun, tap)', present: true),
      FhsDevDir(path: '/dev/bus/usb', purpose: 'USB device nodes', present: true),
      FhsDevDir(path: '/dev/dri', purpose: 'Direct Rendering Interface (GPU)', present: true),
      FhsDevDir(path: '/dev/snd', purpose: 'ALSA sound devices', present: true),
      FhsDevDir(path: '/dev/mapper', purpose: 'Device-mapper (LVM, dm-crypt)', present: true),
      FhsDevDir(path: '/dev/log', purpose: 'Syslog socket', present: true),
      FhsDevDir(path: '/dev/hugepages', purpose: 'Huge pages', present: true),
      FhsDevDir(path: '/dev/mqueue', purpose: 'POSIX message queues', present: true),
    ];
  }

  static DeviceNodeModel? find(String query) {
    final q = query.startsWith('/dev/') ? query : '/dev/$query';
    for (final n in nodes) {
      if (n.path == q || n.name == query) return n;
    }
    return null;
  }

  static const List<ModernTech> modernFeatures = [
    ModernTech(
      name: 'VFIO Passthrough',
      nodePath: '/dev/vfio/vfio',
      kernelSince: 'iommufd k5.15',
      summary: 'IOMMU-agnostic userspace drivers: VMs get safe direct GPU/NIC/NVMe access via group + container fds.',
      icon: Icons.security,
    ),
    ModernTech(
      name: 'DMA-BUF Heaps',
      nodePath: '/dev/dma_heap/system',
      kernelSince: 'k5.6 · 6.19 vfio-pci',
      summary: 'Explicit zero-copy buffer sharing heaps; Linux 6.19 even exports VFIO PCI MMIO BARs as dma-bufs.',
      icon: Icons.layers,
    ),
    ModernTech(
      name: 'GPIO chardev ABI',
      nodePath: '/dev/gpiochip0',
      kernelSince: 'k4.8',
      summary: 'Line-based GPIO with events and multi-consumer safety — replaces the deprecated sysfs GPIO.',
      icon: Icons.settings_input_component,
    ),
    ModernTech(
      name: 'ZRAM compressed swap',
      nodePath: '/dev/zram0',
      kernelSince: 'k3.14 gen',
      summary: 'Compressed RAM block swap (lz4/zstd): faster than disk, no SSD wear; zram-generator configures at boot.',
      icon: Icons.compress,
    ),
    ModernTech(
      name: 'userfaultfd node',
      nodePath: '/dev/userfaultfd',
      kernelSince: 'k6.1',
      summary: 'Device-node entry so sandboxes can grant page-fault handling without exposing the syscall.',
      icon: Icons.touch_app,
    ),
    ModernTech(
      name: 'USB gadget / functionfs',
      nodePath: '/dev/functionfs',
      kernelSince: 'k3.x+',
      summary: 'Present UmerOS as a USB peripheral: HID keyboards (/dev/hidgN) and custom userspace functions.',
      icon: Icons.usb,
    ),
    ModernTech(
      name: 'NVMe generic char nodes',
      nodePath: '/dev/ng0n1',
      kernelSince: 'k4.10',
      summary: 'Per-namespace admin passthrough alongside block nodes — powers modern nvme-cli commands.',
      icon: Icons.bolt,
    ),
    ModernTech(
      name: 'PTP hardware clock',
      nodePath: '/dev/ptp0',
      kernelSince: 'k3.0',
      summary: 'Nanosecond-grade NIC hardware timestamps for linuxptp/chrony and TSN scheduling.',
      icon: Icons.schedule,
    ),
    ModernTech(
      name: 'RFKill multiplexer',
      nodePath: '/dev/rfkill',
      kernelSince: 'k2.6.33',
      summary: 'Single event stream for all radio kill switches (wlan/bt/wwan) consumed by desktop shells.',
      icon: Icons.signal_wifi_off,
    ),
    ModernTech(
      name: 'Netlink uevent monitor',
      nodePath: 'udev_modern.UeventNetlinkMonitor',
      kernelSince: 'systemd-udevd',
      summary: 'Ordered uevent queue with coalescing (debounce), settle() drain and listener groups.',
      icon: Icons.notifications_active,
    ),
    ModernTech(
      name: 'Tags & uaccess seats',
      nodePath: 'TAGS=="uaccess"',
      kernelSince: 'logind era',
      summary: 'Per-device properties and tags; logind grants the active seat user ACLs on tagged nodes.',
      icon: Icons.badge,
    ),
    ModernTech(
      name: 'Predictable naming',
      nodePath: '/dev/disk/by-*',
      kernelSince: 'v197 rules',
      summary: 'Persistent by-id/by-path/by-uuid disk aliases plus topology-based enpXsY network names.',
      icon: Icons.abc,
    ),
    ModernTech(
      name: 'systemd .device units',
      nodePath: 'dev-null.device',
      kernelSince: 'systemd',
      summary: 'Every node synthesises a plugged .device unit for dependency ordering in modern init.',
      icon: Icons.account_tree,
    ),
    ModernTech(
      name: 'Container mknod policy',
      nodePath: 'BPF device filter',
      kernelSince: 'cgroup v2',
      summary: 'Allowlist evaluated at create time: stdio/tty/null-family allowed, everything else denied.',
      icon: Icons.policy,
    ),
    ModernTech(
      name: 'ioctl _IOC encoding',
      nodePath: 'asm-generic/ioctl.h',
      kernelSince: 'ABI classic',
      summary: 'dir(2b)<<30 | size(14b)<<16 | type(8b)<<8 | nr(8b) — decode any raw command with _IOR/_IOW/_IOWR semantics.',
      icon: Icons.calculate,
    ),
    ModernTech(
      name: '/dev/kmsg structured log',
      nodePath: '/dev/kmsg',
      kernelSince: 'k3.5',
      summary: '"prio,seq,usec,flags;msg" records with KEY=value continuations; per-reader cursors, EAGAIN/EPIPE rules.',
      icon: Icons.article,
    ),
    ModernTech(
      name: 'usbmon URB tracing',
      nodePath: '/dev/usbmon0',
      kernelSince: 'k2.6+',
      summary: '64-byte binary event headers (S/C/E × Bi/Bo/Ci/Ii/Zi), MON_IOC magic 0x92, mon_bin_stats.',
      icon: Icons.wifi_tethering,
    ),
    ModernTech(
      name: 'IIO triggered buffers',
      nodePath: '/dev/iio:device0',
      kernelSince: 'k3.x',
      summary: 'Multi-channel continuous capture with scan_elements ("le:s16/32>>0") and int64 sample timestamps.',
      icon: Icons.sensors,
    ),
    ModernTech(
      name: 'LOOP_CONFIGURE + resize',
      nodePath: 'loop ioctl 0x4C22',
      kernelSince: 'k5.0',
      summary: 'Single-shot loop setup replacing 3 old ioctls, plus LOOP_SET_CAPACITY online grow.',
      icon: Icons.settings_backup_restore,
    ),
    ModernTech(
      name: 'TUN multiqueue',
      nodePath: 'TUNSETQUEUE',
      kernelSince: 'k3.8',
      summary: 'Per-queue enable/disable for multiqueue virtio-net backends; persistent taps via TUNSETPERSIST.',
      icon: Icons.lan,
    ),
  ];

  static UdevResult udevadm(List<String> args) {
    if (args.isEmpty) {
      return const UdevResult(command: 'udevadm', args: [], exitCode: 0, stdout: 'usage: udevadm info|monitor|trigger|settle|test [args]\n');
    }
    switch (args.first) {
      case '--help' || '-h':
        return const UdevResult(
          command: 'udevadm', args: [], exitCode: 0,
          stdout: 'udevadm — device manager query and control\n\n'
              '  info [options] /dev/NAME   show device properties\n'
              '  monitor                    kernel uevents live feed\n'
              '  trigger                    replay uevents\n'
              '  settle                     wait for udev queue to drain\n'
              '  test /dev/NAME             simulate a uevent run\n',
        );
      case 'info':
        String? name;
        for (final a in args.skip(1)) {
          if (a.startsWith('--name=')) {
            name = a.split('=')[1];
          } else if (!a.startsWith('-') && !a.contains('=') && a != 'info') {
            name = a;
          }
        }
        if (name == null || name.isEmpty) {
          return const UdevResult(command: 'udevadm', args: [], exitCode: 1, stderr: 'udevadm info: specify device path\n');
        }
        final node = find(name);
        if (node == null) {
          return UdevResult(command: 'udevadm', args: args, exitCode: 1, stderr: "udevadm info: '$name' not found in /dev registry\n");
        }
        final buf = StringBuffer('P: ${node.path}\n')
          ..writeln('N: ${node.name}')
          ..writeln('E: SUBSYSTEM=${node.devType == DevType.directory ? 'kernel' : node.devType.name}')
          ..writeln('E: DEVNAME=${node.path}');
        if (node.hasDevNums) {
          buf
            ..writeln('E: MAJOR=${node.major}')
            ..writeln('E: MINOR=${node.minor}');
        }
        if (node.symlinkTarget != null) buf.writeln('E: DEVLINKS=${node.symlinkTarget}');
        buf
          ..writeln('M: ${node.modeStr} (${node.permsStr})')
          ..writeln('A: DESCRIPTION=${node.description}');
        return UdevResult(command: 'udevadm', args: args, exitCode: 0, stdout: buf.toString());
      case 'monitor':
        return UdevResult(
          command: 'udevadm', args: args, exitCode: 0,
          stdout: 'monitor will print the received events for:\n'
              'UDEV   - event sent out after rule processing\n'
              'KERNEL - the kernel uevent\n\n'
              'KERNEL[0000.42] add  /devices/virtual/mem/null (mem)\n'
              'UDEV  [0000.44] add  /dev/null (null)\n'
              'KERNEL[0000.51] add  /devices/virtual/block/loop0 (block)\n'
              'UDEV  [0000.52] add  /dev/loop0 (block)\n'
              'UDEV  [0000.60] add  /dev/input/event0 (input)\n',
        );
      case 'trigger':
        return UdevResult(command: 'udevadm', args: args, exitCode: 0, stdout: 'Triggering uevents for all devices... done (108 queued)\n');
      case 'settle':
        return UdevResult(command: 'udevadm', args: args, exitCode: 0, stdout: 'udevadm settle - waiting for udev... done.\n');
      case 'test':
        final name = args.length > 1 ? args.last : '';
        final node = find(name);
        if (name.isEmpty || node == null) {
          return UdevResult(command: 'udevadm', args: args, exitCode: 1, stderr: "udevadm test: device '$name' not found\n");
        }
        return UdevResult(
          command: 'udevadm', args: args, exitCode: 0,
          stdout: 'Load module index\n'
              'Read rules: /etc/udev/rules.d\n'
              'Created link: /dev/char/${node.major}:${node.minor} -> ${node.path}\n'
              'ACTION=add DEVPATH=${node.path} SUBSYSTEM=${node.devType.name}\n'
              'Test run of udev rules complete: exit 0\n',
        );
      default:
        return UdevResult(command: 'udevadm', args: args, exitCode: 1, stderr: "udevadm: unknown command '${args.first}'\n");
    }
  }

  static UdevResult mknod(List<String> args) {
    if (args.isEmpty || args.contains('--help')) {
      return const UdevResult(
        command: 'mknod', args: [], exitCode: 0,
        stdout: 'mknod NAME TYPE [MAJOR MINOR]\n'
            '  c  char device     b  block device\n'
            '  p  FIFO\n'
            'example: mknod mydev c 10 250\n',
      );
    }
    if (args.length < 4) {
      return const UdevResult(command: 'mknod', args: [], exitCode: 1, stderr: 'mknod: missing operand (need NAME TYPE MAJOR MINOR)\n');
    }
    final name = args[0];
    final typeChar = args[1];
    final major = int.tryParse(args[2]);
    final minor = int.tryParse(args[3]);
    if (!{'c', 'u', 'b', 'p'}.contains(typeChar)) {
      return UdevResult(command: 'mknod', args: args, exitCode: 1, stderr: "mknod: invalid type '$typeChar'\n");
    }
    if (typeChar != 'p' && (major == null || minor == null)) {
      return const UdevResult(command: 'mknod', args: [], exitCode: 1, stderr: 'mknod: invalid major/minor numbers\n');
    }
    if (find(name) != null) {
      return UdevResult(command: 'mknod', args: args, exitCode: 1, stderr: "mknod: '$name' already exists\n");
    }
    final t = typeChar == 'b' ? 'block' : typeChar == 'p' ? 'fifo' : 'char';
    return UdevResult(
      command: 'mknod', args: args, exitCode: 0,
      stdout: 'created /dev/$name ($t${major != null && minor != null ? ' $major:$minor' : ''})\n',
    );
  }
}

class IoctlInfo {
  final int raw;
  final String hex;
  final String direction;
  final int size;
  final String typeChar;
  final int nr;
  final String macro;
  final String magicNote;

  const IoctlInfo({
    required this.raw,
    required this.hex,
    required this.direction,
    required this.size,
    required this.typeChar,
    required this.nr,
    required this.macro,
    required this.magicNote,
  });
}

IoctlInfo? decodeIoctl(int cmd) {
  if (cmd < 0 || cmd > 0xFFFFFFFF) return null;
  const sizeMask = (1 << 14) - 1;
  final dir = (cmd >> 30) & 0x3;
  final size = (cmd >> 16) & sizeMask;
  final type = (cmd >> 8) & 0xFF;
  final nr = cmd & 0xFF;
  const dirNames = {0: '_IO', 1: '_IOW', 2: '_IOR', 3: '_IOWR'};
  const magicNotes = {
    0x54: "'T' tty", 0x73: "'s' serial", 0x92: 'MON_IOC usbmon',
    0xB7: "'W' watchdog", 0x03: 'HDIO', 0x12: 'SCSI_IOCTL',
    0x94: 'btrfs', 0xAE: 'VFIO', 0x3D: "'=' loop", 0x46: "'F' fbdev",
    0x56: "'V' video4linux", 0x4C: "'L' dm",
  };
  final tc = (type >= 32 && type < 127) ? String.fromCharCode(type) : '$type';
  return IoctlInfo(
    raw: cmd,
    hex: '0x${cmd.toRadixString(16).padLeft(8, '0')}',
    direction: dirNames[dir]!,
    size: size,
    typeChar: tc,
    nr: nr,
    macro: '${dirNames[dir]}($tc, $nr, $size)',
    magicNote: magicNotes[type] ?? 'unknown magic',
  );
}
