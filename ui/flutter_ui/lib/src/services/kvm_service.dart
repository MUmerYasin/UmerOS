/// UmerOS Flutter UI — KVM Virtual Machine Service
/// ================================================
/// Provides integration with the UmerOS Python KVM implementation.
/// Communicates with the umeros_python.exe interpreter for VM management.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/services.dart';

/// Represents a Virtual Machine configuration
class VMConfig {
  final String id;
  final String name;
  final int memoryMB;
  final int vcpus;
  final String? diskPath;
  final String? isoPath;
  final bool enableNetwork;
  final String? macAddress;
  final Map<String, dynamic> extraArgs;

  const VMConfig({
    required this.id,
    required this.name,
    this.memoryMB = 1024,
    this.vcpus = 1,
    this.diskPath,
    this.isoPath,
    this.enableNetwork = true,
    this.macAddress,
    this.extraArgs = const {},
  });

  VMConfig copyWith({
    String? id,
    String? name,
    int? memoryMB,
    int? vcpus,
    String? diskPath,
    String? isoPath,
    bool? enableNetwork,
    String? macAddress,
    Map<String, dynamic>? extraArgs,
  }) {
    return VMConfig(
      id: id ?? this.id,
      name: name ?? this.name,
      memoryMB: memoryMB ?? this.memoryMB,
      vcpus: vcpus ?? this.vcpus,
      diskPath: diskPath ?? this.diskPath,
      isoPath: isoPath ?? this.isoPath,
      enableNetwork: enableNetwork ?? this.enableNetwork,
      macAddress: macAddress ?? this.macAddress,
      extraArgs: extraArgs ?? this.extraArgs,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'memoryMB': memoryMB,
    'vcpus': vcpus,
    'diskPath': diskPath,
    'isoPath': isoPath,
    'enableNetwork': enableNetwork,
    'macAddress': macAddress,
    'extraArgs': extraArgs,
  };

  static VMConfig fromJson(Map<String, dynamic> json) => VMConfig(
    id: json['id'] as String,
    name: json['name'] as String,
    memoryMB: json['memoryMB'] as int? ?? 1024,
    vcpus: json['vcpus'] as int? ?? 1,
    diskPath: json['diskPath'] as String?,
    isoPath: json['isoPath'] as String?,
    enableNetwork: json['enableNetwork'] as bool? ?? true,
    macAddress: json['macAddress'] as String?,
    extraArgs: Map<String, dynamic>.from(json['extraArgs'] ?? {}),
  );

  /// Generate command-line arguments for the KVM interpreter
  List<String> toKvmArgs() {
    final args = <String>[
      '-m', memoryMB.toString(),
      '-smp', vcpus.toString(),
    ];
    if (diskPath != null) {
      args.addAll(['-drive', 'file=$diskPath,format=raw,if=virtio']);
    }
    if (isoPath != null) {
      args.addAll(['-cdrom', isoPath!]);
    }
    if (enableNetwork) {
      final mac = macAddress ?? '52:54:00:${(DateTime.now().millisecondsSinceEpoch % 256).toRadixString(16).padLeft(2, '0')}:${(DateTime.now().millisecondsSinceEpoch ~/ 256 % 256).toRadixString(16).padLeft(2, '0')}:${(DateTime.now().millisecondsSinceEpoch ~/ 65536 % 256).toRadixString(16).padLeft(2, '0')}';
      args.addAll(['-netdev', 'user,id=net0', '-device', 'virtio-net-pci,netdev=net0,mac=$mac']);
    }
    extraArgs.forEach((k, v) {
      args.add('-${k.replaceAll('_', '-')}');
      if (v is! bool || v) args.add(v.toString());
    });
    return args;
  }
}

/// VM Runtime state
enum VMState { stopped, starting, running, paused, stopping, error }

class VMInstance {
  final VMConfig config;
  VMState state;
  Process? process;
  final List<String> outputLog;
  DateTime? startTime;
  int? exitCode;
  String? errorMessage;

  VMInstance({
    required this.config,
    this.state = VMState.stopped,
    this.process,
    List<String>? outputLog,
    this.startTime,
    this.exitCode,
    this.errorMessage,
  }) : outputLog = outputLog ?? [];

  Map<String, dynamic> toJson() => {
    'config': config.toJson(),
    'state': state.name,
    'startTime': startTime?.toIso8601String(),
    'exitCode': exitCode,
    'errorMessage': errorMessage,
  };
}

/// KVM Service - manages VM lifecycle and communicates with Python KVM
class KVMService {
  KVMService._();

  static final KVMService instance = KVMService._();

  // VM instances managed by this service
  final Map<String, VMInstance> _vms = {};

  // Stream controllers for reactive UI
  final _vmsController = StreamController<Map<String, VMInstance>>.broadcast();
  final _logController = StreamController<LogEntry>.broadcast();

  Stream<Map<String, VMInstance>> get vmsStream => _vmsController.stream;
  Stream<LogEntry> get logStream => _logController.stream;

  // Cached interpreter path
  String? _cachedInterpreterPath;
  bool _isInterpreterAvailable = false;

  /// Initialize the service
  Future<void> init() async {
    await _findInterpreter();
    await _loadPersistedVMs();
  }

  /// Find the UmerOS Python interpreter
  Future<void> _findInterpreter() async {
    try {
      final flutterExe = Platform.resolvedExecutable;
      final exeDir = File(flutterExe).parent;
      final sep = Platform.pathSeparator;

      // Walk up to find UmerOS root
      final root7 = exeDir.parent.parent.parent.parent.parent.parent.parent;

      // 1. Same dir as Flutter exe
      final local = '${exeDir.path}$sepumeros_python.exe';
      if (await File(local).exists()) {
        _cachedInterpreterPath = local;
        _isInterpreterAvailable = true;
        return;
      }

      // 2. UmerOS/boot/python_vm/build/
      final rootPath = root7.path;
      final p1 = '$rootPath${sep}boot${sep}python_vm${sep}build${sep}umeros_python.exe';
      if (await File(p1).exists()) {
        _cachedInterpreterPath = p1;
        _isInterpreterAvailable = true;
        return;
      }

      // 3. UmerOS/boot/python_vm/ (no build subdir)
      final p2 = '$rootPath${sep}boot${sep}python_vm${sep}umeros_python.exe';
      if (await File(p2).exists()) {
        _cachedInterpreterPath = p2;
        _isInterpreterAvailable = true;
        return;
      }

      // 4. Fallback: bare name (relies on PATH)
      _cachedInterpreterPath = 'umeros_python.exe';
      _isInterpreterAvailable = false;
    } catch (e) {
      _addLog(LogEntry.error('Failed to find interpreter: $e'));
      _cachedInterpreterPath = 'umeros_python.exe';
      _isInterpreterAvailable = false;
    }
  }

  /// Load persisted VM configurations
  Future<void> _loadPersistedVMs() async {
    // TODO: Implement persistence using prefs_service
    _notifyVMsChanged();
  }

  /// Get all VMs
  Map<String, VMInstance> get vms => Map.unmodifiable(_vms);

  /// Get a specific VM
  VMInstance? getVM(String id) => _vms[id];

  /// Check if interpreter is available
  bool get isInterpreterAvailable => _isInterpreterAvailable;
  String? get interpreterPath => _cachedInterpreterPath;

  /// Create a new VM
  Future<VMInstance> createVM({
    required String name,
    int memoryMB = 1024,
    int vcpus = 1,
    String? diskPath,
    String? isoPath,
    bool enableNetwork = true,
    Map<String, dynamic> extraArgs = const {},
  }) async {
    final id = 'vm_${DateTime.now().millisecondsSinceEpoch}';
    final config = VMConfig(
      id: id,
      name: name,
      memoryMB: memoryMB,
      vcpus: vcpus,
      diskPath: diskPath,
      isoPath: isoPath,
      enableNetwork: enableNetwork,
    );
    final vm = VMInstance(config: config);
    _vms[id] = vm;
    _addLog(LogEntry.info('Created VM "$name" ($id)'));
    _notifyVMsChanged();
    return vm;
  }

  /// Start a VM
  Future<bool> startVM(String id) async {
    final vm = _vms[id];
    if (vm == null) {
      _addLog(LogEntry.error('VM $id not found'));
      return false;
    }
    if (vm.state != VMState.stopped) {
      _addLog(LogEntry.warning('VM ${vm.config.name} is not stopped'));
      return false;
    }
    if (!_isInterpreterAvailable || _cachedInterpreterPath == null) {
      _addLog(LogEntry.error('KVM interpreter not available. Please build umeros_python.exe first.'));
      vm.state = VMState.error;
      vm.errorMessage = 'Interpreter not available';
      _notifyVMsChanged();
      return false;
    }

    vm.state = VMState.starting;
    vm.startTime = DateTime.now();
    vm.outputLog.clear();
    _notifyVMsChanged();

    try {
      final args = [
        '-m', vm.config.memoryMB.toString(),
        '-smp', vm.config.vcpus.toString(),
      ];
      
      if (vm.config.diskPath != null) {
        args.addAll(['-drive', 'file=${vm.config.diskPath},format=raw,if=virtio']);
      }
      if (vm.config.isoPath != null) {
        args.addAll(['-cdrom', vm.config.isoPath!]);
      }
      if (vm.config.enableNetwork) {
        final mac = vm.config.macAddress ?? '52:54:00:${(DateTime.now().millisecondsSinceEpoch % 256).toRadixString(16).padLeft(2, '0')}:${(DateTime.now().millisecondsSinceEpoch ~/ 256 % 256).toRadixString(16).padLeft(2, '0')}:${(DateTime.now().millisecondsSinceEpoch ~/ 65536 % 256).toRadixString(16).padLeft(2, '0')}';
        args.addAll(['-netdev', 'user,id=net0', '-device', 'virtio-net-pci,netdev=net0,mac=$mac']);
      }

      final workDir = Platform.environment['HOME'] ?? Platform.environment['USERPROFILE'] ?? '.';
      final proc = await Process.start(
        _cachedInterpreterPath!,
        args,
        workingDirectory: workDir,
        runInShell: true,
      );

      vm.process = proc;
      vm.state = VMState.running;
      _addLog(LogEntry.info('VM ${vm.config.name} started (PID: ${proc.pid})'));

      // Listen to stdout
      proc.stdout
          .transform(const SystemEncoding().decoder)
          .transform(const LineSplitter())
          .listen((line) {
            vm.outputLog.add(line);
            _addLog(LogEntry.output(line, vmId: id));
          });

      // Listen to stderr
      proc.stderr
          .transform(const SystemEncoding().decoder)
          .transform(const LineSplitter())
          .listen((line) {
            vm.outputLog.add('[STDERR] $line');
            _addLog(LogEntry.error(line, vmId: id));
          });

      // Handle exit
      proc.exitCode.then((code) {
        if (vm.state == VMState.running || vm.state == VMState.starting) {
          vm.state = VMState.stopped;
          vm.exitCode = code;
          _addLog(LogEntry.info('VM ${vm.config.name} exited with code $code'));
          _notifyVMsChanged();
        }
      });

      _notifyVMsChanged();
      return true;
    } catch (e) {
      vm.state = VMState.error;
      vm.errorMessage = e.toString();
      _addLog(LogEntry.error('Failed to start VM ${vm.config.name}: $e'));
      _notifyVMsChanged();
      return false;
    }
  }

  /// Stop a VM
  Future<void> stopVM(String id) async {
    final vm = _vms[id];
    if (vm == null) return;
    if (vm.state == VMState.stopped) return;

    vm.state = VMState.stopping;
    _notifyVMsChanged();

    if (vm.process != null) {
      vm.process!.kill();
      vm.process = null;
    }
    vm.state = VMState.stopped;
    _addLog(LogEntry.info('VM ${vm.config.name} stopped'));
    _notifyVMsChanged();
  }

  /// Restart a VM
  Future<void> restartVM(String id) async {
    await stopVM(id);
    await Future.delayed(const Duration(milliseconds: 500));
    await startVM(id);
  }

  /// Delete a VM
  Future<void> deleteVM(String id) async {
    final vm = _vms[id];
    if (vm == null) return;
    await stopVM(id);
    _vms.remove(id);
    _addLog(LogEntry.info('Deleted VM ${vm.config.name} ($id)'));
    _notifyVMsChanged();
  }

  /// Send command to VM stdin (if running)
  Future<void> sendCommand(String id, String command) async {
    final vm = _vms[id];
    if (vm == null || vm.process == null || vm.state != VMState.running) {
      _addLog(LogEntry.error('Cannot send command: VM not running'));
      return;
    }
    vm.process!.stdin.writeln(command);
    _addLog(LogEntry.input(command, vmId: id));
  }

  // Log management
  void _addLog(LogEntry entry) {
    if (!_logController.isClosed) {
      _logController.add(entry);
    }
  }

  void _notifyVMsChanged() {
    if (!_vmsController.isClosed) {
      _vmsController.add(Map.unmodifiable(_vms));
    }
  }

  void dispose() {
    _vmsController.close();
    _logController.close();
  }
}

/// Log entry for VM operations
class LogEntry {
  final LogType type;
  final String message;
  final String? vmId;
  final DateTime timestamp;

  const LogEntry({
    required this.type,
    required this.message,
    this.vmId,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();

  factory LogEntry.info(String message, {String? vmId}) =>
      LogEntry(type: LogType.info, message: message, vmId: vmId);

  factory LogEntry.warning(String message, {String? vmId}) =>
      LogEntry(type: LogType.warning, message: message, vmId: vmId);

  factory LogEntry.error(String message, {String? vmId}) =>
      LogEntry(type: LogType.error, message: message, vmId: vmId);

  factory LogEntry.output(String message, {String? vmId}) =>
      LogEntry(type: LogType.output, message: message, vmId: vmId);

  factory LogEntry.input(String message, {String? vmId}) =>
      LogEntry(type: LogType.input, message: message, vmId: vmId);

  @override
  String toString() => '[${timestamp.toIso8601String()}] ${type.name}: $message${vmId != null ? ' (VM: $vmId)' : ''}';
}

enum LogType { info, warning, error, output, input }

/// Helper extension for log type colors
extension LogTypeColor on LogType {
  String get label => switch (this) {
    LogType.info => 'INFO',
    LogType.warning => 'WARN',
    LogType.error => 'ERROR',
    LogType.output => 'OUT',
    LogType.input => 'IN',
  };
}