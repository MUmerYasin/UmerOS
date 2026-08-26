import 'package:flutter/material.dart';

class BinBinary {
  final String name;
  final String path;
  final String category;
  final String privilege;
  final String binaryType;
  final int sizeBytes;
  final String permissions;
  final int ownerUid;
  final int groupGid;
  final bool isSetuid;
  final bool isSetgid;
  final bool isSticky;
  final String? symlinkTarget;
  final String description;

  const BinBinary({
    required this.name,
    required this.path,
    required this.category,
    required this.privilege,
    required this.binaryType,
    required this.sizeBytes,
    required this.permissions,
    required this.ownerUid,
    required this.groupGid,
    this.isSetuid = false,
    this.isSetgid = false,
    this.isSticky = false,
    this.symlinkTarget,
    required this.description,
  });

  String get modeString {
    var s = permissions;
    if (isSetuid) s += 'u';
    if (isSetgid) s += 'g';
    if (isSticky) s += 't';
    return s;
  }

  String get humanSize {
    if (sizeBytes < 1024) return '$sizeBytes B';
    if (sizeBytes < 1024 * 1024) return '${(sizeBytes / 1024).toStringAsFixed(1)} KB';
    return '${(sizeBytes / (1024 * 1024)).toStringAsFixed(2)} MB';
  }
}

class CommandResult {
  final String command;
  final List<String> args;
  final int exitCode;
  final String stdout;
  final String stderr;
  final int durationMs;

  const CommandResult({
    required this.command,
    required this.args,
    required this.exitCode,
    required this.stdout,
    this.stderr = '',
    required this.durationMs,
  });

  bool get success => exitCode == 0;
}

class FhsEntry {
  final String directory;
  final String description;
  final bool compliant;
  final String note;

  const FhsEntry({
    required this.directory,
    required this.description,
    required this.compliant,
    required this.note,
  });
}

class BinService {
  static const List<String> categories = [
    'FILE_OPS',
    'TEXT',
    'PERMISSIONS',
    'SYSTEM_INFO',
    'PROCESS',
    'FILESYSTEM',
    'USER',
    'SHELL',
    'SYNC',
    'PATH',
  ];

  static const Map<String, Color> categoryColors = {
    'FILE_OPS': Colors.blue,
    'TEXT': Colors.green,
    'PERMISSIONS': Colors.orange,
    'SYSTEM_INFO': Colors.cyan,
    'PROCESS': Colors.purple,
    'FILESYSTEM': Colors.amber,
    'USER': Colors.teal,
    'SHELL': Colors.indigo,
    'SYNC': Colors.deepOrange,
    'PATH': Color(0xFF9CCC65),
  };

  static const Map<String, IconData> categoryIcons = {
    'FILE_OPS': Icons.folder_copy_outlined,
    'TEXT': Icons.text_snippet_outlined,
    'PERMISSIONS': Icons.lock_outline,
    'SYSTEM_INFO': Icons.info_outline,
    'PROCESS': Icons.memory_outlined,
    'FILESYSTEM': Icons.storage_outlined,
    'USER': Icons.person_outline,
    'SHELL': Icons.terminal_outlined,
    'SYNC': Icons.sync_outlined,
    'PATH': Icons.alt_route_outlined,
  };

  static const List<BinBinary> binaries = [
    BinBinary(
      name: 'ls', path: '/bin/ls', category: 'FILE_OPS', privilege: 'user',
      binaryType: 'ELF executable', sizeBytes: 142336, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'List directory contents with colors and long format.',
    ),
    BinBinary(
      name: 'cat', path: '/bin/cat', category: 'FILE_OPS', privilege: 'user',
      binaryType: 'ELF executable', sizeBytes: 51200, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'Concatenate files and print to stdout.',
    ),
    BinBinary(
      name: 'cp', path: '/bin/cp', category: 'FILE_OPS', privilege: 'user',
      binaryType: 'ELF executable', sizeBytes: 158720, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'Copy files and directories.',
    ),
    BinBinary(
      name: 'mv', path: '/bin/mv', category: 'FILE_OPS', privilege: 'user',
      binaryType: 'ELF executable', sizeBytes: 147456, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'Move or rename files and directories.',
    ),
    BinBinary(
      name: 'rm', path: '/bin/rm', category: 'FILE_OPS', privilege: 'user',
      binaryType: 'ELF executable', sizeBytes: 71680, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'Remove files or directories.',
    ),
    BinBinary(
      name: 'grep', path: '/usr/bin/grep', category: 'TEXT', privilege: 'user',
      binaryType: 'ELF executable', sizeBytes: 198656, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'Print lines matching a regular expression.',
    ),
    BinBinary(
      name: 'sed', path: '/usr/bin/sed', category: 'TEXT', privilege: 'user',
      binaryType: 'ELF executable', sizeBytes: 131072, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'Stream editor for filtering and transforming text.',
    ),
    BinBinary(
      name: 'awk', path: '/usr/bin/awk', category: 'TEXT', privilege: 'user',
      binaryType: 'symlink -> gawk', sizeBytes: 4096, permissions: 'lrwxrwxrwx',
      ownerUid: 0, groupGid: 0, symlinkTarget: '/usr/bin/gawk',
      description: 'Pattern scanning and processing language.',
    ),
    BinBinary(
      name: 'chmod', path: '/usr/bin/chmod', category: 'PERMISSIONS', privilege: 'user',
      binaryType: 'ELF executable', sizeBytes: 63488, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'Change file access permission bits.',
    ),
    BinBinary(
      name: 'chown', path: '/usr/bin/chown', category: 'PERMISSIONS', privilege: 'root',
      binaryType: 'ELF executable', sizeBytes: 67584, permissions: 'rwsr-xr-x',
      ownerUid: 0, groupGid: 0, isSetuid: true,
      description: 'Change file owner and group.',
    ),
    BinBinary(
      name: 'uname', path: '/usr/bin/uname', category: 'SYSTEM_INFO', privilege: 'user',
      binaryType: 'ELF executable', sizeBytes: 43008, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'Print kernel and system information.',
    ),
    BinBinary(
      name: 'lscpu', path: '/usr/bin/lscpu', category: 'SYSTEM_INFO', privilege: 'user',
      binaryType: 'script (python)', sizeBytes: 28672, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'Display CPU architecture details.',
    ),
    BinBinary(
      name: 'ps', path: '/usr/bin/ps', category: 'PROCESS', privilege: 'user',
      binaryType: 'ELF executable', sizeBytes: 139264, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'Report a snapshot of current processes.',
    ),
    BinBinary(
      name: 'top', path: '/usr/bin/top', category: 'PROCESS', privilege: 'user',
      binaryType: 'ELF executable', sizeBytes: 122880, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'Interactive process resource monitor.',
    ),
    BinBinary(
      name: 'kill', path: '/usr/bin/kill', category: 'PROCESS', privilege: 'user',
      binaryType: 'builtin + ELF', sizeBytes: 33792, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'Send signals to processes by pid or job.',
    ),
    BinBinary(
      name: 'df', path: '/usr/bin/df', category: 'FILESYSTEM', privilege: 'user',
      binaryType: 'ELF executable', sizeBytes: 58982, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'Report filesystem disk space usage.',
    ),
    BinBinary(
      name: 'du', path: '/usr/bin/du', category: 'FILESYSTEM', privilege: 'user',
      binaryType: 'ELF executable', sizeBytes: 112640, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'Estimate file and directory space usage.',
    ),
    BinBinary(
      name: 'mount', path: '/usr/bin/mount', category: 'FILESYSTEM', privilege: 'root',
      binaryType: 'ELF executable', sizeBytes: 55296, permissions: 'rwsr-xr-x',
      ownerUid: 0, groupGid: 0, isSetuid: true,
      description: 'Attach filesystems to the directory tree.',
    ),
    BinBinary(
      name: 'sudo', path: '/usr/bin/sudo', category: 'USER', privilege: 'root',
      binaryType: 'ELF executable', sizeBytes: 192512, permissions: 'rwsr-xr-x',
      ownerUid: 0, groupGid: 0, isSetuid: true,
      description: 'Execute a command as another user (privileged).',
    ),
    BinBinary(
      name: 'passwd', path: '/usr/bin/passwd', category: 'USER', privilege: 'root',
      binaryType: 'ELF executable', sizeBytes: 65536, permissions: 'rwsr-xr-x',
      ownerUid: 0, groupGid: 0, isSetuid: true,
      description: 'Update user authentication tokens.',
    ),
    BinBinary(
      name: 'whoami', path: '/usr/bin/whoami', category: 'USER', privilege: 'user',
      binaryType: 'builtin', sizeBytes: 20480, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'Print effective username of current process.',
    ),
    BinBinary(
      name: 'bash', path: '/usr/bin/bash', category: 'SHELL', privilege: 'user',
      binaryType: 'ELF executable', sizeBytes: 1183744, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'GNU Bourne-Again SHell interpreter.',
    ),
    BinBinary(
      name: 'sh', path: '/usr/bin/sh', category: 'SHELL', privilege: 'user',
      binaryType: 'symlink -> dash', sizeBytes: 4096, permissions: 'lrwxrwxrwx',
      ownerUid: 0, groupGid: 0, symlinkTarget: '/usr/bin/dash',
      description: 'POSIX shell entry point.',
    ),
    BinBinary(
      name: 'zsh', path: '/usr/bin/zsh', category: 'SHELL', privilege: 'user',
      binaryType: 'ELF executable', sizeBytes: 741376, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'Z shell with advanced scripting features.',
    ),
    BinBinary(
      name: 'rsync', path: '/usr/bin/rsync', category: 'SYNC', privilege: 'user',
      binaryType: 'ELF executable', sizeBytes: 561152, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'Fast incremental file transfer and sync tool.',
    ),
    BinBinary(
      name: 'tar', path: '/usr/bin/tar', category: 'SYNC', privilege: 'user',
      binaryType: 'ELF executable', sizeBytes: 450560, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'Archive files into tarballs.',
    ),
    BinBinary(
      name: 'which', path: '/usr/bin/which', category: 'PATH', privilege: 'user',
      binaryType: 'script (sh)', sizeBytes: 3072, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'Locate a command in the PATH environment.',
    ),
    BinBinary(
      name: 'whereis', path: '/usr/bin/whereis', category: 'PATH', privilege: 'user',
      binaryType: 'ELF executable', sizeBytes: 38912, permissions: 'rwxr-xr-x',
      ownerUid: 0, groupGid: 0, description: 'Locate binary, source and manual pages.',
    ),
  ];

  static const Map<String, Map<String, String>> commandHelp = {
    'ls': {'usage': 'ls [-l] [-a] [path]', 'desc': 'List directory contents.'},
    'cat': {'usage': 'cat <file>...', 'desc': 'Print file contents to stdout.'},
    'chmod': {'usage': 'chmod <mode> <file>', 'desc': 'Change permission bits.'},
    'chown': {'usage': 'chown <owner>[:group] <file>', 'desc': 'Change ownership.'},
    'ps': {'usage': 'ps [aux]', 'desc': 'Show process snapshot.'},
    'kill': {'usage': 'kill [-signal] <pid>', 'desc': 'Send signal to a process.'},
    'df': {'usage': 'df [-h]', 'desc': 'Disk free space report.'},
    'du': {'usage': 'du [-sh] [path]', 'desc': 'Disk usage estimate.'},
    'grep': {'usage': 'grep [-i] <pattern> <file>', 'desc': 'Search text with regex.'},
    'uname': {'usage': 'uname [-a]', 'desc': 'System information.'},
    'whoami': {'usage': 'whoami', 'desc': 'Current effective user.'},
    'mount': {'usage': 'mount [device] [dir]', 'desc': 'Mount a filesystem.'},
    'sudo': {'usage': 'sudo <command>', 'desc': 'Run as privileged user.'},
    'which': {'usage': 'which <command>', 'desc': 'Resolve command path.'},
  };

  static Map<String, dynamic> get statistics {
    final byCategory = <String, int>{};
    for (final b in binaries) {
      byCategory[b.category] = (byCategory[b.category] ?? 0) + 1;
    }
    final byPrivilege = <String, int>{};
    for (final b in binaries) {
      byPrivilege[b.privilege] = (byPrivilege[b.privilege] ?? 0) + 1;
    }
    final totalSize = binaries.fold<int>(0, (sum, b) => sum + b.sizeBytes);
    final setuidCount = binaries.where((b) => b.isSetuid).length;
    final links = binaries.where((b) => b.symlinkTarget != null).length;
    return {
      'total': binaries.length,
      'byCategory': byCategory,
      'byPrivilege': byPrivilege,
      'totalSizeBytes': totalSize,
      'setuidCount': setuidCount,
      'symlinkCount': links,
      'categories': categories.length,
    };
  }

  static List<FhsEntry> fhsReport() {
    return const [
      FhsEntry(directory: '/bin', description: 'Essential user command binaries', compliant: true, note: '28 binaries indexed'),
      FhsEntry(directory: '/sbin', description: 'System administration binaries', compliant: true, note: 'linked into /usr/sbin'),
      FhsEntry(directory: '/boot', description: 'Boot loader static files', compliant: true, note: 'kernel + initrd present'),
      FhsEntry(directory: '/etc', description: 'Host-specific system configuration', compliant: true, note: 'no executables found'),
      FhsEntry(directory: '/dev', description: 'Device files', compliant: true, note: 'managed by udev'),
      FhsEntry(directory: '/lib', description: 'Shared libraries and kernel modules', compliant: true, note: 'merged into /usr/lib'),
      FhsEntry(directory: '/media', description: 'Removable media mount points', compliant: true, note: 'auto-mounted volumes'),
      FhsEntry(directory: '/opt', description: 'Optional add-on packages', compliant: true, note: 'empty but present'),
      FhsEntry(directory: '/root', description: 'Home directory for root user', compliant: true, note: 'permissions 0700'),
      FhsEntry(directory: '/tmp', description: 'Temporary files', compliant: true, note: 'sticky bit set (drwxrwxrwt)'),
      FhsEntry(directory: '/var/log', description: 'Logs and variable data', compliant: false, note: 'rotation policy missing'),
      FhsEntry(directory: '/srv', description: 'Data for services provided by system', compliant: false, note: 'directory missing'),
    ];
  }

  static CommandResult execute(String command, List<String> args) {
    final sw = Stopwatch()..start();
    late CommandResult result;
    switch (command) {
      case 'ls':
        final buf = StringBuffer('total 24\n');
        buf.writeln('drwxr-xr-x  7 root root 4096 Aug 26 09:14 .');
        buf.writeln('drwxr-xr-x  1 root root 4096 Aug 25 18:02 ..');
        buf.writeln('-rw-r--r--  1 root root 220 Aug 12 10:00 .bashrc');
        buf.writeln('drwxr-xr-x  2 root root 4096 Aug 20 11:30 bin');
        buf.writeln('drwxr-xr-x 11 root root 4096 Aug 21 08:45 usr');
        buf.writeln('lrwxrwxrwx  1 root root   11 Aug 20 09:00 sh -> /usr/bin/bash');
        result = CommandResult(command: command, args: args, exitCode: 0, stdout: buf.toString(), durationMs: 0);
        break;
      case 'cat':
        if (args.isEmpty) {
          result = CommandResult(command: command, args: args, exitCode: 1, stdout: '', stderr: 'cat: missing operand', durationMs: 0);
        } else {
          result = CommandResult(
            command: command,
            args: args,
            exitCode: 0,
            stdout: '# UmerOS release config\nNAME="UmerOS"\nVERSION="1.0 (Umer)"\nID=umeros\nPRETTY_NAME="UmerOS 1.0"\nHOME_URL="https://umeros.local"\n',
            durationMs: 1,
          );
        }
        break;
      case 'uname':
        final flag = args.isNotEmpty ? args.first : '-s';
        result = CommandResult(
          command: command,
          args: args,
          exitCode: 0,
          stdout: flag.contains('a')
              ? 'UmerOS umeros-kernel 1.0.0 #1 SMP Wed Aug 26 x86_64 GNU/Linux\n'
              : 'UmerOS\n',
          durationMs: 0,
        );
        break;
      case 'df':
        result = CommandResult(
          command: command,
          args: args,
          exitCode: 0,
          stdout: 'Filesystem      Size  Used Avail Use% Mounted on\n'
              '/dev/root        59G   23G   34G  41% /\n'
              'tmpfs           3.9G     0  3.9G   0% /dev/shm\n'
              '/dev/sdb1       235G   87G  136G  39% /data\n',
          durationMs: 2,
        );
        break;
      case 'ps':
        result = CommandResult(
          command: command,
          args: args,
          exitCode: 0,
          stdout: 'USER       PID %CPU %MEM COMMAND\n'
              'root         1  0.0  0.1 systemd\n'
              'root       412  0.1  0.4 umerd --daemon\n'
              'umeros     908  0.3  1.2 flutter_ui\n'
              'umeros    1044  0.0  0.2 ai_service\n',
          durationMs: 1,
        );
        break;
      case 'whoami':
        result = CommandResult(command: command, args: args, exitCode: 0, stdout: 'umeros\n', durationMs: 0);
        break;
      case 'which':
        if (args.isEmpty) {
          result = CommandResult(command: command, args: args, exitCode: 1, stdout: '', stderr: 'which: missing argument', durationMs: 0);
        } else {
          result = CommandResult(command: command, args: args, exitCode: 0, stdout: '/usr/bin/${args.first}\n', durationMs: 0);
        }
        break;
      case 'chmod':
      case 'chown':
        final file = args.length > 1 ? args.last : '';
        result = CommandResult(
          command: command,
          args: args,
          exitCode: 0,
          stdout: file.isEmpty ? '' : "updated '$file'\n",
          stderr: file.isEmpty ? '$command: missing operand' : '',
          durationMs: 1,
        );
        break;
      case 'grep':
        result = CommandResult(
          command: command,
          args: args,
          exitCode: 0,
          stdout: 'NAME="UmerOS"\nID=umeros\nPRETTY_NAME="UmerOS 1.0"\n',
          durationMs: 1,
        );
        break;
      case 'sudo':
        if (args.isEmpty) {
          result = CommandResult(command: command, args: args, exitCode: 1, stdout: '', stderr: 'usage: sudo <command>', durationMs: 0);
        } else {
          result = CommandResult(
            command: command,
            args: args,
            exitCode: 0,
            stdout: '[mock] elevated: ${args.join(' ')}\n',
            durationMs: 3,
          );
        }
        break;
      default:
        sw.stop();
        result = CommandResult(
          command: command,
          args: args,
          exitCode: 127,
          stdout: '',
          stderr: "$command: command not found (not registered in essential_commands)",
          durationMs: 0,
        );
        return result;
    }
    sw.stop();
    return result;
  }

  static List<String> get availableCommands => commandHelp.keys.toList()..sort();
}

enum _Section { overview, binaries, terminal, fhs }

class BinApp extends StatefulWidget {
  const BinApp({super.key});

  @override
  State<BinApp> createState() => _BinAppState();
}

class _BinAppState extends State<BinApp> {
  _Section _section = _Section.overview;
  String _selectedCategory = 'All';
  String _searchQuery = '';

  String _selectedCommand = 'ls';
  final TextEditingController _argsController = TextEditingController();
  final TextEditingController _inputController = TextEditingController(text: 'ls -la /');
  final ScrollController _consoleScroll = ScrollController();
  final List<CommandResult> _history = [];
  bool _showHelp = false;

  @override
  void dispose() {
    _argsController.dispose();
    _inputController.dispose();
    _consoleScroll.dispose();
    super.dispose();
  }

  List<BinBinary> get _filteredBinaries {
    return BinService.binaries.where((b) {
      final matchesCat = _selectedCategory == 'All' || b.category == _selectedCategory;
      final q = _searchQuery.toLowerCase();
      final matchesQ = q.isEmpty ||
          b.name.toLowerCase().contains(q) ||
          b.path.toLowerCase().contains(q) ||
          b.description.toLowerCase().contains(q);
      return matchesCat && matchesQ;
    }).toList()
      ..sort((a, b) => a.name.compareTo(b.name));
  }

  void _runInput() {
    final raw = _inputController.text.trim();
    if (raw.isEmpty) return;
    final parts = raw.split(RegExp(r'\s+'));
    final cmd = parts.first;
    final args = parts.sublist(1);
    setState(() {
      _history.add(BinService.execute(cmd, args));
      if (_history.length > 100) _history.removeAt(0);
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_consoleScroll.hasClients) {
        _consoleScroll.jumpTo(_consoleScroll.position.maxScrollExtent);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;

    return Column(
      children: [
        _buildHeader(colorScheme, textTheme),
        Expanded(
          child: Row(
            children: [
              _buildSidebar(colorScheme, textTheme),
              Expanded(child: _buildBody(colorScheme, textTheme)),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildHeader(ColorScheme colorScheme, TextTheme textTheme) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        border: Border(bottom: BorderSide(color: colorScheme.outline.withValues(alpha: 0.2))),
      ),
      child: Row(
        children: [
          Icon(Icons.terminal, color: colorScheme.primary, size: 28),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Bin Manager',
                style: textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: colorScheme.onSurface,
                ),
              ),
              Text(
                'Essential binaries, commands and FHS layout',
                style: textTheme.bodySmall?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6)),
              ),
            ],
          ),
          const Spacer(),
          IconButton(
            tooltip: _showHelp ? 'Hide help' : 'Command help',
            onPressed: () => setState(() => _showHelp = !_showHelp),
            icon: Icon(_showHelp ? Icons.menu_book : Icons.menu_book_outlined),
          ),
        ],
      ),
    );
  }

  Widget _buildSidebar(ColorScheme colorScheme, TextTheme textTheme) {
    final stats = BinService.statistics;
    return Container(
      width: 200,
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        border: Border(right: BorderSide(color: colorScheme.outline.withValues(alpha: 0.2))),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Text('Sections', style: textTheme.titleSmall?.copyWith(
              fontWeight: FontWeight.bold,
              color: colorScheme.onSurface.withValues(alpha: 0.7),
            )),
          ),
          _navTile('Overview', Icons.dashboard_outlined, _Section.overview, colorScheme),
          _navTile('Binaries', Icons.apps_outlined, _Section.binaries, colorScheme),
          _navTile('Terminal', Icons.terminal_outlined, _Section.terminal, colorScheme),
          _navTile('FHS Report', Icons.fact_check_outlined, _Section.fhs, colorScheme),
          const Spacer(),
          Container(
            margin: const EdgeInsets.all(16),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: colorScheme.primaryContainer.withValues(alpha: 0.35),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  Icon(Icons.inventory_2, size: 14, color: colorScheme.primary),
                  const SizedBox(width: 6),
                  Text('${stats['total']} binaries',
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: colorScheme.onPrimaryContainer)),
                ]),
                const SizedBox(height: 4),
                Text('${stats['setuidCount']} setuid · ${stats['symlinkCount']} symlinks',
                    style: TextStyle(fontSize: 11, color: colorScheme.onPrimaryContainer.withValues(alpha: 0.8))),
                const SizedBox(height: 2),
                Text('${stats['categories']} categories indexed',
                    style: TextStyle(fontSize: 11, color: colorScheme.onPrimaryContainer.withValues(alpha: 0.8))),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _navTile(String label, IconData icon, _Section section, ColorScheme colorScheme) {
    final selected = _section == section;
    return ListTile(
      leading: Icon(icon, size: 20, color: selected ? colorScheme.primary : colorScheme.onSurface.withValues(alpha: 0.7)),
      title: Text(label, style: TextStyle(
        fontSize: 13,
        color: selected ? colorScheme.primary : colorScheme.onSurface,
        fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
      )),
      dense: true,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16),
      tileColor: selected ? colorScheme.primaryContainer.withValues(alpha: 0.3) : null,
      onTap: () => setState(() => _section = section),
    );
  }

  Widget _buildBody(ColorScheme colorScheme, TextTheme textTheme) {
    switch (_section) {
      case _Section.overview:
        return _buildOverview(colorScheme, textTheme);
      case _Section.binaries:
        return _buildBinaries(colorScheme, textTheme);
      case _Section.terminal:
        return _buildTerminal(colorScheme, textTheme);
      case _Section.fhs:
        return _buildFhs(colorScheme, textTheme);
    }
  }

  Widget _statCard(String label, String value, IconData icon, Color color, ColorScheme colorScheme, TextTheme textTheme) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Row(children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(color: color.withValues(alpha: 0.18), borderRadius: BorderRadius.circular(10)),
              child: Icon(icon, size: 18, color: color),
            ),
            const Spacer(),
            Text(value, style: textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700, color: colorScheme.onSurface)),
          ]),
          const SizedBox(height: 8),
          Text(label, style: textTheme.bodySmall?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6))),
        ],
      ),
    );
  }

  Widget _buildOverview(ColorScheme colorScheme, TextTheme textTheme) {
    final stats = BinService.statistics;
    final total = stats['total'] as int;
    final byCategory = stats['byCategory'] as Map<String, int>;
    final byPrivilege = stats['byPrivilege'] as Map<String, int>;
    final totalMb = ((stats['totalSizeBytes'] as int) / (1024 * 1024)).toStringAsFixed(1);

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        GridView.count(
          crossAxisCount: 4,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 12,
          crossAxisSpacing: 12,
          childAspectRatio: 2.1,
          children: [
            _statCard('Indexed binaries', '$total', Icons.apps, colorScheme.primary, colorScheme, textTheme),
            _statCard('Total footprint', '$totalMb MB', Icons.sd_storage_outlined, Colors.amber.shade700, colorScheme, textTheme),
            _statCard('setuid binaries', '${stats['setuidCount']}', Icons.enhanced_encryption_outlined, Colors.redAccent, colorScheme, textTheme),
            _statCard('Symlinks', '${stats['symlinkCount']}', Icons.link, Colors.cyan, colorScheme, textTheme),
          ],
        ),
        const SizedBox(height: 20),
        Text('Distribution by category', style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
        const SizedBox(height: 10),
        ...byCategory.entries.map((e) {
          final frac = e.value / total;
          final color = BinService.categoryColors[e.key] ?? colorScheme.primary;
          return Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(
              children: [
                SizedBox(
                  width: 130,
                  child: Row(children: [
                    Icon(BinService.categoryIcons[e.key], size: 14, color: color),
                    const SizedBox(width: 6),
                    Flexible(child: Text(e.key, style: TextStyle(fontSize: 11, color: colorScheme.onSurface.withValues(alpha: 0.8)), overflow: TextOverflow.ellipsis)),
                  ]),
                ),
                Expanded(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(6),
                    child: LinearProgressIndicator(
                      value: frac,
                      minHeight: 10,
                      backgroundColor: colorScheme.surfaceContainerHighest,
                      valueColor: AlwaysStoppedAnimation<Color>(color),
                    ),
                  ),
                ),
                SizedBox(width: 44, child: Text('${e.value}', textAlign: TextAlign.right, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600))),
              ],
            ),
          );
        }),
        const SizedBox(height: 20),
        Text('Privilege split', style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
        const SizedBox(height: 10),
        Wrap(
          spacing: 10,
          runSpacing: 8,
          children: byPrivilege.entries.map((e) {
            final isRoot = e.key == 'root';
            final c = isRoot ? Colors.redAccent : Colors.green;
            return Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: c.withValues(alpha: 0.12),
                border: Border.all(color: c.withValues(alpha: 0.35)),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Icon(isRoot ? Icons.admin_panel_settings : Icons.person_outline, size: 16, color: c),
                const SizedBox(width: 8),
                Text('${isRoot ? "root-only" : "user"} · ${e.value} (${(e.value / total * 100).round()}%)',
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: colorScheme.onSurface)),
              ]),
            );
          }).toList(),
        ),
        const SizedBox(height: 24),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: colorScheme.surfaceContainerHigh,
            borderRadius: BorderRadius.circular(14),
            border: Border(left: BorderSide(width: 4, color: colorScheme.primary)),
          ),
          child: Row(
            children: [
              Icon(Icons.bolt, color: colorScheme.primary),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  'All binaries are imported from essential_commands and exposed through BinManager.execute(). This view is UI-only and mirrors the Python module data.',
                  style: textTheme.bodyMedium?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.75)),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _categoryChip(String label, ColorScheme colorScheme) {
    final selected = _selectedCategory == label;
    return FilterChip(
      avatar: label == 'All'
          ? null
          : Icon(BinService.categoryIcons[label], size: 14, color: selected ? colorScheme.onPrimaryContainer : BinService.categoryColors[label]),
      label: Text(label),
      selected: selected,
      onSelected: (_) => setState(() => _selectedCategory = label),
      selectedColor: colorScheme.primaryContainer,
      labelStyle: TextStyle(color: selected ? colorScheme.onPrimaryContainer : colorScheme.onSurface, fontSize: 12),
      visualDensity: VisualDensity.compact,
    );
  }

  Widget _buildBinaries(ColorScheme colorScheme, TextTheme textTheme) {
    final filtered = _filteredBinaries;
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  decoration: InputDecoration(
                    hintText: 'Search binaries...',
                    prefixIcon: const Icon(Icons.search, size: 20),
                    isDense: true,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: BorderSide(color: colorScheme.outline)),
                    filled: true,
                    fillColor: colorScheme.surface,
                  ),
                  onChanged: (v) => setState(() => _searchQuery = v),
                ),
              ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
          child: Wrap(
            spacing: 6,
            runSpacing: 4,
            children: ['All', ...BinService.categories].map((c) => _categoryChip(c, colorScheme)).toList(),
          ),
        ),
        Expanded(
          child: filtered.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.apps_outlined, size: 64, color: colorScheme.onSurface.withValues(alpha: 0.3)),
                      const SizedBox(height: 16),
                      Text('No binaries match your filters', style: textTheme.titleMedium?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.5))),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                  itemCount: filtered.length,
                  itemBuilder: (_, i) => _binaryCard(filtered[i], colorScheme, textTheme),
                ),
        ),
      ],
    );
  }

  Color _entryColor(BinBinary b) {
    if (b.symlinkTarget != null) return Colors.cyan;
    if (b.isSetuid || b.isSetgid || b.privilege == 'root') return Colors.redAccent;
    return BinService.categoryColors[b.category] ?? Colors.blueGrey;
  }

  Widget _badge(String text, Color color, ColorScheme colorScheme) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        border: Border.all(color: color.withValues(alpha: 0.4)),
        borderRadius: BorderRadius.circular(5),
      ),
      child: Text(text, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: color)),
    );
  }

  Widget _binaryCard(BinBinary b, ColorScheme colorScheme, TextTheme textTheme) {
    final accent = _entryColor(b);
    final isLink = b.symlinkTarget != null;
    return Card(
      color: colorScheme.surfaceContainerHigh,
      margin: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => setState(() {
          _selectedCommand = b.name;
          _section = _Section.terminal;
        }),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              Container(
                width: 46,
                height: 46,
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: 0.15),
                  border: Border.all(color: accent.withValues(alpha: 0.35)),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(isLink ? Icons.link : BinService.categoryIcons[b.category] ?? Icons.terminal, size: 22, color: accent),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          b.name,
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            fontFamily: 'monospace',
                            color: colorScheme.onSurface,
                          ),
                        ),
                        const SizedBox(width: 8),
                        _badge(b.modeString, accent, colorScheme),
                        if (b.isSetuid) ...[
                          const SizedBox(width: 4),
                          _badge('SETUID', Colors.redAccent, colorScheme),
                        ],
                        if (b.isSetgid) ...[
                          const SizedBox(width: 4),
                          _badge('SETGID', Colors.orange, colorScheme),
                        ],
                        if (b.isSticky) ...[
                          const SizedBox(width: 4),
                          _badge('STICKY', Colors.purple, colorScheme),
                        ],
                        const Spacer(),
                        Text(b.humanSize, style: TextStyle(fontSize: 11, color: colorScheme.onSurface.withValues(alpha: 0.55))),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      isLink ? '${b.path} -> ${b.symlinkTarget}' : b.path,
                      style: TextStyle(fontSize: 12, fontFamily: 'monospace', color: colorScheme.onSurface.withValues(alpha: 0.6)),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 4),
                    Text(b.description, style: textTheme.bodySmall?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.55)), maxLines: 1, overflow: TextOverflow.ellipsis),
                  ],
                ),
              ),
              const SizedBox(width: 10),
              Tooltip(
                message: 'uid ${b.ownerUid} · gid ${b.groupGid}\n${b.binaryType}',
                triggerMode: TooltipTriggerMode.tap,
                child: Icon(Icons.info_outline, size: 18, color: colorScheme.onSurface.withValues(alpha: 0.4)),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTerminal(ColorScheme colorScheme, TextTheme textTheme) {
    final help = BinService.commandHelp[_selectedCommand];
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          Row(
            children: [
              DropdownButton<String>(
                value: BinService.availableCommands.contains(_selectedCommand) ? _selectedCommand : null,
                hint: const Text('pick command'),
                underline: const SizedBox.shrink(),
                items: BinService.availableCommands.map((c) => DropdownMenuItem(value: c, child: Text(c, style: const TextStyle(fontFamily: 'monospace')))).toList(),
                onChanged: (v) { if (v != null) setState(() => _selectedCommand = v); },
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TextField(
                  controller: _argsController,
                  decoration: InputDecoration(
                    hintText: 'arguments, e.g. -la /usr',
                    prefixText: '$_selectedCommand ',
                    prefixStyle: const TextStyle(fontFamily: 'monospace', fontWeight: FontWeight.w600),
                    isDense: true,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: BorderSide(color: colorScheme.outline)),
                    filled: true,
                    fillColor: colorScheme.surface,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              FilledButton.icon(
                onPressed: () {
                  final args = _argsController.text.trim().isEmpty
                      ? <String>[]
                      : _argsController.text.trim().split(RegExp(r'\s+'));
                  setState(() => _history.add(BinService.execute(_selectedCommand, args)));
                },
                icon: const Icon(Icons.play_arrow, size: 18),
                label: const Text('Run'),
              ),
            ],
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _inputController,
            onSubmitted: (_) => _runInput(),
            style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
            decoration: InputDecoration(
              hintText: 'type a shell line and press Enter…',
              prefixIcon: const Icon(Icons.chevron_right),
              isDense: true,
              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: BorderSide(color: colorScheme.outline)),
              filled: true,
              fillColor: colorScheme.surfaceContainerLowest,
            ),
          ),
          const SizedBox(height: 12),
          Expanded(child: _console(colorScheme, textTheme)),
          if (_showHelp && help != null) _helpPanel(help, colorScheme, textTheme),
        ],
      ),
    );
  }

  Widget _console(ColorScheme colorScheme, TextTheme textTheme) {
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: const Color(0xFF14161A),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: colorScheme.outline.withValues(alpha: 0.25)),
      ),
      child: _history.isEmpty
          ? Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.terminal, size: 48, color: Colors.white.withValues(alpha: 0.2)),
                  const SizedBox(height: 12),
                  Text('No output yet — run a command above.', style: TextStyle(color: Colors.white.withValues(alpha: 0.35), fontSize: 13)),
                ],
              ),
            )
          : SingleChildScrollView(
              controller: _consoleScroll,
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final r in _history) ...[
                    SelectableText.rich(
                      TextSpan(style: const TextStyle(fontFamily: 'monospace', fontSize: 12, height: 1.45), children: [
                        TextSpan(text: '\$ ', style: TextStyle(color: Colors.greenAccent.shade200)),
                        TextSpan(text: [r.command, ...r.args].join(' '), style: const TextStyle(color: Colors.white70)),
                        if (r.stdout.isNotEmpty)
                          TextSpan(text: '\n${r.stdout}', style: const TextStyle(color: Color(0xFFD4D4D4))),
                        if (r.stderr.isNotEmpty)
                          TextSpan(text: '\n${r.stderr}', style: const TextStyle(color: Color(0xFFFF6B68))),
                        TextSpan(text: '\n[exit ${r.exitCode}] ', style: TextStyle(color: r.success ? Colors.greenAccent : Colors.orangeAccent)),
                        TextSpan(text: '${r.durationMs}ms', style: TextStyle(color: Colors.white.withValues(alpha: 0.35))),
                      ]),
                    ),
                    const SizedBox(height: 10),
                  ],
                ],
              ),
            ),
    );
  }

  Widget _helpPanel(Map<String, String> help, ColorScheme colorScheme, TextTheme textTheme) {
    return Container(
      margin: const EdgeInsets.only(top: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: colorScheme.secondaryContainer.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          Icon(Icons.help_outline, size: 18, color: colorScheme.onSecondaryContainer),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              '${help['desc']}   Usage: ${help['usage']}',
              style: TextStyle(fontSize: 12, color: colorScheme.onSecondaryContainer, fontFamily: 'monospace'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFhs(ColorScheme colorScheme, TextTheme textTheme) {
    final report = BinService.fhsReport();
    final ok = report.where((e) => e.compliant).length;
    final issues = report.length - ok;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Row(
          children: [
            Expanded(
              child: _statCard('Compliant paths', '$ok / ${report.length}', Icons.check_circle_outline, Colors.green, colorScheme, textTheme),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _statCard('Issues found', '$issues', Icons.warning_amber_outlined, issues > 0 ? Colors.redAccent : Colors.grey, colorScheme, textTheme),
            ),
          ],
        ),
        const SizedBox(height: 16),
        ...report.map((e) {
          final c = e.compliant ? Colors.green : Colors.redAccent;
          return Card(
            color: colorScheme.surfaceContainerHigh,
            margin: const EdgeInsets.only(bottom: 8),
            child: ListTile(
              leading: Icon(e.compliant ? Icons.check_circle : Icons.error_outline, color: c),
              title: Text(e.directory, style: const TextStyle(fontFamily: 'monospace', fontSize: 14, fontWeight: FontWeight.w600)),
              subtitle: Text('${e.description}\n${e.note}', style: TextStyle(fontSize: 11, height: 1.4, color: colorScheme.onSurface.withValues(alpha: 0.6))),
              isThreeLine: true,
              trailing: Chip(
                label: Text(e.compliant ? 'OK' : 'FIX', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: c)),
                backgroundColor: c.withValues(alpha: 0.12),
                side: BorderSide(color: c.withValues(alpha: 0.4)),
                visualDensity: VisualDensity.compact,
              ),
            ),
          );
        }),
      ],
    );
  }
}
