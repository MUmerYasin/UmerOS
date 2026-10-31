import 'package:flutter/material.dart';

import '../services/cloud_service.dart';

class CloudApp extends StatefulWidget {
  const CloudApp({super.key, this.service});

  final CloudService? service;

  @override
  State<CloudApp> createState() => _CloudAppState();
}

class _CloudAppState extends State<CloudApp> {
  late final CloudService _service;
  late final bool _ownsService;
  CloudSnapshot? _snapshot;
  CloudCatalog? _catalog;
  String? _error;
  String? _busyServiceId;
  bool _loading = true;
  _CloudTab _tab = _CloudTab.overview;

  @override
  void initState() {
    super.initState();
    _service = widget.service ?? CloudService();
    _ownsService = widget.service == null;
    _refresh();
  }

  @override
  void dispose() {
    if (_ownsService) {
      _service.dispose();
    }
    super.dispose();
  }

  Future<void> _refresh() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final values = await Future.wait<Object>([
        _service.getSnapshot(),
        _service.getCatalog(),
      ]);
      if (!mounted) {
        return;
      }
      setState(() {
        _snapshot = values[0] as CloudSnapshot;
        _catalog = values[1] as CloudCatalog;
      });
    } on CloudServiceException catch (error) {
      if (mounted) {
        setState(() => _error = error.message);
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _operate(
    String serviceId,
    Future<CloudSnapshot> Function() operation,
    String message,
  ) async {
    setState(() => _busyServiceId = serviceId);
    try {
      final snapshot = await operation();
      if (!mounted) {
        return;
      }
      setState(() => _snapshot = snapshot);
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(message)));
    } on CloudServiceException catch (error) {
      if (mounted) {
        _showError(error.message);
      }
    } finally {
      if (mounted) {
        setState(() => _busyServiceId = null);
      }
    }
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), behavior: SnackBarBehavior.floating),
    );
  }

  Future<void> _showDeployDialog() async {
    final catalog = _catalog;
    if (catalog == null ||
        catalog.projects.isEmpty ||
        catalog.images.isEmpty ||
        catalog.flavors.isEmpty) {
      _showError(
        'The cloud catalog has no deployable project, image, or flavor.',
      );
      return;
    }
    final request = await showDialog<CloudDeployRequest>(
      context: context,
      builder: (context) => _DeployDialog(catalog: catalog),
    );
    if (request == null) {
      return;
    }
    await _operate(
      'deploy',
      () => _service.deploy(request),
      '${request.name} deployment requested.',
    );
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 920;
        return Row(
          children: [
            if (wide)
              NavigationRail(
                selectedIndex: _tab.index,
                labelType: NavigationRailLabelType.all,
                onDestinationSelected: (value) =>
                    setState(() => _tab = _CloudTab.values[value]),
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
            if (wide) VerticalDivider(width: 1, color: scheme.outlineVariant),
            Expanded(
              child: Column(
                children: [
                  _Toolbar(
                    loading: _loading,
                    canDeploy: _catalog != null && !_loading,
                    onRefresh: _loading ? null : _refresh,
                    onDeploy: _loading ? null : _showDeployDialog,
                  ),
                  Expanded(child: _body()),
                  if (!wide)
                    NavigationBar(
                      selectedIndex: _tab.index,
                      onDestinationSelected: (value) =>
                          setState(() => _tab = _CloudTab.values[value]),
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

  Widget _body() {
    if (_loading && _snapshot == null) {
      return const Center(child: CircularProgressIndicator());
    }
    final snapshot = _snapshot;
    if (snapshot == null) {
      return _Unavailable(error: _error, onRetry: _refresh);
    }
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: switch (_tab) {
        _CloudTab.overview => _Overview(snapshot: snapshot),
        _CloudTab.workloads => _Workloads(
          snapshot: snapshot,
          busyServiceId: _busyServiceId,
          onScale: (service, replicas) => _operate(
            service.id,
            () => _service.scaleService(service.id, replicas),
            '${service.name} set to $replicas replica${replicas == 1 ? '' : 's'}.',
          ),
          onAutoscale: (service) => _operate(
            service.id,
            () => _service.autoscaleService(
              service.id,
              observedCpuPercent: 140,
              minReplicas: 1,
              maxReplicas: 10,
              targetCpuPercent: 65,
            ),
            '${service.name} evaluated against the latest CPU sample.',
          ),
        ),
        _CloudTab.usage => _Usage(snapshot: snapshot),
      },
    );
  }
}

enum _CloudTab { overview, workloads, usage }

class _Toolbar extends StatelessWidget {
  const _Toolbar({
    required this.loading,
    required this.canDeploy,
    required this.onRefresh,
    required this.onDeploy,
  });

  final bool loading;
  final bool canDeploy;
  final VoidCallback? onRefresh;
  final VoidCallback? onDeploy;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: scheme.surface,
        border: Border(bottom: BorderSide(color: scheme.outlineVariant)),
      ),
      child: Row(
        children: [
          Icon(Icons.cloud_queue, color: scheme.primary),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              'Cloud Control',
              style: Theme.of(
                context,
              ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
            ),
          ),
          Tooltip(
            message: 'Refresh cloud state',
            child: IconButton(
              onPressed: onRefresh,
              icon: loading
                  ? const SizedBox.square(
                      dimension: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.sync),
            ),
          ),
          const SizedBox(width: 8),
          FilledButton.icon(
            onPressed: canDeploy ? onDeploy : null,
            icon: const Icon(Icons.rocket_launch_outlined),
            label: const Text('Deploy'),
          ),
        ],
      ),
    );
  }
}

class _Overview extends StatelessWidget {
  const _Overview({required this.snapshot});

  final CloudSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    final metrics = [
      _Metric(
        'vCPU allocated',
        _quantity(snapshot.capacity.vcpus),
        snapshot.capacity.vcpus.ratio,
        Icons.memory,
        const Color(0xFF2563EB),
      ),
      _Metric(
        'Memory allocated',
        _memory(snapshot.capacity.memoryMb),
        snapshot.capacity.memoryMb.ratio,
        Icons.view_in_ar,
        const Color(0xFF7C3AED),
      ),
      _Metric(
        'Storage allocated',
        _storage(snapshot.capacity.storageGb),
        snapshot.capacity.storageGb.ratio,
        Icons.storage,
        const Color(0xFFB45309),
      ),
      _Metric(
        'Running replicas',
        '${snapshot.runningReplicas} active',
        1,
        Icons.apps,
        const Color(0xFF1F7A6D),
      ),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _Header(
          title: '${_titleCase(snapshot.deploymentModel)} Cloud Pool',
          detail:
              'Live state from the local, simulation-safe UmerOS Cloud API.',
          labels: [
            'Simulation',
            '${snapshot.nodes.length} nodes',
            '${snapshot.projects.length} projects',
          ],
        ),
        const SizedBox(height: 16),
        _Grid(
          minWidth: 210,
          children: metrics
              .map((metric) => _MetricCard(metric: metric))
              .toList(),
        ),
        const SizedBox(height: 20),
        Text(
          'Compute Nodes',
          style: Theme.of(
            context,
          ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 10),
        _Grid(
          minWidth: 280,
          children: snapshot.nodes
              .map((node) => _NodeCard(node: node))
              .toList(),
        ),
      ],
    );
  }
}

class _Workloads extends StatelessWidget {
  const _Workloads({
    required this.snapshot,
    required this.busyServiceId,
    required this.onScale,
    required this.onAutoscale,
  });

  final CloudSnapshot snapshot;
  final String? busyServiceId;
  final Future<void> Function(CloudWorkload service, int replicas) onScale;
  final Future<void> Function(CloudWorkload service) onAutoscale;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _Header(
          title: 'Elastic Workloads',
          detail:
              'Scale simulated replicas and evaluate autoscaling against a CPU sample.',
          labels: ['Loopback control plane'],
        ),
        const SizedBox(height: 16),
        if (snapshot.services.isEmpty)
          const _Empty(
            icon: Icons.hub_outlined,
            title: 'No deployed workloads',
            detail: 'Deploy a service to begin scheduling replicas.',
          )
        else
          _Grid(
            minWidth: 320,
            children: snapshot.services
                .map(
                  (service) => _WorkloadCard(
                    workload: service,
                    busy: service.id == busyServiceId,
                    onScale: (replicas) => onScale(service, replicas),
                    onAutoscale: () => onAutoscale(service),
                  ),
                )
                .toList(),
          ),
      ],
    );
  }
}

class _Usage extends StatelessWidget {
  const _Usage({required this.snapshot});

  final CloudSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _Header(
          title: 'Measured Usage',
          detail:
              'Per-project quota consumption and the current modeled chargeback total.',
          labels: ['Metering enabled'],
        ),
        const SizedBox(height: 16),
        _Grid(
          minWidth: 320,
          children: snapshot.projects
              .map((project) => _ProjectCard(project: project))
              .toList(),
        ),
        const SizedBox(height: 20),
        Text(
          'Recent Events',
          style: Theme.of(
            context,
          ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 10),
        Card(
          child: snapshot.events.isEmpty
              ? const Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('No cloud events have been recorded.'),
                )
              : Column(
                  children: snapshot.events
                      .map(
                        (event) => ListTile(
                          leading: const Icon(Icons.bolt_outlined),
                          title: Text(event),
                          dense: true,
                        ),
                      )
                      .toList(),
                ),
        ),
      ],
    );
  }
}

class _Unavailable extends StatelessWidget {
  const _Unavailable({required this.error, required this.onRetry});

  final String? error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 440),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.cloud_off_outlined,
                size: 44,
                color: Theme.of(context).colorScheme.error,
              ),
              const SizedBox(height: 16),
              Text(
                'Cloud control service unavailable',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              Text(
                error ?? 'The local cloud service could not be reached.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DeployDialog extends StatefulWidget {
  const _DeployDialog({required this.catalog});

  final CloudCatalog catalog;

  @override
  State<_DeployDialog> createState() => _DeployDialogState();
}

class _DeployDialogState extends State<_DeployDialog> {
  late final TextEditingController _name;
  late String _projectId;
  late String _imageId;
  late String _flavorId;
  String? _networkId;
  int _replicas = 1;
  String? _validationMessage;

  @override
  void initState() {
    super.initState();
    _name = TextEditingController(text: 'new-service');
    _projectId = widget.catalog.projects.first.id;
    _imageId = widget.catalog.images.first.id;
    _flavorId = widget.catalog.flavors.first.id;
  }

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final networks = widget.catalog.networks
        .where((item) => item.projectId == _projectId)
        .toList();
    return AlertDialog(
      title: const Text('Deploy Workload'),
      content: SizedBox(
        width: 440,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: _name,
                decoration: const InputDecoration(labelText: 'Service name'),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: _projectId,
                decoration: const InputDecoration(labelText: 'Project'),
                items: widget.catalog.projects
                    .map(
                      (item) => DropdownMenuItem(
                        value: item.id,
                        child: Text(item.name),
                      ),
                    )
                    .toList(),
                onChanged: (value) => setState(() {
                  _projectId = value!;
                  _networkId = null;
                }),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: _imageId,
                decoration: const InputDecoration(labelText: 'Image'),
                items: widget.catalog.images
                    .map(
                      (item) => DropdownMenuItem(
                        value: item.id,
                        child: Text(item.name),
                      ),
                    )
                    .toList(),
                onChanged: (value) => setState(() => _imageId = value!),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: _flavorId,
                decoration: const InputDecoration(labelText: 'Flavor'),
                items: widget.catalog.flavors
                    .map(
                      (item) => DropdownMenuItem(
                        value: item.id,
                        child: Text(
                          '${item.name} - ${item.vcpus} vCPU, ${_memoryValue(item.memoryMb)}',
                        ),
                      ),
                    )
                    .toList(),
                onChanged: (value) => setState(() => _flavorId = value!),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String?>(
                key: ValueKey(_projectId),
                initialValue: _networkId,
                decoration: const InputDecoration(labelText: 'Network'),
                items: [
                  const DropdownMenuItem<String?>(
                    value: null,
                    child: Text('Use project default'),
                  ),
                  ...networks.map(
                    (item) => DropdownMenuItem<String?>(
                      value: item.id,
                      child: Text(item.name),
                    ),
                  ),
                ],
                onChanged: (value) => setState(() => _networkId = value),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<int>(
                initialValue: _replicas,
                decoration: const InputDecoration(
                  labelText: 'Initial replicas',
                ),
                items: [1, 2, 3, 4]
                    .map(
                      (item) =>
                          DropdownMenuItem(value: item, child: Text('$item')),
                    )
                    .toList(),
                onChanged: (value) => setState(() => _replicas = value!),
              ),
              if (_validationMessage != null) ...[
                const SizedBox(height: 12),
                Text(
                  _validationMessage!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton.icon(
          onPressed: _submit,
          icon: const Icon(Icons.rocket_launch_outlined),
          label: const Text('Deploy'),
        ),
      ],
    );
  }

  void _submit() {
    final name = _name.text.trim();
    if (!RegExp(r'^[a-zA-Z0-9][a-zA-Z0-9-]*$').hasMatch(name)) {
      setState(
        () => _validationMessage =
            'Use letters, numbers, and hyphens; begin with a letter or number.',
      );
      return;
    }
    Navigator.pop(
      context,
      CloudDeployRequest(
        projectId: _projectId,
        name: name,
        imageId: _imageId,
        flavorId: _flavorId,
        replicas: _replicas,
        networkId: _networkId,
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({
    required this.title,
    required this.detail,
    required this.labels,
  });

  final String title;
  final String detail;
  final List<String> labels;

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
              constraints: const BoxConstraints(maxWidth: 620),
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
                  Text(detail),
                ],
              ),
            ),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: labels.map(_Chip.new).toList(),
            ),
          ],
        ),
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip(this.label);

  final String label;

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme.primary;
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

class _MetricCard extends StatelessWidget {
  const _MetricCard({required this.metric});

  final _Metric metric;

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
              style: Theme.of(
                context,
              ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 12),
            LinearProgressIndicator(
              value: metric.progress.clamp(0.0, 1.0).toDouble(),
              color: metric.color,
              minHeight: 7,
            ),
          ],
        ),
      ),
    );
  }
}

class _NodeCard extends StatelessWidget {
  const _NodeCard({required this.node});

  final CloudNodeStatus node;

  @override
  Widget build(BuildContext context) {
    final color = node.healthy && node.enabled
        ? const Color(0xFF1F7A6D)
        : Colors.red;
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
                _Chip(node.zone),
              ],
            ),
            const SizedBox(height: 14),
            _Bar(label: 'CPU', value: node.cpu, color: const Color(0xFF2563EB)),
            _Bar(
              label: 'Memory',
              value: node.memory,
              color: const Color(0xFF7C3AED),
            ),
            _Bar(
              label: 'Storage',
              value: node.storage,
              color: const Color(0xFFB45309),
            ),
            Text(
              '${node.instances} scheduled instance${node.instances == 1 ? '' : 's'}',
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: node.traits
                  .map(
                    (item) => Chip(
                      label: Text(item),
                      visualDensity: VisualDensity.compact,
                    ),
                  )
                  .toList(),
            ),
          ],
        ),
      ),
    );
  }
}

class _WorkloadCard extends StatelessWidget {
  const _WorkloadCard({
    required this.workload,
    required this.busy,
    required this.onScale,
    required this.onAutoscale,
  });

  final CloudWorkload workload;
  final bool busy;
  final ValueChanged<int> onScale;
  final VoidCallback onAutoscale;

  @override
  Widget build(BuildContext context) {
    final color = workload.state == 'active'
        ? const Color(0xFF1F7A6D)
        : const Color(0xFFB45309);
    final ready = workload.desired == 0
        ? 0.0
        : workload.ready / workload.desired;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.hub_outlined, color: color),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    workload.name,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                _Chip(workload.state),
              ],
            ),
            const SizedBox(height: 10),
            Text(
              workload.endpoint,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 14),
            _Bar(
              label: '${workload.ready}/${workload.desired} ready',
              value: ready,
              color: color,
            ),
            Row(
              children: [
                Tooltip(
                  message: 'Scale out',
                  child: IconButton.filledTonal(
                    onPressed: busy
                        ? null
                        : () => onScale(workload.desired + 1),
                    icon: const Icon(Icons.add),
                  ),
                ),
                const SizedBox(width: 8),
                Tooltip(
                  message: 'Scale in',
                  child: IconButton.filledTonal(
                    onPressed: busy || workload.desired == 0
                        ? null
                        : () => onScale(workload.desired - 1),
                    icon: const Icon(Icons.remove),
                  ),
                ),
                const SizedBox(width: 8),
                Tooltip(
                  message: 'Evaluate autoscaling',
                  child: IconButton.filledTonal(
                    onPressed: busy ? null : onAutoscale,
                    icon: busy
                        ? const SizedBox.square(
                            dimension: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.auto_graph),
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

class _ProjectCard extends StatelessWidget {
  const _ProjectCard({required this.project});

  final CloudProjectStatus project;

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
                const Icon(
                  Icons.account_tree_outlined,
                  color: Color(0xFF2563EB),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    project.name,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                Text(
                  '\$${project.cost.toStringAsFixed(2)}',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ],
            ),
            const SizedBox(height: 16),
            _Bar(
              label: 'Instances',
              value: project.ratioFor('instances'),
              color: const Color(0xFF1F7A6D),
            ),
            _Bar(
              label: 'vCPU',
              value: project.ratioFor('vcpus'),
              color: const Color(0xFF2563EB),
            ),
            _Bar(
              label: 'Memory',
              value: project.ratioFor('memory_mb'),
              color: const Color(0xFF7C3AED),
            ),
            _Bar(
              label: 'Storage',
              value: project.ratioFor('storage_gb'),
              color: const Color(0xFFB45309),
            ),
          ],
        ),
      ),
    );
  }
}

class _Bar extends StatelessWidget {
  const _Bar({required this.label, required this.value, required this.color});

  final String label;
  final double value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final clamped = value.clamp(0.0, 1.0).toDouble();
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(label)),
              Text('${(clamped * 100).round()}%'),
            ],
          ),
          const SizedBox(height: 6),
          LinearProgressIndicator(value: clamped, color: color, minHeight: 7),
        ],
      ),
    );
  }
}

class _Grid extends StatelessWidget {
  const _Grid({required this.children, required this.minWidth});

  final List<Widget> children;
  final double minWidth;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final count = (constraints.maxWidth / minWidth)
            .floor()
            .clamp(1, 4)
            .toInt();
        const gap = 12.0;
        final width = (constraints.maxWidth - gap * (count - 1)) / count;
        return Wrap(
          spacing: gap,
          runSpacing: gap,
          children: children
              .map((item) => SizedBox(width: width, child: item))
              .toList(),
        );
      },
    );
  }
}

class _Empty extends StatelessWidget {
  const _Empty({required this.icon, required this.title, required this.detail});

  final IconData icon;
  final String title;
  final String detail;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 48),
      child: Center(
        child: Column(
          children: [
            Icon(icon, size: 38, color: Theme.of(context).colorScheme.outline),
            const SizedBox(height: 12),
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 4),
            Text(detail, textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}

class _Metric {
  const _Metric(this.label, this.value, this.progress, this.icon, this.color);

  final String label;
  final String value;
  final double progress;
  final IconData icon;
  final Color color;
}

String _quantity(CloudResource resource) =>
    '${resource.used} / ${resource.total}';

String _memory(CloudResource resource) =>
    '${_memoryValue(resource.used)} / ${_memoryValue(resource.total)}';

String _memoryValue(int megabytes) =>
    '${(megabytes / 1024).toStringAsFixed(megabytes % 1024 == 0 ? 0 : 1)} GB';

String _storage(CloudResource resource) =>
    '${_storageValue(resource.used)} / ${_storageValue(resource.total)}';

String _storageValue(int gigabytes) => gigabytes >= 1024
    ? '${(gigabytes / 1024).toStringAsFixed(1)} TB'
    : '$gigabytes GB';

String _titleCase(String value) =>
    value.isEmpty ? value : '${value[0].toUpperCase()}${value.substring(1)}';
