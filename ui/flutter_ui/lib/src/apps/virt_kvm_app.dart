/// UmerOS Flutter UI — Virt / KVM Manager
/// =====================================================
/// Desktop control panel for the UmerOS KVM subsystem
/// (the Dart twin of the Python `virt/kvm` + `virt/lib`
/// ports).  HCI principles applied:
///   * Nielsen #2  — plain, task-oriented labels
///   * Nielsen #6  — recognition over recall: live status,
///                   icons and colour cues everywhere
///   * Nielsen #3  — user control: start / pause / resume /
///                   stop / delete with an undo-safe log
///   * Nielsen #4  — consistency: shares the tab-card
///                   vocabulary used by Boot Manager etc.
///   * Nielsen #5  — error prevention: destructive actions
///                   ask for confirmation, invalid actions
///                   are disabled
///   * Nielsen #7  — flexibility: quick actions + detail
///                   inspection
///   * Nielsen #8  — aesthetic & minimalist: one concern
///                   per tab, no decoration for decoration
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../services/kvm_service.dart';
import '../widgets/auto_adjust_box.dart';

class VirtKvmApp extends StatefulWidget {
  const VirtKvmApp({super.key});

  @override
  State<VirtKvmApp> createState() => _VirtKvmAppState();
}

class _VirtKvmAppState extends State<VirtKvmApp> {
  int _tab = 0;
  String? _selectedVmId;

  @override
  void initState() {
    super.initState();
    // Ensure the service is alive and probed once.
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final svc = KVMService.instance;
      if (svc.vms.isEmpty && !svc.interpreterAvailable) {
        // first run — probe the interpreter lazily
        await svc.init();
        if (mounted) setState(() {});
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<void>(
      stream: KVMService.instance.vmsStream,
      builder: (context, _) {
        final svc = KVMService.instance;
        final vmList = svc.vms.values.toList()
          ..sort((a, b) => a.config.name.compareTo(b.config.name));
        if (_selectedVmId != null && !svc.vms.containsKey(_selectedVmId)) {
          _selectedVmId = vmList.isNotEmpty ? vmList.first.config.id : null;
        }
        return Column(
          children: [
            _buildHeader(svc),
            _buildTabBar(),
            Expanded(
              child: _buildBody(svc, vmList),
            ),
          ],
        );
      },
    );
  }

  // ── Header ────────────────────────────────────────────

  Widget _buildHeader(KVMService svc) {
    final scheme = Theme.of(context).colorScheme;
    final running = svc.vms.values.where((v) => v.state == VMState.running).length;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: scheme.surface,
        border: Border(
          bottom: BorderSide(color: scheme.outline.withValues(alpha: 0.2)),
        ),
      ),
      child: AutoAdjustRow(
        spacing: 16,
        children: [
          _StatChip(
            icon: Icons.memory,
            label: 'VMs',
            value: '${svc.vms.length}',
            color: Colors.teal,
          ),
          _StatChip(
            icon: Icons.play_circle,
            label: 'Running',
            value: '$running',
            color: Colors.green,
          ),
          _StatChip(
            icon: Icons.hub,
            label: 'IRQ bypass',
            value: '${svc.irqBypassPeers.length}',
            color: Colors.deepPurple,
          ),
          const Spacer(),
          FilledButton.tonalIcon(
            onPressed: () => _showCreateVMDialog(svc),
            icon: const Icon(Icons.add, size: 18),
            label: const Text('New VM'),
          ),
        ],
      ),
    );
  }

  // ── Tab bar ───────────────────────────────────────────

  Widget _buildTabBar() {
    final tabs = const [
      'Virtual Machines',
      'Memory & vCPUs',
      'IRQ Routing',
      'KVM Stats',
      'IRQ Bypass',
      'Activity Log',
    ];
    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.2),
          ),
        ),
      ),
      child: AutoAdjustRow(
        spacing: 0,
        children: [
          for (var i = 0; i < tabs.length; i++)
            _TabButton(
              label: tabs[i],
              isSelected: _tab == i,
              onTap: () => setState(() => _tab = i),
            ),
        ],
      ),
    );
  }

  // ── Body ──────────────────────────────────────────────

  Widget _buildBody(KVMService svc, List<VMInstance> vmList) {
    return switch (_tab) {
      0 => _buildVMListTab(svc, vmList),
      1 => _buildMemoryTab(svc),
      2 => _buildIRQTab(svc),
      3 => _buildStatsTab(svc),
      4 => _buildBypassTab(svc),
      _ => _buildLogTab(svc),
    };
  }

  // ── Tab 1: VM list ────────────────────────────────────

  Widget _buildVMListTab(KVMService svc, List<VMInstance> vmList) {
    if (vmList.isEmpty) {
      return Center(
        child: AutoAdjustBox(
          maxWidth: 420,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.memory_outlined, size: 64, color: Colors.teal.shade200),
              const SizedBox(height: 16),
              Text(
                'No virtual machines yet',
                style: GoogleFonts.inter(
                    fontSize: 18, fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 8),
              Text(
                'Create a VM to model the KVM subsystem — memory slots, vCPUs, IRQ routing and stats.',
                textAlign: TextAlign.center,
                style: GoogleFonts.inter(fontSize: 13, color: Colors.grey),
              ),
              const SizedBox(height: 16),
              FilledButton.tonalIcon(
                onPressed: () => _showCreateVMDialog(svc),
                icon: const Icon(Icons.add),
                label: const Text('Create your first VM'),
              ),
            ],
          ),
        ),
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: vmList.length,
      separatorBuilder: (_, _) => const SizedBox(height: 12),
      itemBuilder: (context, index) {
        final vm = vmList[index];
        final selected = vm.config.id == _selectedVmId;
        return _VMCard(
          vm: vm,
          selected: selected,
          onSelect: () => setState(() => _selectedVmId = vm.config.id),
          onStart: () => svc.startVM(vm.config.id),
          onPause: () => svc.pauseVM(vm.config.id),
          onResume: () => svc.resumeVM(vm.config.id),
          onStop: () => svc.stopVM(vm.config.id),
          onRestart: () => svc.restartVM(vm.config.id),
          onDelete: () => _confirmDelete(svc, vm),
        );
      },
    );
  }

  // ── Tab 2: Memory & vCPUs ─────────────────────────────

  Widget _buildMemoryTab(KVMService svc) {
    final vm = _selected(svc);
    if (vm == null) return _noSelection();
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SectionTitle(
            title: 'Guest memory slots',
            trailing: FilledButton.tonalIcon(
              onPressed: () => _showAddMemoryDialog(svc, vm),
              icon: const Icon(Icons.add, size: 16),
              label: const Text('Add slot'),
            ),
          ),
          const SizedBox(height: 8),
          if (vm.memorySlots.isEmpty)
            const _EmptyNote(text: 'No memory slots — add one to map guest RAM.'),
          for (final slot in vm.memorySlots)
            _MemorySlotTile(
              slot: slot,
              onToggleDirty: () => svc.toggleDirtyLogging(vm.config.id, slot.slotId),
            ),
          const SizedBox(height: 24),
          _SectionTitle(
            title: 'Virtual CPUs',
            trailing: FilledButton.tonalIcon(
              onPressed: () => svc.addVCPU(vm.config.id),
              icon: const Icon(Icons.add, size: 16),
              label: const Text('Add vCPU'),
            ),
          ),
          const SizedBox(height: 8),
          if (vm.vcpus.isEmpty) const _EmptyNote(text: 'No vCPUs.'),
          for (final vcpu in vm.vcpus) _VCPUTile(vcpu: vcpu),
          const SizedBox(height: 24),
          _SectionTitle(title: 'Dirty ring'),
          const SizedBox(height: 8),
          _DirtyRingCard(
            ring: vm.dirtyRing,
            onSimulate: vm.state == VMState.running
                ? () => svc.simulateDirtyWrite(vm.config.id)
                : null,
          ),
        ],
      ),
    );
  }

  // ── Tab 3: IRQ routing ────────────────────────────────

  Widget _buildIRQTab(KVMService svc) {
    final vm = _selected(svc);
    if (vm == null) return _noSelection();
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SectionTitle(
            title: 'IRQ routing table (GSI → chip pin)',
            trailing: FilledButton.tonalIcon(
              onPressed: () => _showAddIRQDialog(svc, vm),
              icon: const Icon(Icons.add, size: 16),
              label: const Text('Add route'),
            ),
          ),
          const SizedBox(height: 8),
          if (vm.irqRouting.isEmpty)
            const _EmptyNote(text: 'No IRQ routes — create an IRQ chip and add routes.'),
          for (final r in vm.irqRouting) _IRQRouteTile(route: r),
          const SizedBox(height: 24),
          _InfoCard(
            title: 'About IRQ routing',
            body:
                'KVM exposes a routing table that maps a Guest Source ID (GSI) to '
                'a pin on either the legacy PIC or the IOAPIC. Add a route to '
                'wire a virtual device interrupt to a guest-visible IRQ line.',
          ),
        ],
      ),
    );
  }

  // ── Tab 4: KVM stats ──────────────────────────────────

  Widget _buildStatsTab(KVMService svc) {
    final vm = _selected(svc);
    if (vm == null) return _noSelection();
    final counters = vm.stats.counters.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SectionTitle(title: 'KVM statistics counters'),
          const SizedBox(height: 8),
          if (counters.isEmpty)
            const _EmptyNote(text: 'No counters yet — start the VM to record KVM ioctl activity.'),
          if (counters.isNotEmpty)
            LayoutBuilder(
              builder: (context, constraints) {
          final cols = constraints.maxWidth > 640 ? 3 : 2;
          return GridView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: cols,
                    mainAxisSpacing: 10,
                    crossAxisSpacing: 10,
                    childAspectRatio: 2.4,
                  ),
                  itemCount: counters.length,
                  itemBuilder: (context, i) {
                    final e = counters[i];
                    return _StatCard(name: e.key, value: e.value);
                  },
                );
              },
            ),
          const SizedBox(height: 24),
          _SectionTitle(title: 'Coalesced MMIO'),
          const SizedBox(height: 8),
          _CoalescedMMCard(mmio: vm.coalescedMMIO),
        ],
      ),
    );
  }

  // ── Tab 5: IRQ bypass ─────────────────────────────────

  Widget _buildBypassTab(KVMService svc) {
    final producers = svc.irqBypassPeers.where((p) => p.isProducer).toList();
    final consumers = svc.irqBypassPeers.where((p) => !p.isProducer).toList();
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SectionTitle(title: 'IRQ bypass — producers'),
          const SizedBox(height: 8),
          for (final p in producers)
            _BypassPeerTile(
              peer: p,
              onConnect: p.connected ? null : () => svc.connectIRQBypass(p.name),
              onDisconnect: p.connected ? () => svc.disconnectIRQBypass(p.name) : null,
            ),
          const SizedBox(height: 24),
          _SectionTitle(title: 'IRQ bypass — consumers'),
          const SizedBox(height: 8),
          for (final p in consumers)
            _BypassPeerTile(
              peer: p,
              onConnect: p.connected ? null : () => svc.connectIRQBypass(p.name),
              onDisconnect: p.connected ? () => svc.disconnectIRQBypass(p.name) : null,
            ),
          const SizedBox(height: 24),
          _InfoCard(
            title: 'About IRQ bypass',
            body:
                'The IRQ-bypass framework (virt/lib) lets producers such as '
                'virtio devices signal consumers (KVM IOAPIC, VFIO) without a '
                'kernel round-trip. Connect a producer to a consumer to '
                'establish a direct eventfd link.',
          ),
        ],
      ),
    );
  }

  // ── Tab 6: Log ────────────────────────────────────────

  Widget _buildLogTab(KVMService svc) {
    final log = svc.log;
    if (log.isEmpty) {
      return const Center(child: _EmptyNote(text: 'No activity yet.'));
    }
    return StreamBuilder<LogEntry>(
      stream: svc.logStream,
      builder: (context, snap) {
        final entries = svc.log;
        return ListView.separated(
          padding: const EdgeInsets.all(12),
          reverse: false,
          itemCount: entries.length,
          separatorBuilder: (_, _) => const SizedBox(height: 2),
          itemBuilder: (context, i) {
            final e = entries[i];
            return _LogTile(entry: e);
          },
        );
      },
    );
  }

  // ── Helpers ───────────────────────────────────────────

  VMInstance? _selected(KVMService svc) {
    final id = _selectedVmId;
    if (id == null) return null;
    return svc.vms[id];
  }

  Widget _noSelection() {
    return const Center(
      child: _EmptyNote(
          text: 'Select a virtual machine from the "Virtual Machines" tab first.'),
    );
  }

  Future<void> _showCreateVMDialog(KVMService svc) async {
    final nameCtrl = TextEditingController(text: 'my-vm');
    final memCtrl = TextEditingController(text: '1024');
    final vcpuCtrl = TextEditingController(text: '1');
    var network = true;
    final result = await showDialog<bool>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setLocal) {
            return AlertDialog(
              title: const Text('Create virtual machine'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _DialogLabel('Name'),
                    TextField(controller: nameCtrl),
                    const SizedBox(height: 12),
                    _DialogLabel('Memory (MB)'),
                    TextField(
                      controller: memCtrl,
                      keyboardType: TextInputType.number,
                    ),
                    const SizedBox(height: 12),
                    _DialogLabel('vCPUs'),
                    TextField(
                      controller: vcpuCtrl,
                      keyboardType: TextInputType.number,
                    ),
                    const SizedBox(height: 12),
                    SwitchListTile(
                      title: const Text('Enable network'),
                      value: network,
                      onChanged: (v) => setLocal(() => network = v),
                      contentPadding: EdgeInsets.zero,
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context, false),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: () => Navigator.pop(context, true),
                  child: const Text('Create'),
                ),
              ],
            );
          },
        );
      },
    );
    if (result == true) {
      final name = nameCtrl.text.trim();
      if (name.isEmpty) {
        _toast('VM name cannot be empty');
        return;
      }
      final mem = int.tryParse(memCtrl.text) ?? 1024;
      final vcpus = int.tryParse(vcpuCtrl.text) ?? 1;
      await svc.createVM(
        name: name,
        memoryMB: mem.clamp(16, 65536),
        vcpus: vcpus.clamp(1, 255),
        enableNetwork: network,
      );
      if (mounted) setState(() {});
    }
  }

  Future<void> _showAddMemoryDialog(KVMService svc, VMInstance vm) async {
    final sizeCtrl = TextEditingController(text: '512');
    final gpaCtrl = TextEditingController(
        text: '0x${(vm.totalMemoryBytes).toRadixString(16)}');
    final result = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Add guest memory slot'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const _DialogLabel('Size (MB)'),
            TextField(controller: sizeCtrl, keyboardType: TextInputType.number),
            const SizedBox(height: 12),
            const _DialogLabel('Guest physical address'),
            TextField(controller: gpaCtrl),
          ],
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Add')),
        ],
      ),
    );
    if (result == true) {
      final size = int.tryParse(sizeCtrl.text) ?? 512;
      final gpa = int.tryParse(gpaCtrl.text.replaceFirst('0x', ''), radix: 16) ??
          vm.totalMemoryBytes;
      await svc.addMemorySlot(vm.config.id, sizeMB: size, gpa: gpa);
      if (mounted) setState(() {});
    }
  }

  Future<void> _showAddIRQDialog(KVMService svc, VMInstance vm) async {
    final gsiCtrl = TextEditingController(text: '0');
    var chip = 'ioapic';
    final pinCtrl = TextEditingController(text: '0');
    final result = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setLocal) => AlertDialog(
          title: const Text('Add IRQ route'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const _DialogLabel('GSI'),
              TextField(controller: gsiCtrl, keyboardType: TextInputType.number),
              const SizedBox(height: 12),
              const _DialogLabel('IRQ chip'),
              DropdownButton<String>(
                value: chip,
                items: const [
                  DropdownMenuItem(value: 'ioapic', child: Text('IOAPIC')),
                  DropdownMenuItem(value: 'pic', child: Text('PIC')),
                ],
                onChanged: (v) => setLocal(() => chip = v ?? 'ioapic'),
              ),
              const SizedBox(height: 12),
              const _DialogLabel('Pin'),
              TextField(controller: pinCtrl, keyboardType: TextInputType.number),
            ],
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Cancel')),
            FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Add')),
          ],
        ),
      ),
    );
    if (result == true) {
      final gsi = int.tryParse(gsiCtrl.text) ?? 0;
      final pin = int.tryParse(pinCtrl.text) ?? 0;
      await svc.addIRQRoute(vm.config.id, gsi: gsi, chip: chip, pin: pin);
      if (mounted) setState(() {});
    }
  }

  Future<void> _confirmDelete(KVMService svc, VMInstance vm) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Delete "${vm.config.name}"?'),
        content: const Text('This removes the VM and its KVM state. This cannot be undone.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Colors.red,
            ),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (ok == true) {
      await svc.deleteVM(vm.config.id);
      if (mounted) setState(() {});
    }
  }

  void _toast(String msg) {
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(msg)));
  }
}

// ── Reusable pieces ───────────────────────────────────────

class _TabButton extends StatelessWidget {
  final String label;
  final bool isSelected;
  final VoidCallback onTap;
  const _TabButton({
    required this.label,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return InkWell(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(
              width: 2,
              color: isSelected ? scheme.primary : Colors.transparent,
            ),
          ),
        ),
        child: Text(
          label,
          style: GoogleFonts.inter(
            fontSize: 13,
            fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
            color: isSelected ? scheme.primary : scheme.onSurfaceVariant,
          ),
        ),
      ),
    );
  }
}

class _StatChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;
  const _StatChip({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 18, color: color),
          const SizedBox(width: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(value,
                  style: GoogleFonts.inter(
                      fontSize: 15, fontWeight: FontWeight.w700)),
              Text(label,
                  style: GoogleFonts.inter(
                      fontSize: 11, color: Colors.grey.shade600)),
            ],
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String title;
  final Widget? trailing;
  const _SectionTitle({required this.title, this.trailing});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(
            title,
            style: GoogleFonts.inter(
                fontSize: 15, fontWeight: FontWeight.w600),
          ),
        ),
        ?trailing,
      ],
    );
  }
}

class _EmptyNote extends StatelessWidget {
  final String text;
  const _EmptyNote({required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(text,
          style: GoogleFonts.inter(fontSize: 13, color: Colors.grey.shade700)),
    );
  }
}

class _DialogLabel extends StatelessWidget {
  final String text;
  const _DialogLabel(this.text);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Text(text,
          style: GoogleFonts.inter(
              fontSize: 12, fontWeight: FontWeight.w600, color: Colors.grey)),
    );
  }
}

class _InfoCard extends StatelessWidget {
  final String title;
  final String body;
  const _InfoCard({required this.title, required this.body});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.blue.shade50,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.blue.shade100),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: GoogleFonts.inter(
                  fontSize: 13, fontWeight: FontWeight.w600, color: Colors.blue.shade900)),
          const SizedBox(height: 4),
          Text(body,
              style: GoogleFonts.inter(
                  fontSize: 12, color: Colors.blue.shade800, height: 1.4)),
        ],
      ),
    );
  }
}

// ── VM card ─────────────────────────────────────────────

class _VMCard extends StatelessWidget {
  final VMInstance vm;
  final bool selected;
  final VoidCallback onSelect;
  final VoidCallback onStart;
  final VoidCallback onPause;
  final VoidCallback onResume;
  final VoidCallback onStop;
  final VoidCallback onRestart;
  final VoidCallback onDelete;

  const _VMCard({
    required this.vm,
    required this.selected,
    required this.onSelect,
    required this.onStart,
    required this.onPause,
    required this.onResume,
    required this.onStop,
    required this.onRestart,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final (stateColor, stateLabel) = switch (vm.state) {
      VMState.running => (Colors.green, 'Running'),
      VMState.paused => (Colors.orange, 'Paused'),
      VMState.starting ||
      VMState.stopping =>
        (Colors.blue, 'Working…'),
      VMState.error => (Colors.red, 'Error'),
      VMState.stopped => (Colors.grey, 'Stopped'),
    };
    return Card(
      elevation: selected ? 2 : 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: selected ? scheme.primary : scheme.outline.withValues(alpha: 0.25),
          width: selected ? 1.6 : 1,
        ),
      ),
      child: InkWell(
        onTap: onSelect,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.memory, color: scheme.primary),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(vm.config.name,
                            style: GoogleFonts.inter(
                                fontSize: 15, fontWeight: FontWeight.w600)),
                        Text(vm.config.id,
                            style: GoogleFonts.inter(
                                fontSize: 11, color: Colors.grey)),
                      ],
                    ),
                  ),
                  _StateBadge(color: stateColor, label: stateLabel),
                ],
              ),
              const SizedBox(height: 12),
              AutoAdjustRow(
                spacing: 8,
                children: [
                  _MiniStat(label: 'Memory', value: '${vm.config.memoryMB} MB'),
                  _MiniStat(label: 'vCPUs', value: '${vm.vcpus.length}'),
                  _MiniStat(label: 'Slots', value: '${vm.memorySlots.length}'),
                  _MiniStat(label: 'IRQ', value: '${vm.irqRouting.length}'),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  if (vm.state == VMState.stopped)
                    _ActionBtn(
                      label: 'Start',
                      icon: Icons.play_arrow,
                      onTap: onStart,
                      color: Colors.green,
                    ),
                  if (vm.state == VMState.running) ...[
                    _ActionBtn(
                      label: 'Pause',
                      icon: Icons.pause,
                      onTap: onPause,
                      color: Colors.orange,
                    ),
                    _ActionBtn(
                      label: 'Stop',
                      icon: Icons.stop,
                      onTap: onStop,
                      color: Colors.red,
                    ),
                  ],
                  if (vm.state == VMState.paused) ...[
                    _ActionBtn(
                      label: 'Resume',
                      icon: Icons.play_arrow,
                      onTap: onResume,
                      color: Colors.green,
                    ),
                    _ActionBtn(
                      label: 'Stop',
                      icon: Icons.stop,
                      onTap: onStop,
                      color: Colors.red,
                    ),
                  ],
                  if (vm.state != VMState.starting &&
                      vm.state != VMState.stopping)
                    _ActionBtn(
                      label: 'Restart',
                      icon: Icons.restart_alt,
                      onTap: onRestart,
                      color: Colors.blue,
                    ),
                  const Spacer(),
                  IconButton(
                    onPressed: onDelete,
                    icon: const Icon(Icons.delete_outline, color: Colors.red),
                    tooltip: 'Delete VM',
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StateBadge extends StatelessWidget {
  final Color color;
  final String label;
  const _StateBadge({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Text(label,
              style: GoogleFonts.inter(
                  fontSize: 12, fontWeight: FontWeight.w600, color: color)),
        ],
      ),
    );
  }
}

class _MiniStat extends StatelessWidget {
  final String label;
  final String value;
  const _MiniStat({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('$label: ',
              style: GoogleFonts.inter(fontSize: 11, color: Colors.grey.shade700)),
          Text(value,
              style: GoogleFonts.inter(
                  fontSize: 11, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}

class _ActionBtn extends StatelessWidget {
  final String label;
  final IconData icon;
  final VoidCallback onTap;
  final Color color;
  const _ActionBtn({
    required this.label,
    required this.icon,
    required this.onTap,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 6),
      child: OutlinedButton.icon(
        onPressed: onTap,
        icon: Icon(icon, size: 15, color: color),
        label: Text(label,
            style: GoogleFonts.inter(fontSize: 12, color: color)),
        style: OutlinedButton.styleFrom(
          foregroundColor: color,
          side: BorderSide(color: color.withValues(alpha: 0.5)),
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        ),
      ),
    );
  }
}

// ── Memory & vCPU tiles ─────────────────────────────────

class _MemorySlotTile extends StatelessWidget {
  final MemorySlot slot;
  final VoidCallback onToggleDirty;
  const _MemorySlotTile({required this.slot, required this.onToggleDirty});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: ListTile(
        leading: Icon(Icons.memory, color: Colors.teal),
        title: Text('Slot #${slot.slotId} — ${slot.sizeMB}',
            style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('GPA ${slot.gpaHex} · ${slot.memorySize} bytes · userspace 0x${slot.userspaceAddr.toRadixString(16)}'),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('dirty log',
                style: GoogleFonts.inter(fontSize: 11, color: Colors.grey)),
            Switch(
              value: slot.dirtyLogging,
              onChanged: (_) => onToggleDirty(),
            ),
          ],
        ),
      ),
    );
  }
}

class _VCPUTile extends StatelessWidget {
  final VCPU vcpu;
  const _VCPUTile({required this.vcpu});

  @override
  Widget build(BuildContext context) {
    final color = vcpu.state == 'running'
        ? Colors.green
        : vcpu.state == 'paused'
            ? Colors.orange
            : Colors.grey;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: ListTile(
        leading: Icon(Icons.hardware, color: color),
        title: Text('vCPU #${vcpu.id}',
            style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('State: ${vcpu.state}'),
        trailing: Icon(Icons.circle, size: 12, color: color),
      ),
    );
  }
}

class _DirtyRingCard extends StatelessWidget {
  final DirtyRingState ring;
  final VoidCallback? onSimulate;
  const _DirtyRingCard({required this.ring, this.onSimulate});

  @override
  Widget build(BuildContext context) {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            Icon(Icons.bubble_chart, color: Colors.indigo),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Capacity ${ring.size} · head ${ring.head} · tail ${ring.tail}',
                      style: GoogleFonts.inter(fontSize: 13)),
                  Text('${ring.count} pending dirty pages',
                      style: GoogleFonts.inter(fontSize: 12, color: Colors.grey)),
                ],
              ),
            ),
            if (onSimulate != null)
              FilledButton.tonalIcon(
                onPressed: onSimulate,
                icon: const Icon(Icons.touch_app, size: 15),
                label: const Text('Simulate write'),
              ),
          ],
        ),
      ),
    );
  }
}

// ── IRQ routing tile ────────────────────────────────────

class _IRQRouteTile extends StatelessWidget {
  final IRQRoutingEntry route;
  const _IRQRouteTile({required this.route});

  @override
  Widget build(BuildContext context) {
    final color = route.chip == 'ioapic' ? Colors.deepPurple : Colors.brown;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: ListTile(
        leading: Icon(Icons.call_split, color: color),
        title: Text('GSI ${route.gsi} → ${route.chip.toUpperCase()} pin ${route.pin}',
            style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('Guest interrupt ${route.gsi} delivered to ${route.chip} line ${route.pin}'),
        trailing: Icon(Icons.check_circle, size: 16, color: color),
      ),
    );
  }
}

// ── Stats cards ─────────────────────────────────────────

class _StatCard extends StatelessWidget {
  final String name;
  final int value;
  const _StatCard({required this.name, required this.value});

  @override
  Widget build(BuildContext context) {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(name,
                style: GoogleFonts.inter(
                    fontSize: 11, color: Colors.grey.shade700),
                maxLines: 1,
                overflow: TextOverflow.ellipsis),
            Text('$value',
                style: GoogleFonts.inter(
                    fontSize: 18, fontWeight: FontWeight.w700)),
          ],
        ),
      ),
    );
  }
}

class _CoalescedMMCard extends StatelessWidget {
  final CoalescedMMIOState mmio;
  const _CoalescedMMCard({required this.mmio});

  @override
  Widget build(BuildContext context) {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            Icon(Icons.merge_type, color: Colors.orange.shade700),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Capacity ${mmio.capacity} · ${mmio.pending} pending',
                      style: GoogleFonts.inter(fontSize: 13)),
                  Text('MMIO writes are batched to reduce VM exits.',
                      style: GoogleFonts.inter(fontSize: 12, color: Colors.grey)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── IRQ bypass tile ─────────────────────────────────────

class _BypassPeerTile extends StatelessWidget {
  final IRQBypassPeer peer;
  final VoidCallback? onConnect;
  final VoidCallback? onDisconnect;
  const _BypassPeerTile({
    required this.peer,
    this.onConnect,
    this.onDisconnect,
  });

  @override
  Widget build(BuildContext context) {
    final color = peer.isProducer ? Colors.deepPurple : Colors.teal;
    final role = peer.isProducer ? 'Producer' : 'Consumer';
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: ListTile(
        leading: Icon(
          peer.isProducer ? Icons.output : Icons.input,
          color: color,
        ),
        title: Text(peer.name,
            style: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 13)),
        subtitle: Text('$role · ${peer.connected ? "connected" : "idle"}'),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (peer.connected)
              Icon(Icons.link, size: 16, color: Colors.green),
            const SizedBox(width: 8),
            if (onConnect != null)
              FilledButton.tonal(
                onPressed: onConnect,
                style: FilledButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                ),
                child: const Text('Connect', style: TextStyle(fontSize: 12)),
              ),
            if (onDisconnect != null)
              OutlinedButton(
                onPressed: onDisconnect,
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                ),
                child: const Text('Disconnect', style: TextStyle(fontSize: 12)),
              ),
          ],
        ),
      ),
    );
  }
}

// ── Log tile ────────────────────────────────────────────

class _LogTile extends StatelessWidget {
  final LogEntry entry;
  const _LogTile({required this.entry});

  @override
  Widget build(BuildContext context) {
    final color = switch (entry.type) {
      LogType.info => Colors.blue,
      LogType.warning => Colors.orange,
      LogType.error => Colors.red,
      LogType.output => Colors.green,
      LogType.input => Colors.teal,
    };
    final time =
        '${entry.timestamp.hour.toString().padLeft(2, '0')}:${entry.timestamp.minute.toString().padLeft(2, '0')}:${entry.timestamp.second.toString().padLeft(2, '0')}';
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('$time ',
              style: GoogleFonts.firaCode(fontSize: 11, color: Colors.grey)),
          SizedBox(
            width: 46,
            child: Text(entry.label,
                style: GoogleFonts.firaCode(
                    fontSize: 11, color: color, fontWeight: FontWeight.w700)),
          ),
          const SizedBox(width: 4),
          Expanded(
            child: Text(entry.message,
                style: GoogleFonts.firaCode(fontSize: 11, height: 1.4)),
          ),
        ],
      ),
    );
  }
}