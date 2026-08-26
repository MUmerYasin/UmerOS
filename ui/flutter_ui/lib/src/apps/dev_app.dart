import 'package:flutter/material.dart';
import '../widgets/auto_adjust_box.dart';
import 'dev_models.dart';

enum _Section { overview, browse, tree, modern, terminal, fhs }

class DevApp extends StatefulWidget {
  const DevApp({super.key});

  @override
  State<DevApp> createState() => _DevAppState();
}

class _DevAppState extends State<DevApp> {
  _Section _section = _Section.overview;
  DevType? _typeFilter;
  String _searchQuery = '';

  final TextEditingController _cmdController =
      TextEditingController(text: 'udevadm info /dev/null');
  final ScrollController _consoleScroll = ScrollController();
  final List<UdevResult> _history = [];

  static const _quickCommands = [
    'udevadm info /dev/null',
    'udevadm monitor',
    'udevadm settle',
    'udevadm test /dev/tty',
    'mknod --help',
  ];

  @override
  void dispose() {
    _cmdController.dispose();
    _consoleScroll.dispose();
    super.dispose();
  }

  List<DeviceNodeModel> get _filtered {
    return DevService.nodes.where((n) {
      final matchType = _typeFilter == null || n.devType == _typeFilter;
      final q = _searchQuery.toLowerCase();
      final matchQ = q.isEmpty ||
          n.name.toLowerCase().contains(q) ||
          n.path.toLowerCase().contains(q) ||
          n.description.toLowerCase().contains(q);
      return matchType && matchQ;
    }).toList();
  }

  void _runCommand([String? raw]) {
    final text = (raw ?? _cmdController.text).trim();
    if (text.isEmpty) return;
    if (raw != null) _cmdController.text = raw;
    final parts = text.split(RegExp(r'\s+'));
    final tool = parts.first;
    final rest = parts.sublist(1);
    setState(() {
      _history.add(
          tool == 'mknod' ? DevService.mknod(rest) : DevService.udevadm(rest));
      if (_history.length > 80) _history.removeAt(0);
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
        border:
            Border(bottom: BorderSide(color: colorScheme.outline.withValues(alpha: 0.2))),
      ),
      child: AutoAdjustRow(
        spacing: 12,
        children: [
          Icon(Icons.developer_board, color: colorScheme.primary, size: 28),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Device Manager',
                  style: textTheme.titleLarge
                      ?.copyWith(fontWeight: FontWeight.bold, color: colorScheme.onSurface)),
              Text('/dev hierarchy · devtmpfs · udevadm',
                  style: textTheme.bodySmall
                      ?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6))),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSidebar(ColorScheme colorScheme, TextTheme textTheme) {
    final stats = DevService.statistics();
    return Container(
      width: 200,
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
        border:
            Border(right: BorderSide(color: colorScheme.outline.withValues(alpha: 0.2))),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Text('Sections',
                style: textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: colorScheme.onSurface.withValues(alpha: 0.7))),
          ),
          _navTile('Overview', Icons.dashboard_outlined, _Section.overview, colorScheme),
          _navTile('Browse Nodes', Icons.apps_outlined, _Section.browse, colorScheme),
          _navTile('Device Tree', Icons.account_tree_outlined, _Section.tree, colorScheme),
          _navTile('Modern Tech', Icons.auto_awesome, _Section.modern, colorScheme),
          _navTile('Udevadm Shell', Icons.terminal_outlined, _Section.terminal, colorScheme),
          _navTile('FHS Map', Icons.fact_check_outlined, _Section.fhs, colorScheme),
          const Spacer(),
          Container(
            margin: const EdgeInsets.all(16),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: colorScheme.primaryContainer.withValues(alpha: 0.35),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Icon(Icons.verified_outlined, size: 14, color: Colors.green.shade700),
                const SizedBox(width: 6),
                Flexible(
                  child: Text('devtmpfs populated',
                      style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: colorScheme.onPrimaryContainer)),
                ),
              ]),
              const SizedBox(height: 4),
              Text('${stats['total']} nodes · ${stats['groups']} groups',
                  style: TextStyle(
                      fontSize: 11,
                      color: colorScheme.onPrimaryContainer.withValues(alpha: 0.8))),
            ]),
          ),
        ],
      ),
    );
  }

  Widget _navTile(String label, IconData icon, _Section section, ColorScheme colorScheme) {
    final selected = _section == section;
    return ListTile(
      leading: Icon(icon, size: 20,
          color: selected ? colorScheme.primary : colorScheme.onSurface.withValues(alpha: 0.7)),
      title: Text(label,
          style: TextStyle(
              fontSize: 13,
              color: selected ? colorScheme.primary : colorScheme.onSurface,
              fontWeight: selected ? FontWeight.w600 : FontWeight.normal)),
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
      case _Section.browse:
        return _buildBrowse(colorScheme, textTheme);
      case _Section.tree:
        return _buildTree(colorScheme, textTheme);
      case _Section.modern:
        return _buildModern(colorScheme, textTheme);
      case _Section.terminal:
        return _buildTerminal(colorScheme, textTheme);
      case _Section.fhs:
        return _buildFhs(colorScheme, textTheme);
    }
  }

  Widget _statCard(String label, String value, IconData icon, Color color,
      TextTheme textTheme, ColorScheme colorScheme) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.18),
                  borderRadius: BorderRadius.circular(9)),
              child: Icon(icon, size: 17, color: color),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerRight,
                child: Text(value,
                    style: textTheme.titleLarge
                        ?.copyWith(fontWeight: FontWeight.w700, color: colorScheme.onSurface)),
              ),
            ),
          ]),
          const SizedBox(height: 8),
          Text(label,
              style: textTheme.bodySmall
                  ?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6)),
              maxLines: 1,
              overflow: TextOverflow.ellipsis),
        ],
      ),
    );
  }

  Widget _buildOverview(ColorScheme colorScheme, TextTheme textTheme) {
    final stats = DevService.statistics();
    final total = stats['total'] as int;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        LayoutBuilder(builder: (context, constraints) {
          const gap = 12.0;
          final w = constraints.maxWidth;
          final cols = w < 480 ? 1 : (w < 760 ? 2 : 4);
          final items = <Widget>[
            _statCard('Registered nodes', '$total', Icons.developer_board,
                colorScheme.primary, textTheme, colorScheme),
            _statCard('Character devices', '${stats[DevType.char.name]}',
                Icons.memory_outlined, DevService.typeColors[DevType.char]!, textTheme, colorScheme),
            _statCard('Block devices', '${stats[DevType.block.name]}',
                Icons.storage_outlined, DevService.typeColors[DevType.block]!, textTheme, colorScheme),
            _statCard('Links & dirs',
                '${(stats[DevType.symlink.name] ?? 0) + (stats[DevType.directory.name] ?? 0)}',
                Icons.link, DevService.typeColors[DevType.symlink]!, textTheme, colorScheme),
          ];
          final rows = <List<Widget>>[];
          for (var i = 0; i < items.length; i += cols) {
            rows.add(items.sublist(i, (i + cols).clamp(0, items.length)));
          }
          return Column(children: [
            for (final row in rows)
              Padding(
                padding: const EdgeInsets.only(bottom: gap),
                child: IntrinsicHeight(
                  child: Row(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        for (final card in row) ...[
                          Expanded(child: card),
                          if (card != row.last) const SizedBox(width: gap),
                        ],
                        for (var f = row.length; f < cols; f++) ...[
                          const SizedBox(width: gap),
                          const Expanded(child: SizedBox.shrink()),
                        ],
                      ]),
                ),
              ),
          ]);
        }),
        const SizedBox(height: 20),
        Text('Nodes by type',
            style: textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
        const SizedBox(height: 10),
        ...DevType.values.map((t) {
          final count = stats[t.name] as int;
          return Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(children: [
              SizedBox(
                width: 120,
                child: Row(children: [
                  Icon(DevService.typeIcons[t],
                      size: 14, color: DevService.typeColors[t]),
                  const SizedBox(width: 6),
                  Flexible(
                      child: Text(DevService.typeLabels[t]!,
                          style: TextStyle(
                              fontSize: 12,
                              color: colorScheme.onSurface.withValues(alpha: 0.8)),
                          overflow: TextOverflow.ellipsis)),
                ]),
              ),
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(6),
                  child: LinearProgressIndicator(
                    value: total == 0 ? 0 : count / total,
                    minHeight: 10,
                    backgroundColor: colorScheme.surfaceContainerHighest,
                    valueColor:
                        AlwaysStoppedAnimation<Color>(DevService.typeColors[t]!),
                  ),
                ),
              ),
              SizedBox(
                  width: 40,
                  child: Text('$count',
                      textAlign: TextAlign.right,
                      style: const TextStyle(
                          fontSize: 12, fontWeight: FontWeight.w600))),
            ]),
          );
        }),
        const SizedBox(height: 24),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: colorScheme.surfaceContainerHigh,
            borderRadius: BorderRadius.circular(14),
            border: Border(left: BorderSide(width: 4, color: colorScheme.primary)),
          ),
          child: AutoAdjustRow(children: [
            Icon(Icons.bolt, color: colorScheme.primary),
            const SizedBox(width: 12),
            Flexible(
              child: Text(
                'devtmpfs populated at boot by DevTmpFS.populate() — mirrors the Python engine: pseudo devices, TTYs, loop, SCSI/NVMe, DRI, ALSA and input subsystems.',
                style: textTheme.bodyMedium
                    ?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.75)),
              ),
            ),
          ]),
        ),
      ],
    );
  }

  Widget _typeChip(DevType? type, ColorScheme colorScheme) {
    final selected = _typeFilter == type;
    return FilterChip(
      avatar: type == null
          ? null
          : Icon(DevService.typeIcons[type],
              size: 14,
              color: selected
                  ? colorScheme.onPrimaryContainer
                  : DevService.typeColors[type]),
      label: Text(type == null ? 'All' : DevService.typeLabels[type]!),
      selected: selected,
      onSelected: (_) => setState(() => _typeFilter = selected ? null : type),
      selectedColor: colorScheme.primaryContainer,
      labelStyle: TextStyle(
          fontSize: 12,
          color: selected ? colorScheme.onPrimaryContainer : colorScheme.onSurface),
      visualDensity: VisualDensity.compact,
    );
  }

  Widget _buildBrowse(ColorScheme colorScheme, TextTheme textTheme) {
    final filtered = _filtered;
    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
        child: TextField(
          decoration: InputDecoration(
            hintText: 'Search nodes (paths, names, descriptions)...',
            prefixIcon: const Icon(Icons.search, size: 20),
            isDense: true,
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: BorderSide(color: colorScheme.outline)),
            filled: true,
            fillColor: colorScheme.surface,
          ),
          onChanged: (v) => setState(() => _searchQuery = v),
        ),
      ),
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
        child: Wrap(
          spacing: 6,
          runSpacing: 4,
          children:
              [null, ...DevType.values].map((t) => _typeChip(t, colorScheme)).toList(),
        ),
      ),
      Expanded(
        child: filtered.isEmpty
            ? Center(
                child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                  Icon(Icons.developer_board_off_outlined,
                      size: 64, color: colorScheme.onSurface.withValues(alpha: 0.3)),
                  const SizedBox(height: 16),
                  Text('No device nodes match your filters',
                      style: textTheme.titleMedium
                          ?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.5))),
                ]))
            : ListView.builder(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                itemCount: filtered.length,
                itemBuilder: (_, i) => _nodeCard(filtered[i], colorScheme, textTheme),
              ),
      ),
    ]);
  }

  Widget _badge(String text, Color color, ColorScheme colorScheme) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        border: Border.all(color: color.withValues(alpha: 0.4)),
        borderRadius: BorderRadius.circular(5),
      ),
      child:
          Text(text, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: color)),
    );
  }

  Widget _nodeCard(DeviceNodeModel n, ColorScheme colorScheme, TextTheme textTheme) {
    final accent = DevService.typeColors[n.devType]!;
    return Card(
      color: colorScheme.surfaceContainerHigh,
      margin: const EdgeInsets.only(bottom: 8),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => _runCommand('udevadm info ${n.path}'),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: accent.withValues(alpha: 0.15),
                border: Border.all(color: accent.withValues(alpha: 0.35)),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(DevService.typeIcons[n.devType], size: 21, color: accent),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Wrap(
                  spacing: 6,
                  runSpacing: 4,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Text(n.name,
                        style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            fontFamily: 'monospace')),
                    _badge(DevService.typeLabels[n.devType]!, accent, colorScheme),
                    if (n.hasDevNums)
                      _badge('${n.major}:${n.minor}', Colors.blueGrey, colorScheme),
                    _badge(n.modeStr, colorScheme.outline, colorScheme),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  n.symlinkTarget != null
                      ? '${n.path} -> ${n.symlinkTarget}'
                      : n.path,
                  style: TextStyle(
                      fontSize: 12,
                      fontFamily: 'monospace',
                      color: n.symlinkTarget != null
                          ? Colors.cyan
                          : colorScheme.onSurface.withValues(alpha: 0.6)),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 4),
                Text(n.description,
                    style: textTheme.bodySmall
                        ?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.55)),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis),
              ]),
            ),
            Tooltip(
              message: '${n.permsStr}\nclick to run udevadm info',
              triggerMode: TooltipTriggerMode.tap,
              child: Icon(Icons.info_outline,
                  size: 18, color: colorScheme.onSurface.withValues(alpha: 0.4)),
            ),
          ]),
        ),
      ),
    );
  }

  Widget _buildTree(ColorScheme colorScheme, TextTheme textTheme) {
    final groups = DevService.groupedNodes();
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        for (final entry in groups.entries)
          Card(
            color: colorScheme.surfaceContainerHigh,
            margin: const EdgeInsets.only(bottom: 8),
            child: Theme(
              data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
              child: ExpansionTile(
                initiallyExpanded: entry.key == '/dev',
                tilePadding: const EdgeInsets.symmetric(horizontal: 16),
                childrenPadding: const EdgeInsets.fromLTRB(8, 0, 8, 8),
                leading: Icon(Icons.folder_outlined,
                    color: colorScheme.primary, size: 20),
                title: Text(entry.key,
                    style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 13,
                        fontWeight: FontWeight.w600)),
                trailing: Chip(
                  label: Text('${entry.value.length}',
                      style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700)),
                  backgroundColor: colorScheme.primaryContainer.withValues(alpha: 0.4),
                  visualDensity: VisualDensity.compact,
                ),
                children: [
                  for (final n in entry.value)
                    ListTile(
                      dense: true,
                      visualDensity: VisualDensity.compact,
                      leading: Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: DevService.typeColors[n.devType]),
                      ),
                      title: Text(
                        n.path == '${entry.key}/${n.name}' || n.path == '/dev/${n.name}'
                            ? n.name
                            : n.path,
                        style: const TextStyle(fontSize: 12, fontFamily: 'monospace'),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      subtitle: n.hasDevNums
                          ? Text('${n.major}:${n.minor} · ${n.modeStr}',
                              style: TextStyle(
                                  fontSize: 10,
                                  color: colorScheme.onSurface.withValues(alpha: 0.5)))
                          : null,
                      trailing: n.symlinkTarget != null
                          ? Icon(Icons.link, size: 14, color: Colors.cyan)
                          : null,
                      onTap: () =>
                          setState(() => _runCommand('udevadm info ${n.path}')),
                    ),
                ],
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildModern(ColorScheme colorScheme, TextTheme textTheme) {
    const features = DevService.modernFeatures;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                Colors.deepPurple.withValues(alpha: 0.18),
                Colors.cyan.withValues(alpha: 0.12),
              ],
            ),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: Colors.deepPurple.withValues(alpha: 0.3)),
          ),
          child: AutoAdjustRow(children: [
            Icon(Icons.auto_awesome, color: Colors.deepPurple, size: 26),
            const SizedBox(width: 12),
            Flexible(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Next-Generation /dev Techniques',
                    style: textTheme.titleMedium
                        ?.copyWith(fontWeight: FontWeight.w700, color: colorScheme.onSurface)),
                const SizedBox(height: 4),
                Text(
                  '${features.length} techniques adopted from modern mainline Linux (k5.x–6.19) and systemd-udevd — previously missing from UmerOS. Implemented in dev/virtualization_devices.py, dev/modern_devices.py and dev/udev_modern.py.',
                  style: textTheme.bodySmall
                      ?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.7)),
                ),
              ]),
            ),
          ]),
        ),
        const SizedBox(height: 16),
        for (final f in features)
          Card(
            color: colorScheme.surfaceContainerHigh,
            margin: const EdgeInsets.only(bottom: 8),
            child: InkWell(
              borderRadius: BorderRadius.circular(12),
              onTap: () {
                if (f.nodePath.startsWith('/dev/')) {
                  _runCommand('udevadm info ${f.nodePath}');
                }
              },
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      color: Colors.deepPurple.withValues(alpha: 0.15),
                      border: Border.all(color: Colors.deepPurple.withValues(alpha: 0.35)),
                      borderRadius: BorderRadius.circular(11),
                    ),
                    child: Icon(f.icon, size: 20, color: Colors.deepPurple),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      AutoAdjustRow(spacing: 6, runSpacing: 4, children: [
                        Flexible(child: Text(f.name,
                            style: textTheme.titleSmall
                                ?.copyWith(fontWeight: FontWeight.w700, color: colorScheme.onSurface))),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.purple.withValues(alpha: 0.15),
                            border: Border.all(color: Colors.purple.withValues(alpha: 0.4)),
                            borderRadius: BorderRadius.circular(5),
                          ),
                          child: Text(f.kernelSince,
                              style: const TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w600,
                                  color: Colors.deepPurple)),
                        ),
                      ]),
                      const SizedBox(height: 6),
                      Text(f.nodePath,
                          style: TextStyle(
                              fontSize: 11,
                              fontFamily: 'monospace',
                              color: colorScheme.primary.withValues(alpha: 0.9)),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis),
                      const SizedBox(height: 6),
                      Text(f.summary,
                          style: textTheme.bodySmall
                              ?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.65), height: 1.35)),
                    ]),
                  ),
                ]),
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildTerminal(ColorScheme colorScheme, TextTheme textTheme) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(children: [
        TextField(
          controller: _cmdController,
          onSubmitted: (_) => _runCommand(),
          style: const TextStyle(fontFamily: 'monospace', fontSize: 13),
          decoration: InputDecoration(
            hintText: 'udevadm <info|monitor|trigger|settle|test> [path]',
            prefixIcon: const Icon(Icons.chevron_right),
            isDense: true,
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: BorderSide(color: colorScheme.outline)),
            filled: true,
            fillColor: colorScheme.surfaceContainerLowest,
          ),
        ),
        const SizedBox(height: 10),
        Align(
          alignment: Alignment.centerLeft,
          child: Wrap(
            spacing: 6,
            runSpacing: 4,
            children: [
              for (final c in _quickCommands)
                ActionChip(
                  label: Text(c,
                      style: const TextStyle(fontSize: 11, fontFamily: 'monospace')),
                  onPressed: () => _runCommand(c),
                  visualDensity: VisualDensity.compact,
                ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        Expanded(child: _console(colorScheme)),
      ]),
    );
  }

  Widget _console(ColorScheme colorScheme) {
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
                  Icon(Icons.terminal,
                      size: 48, color: Colors.white.withValues(alpha: 0.2)),
                  const SizedBox(height: 12),
                  Text('Run udevadm or mknod — try a quick command above.',
                      style:
                          TextStyle(color: Colors.white.withValues(alpha: 0.35), fontSize: 13)),
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
                      TextSpan(
                          style: const TextStyle(
                              fontFamily: 'monospace', fontSize: 12, height: 1.45),
                          children: [
                            TextSpan(text: '\$ ',
                                style: TextStyle(color: Colors.greenAccent.shade200)),
                            TextSpan(
                                text: [r.command, ...r.args].join(' '),
                                style: const TextStyle(color: Colors.white70)),
                            if (r.stdout.isNotEmpty)
                              TextSpan(text: '\n${r.stdout}',
                                  style: const TextStyle(color: Color(0xFFD4D4D4))),
                            if (r.stderr.isNotEmpty)
                              TextSpan(text: '\n${r.stderr}',
                                  style: const TextStyle(color: Color(0xFFFF6B68))),
                            TextSpan(
                                text: '\n[exit ${r.exitCode}]',
                                style: TextStyle(
                                    color: r.success
                                        ? Colors.greenAccent
                                        : Colors.orangeAccent)),
                          ]),
                    ),
                    const SizedBox(height: 10),
                  ],
                ],
              ),
            ),
    );
  }

  Widget _buildFhs(ColorScheme colorScheme, TextTheme textTheme) {
    final map = DevService.fhsMap();
    final present = map.where((e) => e.present).length;
    return ListView(padding: const EdgeInsets.all(16), children: [
      Row(children: [
        Expanded(
            child: _statCard('FHS paths present', '$present / ${map.length}',
                Icons.check_circle_outline, Colors.green, textTheme, colorScheme)),
        const SizedBox(width: 12),
        Expanded(
            child: _statCard('Spec version', 'FHS 3.0', Icons.menu_book_outlined,
                colorScheme.primary, textTheme, colorScheme)),
      ]),
      const SizedBox(height: 16),
      ...map.map((e) {
        final c = e.present ? Colors.green : Colors.redAccent;
        return Card(
          color: colorScheme.surfaceContainerHigh,
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            leading: Icon(e.present ? Icons.check_circle : Icons.error_outline, color: c),
            title: Text(e.path,
                style: const TextStyle(
                    fontFamily: 'monospace', fontSize: 14, fontWeight: FontWeight.w600)),
            subtitle: Text(e.purpose,
                style: TextStyle(
                    fontSize: 12, color: colorScheme.onSurface.withValues(alpha: 0.6))),
            trailing: Chip(
              label: Text(e.present ? 'OK' : 'MISSING',
                  style: TextStyle(
                      fontSize: 10, fontWeight: FontWeight.w700, color: c)),
              backgroundColor: c.withValues(alpha: 0.12),
              side: BorderSide(color: c.withValues(alpha: 0.4)),
              visualDensity: VisualDensity.compact,
            ),
          ),
        );
      }),
    ]);
  }
}
