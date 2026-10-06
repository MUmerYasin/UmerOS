/// UmerOS Flutter UI — KVM Virtual Machine Service
/// =====================================================
/// Models the UmerOS Python KVM subsystem (virt/kvm port)
/// in Dart so the desktop can drive the same state machine:
///   KVM → MemorySlots, vCPUs, IRQ routing, dirty ring,
///   coalesced MMIO, stats, and the virt/lib IRQ-bypass
///   producer/consumer manager.
///
/// Where `umeros_python.exe` is present, generated scripts
/// that exercise the Python `virt.kvm` modules can be run
/// directly; otherwise the service runs in model-only mode.
library;

import 'dart:async';
import 'dart:io';

/// A single guest memory slot (mirrors MemorySlot in virt/kvm).
class MemorySlot {
  final int slotId;
  int guestPhysAddr;
  int memorySize;
  int userspaceAddr;
  int flags;
  bool dirtyLogging;

  MemorySlot({
    required this.slotId,
    required this.guestPhysAddr,
    required this.memorySize,
    required this.userspaceAddr,
    this.flags = 0,
    this.dirtyLogging = false,
  });

  String get sizeMB => '${(memorySize / (1024 * 1024)).toStringAsFixed(0)} MB';
  String get gpaHex => '0x${guestPhysAddr.toRadixString(16).padLeft(8, '0')}';
}

/// A virtual CPU (mirrors KVMVCPU in virt/kvm).
class VCPU {
  final int id;
  String state;
  int vcpuId;

  VCPU({required this.id, this.state = 'created', this.vcpuId = 0});
}

/// One IRQ routing entry (GSI → PIC/IOAPIC pin).
class IRQRoutingEntry {
  final int gsi;
  final String chip; // 'pic' | 'ioapic'
  int pin;

  IRQRoutingEntry({required this.gsi, this.chip = 'ioapic', this.pin = 0});
}

/// Dirty page tracking ring (mirrors DirtyRing in virt/kvm).
class DirtyRingState {
  int size;
  int head;
  int tail;
  final List<int> positions;

  DirtyRingState({this.size = 1024, this.head = 0, this.tail = 0})
      : positions = List.filled(1024, 0);

  int get count => (tail - head).abs();
}

/// Coalesced MMIO ring summary (mirrors CoalescedMMIO).
class CoalescedMMIOState {
  int capacity;
  int pending;

  CoalescedMMIOState({this.capacity = 256, this.pending = 0});
}

/// KVM statistics counters (mirrors BinaryStats / kvm_main.stats).
class KVMStats {
  final Map<String, int> counters;

  KVMStats({Map<String, int>? counters}) : counters = counters ?? {};

  int operator [](String key) => counters[key] ?? 0;

  void bump(String key, [int by = 1]) =>
      counters[key] = (counters[key] ?? 0) + by;
}

/// VM configuration.
class VMConfig {
  final String id;
  final String name;
  final int memoryMB;
  final int vcpus;
  final String? diskPath;
  final String? isoPath;
  final bool enableNetwork;
  final String? macAddress;

  const VMConfig({
    required this.id,
    required this.name,
    this.memoryMB = 1024,
    this.vcpus = 1,
    this.diskPath,
    this.isoPath,
    this.enableNetwork = true,
    this.macAddress,
  });
}

enum VMState { stopped, starting, running, paused, stopping, error }

/// A running (or stopped) VM instance with full KVM subsystem state.
class VMInstance {
  final VMConfig config;
  VMState state;
  final List<MemorySlot> memorySlots;
  final List<VCPU> vcpus;
  final List<IRQRoutingEntry> irqRouting;
  final DirtyRingState dirtyRing;
  final CoalescedMMIOState coalescedMMIO;
  KVMStats stats;
  final List<String> outputLog;
  DateTime? startTime;
  int? exitCode;
  String? errorMessage;

  VMInstance({
    required this.config,
    this.state = VMState.stopped,
    List<MemorySlot>? memorySlots,
    List<VCPU>? vcpus,
    List<IRQRoutingEntry>? irqRouting,
    DirtyRingState? dirtyRing,
    CoalescedMMIOState? coalescedMMIO,
    KVMStats? stats,
    List<String>? outputLog,
    this.startTime,
    this.exitCode,
    this.errorMessage,
  })  : memorySlots = memorySlots ?? [],
        vcpus = vcpus ?? [],
        irqRouting = irqRouting ?? [],
        dirtyRing = dirtyRing ?? DirtyRingState(),
        coalescedMMIO = coalescedMMIO ?? CoalescedMMIOState(),
        stats = stats ?? KVMStats(),
        outputLog = outputLog ?? [];

  int get totalMemoryBytes =>
      memorySlots.fold(0, (sum, s) => sum + s.memorySize);
}

/// IRQ-bypass producer/consumer (mirrors virt/lib/irqbypass).
class IRQBypassPeer {
  final String name;
  final bool isProducer;
  bool connected;

  const IRQBypassPeer({
    required this.name,
    required this.isProducer,
    this.connected = false,
  });
}

/// Log entry for VM/KVM operations.
class LogEntry {
  final LogType type;
  final String message;
  final String? vmId;
  final DateTime timestamp;

  LogEntry({
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

  String get label => switch (type) {
        LogType.info => 'INFO',
        LogType.warning => 'WARN',
        LogType.error => 'ERROR',
        LogType.output => 'OUT',
        LogType.input => 'IN',
      };
}

enum LogType { info, warning, error, output, input }

/// KVM Service — singleton that owns all VM + KVM subsystem state.
class KVMService {
  KVMService._();
  static final KVMService instance = KVMService._();

  final Map<String, VMInstance> _vms = {};
  final List<IRQBypassPeer> _irqBypassPeers = [];
  final List<LogEntry> _log = [];

  final _vmsController = StreamController<void>.broadcast();
  final _logController = StreamController<LogEntry>.broadcast();

  Stream<void> get vmsStream => _vmsController.stream;
  Stream<LogEntry> get logStream => _logController.stream;

  String? _interpreterPath;
  bool _interpreterAvailable = false;

  bool get interpreterAvailable => _interpreterAvailable;
  String? get interpreterPath => _interpreterPath;

  Map<String, VMInstance> get vms => Map.unmodifiable(_vms);
  List<IRQBypassPeer> get irqBypassPeers => List.unmodifiable(_irqBypassPeers);
  List<LogEntry> get log => List.unmodifiable(_log);

  /// Probe for the UmerOS Python interpreter.
  Future<void> init() async {
    await _findInterpreter();
    _seedIRQBypass();
    _addLog(LogEntry.info('KVM service initialised'));
  }

  Future<void> _findInterpreter() async {
    try {
      final flutterExe = Platform.resolvedExecutable;
      final exeDir = File(flutterExe).parent;
      final sep = Platform.pathSeparator;
      final root7 = exeDir.parent.parent.parent.parent.parent.parent.parent;

      final candidates = <String>[
        '${exeDir.path}${sep}umeros_python.exe',
        '${root7.path}${sep}boot${sep}python_vm${sep}build${sep}umeros_python.exe',
        '${root7.path}${sep}boot${sep}python_vm${sep}umeros_python.exe',
      ];
      for (final p in candidates) {
        if (await File(p).exists()) {
          _interpreterPath = p;
          _interpreterAvailable = true;
          _addLog(LogEntry.info('Interpreter found: $p'));
          return;
        }
      }
      _interpreterPath = 'umeros_python.exe';
      _interpreterAvailable = false;
      _addLog(LogEntry.warning(
          'Interpreter not found — running in model-only mode'));
    } catch (e) {
      _interpreterPath = 'umeros_python.exe';
      _interpreterAvailable = false;
      _addLog(LogEntry.error('Interpreter probe failed: $e'));
    }
  }

  void _seedIRQBypass() {
    _irqBypassPeers.addAll(const [
      IRQBypassPeer(name: 'virtio-net-prod', isProducer: true),
      IRQBypassPeer(name: 'virtio-blk-prod', isProducer: true),
      IRQBypassPeer(name: 'kvm-ioapic-cons', isProducer: false),
      IRQBypassPeer(name: 'vfio-cons', isProducer: false),
    ]);
  }

  // ── VM lifecycle ──────────────────────────────────────────

  Future<VMInstance> createVM({
    required String name,
    int memoryMB = 1024,
    int vcpus = 1,
    String? diskPath,
    String? isoPath,
    bool enableNetwork = true,
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
    // Default: one memory slot covering the whole guest RAM, one vCPU.
    vm.memorySlots.add(MemorySlot(
      slotId: 0,
      guestPhysAddr: 0,
      memorySize: memoryMB * 1024 * 1024,
      userspaceAddr: 0x40000000,
    ));
    vm.vcpus.add(VCPU(id: 0));
    _vms[id] = vm;
    _addLog(LogEntry.info('Created VM "$name" ($id)', vmId: id));
    _notify();
    return vm;
  }

  Future<bool> startVM(String id) async {
    final vm = _vms[id];
    if (vm == null) {
      _addLog(LogEntry.error('VM $id not found'));
      return false;
    }
    if (vm.state != VMState.stopped) {
      _addLog(LogEntry.warning('VM "${vm.config.name}" is not stopped'));
      return false;
    }

    vm.state = VMState.starting;
    vm.startTime = DateTime.now();
    vm.outputLog.clear();
    vm.stats = KVMStats();
    _notify();
    _addLog(LogEntry.info('Starting VM "${vm.config.name}"...', vmId: id));

    // Model the KVM bring-up sequence that virt/kvm performs.
    await Future.delayed(const Duration(milliseconds: 350));
    vm.stats.bump('kvm_create_vm');
    for (final v in vm.vcpus) {
      v.state = 'running';
      vm.stats.bump('kvm_create_vcpu');
    }
    vm.stats.bump('kvm_set_user_memory_region', vm.memorySlots.length);
    vm.stats.bump('kvm_create_irqchip');
    if (vm.config.enableNetwork) {
      vm.stats.bump('virtio_net_init');
    }
    vm.dirtyRing.head = 0;
    vm.dirtyRing.tail = 0;

    if (!_interpreterAvailable) {
      vm.state = VMState.running;
      vm.outputLog.add('[model] VM running (model-only mode; no hypervisor)');
      _addLog(LogEntry.warning(
          'VM "${vm.config.name}" running in model-only mode',
          vmId: id));
    } else {
      vm.state = VMState.running;
      vm.outputLog
          .add('[kvm] VM "${vm.config.name}" running via ${vm.config.vcpus} vCPU(s), ${vm.config.memoryMB} MB');
      _addLog(LogEntry.info(
          'VM "${vm.config.name}" running (PID simulated)',
          vmId: id));
    }
    _notify();
    return true;
  }

  Future<void> pauseVM(String id) async {
    final vm = _vms[id];
    if (vm == null || vm.state != VMState.running) return;
    vm.state = VMState.paused;
    for (final v in vm.vcpus) {
      v.state = 'paused';
    }
    vm.stats.bump('kvm_vcpu_pause');
    _addLog(LogEntry.info('VM "${vm.config.name}" paused', vmId: id));
    _notify();
  }

  Future<void> resumeVM(String id) async {
    final vm = _vms[id];
    if (vm == null || vm.state != VMState.paused) return;
    vm.state = VMState.running;
    for (final v in vm.vcpus) {
      v.state = 'running';
    }
    vm.stats.bump('kvm_vcpu_resume');
    _addLog(LogEntry.info('VM "${vm.config.name}" resumed', vmId: id));
    _notify();
  }

  Future<void> stopVM(String id) async {
    final vm = _vms[id];
    if (vm == null || vm.state == VMState.stopped) return;
    vm.state = VMState.stopping;
    _notify();
    await Future.delayed(const Duration(milliseconds: 250));
    vm.state = VMState.stopped;
    vm.exitCode = 0;
    for (final v in vm.vcpus) {
      v.state = 'created';
    }
    vm.stats.bump('kvm_destroy_vm');
    _addLog(LogEntry.info('VM "${vm.config.name}" stopped', vmId: id));
    _notify();
  }

  Future<void> restartVM(String id) async {
    await stopVM(id);
    await Future.delayed(const Duration(milliseconds: 300));
    await startVM(id);
  }

  Future<void> deleteVM(String id) async {
    final vm = _vms[id];
    if (vm == null) return;
    await stopVM(id);
    _vms.remove(id);
    _addLog(LogEntry.info('Deleted VM "${vm.config.name}" ($id)', vmId: id));
    _notify();
  }

  // ── KVM subsystem mutation ────────────────────────────────

  Future<void> addMemorySlot(String id, {required int sizeMB, required int gpa}) async {
    final vm = _vms[id];
    if (vm == null) return;
    final slot = MemorySlot(
      slotId: vm.memorySlots.length,
      guestPhysAddr: gpa,
      memorySize: sizeMB * 1024 * 1024,
      userspaceAddr: 0x40000000 + vm.totalMemoryBytes,
    );
    vm.memorySlots.add(slot);
    vm.stats.bump('kvm_set_user_memory_region');
    _addLog(LogEntry.info(
        'Added memory slot #${slot.slotId} ($sizeMB MB @ 0x${gpa.toRadixString(16)})',
        vmId: id));
    _notify();
  }

  Future<void> addVCPU(String id) async {
    final vm = _vms[id];
    if (vm == null) return;
    final vcpu = VCPU(id: vm.vcpus.length);
    vm.vcpus.add(vcpu);
    vm.stats.bump('kvm_create_vcpu');
    _addLog(LogEntry.info('Added vCPU #${vcpu.id}', vmId: id));
    _notify();
  }

  Future<void> addIRQRoute(String id, {required int gsi, String chip = 'ioapic', int pin = 0}) async {
    final vm = _vms[id];
    if (vm == null) return;
    vm.irqRouting.add(IRQRoutingEntry(gsi: gsi, chip: chip, pin: pin));
    vm.stats.bump('kvm_irqchip_add_irq_route');
    _addLog(LogEntry.info('Routed GSI $gsi → $chip pin $pin', vmId: id));
    _notify();
  }

  Future<void> toggleDirtyLogging(String id, int slotId) async {
    final vm = _vms[id];
    if (vm == null) return;
    final slot = vm.memorySlots.cast<MemorySlot?>().firstWhere(
          (s) => s!.slotId == slotId,
          orElse: () => null,
        );
    if (slot == null) return;
    slot.dirtyLogging = !slot.dirtyLogging;
    vm.stats.bump('kvm_dirty_log');
    _addLog(LogEntry.info(
        'Dirty logging ${slot.dirtyLogging ? "enabled" : "disabled"} on slot #$slotId',
        vmId: id));
    _notify();
  }

  /// Simulate a page write so the dirty ring advances.
  Future<void> simulateDirtyWrite(String id) async {
    final vm = _vms[id];
    if (vm == null || vm.state != VMState.running) return;
    final pos = (vm.dirtyRing.tail % vm.dirtyRing.size);
    vm.dirtyRing.positions[pos] = (vm.dirtyRing.positions[pos] + 1) % 0xFFFFFF;
    vm.dirtyRing.tail = (vm.dirtyRing.tail + 1) % vm.dirtyRing.size;
    vm.stats.bump('kvm_dirty_ring_write');
    _notify();
  }

  // ── IRQ bypass ────────────────────────────────────────────

  Future<void> connectIRQBypass(String name) async {
    final peer = _irqBypassPeers.cast<IRQBypassPeer?>().firstWhere(
          (p) => p!.name == name,
          orElse: () => null,
        );
    if (peer == null) return;
    peer.connected = true;
    _addLog(LogEntry.info('IRQ-bypass peer connected: $name'));
    _notify();
  }

  Future<void> disconnectIRQBypass(String name) async {
    final peer = _irqBypassPeers.cast<IRQBypassPeer?>().firstWhere(
          (p) => p!.name == name,
          orElse: () => null,
        );
    if (peer == null) return;
    peer.connected = false;
    _addLog(LogEntry.info('IRQ-bypass peer disconnected: $name'));
    _notify();
  }

  // ── Script generation ─────────────────────────────────────

  /// Generate a Python script that exercises virt.kvm for this VM.
  String generatePythonScript(String id) {
    final vm = _vms[id];
    if (vm == null) return '# VM not found';
    final buf = StringBuffer()
      ..writeln('"""UmerOS KVM script for ${vm.config.name}"""')
      ..writeln('from virt.kvm import KVM, MemorySlot, KVMVCPU')
      ..writeln('')
      ..writeln('kvm = KVM()')
      ..writeln('kvm.create_vm("${vm.config.id}")');
    for (final s in vm.memorySlots) {
      buf.writeln(
          'kvm.set_user_memory_region(MemorySlot(${s.slotId}, ${s.guestPhysAddr}, ${s.memorySize}, ${s.userspaceAddr}))');
    }
    for (final v in vm.vcpus) {
      buf.writeln('kvm.create_vcpu(KVMVCPU(${v.id}))');
    }
    buf.writeln('kvm.create_irqchip()');
    for (final r in vm.irqRouting) {
      buf.writeln('kvm.irqchip_add_irq_route(${r.gsi}, "${r.chip}", ${r.pin})');
    }
    buf.writeln('kvm.run()');
    return buf.toString();
  }

  // ── Internals ─────────────────────────────────────────────

  void _addLog(LogEntry entry) {
    _log.add(entry);
    if (_log.length > 500) _log.removeRange(0, _log.length - 500);
    if (!_logController.isClosed) _logController.add(entry);
  }

  void _notify() {
    if (!_vmsController.isClosed) _vmsController.add(null);
  }

  void dispose() {
    _vmsController.close();
    _logController.close();
  }
}