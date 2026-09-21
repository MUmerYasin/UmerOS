import 'package:flutter/material.dart';

class CloudApp extends StatefulWidget {
  const CloudApp({super.key});

  @override
  State<CloudApp> createState() => _CloudAppState();
}

class _CloudAppState extends State<CloudApp> {
  CloudView _view = CloudView.overview;
  bool _autoscale = true;
  int _targetReplicas = 4;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 920;
        final content = _CloudContent(
          view: _view,
          autoscale: _autoscale,
          targetReplicas: _targetReplicas,
          onAutoscaleChanged: (value) => setState(() => _autoscale = value),
          onTargetReplicasChanged: (value) {
            setState(() => _targetReplicas = value);
          },
        );

        return Row(
          children: [
            if (wide)
              NavigationRail(
                selectedIndex: _view.index,
                onDestinationSelected: _selectView,
                labelType: NavigationRailLabelType.all,
                backgroundColor: colorScheme.surface,
                destinations: const [
                  NavigationRailDestination(
                    icon: Icon(Icons.dashboard_outlined),
                    selectedIcon: Icon(Icons.dashboard),
                    label: Text('Overview'),
                  ),
                  NavigationRailDestination(
                    icon: Icon(Icons.hub_outlined),
                    selectedIcon: Icon(Icons.hub),
                    label: Text('Workloads'),
                  ),
                  NavigationRailDestination(
                    icon: Icon(Icons.query_stats_outlined),
                    selectedIcon: Icon(Icons.query_stats),
                    label: Text('Usage'),
                  ),
                ],
              ),
            if (wide)
              VerticalDivider(
                width: 1,
                color: colorScheme.outlineVariant.withValues(alpha: 0.7),
              ),
            Expanded(
              child: Column(
                children: [
                  _CloudToolbar(onRefresh: () {}, onDeploy: () {}),
                  Expanded(child: content),
                  if (!wide)
                    NavigationBar(
                      selectedIndex: _view.index,
                      onDestinationSelected: _selectView,
                      destinations: const [
                        NavigationDestination(
                          icon: Icon(Icons.dashboard_outlined),
                          selectedIcon: Icon(Icons.dashboard),
                          label: 'Overview',
                        ),
                        NavigationDestination(
                          icon: Icon(Icons.hub_outlined),
                          selectedIcon: Icon(Icons.hub),
                          label: 'Workloads',
                        ),
                        NavigationDestination(
                          icon: Icon(Icons.query_stats_outlined),
                          selectedIcon: Icon(Icons.query_stats),
                          label: 'Usage',
                        ),
                      ],
                    ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }

  void _selectView(int index) {
    setState(() => _view = CloudView.values[index]);
  }
}

enum CloudView { overview, workloads, usage }

class _CloudToolbar extends StatelessWidget {
  const _CloudToolbar({required this.onRefresh, required this.onDeploy});

  final VoidCallback onRefresh;
  final VoidCallback onDeploy;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: colorScheme.surface,
        border: Border(
          bottom: BorderSide(color: colorScheme.outlineVariant.withValues(alpha: 0.7)),
        ),
      ),
      child: Row(
        children: [
          Icon(Icons.cloud_queue, color: colorScheme.primary),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              'Cloud Control',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
            ),
          ),
          Tooltip(
            message: 'Refresh cloud state',
            child: IconButton(
              onPressed: onRefresh,
              icon: const Icon(Icons.sync),
            ),
          ),
          const SizedBox(width: 8),
          Tooltip(
            message: 'Deploy workload',
            child: FilledButton.icon(
              onPressed: onDeploy,
              icon: const Icon(Icons.rocket_launch_outlined),
              label: const Text('Deploy'),
            ),
          ),
        ],
      ),
    );
  }
}

class _CloudContent extends StatelessWidget {
  const _CloudContent({
    required this.view,
    required this.autoscale,
    required this.targetReplicas,
    required this.onAutoscaleChanged,
    required this.onTargetReplicasChanged,
  });

  final CloudView view;
  final bool autoscale;
  final int targetReplicas;
  final ValueChanged<bool> onAutoscaleChanged;
  final ValueChanged<int> onTargetReplicasChanged;

  @override
  Widget build(BuildContext context) {
    final child = switch (view) {
      CloudView.overview => const _OverviewPane(),
      CloudView.workloads => _WorkloadsPane(
          autoscale: autoscale,
          targetReplicas: targetReplicas,
          onAutoscaleChanged: onAutoscaleChanged,
          onTargetReplicasChanged: onTargetReplicasChanged,
        ),
      CloudView.usage => const _UsagePane(),
    };

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: child,
    );
  }
}

class _OverviewPane extends StatelessWidget {
  const _OverviewPane();

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _HeaderPanel(
          title: 'Private Cloud Pool',
          subtitle: 'Resource pooling, scheduling, quotas, virtual networking, and metered usage for UmerOS workloads.',
          chips: [
            _StatusChip(label: 'Scheduler healthy', color: Color(0xFF1F7A6D)),
            _StatusChip(label: 'Quota guard on', color: Color(0xFF2563EB)),
            _StatusChip(label: 'Metering live', color: Color(0xFF7C3AED)),
          ],
        ),
        const SizedBox(height: 16),
        _ResponsiveGrid(
          minItemWidth: 210,
          children: _metrics.map((metric) => _MetricCard(metric: metric)).toList(),
        ),
        const SizedBox(height: 20),
        const _SectionTitle('Compute Nodes'),
        const SizedBox(height: 10),
        _ResponsiveGrid(
          minItemWidth: 280,
          children: _nodes.map((node) => _NodeCard(node: node)).toList(),
        ),
        const SizedBox(height: 20),
        const _SectionTitle('Cloud OS Services'),
        const SizedBox(height: 10),
        _ResponsiveGrid(
          minItemWidth: 250,
          children: _controlServices
              .map((service) => _ControlPlaneCard(service: service))
              .toList(),
        ),
      ],
    );
  }
}

class _WorkloadsPane extends StatelessWidget {
  const _WorkloadsPane({
    required this.autoscale,
    required this.targetReplicas,
    required this.onAutoscaleChanged,
    required this.onTargetReplicasChanged,
  });

  final bool autoscale;
  final int targetReplicas;
  final ValueChanged<bool> onAutoscaleChanged;
  final ValueChanged<int> onTargetReplicasChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _HeaderPanel(
          title: 'Elastic Workloads',
          subtitle: 'Services are represented as isolated replicas with shared virtual-network endpoints.',
          trailing: SegmentedButton<int>(
            segments: const [
              ButtonSegment(value: 2, label: Text('2')),
              ButtonSegment(value: 4, label: Text('4')),
              ButtonSegment(value: 6, label: Text('6')),
            ],
            selected: {targetReplicas},
            onSelectionChanged: (values) => onTargetReplicasChanged(values.first),
          ),
        ),
        const SizedBox(height: 12),
        Card(
          child: SwitchListTile(
            value: autoscale,
            onChanged: onAutoscaleChanged,
            secondary: const Icon(Icons.auto_graph),
            title: const Text('Autoscale notebook-api'),
            subtitle: Text('Target replicas: $targetReplicas'),
          ),
        ),
        const SizedBox(height: 16),
        _ResponsiveGrid(
          minItemWidth: 320,
          children: _workloads.map((item) {
            final adjusted = item.name == 'notebook-api' ? targetReplicas : item.desired;
            return _WorkloadCard(workload: item.copyWith(desired: adjusted));
          }).toList(),
        ),
      ],
    );
  }
}

class _UsagePane extends StatelessWidget {
  const _UsagePane();

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _HeaderPanel(
          title: 'Measured Usage',
          subtitle: 'Per-project quota, consumption, and chargeback snapshot.',
          chips: [_StatusChip(label: '1 hour window', color: Color(0xFF475569))],
        ),
        const SizedBox(height: 16),
        _ResponsiveGrid(
          minItemWidth: 320,
          children: _projects.map((project) => _ProjectQuotaCard(project: project)).toList(),
        ),
        const SizedBox(height: 20),
        const _SectionTitle('Recent Events'),
        const SizedBox(height: 10),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(8),
            child: Column(
              children: _events
                  .map(
                    (event) => ListTile(
                      leading: Icon(event.icon, color: event.color),
                      title: Text(event.title),
                      subtitle: Text(event.detail),
                      dense: true,
                    ),
                  )
                  .toList(),
            ),
          ),
        ),
      ],
    );
  }
}

class _HeaderPanel extends StatelessWidget {
  const _HeaderPanel({
    required this.title,
    required this.subtitle,
    this.chips = const [],
    this.trailing,
  });

  final String title;
  final String subtitle;
  final List<Widget> chips;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Wrap(
          alignment: WrapAlignment.spaceBetween,
          crossAxisAlignment: WrapCrossAlignment.center,
          runSpacing: 14,
          children: [
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 640),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                  const SizedBox(height: 4),
                  Text(subtitle),
                ],
              ),
            ),
            trailing ??
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: chips,
                ),
          ],
        ),
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({required this.metric});

  final _CloudMetric metric;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(metric.icon, color: metric.color),
            const SizedBox(height: 12),
            Text(metric.label, style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 4),
            Text(
              metric.value,
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 12),
            _PlainProgress(value: metric.progress, color: metric.color),
          ],
        ),
      ),
    );
  }
}

class _NodeCard extends StatelessWidget {
  const _NodeCard({required this.node});

  final _CloudNode node;

  @override
  Widget build(BuildContext context) {
    final color = node.healthy ? const Color(0xFF1F7A6D) : Colors.red;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.dns_outlined, color: color),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    node.host,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                ),
                _StatusChip(label: node.zone, color: color),
              ],
            ),
            const SizedBox(height: 14),
            _UsageBar(label: 'CPU', value: node.cpu, color: const Color(0xFF2563EB)),
            _UsageBar(label: 'Memory', value: node.memory, color: const Color(0xFF7C3AED)),
            _UsageBar(label: 'Storage', value: node.storage, color: const Color(0xFFB45309)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: node.traits
                  .map((trait) => Chip(label: Text(trait), visualDensity: VisualDensity.compact))
                  .toList(),
            ),
          ],
        ),
      ),
    );
  }
}

class _ControlPlaneCard extends StatelessWidget {
  const _ControlPlaneCard({required this.service});

  final _ControlService service;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(service.icon, color: service.color),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(service.name, style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 4),
                  Text(service.status),
                  const SizedBox(height: 12),
                  _PlainProgress(value: service.load, color: service.color),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _WorkloadCard extends StatelessWidget {
  const _WorkloadCard({required this.workload});

  final _Workload workload;

  @override
  Widget build(BuildContext context) {
    final readyRatio = workload.ready / workload.desired.clamp(1, 99).toDouble();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.hub_outlined, color: workload.color),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    workload.name,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                ),
                _StatusChip(label: workload.state, color: workload.color),
              ],
            ),
            const SizedBox(height: 10),
            Text(workload.endpoint, overflow: TextOverflow.ellipsis),
            const SizedBox(height: 14),
            _UsageBar(
              label: '${workload.ready}/${workload.desired} ready',
              value: readyRatio,
              color: workload.color,
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              children: [
                Tooltip(
                  message: 'Scale out',
                  child: IconButton.filledTonal(
                    icon: const Icon(Icons.add),
                    onPressed: () {},
                  ),
                ),
                Tooltip(
                  message: 'Scale in',
                  child: IconButton.filledTonal(
                    icon: const Icon(Icons.remove),
                    onPressed: () {},
                  ),
                ),
                Tooltip(
                  message: 'Heal replicas',
                  child: IconButton.filledTonal(
                    icon: const Icon(Icons.healing_outlined),
                    onPressed: () {},
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ProjectQuotaCard extends StatelessWidget {
  const _ProjectQuotaCard({required this.project});

  final _ProjectUsage project;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.account_tree_outlined, color: Color(0xFF2563EB)),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    project.name,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                ),
                Text(project.cost, style: Theme.of(context).textTheme.titleMedium),
              ],
            ),
            const SizedBox(height: 16),
            _UsageBar(label: 'Instances', value: project.instances, color: const Color(0xFF1F7A6D)),
            _UsageBar(label: 'vCPU', value: project.vcpu, color: const Color(0xFF2563EB)),
            _UsageBar(label: 'Memory', value: project.memory, color: const Color(0xFF7C3AED)),
            _UsageBar(label: 'Storage', value: project.storage, color: const Color(0xFFB45309)),
          ],
        ),
      ),
    );
  }
}

class _UsageBar extends StatelessWidget {
  const _UsageBar({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final double value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final clamped = value.clamp(0.0, 1.0).toDouble();
    final percent = (clamped * 100).round();
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(label)),
              Text('$percent%'),
            ],
          ),
          const SizedBox(height: 6),
          _PlainProgress(value: clamped, color: color),
        ],
      ),
    );
  }
}

class _PlainProgress extends StatelessWidget {
  const _PlainProgress({required this.value, required this.color});

  final double value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return LinearProgressIndicator(
      value: value.clamp(0.0, 1.0).toDouble(),
      minHeight: 7,
      borderRadius: BorderRadius.circular(4),
      color: color,
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.11),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.28)),
      ),
      child: Text(
        label,
        style: TextStyle(color: color, fontWeight: FontWeight.w600),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
    );
  }
}

class _ResponsiveGrid extends StatelessWidget {
  const _ResponsiveGrid({
    required this.children,
    this.minItemWidth = 260,
  });

  final List<Widget> children;
  final double minItemWidth;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        final count = (width / minItemWidth).floor().clamp(1, 4);
        final gap = 12.0;
        final itemWidth = (width - gap * (count - 1)) / count;
        return Wrap(
          spacing: gap,
          runSpacing: gap,
          children: children
              .map(
                (child) => SizedBox(
                  width: itemWidth,
                  child: child,
                ),
              )
              .toList(),
        );
      },
    );
  }
}

class _CloudMetric {
  const _CloudMetric(this.label, this.value, this.progress, this.icon, this.color);

  final String label;
  final String value;
  final double progress;
  final IconData icon;
  final Color color;
}

class _CloudNode {
  const _CloudNode({
    required this.host,
    required this.zone,
    required this.cpu,
    required this.memory,
    required this.storage,
    required this.traits,
  }) : healthy = true;

  final String host;
  final String zone;
  final double cpu;
  final double memory;
  final double storage;
  final List<String> traits;
  final bool healthy;
}

class _ControlService {
  const _ControlService(this.name, this.status, this.load, this.icon, this.color);

  final String name;
  final String status;
  final double load;
  final IconData icon;
  final Color color;
}

class _Workload {
  const _Workload({
    required this.name,
    required this.endpoint,
    required this.ready,
    required this.desired,
    required this.state,
    required this.color,
  });

  final String name;
  final String endpoint;
  final int ready;
  final int desired;
  final String state;
  final Color color;

  _Workload copyWith({int? desired}) {
    final nextDesired = desired ?? this.desired;
    return _Workload(
      name: name,
      endpoint: endpoint,
      ready: ready.clamp(0, nextDesired),
      desired: nextDesired,
      state: state,
      color: color,
    );
  }
}

class _ProjectUsage {
  const _ProjectUsage({
    required this.name,
    required this.cost,
    required this.instances,
    required this.vcpu,
    required this.memory,
    required this.storage,
  });

  final String name;
  final String cost;
  final double instances;
  final double vcpu;
  final double memory;
  final double storage;
}

class _CloudEvent {
  const _CloudEvent(this.title, this.detail, this.icon, this.color);

  final String title;
  final String detail;
  final IconData icon;
  final Color color;
}

const _metrics = [
  _CloudMetric('vCPU allocated', '18 / 72', 0.25, Icons.memory, Color(0xFF2563EB)),
  _CloudMetric('Memory allocated', '44 / 288 GB', 0.15, Icons.view_in_ar, Color(0xFF7C3AED)),
  _CloudMetric('Storage allocated', '410 / 4.5 TB', 0.09, Icons.storage, Color(0xFFB45309)),
  _CloudMetric('Running replicas', '9 active', 0.60, Icons.apps, Color(0xFF1F7A6D)),
];

const _nodes = [
  _CloudNode(
    host: 'edge-1',
    zone: 'edge-a',
    cpu: 0.19,
    memory: 0.22,
    storage: 0.11,
    traits: ['ssd', 'edge'],
  ),
  _CloudNode(
    host: 'core-1',
    zone: 'core-a',
    cpu: 0.34,
    memory: 0.28,
    storage: 0.18,
    traits: ['ssd', 'ha'],
  ),
  _CloudNode(
    host: 'gpu-1',
    zone: 'core-gpu',
    cpu: 0.21,
    memory: 0.17,
    storage: 0.08,
    traits: ['ssd', 'gpu'],
  ),
];

const _controlServices = [
  _ControlService('Placement', 'Filter and weight scheduler', 0.34, Icons.route_outlined, Color(0xFF2563EB)),
  _ControlService('Quota', 'Project guardrail active', 0.42, Icons.policy_outlined, Color(0xFF7C3AED)),
  _ControlService('Metering', 'Usage window collecting', 0.28, Icons.speed_outlined, Color(0xFF1F7A6D)),
  _ControlService('Network', 'Virtual network ready', 0.18, Icons.lan_outlined, Color(0xFFB45309)),
];

const _workloads = [
  _Workload(
    name: 'notebook-api',
    endpoint: 'https://notebook-api.apps.umeros.local',
    ready: 2,
    desired: 4,
    state: 'active',
    color: Color(0xFF1F7A6D),
  ),
  _Workload(
    name: 'artifact-cache',
    endpoint: 'https://artifact-cache.apps.umeros.local',
    ready: 3,
    desired: 3,
    state: 'active',
    color: Color(0xFF2563EB),
  ),
  _Workload(
    name: 'gpu-worker',
    endpoint: 'https://gpu-worker.apps.umeros.local',
    ready: 1,
    desired: 2,
    state: 'scaling',
    color: Color(0xFFB45309),
  ),
];

const _projects = [
  _ProjectUsage(
    name: 'Research Cloud',
    cost: '\$0.18',
    instances: 0.45,
    vcpu: 0.28,
    memory: 0.34,
    storage: 0.20,
  ),
  _ProjectUsage(
    name: 'System Services',
    cost: '\$0.07',
    instances: 0.30,
    vcpu: 0.18,
    memory: 0.21,
    storage: 0.13,
  ),
];

const _events = [
  _CloudEvent('service svc-0001 reconciled', 'notebook-api target set to 4 replicas', Icons.tune, Color(0xFF1F7A6D)),
  _CloudEvent('instance inst-0003 migrated', 'moved from edge-a to core-a', Icons.move_up_outlined, Color(0xFF2563EB)),
  _CloudEvent('volume vol-0001 attached', 'db-data attached to research-db', Icons.link, Color(0xFF7C3AED)),
  _CloudEvent('quota check passed', 'project Research Cloud within all limits', Icons.verified_user_outlined, Color(0xFFB45309)),
];
